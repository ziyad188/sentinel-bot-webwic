from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CategoryListItem(BaseModel):
    idx: int
    id: UUID
    project_id: UUID
    category: str
    slack_user_id: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    slack_display_name: Optional[str] = None
    slack_real_name: Optional[str] = None


class CategoryListResponse(BaseModel):
    items: list[CategoryListItem]
    total: int
    page: int
    page_size: int


class CategoryOption(BaseModel):
    id: UUID
    category: str


class CategoryOptionsResponse(BaseModel):
    items: list[CategoryOption]
    total: int
    page: int
    page_size: int


class CategoryOwnerCreateRequest(BaseModel):
    category_id: UUID
    slack_user_id: str


class CategoryOwnerResponse(BaseModel):
    category_id: UUID
    slack_user_id: str
    name: str
    email: Optional[str] = None
    is_active: Optional[bool] = None
