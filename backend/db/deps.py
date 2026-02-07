import asyncpg

from db.supabase import connect_db


async def get_pg_pool() -> asyncpg.Pool:
    return await connect_db()
