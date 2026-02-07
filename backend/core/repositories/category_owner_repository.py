from __future__ import annotations

import asyncpg


class CategoryOwnerRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def get_slack_user(self, *, slack_user_id: str) -> asyncpg.Record | None:
        query = """
            SELECT
                slack_user_id,
                display_name,
                real_name,
                email,
                is_active
            FROM slack_users
            WHERE slack_user_id = $1
            LIMIT 1
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, slack_user_id)

    async def create_owner(
        self,
        *,
        category_id: str,
        slack_user_id: str,
        display_name: str,
        real_name: str,
        email: str | None,
        is_active: bool | None,
    ) -> asyncpg.Record:
        query = """
            INSERT INTO slack_category_owners (
                category_id,
                slack_user_id,
                display_name,
                real_name,
                email,
                is_active
            )
            VALUES ($1::uuid, $2, $3, $4, $5, $6)
            RETURNING category_id, slack_user_id, display_name, real_name, email, is_active
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(
                query,
                category_id,
                slack_user_id,
                display_name,
                real_name,
                email,
                is_active,
            )
