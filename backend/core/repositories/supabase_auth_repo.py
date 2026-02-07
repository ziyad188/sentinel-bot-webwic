import httpx
from typing import Any, Dict, Optional

from settings.config import get_settings


class SupabaseAuthRepo:
    def __init__(self) -> None:
        self._s = get_settings()

    def _headers(self, access_token: str | None = None) -> Dict[str, str]:
        token = access_token or self._s.SUPABASE_ANON_KEY
        return {
            "apikey": self._s.SUPABASE_ANON_KEY,
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _base_url(self) -> str:
        return self._s.SUPABASE_URL.rstrip("/")

    async def signup_email_password(
        self,
        *,
        email: str,
        password: str,
        user_metadata: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        url = f"{self._base_url()}/auth/v1/signup"
        payload: Dict[str, Any] = {"email": email, "password": password}
        if user_metadata:
            payload["data"] = user_metadata  

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)

        if resp.status_code >= 400:
            raise RuntimeError(f"Supabase signup failed: {resp.status_code} {resp.text}")

        return resp.json()

    async def login_email_password(
        self,
        *,
        email: str,
        password: str,
    ) -> Dict[str, Any]:
        url = f"{self._base_url()}/auth/v1/token?grant_type=password"
        payload: Dict[str, Any] = {"email": email, "password": password}

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)
        

        if resp.status_code >= 400:
            raise RuntimeError(f"Supabase login failed: {resp.status_code} {resp.text}")

        return resp.json()

    async def refresh_session(self, *, refresh_token: str) -> Dict[str, Any]:
        url = f"{self._base_url()}/auth/v1/token?grant_type=refresh_token"
        payload: Dict[str, Any] = {"refresh_token": refresh_token}

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=self._headers(), json=payload)

        if resp.status_code >= 400:
            raise RuntimeError(f"Supabase refresh failed: {resp.status_code} {resp.text}")

        return resp.json()

    async def logout(self, *, access_token: str, refresh_token: Optional[str] = None) -> None:
        url = f"{self._base_url()}/auth/v1/logout"
        payload: Dict[str, Any] = {}
        if refresh_token:
            payload["refresh_token"] = refresh_token

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(url, headers=self._headers(access_token), json=payload)

        if resp.status_code >= 400:
            raise RuntimeError(f"Supabase logout failed: {resp.status_code} {resp.text}")
