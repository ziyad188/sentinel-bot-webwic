from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials

from core.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutRequest,
    LogoutResponse,
    RefreshRequest,
    RefreshResponse,
    SignUpRequest,
    SignUpResponse,
)
from core.services.auth_service import AuthService
from core.repositories.supabase_auth_repo import SupabaseAuthRepo
from core.auth.deps import get_current_user, security
import logging

router = APIRouter(prefix="/auth", tags=["auth"])

logger = logging.getLogger(__name__)

@router.post("/signup", response_model=SignUpResponse, status_code=status.HTTP_201_CREATED)
async def signup(payload: SignUpRequest):
    try:
        svc = AuthService(SupabaseAuthRepo())
        return await svc.signup(payload)
    except RuntimeError as e:
        logger.exception("Signup failed: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest):
    try:
        svc = AuthService(SupabaseAuthRepo())
        return await svc.login(payload)
    except RuntimeError as e:
        logger.exception("Signup failed: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(payload: RefreshRequest):
    try:
        svc = AuthService(SupabaseAuthRepo())
        return await svc.refresh(payload)
    except RuntimeError as e:
        logger.exception("Refresh failed: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/logout", response_model=LogoutResponse)
async def logout(
    payload: LogoutRequest | None = None,
    creds: HTTPAuthorizationCredentials = Depends(security),
    _user=Depends(get_current_user),
):
    try:
        if creds is None or not creds.credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Missing authorization token",
            )
        svc = AuthService(SupabaseAuthRepo())
        return await svc.logout(creds.credentials, payload or LogoutRequest())
    except RuntimeError as e:
        logger.exception("Logout failed: %s", str(e))
        raise HTTPException(status_code=400, detail=str(e))
