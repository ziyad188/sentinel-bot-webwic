import os
import json
import mimetypes
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, Any, Tuple

import httpx


@dataclass
class WebhookConfig:
    p0: str
    p1: str
    p2: str


@dataclass
class BotConfig:
    token: str
    channel_id: str  


def env_required(name: str) -> str:
    v = os.getenv(name, "").strip()
    if not v:
        raise SystemExit(f"Missing env var: {name}")
    return v


async def post_webhook(url: str, text: str) -> None:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(url, json={"text": text})
        r.raise_for_status()


def format_incident(
    *,
    priority: str,
    title: str,
    service: str,
    env: str,
    message: str,
    request_id: Optional[str] = None,
    mention: Optional[str] = None,  # "<!channel>" / "<!here>" / "<@U...>"
) -> str:
    pr = (priority or "").upper()
    if pr not in ("P0", "P1", "P2"):
        pr = "P2"

    lines = []
    if mention:
        lines.append(mention)
    lines.append(f"*{pr}* | *{title}*")
    lines.append(f"*Service:* {service} | *Env:* {env}")
    if request_id:
        lines.append(f"*Request ID:* {request_id}")
    lines.append(f"*Details:* {message}")
    return "\n".join(lines)


async def slack_api_call(
    *,
    token: str,
    method: str,
    data: Dict[str, Any],
) -> Dict[str, Any]:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.post(f"https://slack.com/api/{method}", headers=headers, data=data)
        r.raise_for_status()
        payload = r.json()
    if not payload.get("ok"):
        raise RuntimeError(f"Slack API error on {method}: {payload.get('error')} ({payload})")
    return payload


async def upload_file_via_external_flow(
    *,
    bot: BotConfig,
    file_path: str,
    title: Optional[str] = None,
    initial_comment: Optional[str] = None,
) -> None:
    file_path = file_path.strip()
    if not file_path:
        return

    if not os.path.exists(file_path):
        raise FileNotFoundError(file_path)

    filename = os.path.basename(file_path)
    length = os.path.getsize(file_path)
    mime, _ = mimetypes.guess_type(file_path)
    if not mime:
        mime = "application/octet-stream"

    # 1) Get upload URL + file_id
    # files.getUploadURLExternal returns an upload_url and file_id to use next. :contentReference[oaicite:2]{index=2}
    meta = await slack_api_call(
        token=bot.token,
        method="files.getUploadURLExternal",
        data={
            "filename": filename,
            "length": str(length),
            # "alt_txt": "optional alt text",
        },
    )

    upload_url = meta["upload_url"]
    file_id = meta["file_id"]

    # 2) Upload bytes to upload_url (Slack expects raw octet-stream)
    async with httpx.AsyncClient(timeout=60) as client:
        with open(file_path, "rb") as f:
            up = await client.post(
                upload_url,
                content=f.read(),
                headers={"Content-Type": "application/octet-stream"},
            )
        up.raise_for_status()

    # 3) Complete upload (share to channel)
    # If not called, uploaded file is discarded. :contentReference[oaicite:3]{index=3}
    files_arg = json.dumps([{"id": file_id, "title": title or filename}])
    await slack_api_call(
        token=bot.token,
        method="files.completeUploadExternal",
        data={
            "channel_id": bot.channel_id,
            "files": files_arg,
            # optional:
            # "initial_comment": initial_comment or "",
        },
    )


async def main() -> None:
    # Webhook-based P0/P1/P2 message tests
    webhooks = WebhookConfig(
        p0=env_required("SLACK_WEBHOOK_P0"),
        p1=env_required("SLACK_WEBHOOK_P1"),
        p2=env_required("SLACK_WEBHOOK_P2"),
    )

    # Bot-based file upload tests (PNG/MP4)
    # Needs scopes like files:write, chat:write and app installed to workspace. :contentReference[oaicite:4]{index=4}
    bot = BotConfig(
        token=os.getenv("SLACK_BOT_TOKEN", "").strip(),
        channel_id=os.getenv("SLACK_CHANNEL_ID", "").strip(),
    )

    # 1) Send sample incidents
    msgs = [
        ("P2", webhooks.p2, format_incident(
            priority="P2",
            title="Test: minor issue",
            service="finprime-core",
            env="development",
            message="This is a P2 test message to validate Slack routing.",
        )),
        ("P1", webhooks.p1, format_incident(
            priority="P1",
            title="Test: degraded performance",
            service="integration-consumer",
            env="staging",
            message="This is a P1 test message. Expect team to see it.",
            mention="<!here>",
        )),
        ("P0", webhooks.p0, format_incident(
            priority="P0",
            title="Test: outage",
            service="finprime-core",
            env="production",
            message="This is a P0 test message. Treat as paging/noise test.",
            mention="<!channel>",
        )),
    ]

    for pr, url, text in msgs:
        await post_webhook(url, text)
        print(f"Posted {pr} webhook message OK")

    # 2) Upload test files (optional)
    png_path = os.getenv("TEST_PNG_PATH", "").strip()
    mp4_path = os.getenv("TEST_MP4_PATH", "").strip()

    if bot.token and bot.channel_id:
        if png_path:
            await upload_file_via_external_flow(
                bot=bot,
                file_path=png_path,
                title="Test PNG upload",
                initial_comment="Uploading a test PNG",
            )
            print("Uploaded PNG OK")

        if mp4_path:
            await upload_file_via_external_flow(
                bot=bot,
                file_path=mp4_path,
                title="Test MP4 upload",
                initial_comment="Uploading a test MP4/video",
            )
            print("Uploaded MP4 OK")
    else:
        print("Skipping file upload: set SLACK_BOT_TOKEN and SLACK_CHANNEL_ID to test PNG/MP4 uploads.")


if __name__ == "__main__":
    asyncio.run(main())
