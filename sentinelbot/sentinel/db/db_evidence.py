from __future__ import annotations

import base64
import logging
import os
from typing import Any

from .client import get_supabase

logger = logging.getLogger(__name__)

SCREENSHOT_BUCKET = "evidence-screenshots"
VIDEO_BUCKET = "evidence-videos"


def ensure_buckets_exist() -> None:
    """Create storage buckets if they don't already exist."""
    sb = get_supabase()
    existing = {b.name for b in sb.storage.list_buckets()}
    for bucket in (SCREENSHOT_BUCKET, VIDEO_BUCKET):
        if bucket not in existing:
            sb.storage.create_bucket(bucket, options={"public": True})
            logger.info(f"Created storage bucket: {bucket}")


def upload_screenshot(
    *,
    run_id: str,
    step: int,
    base64_image: str,
    issue_id: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    """Decode a base64 PNG, upload to Supabase Storage, and insert an evidence row.

    Storage path: {run_id}/step_{step:03d}.png
    Returns the evidence row.
    """
    sb = get_supabase()
    image_bytes = base64.b64decode(base64_image)
    storage_path = f"{run_id}/step_{step:03d}.png"

    # Upload to bucket
    sb.storage.from_(SCREENSHOT_BUCKET).upload(
        path=storage_path,
        file=image_bytes,
        file_options={"content-type": "image/png", "upsert": "true"},
    )

    # Insert evidence record
    row: dict[str, Any] = {
        "run_id": run_id,
        "type": "screenshot",
        "storage_path": storage_path,
        "label": label or f"Step {step}",
    }
    if issue_id:
        row["issue_id"] = issue_id

    result = sb.table("evidence").insert(row).execute()
    return result.data[0]


def upload_video(
    *,
    run_id: str,
    local_path: str,
    label: str | None = None,
) -> dict[str, Any] | None:
    """Upload a video file to Supabase Storage and insert an evidence row.

    Storage path: {run_id}/{filename}
    Returns the evidence row, or None if the file doesn't exist.
    """
    if not os.path.exists(local_path):
        logger.warning(f"Video file not found: {local_path}")
        return None

    sb = get_supabase()
    filename = os.path.basename(local_path)
    storage_path = f"{run_id}/{filename}"

    with open(local_path, "rb") as f:
        video_bytes = f.read()

    sb.storage.from_(VIDEO_BUCKET).upload(
        path=storage_path,
        file=video_bytes,
        file_options={"content-type": "video/webm", "upsert": "true"},
    )

    row = {
        "run_id": run_id,
        "type": "video",
        "storage_path": storage_path,
        "label": label or "Recording",
    }
    result = sb.table("evidence").insert(row).execute()
    return result.data[0]


def link_evidence_to_issue(evidence_id: str, issue_id: str) -> None:
    """Set the issue_id on an existing evidence row."""
    sb = get_supabase()
    sb.table("evidence").update({"issue_id": issue_id}).eq("id", evidence_id).execute()


def get_evidence_for_run(run_id: str) -> list[dict[str, Any]]:
    """List all evidence (screenshots + videos) for a run."""
    sb = get_supabase()
    result = (
        sb.table("evidence")
        .select("*")
        .eq("run_id", run_id)
        .order("created_at")
        .execute()
    )
    return result.data


def get_screenshot_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generate a signed URL for a screenshot in Supabase Storage."""
    sb = get_supabase()
    result = sb.storage.from_(SCREENSHOT_BUCKET).create_signed_url(
        storage_path, expires_in
    )
    return result.get("signedURL", "")


def get_video_url(storage_path: str, expires_in: int = 3600) -> str:
    """Generate a signed URL for a video in Supabase Storage."""
    sb = get_supabase()
    result = sb.storage.from_(VIDEO_BUCKET).create_signed_url(
        storage_path, expires_in
    )
    return result.get("signedURL", "")
