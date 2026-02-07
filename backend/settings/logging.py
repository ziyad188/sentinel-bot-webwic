import logging
import logging.config
import os
from pathlib import Path


def setup_logging(log_level: str | None = None, log_dir: Path | None = None) -> None:
    """Configure console + file logging."""
    level = (log_level or os.getenv("LOG_LEVEL", "INFO")).upper()
    base_dir = Path(__file__).resolve().parents[1]
    logs_path = log_dir or (base_dir / "logs")
    logs_path.mkdir(parents=True, exist_ok=True)

    logging_config = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "default",
            },
            "file": {
                "class": "logging.FileHandler",
                "formatter": "default",
                "filename": str(logs_path / "app.log"),
                "encoding": "utf-8",
            },
        },
        "root": {
            "handlers": ["console", "file"],
            "level": level,
        },
    }

    logging.config.dictConfig(logging_config)
