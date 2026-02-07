from __future__ import annotations

from datetime import datetime, time, timezone, timedelta

from core.repositories.widgets_repository import WidgetsRepository
from core.schemas.widgets import WidgetSummaryRequest, WidgetSummaryResponse


class WidgetsService:
    def __init__(self, repo: WidgetsRepository) -> None:
        self._repo = repo

    async def get_summary(self, req: WidgetSummaryRequest) -> WidgetSummaryResponse:
        start = datetime.combine(req.date, time.min, tzinfo=timezone.utc)
        end = datetime.combine(req.date, time.min, tzinfo=timezone.utc) + timedelta(days=1)

        data = await self._repo.get_summary(
            project_id=str(req.project_id),
            start=start,
            end=end,
        )

        return WidgetSummaryResponse(
            project_id=req.project_id,
            date=req.date,
            runs_count=data["runs_count"],
            issues_count=data["issues_count"],
            p0_count=data["p0_count"],
            p1_count=data["p1_count"],
            avg_issue_time_ms=data["avg_issue_time_ms"],
        )
