from __future__ import annotations

import logging
from typing import Any

from .client import get_supabase

logger = logging.getLogger(__name__)


def get_device_by_id(device_id: str) -> dict[str, Any]:
    """Fetch a device row by UUID.

    Returns dict with keys matching the DB columns:
      id, name, platform, viewport_width, viewport_height,
      device_scale_factor, user_agent, enabled, sort_order, created_at
    """
    sb = get_supabase()
    result = sb.table("devices").select("*").eq("id", device_id).single().execute()
    return result.data


def get_network_by_id(network_id: str) -> dict[str, Any]:
    """Fetch a network row by UUID.

    Returns dict with keys:
      id, name, latency_ms, download_kbps, upload_kbps, enabled, sort_order, created_at
    """
    sb = get_supabase()
    result = sb.table("networks").select("*").eq("id", network_id).single().execute()
    return result.data


def list_devices(enabled_only: bool = True) -> list[dict[str, Any]]:
    """List all devices, optionally filtered to enabled ones."""
    sb = get_supabase()
    query = sb.table("devices").select("*").order("sort_order")
    if enabled_only:
        query = query.eq("enabled", True)
    result = query.execute()
    return result.data


def list_networks(enabled_only: bool = True) -> list[dict[str, Any]]:
    """List all networks, optionally filtered to enabled ones."""
    sb = get_supabase()
    query = sb.table("networks").select("*").order("sort_order")
    if enabled_only:
        query = query.eq("enabled", True)
    result = query.execute()
    return result.data


def device_to_playwright_profile(device: dict[str, Any]) -> dict[str, Any]:
    """Convert a DB device row into a Playwright-compatible device profile dict.

    This replaces the hardcoded DEVICE_PROFILES in playwright_tool.py.
    """
    is_mobile = device.get("platform", "").lower() in ("ios", "android", "mobile")
    return {
        "viewport": {
            "width": device["viewport_width"],
            "height": device["viewport_height"],
        },
        "user_agent": device.get("user_agent") or "",
        "device_scale_factor": float(device.get("device_scale_factor", 1)),
        "is_mobile": is_mobile,
        "has_touch": is_mobile,
    }


def network_to_throttle_profile(network: dict[str, Any]) -> dict[str, Any]:
    """Convert a DB network row into a CDP network-throttle dict.

    Returns an empty dict for no-throttle (latency=0, download/upload unlimited),
    matching the existing NETWORK_PROFILES["wifi"] == {} convention.
    """
    lat = network.get("latency_ms", 0)
    down = network.get("download_kbps", 0)
    up = network.get("upload_kbps", 0)

    # Treat zero-latency + high-bandwidth as "no throttle"
    if lat == 0 and down == 0 and up == 0:
        return {}

    return {
        "offline": False,
        "download_throughput": (down * 1024) // 8 if down else -1,
        "upload_throughput": (up * 1024) // 8 if up else -1,
        "latency": lat,
    }
