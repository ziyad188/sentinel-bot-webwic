from __future__ import annotations

import asyncpg
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, status

from core.auth.deps import get_current_user
from core.repositories.runs_repository import RunsRepository
from core.schemas.runs import (
    RunCreateRequest,
    RunCreateResponse,
    RunIssuesResponse,
    RunListResponse,
    RunningRunListResponse,
)
from core.services.runs_service import RunsService
from db.deps import get_pg_pool

router = APIRouter(prefix="/runs", tags=["runs"])


@router.post("", response_model=RunCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: RunCreateRequest,
    _user=Depends(get_current_user),
):
    try:
        svc = RunsService(RunsRepository())
        return await svc.create_run(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("", response_model=RunListResponse)
async def list_runs(
    project_id: UUID = Query(...),
    status: str | None = Query(None),
    severity: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = RunsService(RunsRepository())
        return await svc.list_runs(
            pool=pool,
            project_id=str(project_id),
            status=status,
            severity=severity,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{run_id}/issues", response_model=RunIssuesResponse)
async def get_run_issues(
    run_id: UUID,
    project_id: UUID = Query(...),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = RunsService(RunsRepository())
        return await svc.get_run_issues(
            pool=pool,
            project_id=str(project_id),
            run_id=str(run_id),
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/running", response_model=RunningRunListResponse)
async def list_running_runs(
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = RunsService(RunsRepository())
        return await svc.list_running_runs(pool=pool)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
