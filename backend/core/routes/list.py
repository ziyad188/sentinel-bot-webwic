from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, Query

from core.auth.deps import get_current_user
from core.repositories.list_repo import ListRepo
from core.schemas.list import DeviceListResponse, NetworkListResponse, ProjectListResponse
from core.services.list_service import ListService
from db.deps import get_pg_pool

router = APIRouter(prefix="/list", tags=["list"])


@router.get("/devices", response_model=DeviceListResponse)
async def list_devices(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    svc = ListService(ListRepo(pool))
    return await svc.list_devices(page=page, page_size=page_size)


@router.get("/networks", response_model=NetworkListResponse)
async def list_networks(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    svc = ListService(ListRepo(pool))
    return await svc.list_networks(page=page, page_size=page_size)


@router.get("/projects", response_model=ProjectListResponse)
async def list_projects(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    svc = ListService(ListRepo(pool))
    return await svc.list_projects(page=page, page_size=page_size)
