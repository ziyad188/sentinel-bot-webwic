from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from .client import get_supabase

logger = logging.getLogger(__name__)


def insert_log(
    *,
    run_id: str,
    level: str,          # info | warn | error | debug
    event_type: str,     # e.g. "run_start", "api_call", "tool_result"
    message: str | None = None,
    payload: dict | None = None,
) -> dict[str, Any]:
    """Append a structured log entry for a run."""
    sb = get_supabase()
    row: dict[str, Any] = {
        "run_id": run_id,
        "ts": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "event_type": event_type,
    }
    if message:
        row["message"] = message
    if payload:
        row["payload"] = payload

    result = sb.table("run_logs").insert(row).execute()
    return result.data[0] if result.data else {}


def insert_step(
    *,
    run_id: str,
    step_index: int,
    action_type: str | None = None,
    description: str | None = None,
    duration_ms: int | None = None,
) -> dict[str, Any]:
    """Record a single run step (tool call)."""
    sb = get_supabase()
    row: dict[str, Any] = {
        "run_id": run_id,
        "step_index": step_index,
    }
    if action_type:
        row["action_type"] = action_type
    if description:
        row["description"] = description
    if duration_ms is not None:
        row["duration_ms"] = duration_ms

    result = sb.table("run_steps").insert(row).execute()
    return result.data[0] if result.data else {}


def get_logs_for_run(run_id: str) -> list[dict[str, Any]]:
    """Fetch all log entries for a run, ordered by timestamp."""
    sb = get_supabase()
    result = (
        sb.table("run_logs")
        .select("*")
        .eq("run_id", run_id)
        .order("ts")
        .execute()
    )
    return result.data


def get_steps_for_run(run_id: str) -> list[dict[str, Any]]:
    """Fetch all steps for a run, ordered by step_index."""
    sb = get_supabase()
    result = (
        sb.table("run_steps")
        .select("*")
        .eq("run_id", run_id)
        .order("step_index")
        .execute()
    )
    return result.data
