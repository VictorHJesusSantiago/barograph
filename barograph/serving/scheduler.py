"""A lightweight scheduled-task runner for recurring forecast jobs."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from dataclasses import dataclass

from loguru import logger

JobFunc = Callable[[], None]


@dataclass
class ScheduledJob:
    """A repeatable task with a fixed interval in seconds."""

    name: str
    func: JobFunc
    interval_seconds: float
    next_run: float = 0.0
    last_error: str | None = None
    runs: int = 0
    failures: int = 0

    def due(self, now: float) -> bool:
        return now >= self.next_run

    def execute(self) -> None:
        try:
            self.func()
            self.runs += 1
            self.last_error = None
        except Exception as exc:  # noqa: BLE001 - job errors are logged
            logger.error("Scheduled job {} failed: {}", self.name, exc)
            self.failures += 1
            self.last_error = str(exc)


class Scheduler:
    """Run recurring jobs in a background thread.

    Jobs are executed serially in a single worker thread; a failing job does
    not stop the others.
    """

    def __init__(self, tick_seconds: float = 0.25) -> None:
        self.tick_seconds = tick_seconds
        self.jobs: list[ScheduledJob] = []
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def add(self, name: str, func: JobFunc, interval_seconds: float) -> ScheduledJob:
        """Register a periodic job."""
        job = ScheduledJob(
            name=name,
            func=func,
            interval_seconds=max(interval_seconds, 0.0),
            next_run=time.monotonic() + max(interval_seconds, 0.0),
        )
        self.jobs.append(job)
        return job

    def start(self) -> None:
        """Start the worker thread (idempotent)."""
        if self._thread is not None and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Signal the worker thread to stop and join it."""
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None

    def _loop(self) -> None:
        now = time.monotonic()
        for job in self.jobs:
            if job.next_run <= 0:
                job.next_run = now + job.interval_seconds
        while not self._stop.is_set():
            now = time.monotonic()
            for job in self.jobs:
                if job.due(now):
                    job.execute()
                    job.next_run = now + job.interval_seconds
            self._stop.wait(self.tick_seconds)

    @property
    def stats(self) -> dict[str, int]:
        """Per-job run/failure counts."""
        return {job.name: job.runs for job in self.jobs}
