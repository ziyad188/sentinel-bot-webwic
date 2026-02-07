from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID


class ProjectCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    environment: str = Field(default="staging", max_length=50)
    target_url: str = Field(min_length=1, max_length=2000)


class ProjectCreateResponse(BaseModel):
    id: UUID
    name: str
    environment: str
    target_url: str
