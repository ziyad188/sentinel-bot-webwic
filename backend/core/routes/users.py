from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.deps import get_current_user
from core.repositories.users_repository import UsersRepository
from core.schemas.users import (
    SlackUserCreateRequest,
    SlackUserCreateResponse,
    SlackUserListResponse,
    SlackUserWithCategoriesResponse,
)
from core.services.users_service import UsersService
from db.deps import get_pg_pool

router = APIRouter(prefix="/users", tags=["users"])


@router.get("", response_model=SlackUserListResponse)
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = UsersService(UsersRepository(pool))
        return await svc.list_users(page=page, page_size=page_size)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/with-categories", response_model=SlackUserWithCategoriesResponse)
async def list_users_with_categories(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = UsersService(UsersRepository(pool))
        return await svc.list_users_with_categories(page=page, page_size=page_size)
    except Exception as exc:
        print("ee",exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("", response_model=SlackUserCreateResponse, status_code=201)
async def create_user(
    payload: SlackUserCreateRequest,
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = UsersService(UsersRepository(pool))
        return await svc.create_user(req=payload)
    except Exception as exc:
        print("exec", exc)
        raise HTTPException(status_code=400, detail=str(exc))
