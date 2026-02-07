from __future__ import annotations

import asyncpg
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.deps import get_current_user
from core.repositories.categories_repository import CategoriesRepository
from core.schemas.categories import (
    CategoryListResponse,
    CategoryOptionsResponse,
    CategoryOwnerCreateRequest,
    CategoryOwnerResponse,
)
from core.repositories.category_owner_repository import CategoryOwnerRepository
from core.services.category_owner_service import CategoryOwnerService
from core.services.categories_service import CategoriesService
from db.deps import get_pg_pool

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
async def list_categories(
    project_id: UUID = Query(...),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = CategoriesService(CategoriesRepository(pool))
        return await svc.list_categories(
            project_id=str(project_id),
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/options", response_model=CategoryOptionsResponse)
async def list_category_options(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = CategoriesService(CategoriesRepository(pool))
        return await svc.list_category_options(
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/owner", response_model=CategoryOwnerResponse)
async def create_category_owner(
    payload: CategoryOwnerCreateRequest,
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = CategoryOwnerService(CategoryOwnerRepository(pool))
        return await svc.create_owner(payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
