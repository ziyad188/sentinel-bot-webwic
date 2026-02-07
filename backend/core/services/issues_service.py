from __future__ import annotations
import traceback

from core.repositories.issues_repository import IssuesRepository
import asyncio

from settings import get_settings
from utils.storage import sign_storage_path
from core.schemas.issues import (
    IssueDetailResponse,
    IssueListItem,
    IssueListResponse,
    IssueMediaItem,
    LastIssueMediaItem,
    LastIssueResponse,
    IssueStatusUpdateRequest,
    IssueStatusUpdateResponse,
)


class IssuesService:
    def __init__(self, repo: IssuesRepository) -> None:
        self._repo = repo

    async def list_issues(
        self,
        *,
        project_id: str,
        severity: str | None,
        category: str | None,
        status: str | None,
        page: int,
        page_size: int,
    ) -> IssueListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        try:
            rows, total = await self._repo.list_issues(
                project_id=str(project_id),
                severity=severity,
                category=category,
                status=status,
                limit=limit,
                offset=offset,
            )
        except Exception as e:
            traceback.print_exc()
            raise

        items: list[IssueListItem] = []
        for idx, row in enumerate(rows):
            items.append(
                IssueListItem(
                    idx=idx,
                    id=str(row["id"]),
                    project_id=str(row["project_id"]),
                    title=row["title"],
                    description=row["description"],
                    severity=row["severity"],
                    category=row["category"],
                    owner_team=row["owner_team"],
                    status=row["status"],
                    created_at=row["created_at"],
                    resolved_at=row["resolved_at"],
                    run_id=str(row["run_id"]) if row["run_id"] else None,
                    slack_url=row["slack_url"],
                    slack_user_id=row["slack_user_id"],
                    slack_display_name=row["slack_display_name"],
                    slack_real_name=row["slack_real_name"],
                    slack_email=row["slack_email"],
                    slack_avatar_url=row["slack_avatar_url"],
                    device_id=str(row["device_id"]) if row["device_id"] else None,
                    device_name=row["device_name"],
                    network_id=str(row["network_id"]) if row["network_id"] else None,
                    network_name=row["network_name"],
                    locale=row["locale"],
                )
            )

        return IssueListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def update_status(
        self,
        *,
        issue_id: str,
        req: IssueStatusUpdateRequest,
    ) -> IssueStatusUpdateResponse:
        row = await self._repo.update_issue_status(issue_id=issue_id, status=req.status)
        if not row:
            raise RuntimeError("Issue not found")
        return IssueStatusUpdateResponse(id=str(row["id"]), status=row["status"])

    async def get_issue_detail(
        self,
        *,
        project_id: str,
        issue_id: str,
    ) -> IssueDetailResponse:
        try:
            row = await self._repo.get_issue_detail(project_id=project_id, issue_id=issue_id)
        except Exception as e:
            traceback.print_exc
            raise
        if not row:
            raise RuntimeError("Issue not found")

        settings = get_settings()

        async def build_media(item):
            bucket = settings.STORAGE_BUCKET_SCREENSHOTS
            url = await sign_storage_path(bucket, item["storage_path"])
            return IssueMediaItem(
                id=str(item["id"]),
                issue_id=str(item["issue_id"]),
                type=item["type"],
                storage_path=item["storage_path"],
                label=item["label"],
                created_at=item["created_at"],
                url=url,
            )

        media_rows = await self._repo.list_issue_media(issue_id=str(issue_id))
        media = await asyncio.gather(*(build_media(m) for m in media_rows))

        run_id = row["run_id"]
        run_display_id = None
        if run_id:
            run_display_id = f"RUN-{str(run_id)[:8].upper()}"

        return IssueDetailResponse(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            title=row["title"],
            description=row["description"],
            severity=row["severity"],
            category=row["category"],
            owner_team=row["owner_team"],
            status=row["status"],
            created_at=row["created_at"],
            resolved_at=row["resolved_at"],
            run_id=str(row["run_id"]) if row["run_id"] else None,
            run_display_id=run_display_id,
            slack_url=row["slack_url"],
            slack_user_id=row["slack_user_id"],
            owner_name=row["owner_name"],
            media=media,
        )

    async def get_last_issue(
        self,
        *,
        project_id: str | None,
    ) -> LastIssueResponse:
        row = await self._repo.get_last_issue(project_id=project_id)
        if not row:
            raise RuntimeError("No issues found")

        media_rows = await self._repo.list_issue_media(issue_id=str(row["id"]))
        settings = get_settings()

        async def build_media(item):
            url = await sign_storage_path(settings.STORAGE_BUCKET_SCREENSHOTS, item["storage_path"])
            return LastIssueMediaItem(
                id=str(item["id"]),
                storage_path=item["storage_path"],
                label=item["label"],
                created_at=item["created_at"],
                url=url,
            )

        media = await asyncio.gather(*(build_media(m) for m in media_rows))

        return LastIssueResponse(
            id=str(row["id"]),
            project_id=str(row["project_id"]),
            title=row["title"],
            description=row["description"],
            severity=row["severity"],
            slack_url=row["slack_url"],
            slack_user_id=str(row["slack_user_id"]) if row["slack_user_id"] else None,
            owner_name=row["owner_name"],
            device_name=row["device_name"],
            network_name=row["network_name"],
            created_at=row["created_at"],
            media=media,
        )
