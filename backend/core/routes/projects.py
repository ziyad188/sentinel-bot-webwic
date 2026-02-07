from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from core.auth.deps import get_current_user
from core.repositories.project_repo import ProjectRepo
from core.schemas.projects import ProjectCreateRequest, ProjectCreateResponse
from core.services.project_service import ProjectService
from db.deps import get_pg_pool

router = APIRouter(prefix="/projects", tags=["projects"])


@router.post("", response_model=ProjectCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    payload: ProjectCreateRequest,
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = ProjectService(ProjectRepo(pool))
        return await svc.create_project(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
