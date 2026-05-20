from __future__ import annotations

import asyncio
from contextlib import suppress

from app.core.config import settings
from app.core.database import SessionLocal
from app.services.monitor_service import MonitorService


class MonitorScheduler:
    def __init__(self) -> None:
        self._task: asyncio.Task | None = None
        self._stop_event: asyncio.Event | None = None

    async def _loop(self) -> None:
        self._stop_event = asyncio.Event()
        while not self._stop_event.is_set():
            db = SessionLocal()
            try:
                await MonitorService(db).run_due_waybills()
            finally:
                db.close()
            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=settings.monitor_scheduler_interval_seconds,
                )
            except TimeoutError:
                continue

    def start(self) -> None:
        if not settings.enable_monitor_scheduler or self._task is not None:
            return
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()
        if self._task is not None:
            self._task.cancel()
            with suppress(asyncio.CancelledError):
                await self._task
        self._task = None


monitor_scheduler = MonitorScheduler()
