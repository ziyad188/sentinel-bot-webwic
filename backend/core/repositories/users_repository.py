from __future__ import annotations

from typing import Sequence

import asyncpg


class UsersRepository:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_users(self, *, limit: int, offset: int) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                id,
                slack_user_id,
                display_name,
                real_name,
                email,
                avatar_url,
                is_active,
                created_at,
                updated_at,
                uuid_id
            FROM slack_users
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM slack_users"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            total = await conn.fetchval(count_query)

        return rows, int(total or 0)

    async def create_user(
        self,
        *,
        conn: asyncpg.Connection,
        slack_user_id: str,
        display_name: str,
        real_name: str,
        email: str | None,
        is_active: bool | None,
        avatar_url: str | None,
    ) -> asyncpg.Record:
        query = """
            INSERT INTO slack_users (
                slack_user_id,
                display_name,
                real_name,
                email,
                avatar_url,
                is_active
            )
            VALUES ($1, $2, $3, $4, $5, $6)
            RETURNING id, slack_user_id, display_name, real_name, email, is_active
        """
        return await conn.fetchrow(
            query,
            slack_user_id,
            display_name,
            real_name,
            email,
            avatar_url,
            is_active,
        )

    async def add_category_owners(
        self,
        *,
        conn: asyncpg.Connection,
        project_id: str,
        slack_user_id: str,
        categories: list[str],
    ) -> None:
        if not categories:
            return
        query = """
            INSERT INTO slack_category_owners (
                project_id,
                category,
                slack_user_id
            )
            VALUES ($1::uuid, $2, $3)
        """
        await conn.executemany(
            query,
            [(project_id, category, slack_user_id) for category in categories],
        )

    async def list_users_with_categories(
        self, *, limit: int, offset: int
    ) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                su.id,
                su.slack_user_id,
                su.display_name,
                su.real_name,
                su.email,
                su.avatar_url,
                su.is_active,
                su.created_at,
                su.updated_at,
                COALESCE(
                    ARRAY_AGG(DISTINCT c.category) FILTER (WHERE c.category IS NOT NULL),
                    ARRAY[]::text[]
                ) AS categories
            FROM slack_users su
            LEFT JOIN slack_category_owners c ON c.slack_user_id = su.slack_user_id
            GROUP BY
                su.id,
                su.slack_user_id,
                su.display_name,
                su.real_name,
                su.email,
                su.avatar_url,
                su.is_active,
                su.created_at,
                su.updated_at
            ORDER BY su.created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM slack_users"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            total = await conn.fetchval(count_query)

        return rows, int(total or 0)
