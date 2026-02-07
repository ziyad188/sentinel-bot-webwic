from __future__ import annotations

from core.repositories.runs_repository import RunsRepository
import asyncio

from settings import get_settings
from utils.storage import sign_storage_path
from core.schemas.runs import (
    IssueSummary,
    RunCreateRequest,
    RunCreateResponse,
    RunListItem,
    RunListResponse,
    RunIssuesResponse,
    IssueDetail,
    EvidenceItem,
    RunningRunItem,
    RunningRunListResponse,
)


class RunsService:
    def __init__(self, repo: RunsRepository) -> None:
        self._repo = repo

    async def create_run(self, req: RunCreateRequest) -> RunCreateResponse:
        data = await self._repo.create_run(
            project_id=str(req.project_id),
            device_id=str(req.device_id),
            network_id=str(req.network_id),
            locale=req.locale,
            persona=req.persona,
            input_data=req.input_data,
        )
        return RunCreateResponse.model_validate(data)

    async def list_runs(
        self,
        *,
        pool,
        project_id: str,
        status: str | None,
        severity: str | None,
        page: int,
        page_size: int,
    ) -> RunListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_runs(
            pool=pool,
            project_id=project_id,
            status=status,
            severity=severity,
            limit=limit,
            offset=offset,
        )

        run_ids = [str(r["id"]) for r in rows]
        try:
            issue_rows = await self._repo.list_issues_for_runs(pool=pool, run_ids=run_ids)
        except Exception as e:
            print(e)
        issues_by_run: dict[str, list[IssueSummary]] = {}
        for issue in issue_rows:
            run_id = str(issue["run_id"])
            issues_by_run.setdefault(run_id, []).append(
                IssueSummary(
                    id=issue["id"],
                    title=issue.get("title"),
                    severity=issue.get("severity"),
                    status=issue.get("status"),
                )
            )

        items: list[RunListItem] = []
        for row in rows:
            run_id = str(row["id"])
            display_id = f"RUN-{run_id[:8].upper()}"
            result = row.get("result")
            issues = issues_by_run.get(run_id, [])
            if result is None and issues:
                result = "issue_found"

            items.append(
                RunListItem(
                    id=row["id"],
                    display_id=display_id,
                    started_at=row.get("started_at"),
                    duration_ms=row.get("duration_ms"),
                    device_id=row.get("device_id"),
                    device_name=row.get("device_name"),
                    network_id=row.get("network_id"),
                    network_name=row.get("network_name"),
                    locale=row.get("locale"),
                    status=row.get("status"),
                    result=result,
                    issues=issues,
                )
            )

        return RunListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_run_issues(
        self,
        *,
        pool,
        project_id: str,
        run_id: str,
    ) -> RunIssuesResponse:
        issue_rows = await self._repo.list_run_issues(
            pool=pool,
            project_id=project_id,
            run_id=run_id,
        )
        evidence_rows = await self._repo.list_run_evidence(pool=pool, run_id=run_id)

        issues: list[IssueDetail] = []
        for idx, row in enumerate(issue_rows):
            issues.append(
                IssueDetail(
                    idx=idx,
                    id=row["id"],
                    project_id=row["project_id"],
                    title=row["title"],
                    description=row["description"],
                    severity=row["severity"],
                    category=row["category"],
                    owner_team=row["owner_team"],
                    status=row["status"],
                    created_at=row["created_at"],
                    resolved_at=row["resolved_at"],
                    run_id=row["run_id"],
                    slack_url=row["slack_url"],
                )
            )

        settings = get_settings()

        async def build_media(row):
            bucket = (
                settings.STORAGE_BUCKET_SCREENSHOTS
                if row["type"] == "screenshot"
                else settings.STORAGE_BUCKET_VIDEOS
            )
            url = await sign_storage_path(bucket, row["storage_path"])
            return EvidenceItem(
                id=row["id"],
                run_id=row["run_id"],
                issue_id=row["issue_id"],
                type=row["type"],
                storage_path=row["storage_path"],
                label=row["label"],
                created_at=row["created_at"],
                url=url,
            )

        media = await asyncio.gather(*(build_media(r) for r in evidence_rows))

        return RunIssuesResponse(
            project_id=str(project_id),
            run_id=str(run_id),
            issues=issues,
            media=media,
        )

    async def list_running_runs(self, *, pool) -> RunningRunListResponse:
        rows = await self._repo.list_running_runs(pool=pool)
        items: list[RunningRunItem] = []
        for row in rows:
            run_id = str(row["id"])
            display_id = f"RUN-{run_id[:8].upper()}"
            items.append(
                RunningRunItem(
                    id=row["id"],
                    display_id=display_id,
                    started_at=row["started_at"],
                    device_id=row["device_id"],
                    device_name=row["device_name"],
                    network_id=row["network_id"],
                    network_name=row["network_name"],
                )
            )
        return RunningRunListResponse(items=items)
