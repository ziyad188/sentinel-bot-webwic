from typing import Any, Dict, Optional

from core.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    SignUpRequest,
    SignUpResponse,
    SupabaseSession,
)
from core.repositories.supabase_auth_repo import SupabaseAuthRepo
import logging

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self, repo: SupabaseAuthRepo) -> None:
        self._repo = repo

    async def signup(self, req: SignUpRequest) -> SignUpResponse:
        user_metadata: Dict[str, Any] = {}
        if req.full_name:
            user_metadata["full_name"] = req.full_name
        if req.metadata:
            user_metadata.update(req.metadata)

        data = await self._repo.signup_email_password(
            email=req.email,
            password=req.password,
            user_metadata=user_metadata or None,
        )

        user = data.get("user") or {}
        session = data.get("session") 
        if not session and data.get("access_token"):
             session = {
                "access_token": data.get("access_token"),
                "refresh_token": data.get("refresh_token"),
                "expires_in": data.get("expires_in"),
                "token_type": data.get("token_type"),
            }

        user_id = str(user.get("id") or "")
        email = str(user.get("email") or req.email)

        if not user_id:
            logger.exception("Supabase signup returned no user id ")
            raise RuntimeError("Supabase signup returned no user id")

        if session:
            return SignUpResponse(
                user_id=user_id,
                email=email,
                confirmation_required=False,
                session=SupabaseSession(
                    access_token=session["access_token"],
                    refresh_token=session["refresh_token"],
                    expires_in=int(session["expires_in"]),
                    token_type=session["token_type"],
                ),
            )

        return SignUpResponse(
            user_id=user_id,
            email=email,
            confirmation_required=True,
            session=None,
        )

    async def login(self, req: LoginRequest) -> LoginResponse:
        data = await self._repo.login_email_password(
            email=req.email,
            password=req.password,
        )

        user = data.get("user") or {}
        session = data.get("session") or data

        user_id = str(user.get("id") or "")
        email = str(user.get("email") or req.email)

        if not user_id:
            logger.exception("Supabase login returned no user id")
            raise RuntimeError("Supabase login returned no user id")

        return LoginResponse(
            user_id=user_id,
            email=email,
            session=SupabaseSession(
                access_token=session["access_token"],
                refresh_token=session["refresh_token"],
                expires_in=int(session["expires_in"]),
                token_type=session["token_type"],
            ),
        )

    async def refresh(self, req: RefreshRequest) -> RefreshResponse:
        data = await self._repo.refresh_session(refresh_token=req.refresh_token)

        user = data.get("user") or {}
        session = data.get("session") or data

        user_id = str(user.get("id") or "")
        email = str(user.get("email") or "")

        if not user_id:
            logger.exception("Supabase refresh returned no user id")
            raise RuntimeError("Supabase refresh returned no user id")

        return RefreshResponse(
            user_id=user_id,
            email=email,
            session=SupabaseSession(
                access_token=session["access_token"],
                refresh_token=session["refresh_token"],
                expires_in=int(session["expires_in"]),
                token_type=session["token_type"],
            ),
        )

    async def logout(self, access_token: str, req: LogoutRequest) -> LogoutResponse:
        await self._repo.logout(access_token=access_token, refresh_token=req.refresh_token)
        return LogoutResponse(success=True)
