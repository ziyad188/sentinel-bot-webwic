from __future__ import annotations

from typing import Sequence

import asyncpg


class EvidenceRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_evidence(
        self,
        *,
        project_id: str,
        media_type: str | None,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                e.id,
                e.run_id,
                e.issue_id,
                e.type,
                e.storage_path,
                e.label,
                e.created_at,
                r.project_id,
                r.device_id,
                d.name AS device_name,
                i.title AS issue_title
            FROM evidence e
            LEFT JOIN runs r ON r.id = e.run_id
            LEFT JOIN devices d ON d.id = r.device_id
            LEFT JOIN issues i ON i.id = e.issue_id
            WHERE r.project_id = $1::uuid
              AND ($2::text IS NULL OR e.type = $2)
            ORDER BY e.created_at DESC
            LIMIT $3 OFFSET $4
        """
        count_query = """
            SELECT COUNT(*)
            FROM evidence e
            LEFT JOIN runs r ON r.id = e.run_id
            WHERE r.project_id = $1::uuid
              AND ($2::text IS NULL OR e.type = $2)
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, project_id, media_type, limit, offset)
            total = await conn.fetchval(count_query, project_id, media_type)

        return rows, int(total or 0)
