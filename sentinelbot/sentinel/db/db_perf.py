"""Performance metrics persistence for Core Web Vitals and resource timing."""

from __future__ import annotations

import logging
from typing import Any

from .client import get_supabase

logger = logging.getLogger(__name__)


def insert_perf_metrics(
    *,
    run_id: str,
    url: str,
    lcp_ms: float | None = None,
    cls: float | None = None,
    ttfb_ms: float | None = None,
    fcp_ms: float | None = None,
    dom_content_loaded_ms: float | None = None,
    resource_count: int | None = None,
    total_transfer_kb: float | None = None,
    step: int | None = None,
) -> dict[str, Any]:
    """Insert a performance metrics row for a page load within a run.

    Collects Core Web Vitals (LCP, CLS, TTFB, FCP) + resource stats.

    Args:
        run_id: The run that captured these metrics
        url: The page URL where metrics were collected
        lcp_ms: Largest Contentful Paint (milliseconds)
        cls: Cumulative Layout Shift (unitless score)
        ttfb_ms: Time to First Byte (milliseconds)
        fcp_ms: First Contentful Paint (milliseconds)
        dom_content_loaded_ms: DOMContentLoaded event time (milliseconds)
        resource_count: Number of resources loaded
        total_transfer_kb: Total transfer size in KB
        step: The step number where metrics were collected
    """
    sb = get_supabase()
    row: dict[str, Any] = {
        "run_id": run_id,
        "url": url,
    }
    if lcp_ms is not None:
        row["lcp_ms"] = round(lcp_ms, 2)
    if cls is not None:
        row["cls"] = round(cls, 4)
    if ttfb_ms is not None:
        row["ttfb_ms"] = round(ttfb_ms, 2)
    if fcp_ms is not None:
        row["fcp_ms"] = round(fcp_ms, 2)
    if dom_content_loaded_ms is not None:
        row["dom_content_loaded_ms"] = round(dom_content_loaded_ms, 2)
    if resource_count is not None:
        row["resource_count"] = resource_count
    if total_transfer_kb is not None:
        row["total_transfer_kb"] = round(total_transfer_kb, 2)
    if step is not None:
        row["step"] = step

    try:
        result = sb.table("performance_metrics").insert(row).execute()
        return result.data[0]
    except Exception as e:
        logger.warning(f"Failed to insert perf metrics for run {run_id}: {e}")
        return row


def get_perf_metrics_for_run(run_id: str) -> list[dict[str, Any]]:
    """Get all performance metrics collected during a run."""
    sb = get_supabase()
    result = (
        sb.table("performance_metrics")
        .select("*")
        .eq("run_id", run_id)
        .order("created_at")
        .execute()
    )
    return result.data


def get_perf_trends(
    project_id: str,
    url_pattern: str | None = None,
    days: int = 7,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Get performance metric trends for a project over time.

    Joins with runs to filter by project_id and date range.
    Returns metrics sorted by collection time.
    """
    sb = get_supabase()
    from datetime import datetime, timedelta, timezone

    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()

    # Query performance_metrics joined with runs
    query = (
        sb.table("performance_metrics")
        .select("*, runs!inner(project_id, device_id, network_id, locale, started_at)")
        .eq("runs.project_id", project_id)
        .gte("runs.started_at", cutoff)
        .order("created_at", desc=True)
        .limit(limit)
    )

    result = query.execute()
    return result.data
