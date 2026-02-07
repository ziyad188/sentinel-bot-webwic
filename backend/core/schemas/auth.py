from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class SignUpRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=16)
    full_name: Optional[str] = Field(default=None, max_length=120)
    metadata: Optional[Dict[str, Any]] = None


class SupabaseSession(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    token_type: str


class SignUpResponse(BaseModel):
    user_id: str
    email: str
    confirmation_required: bool = False
    session: Optional[SupabaseSession] = None


class LoginRequest(BaseModel):
    email: str
    password: str = Field(min_length=8, max_length=128)


class LoginResponse(BaseModel):
    user_id: str
    email: str
    session: SupabaseSession


class RefreshRequest(BaseModel):
    refresh_token: str


class RefreshResponse(BaseModel):
    user_id: str
    email: str
    session: SupabaseSession


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class LogoutResponse(BaseModel):
    success: bool
