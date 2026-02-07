import asyncpg
import ssl
from typing import Any
from settings.config import get_settings

_pool: asyncpg.Pool | None = None

def _dsn() -> str:
    s = get_settings()
    return (
        f"postgresql://{s.SUPABASE_DB_USER}:{s.SUPABASE_DB_PASSWORD}"
        f"@{s.SUPABASE_DB_HOST}:{s.SUPABASE_DB_PORT}/{s.SUPABASE_DB_NAME}"
        f"?sslmode={s.SUPABASE_DB_SSLMODE}"
    )

async def connect_db() -> asyncpg.Pool:
    global _pool
    if _pool is not None:
        return _pool
    
    ssl_ctx = ssl.create_default_context()
    _pool = await asyncpg.create_pool(
        dsn=_dsn(),
        # ssl=ssl_ctx,
        min_size=1,
        max_size=10,
        command_timeout=60,
    )
    return _pool

async def close_db() -> None:
    global _pool
    if _pool is not None:
        await _pool.close()
        _pool = None

async def fetch_all(query: str, *args: Any):
    pool = await connect_db()
    async with pool.acquire() as conn:
        return await conn.fetch(query, *args)

async def fetch_one(query: str, *args: Any):
    pool = await connect_db()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def fetch_row(query: str, *args: Any):
    pool = await connect_db()
    async with pool.acquire() as conn:
        return await conn.fetchrow(query, *args)

async def execute(query: str, *args: Any):
    pool = await connect_db()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
