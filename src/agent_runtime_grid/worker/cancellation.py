from __future__ import annotations

import asyncio
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from agent_runtime_grid.domain.jobs import JobRecord
from agent_runtime_grid.worker.state_machine import record_cancelled


class JobCancelledError(RuntimeError):
    pass


class CancellationRegistry:
    def __init__(self) -> None:
        self._events: dict[str, asyncio.Event] = {}

    def event_for(self, job_id: str) -> asyncio.Event:
        return self._events.setdefault(job_id, asyncio.Event())

    def request_cancel(self, job_id: str | UUID) -> None:
        self.event_for(str(job_id)).set()

    def is_cancelled(self, job_id: str | UUID) -> bool:
        return self.event_for(str(job_id)).is_set()


async def cancel_queued_job(
    session: AsyncSession,
    job: JobRecord,
    *,
    worker_id: str = "api",
) -> None:
    await record_cancelled(
        session,
        job,
        worker_id=worker_id,
        attempt_number=0,
        cancelled_while="queued",
    )
