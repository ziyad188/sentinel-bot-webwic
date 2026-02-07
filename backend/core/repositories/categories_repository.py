from __future__ import annotations

from typing import Sequence

import asyncpg


class CategoriesRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_categories(
        self,
        *,
        project_id: str,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                c.id,
                c.project_id,
                c.category,
                c.slack_user_id,
                c.created_at,
                c.updated_at,
                su.display_name AS slack_display_name,
                su.real_name AS slack_real_name
            FROM slack_category_owners c
            LEFT JOIN slack_users su ON su.slack_user_id = c.slack_user_id
            WHERE c.project_id = $1::uuid
            ORDER BY c.created_at DESC
            LIMIT $2 OFFSET $3
        """
        count_query = """
            SELECT COUNT(*)
            FROM slack_category_owners c
            WHERE c.project_id = $1::uuid
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, project_id, limit, offset)
            total = await conn.fetchval(count_query, project_id)

        return rows, int(total or 0)

    async def list_category_options(
        self,
        *,
        limit: int,
        offset: int,
    ) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                id,
                category
            FROM slack_category_owners
            ORDER BY category ASC
            LIMIT $1 OFFSET $2
        """
        count_query = """
            SELECT COUNT(*)
            FROM slack_category_owners
        """

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            total = await conn.fetchval(count_query)

        return rows, int(total or 0)
