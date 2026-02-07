from __future__ import annotations

from datetime import date
from uuid import UUID

from pydantic import BaseModel


class WidgetSummaryRequest(BaseModel):
    project_id: UUID
    date: date  # YYYY-MM-DD (UTC)


class WidgetSummaryResponse(BaseModel):
    project_id: UUID
    date: date
    runs_count: int
    issues_count: int
    p0_count: int
    p1_count: int
    avg_issue_time_ms: int | None
