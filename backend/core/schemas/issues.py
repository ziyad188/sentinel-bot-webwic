from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from typing import Literal

from pydantic import BaseModel


IssueStatus = Literal["investigating", "resolved"]


class IssueListItem(BaseModel):
    idx: int
    id: UUID
    project_id: UUID
    title: str
    description: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    owner_team: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    run_id: Optional[UUID] = None
    slack_url: Optional[str] = None
    slack_user_id: Optional[str] = None
    slack_display_name: Optional[str] = None
    slack_real_name: Optional[str] = None
    slack_email: Optional[str] = None
    slack_avatar_url: Optional[str] = None
    device_id: Optional[UUID] = None
    device_name: Optional[str] = None
    network_id: Optional[UUID] = None
    network_name: Optional[str] = None
    locale: Optional[str] = None


class IssueListResponse(BaseModel):
    items: list[IssueListItem]
    total: int
    page: int
    page_size: int


class IssueStatusUpdateRequest(BaseModel):
    status: IssueStatus


class IssueStatusUpdateResponse(BaseModel):
    id: UUID
    status: IssueStatus


class IssueMediaItem(BaseModel):
    id: UUID
    issue_id: UUID
    type: str
    storage_path: str
    label: Optional[str] = None
    created_at: Optional[datetime] = None
    url: str


class IssueDetailResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: Optional[str] = None
    severity: Optional[str] = None
    category: Optional[str] = None
    owner_team: Optional[str] = None
    status: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    run_id: Optional[UUID] = None
    run_display_id: Optional[str] = None
    slack_url: Optional[str] = None
    slack_user_id: Optional[str] = None
    owner_name: Optional[str] = None
    media: list[IssueMediaItem] = []


class LastIssueMediaItem(BaseModel):
    id: UUID
    storage_path: str
    label: Optional[str] = None
    created_at: Optional[datetime] = None
    url: str


class LastIssueResponse(BaseModel):
    id: UUID
    project_id: UUID
    title: str
    description: Optional[str] = None
    severity: Optional[str] = None
    slack_url: Optional[str] = None
    slack_user_id: Optional[str] = None
    owner_name: Optional[str] = None
    device_name: Optional[str] = None
    network_name: Optional[str] = None
    created_at: Optional[datetime] = None
    media: list[LastIssueMediaItem] = []
