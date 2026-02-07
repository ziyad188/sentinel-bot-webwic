from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .client import get_supabase

logger = logging.getLogger(__name__)


def create_run(
    *,
    project_id: str,
    device_id: str,
    network_id: str,
    locale: str = "en-US",
    persona: str | None = None,
) -> dict[str, Any]:
    """Insert a new run row and return the full record."""
    sb = get_supabase()
    row = {
        "project_id": project_id,
        "device_id": device_id,
        "network_id": network_id,
        "status": "running",
        "locale": locale,
        "persona": persona,
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    result = sb.table("runs").insert(row).execute()
    return result.data[0]


def update_run_completed(
    run_id: str,
    *,
    result: str,  # "no_issues" | "issue_found" | "crash"
    duration_ms: int,
) -> dict[str, Any]:
    """Mark a run as completed."""
    sb = get_supabase()
    row = {
        "status": "completed",
        "result": result,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
    }
    res = sb.table("runs").update(row).eq("id", run_id).execute()
    return res.data[0] if res.data else {}


def update_run_failed(
    run_id: str,
    *,
    duration_ms: int,
) -> dict[str, Any]:
    """Mark a run as failed."""
    sb = get_supabase()
    row = {
        "status": "failed",
        "result": "crash",
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "duration_ms": duration_ms,
    }
    res = sb.table("runs").update(row).eq("id", run_id).execute()
    return res.data[0] if res.data else {}


def get_run(run_id: str) -> dict[str, Any] | None:
    """Fetch a single run by ID, including joined device/network names."""
    sb = get_supabase()
    result = (
        sb.table("runs")
        .select("*, devices(name, platform, viewport_width, viewport_height), networks(name, latency_ms)")
        .eq("id", run_id)
        .single()
        .execute()
    )
    return result.data


def list_runs(project_id: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """List recent runs, optionally filtered by project."""
    sb = get_supabase()
    query = (
        sb.table("runs")
        .select("*, devices(name), networks(name)")
        .order("started_at", desc=True)
        .limit(limit)
    )
    if project_id:
        query = query.eq("project_id", project_id)
    result = query.execute()
    return result.data


def get_previous_run(
    *,
    project_id: str,
    device_id: str,
    network_id: str,
    exclude_run_id: str,
) -> dict[str, Any] | None:
    """Find the most recent completed run for the same project/device/network combo.

    Used for cross-run regression detection — comparing the current run's
    results against the previous run to find regressions.

    Args:
        project_id: Project to scope the search
        device_id: Must match same device
        network_id: Must match same network
        exclude_run_id: Skip this run (the current one)

    Returns:
        The previous run row, or None if no previous run exists.
    """
    sb = get_supabase()
    result = (
        sb.table("runs")
        .select("*")
        .eq("project_id", project_id)
        .eq("device_id", device_id)
        .eq("network_id", network_id)
        .eq("status", "completed")
        .neq("id", exclude_run_id)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    return result.data[0] if result.data else None
