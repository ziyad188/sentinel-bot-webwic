from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api"

DEFAULT_CATEGORY_OWNERS: dict[str, str | None] = {
    "frontend": None,
    "backend": None,
    "ux": None,
    "performance": None,
    "integration": None,
}

# Claude's output categories → DB category names (for fallback resolution)
# Claude reports: functional, visual, performance, accessibility, mobile
# DB now supports both sets directly. This alias map is a fallback
# in case a category doesn't have a direct DB entry.
CATEGORY_ALIAS: dict[str, str] = {
    "functional": "backend",
    "visual": "frontend",
    "accessibility": "ux",
    "mobile": "frontend",
}


def _get_token() -> str | None:
    return os.environ.get("SLACK_BOT_TOKEN")


def _headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json; charset=utf-8",
    }


def _get_owner_for_category(category: str | None, project_id: str | None = None) -> str | None:
    """Resolve the Slack user ID for an issue category.

    Maps Claude's output categories (functional, visual, etc.) to DB categories
    (backend, frontend, etc.) then looks up the owner.
    Checks env vars first, then slack_category_owners, then slack_integrations.
    """
    if not category:
        return None

    # Try exact category first, then alias fallback
    categories_to_try = [category]
    alias = CATEGORY_ALIAS.get(category)
    if alias and alias != category:
        categories_to_try.append(alias)

    for cat in categories_to_try:
        env_key = f"SLACK_OWNER_{cat.upper()}"
        owner = os.environ.get(env_key)
        if owner:
            return owner

    # Try the dedicated slack_category_owners table (project-scoped)
    for cat in categories_to_try:
        try:
            from sentinel.db.client import get_supabase
            sb = get_supabase()
            query = (
                sb.table("slack_category_owners")
                .select("slack_user_id")
                .eq("category", cat)
            )
            if project_id:
                query = query.eq("project_id", project_id)
            result = query.limit(1).execute()
            if result.data and result.data[0].get("slack_user_id"):
                return result.data[0]["slack_user_id"]
        except Exception:
            pass

    # Fallback: slack_integrations JSON blob
    try:
        from sentinel.db.client import get_supabase
        sb = get_supabase()
        query = sb.table("slack_integrations").select("category_owners")
        if project_id:
            query = query.eq("project_id", project_id)
        result = query.limit(1).execute()
        if result.data:
            owners = result.data[0].get("category_owners") or {}
            for cat in categories_to_try:
                if owners.get(cat):
                    return owners[cat]
    except Exception:
        pass

    for cat in categories_to_try:
        if DEFAULT_CATEGORY_OWNERS.get(cat):
            return DEFAULT_CATEGORY_OWNERS[cat]
    return None


# ── Channel Management ──────────────────────────────────────────────────


def _get_slack_user_ids_from_db() -> list[str]:
    """Fetch all active Slack user IDs from the slack_users table."""
    try:
        from sentinel.db.client import get_supabase
        sb = get_supabase()
        result = (
            sb.table("slack_users")
            .select("slack_user_id")
            .eq("is_active", True)
            .execute()
        )
        return [row["slack_user_id"] for row in (result.data or []) if row.get("slack_user_id")]
    except Exception as e:
        logger.warning(f"Slack: could not fetch users from DB: {e}")
        return []


async def _invite_users_to_channel(
    client: httpx.AsyncClient,
    token: str,
    channel_id: str,
    channel_name: str,
) -> None:
    """Invite all active slack_users from the DB to a channel."""
    user_ids = _get_slack_user_ids_from_db()
    if not user_ids:
        logger.info(
            f"Slack: no active users in slack_users table — "
            f"channel #{channel_name} created but no users invited."
        )
        return

    for user_id in user_ids:
        resp = await client.post(
            f"{SLACK_API}/conversations.invite",
            headers=_headers(token),
            json={"channel": channel_id, "users": user_id},
        )
        data = resp.json()
        if data.get("ok"):
            logger.info(f"Slack: invited {user_id} to #{channel_name}")
        elif data.get("error") == "already_in_channel":
            logger.debug(f"Slack: {user_id} already in #{channel_name}")
        else:
            logger.warning(f"Slack: failed to invite {user_id}: {data.get('error')}")


def _slugify(name: str) -> str:
    """Convert a project name to a Slack-safe channel name."""
    import re
    slug = re.sub(r"[^a-z0-9-]", "-", name.lower())
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:76]  # Slack max channel name length is 80, leave room for prefix


async def find_or_create_channel(
    project_name: str,
    project_id: str,
) -> str | None:
    """Find or create #sentinel-{project} channel. Returns channel ID or None."""
    token = _get_token()
    if not token:
        logger.debug("Slack: no SLACK_BOT_TOKEN set, skipping")
        return None

    channel_name = f"sentinel-{_slugify(project_name)}"

    async with httpx.AsyncClient() as client:
        # Search existing channels (public only — private requires groups:read scope)
        resp = await client.get(
            f"{SLACK_API}/conversations.list",
            headers=_headers(token),
            params={"types": "public_channel", "limit": 1000, "exclude_archived": "true"},
        )
        data = resp.json()
        if data.get("ok"):
            for ch in data.get("channels", []):
                if ch["name"] == channel_name:
                    logger.info(f"Slack: found existing channel #{channel_name} ({ch['id']})")
                    # Ensure all DB users are invited
                    await _invite_users_to_channel(client, token, ch["id"], channel_name)
                    return ch["id"]

        # Create new channel
        resp = await client.post(
            f"{SLACK_API}/conversations.create",
            headers=_headers(token),
            json={"name": channel_name},
        )
        data = resp.json()
        if data.get("ok"):
            channel_id = data["channel"]["id"]
            logger.info(f"Slack: created channel #{channel_name} ({channel_id})")

            # Set channel topic
            await client.post(
                f"{SLACK_API}/conversations.setTopic",
                headers=_headers(token),
                json={
                    "channel": channel_id,
                    "topic": f"SentinelBot QA alerts for project {project_id[:8]}…",
                },
            )

            # Invite users so they can see the channel
            await _invite_users_to_channel(client, token, channel_id, channel_name)

            return channel_id
        elif data.get("error") == "name_taken":
            # Channel exists but bot isn't a member — search all channels
            logger.info(f"Slack: channel #{channel_name} exists but bot not a member, searching...")
            resp = await client.get(
                f"{SLACK_API}/conversations.list",
                headers=_headers(token),
                params={
                    "types": "public_channel,private_channel",
                    "limit": 1000,
                    "exclude_archived": "true",
                },
            )
            all_data = resp.json()
            channel_id = None
            if all_data.get("ok"):
                for ch in all_data.get("channels", []):
                    if ch["name"] == channel_name:
                        channel_id = ch["id"]
                        break

            if channel_id:
                # Join the channel
                await client.post(
                    f"{SLACK_API}/conversations.join",
                    headers=_headers(token),
                    json={"channel": channel_id},
                )
                logger.info(f"Slack: joined existing channel #{channel_name} ({channel_id})")
                # Invite DB users
                await _invite_users_to_channel(client, token, channel_id, channel_name)
                return channel_id
            else:
                logger.warning(f"Slack: channel #{channel_name} exists but could not be found via API")
                return None
        else:
            logger.warning(f"Slack: failed to create channel: {data.get('error')}")
            return None


# ── Issue Posting ────────────────────────────────────────────────────────

SEVERITY_EMOJI = {
    "P0": "🔴",
    "P1": "🟠",
    "P2": "🟡",
    "P3": "🟢",
}

SEVERITY_LABEL = {
    "P0": "Showstopper",
    "P1": "Critical",
    "P2": "Major",
    "P3": "Minor",
}


async def post_issue_to_slack(
    *,
    channel_id: str,
    issue_data: dict[str, Any],
    issue_db_row: dict[str, Any],
    run_id: str,
    target_url: str,
    device_label: str,
    network_label: str,
    project_id: str | None = None,
    screenshot_base64: str | None = None,
    recent_screenshots: list[dict[str, Any]] | None = None,
    similar_issues: list[dict[str, Any]] | None = None,
    is_realtime: bool = False,
) -> str | None:
    """Post a rich issue message to Slack, returns the message timestamp (thread_ts).

    Args:
        channel_id: Slack channel ID
        issue_data: Raw issue dict from Claude's output
        issue_db_row: The created issue row from the DB
        run_id: The run that found this issue
        target_url: URL being tested
        device_label: Device name
        network_label: Network condition
        screenshot_base64: Optional primary screenshot to upload
        recent_screenshots: Last 2-3 screenshots [{"b64": ..., "step": ...}]
            uploaded as threaded replies for context
        similar_issues: Related issues from root cause analysis
        is_realtime: Whether this was detected mid-run (vs end-of-run)
    """
    token = _get_token()
    if not token or not channel_id:
        return None

    severity = issue_data.get("severity", "P2")
    emoji = SEVERITY_EMOJI.get(severity, "⚪")
    label = SEVERITY_LABEL.get(severity, "Unknown")
    title = issue_data.get("title", "Untitled issue")
    category = issue_data.get("category", "unknown")
    issue_id = issue_db_row.get("id", "unknown")

    # Build the owner mention
    owner_id = _get_owner_for_category(category, project_id=project_id)
    owner_mention = f" → <@{owner_id}>" if owner_id else ""

    # Build reproduction steps
    steps = issue_data.get("steps_to_reproduce", [])
    steps_text = "\n".join(f"  {i+1}. {s}" for i, s in enumerate(steps)) if steps else "_No steps provided_"

    # Real-time badge
    rt_badge = "  ⚡ *LIVE DETECTION*" if is_realtime else ""

    # Root cause section
    root_cause_text = ""
    if similar_issues:
        matches = []
        for s in similar_issues[:3]:
            matches.append(
                f"• `{s['id'][:8]}…` ({s['severity']}) — _{s['title']}_ "
                f"(similarity: {s.get('similarity_score', '?')})"
            )
        root_cause_text = (
            "\n\n🔗 *Possibly Related Issues:*\n" + "\n".join(matches)
        )

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{emoji} [{severity}] {title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Severity:* {emoji} {label}{rt_badge}"},
                {"type": "mrkdwn", "text": f"*Category:* {category}{owner_mention}"},
                {"type": "mrkdwn", "text": f"*Device:* {device_label}"},
                {"type": "mrkdwn", "text": f"*Network:* {network_label}"},
                {"type": "mrkdwn", "text": f"*URL:* <{target_url}>"},
                {"type": "mrkdwn", "text": f"*Issue ID:* `{issue_id[:8]}…`"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n{issue_data.get('description', '_No description_')}",
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Expected:* {issue_data.get('expected', '_N/A_')}\n"
                    f"*Actual:* {issue_data.get('actual', '_N/A_')}"
                ),
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Steps to Reproduce:*\n{steps_text}",
            },
        },
    ]

    # Severity justification
    justification = issue_data.get("severity_justification")
    if justification:
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"💡 *Severity rationale:* {justification}"},
            ],
        })

    # Root cause matches
    if root_cause_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": root_cause_text},
        })

    # Footer
    blocks.append({
        "type": "context",
        "elements": [
            {"type": "mrkdwn", "text": f"Run `{run_id[:8]}…` | Issue `{issue_id[:8]}…`"},
        ],
    })

    async with httpx.AsyncClient() as client:
        # Post main message
        resp = await client.post(
            f"{SLACK_API}/chat.postMessage",
            headers=_headers(token),
            json={
                "channel": channel_id,
                "blocks": blocks,
                "text": f"{emoji} [{severity}] {title}",  # fallback for notifications
            },
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning(f"Slack: failed to post issue: {data.get('error')}")
            return None

        thread_ts = data["ts"]
        logger.info(f"Slack: posted issue {issue_id[:8]}… to channel {channel_id}")

        # Get permalink URL for this message
        slack_url = None
        try:
            permalink_resp = await client.get(
                f"{SLACK_API}/chat.getPermalink",
                headers=_headers(token),
                params={"channel": channel_id, "message_ts": thread_ts},
            )
            permalink_data = permalink_resp.json()
            if permalink_data.get("ok"):
                slack_url = permalink_data["permalink"]
                logger.info(f"Slack: permalink for issue {issue_id[:8]}…: {slack_url}")
        except Exception as e:
            logger.warning(f"Slack: failed to get permalink: {e}")

        # Save slack_url to the issue in DB
        if slack_url and issue_id != "unknown":
            try:
                from sentinel.db.client import get_supabase
                sb = get_supabase()
                sb.table("issues").update({"slack_url": slack_url}).eq("id", issue_id).execute()
                logger.info(f"Slack: saved slack_url for issue {issue_id[:8]}…")
            except Exception as e:
                logger.warning(f"Slack: failed to save slack_url to DB: {e}")

        # Upload screenshot(s) as threaded replies
        # Collect all screenshots to upload: primary + recent context
        screenshots_to_upload: list[dict[str, Any]] = []

        if recent_screenshots:
            # Use recent screenshots (last 2-3 leading up to the issue)
            # Deduplicate: if screenshot_base64 matches one in recent, skip it
            seen_steps = set()
            for ss in recent_screenshots:
                step_num = ss.get("step", "?")
                if step_num not in seen_steps:
                    seen_steps.add(step_num)
                    screenshots_to_upload.append(ss)
        elif screenshot_base64:
            # Fallback: single screenshot only
            screenshots_to_upload.append({"b64": screenshot_base64, "step": "?"})

        if screenshots_to_upload:
            # Brief delay so the main message is fully posted before images
            await asyncio.sleep(2)
            for i, ss in enumerate(screenshots_to_upload):
                step_label = f"Step {ss['step']}" if ss.get('step') != '?' else 'Evidence'
                await _upload_screenshot_to_thread(
                    client, token, channel_id, thread_ts,
                    ss["b64"],
                    title=f"{step_label} — {title}",
                    severity=severity,
                )
                # Small delay between uploads to preserve order in thread
                if i < len(screenshots_to_upload) - 1:
                    await asyncio.sleep(1)

        return thread_ts


async def _upload_screenshot_to_thread(
    client: httpx.AsyncClient,
    token: str,
    channel_id: str,
    thread_ts: str,
    screenshot_base64: str,
    title: str,
    severity: str,
) -> None:
    """Upload a screenshot as a file to a Slack thread."""
    try:
        image_bytes = base64.b64decode(screenshot_base64)

        # Step 1: Get upload URL
        resp = await client.post(
            f"{SLACK_API}/files.getUploadURLExternal",
            headers={"Authorization": f"Bearer {token}"},
            data={
                "filename": f"evidence_{severity}_{title[:30].replace(' ', '_')}.png",
                "length": len(image_bytes),
            },
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning(f"Slack: failed to get upload URL: {data.get('error')}")
            return

        upload_url = data["upload_url"]
        file_id = data["file_id"]

        # Step 2: Upload file bytes
        await client.post(
            upload_url,
            content=image_bytes,
            headers={"Content-Type": "application/octet-stream"},
        )

        # Step 3: Complete upload + share to channel thread
        resp = await client.post(
            f"{SLACK_API}/files.completeUploadExternal",
            headers=_headers(token),
            json={
                "files": [{"id": file_id, "title": f"📸 Evidence: {title}"}],
                "channel_id": channel_id,
                "thread_ts": thread_ts,
                "initial_comment": f"📸 Screenshot evidence for [{severity}] {title}",
            },
        )
        data = resp.json()
        if data.get("ok"):
            logger.info(f"Slack: uploaded screenshot to thread {thread_ts}")
        else:
            logger.warning(f"Slack: failed to complete upload: {data.get('error')}")

    except Exception as e:
        logger.warning(f"Slack: screenshot upload failed: {e}")


async def post_run_summary_to_slack(
    *,
    channel_id: str,
    run_id: str,
    target_url: str,
    device_label: str,
    network_label: str,
    issue_count: int,
    step_count: int,
    duration_ms: int,
    tests_passed: list[str],
    ux_confusion_count: int = 0,
    locale_issue_count: int = 0,
    captcha_encountered: bool = False,
) -> None:
    """Post a run completion summary to the Slack channel."""
    token = _get_token()
    if not token or not channel_id:
        return

    duration_s = duration_ms / 1000
    status_emoji = "✅" if issue_count == 0 else f"🚨 {issue_count} issue(s)"

    summary_lines = [
        f"*Run Complete:* `{run_id[:8]}…`",
        f"*URL:* <{target_url}>",
        f"*Device:* {device_label} | *Network:* {network_label}",
        f"*Duration:* {duration_s:.1f}s | *Steps:* {step_count}",
        f"*Result:* {status_emoji}",
    ]
    if ux_confusion_count:
        summary_lines.append(f"*UX Confusion Events:* {ux_confusion_count}")
    if locale_issue_count:
        summary_lines.append(f"*Locale Issues:* {locale_issue_count}")
    if captcha_encountered:
        summary_lines.append("⚠️ CAPTCHA/OTP gate encountered")
    if tests_passed:
        passed_str = ", ".join(tests_passed[:5])
        if len(tests_passed) > 5:
            passed_str += f" (+{len(tests_passed) - 5} more)"
        summary_lines.append(f"*Tests Passed:* {passed_str}")

    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(summary_lines),
            },
        },
    ]

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{SLACK_API}/chat.postMessage",
            headers=_headers(token),
            json={
                "channel": channel_id,
                "blocks": blocks,
                "text": f"Run {run_id[:8]}… complete: {status_emoji}",
            },
        )
        data = resp.json()
        if data.get("ok"):
            logger.info(f"Slack: posted run summary for {run_id[:8]}…")
        else:
            logger.warning(f"Slack: failed to post run summary: {data.get('error')}")


def is_slack_configured() -> bool:
    """Check if Slack integration is available."""
    return bool(_get_token())
