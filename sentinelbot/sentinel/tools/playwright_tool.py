import asyncio
import base64
import logging
import os
from typing import Any, Literal, cast, get_args

from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright

from anthropic.types.beta import BetaToolUnionParam

from .base import BaseAnthropicTool, ToolError, ToolResult

logger = logging.getLogger(__name__)

# ── Action types (must match computer_20250124 schema exactly) ──────────

Action = Literal[
    "key",
    "type",
    "mouse_move",
    "left_click",
    "left_click_drag",
    "right_click",
    "middle_click",
    "double_click",
    "triple_click",
    "screenshot",
    "cursor_position",
    "left_mouse_down",
    "left_mouse_up",
    "scroll",
    "hold_key",
    "wait",
]

ScrollDirection = Literal["up", "down", "left", "right"]

# ── Device profiles ─────────────────────────────────────────────────────

DEVICE_PROFILES: dict[str, dict[str, Any]] = {
    "iphone_se": {
        "viewport": {"width": 375, "height": 667},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"
        ),
        "device_scale_factor": 2,
        "is_mobile": True,
        "has_touch": True,
    },
    "iphone_14": {
        "viewport": {"width": 390, "height": 844},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1"
        ),
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    },
    "iphone_15_pro": {
        "viewport": {"width": 393, "height": 852},
        "user_agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
        ),
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    },
    "pixel_7": {
        "viewport": {"width": 412, "height": 915},
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
        ),
        "device_scale_factor": 2.625,
        "is_mobile": True,
        "has_touch": True,
    },
    "galaxy_s8": {
        "viewport": {"width": 360, "height": 740},
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 9; SM-G950F) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
        ),
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    },
    "galaxy_s23": {
        "viewport": {"width": 360, "height": 780},
        "user_agent": (
            "Mozilla/5.0 (Linux; Android 13; SM-S911B) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Mobile Safari/537.36"
        ),
        "device_scale_factor": 3,
        "is_mobile": True,
        "has_touch": True,
    },
    "desktop": {
        "viewport": {"width": 1280, "height": 800},
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        ),
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
    },
    "desktop_1440": {
        "viewport": {"width": 1440, "height": 900},
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        ),
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
    },
    "desktop_1920": {
        "viewport": {"width": 1920, "height": 1080},
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36"
        ),
        "device_scale_factor": 1,
        "is_mobile": False,
        "has_touch": False,
    },
}

# ── Network throttling profiles ─────────────────────────────────────────

NETWORK_PROFILES: dict[str, dict[str, Any]] = {
    "wifi": {},          # No throttling
    "4g": {
        "offline": False,
        "download_throughput": 9000 * 1024 // 8,        # 9 Mbps
        "upload_throughput": 9000 * 1024 // 8,           # 9 Mbps
        "latency": 80,   # ms
    },
    "fast_3g": {
        "offline": False,
        "download_throughput": 1600 * 1024 // 8,        # 1.6 Mbps
        "upload_throughput": 750 * 1024 // 8,            # 750 Kbps
        "latency": 150,  # ms
    },
    "slow_3g": {
        "offline": False,
        "download_throughput": 400 * 1024 // 8,         # 400 Kbps
        "upload_throughput": 400 * 1024 // 8,
        "latency": 400,  # ms
    },
    "high_latency": {
        "offline": False,
        "download_throughput": 2000 * 1024 // 8,        # 2 Mbps
        "upload_throughput": 2000 * 1024 // 8,
        "latency": 800,  # ms
    },
    "offline": {
        "offline": True,
        "download_throughput": 0,
        "upload_throughput": 0,
        "latency": 0,
    },
}

# ── Key name mapping (xdotool key names → Playwright key names) ─────────

XDOTOOL_TO_PLAYWRIGHT_KEYS: dict[str, str] = {
    "Return": "Enter",
    "BackSpace": "Backspace",
    "Tab": "Tab",
    "Escape": "Escape",
    "space": " ",
    "Delete": "Delete",
    "Home": "Home",
    "End": "End",
    "Page_Up": "PageUp",
    "Page_Down": "PageDown",
    "Up": "ArrowUp",
    "Down": "ArrowDown",
    "Left": "ArrowLeft",
    "Right": "ArrowRight",
    "super": "Meta",
    "Super_L": "Meta",
    "Super_R": "Meta",
    "Control_L": "Control",
    "Control_R": "Control",
    "Alt_L": "Alt",
    "Alt_R": "Alt",
    "Shift_L": "Shift",
    "Shift_R": "Shift",
    "ctrl": "Control",
    "alt": "Alt",
    "shift": "Shift",
    "cmd": "Meta",
    "command": "Meta",
    "meta": "Meta",
    "enter": "Enter",
    "return": "Enter",
    "backspace": "Backspace",
    "escape": "Escape",
    "esc": "Escape",
    "delete": "Delete",
    "tab": "Tab",
    "arrowup": "ArrowUp",
    "arrowdown": "ArrowDown",
    "arrowleft": "ArrowLeft",
    "arrowright": "ArrowRight",
    "pageup": "PageUp",
    "pagedown": "PageDown",
    "home": "Home",
    "end": "End",
}


def _translate_key(key_name: str) -> str:
    """Translate xdotool-style key names to Playwright key names.

    Handles compound key expressions like 'ctrl+a' → 'Control+a'
    and single keys like 'Return' → 'Enter'.
    """
    if "+" in key_name:
        parts = key_name.split("+")
        return "+".join(XDOTOOL_TO_PLAYWRIGHT_KEYS.get(p.strip(), p.strip()) for p in parts)
    return XDOTOOL_TO_PLAYWRIGHT_KEYS.get(key_name, key_name)


class PlaywrightComputerTool(BaseAnthropicTool):
    """
    A Playwright-based ComputerTool that emulates a mobile browser.

    Implements the same interface as ComputerTool20250124 (api_type="computer_20250124")
    so Claude sends the same actions, but executes them via Playwright instead of xdotool.

    The browser runs headless=False into the X11 display so it's visible in VNC.
    """

    name: Literal["computer"] = "computer"
    api_type: Literal["computer_20250124"] = "computer_20250124"

    def __init__(
        self,
        *,
        device_profile: str = "iphone_14",
        network_profile: str = "wifi",
        device_profile_dict: dict | None = None,
        network_profile_dict: dict | None = None,
        target_url: str | None = None,
        locale: str = "en-US",
        video_dir: str | None = None,
    ):
        super().__init__()
        self._device_profile_name = device_profile
        # Use explicit dict if provided (e.g. from Supabase), else fall back to hardcoded
        self._device = device_profile_dict or DEVICE_PROFILES.get(device_profile, DEVICE_PROFILES["iphone_14"])
        self._network_profile_name = network_profile
        self._network = network_profile_dict or NETWORK_PROFILES.get(network_profile, NETWORK_PROFILES["wifi"])
        self._target_url = target_url
        self._locale = locale
        self._video_dir = video_dir

        # Playwright objects (initialized lazily)
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

        # Console log capture
        self._console_errors: list[str] = []

        # Performance metrics collected per page navigation
        self._perf_metrics: list[dict[str, Any]] = []

        # Accessibility violations collected via axe-core
        self._a11y_violations: list[dict[str, Any]] = []

        # Screenshot delay (same pattern as original ComputerTool)
        self._screenshot_delay = 1.0

        # Viewport dimensions (what Claude sees as the coordinate space)
        self._width = self._device["viewport"]["width"]
        self._height = self._device["viewport"]["height"]

        # Track cursor position for cursor_position action
        self._cursor_x = 0
        self._cursor_y = 0

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def _ensure_browser(self):
        """Lazily initialize the Playwright browser, context, and page."""
        if self._page is not None:
            return

        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=[
                "--no-sandbox",
                "--disable-gpu",
                "--disable-dev-shm-usage",
            ],
        )

        # Create context with device emulation (and optional video recording)
        context_opts: dict[str, Any] = {
            "viewport": self._device["viewport"],
            "user_agent": self._device["user_agent"],
            "device_scale_factor": self._device["device_scale_factor"],
            "is_mobile": self._device["is_mobile"],
            "has_touch": self._device["has_touch"],
            "locale": self._locale,
        }
        if self._video_dir:
            import os as _os
            _os.makedirs(self._video_dir, exist_ok=True)
            context_opts["record_video_dir"] = self._video_dir

        self._context = await self._browser.new_context(**context_opts)

        self._page = self._context.pages[0] if self._context.pages else await self._context.new_page()

        # Wire up console error capture
        self._page.on("console", lambda msg: (
            self._console_errors.append(f"[{msg.type}] {msg.text}")
            if msg.type in ("error", "warning") else None
        ))
        self._page.on("pageerror", lambda err: (
            self._console_errors.append(f"[PAGE_ERROR] {err}")
        ))

        # Apply network throttling
        if self._network and self._network.get("latency") is not None:
            try:
                cdp = await self._page.context.new_cdp_session(self._page)
                await cdp.send("Network.emulateNetworkConditions", {
                    "offline": self._network.get("offline", False),
                    "downloadThroughput": self._network.get("download_throughput", -1),
                    "uploadThroughput": self._network.get("upload_throughput", -1),
                    "latency": self._network.get("latency", 0),
                })
            except Exception as e:
                logger.warning(f"Failed to set network throttling: {e}")

        # Navigate to target URL if provided
        if self._target_url:
            url = self._target_url
            if not url.startswith(("http://", "https://")):
                url = "https://" + url
            try:
                await self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except Exception as e:
                logger.warning(f"Failed to navigate to {self._target_url}: {e}")

    async def close(self):
        """Clean up Playwright resources. Closes context first to finalize video recording."""
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._page = None
        self._context = None
        self._browser = None
        self._playwright = None

    # ── Tool interface ──────────────────────────────────────────────────

    def to_params(self) -> BetaToolUnionParam:
        """Return tool parameters for the Claude API.

        Uses the Playwright viewport dimensions as the coordinate space.
        Claude will send coordinates in this space and we use them directly.
        """
        return cast(
            BetaToolUnionParam,
            {
                "name": self.name,
                "type": self.api_type,
                "display_width_px": self._width,
                "display_height_px": self._height,
            },
        )

    async def __call__(
        self,
        *,
        action: Action,
        text: str | None = None,
        coordinate: tuple[int, int] | None = None,
        start_coordinate: tuple[int, int] | None = None,
        scroll_direction: ScrollDirection | None = None,
        scroll_amount: int | None = None,
        duration: int | float | None = None,
        key: str | None = None,
        **kwargs,
    ) -> ToolResult:
        """Execute an action via Playwright.

        This method handles all the same actions as ComputerTool20250124:
        left_click, right_click, double_click, triple_click, middle_click,
        mouse_move, left_click_drag, left_mouse_down, left_mouse_up,
        key, type, scroll, screenshot, cursor_position, hold_key, wait.
        """
        await self._ensure_browser()
        assert self._page is not None

        try:
            return await self._dispatch_action(
                action=action,
                text=text,
                coordinate=coordinate,
                start_coordinate=start_coordinate,
                scroll_direction=scroll_direction,
                scroll_amount=scroll_amount,
                duration=duration,
                key=key,
            )
        except ToolError:
            raise
        except Exception as e:
            logger.error(f"PlaywrightComputerTool error: {action=} {e}", exc_info=True)
            raise ToolError(f"Action '{action}' failed: {str(e)}")

    async def _dispatch_action(
        self,
        *,
        action: Action,
        text: str | None,
        coordinate: tuple[int, int] | None,
        start_coordinate: tuple[int, int] | None,
        scroll_direction: ScrollDirection | None,
        scroll_amount: int | None,
        duration: int | float | None,
        key: str | None,
    ) -> ToolResult:
        assert self._page is not None

        # ── Screenshot ──────────────────────────────────────────────
        if action == "screenshot":
            return await self._take_screenshot()

        # ── Cursor position ─────────────────────────────────────────
        if action == "cursor_position":
            return ToolResult(output=f"X={self._cursor_x},Y={self._cursor_y}")

        # ── Click actions ───────────────────────────────────────────
        if action in ("left_click", "right_click", "middle_click", "double_click", "triple_click"):
            if text is not None:
                raise ToolError(f"text is not accepted for {action}")

            x, y = self._validate_coordinate(coordinate, required=False)

            # Move to coordinate if given
            if coordinate is not None:
                await self._page.mouse.move(x, y)
                self._cursor_x, self._cursor_y = x, y

            button = "right" if action == "right_click" else "middle" if action == "middle_click" else "left"
            click_count = 1
            if action == "double_click":
                click_count = 2
            elif action == "triple_click":
                click_count = 3

            # Hold modifier key if specified
            if key:
                pw_key = _translate_key(key)
                await self._page.keyboard.down(pw_key)

            await self._page.mouse.click(self._cursor_x, self._cursor_y, button=button, click_count=click_count)

            if key:
                pw_key = _translate_key(key)
                await self._page.keyboard.up(pw_key)

            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        # ── Mouse move ──────────────────────────────────────────────
        if action == "mouse_move":
            if coordinate is None:
                raise ToolError("coordinate is required for mouse_move")
            x, y = self._validate_coordinate(coordinate)
            await self._page.mouse.move(x, y)
            self._cursor_x, self._cursor_y = x, y
            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        # ── Left click drag ─────────────────────────────────────────
        if action == "left_click_drag":
            if coordinate is None:
                raise ToolError("coordinate is required for left_click_drag")
            if start_coordinate is None:
                raise ToolError("start_coordinate is required for left_click_drag")
            if text is not None:
                raise ToolError("text is not accepted for left_click_drag")

            sx, sy = self._validate_coordinate(start_coordinate)
            ex, ey = self._validate_coordinate(coordinate)

            await self._page.mouse.move(sx, sy)
            await self._page.mouse.down()
            await self._page.mouse.move(ex, ey, steps=10)
            await self._page.mouse.up()
            self._cursor_x, self._cursor_y = ex, ey

            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        # ── Mouse down / up ─────────────────────────────────────────
        if action == "left_mouse_down":
            if coordinate is not None:
                raise ToolError("coordinate is not accepted for left_mouse_down")
            await self._page.mouse.down()
            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        if action == "left_mouse_up":
            if coordinate is not None:
                raise ToolError("coordinate is not accepted for left_mouse_up")
            await self._page.mouse.up()
            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        # ── Key press ───────────────────────────────────────────────
        if action == "key":
            if text is None:
                raise ToolError("text is required for key")
            if coordinate is not None:
                raise ToolError("coordinate is not accepted for key")

            # Handle space-separated repeated keys (e.g. "Backspace Backspace Backspace")
            # and single keys or combo keys (e.g. "Control+a")
            keys = text.split(" ") if "+" not in text and " " in text else [text]
            for k in keys:
                pw_key = _translate_key(k.strip())
                if pw_key:
                    await self._page.keyboard.press(pw_key)

            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        # ── Type text ───────────────────────────────────────────────
        if action == "type":
            if text is None:
                raise ToolError("text is required for type")
            if coordinate is not None:
                raise ToolError("coordinate is not accepted for type")

            await self._page.keyboard.type(text, delay=12)

            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        # ── Scroll ──────────────────────────────────────────────────
        if action == "scroll":
            if scroll_direction is None or scroll_direction not in get_args(ScrollDirection):
                raise ToolError(f"scroll_direction must be 'up', 'down', 'left', or 'right'")
            if not isinstance(scroll_amount, int) or scroll_amount < 0:
                raise ToolError(f"scroll_amount must be a non-negative int")

            # Move to coordinate first if given
            if coordinate is not None:
                x, y = self._validate_coordinate(coordinate)
                await self._page.mouse.move(x, y)
                self._cursor_x, self._cursor_y = x, y

            # Hold modifier key if specified
            if text:
                pw_key = _translate_key(text)
                await self._page.keyboard.down(pw_key)

            # Playwright scroll: mouse.wheel(delta_x, delta_y)
            # Each "click" of scroll = ~100 pixels
            pixels_per_click = 100
            delta = scroll_amount * pixels_per_click

            if scroll_direction == "up":
                await self._page.mouse.wheel(0, -delta)
            elif scroll_direction == "down":
                await self._page.mouse.wheel(0, delta)
            elif scroll_direction == "left":
                await self._page.mouse.wheel(-delta, 0)
            elif scroll_direction == "right":
                await self._page.mouse.wheel(delta, 0)

            if text:
                pw_key = _translate_key(text)
                await self._page.keyboard.up(pw_key)

            await asyncio.sleep(self._screenshot_delay)
            return await self._take_screenshot()

        # ── Hold key ────────────────────────────────────────────────
        if action == "hold_key":
            if text is None:
                raise ToolError("text is required for hold_key")
            if duration is None or not isinstance(duration, (int, float)):
                raise ToolError("duration must be a number")
            if duration < 0:
                raise ToolError("duration must be non-negative")
            if duration > 100:
                raise ToolError("duration is too long")

            pw_key = _translate_key(text)
            await self._page.keyboard.down(pw_key)
            await asyncio.sleep(duration)
            await self._page.keyboard.up(pw_key)

            return await self._take_screenshot()

        # ── Wait ────────────────────────────────────────────────────
        if action == "wait":
            if duration is None or not isinstance(duration, (int, float)):
                raise ToolError("duration must be a number")
            if duration < 0:
                raise ToolError("duration must be non-negative")
            if duration > 100:
                raise ToolError("duration is too long")

            await asyncio.sleep(duration)
            return await self._take_screenshot()

        raise ToolError(f"Invalid action: {action}")

    # ── Helpers ─────────────────────────────────────────────────────

    async def _take_screenshot(self) -> ToolResult:
        """Capture a screenshot of the current page via Playwright.
        
        Resizes to fit within MAX_SCREENSHOT_DIMENSION to avoid Anthropic's
        image size limit for multi-image requests (2000px per dimension).
        """
        MAX_SCREENSHOT_DIMENSION = 1568  # Safe margin under 2000px API limit

        assert self._page is not None
        try:
            png_bytes = await self._page.screenshot(type="png")

            # Resize if any dimension exceeds the limit
            from PIL import Image
            import io

            img = Image.open(io.BytesIO(png_bytes))
            w, h = img.size
            if w > MAX_SCREENSHOT_DIMENSION or h > MAX_SCREENSHOT_DIMENSION:
                scale = min(MAX_SCREENSHOT_DIMENSION / w, MAX_SCREENSHOT_DIMENSION / h)
                new_w, new_h = int(w * scale), int(h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                png_bytes = buf.getvalue()

            b64 = base64.b64encode(png_bytes).decode("utf-8")
            return ToolResult(base64_image=b64)
        except Exception as e:
            raise ToolError(f"Failed to take screenshot: {e}")

    def _validate_coordinate(
        self, coordinate: tuple[int, int] | None, required: bool = True
    ) -> tuple[int, int]:
        """Validate and return coordinates. No scaling needed since viewport = coordinate space."""
        if coordinate is None:
            if required:
                raise ToolError("coordinate is required")
            return self._cursor_x, self._cursor_y

        if not isinstance(coordinate, (list, tuple)) or len(coordinate) != 2:
            raise ToolError(f"{coordinate} must be a tuple of length 2")
        if not all(isinstance(i, (int, float)) and i >= 0 for i in coordinate):
            raise ToolError(f"{coordinate} must be a tuple of non-negative numbers")

        x, y = int(coordinate[0]), int(coordinate[1])

        # Clamp to viewport (don't error, some slight overflows are normal)
        x = min(x, self._width - 1)
        y = min(y, self._height - 1)

        return x, y

    # ── Extra methods for SentinelBot integration ───────────────────

    @property
    def page(self) -> Page | None:
        """Direct access to the Playwright page for advanced use (console logs, network, etc.)."""
        return self._page

    @property
    def current_url(self) -> str | None:
        """Get the current page URL."""
        return self._page.url if self._page else None

    async def get_console_errors(self) -> list[str]:
        """Return captured console errors and warnings from the page."""
        return list(self._console_errors)

    def clear_console_errors(self):
        """Clear the captured console errors list."""
        self._console_errors.clear()

    async def navigate(self, url: str, timeout: int = 30000):
        """Navigate to a URL directly (useful for SentinelBot setup before loop starts)."""
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        await self._ensure_browser()
        assert self._page is not None
        await self._page.goto(url, wait_until="domcontentloaded", timeout=timeout)

    # ── Performance Metrics Collection ──────────────────────────────

    async def collect_perf_metrics(self, step: int | None = None) -> dict[str, Any] | None:
        """Collect Core Web Vitals and resource timing from the current page.

        Injects JavaScript to gather:
        - LCP (Largest Contentful Paint)
        - CLS (Cumulative Layout Shift)
        - TTFB (Time to First Byte)
        - FCP (First Contentful Paint)
        - DOMContentLoaded timing
        - Resource count and total transfer size

        Returns the metrics dict, or None if collection fails.
        """
        if not self._page:
            return None

        try:
            metrics = await self._page.evaluate("""
            () => {
                const result = {};

                // Navigation timing
                const nav = performance.getEntriesByType('navigation');
                if (nav.length > 0) {
                    const n = nav[0];
                    result.ttfb_ms = n.responseStart - n.requestStart;
                    result.dom_content_loaded_ms = n.domContentLoadedEventEnd - n.startTime;
                }

                // FCP (First Contentful Paint)
                const fcp = performance.getEntriesByName('first-contentful-paint');
                if (fcp.length > 0) {
                    result.fcp_ms = fcp[0].startTime;
                }

                // LCP (Largest Contentful Paint) — uses PerformanceObserver entries
                const lcpEntries = performance.getEntriesByType('largest-contentful-paint');
                if (lcpEntries.length > 0) {
                    result.lcp_ms = lcpEntries[lcpEntries.length - 1].startTime;
                }

                // CLS (Cumulative Layout Shift)
                const clsEntries = performance.getEntriesByType('layout-shift');
                if (clsEntries.length > 0) {
                    let clsScore = 0;
                    clsEntries.forEach(entry => {
                        if (!entry.hadRecentInput) {
                            clsScore += entry.value;
                        }
                    });
                    result.cls = clsScore;
                }

                // Resource stats
                const resources = performance.getEntriesByType('resource');
                result.resource_count = resources.length;
                let totalBytes = 0;
                resources.forEach(r => {
                    totalBytes += r.transferSize || 0;
                });
                result.total_transfer_kb = totalBytes / 1024;

                return result;
            }
            """)

            if metrics:
                metrics["url"] = self._page.url
                if step is not None:
                    metrics["step"] = step
                self._perf_metrics.append(metrics)
                logger.info(
                    f"Perf metrics for {self._page.url}: "
                    f"LCP={metrics.get('lcp_ms', '?')}ms, "
                    f"CLS={metrics.get('cls', '?')}, "
                    f"TTFB={metrics.get('ttfb_ms', '?')}ms, "
                    f"FCP={metrics.get('fcp_ms', '?')}ms"
                )
                return metrics
        except Exception as e:
            logger.warning(f"Failed to collect perf metrics: {e}")
        return None

    def get_perf_metrics(self) -> list[dict[str, Any]]:
        """Return all collected performance metrics."""
        return list(self._perf_metrics)

    # ── Accessibility Auditing (axe-core) ───────────────────────────

    async def run_accessibility_audit(
        self,
        standard: str = "wcag21aa",
    ) -> list[dict[str, Any]]:
        """Run an axe-core accessibility audit on the current page.

        Injects axe-core from CDN, runs axe.run() with the specified WCAG standard,
        and returns the list of violations.

        Args:
            standard: WCAG standard tag — one of 'wcag2a', 'wcag2aa', 'wcag21a',
                      'wcag21aa', 'wcag22aa', 'best-practice'.
                      Default is 'wcag21aa' (WCAG 2.1 AA).

        Returns:
            List of violation dicts, each with: id, impact, description, help,
            helpUrl, nodes (list of affected elements).
        """
        if not self._page:
            return []

        try:
            # Inject axe-core if not already present
            axe_loaded = await self._page.evaluate("typeof window.axe !== 'undefined'")
            if not axe_loaded:
                await self._page.add_script_tag(
                    url="https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"
                )
                # Wait for axe to become available
                await self._page.wait_for_function(
                    "typeof window.axe !== 'undefined'",
                    timeout=10000,
                )

            # Run the audit with the specified standard
            violations = await self._page.evaluate(f"""
            async () => {{
                const results = await axe.run(document, {{
                    runOnly: {{
                        type: 'tag',
                        values: ['{standard}']
                    }}
                }});
                return results.violations.map(v => ({{
                    id: v.id,
                    impact: v.impact,
                    description: v.description,
                    help: v.help,
                    helpUrl: v.helpUrl,
                    tags: v.tags,
                    nodes: v.nodes.slice(0, 5).map(n => ({{
                        html: n.html.substring(0, 200),
                        target: n.target,
                        failureSummary: n.failureSummary
                    }}))
                }}));
            }}
            """)

            if violations:
                self._a11y_violations.extend(violations)
                logger.info(
                    f"Accessibility audit on {self._page.url}: "
                    f"{len(violations)} violations found"
                )
            else:
                logger.info(f"Accessibility audit on {self._page.url}: no violations")

            return violations or []

        except Exception as e:
            logger.warning(f"Accessibility audit failed: {e}")
            return []

    def get_a11y_violations(self) -> list[dict[str, Any]]:
        """Return all collected accessibility violations across all page audits."""
        return list(self._a11y_violations)
