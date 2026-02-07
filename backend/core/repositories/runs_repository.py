from __future__ import annotations

from typing import Any, Dict, Sequence

import httpx

from settings import get_settings


class RunsRepository:
    def __init__(self) -> None:
        self._s = get_settings()

    def _base_url(self) -> str:
        return (self._s.TEST_SERVICE_URL or "").rstrip("/")

    async def create_run(
        self,
        *,
        project_id: str,
        device_id: str,
        network_id: str,
        locale: str,
        persona: str | None,
        input_data: dict | None,
    ) -> Dict[str, Any]:
        if not self._base_url():
            raise RuntimeError("TEST_SERVICE_URL is not configured")

        url = f"{self._base_url()}/api/test"
        payload: Dict[str, Any] = {
            "project_id": project_id,
            "device_id": device_id,
            "network_id": network_id,
            "locale": locale,
            "persona": persona,
            "continous_monitoring": False,
        }
        if input_data is not None:
            payload["input_data"] = input_data

        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(url, json=payload)
            

        if resp.status_code >= 400:
            raise RuntimeError(f"Test service failed: {resp.status_code} {resp.text}")

        return resp.json()

    async def list_runs(
        self,
        *,
        pool,
        project_id: str,
        status: str | None,
        severity: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[Any], int]:
        query = """
            SELECT
                r.id,
                r.status,
                r.result,
                r.locale,
                r.started_at,
                r.duration_ms,
                r.device_id,
                d.name AS device_name,
                r.network_id,
                n.name AS network_name
            FROM runs r
            LEFT JOIN devices d ON d.id = r.device_id
            LEFT JOIN networks n ON n.id = r.network_id
            WHERE r.project_id = $1
              AND ($2::text IS NULL OR r.status = $2)
              AND (
                $3::text IS NULL
                OR EXISTS (
                    SELECT 1
                    FROM issues i
                    WHERE i.run_id = r.id
                      AND i.severity = $3
                )
              )
            ORDER BY r.started_at DESC NULLS LAST, r.id DESC
            LIMIT $4 OFFSET $5
        """
        count_query = """
            SELECT COUNT(*)
            FROM runs r
            WHERE r.project_id = $1
              AND ($2::text IS NULL OR r.status = $2)
              AND (
                $3::text IS NULL
                OR EXISTS (
                    SELECT 1
                    FROM issues i
                    WHERE i.run_id = r.id
                      AND i.severity = $3
                )
              )
        """

        async with pool.acquire() as conn:
            rows = await conn.fetch(query, project_id, status, severity, limit, offset)
            total = await conn.fetchval(count_query, project_id, status, severity)

        return rows, int(total or 0)

    async def list_running_runs(self, *, pool) -> Sequence[Any]:
        query = """
            SELECT
                r.id,
                r.started_at,
                r.device_id,
                d.name AS device_name,
                r.network_id,
                n.name AS network_name
            FROM runs r
            LEFT JOIN devices d ON d.id = r.device_id
            LEFT JOIN networks n ON n.id = r.network_id
            WHERE r.status = 'running'
            ORDER BY r.started_at DESC NULLS LAST, r.id DESC
        """
        async with pool.acquire() as conn:
            return await conn.fetch(query)

    async def list_issues_for_runs(self, *, pool, run_ids: list[str]) -> Sequence[Any]:
        if not run_ids:
            return []
        query = """
            SELECT
                id,
                run_id,
                title,
                severity,
                status
            FROM issues
            WHERE run_id = ANY($1::uuid[])
            ORDER BY created_at DESC
        """
        async with pool.acquire() as conn:
            return await conn.fetch(query, run_ids)

    async def list_run_issues(
        self,
        *,
        pool,
        project_id: str,
        run_id: str,
    ) -> Sequence[Any]:
        query = """
            SELECT
                id,
                project_id,
                title,
                description,
                severity,
                category,
                owner_team,
                status,
                created_at,
                resolved_at,
                run_id,
                slack_url
            FROM issues
            WHERE project_id = $1
              AND run_id = $2
            ORDER BY created_at DESC
        """
        async with pool.acquire() as conn:
            return await conn.fetch(query, project_id, run_id)

    async def list_run_evidence(self, *, pool, run_id: str) -> Sequence[Any]:
        query = """
            SELECT
                id,
                run_id,
                issue_id,
                type,
                storage_path,
                label,
                created_at
            FROM evidence
            WHERE run_id = $1
            ORDER BY created_at ASC
        """
        async with pool.acquire() as conn:
            return await conn.fetch(query, run_id)
