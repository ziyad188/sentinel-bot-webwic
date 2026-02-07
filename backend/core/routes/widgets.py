from __future__ import annotations

import asyncpg
from fastapi import APIRouter, Depends, HTTPException

from core.auth.deps import get_current_user
from core.repositories.widgets_repository import WidgetsRepository
from core.schemas.widgets import WidgetSummaryRequest, WidgetSummaryResponse
from core.services.widgets_service import WidgetsService
from db.deps import get_pg_pool

router = APIRouter(prefix="/widgets", tags=["widgets"])


@router.post("/summary", response_model=WidgetSummaryResponse)
async def get_widget_summary(
    payload: WidgetSummaryRequest,
    _user=Depends(get_current_user),
    pool: asyncpg.Pool = Depends(get_pg_pool),
):
    try:
        svc = WidgetsService(WidgetsRepository(pool))
        return await svc.get_summary(payload)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
