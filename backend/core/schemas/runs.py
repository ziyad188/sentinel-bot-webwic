from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class RunCreateRequest(BaseModel):
    project_id: UUID
    device_id: UUID
    network_id: UUID
    locale: str = Field(default="en-US")
    persona: str | None = None
    input_data: dict | None = None


class RunCreateResponse(BaseModel):
    run_id: UUID
    status: str
    detail: str


class IssueDetail(BaseModel):
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


class EvidenceItem(BaseModel):
    id: UUID
    run_id: UUID
    issue_id: Optional[UUID] = None
    type: str
    storage_path: str
    label: Optional[str] = None
    created_at: Optional[datetime] = None
    url: str


class RunIssuesResponse(BaseModel):
    project_id: UUID
    run_id: UUID
    issues: list[IssueDetail]
    media: list[EvidenceItem]


class IssueSummary(BaseModel):
    id: UUID
    title: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None


class RunListItem(BaseModel):
    id: UUID
    display_id: str
    started_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    device_id: Optional[UUID] = None
    device_name: Optional[str] = None
    network_id: Optional[UUID] = None
    network_name: Optional[str] = None
    locale: Optional[str] = None
    status: str
    result: Optional[str] = None
    issues: list[IssueSummary] = []


class RunListResponse(BaseModel):
    items: list[RunListItem]
    total: int
    page: int
    page_size: int


class RunningRunItem(BaseModel):
    id: UUID
    display_id: str
    started_at: Optional[datetime] = None
    device_id: Optional[UUID] = None
    device_name: Optional[str] = None
    network_id: Optional[UUID] = None
    network_name: Optional[str] = None


class RunningRunListResponse(BaseModel):
    items: list[RunningRunItem]
