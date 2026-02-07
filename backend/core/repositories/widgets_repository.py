from __future__ import annotations

from datetime import datetime

import asyncpg


class WidgetsRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_summary(
        self,
        *,
        project_id: str,
        start: datetime,
        end: datetime,
    ) -> dict:
        runs_query = """
            SELECT COUNT(*)
            FROM runs
            WHERE project_id = $1::uuid
              AND started_at >= $2
              AND started_at < $3
        """
        issues_query = """
            SELECT
                COUNT(*) AS issues_count,
                COUNT(*) FILTER (WHERE severity = 'P0') AS p0_count,
                COUNT(*) FILTER (WHERE severity = 'P1') AS p1_count
            FROM issues
            WHERE project_id = $1::uuid
              AND created_at >= $2
              AND created_at < $3
        """
        avg_time_query = """
            SELECT AVG(EXTRACT(EPOCH FROM (i.created_at - r.started_at)) * 1000) AS avg_ms
            FROM issues i
            JOIN runs r ON r.id = i.run_id
            WHERE i.project_id = $1::uuid
              AND i.created_at >= $2
              AND i.created_at < $3
              AND r.started_at IS NOT NULL
        """

        async with self._pool.acquire() as conn:
            runs_count = await conn.fetchval(runs_query, project_id, start, end)
            issue_row = await conn.fetchrow(issues_query, project_id, start, end)
            avg_ms = await conn.fetchval(avg_time_query, project_id, start, end)

        return {
            "runs_count": int(runs_count or 0),
            "issues_count": int(issue_row["issues_count"] or 0),
            "p0_count": int(issue_row["p0_count"] or 0),
            "p1_count": int(issue_row["p1_count"] or 0),
            "avg_issue_time_ms": int(avg_ms) if avg_ms is not None else None,
        }
