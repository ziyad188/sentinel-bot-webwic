from __future__ import annotations

import asyncpg
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.deps import get_current_user
from core.repositories.issues_repository import IssuesRepository
from core.schemas.issues import (
    IssueDetailResponse,
    IssueListResponse,
    LastIssueResponse,
    IssueStatusUpdateRequest,
    IssueStatusUpdateResponse,
)
from core.services.issues_service import IssuesService
from db.deps import get_pg_pool

router = APIRouter(prefix="/issues", tags=["issues"])


@router.get("", response_model=IssueListResponse)
async def list_issues(
    project_id: UUID = Query(...),
    severity: str | None = Query(None),
    category: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = IssuesService(IssuesRepository(pool))
        return await svc.list_issues(
            project_id=str(project_id),
            severity=severity,
            category=category,
            status=status,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.patch("/{issue_id}/status", response_model=IssueStatusUpdateResponse)
async def update_issue_status(
    issue_id: UUID,
    payload: IssueStatusUpdateRequest,
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = IssuesService(IssuesRepository(pool))
        return await svc.update_status(issue_id=str(issue_id), req=payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/last/issuedata", response_model=LastIssueResponse)
async def get_last_issue(
    project_id: UUID | None = Query(None),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = IssuesService(IssuesRepository(pool))
        return await svc.get_last_issue(
            project_id=str(project_id) if project_id else None,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        print("error", exc)
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/{issue_id}", response_model=IssueDetailResponse)
async def get_issue_detail(
    issue_id: UUID,
    project_id: UUID = Query(...),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = IssuesService(IssuesRepository(pool))
        return await svc.get_issue_detail(project_id=str(project_id), issue_id=str(issue_id))
    except RuntimeError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

