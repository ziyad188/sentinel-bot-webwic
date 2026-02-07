import base64
import json
import os
from datetime import datetime, timezone


def make_run_dir(base_dir: str = "/tmp/sentinel_runs") -> tuple[str, str]:
    """Create a timestamped run directory.

    Returns:
        Tuple of (run_id, run_dir_path)
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%S-%f")[:-3] + "Z"
    run_id = f"run_{ts}"
    run_dir = os.path.join(base_dir, run_id)
    os.makedirs(run_dir, exist_ok=True)
    return run_id, run_dir


def make_run_paths(run_dir: str) -> dict[str, str]:
    """Create subdirectories for screenshots, logs, and videos.

    Matches sentinel-manual-agent's directory structure:
        run_<timestamp>/
            screenshots/
            logs/
            videos/
    """
    paths = {
        "screenshots": os.path.join(run_dir, "screenshots"),
        "logs": os.path.join(run_dir, "logs"),
        "videos": os.path.join(run_dir, "videos"),
    }
    for p in paths.values():
        os.makedirs(p, exist_ok=True)
    return paths


def append_log(log_file: str, entry: dict):
    """Append a JSONL entry to the log file.

    Each entry is a single JSON object on its own line,
    matching sentinel-manual-agent's events.jsonl format.
    """
    with open(log_file, "a") as f:
        f.write(json.dumps(entry, default=str) + "\n")


def save_screenshot(screenshots_dir: str, step: int, base64_image: str) -> str:
    """Save a base64-encoded PNG screenshot to disk.

    Args:
        screenshots_dir: Directory to save the screenshot
        step: Step number (used for filename ordering)
        base64_image: Base64-encoded PNG data

    Returns:
        The filename (not full path) of the saved screenshot
    """
    filename = f"step_{step:03d}.png"
    filepath = os.path.join(screenshots_dir, filename)
    with open(filepath, "wb") as f:
        f.write(base64.b64decode(base64_image))
    return filename


def read_events_log(log_file: str) -> list[dict]:
    """Read all events from a JSONL log file."""
    events = []
    if os.path.exists(log_file):
        with open(log_file, "r") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        events.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    return events
