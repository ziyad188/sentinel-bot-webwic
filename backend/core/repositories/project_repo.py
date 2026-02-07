from __future__ import annotations

import asyncpg


class ProjectRepo:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def create_project(self, *, name: str, environment: str, target_url: str) -> asyncpg.Record:
        query = """
            INSERT INTO projects (name, environment, target_url)
            VALUES ($1, $2, $3)
            RETURNING id, name, environment, target_url
        """
        async with self._pool.acquire() as conn:
            return await conn.fetchrow(query, name, environment, target_url)
