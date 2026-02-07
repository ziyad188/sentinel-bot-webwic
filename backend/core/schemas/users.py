from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class SlackUserListItem(BaseModel):
    idx: int
    id: UUID
    slack_user_id: str
    display_name: Optional[str] = None
    real_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    uuid_id: Optional[UUID] = None


class SlackUserListResponse(BaseModel):
    items: list[SlackUserListItem]
    total: int
    page: int
    page_size: int


class SlackUserWithCategoriesItem(BaseModel):
    idx: int
    id: UUID
    slack_user_id: str
    display_name: Optional[str] = None
    real_name: Optional[str] = None
    email: Optional[str] = None
    avatar_url: Optional[str] = None
    is_active: Optional[bool] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    categories: list[str] = []


class SlackUserWithCategoriesResponse(BaseModel):
    items: list[SlackUserWithCategoriesItem]
    total: int
    page: int
    page_size: int


class SlackUserCreateRequest(BaseModel):
    slack_user_id: str
    name: str
    email: Optional[str] = None
    is_active: bool = True
    project_id: UUID
    categories: list[str] = []
    avatar_url: Optional[str] = None


class SlackUserCreateResponse(BaseModel):
    id: UUID
    slack_user_id: str
    name: str
    email: Optional[str] = None
    is_active: Optional[bool] = None
    project_id: UUID
    categories: list[str]
