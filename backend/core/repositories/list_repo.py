from __future__ import annotations

from typing import Sequence

import asyncpg


class ListRepo:
    def __init__(self, pool: asyncpg.Pool) -> None:
        self._pool = pool

    async def list_devices(self, *, limit: int, offset: int) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                id,
                name
            FROM devices
            ORDER BY sort_order ASC, created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM devices"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            total = await conn.fetchval(count_query)

        return rows, int(total or 0)

    async def list_networks(self, *, limit: int, offset: int) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                id,
                name
            FROM networks
            ORDER BY sort_order ASC, created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM networks"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            total = await conn.fetchval(count_query)

        return rows, int(total or 0)

    async def list_projects(self, *, limit: int, offset: int) -> tuple[Sequence[asyncpg.Record], int]:
        query = """
            SELECT
                id,
                name,
                environment
            FROM projects
            ORDER BY created_at DESC
            LIMIT $1 OFFSET $2
        """
        count_query = "SELECT COUNT(*) FROM projects"

        async with self._pool.acquire() as conn:
            rows = await conn.fetch(query, limit, offset)
            total = await conn.fetchval(count_query)

        return rows, int(total or 0)
