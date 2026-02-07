from __future__ import annotations

import asyncio

from settings import get_settings
from utils.storage import sign_storage_path
from core.repositories.evidence_repository import EvidenceRepository
from core.schemas.evidence import EvidenceListItem, EvidenceListResponse


class EvidenceService:
    def __init__(self, repo: EvidenceRepository) -> None:
        self._repo = repo

    async def list_evidence(
        self,
        *,
        project_id: str,
        media_type: str | None,
        page: int,
        page_size: int,
    ) -> EvidenceListResponse:
        limit = page_size
        offset = (page - 1) * page_size
        rows, total = await self._repo.list_evidence(
            project_id=project_id,
            media_type=media_type,
            limit=limit,
            offset=offset,
        )

        settings = get_settings()

        async def build_item(row):
            bucket = (
                settings.STORAGE_BUCKET_SCREENSHOTS
                if row["type"] == "screenshot"
                else settings.STORAGE_BUCKET_VIDEOS
            )
            url = await sign_storage_path(bucket, row["storage_path"])
            run_display_id = None
            if row["run_id"]:
                run_display_id = f"RUN-{str(row['run_id'])[:8].upper()}"
            return EvidenceListItem(
                id=row["id"],
                project_id=row["project_id"],
                run_id=run_display_id or "",
                issue_id=row["issue_id"],
                issue_title=row["issue_title"],
                type=row["type"],
                storage_path=row["storage_path"],
                label=row["label"],
                created_at=row["created_at"],
                device_id=row["device_id"],
                device_name=row["device_name"],
                url=url,
            )

        items = await asyncio.gather(*(build_item(r) for r in rows))

        return EvidenceListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )
