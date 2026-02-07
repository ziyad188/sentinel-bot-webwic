import asyncio
import glob
import json
import logging
import os
import re
import time
import traceback
from collections import deque
from typing import Any

import httpx
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from sentinel.loop import APIProvider, sampling_loop
from sentinel.sentinel_prompt import get_sentinel_system_prompt, PERSONA_PROFILES
from sentinel.tools import PlaywrightComputerTool, ToolCollection
from sentinel.tools.base import ToolResult
from sentinel.tools.bash import BashTool20250124
from sentinel.scheduler import ContinuousScheduler, ScheduleConfig
from sentinel.slack_notifier import (
    _get_owner_for_category,
    find_or_create_channel,
    is_slack_configured,
    post_issue_to_slack,
    post_run_summary_to_slack,
)

# DB layer
from sentinel.db.db_devices import (
    device_to_playwright_profile,
    get_device_by_id,
    get_network_by_id,
    list_devices,
    list_networks,
    network_to_throttle_profile,
)
from sentinel.db.db_evidence import (
    ensure_buckets_exist,
    get_evidence_for_run,
    link_evidence_to_issue,
    upload_screenshot,
    upload_video,
)
from sentinel.db.db_issues import (
    _jaccard_similarity,
    _tokenize,
    create_issue,
    find_similar_issues,
    get_issue_frequency,
    get_issues_for_run,
    link_issue_to_run,
)
from sentinel.db.db_logs import insert_log, insert_step
from sentinel.db.db_runs import (
    create_run,
    get_previous_run,
    get_run as db_get_run,
    list_runs as db_list_runs,
    update_run_completed,
    update_run_failed,
)
from sentinel.db.db_perf import (
    insert_perf_metrics,
    get_perf_metrics_for_run,
)

# ── Logging ─────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)

# ── FastAPI app ─────────────────────────────────────────────────────────

app = FastAPI(
    title="SentinelBot",
    description="Claude-powered mobile QA testing via Playwright, persisted to Supabase",
    version="0.3.0",
)

# ── Continuous Monitoring Scheduler ─────────────────────────────────────
scheduler = ContinuousScheduler()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Temp dir for video recording (uploaded to Supabase after run)
VIDEO_TMP_DIR = os.environ.get("SENTINEL_VIDEO_DIR", "/tmp/sentinel_videos")

# ── Sensitive key auto-detection ────────────────────────────────────────
# Patterns (lowercased, substring match) that mark a key as sensitive.
_SENSITIVE_PATTERNS: list[str] = [
    "password", "passwd", "pass_word",
    "secret", "token", "api_key", "apikey",
    "otp", "pin", "mpin",
    "ssn", "social_security",
    "credit_card", "creditcard", "card_number", "cardnumber",
    "cvv", "cvc", "ccv",
    "mobile", "phone", "cell",
    "auth", "credential",
    "private_key", "privatekey",
    "access_key", "accesskey",
]


def _detect_sensitive_keys(
    input_data: dict[str, str],
    extra_sensitive_keys: list[str] | None = None,
) -> set[str]:
    """Return the set of keys in *input_data* that should be masked in logs.

    Auto-detects common sensitive patterns (password, phone, token, …)
    and merges with any explicitly provided *extra_sensitive_keys*.
    """
    detected: set[str] = set()
    for key in input_data:
        key_lower = key.lower().replace("-", "_").replace(" ", "_")
        if any(pat in key_lower for pat in _SENSITIVE_PATTERNS):
            detected.add(key)
    if extra_sensitive_keys:
        detected.update(extra_sensitive_keys)
    return detected


def _mask_input_data(
    input_data: dict[str, str],
    extra_sensitive_keys: list[str] | None = None,
) -> dict[str, str]:
    """Return a copy of *input_data* with sensitive values replaced by '****'."""
    sensitive = _detect_sensitive_keys(input_data, extra_sensitive_keys)
    return {
        k: ("****" if k in sensitive else v)
        for k, v in input_data.items()
    }


@app.on_event("startup")
async def _startup():
    """Ensure Supabase storage buckets exist on server start."""
    try:
        ensure_buckets_exist()
        logger.info("Supabase storage buckets verified")
    except Exception as e:
        logger.warning(f"Could not verify storage buckets: {e}")


# ── Request / Response Models ───────────────────────────────────────────


class TestRequest(BaseModel):
    """Configuration for a QA test run."""

    project_id: str
    device_id: str
    network_id: str
    task: str | None = None
    model: str = "claude-sonnet-4-5-20250929"
    locale: str = "en-US"
    persona: str | None = None
    max_tokens: int = 8192
    thinking_budget: int | None = None
    only_n_most_recent_images: int = 3

    # ── User-provided test inputs ──────────────────────────────────
    # Arbitrary key-value pairs for the agent to use during testing
    # (e.g. login credentials, form data, search queries).
    input_data: dict[str, str] | None = None
    # Extra keys to mask in logs on top of auto-detected ones.
    # Auto-detection covers: password, token, otp, phone/mobile, ssn, etc.
    sensitive_keys: list[str] | None = None

    # ── 24/7 Continuous Monitoring ──────────────────────────────────
    # Set continuous_monitoring=true to start a recurring schedule
    # alongside the immediate test run.
    continuous_monitoring: bool = False
    monitoring_interval_minutes: int = 60
    monitoring_device_ids: list[str] | None = None   # defaults to [device_id]
    monitoring_network_ids: list[str] | None = None   # defaults to [network_id]
    monitoring_locales: list[str] | None = None       # defaults to [locale]
    monitoring_personas: list[str | None] | None = None  # defaults to [persona]


# ── Endpoints ───────────────────────────────────────────────────────────


@app.get("/api/health")
async def health():
    """Health check endpoint."""
    active_schedules = len([s for s in scheduler.list_schedules() if s.is_running])
    return {
        "status": "ok",
        "service": "sentinelbot",
        "version": "0.3.0",
        "active_schedules": active_schedules,
    }


@app.get("/api/devices")
async def api_list_devices():
    """List all enabled device profiles from the database."""
    devices = list_devices(enabled_only=True)
    return [
        {
            "id": d["id"],
            "name": d["name"],
            "platform": d["platform"],
            "viewport": f"{d['viewport_width']}x{d['viewport_height']}",
        }
        for d in devices
    ]


@app.get("/api/networks")
async def api_list_networks():
    """List all enabled network profiles from the database."""
    networks = list_networks(enabled_only=True)
    return [
        {
            "id": n["id"],
            "name": n["name"],
            "latency_ms": n["latency_ms"],
            "download_kbps": n["download_kbps"],
            "upload_kbps": n["upload_kbps"],
        }
        for n in networks
    ]


@app.post("/api/test")
async def start_test(req: TestRequest, background_tasks: BackgroundTasks):
    """Start a new QA test run.

    Requires project_id, device_id, network_id (UUIDs from the database).
    Returns immediately with a run_id. Poll GET /api/runs/{run_id} for status.
    """
    # Validate API key
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(status_code=500, detail="ANTHROPIC_API_KEY is not set")

    # Fetch device and network from DB
    try:
        device = get_device_by_id(req.device_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Device not found: {req.device_id}")
    try:
        network = get_network_by_id(req.network_id)
    except Exception:
        raise HTTPException(status_code=400, detail=f"Network not found: {req.network_id}")

    # Fetch project to get target_url
    from sentinel.db.client import get_supabase

    sb = get_supabase()
    try:
        project = (
            sb.table("projects").select("*").eq("id", req.project_id).single().execute()
        )
        project_data = project.data
    except Exception:
        raise HTTPException(
            status_code=400, detail=f"Project not found: {req.project_id}"
        )

    target_url = project_data["target_url"]
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    # Create run row in DB
    run_row = create_run(
        project_id=req.project_id,
        device_id=req.device_id,
        network_id=req.network_id,
        locale=req.locale,
        persona=req.persona,
    )
    run_id = run_row["id"]

    # Log run start (mask sensitive values before logging)
    log_payload = req.model_dump()
    if req.input_data:
        log_payload["input_data"] = _mask_input_data(
            req.input_data, req.sensitive_keys
        )
    insert_log(
        run_id=run_id,
        level="info",
        event_type="run_start",
        message=f"Starting test for {target_url}",
        payload=log_payload,
    )

    # Schedule background execution
    background_tasks.add_task(
        _execute_run,
        run_id=run_id,
        req=req,
        target_url=target_url,
        device=device,
        network=network,
        project_id=req.project_id,
        project_data=project_data,
        api_key=api_key,
    )

    # ── Optionally start 24/7 continuous monitoring ──────────────
    schedule_info = None
    if req.continuous_monitoring:
        config = ScheduleConfig(
            project_id=req.project_id,
            device_ids=req.monitoring_device_ids or [req.device_id],
            network_ids=req.monitoring_network_ids or [req.network_id],
            locales=req.monitoring_locales or [req.locale],
            personas=req.monitoring_personas if req.monitoring_personas is not None else [req.persona],
            interval_minutes=req.monitoring_interval_minutes,
            model=req.model,
            max_tokens=req.max_tokens,
            thinking_budget=req.thinking_budget,
            only_n_most_recent_images=req.only_n_most_recent_images,
            task=req.task,
            input_data=req.input_data,
            sensitive_keys=req.sensitive_keys,
        )
        state = scheduler.create_schedule(config)
        combo_count = (
            len(config.device_ids)
            * len(config.network_ids)
            * len(config.locales)
            * len(config.personas)
        )
        scheduler.start_schedule(state.schedule_id, _scheduled_run_trigger)
        schedule_info = {
            "schedule_id": state.schedule_id,
            "combo_count": combo_count,
            "interval_minutes": req.monitoring_interval_minutes,
        }
        insert_log(
            run_id=run_id,
            level="info",
            event_type="continuous_monitoring_started",
            message=(
                f"24/7 monitoring enabled: {combo_count} combos every "
                f"{req.monitoring_interval_minutes}m (schedule {state.schedule_id})"
            ),
            payload=schedule_info,
        )
        logger.info(
            f"Run {run_id}: continuous monitoring started — schedule {state.schedule_id}"
        )

    response = {
        "run_id": run_id,
        "status": "running",
        "detail": f"Test started. Poll GET /api/runs/{run_id} for results.",
    }
    if schedule_info:
        response["continuous_monitoring"] = schedule_info
    return response


@app.get("/api/runs")
async def api_list_runs(project_id: str | None = None, limit: int = 50):
    """List recent runs, optionally filtered by project_id."""
    return db_list_runs(project_id=project_id, limit=limit)


@app.get("/api/runs/{run_id}")
async def api_get_run(run_id: str):
    """Get detailed results for a specific run, including all intelligence data."""
    run = db_get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    # Attach issues and evidence
    issues = get_issues_for_run(run_id)
    evidence = get_evidence_for_run(run_id)

    # Attach intelligence data from logs
    from sentinel.db.db_logs import get_logs_for_run

    logs = get_logs_for_run(run_id)
    ux_confusion = [
        log.get("payload", {})
        for log in logs
        if log.get("event_type") == "ux_confusion"
    ]
    locale_issues = [
        log.get("payload", {})
        for log in logs
        if log.get("event_type") == "locale_issue"
    ]
    root_cause_matches = [
        log.get("payload", {})
        for log in logs
        if log.get("event_type") == "root_cause_match"
    ]
    captcha_logs = [
        log.get("payload", {})
        for log in logs
        if log.get("event_type") == "captcha_encountered"
    ]
    a11y_violations = [
        log.get("payload", {})
        for log in logs
        if log.get("event_type") == "a11y_violation"
    ]
    regression_events = [
        log.get("payload", {})
        for log in logs
        if log.get("event_type") == "regression_detected"
    ]
    flaky_events = [
        log.get("payload", {})
        for log in logs
        if log.get("event_type") in ("flaky_confirmed", "flaky_detected")
    ]

    # Performance metrics
    perf_metrics = get_perf_metrics_for_run(run_id)

    return {
        **run,
        "issues": issues,
        "evidence": evidence,
        "ux_confusion_events": ux_confusion,
        "locale_issues": locale_issues,
        "root_cause_matches": root_cause_matches,
        "captcha_encountered": len(captcha_logs) > 0,
        "captcha_details": captcha_logs[0] if captcha_logs else None,
        "accessibility_violations": a11y_violations,
        "regressions": regression_events,
        "flaky_detection": flaky_events,
        "performance_metrics": perf_metrics,
    }


@app.get("/api/runs/{run_id}/issues")
async def api_get_run_issues(run_id: str):
    """Get all issues found during a run."""
    return get_issues_for_run(run_id)


@app.get("/api/runs/{run_id}/evidence")
async def api_get_run_evidence(run_id: str):
    """Get all evidence (screenshots/videos) for a run."""
    return get_evidence_for_run(run_id)


# ── Background Run Execution ────────────────────────────────────────────


async def _execute_run(
    *,
    run_id: str,
    req: TestRequest,
    target_url: str,
    device: dict[str, Any],
    network: dict[str, Any],
    project_id: str,
    project_data: dict[str, Any] | None = None,
    api_key: str,
):
    """Execute the Claude sampling loop for a test run."""
    start_time = time.monotonic()
    step_counter = {"count": 0}

    # Convert DB rows to Playwright-compatible profile dicts
    pw_device_profile = device_to_playwright_profile(device)
    pw_network_profile = network_to_throttle_profile(network)

    # Human-readable labels for the system prompt
    device_label = f"{device['name']} ({device['viewport_width']}x{device['viewport_height']})"
    network_label = network["name"]

    # Temp video directory for this run
    video_dir = os.path.join(VIDEO_TMP_DIR, run_id)
    os.makedirs(video_dir, exist_ok=True)

    # Initialize PlaywrightComputerTool with DB-sourced profiles
    pw_tool = PlaywrightComputerTool(
        device_profile_dict=pw_device_profile,
        network_profile_dict=pw_network_profile,
        target_url=target_url,
        locale=req.locale,
        video_dir=video_dir,
    )
    tool_collection = ToolCollection(pw_tool, BashTool20250124())

    # Build task — always inject the target URL so Claude never asks for it
    base_task = req.task or (
        "Thoroughly test the main user flow. "
        "Try all interactive elements, test form validation, check for visual issues, "
        "and report all bugs and issues found."
    )
    task = f"Navigate to {target_url} and {base_task}"

    # Append user-provided input data to the task so the agent uses them
    if req.input_data:
        input_lines = "\n".join(f"  - {k}: {v}" for k, v in req.input_data.items())
        task += (
            f"\n\nYou have been provided the following input data to use during testing. "
            f"Use these values when you encounter corresponding fields (e.g. login forms, "
            f"search bars, registration fields, etc.):\n{input_lines}"
        )

    # Build system prompt with persona + locale awareness
    system_prompt = get_sentinel_system_prompt(
        device_label=device_label,
        network_label=network_label,
        target_url=target_url,
        persona=req.persona,
        locale=req.locale,
    )

    # ── Callbacks ───────────────────────────────────────────────────

    # Track pending tool_use blocks so we can correlate them with results
    pending_tools: dict[str, dict[str, Any]] = {}   # tool_id → {action, input, start_time}
    realtime_issues_reported: set[str] = set()       # titles already escalated mid-run
    last_screenshot_b64: dict[str, str | None] = {"img": None}  # most recent screenshot
    # Rolling buffer of last 3 screenshots for multi-image Slack uploads
    recent_screenshots: deque[dict[str, Any]] = deque(maxlen=3)  # [{"b64": ..., "step": ...}]

    # Resolve Slack channel once (reused for all issues in this run)
    slack_channel_id: dict[str, str | None] = {"id": None}
    if is_slack_configured():
        try:
            slack_channel_id["id"] = await find_or_create_channel(
                project_name=project_data.get("name", project_id[:8]),
                project_id=project_id,
            )
        except Exception as e:
            logger.warning(f"Run {run_id}: failed to resolve Slack channel: {e}")

    def _describe_action(tool_input: dict) -> str:
        """Build a human-readable description from a tool_use input."""
        action = tool_input.get("action", "unknown")
        coord = tool_input.get("coordinate")
        text = tool_input.get("text")
        scroll_dir = tool_input.get("scroll_direction")
        scroll_amt = tool_input.get("scroll_amount")
        duration = tool_input.get("duration")
        start_coord = tool_input.get("start_coordinate")

        parts = [action]
        if coord:
            parts.append(f"at ({coord[0]}, {coord[1]})")
        if start_coord:
            parts.append(f"from ({start_coord[0]}, {start_coord[1]})")
        if text:
            display = text if len(text) <= 40 else text[:37] + "..."
            parts.append(f'"{display}"')
        if scroll_dir:
            parts.append(f"{scroll_dir} {scroll_amt or 3}x")
        if duration:
            parts.append(f"wait {duration}s")
        return " ".join(parts)

    def output_callback(content_block):
        """Log assistant output blocks to run_logs + detect real-time issues."""
        if isinstance(content_block, dict):
            block_type = content_block.get("type", "unknown")
            payload: dict[str, Any] = {"block_type": block_type}

            if block_type == "text":
                text_content = content_block.get("text", "")
                payload["text"] = text_content

                # ── Real-time issue detection ───────────────────────
                _check_realtime_issue(
                    text_content,
                    run_id=run_id,
                    project_id=project_id,
                    target_url=target_url,
                    device_label=device_label,
                    network_label=network_label,
                    slack_channel_id=slack_channel_id["id"],
                    realtime_issues_reported=realtime_issues_reported,
                    last_screenshot_b64=last_screenshot_b64["img"],
                    recent_screenshots=list(recent_screenshots),
                )

            elif block_type == "tool_use":
                tool_id = content_block.get("id", "")
                tool_input = content_block.get("input", {})
                payload["tool_name"] = content_block.get("name")
                payload["tool_input"] = tool_input
                # Stash for correlation with tool_output_callback
                pending_tools[tool_id] = {
                    "action": tool_input.get("action", content_block.get("name", "unknown")),
                    "input": tool_input,
                    "start_time": time.monotonic(),
                }

            insert_log(
                run_id=run_id,
                level="info",
                event_type="assistant_output",
                message=payload.get("text", f"Tool: {payload.get('tool_name', '')}"),
                payload=payload,
            )

    def tool_output_callback(result: ToolResult, tool_id: str):
        """Save screenshots to Supabase Storage, record steps and logs."""
        step = step_counter["count"]
        step_counter["count"] += 1

        # Look up the pending tool_use for action details + timing
        pending = pending_tools.pop(tool_id, None)
        if pending:
            action_type = pending["action"]
            description = _describe_action(pending["input"])
            duration_ms = int((time.monotonic() - pending["start_time"]) * 1000)
        else:
            action_type = "tool_result"
            description = result.output or result.error or ""
            duration_ms = None

        # Append error info to description if present
        if result.error:
            description = f"{description} [ERROR: {result.error}]" if description else result.error

        # Record the step
        insert_step(
            run_id=run_id,
            step_index=step,
            action_type=action_type,
            description=description,
            duration_ms=duration_ms,
        )

        # Upload screenshot to Supabase Storage
        if result.base64_image:
            last_screenshot_b64["img"] = result.base64_image
            recent_screenshots.append({"b64": result.base64_image, "step": step})
            try:
                upload_screenshot(
                    run_id=run_id,
                    step=step,
                    base64_image=result.base64_image,
                    label=f"Step {step}",
                )
            except Exception as e:
                logger.warning(f"Run {run_id}: failed to upload screenshot step {step}: {e}")

        # Log the tool result
        insert_log(
            run_id=run_id,
            level="info",
            event_type="tool_result",
            message=result.output or result.error or "screenshot",
            payload={
                "tool_id": tool_id,
                "step": step,
                "has_screenshot": result.base64_image is not None,
                "error": result.error,
            },
        )

    def api_response_callback(request, response, error):
        """Log API call metadata."""
        level = "error" if error else "info"
        payload: dict[str, Any] = {
            "method": str(request.method),
            "url": str(request.url),
        }
        if error:
            payload["error"] = str(error)
            logger.error(f"Run {run_id}: API error: {error}")
        if isinstance(response, httpx.Response):
            payload["status_code"] = response.status_code
            if response.status_code >= 400:
                level = "error"
                logger.error(f"Run {run_id}: API returned {response.status_code}")

        insert_log(
            run_id=run_id,
            level=level,
            event_type="api_call",
            message=f"API {payload['method']} {payload['url']}",
            payload=payload,
        )

    # ── Execute ─────────────────────────────────────────────────────

    logger.info(f"Run {run_id}: starting sampling loop for {target_url}")

    try:
        messages = await sampling_loop(
            model=req.model,
            provider=APIProvider.ANTHROPIC,
            system_prompt_suffix=system_prompt,
            messages=[{"role": "user", "content": task}],
            output_callback=output_callback,
            tool_output_callback=tool_output_callback,
            api_response_callback=api_response_callback,
            api_key=api_key,
            only_n_most_recent_images=req.only_n_most_recent_images,
            max_tokens=req.max_tokens,
            tool_version="sentinel_playwright",
            tool_collection_override=tool_collection,
            thinking_budget=req.thinking_budget,
        )

        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        logger.info(f"Run {run_id}: sampling loop returned {len(messages)} messages in {elapsed_ms}ms")

        # Check if Claude actually responded
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        if not assistant_msgs:
            update_run_failed(run_id, duration_ms=elapsed_ms)
            insert_log(
                run_id=run_id,
                level="error",
                event_type="run_error",
                message="No assistant response received from Claude API",
            )
            logger.error(f"Run {run_id}: no assistant messages returned")
            return

        # Warn if Claude didn't use tools (only 2 messages = user + 1 assistant)
        if len(messages) <= 2 and step_counter["count"] == 0:
            logger.warning(
                f"Run {run_id}: Claude responded without using any tools "
                f"({len(messages)} messages, 0 steps). It may not have tested anything."
            )

        # Extract structured JSON from Claude's final message
        raw_summary = _extract_last_text(messages)
        if raw_summary:
            logger.info(f"Run {run_id}: raw final response (first 500 chars): {raw_summary[:500]}")
        else:
            logger.warning(f"Run {run_id}: no text content in final assistant message")
        parsed = _parse_structured_output(raw_summary) if raw_summary else None

        # Determine result
        issues_found = parsed.get("issues", []) if parsed else []
        run_result = "issue_found" if issues_found else "no_issues"

        # Mark run completed
        update_run_completed(run_id, result=run_result, duration_ms=elapsed_ms)

        # Persist issues to DB
        if parsed and issues_found:
            await _persist_issues(
                run_id=run_id,
                project_id=project_id,
                issues=issues_found,
                slack_channel_id=slack_channel_id["id"],
                target_url=target_url,
                device_label=device_label,
                network_label=network_label,
                realtime_issues_reported=realtime_issues_reported,
                recent_screenshots=list(recent_screenshots),
            )

        # Persist UX confusion events
        ux_confusion_events = parsed.get("ux_confusion_events", []) if parsed else []
        if ux_confusion_events:
            for event in ux_confusion_events:
                insert_log(
                    run_id=run_id,
                    level="warn",
                    event_type="ux_confusion",
                    message=(
                        f"UX confusion on '{event.get('screen', 'unknown')}': "
                        f"{event.get('confusion_reason', 'unspecified')}"
                    ),
                    payload=event,
                )
            logger.info(
                f"Run {run_id}: {len(ux_confusion_events)} UX confusion events logged"
            )

        # Persist locale/translation issues
        locale_issues = parsed.get("locale_issues", []) if parsed else []
        if locale_issues:
            for li in locale_issues:
                insert_log(
                    run_id=run_id,
                    level="warn",
                    event_type="locale_issue",
                    message=(
                        f"Locale issue: {li.get('type', 'unknown')} — "
                        f"found '{li.get('text_found', '')}' "
                        f"(expected {li.get('expected_language', 'unknown')})"
                    ),
                    payload=li,
                )
            logger.info(
                f"Run {run_id}: {len(locale_issues)} locale issues logged"
            )

        # Log CAPTCHA encounters
        if parsed and parsed.get("captcha_encountered"):
            insert_log(
                run_id=run_id,
                level="warn",
                event_type="captcha_encountered",
                message=f"CAPTCHA/OTP gate encountered: {parsed.get('captcha_details', 'unknown')}",
                payload={
                    "captcha_details": parsed.get("captcha_details"),
                },
            )

        # Log completion
        insert_log(
            run_id=run_id,
            level="info",
            event_type="run_complete",
            message=parsed.get("summary", "Run completed") if parsed else "Run completed",
            payload={
                "step_count": step_counter["count"],
                "issue_count": len(issues_found),
                "ux_confusion_count": len(ux_confusion_events),
                "locale_issue_count": len(locale_issues),
                "captcha_encountered": parsed.get("captcha_encountered", False) if parsed else False,
                "message_count": len(messages),
                "tests_passed": parsed.get("tests_passed", []) if parsed else [],
                "recommendations": parsed.get("recommendations", []) if parsed else [],
                "duration_ms": elapsed_ms,
            },
        )

        # ── Collect perf metrics before closing browser ─────────────
        # (Capture metrics from the last page visited)
        try:
            await pw_tool.collect_perf_metrics(step=step_counter["count"])
        except Exception as e:
            logger.debug(f"Run {run_id}: final perf metrics collection: {e}")

        # ── Run a11y audit on current page before browser closes ────
        try:
            await pw_tool.run_accessibility_audit(standard="wcag21aa")
        except Exception as e:
            logger.debug(f"Run {run_id}: a11y audit: {e}")

        # Upload videos (Playwright saves them on context close)
        await pw_tool.close()
        _upload_run_videos(run_id, video_dir)

        # ── Performance Metrics Collection ──────────────────────────
        try:
            perf_data = pw_tool.get_perf_metrics()
            for pm in perf_data:
                insert_perf_metrics(
                    run_id=run_id,
                    url=pm.get("url", target_url),
                    lcp_ms=pm.get("lcp_ms"),
                    cls=pm.get("cls"),
                    ttfb_ms=pm.get("ttfb_ms"),
                    fcp_ms=pm.get("fcp_ms"),
                    dom_content_loaded_ms=pm.get("dom_content_loaded_ms"),
                    resource_count=pm.get("resource_count"),
                    total_transfer_kb=pm.get("total_transfer_kb"),
                    step=pm.get("step"),
                )
            if perf_data:
                insert_log(
                    run_id=run_id,
                    level="info",
                    event_type="perf_metrics_collected",
                    message=f"Collected performance metrics for {len(perf_data)} page(s)",
                    payload={"metrics_count": len(perf_data), "metrics": perf_data},
                )
                logger.info(f"Run {run_id}: persisted {len(perf_data)} perf metric row(s)")
        except Exception as e:
            logger.warning(f"Run {run_id}: perf metrics persistence failed: {e}")

        # ── Accessibility Audit (axe-core) ──────────────────────────
        a11y_issue_count = 0
        try:
            a11y_violations = pw_tool.get_a11y_violations()
            if a11y_violations:
                a11y_issue_count = await _persist_a11y_violations(
                    run_id=run_id,
                    project_id=project_id,
                    violations=a11y_violations,
                    target_url=target_url,
                    device_label=device_label,
                    network_label=network_label,
                    slack_channel_id=slack_channel_id["id"],
                    realtime_issues_reported=realtime_issues_reported,
                )
                logger.info(
                    f"Run {run_id}: {a11y_issue_count} a11y issues created "
                    f"from {len(a11y_violations)} violations"
                )
        except Exception as e:
            logger.warning(f"Run {run_id}: a11y audit persistence failed: {e}")

        # ── Cross-Run Regression Detection ──────────────────────────
        regression_count = 0
        try:
            regression_count = await _check_regressions(
                run_id=run_id,
                project_id=project_id,
                device_id=req.device_id,
                network_id=req.network_id,
                current_issues=issues_found,
                tests_passed=parsed.get("tests_passed", []) if parsed else [],
                target_url=target_url,
                device_label=device_label,
                network_label=network_label,
                slack_channel_id=slack_channel_id["id"],
            )
            if regression_count:
                logger.info(f"Run {run_id}: {regression_count} regression(s) detected")
        except Exception as e:
            logger.warning(f"Run {run_id}: regression detection failed: {e}")

        # ── Flaky Test Detection (P0/P1 only) ───────────────────────
        flaky_results = {}
        try:
            p0p1_issues = [
                i for i in issues_found
                if i.get("severity") in ("P0", "P1")
                and i.get("title") not in realtime_issues_reported
            ]
            if p0p1_issues:
                flaky_results = await _run_flaky_detection(
                    run_id=run_id,
                    project_id=project_id,
                    req=req,
                    target_url=target_url,
                    device=device,
                    network=network,
                    project_data=project_data,
                    api_key=api_key,
                    p0p1_issues=p0p1_issues,
                    slack_channel_id=slack_channel_id["id"],
                )
        except Exception as e:
            logger.warning(f"Run {run_id}: flaky detection failed: {e}")

        # ── Slack run summary ───────────────────────────────────────
        if slack_channel_id["id"]:
            try:
                await post_run_summary_to_slack(
                    channel_id=slack_channel_id["id"],
                    run_id=run_id,
                    target_url=target_url,
                    device_label=device_label,
                    network_label=network_label,
                    issue_count=len(issues_found),
                    step_count=step_counter["count"],
                    duration_ms=elapsed_ms,
                    tests_passed=parsed.get("tests_passed", []) if parsed else [],
                    ux_confusion_count=len(ux_confusion_events),
                    locale_issue_count=len(locale_issues),
                    captcha_encountered=parsed.get("captcha_encountered", False) if parsed else False,
                )
            except Exception as e:
                logger.warning(f"Run {run_id}: failed to post Slack run summary: {e}")

        logger.info(
            f"Run {run_id} completed: {step_counter['count']} steps, "
            f"{len(issues_found)} issues, {elapsed_ms}ms"
        )

    except Exception as e:
        elapsed_ms = int((time.monotonic() - start_time) * 1000)
        update_run_failed(run_id, duration_ms=elapsed_ms)
        insert_log(
            run_id=run_id,
            level="error",
            event_type="run_error",
            message=f"{type(e).__name__}: {e}",
            payload={"traceback": traceback.format_exc()},
        )
        logger.error(f"Run {run_id} failed: {e}", exc_info=True)
        await pw_tool.close()


async def _persist_issues(
    *,
    run_id: str,
    project_id: str,
    issues: list[dict[str, Any]],
    slack_channel_id: str | None = None,
    target_url: str = "",
    device_label: str = "",
    network_label: str = "",
    realtime_issues_reported: set[str] | None = None,
    recent_screenshots: list[dict[str, Any]] | None = None,
) -> None:
    """Create issue rows, link to run, perform root cause analysis, and notify Slack."""
    for issue_data in issues:
        try:
            severity = issue_data.get("severity", "P2")
            if severity not in ("P0", "P1", "P2", "P3"):
                severity = "P2"

            # Skip DB creation if already created in real-time
            title = issue_data.get("title", "Untitled issue")
            already_reported = realtime_issues_reported and title in realtime_issues_reported

            if already_reported:
                logger.info(f"Run {run_id}: issue \"{title}\" already reported in real-time, skipping")
                continue

            # Resolve Slack user for the category owner
            owner_slack_id = _get_owner_for_category(
                issue_data.get("category"), project_id=project_id
            )
            issue = create_issue(
                project_id=project_id,
                title=title,
                description=issue_data.get("description"),
                severity=severity,
                category=issue_data.get("category"),
                run_id=run_id,
                slack_user_id=owner_slack_id,
            )
            link_issue_to_run(issue["id"], run_id)

            # Link screenshot evidence if screenshot_step is specified
            screenshot_step = issue_data.get("screenshot_step")
            if screenshot_step is not None:
                _link_screenshot_to_issue(run_id, issue["id"], screenshot_step)

            # ── Root Cause Intelligence ─────────────────────────────
            similar = []
            try:
                similar = find_similar_issues(
                    project_id=project_id,
                    title=issue_data.get("title", ""),
                    description=issue_data.get("description"),
                    threshold=0.35,
                    max_results=3,
                    exclude_issue_id=issue["id"],
                )
                if similar:
                    related_ids = [s["id"] for s in similar]
                    related_titles = [
                        f"{s['id'][:8]}… ({s['severity']}, score={s['similarity_score']}) \"{s['title']}\""
                        for s in similar
                    ]
                    insert_log(
                        run_id=run_id,
                        level="info",
                        event_type="root_cause_match",
                        message=(
                            f"Issue \"{issue_data.get('title')}\" is similar to "
                            f"{len(similar)} existing issue(s)"
                        ),
                        payload={
                            "new_issue_id": issue["id"],
                            "similar_issues": related_ids,
                            "matches": related_titles,
                            "top_similarity": similar[0]["similarity_score"],
                        },
                    )
                    logger.info(
                        f"Run {run_id}: issue {issue['id'][:8]}… has {len(similar)} "
                        f"similar issues (top score: {similar[0]['similarity_score']})"
                    )
            except Exception as e:
                logger.warning(f"Run {run_id}: root cause analysis failed: {e}")

            # ── Slack Notification (end-of-run issues) ──────────────
            if slack_channel_id:
                try:
                    screenshot_b64 = None
                    if screenshot_step is not None:
                        screenshot_b64 = _get_screenshot_b64_for_step(run_id, screenshot_step)
                    await post_issue_to_slack(
                        channel_id=slack_channel_id,
                        issue_data=issue_data,
                        issue_db_row=issue,
                        run_id=run_id,
                        target_url=target_url,
                        device_label=device_label,
                        network_label=network_label,
                        project_id=project_id,
                        screenshot_base64=screenshot_b64,
                        recent_screenshots=recent_screenshots or [],
                        similar_issues=similar,
                        is_realtime=False,
                    )
                except Exception as e:
                    logger.warning(f"Run {run_id}: Slack notification failed: {e}")

            logger.info(f"Run {run_id}: created issue {issue['id']} — {issue_data.get('title')}")
        except Exception as e:
            logger.warning(f"Run {run_id}: failed to persist issue: {e}")


def _link_screenshot_to_issue(run_id: str, issue_id: str, step: int) -> None:
    """Find the evidence row for a screenshot step and link it to an issue."""
    try:
        from sentinel.db.client import get_supabase

        sb = get_supabase()
        storage_path = f"{run_id}/step_{step:03d}.png"
        result = (
            sb.table("evidence")
            .select("id")
            .eq("run_id", run_id)
            .eq("storage_path", storage_path)
            .execute()
        )
        if result.data:
            link_evidence_to_issue(result.data[0]["id"], issue_id)
    except Exception as e:
        logger.warning(f"Failed to link screenshot step {step} to issue {issue_id}: {e}")


def _get_screenshot_b64_for_step(run_id: str, step: int) -> str | None:
    """Retrieve a screenshot's base64 content from Supabase Storage for Slack upload."""
    try:
        import base64 as b64module
        from sentinel.db.client import get_supabase
        from sentinel.db.db_evidence import SCREENSHOT_BUCKET

        sb = get_supabase()
        storage_path = f"{run_id}/step_{step:03d}.png"
        file_bytes = sb.storage.from_(SCREENSHOT_BUCKET).download(storage_path)
        if file_bytes:
            return b64module.b64encode(file_bytes).decode("utf-8")
    except Exception as e:
        logger.debug(f"Could not retrieve screenshot for step {step}: {e}")
    return None


def _check_realtime_issue(
    text: str,
    *,
    run_id: str,
    project_id: str,
    target_url: str,
    device_label: str,
    network_label: str,
    slack_channel_id: str | None,
    realtime_issues_reported: set[str],
    last_screenshot_b64: str | None,
    recent_screenshots: list[dict[str, Any]] | None = None,
) -> None:
    """Parse real-time 🚨 ISSUE_FOUND markers from Claude's text output.

    When found, immediately creates the issue in the DB and sends a Slack notification.
    This runs synchronously in the output_callback context.
    """
    MARKER = "🚨 ISSUE_FOUND:"
    if MARKER not in text:
        return

    # May have multiple markers in one text block
    for line in text.split("\n"):
        line = line.strip()
        if not line.startswith(MARKER):
            continue

        json_str = line[len(MARKER):].strip()
        try:
            issue_data = json.loads(json_str)
        except (json.JSONDecodeError, ValueError):
            logger.warning(f"Run {run_id}: failed to parse real-time issue JSON: {json_str[:200]}")
            continue

        title = issue_data.get("title", "Untitled issue")
        if title in realtime_issues_reported:
            continue  # Already handled
        realtime_issues_reported.add(title)

        severity = issue_data.get("severity", "P2")
        if severity not in ("P0", "P1", "P2", "P3"):
            severity = "P2"

        logger.info(f"Run {run_id}: ⚡ REAL-TIME issue detected: [{severity}] {title}")

        # Create issue in DB immediately
        try:
            owner_slack_id = _get_owner_for_category(
                issue_data.get("category"), project_id=project_id
            )
            issue = create_issue(
                project_id=project_id,
                title=title,
                description=issue_data.get("description"),
                severity=severity,
                category=issue_data.get("category"),
                run_id=run_id,
                slack_user_id=owner_slack_id,
            )
            link_issue_to_run(issue["id"], run_id)

            # Link screenshot if available
            screenshot_step = issue_data.get("screenshot_step")
            if screenshot_step is not None:
                _link_screenshot_to_issue(run_id, issue["id"], screenshot_step)

            insert_log(
                run_id=run_id,
                level="warn",
                event_type="realtime_issue",
                message=f"⚡ [{severity}] {title}",
                payload={
                    "issue_id": issue["id"],
                    "issue_data": issue_data,
                    "realtime": True,
                },
            )

            # Send Slack notification immediately
            if slack_channel_id:
                # Find similar issues for root cause context
                similar = []
                try:
                    similar = find_similar_issues(
                        project_id=project_id,
                        title=title,
                        description=issue_data.get("description"),
                        threshold=0.35,
                        max_results=3,
                        exclude_issue_id=issue["id"],
                    )
                except Exception:
                    pass

                # Get screenshot for Slack — prefer stored, fallback to last captured
                screenshot_for_slack = None
                if screenshot_step is not None:
                    screenshot_for_slack = _get_screenshot_b64_for_step(run_id, screenshot_step)
                if not screenshot_for_slack:
                    screenshot_for_slack = last_screenshot_b64

                try:
                    loop = asyncio.get_event_loop()
                    loop.create_task(
                        post_issue_to_slack(
                            channel_id=slack_channel_id,
                            issue_data=issue_data,
                            issue_db_row=issue,
                            run_id=run_id,
                            target_url=target_url,
                            device_label=device_label,
                            network_label=network_label,
                            project_id=project_id,
                            screenshot_base64=screenshot_for_slack,
                            recent_screenshots=recent_screenshots,
                            similar_issues=similar,
                            is_realtime=True,
                        )
                    )
                except Exception as e:
                    logger.warning(f"Run {run_id}: real-time Slack notification failed: {e}")

        except Exception as e:
            logger.warning(f"Run {run_id}: failed to persist real-time issue: {e}")


def _upload_run_videos(run_id: str, video_dir: str) -> None:
    """Upload all video files from the temp directory to Supabase Storage."""
    for video_path in glob.glob(os.path.join(video_dir, "*.webm")):
        try:
            upload_video(run_id=run_id, local_path=video_path, label="Session recording")
            logger.info(f"Run {run_id}: uploaded video {os.path.basename(video_path)}")
        except Exception as e:
            logger.warning(f"Run {run_id}: failed to upload video: {e}")


# ── Accessibility Audit Persistence ─────────────────────────────────────


# Map axe-core impact levels to SentinelBot severities
_AXE_IMPACT_TO_SEVERITY = {
    "critical": "P0",
    "serious": "P1",
    "moderate": "P2",
    "minor": "P3",
}


async def _persist_a11y_violations(
    *,
    run_id: str,
    project_id: str,
    violations: list[dict[str, Any]],
    target_url: str,
    device_label: str,
    network_label: str,
    slack_channel_id: str | None,
    realtime_issues_reported: set[str],
) -> int:
    """Convert axe-core violations to issues and persist to DB.

    Returns the number of issues created.
    """
    created = 0
    for v in violations:
        impact = v.get("impact", "minor")
        severity = _AXE_IMPACT_TO_SEVERITY.get(impact, "P2")
        title = f"A11y: {v.get('help', v.get('id', 'unknown'))}"

        # Skip if already reported in real-time
        if title in realtime_issues_reported:
            continue

        # Build description with affected elements
        nodes_desc = ""
        nodes = v.get("nodes", [])
        if nodes:
            node_lines = []
            for n in nodes[:3]:
                target = n.get("target", ["unknown"])
                target_str = " > ".join(target) if isinstance(target, list) else str(target)
                summary = n.get("failureSummary", "")
                node_lines.append(f"  • {target_str}: {summary}")
            nodes_desc = "\nAffected elements:\n" + "\n".join(node_lines)

        description = (
            f"{v.get('description', '')}\n"
            f"WCAG Rule: {v.get('id', 'unknown')}\n"
            f"Impact: {impact}\n"
            f"Help: {v.get('helpUrl', 'N/A')}"
            f"{nodes_desc}"
        )

        try:
            owner_slack_id = _get_owner_for_category(
                "accessibility", project_id=project_id
            )
            issue = create_issue(
                project_id=project_id,
                title=title,
                description=description,
                severity=severity,
                category="accessibility",
                run_id=run_id,
                slack_user_id=owner_slack_id,
            )
            link_issue_to_run(issue["id"], run_id)
            created += 1

            insert_log(
                run_id=run_id,
                level="warn",
                event_type="a11y_violation",
                message=f"[{severity}] {title}",
                payload={
                    "issue_id": issue["id"],
                    "axe_rule_id": v.get("id"),
                    "impact": impact,
                    "help_url": v.get("helpUrl"),
                    "node_count": len(nodes),
                },
            )

            # Notify Slack
            if slack_channel_id:
                try:
                    await post_issue_to_slack(
                        channel_id=slack_channel_id,
                        issue_data={
                            "title": title,
                            "description": description,
                            "severity": severity,
                            "severity_justification": f"axe-core: {impact} impact WCAG 2.1 AA violation",
                            "category": "accessibility",
                            "steps_to_reproduce": [
                                f"Navigate to {target_url}",
                                "Run axe-core accessibility audit",
                                f"Violation: {v.get('id')} ({impact})",
                            ],
                            "expected": "Page should pass WCAG 2.1 AA accessibility checks",
                            "actual": v.get("help", "Accessibility violation detected"),
                        },
                        issue_db_row=issue,
                        run_id=run_id,
                        target_url=target_url,
                        device_label=device_label,
                        network_label=network_label,
                        project_id=project_id,
                        is_realtime=False,
                    )
                except Exception as e:
                    logger.warning(f"Run {run_id}: a11y Slack notification failed: {e}")

        except Exception as e:
            logger.warning(f"Run {run_id}: failed to create a11y issue '{title}': {e}")

    return created


# ── Cross-Run Regression Detection ──────────────────────────────────────


async def _check_regressions(
    *,
    run_id: str,
    project_id: str,
    device_id: str,
    network_id: str,
    current_issues: list[dict[str, Any]],
    tests_passed: list[str],
    target_url: str,
    device_label: str,
    network_label: str,
    slack_channel_id: str | None,
) -> int:
    """Compare current run against previous run to detect regressions.

    A regression is detected when:
    - A test that passed in the previous run now has a matching issue, OR
    - The previous run had no issues of a certain type but now one appears

    Returns the number of regressions detected.
    """
    prev_run = get_previous_run(
        project_id=project_id,
        device_id=device_id,
        network_id=network_id,
        exclude_run_id=run_id,
    )
    if not prev_run:
        logger.info(f"Run {run_id}: no previous run found for regression comparison")
        return 0

    prev_run_id = prev_run["id"]

    # Get previous run's issues
    prev_issues = get_issues_for_run(prev_run_id)
    prev_issue_titles = {i.get("title", "").lower().strip() for i in prev_issues}

    # Get previous run's logs to find tests_passed
    from sentinel.db.db_logs import get_logs_for_run
    prev_logs = get_logs_for_run(prev_run_id)
    prev_tests_passed: list[str] = []
    for log in prev_logs:
        if log.get("event_type") == "run_complete":
            payload = log.get("payload", {})
            prev_tests_passed = payload.get("tests_passed", [])
            break

    if not prev_tests_passed:
        logger.info(f"Run {run_id}: previous run had no tests_passed data, skipping regression check")
        return 0

    # Find regressions: tests that passed before but now have matching issues
    regression_count = 0
    current_issue_titles_lower = [i.get("title", "").lower().strip() for i in current_issues]

    from sentinel.db.db_issues import _tokenize, _jaccard_similarity

    for passed_test in prev_tests_passed:
        passed_tokens = _tokenize(passed_test)
        if not passed_tokens:
            continue

        # Check if any current issue matches this previously-passing test
        for issue_data in current_issues:
            issue_title = issue_data.get("title", "")
            issue_tokens = _tokenize(issue_title + " " + issue_data.get("description", ""))
            similarity = _jaccard_similarity(passed_tokens, issue_tokens)

            if similarity >= 0.3:
                # Regression detected!
                regression_count += 1
                regression_title = f"⚠️ REGRESSION: {issue_data.get('title', 'Unknown')}"

                logger.warning(
                    f"Run {run_id}: REGRESSION — '{passed_test}' passed in run "
                    f"{prev_run_id[:8]}… but now has issue: {issue_data.get('title')}"
                )

                # Create regression issue
                try:
                    owner_slack_id = _get_owner_for_category(
                        "regression", project_id=project_id
                    )
                    reg_issue = create_issue(
                        project_id=project_id,
                        title=regression_title,
                        description=(
                            f"This is a regression. The test '{passed_test}' passed in the "
                            f"previous run ({prev_run_id[:8]}…) but now fails.\n\n"
                            f"Current issue: {issue_data.get('description', 'N/A')}\n"
                            f"Previous run: {prev_run_id}\n"
                            f"Current run: {run_id}\n"
                            f"Similarity score: {similarity:.3f}"
                        ),
                        severity=issue_data.get("severity", "P1"),
                        category="regression",
                        run_id=run_id,
                        slack_user_id=owner_slack_id,
                    )
                    link_issue_to_run(reg_issue["id"], run_id)

                    insert_log(
                        run_id=run_id,
                        level="error",
                        event_type="regression_detected",
                        message=regression_title,
                        payload={
                            "regression_issue_id": reg_issue["id"],
                            "previous_run_id": prev_run_id,
                            "previously_passed": passed_test,
                            "current_issue_title": issue_data.get("title"),
                            "similarity_score": round(similarity, 3),
                        },
                    )

                    # Slack notification
                    if slack_channel_id:
                        try:
                            await post_issue_to_slack(
                                channel_id=slack_channel_id,
                                issue_data={
                                    "title": regression_title,
                                    "description": (
                                        f"⚠️ *REGRESSION DETECTED*\n\n"
                                        f"The test *\"{passed_test}\"* passed in the previous run "
                                        f"(`{prev_run_id[:8]}…`) but now has an issue.\n\n"
                                        f"*Current issue:* {issue_data.get('description', 'N/A')}"
                                    ),
                                    "severity": issue_data.get("severity", "P1"),
                                    "severity_justification": (
                                        "Regression — this functionality was working in the previous run"
                                    ),
                                    "category": "regression",
                                    "steps_to_reproduce": issue_data.get("steps_to_reproduce", []),
                                    "expected": f"Should work as it did in run {prev_run_id[:8]}…",
                                    "actual": issue_data.get("actual", "Regression observed"),
                                },
                                issue_db_row=reg_issue,
                                run_id=run_id,
                                target_url=target_url,
                                device_label=device_label,
                                network_label=network_label,
                                project_id=project_id,
                                is_realtime=False,
                            )
                        except Exception as e:
                            logger.warning(f"Run {run_id}: regression Slack notification failed: {e}")

                except Exception as e:
                    logger.warning(f"Run {run_id}: failed to create regression issue: {e}")

                break  # One regression per passed_test is enough

    if regression_count:
        insert_log(
            run_id=run_id,
            level="error",
            event_type="regression_summary",
            message=f"{regression_count} regression(s) detected vs run {prev_run_id[:8]}…",
            payload={
                "regression_count": regression_count,
                "previous_run_id": prev_run_id,
                "previous_tests_passed_count": len(prev_tests_passed),
                "current_issue_count": len(current_issues),
            },
        )

    return regression_count


# ── Flaky Test Detection ────────────────────────────────────────────────


async def _run_flaky_detection(
    *,
    run_id: str,
    project_id: str,
    req: TestRequest,
    target_url: str,
    device: dict[str, Any],
    network: dict[str, Any],
    project_data: dict[str, Any] | None,
    api_key: str,
    p0p1_issues: list[dict[str, Any]],
    slack_channel_id: str | None,
) -> dict[str, Any]:
    """Run flaky test detection for P0/P1 issues.

    Performs up to 2 verification runs targeting the failing flows.
    Uses majority vote (2/3) to confirm or mark issues as flaky.

    Returns a summary dict with confirmed and flaky issue counts.
    """
    logger.info(
        f"Run {run_id}: starting flaky detection for {len(p0p1_issues)} P0/P1 issue(s)"
    )

    insert_log(
        run_id=run_id,
        level="info",
        event_type="flaky_detection_start",
        message=f"Verifying {len(p0p1_issues)} P0/P1 issues with 2 re-runs",
        payload={"issues": [i.get("title") for i in p0p1_issues]},
    )

    # Build a focused verification task
    issue_descriptions = []
    for i, issue in enumerate(p0p1_issues[:5], 1):  # Cap at 5 issues
        issue_descriptions.append(
            f"{i}. [{issue.get('severity', 'P1')}] {issue.get('title', 'Unknown')}: "
            f"{issue.get('description', 'No description')[:200]}"
        )
    issues_text = "\n".join(issue_descriptions)

    verification_task = (
        f"Navigate to {target_url} and VERIFY the following issues. "
        f"For each issue, try to reproduce it using the same steps. "
        f"Report ONLY these specific issues if you can reproduce them. "
        f"If an issue does not reproduce, note it in tests_passed.\n\n"
        f"Issues to verify:\n{issues_text}"
    )

    # Track reproduction counts per issue title
    reproduced: dict[str, int] = {i.get("title", ""): 1 for i in p0p1_issues}  # 1 = original run
    total_attempts: dict[str, int] = {i.get("title", ""): 1 for i in p0p1_issues}

    # Run 2 verification rounds
    for verification_round in range(1, 3):
        logger.info(f"Run {run_id}: flaky verification round {verification_round}/2")

        try:
            # Create a verification run
            verify_run = create_run(
                project_id=project_id,
                device_id=req.device_id,
                network_id=req.network_id,
                locale=req.locale,
                persona=req.persona,
            )
            verify_run_id = verify_run["id"]

            insert_log(
                run_id=verify_run_id,
                level="info",
                event_type="flaky_verification_run",
                message=f"Flaky verification round {verification_round}/2 for run {run_id[:8]}…",
                payload={"original_run_id": run_id, "round": verification_round},
            )

            # Set up a minimal Playwright instance for verification
            pw_device_profile = device_to_playwright_profile(device)
            pw_network_profile = network_to_throttle_profile(network)
            verify_video_dir = os.path.join(VIDEO_TMP_DIR, verify_run_id)
            os.makedirs(verify_video_dir, exist_ok=True)

            verify_pw = PlaywrightComputerTool(
                device_profile_dict=pw_device_profile,
                network_profile_dict=pw_network_profile,
                target_url=target_url,
                locale=req.locale,
                video_dir=verify_video_dir,
            )
            verify_tool_collection = ToolCollection(verify_pw, BashTool20250124())

            device_label = f"{device['name']} ({device['viewport_width']}x{device['viewport_height']})"
            network_label = network["name"]

            system_prompt = get_sentinel_system_prompt(
                device_label=device_label,
                network_label=network_label,
                target_url=target_url,
                persona=req.persona,
                locale=req.locale,
            )

            verify_start = time.monotonic()

            messages = await sampling_loop(
                model=req.model,
                provider=APIProvider.ANTHROPIC,
                system_prompt_suffix=system_prompt,
                messages=[{"role": "user", "content": verification_task}],
                output_callback=lambda _: None,
                tool_output_callback=lambda result, tid: None,
                api_response_callback=lambda req, resp, err: None,
                api_key=api_key,
                only_n_most_recent_images=req.only_n_most_recent_images,
                max_tokens=req.max_tokens,
                tool_version="sentinel_playwright",
                tool_collection_override=verify_tool_collection,
                thinking_budget=req.thinking_budget,
            )

            verify_elapsed = int((time.monotonic() - verify_start) * 1000)
            await verify_pw.close()

            # Parse the verification results
            raw = _extract_last_text(messages)
            parsed = _parse_structured_output(raw) if raw else None

            if parsed:
                verify_issues = parsed.get("issues", [])
                verify_passed = parsed.get("tests_passed", [])

                verify_issue_titles = {i.get("title", "").lower().strip() for i in verify_issues}

                for issue_title in reproduced:
                    total_attempts[issue_title] = total_attempts.get(issue_title, 1) + 1
                    # Check if this issue reproduced
                    issue_tokens = _tokenize(issue_title)
                    for vi in verify_issues:
                        vi_tokens = _tokenize(vi.get("title", "") + " " + vi.get("description", ""))
                        if _jaccard_similarity(issue_tokens, vi_tokens) >= 0.3:
                            reproduced[issue_title] = reproduced.get(issue_title, 1) + 1
                            break

                update_run_completed(verify_run_id, result="flaky_verification", duration_ms=verify_elapsed)
            else:
                update_run_failed(verify_run_id, duration_ms=verify_elapsed)

        except Exception as e:
            logger.warning(f"Run {run_id}: flaky verification round {verification_round} failed: {e}")

    # Analyze results — 2/3 majority vote
    confirmed_issues = []
    flaky_issues = []

    for issue_data in p0p1_issues:
        title = issue_data.get("title", "")
        repro_count = reproduced.get(title, 1)
        attempt_count = total_attempts.get(title, 1)

        if repro_count >= 2:
            # Confirmed — reproduced in ≥2 out of 3 runs
            confirmed_issues.append(title)
            insert_log(
                run_id=run_id,
                level="info",
                event_type="flaky_confirmed",
                message=f"✅ CONFIRMED: [{issue_data.get('severity')}] {title} ({repro_count}/{attempt_count} runs)",
                payload={
                    "issue_title": title,
                    "reproduced": repro_count,
                    "total_attempts": attempt_count,
                    "confirmed": True,
                },
            )
        else:
            # Flaky — reproduced in only 1 out of 3 runs
            flaky_issues.append(title)
            insert_log(
                run_id=run_id,
                level="warn",
                event_type="flaky_detected",
                message=f"🔄 FLAKY: [{issue_data.get('severity')}] {title} ({repro_count}/{attempt_count} runs)",
                payload={
                    "issue_title": title,
                    "reproduced": repro_count,
                    "total_attempts": attempt_count,
                    "flaky": True,
                },
            )

            # Update the issue in DB to mark as flaky (downgrade severity by 1 level)
            try:
                from sentinel.db.client import get_supabase
                sb = get_supabase()
                severity_downgrade = {
                    "P0": "P1",
                    "P1": "P2",
                }
                new_severity = severity_downgrade.get(issue_data.get("severity", "P1"), "P2")
                sb.table("issues").update({
                    "status": "flaky",
                    "severity": new_severity,
                }).eq("title", title).eq("run_id", run_id).execute()
            except Exception as e:
                logger.warning(f"Run {run_id}: failed to update flaky issue: {e}")

    # Slack summary for flaky detection
    if slack_channel_id and (confirmed_issues or flaky_issues):
        try:
            from sentinel.slack_notifier import _get_token, _headers, SLACK_API
            token = _get_token()
            if token:
                confirmed_text = "\n".join(f"  ✅ {t}" for t in confirmed_issues) or "  _None_"
                flaky_text = "\n".join(f"  🔄 {t}" for t in flaky_issues) or "  _None_"

                blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🔄 Flaky Test Detection Results",
                            "emoji": True,
                        },
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": (
                                f"Verified {len(p0p1_issues)} P0/P1 issues with 2 re-runs "
                                f"(3 total attempts per issue).\n\n"
                                f"*Confirmed (≥2/3 reproduced):*\n{confirmed_text}\n\n"
                                f"*Flaky (1/3 reproduced — severity downgraded):*\n{flaky_text}"
                            ),
                        },
                    },
                    {
                        "type": "context",
                        "elements": [
                            {"type": "mrkdwn", "text": f"Original run `{run_id[:8]}…`"},
                        ],
                    },
                ]

                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{SLACK_API}/chat.postMessage",
                        headers=_headers(token),
                        json={
                            "channel": slack_channel_id,
                            "blocks": blocks,
                            "text": f"🔄 Flaky detection: {len(confirmed_issues)} confirmed, {len(flaky_issues)} flaky",
                        },
                    )
        except Exception as e:
            logger.warning(f"Run {run_id}: flaky detection Slack summary failed: {e}")

    result = {
        "confirmed_count": len(confirmed_issues),
        "flaky_count": len(flaky_issues),
        "confirmed": confirmed_issues,
        "flaky": flaky_issues,
    }

    insert_log(
        run_id=run_id,
        level="info",
        event_type="flaky_detection_complete",
        message=(
            f"Flaky detection complete: {len(confirmed_issues)} confirmed, "
            f"{len(flaky_issues)} flaky"
        ),
        payload=result,
    )

    logger.info(
        f"Run {run_id}: flaky detection — "
        f"{len(confirmed_issues)} confirmed, {len(flaky_issues)} flaky"
    )

    return result


# ── Helpers ─────────────────────────────────────────────────────────────


def _extract_last_text(messages: list) -> str | None:
    """Get the text content of the last assistant message."""
    for msg in reversed(messages):
        if msg.get("role") == "assistant":
            content = msg.get("content", [])
            if isinstance(content, list):
                for block in content:
                    if isinstance(block, dict) and block.get("type") == "text":
                        return block["text"]
            break
    return None


def _parse_structured_output(text: str) -> dict | None:
    """Extract structured JSON from Claude's final response.

    Tries multiple strategies:
    1. JSON inside ```json ... ``` fences (greedy brace matching)
    2. First top-level { ... } in the text
    3. The raw text itself as JSON
    """
    # Strategy 1: fenced code block
    match = re.search(r"```(?:json)?\s*\n?(\{.+\})\s*```", text, re.DOTALL)
    if match:
        raw = match.group(1)
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return data
        except (json.JSONDecodeError, ValueError):
            pass

    # Strategy 2: find the outermost { ... } by brace counting
    start = text.find("{")
    if start != -1:
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    raw = text[start : i + 1]
                    try:
                        data = json.loads(raw)
                        if isinstance(data, dict):
                            return data
                    except (json.JSONDecodeError, ValueError):
                        pass
                    break

    # Strategy 3: raw text
    try:
        data = json.loads(text.strip())
        if isinstance(data, dict):
            return data
    except (json.JSONDecodeError, ValueError):
        pass

    logger.warning(
        f"Failed to parse structured JSON from Claude's response. "
        f"First 300 chars: {text[:300]}"
    )
    return None


# ── Scheduler Endpoints ─────────────────────────────────────────────────


class ScheduleRequest(BaseModel):
    """Request body for creating a continuous monitoring schedule."""

    project_id: str
    device_ids: list[str]
    network_ids: list[str]
    locales: list[str] = ["en-US"]
    personas: list[str | None] = [None]
    interval_minutes: int = 60
    model: str = "claude-sonnet-4-5-20250929"
    max_tokens: int = 8192
    thinking_budget: int | None = None
    only_n_most_recent_images: int = 3
    task: str | None = None
    input_data: dict[str, str] | None = None
    sensitive_keys: list[str] | None = None


@app.post("/api/schedules")
async def create_schedule(req: ScheduleRequest):
    """Create and start a continuous monitoring schedule.

    The scheduler will rotate through all combinations of device × network × locale × persona,
    running one test per interval.
    """
    config = ScheduleConfig(
        project_id=req.project_id,
        device_ids=req.device_ids,
        network_ids=req.network_ids,
        locales=req.locales,
        personas=req.personas,
        interval_minutes=req.interval_minutes,
        model=req.model,
        max_tokens=req.max_tokens,
        thinking_budget=req.thinking_budget,
        only_n_most_recent_images=req.only_n_most_recent_images,
        task=req.task,
        input_data=req.input_data,
        sensitive_keys=req.sensitive_keys,
    )

    state = scheduler.create_schedule(config)

    # Build the total combo count for the response
    combo_count = (
        len(req.device_ids)
        * len(req.network_ids)
        * len(req.locales)
        * len(req.personas)
    )

    # Start the schedule with a function that triggers _execute_run
    scheduler.start_schedule(state.schedule_id, _scheduled_run_trigger)

    return {
        "schedule_id": state.schedule_id,
        "status": "running",
        "combo_count": combo_count,
        "interval_minutes": req.interval_minutes,
        "detail": f"Schedule created. {combo_count} combos will rotate every {req.interval_minutes}m.",
    }


@app.get("/api/schedules")
async def list_schedules():
    """List all schedules (active and stopped)."""
    return [
        {
            "schedule_id": s.schedule_id,
            "project_id": s.config.project_id,
            "is_running": s.is_running,
            "total_runs": s.total_runs,
            "last_run_at": s.last_run_at,
            "interval_minutes": s.config.interval_minutes,
            "created_at": s.created_at,
        }
        for s in scheduler.list_schedules()
    ]


@app.get("/api/schedules/{schedule_id}")
async def get_schedule(schedule_id: str):
    """Get details of a specific schedule."""
    state = scheduler.get_schedule(schedule_id)
    if not state:
        raise HTTPException(status_code=404, detail="Schedule not found")
    return {
        "schedule_id": state.schedule_id,
        "config": state.config.model_dump(),
        "is_running": state.is_running,
        "total_runs": state.total_runs,
        "current_run_id": state.current_run_id,
        "last_run_at": state.last_run_at,
        "next_combo_index": state.next_combo_index,
        "created_at": state.created_at,
    }


@app.delete("/api/schedules/{schedule_id}")
async def stop_schedule(schedule_id: str):
    """Stop and remove a schedule."""
    state = scheduler.get_schedule(schedule_id)
    if not state:
        raise HTTPException(status_code=404, detail="Schedule not found")
    scheduler.delete_schedule(schedule_id)
    return {"status": "stopped", "total_runs": state.total_runs}


async def _scheduled_run_trigger(
    *,
    project_id: str,
    device_id: str,
    network_id: str,
    locale: str,
    persona: str | None,
    model: str,
    max_tokens: int,
    thinking_budget: int | None,
    only_n_most_recent_images: int,
    task: str | None,
    input_data: dict[str, str] | None = None,
    sensitive_keys: list[str] | None = None,
) -> str:
    """Trigger a test run from the scheduler. Returns the run_id."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set")

    device = get_device_by_id(device_id)
    network = get_network_by_id(network_id)

    from sentinel.db.client import get_supabase

    sb = get_supabase()
    project = sb.table("projects").select("*").eq("id", project_id).single().execute()
    target_url = project.data["target_url"]
    if not target_url.startswith(("http://", "https://")):
        target_url = "https://" + target_url

    run_row = create_run(
        project_id=project_id,
        device_id=device_id,
        network_id=network_id,
        locale=locale,
        persona=persona,
    )
    run_id = run_row["id"]

    insert_log(
        run_id=run_id,
        level="info",
        event_type="scheduled_run_start",
        message=f"Scheduled test for {target_url}",
        payload={
            "locale": locale,
            "persona": persona,
            "device_id": device_id,
            "network_id": network_id,
        },
    )

    # Build a fake TestRequest for _execute_run
    req = TestRequest(
        project_id=project_id,
        device_id=device_id,
        network_id=network_id,
        locale=locale,
        persona=persona,
        model=model,
        max_tokens=max_tokens,
        thinking_budget=thinking_budget,
        only_n_most_recent_images=only_n_most_recent_images,
        task=task,
        input_data=input_data,
        sensitive_keys=sensitive_keys,
    )

    # Run in background (don't await — scheduler controls pacing)
    import asyncio

    asyncio.create_task(
        _execute_run(
            run_id=run_id,
            req=req,
            target_url=target_url,
            device=device,
            network=network,
            project_id=project_id,
            project_data=project.data,
            api_key=api_key,
        )
    )

    return run_id


# ── Persona & Intelligence Endpoints ────────────────────────────────────


@app.get("/api/personas")
async def list_personas():
    """List all available user personas for testing."""
    return [
        {"key": key, "label": p["label"], "behavior_summary": p["behavior"][:120] + "..."}
        for key, p in PERSONA_PROFILES.items()
    ]


@app.get("/api/projects/{project_id}/issues/similar")
async def find_similar(project_id: str, title: str, description: str | None = None):
    """Find issues similar to the given title/description (root cause intelligence)."""
    results = find_similar_issues(
        project_id=project_id,
        title=title,
        description=description,
        threshold=0.25,
        max_results=10,
    )
    return results


@app.get("/api/projects/{project_id}/issues/trends")
async def issue_trends(project_id: str, days: int = 7):
    """Get issue frequency/trend analysis for a project.

    Groups similar issues and shows how often they recur.
    """
    return get_issue_frequency(
        project_id=project_id,
        days=days,
    )


@app.get("/api/runs/{run_id}/ux-confusion")
async def get_ux_confusion_events(run_id: str):
    """Get UX confusion events detected during a run."""
    from sentinel.db.db_logs import get_logs_for_run

    logs = get_logs_for_run(run_id)
    return [
        {
            "timestamp": log["ts"],
            "message": log.get("message"),
            **(log.get("payload") or {}),
        }
        for log in logs
        if log.get("event_type") == "ux_confusion"
    ]


@app.get("/api/runs/{run_id}/locale-issues")
async def get_locale_issues(run_id: str):
    """Get localisation/translation issues detected during a run."""
    from sentinel.db.db_logs import get_logs_for_run

    logs = get_logs_for_run(run_id)
    return [
        {
            "timestamp": log["ts"],
            "message": log.get("message"),
            **(log.get("payload") or {}),
        }
        for log in logs
        if log.get("event_type") == "locale_issue"
    ]


@app.get("/api/runs/{run_id}/root-causes")
async def get_root_cause_matches(run_id: str):
    """Get root cause intelligence matches for issues found in a run."""
    from sentinel.db.db_logs import get_logs_for_run

    logs = get_logs_for_run(run_id)
    return [
        {
            "timestamp": log["ts"],
            "message": log.get("message"),
            **(log.get("payload") or {}),
        }
        for log in logs
        if log.get("event_type") == "root_cause_match"
    ]


@app.get("/api/runs/{run_id}/performance")
async def get_run_performance(run_id: str):
    """Get Core Web Vitals and resource timing metrics collected during a run."""
    metrics = get_perf_metrics_for_run(run_id)
    if not metrics:
        return {"run_id": run_id, "metrics": [], "detail": "No performance metrics collected"}
    return {"run_id": run_id, "metrics": metrics}


@app.get("/api/projects/{project_id}/performance/trends")
async def get_perf_trends_endpoint(project_id: str, days: int = 7):
    """Get performance metric trends for a project over time."""
    from sentinel.db.db_perf import get_perf_trends
    return get_perf_trends(project_id=project_id, days=days)


@app.get("/api/runs/{run_id}/accessibility")
async def get_run_accessibility(run_id: str):
    """Get accessibility (axe-core WCAG 2.1 AA) violations detected during a run."""
    from sentinel.db.db_logs import get_logs_for_run

    logs = get_logs_for_run(run_id)
    violations = [
        {
            "timestamp": log["ts"],
            "message": log.get("message"),
            **(log.get("payload") or {}),
        }
        for log in logs
        if log.get("event_type") == "a11y_violation"
    ]
    return {"run_id": run_id, "violation_count": len(violations), "violations": violations}


@app.get("/api/runs/{run_id}/regressions")
async def get_run_regressions(run_id: str):
    """Get cross-run regression detection results for a run."""
    from sentinel.db.db_logs import get_logs_for_run

    logs = get_logs_for_run(run_id)
    regressions = [
        {
            "timestamp": log["ts"],
            "message": log.get("message"),
            **(log.get("payload") or {}),
        }
        for log in logs
        if log.get("event_type") in ("regression_detected", "regression_summary")
    ]
    return {"run_id": run_id, "regressions": regressions}


@app.get("/api/runs/{run_id}/flaky")
async def get_run_flaky(run_id: str):
    """Get flaky test detection results for a run."""
    from sentinel.db.db_logs import get_logs_for_run

    logs = get_logs_for_run(run_id)
    flaky_events = [
        {
            "timestamp": log["ts"],
            "message": log.get("message"),
            **(log.get("payload") or {}),
        }
        for log in logs
        if log.get("event_type") in ("flaky_detection_start", "flaky_confirmed",
                                      "flaky_detected", "flaky_detection_complete")
    ]
    return {"run_id": run_id, "flaky_detection": flaky_events}


# ── Slack Integration Endpoints ──────────────────────────────────────


@app.get("/api/slack/status")
async def slack_status():
    """Check if Slack integration is configured and working."""
    configured = is_slack_configured()
    return {
        "configured": configured,
        "detail": (
            "SLACK_BOT_TOKEN is set. Slack notifications are active."
            if configured
            else "SLACK_BOT_TOKEN not set. Set it to enable Slack escalation."
        ),
    }


class SlackOwnerMapping(BaseModel):
    """Map issue categories to Slack user IDs for @mention routing."""
    frontend: str | None = None
    backend: str | None = None
    ux: str | None = None
    performance: str | None = None
    integration: str | None = None


@app.post("/api/slack/owners")
async def set_slack_owners(mapping: SlackOwnerMapping):
    """Set category → Slack user ID mapping for issue routing.

    Pass Slack user IDs (e.g., U12345678) for each category.
    Issues in that category will @mention the corresponding user.
    """
    owner_map = {k: v for k, v in mapping.model_dump().items() if v}

    # Store in env vars for this process
    for category, user_id in owner_map.items():
        os.environ[f"SLACK_OWNER_{category.upper()}"] = user_id

    return {
        "status": "ok",
        "owners_set": owner_map,
        "detail": "Owner mappings updated. Issues will @mention these users.",
    }


@app.get("/api/slack/owners")
async def get_slack_owners():
    """Get current category → Slack user ID mapping."""
    categories = ["frontend", "backend", "ux", "performance", "integration"]
    owners = {}
    for cat in categories:
        env_key = f"SLACK_OWNER_{cat.upper()}"
        owners[cat] = os.environ.get(env_key)
    return owners
