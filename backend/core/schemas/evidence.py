from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class EvidenceListItem(BaseModel):
    id: UUID
    project_id: UUID
    run_id: str
    issue_id: Optional[UUID] = None
    issue_title: Optional[str] = None
    type: str
    storage_path: str
    label: Optional[str] = None
    created_at: Optional[datetime] = None
    device_id: Optional[UUID] = None
    device_name: Optional[str] = None
    url: str


class EvidenceListResponse(BaseModel):
    items: list[EvidenceListItem]
    total: int
    page: int
    page_size: int
