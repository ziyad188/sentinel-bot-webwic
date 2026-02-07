from __future__ import annotations

from pydantic import BaseModel, Field
from uuid import UUID

class DeviceOption(BaseModel):
    id: UUID
    name: str


class DeviceListQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=25, ge=1, le=100)


class DeviceListResponse(BaseModel):
    items: list[DeviceOption]
    total: int
    page: int
    page_size: int


class NetworkOption(BaseModel):
    id: UUID
    name: str


class NetworkListResponse(BaseModel):
    items: list[NetworkOption]
    total: int
    page: int
    page_size: int


class ProjectOption(BaseModel):
    id: UUID
    name: str
    environment: str


class ProjectListResponse(BaseModel):
    items: list[ProjectOption]
    total: int
    page: int
    page_size: int
