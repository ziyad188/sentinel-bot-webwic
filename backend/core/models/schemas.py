from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

RunStatus = Literal["running", "completed", "failed"]
RunResult = Literal["no_issues", "issue_found", "crash"]
IssueSeverity = Literal["P0", "P1", "P2", "P3"]
IssueCategory = Literal["backend", "frontend", "ux", "performance", "integration"]
IssueStatus = Literal["new", "investigating", "assigned", "resolved"]
EvidenceType = Literal["screenshot", "video"]


class APIModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class Project(APIModel):
    id: UUID | None = None
    name: str
    environment: str = "staging"
    target_url: str
    created_at: datetime | None = None


class Run(APIModel):
    id: UUID | None = None
    project_id: UUID

    status: RunStatus
    result: RunResult | None = None

    device_id: UUID | None = None
    network_id: UUID | None = None
    locale: str | None = None
    persona: str | None = None

    started_at: datetime | None = None
    finished_at: datetime | None = None
    duration_ms: int | None = None


class RunStep(APIModel):
    id: UUID | None = None
    run_id: UUID

    step_index: int | None = None
    action_type: str | None = None
    description: str | None = None
    duration_ms: int | None = None

    created_at: datetime | None = None


class Issue(APIModel):
    id: UUID | None = None
    project_id: UUID

    title: str
    description: str | None = None

    severity: IssueSeverity
    category: IssueCategory | None = None

    owner_team: str | None = None
    status: IssueStatus = "new"

    created_at: datetime | None = None
    resolved_at: datetime | None = None


class IssueRun(APIModel):
    issue_id: UUID
    run_id: UUID


class Evidence(APIModel):
    id: UUID | None = None
    run_id: UUID
    issue_id: UUID | None = None

    type: EvidenceType
    storage_path: str
    label: str | None = None

    created_at: datetime | None = None


class ProjectSettings(APIModel):
    project_id: UUID

    device_rotation: bool = True
    locale_rotation: bool = False
    record_evidence: bool = True
    clip_duration_sec: int = 10


class SlackIntegration(APIModel):
    project_id: UUID

    webhook_url: str
    enabled: bool = True
    created_at: datetime | None = None


class Device(APIModel):
    id: UUID | None = None

    name: str
    platform: str
    viewport_width: int
    viewport_height: int
    device_scale_factor: float = 1.0
    user_agent: str | None = None

    enabled: bool = True
    sort_order: int = 0

    created_at: datetime | None = None


class Network(APIModel):
    id: UUID | None = None

    name: str
    latency_ms: int
    download_kbps: int
    upload_kbps: int

    enabled: bool = True
    sort_order: int = 0

    created_at: datetime | None = None
