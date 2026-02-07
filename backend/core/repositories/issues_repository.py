from __future__ import annotations

from typing import Sequence

import asyncpg


class IssuesRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_issues(
        self,
        *,
        project_id: str,
        severity: str | None,
        category: str | None,
        status: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                i.id,
                i.project_id,
                i.title,
                i.description,
                i.severity,
                i.category,
                i.owner_team,
                i.status,
                i.created_at,
                i.resolved_at,
                i.run_id,
                i.slack_url,
                i.slack_user_id,
                su.display_name AS slack_display_name,
                su.real_name AS slack_real_name,
                su.email AS slack_email,
                su.avatar_url AS slack_avatar_url,
                r.device_id,
                d.name AS device_name,
                r.network_id,
                n.name AS network_name,
                r.locale
            FROM issues i
            LEFT JOIN slack_users su ON su.id = i.slack_user_id
            LEFT JOIN runs r ON r.id = i.run_id
            LEFT JOIN devices d ON d.id = r.device_id
            LEFT JOIN networks n ON n.id = r.network_id
            WHERE i.project_id = $1::uuid
              AND ($2::text IS NULL OR i.severity = $2)
              AND ($3::text IS NULL OR i.category = $3)
              AND ($4::text IS NULL OR i.status = $4)
            ORDER BY i.created_at DESC
            LIMIT $5 OFFSET $6
        """
        count_query = """
            SELECT COUNT(*)
            FROM issues i
            WHERE i.project_id = $1::uuid
              AND ($2::text IS NULL OR i.severity = $2)
              AND ($3::text IS NULL OR i.category = $3)
              AND ($4::text IS NULL OR i.status = $4)
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, project_id, severity, category, status, limit, offset)
            total = await conn.fetchval(count_query, project_id, severity, category, status)

        return rows, int(total or 0)

    async def update_issue_status(
        self,
        *,
        issue_id: str,
        status: str,
    ) -> asyncpg.Record:
        query = """
            UPDATE issues
            SET status = $2,
                resolved_at = CASE WHEN $2 = 'resolved' THEN NOW() ELSE resolved_at END
            WHERE id = $1
            RETURNING id, status
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, issue_id, status)

    async def get_issue_detail(
        self,
        *,
        project_id: str,
        issue_id: str,
    ) -> asyncpg.Record | None:
        query = """
            SELECT
                i.id,
                i.project_id,
                i.title,
                i.description,
                i.severity,
                i.category,
                i.owner_team,
                i.status,
                i.created_at,
                i.resolved_at,
                i.run_id,
                i.slack_url,
                i.slack_user_id,
                su.display_name AS owner_name
            FROM issues i
            LEFT JOIN slack_users su ON su.id = i.slack_user_id
            WHERE i.project_id = $1
              AND i.id = $2
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, project_id, issue_id)

    async def list_issue_media(self, *, issue_id: str) -> Sequence[asyncpg.Record]:
        query = """
            SELECT
                id,
                issue_id,
                type,
                storage_path,
                label,
                created_at
            FROM evidence
            WHERE issue_id = $1
              AND type = 'screenshot'
            ORDER BY created_at ASC
        """
        async with self._pool.acquire() as conn:
            return await conn.fetch(query, issue_id)

    async def get_last_issue(
        self,
        *,
        project_id: str | None,
    ) -> asyncpg.Record | None:
        query = """
            SELECT
                i.id,
                i.project_id,
                i.title,
                i.description,
                i.severity,
                i.slack_url,
                i.slack_user_id,
                su.display_name AS owner_name,
                r.device_id,
                d.name AS device_name,
                r.network_id,
                n.name AS network_name,
                i.created_at
            FROM issues i
            LEFT JOIN slack_users su ON su.id = i.slack_user_id
            LEFT JOIN runs r ON r.id = i.run_id
            LEFT JOIN devices d ON d.id = r.device_id
            LEFT JOIN networks n ON n.id = r.network_id
            WHERE ($1::uuid IS NULL OR i.project_id = $1::uuid)
            ORDER BY i.created_at DESC NULLS LAST, i.id DESC
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, project_id)
