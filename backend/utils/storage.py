from __future__ import annotations

from typing import Optional

import httpx

from settings import get_settings


async def sign_storage_path(bucket: str, path: str, expires_in: int = 3600) -> str:
    settings = get_settings()
    base_url = settings.SUPABASE_URL.rstrip("/")
    url = f"{base_url}/storage/v1/object/sign/{bucket}/{path}"
    headers = {
        "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
        "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
        "Content-Type": "application/json",
    }

    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.post(url, headers=headers, json={"expiresIn": expires_in})

    if resp.status_code >= 400:
        raise RuntimeError(f"Supabase sign URL failed: {resp.status_code} {resp.text}")

    data = resp.json()
    signed_url: Optional[str] = (
        data.get("signedURL") or data.get("signedUrl") or data.get("signed_url")
    )
    if not signed_url:
        raise RuntimeError("Supabase sign URL response missing signed URL")

    if signed_url.startswith("http"):
        return signed_url

    # Normalize path to include /storage/v1 prefix for browser access.
    if signed_url.startswith("/storage/v1/"):
        return f"{base_url}{signed_url}"
    if signed_url.startswith("/object/"):
        return f"{base_url}/storage/v1{signed_url}"
    if signed_url.startswith("storage/v1/"):
        return f"{base_url}/{signed_url}"
    if signed_url.startswith("object/"):
        return f"{base_url}/storage/v1/{signed_url}"

    # Fallback: assume it is already a storage path fragment.
    return f"{base_url}/storage/v1/{signed_url.lstrip('/')}"
