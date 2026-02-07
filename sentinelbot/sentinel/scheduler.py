from __future__ import annotations

import asyncio
import itertools
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel

logger = logging.getLogger(__name__)


class ScheduleConfig(BaseModel):
    """Configuration for a continuous monitoring schedule."""

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
    input_data: dict[str, str | int] | None = None
    sensitive_keys: list[str] | None = None
    enabled: bool = True


class ScheduleState(BaseModel):
    """Runtime state for an active schedule."""

    schedule_id: str
    config: ScheduleConfig
    created_at: str
    is_running: bool = False
    current_run_id: str | None = None
    total_runs: int = 0
    last_run_at: str | None = None
    next_combo_index: int = 0


class ContinuousScheduler:
    """Manages rotating test schedules across device/network/locale combos.

    Each schedule rotates through all combinations of (device, network, locale, persona)
    on a timed interval.
    """

    def __init__(self):
        self._schedules: dict[str, ScheduleState] = {}
        self._tasks: dict[str, asyncio.Task] = {}

    @property
    def schedules(self) -> dict[str, ScheduleState]:
        return self._schedules

    def create_schedule(self, config: ScheduleConfig) -> ScheduleState:
        """Register a new schedule (does not start it)."""
        schedule_id = str(uuid.uuid4())
        state = ScheduleState(
            schedule_id=schedule_id,
            config=config,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._schedules[schedule_id] = state
        logger.info(
            f"Schedule {schedule_id} created for project {config.project_id} "
            f"({len(self._get_combos(config))} combos, every {config.interval_minutes}m)"
        )
        return state

    def start_schedule(self, schedule_id: str, run_test_fn) -> None:
        """Start the asyncio loop for a schedule.

        Args:
            schedule_id: ID returned by create_schedule
            run_test_fn: Async callable(project_id, device_id, network_id, locale, persona, model, ...)
                         that triggers a single test run. This is wired to the server's _execute_run.
        """
        if schedule_id not in self._schedules:
            raise ValueError(f"Schedule {schedule_id} not found")
        if schedule_id in self._tasks:
            raise ValueError(f"Schedule {schedule_id} is already running")

        state = self._schedules[schedule_id]
        task = asyncio.create_task(
            self._run_loop(state, run_test_fn),
            name=f"schedule-{schedule_id}",
        )
        self._tasks[schedule_id] = task
        logger.info(f"Schedule {schedule_id} started")

    def stop_schedule(self, schedule_id: str) -> None:
        """Cancel the asyncio task for a schedule."""
        task = self._tasks.pop(schedule_id, None)
        if task:
            task.cancel()
            logger.info(f"Schedule {schedule_id} stopped")
        state = self._schedules.get(schedule_id)
        if state:
            state.is_running = False

    def delete_schedule(self, schedule_id: str) -> None:
        """Stop and remove a schedule."""
        self.stop_schedule(schedule_id)
        self._schedules.pop(schedule_id, None)

    def get_schedule(self, schedule_id: str) -> ScheduleState | None:
        return self._schedules.get(schedule_id)

    def list_schedules(self) -> list[ScheduleState]:
        return list(self._schedules.values())

    # ── Internal ────────────────────────────────────────────────────

    @staticmethod
    def _get_combos(config: ScheduleConfig) -> list[dict[str, Any]]:
        """Generate all (device, network, locale, persona) combinations."""
        combos = []
        for device_id, network_id, locale, persona in itertools.product(
            config.device_ids,
            config.network_ids,
            config.locales,
            config.personas,
        ):
            combos.append({
                "device_id": device_id,
                "network_id": network_id,
                "locale": locale,
                "persona": persona,
            })
        return combos

    async def _run_loop(self, state: ScheduleState, run_test_fn) -> None:
        """Infinite loop: run one combo, sleep, repeat."""
        config = state.config
        combos = self._get_combos(config)

        if not combos:
            logger.warning(f"Schedule {state.schedule_id}: no combos to run")
            return

        state.is_running = True
        logger.info(
            f"Schedule {state.schedule_id}: entering loop with {len(combos)} combos, "
            f"interval={config.interval_minutes}m"
        )

        try:
            while True:
                combo = combos[state.next_combo_index % len(combos)]
                state.next_combo_index = (state.next_combo_index + 1) % len(combos)

                logger.info(
                    f"Schedule {state.schedule_id}: running combo "
                    f"device={combo['device_id'][:8]}… network={combo['network_id'][:8]}… "
                    f"locale={combo['locale']} persona={combo['persona']}"
                )

                try:
                    run_id = await run_test_fn(
                        project_id=config.project_id,
                        device_id=combo["device_id"],
                        network_id=combo["network_id"],
                        locale=combo["locale"],
                        persona=combo["persona"],
                        model=config.model,
                        max_tokens=config.max_tokens,
                        thinking_budget=config.thinking_budget,
                        only_n_most_recent_images=config.only_n_most_recent_images,
                        task=config.task,
                        input_data=config.input_data,
                        sensitive_keys=config.sensitive_keys,
                    )
                    state.current_run_id = run_id
                    state.total_runs += 1
                    state.last_run_at = datetime.now(timezone.utc).isoformat()
                    logger.info(
                        f"Schedule {state.schedule_id}: run {run_id} started "
                        f"(total: {state.total_runs})"
                    )
                except Exception as e:
                    logger.error(
                        f"Schedule {state.schedule_id}: failed to start run: {e}",
                        exc_info=True,
                    )

                # Sleep until next interval
                await asyncio.sleep(config.interval_minutes * 60)

        except asyncio.CancelledError:
            logger.info(f"Schedule {state.schedule_id}: cancelled")
            state.is_running = False
        except Exception as e:
            logger.error(f"Schedule {state.schedule_id}: loop crashed: {e}", exc_info=True)
            state.is_running = False
