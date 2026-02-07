from __future__ import annotations

import asyncpg
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query

from core.auth.deps import get_current_user
from core.repositories.evidence_repository import EvidenceRepository
from core.schemas.evidence import EvidenceListResponse
from core.services.evidence_service import EvidenceService
from db.deps import get_pg_pool

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("", response_model=EvidenceListResponse)
async def list_evidence(
    project_id: UUID = Query(...),
    media_type: str | None = Query(None, description="screenshot | video"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = EvidenceService(EvidenceRepository(pool))
        return await svc.list_evidence(
            project_id=str(project_id),
            media_type=media_type,
            page=page,
            page_size=page_size,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
