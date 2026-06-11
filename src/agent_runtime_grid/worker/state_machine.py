from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from agent_runtime_grid.domain.jobs import JobRecord
from agent_runtime_grid.storage.finalization import FinalizationResult, finalize_job
from agent_runtime_grid.storage.models import job_events_table, jobs_table


async def load_job_for_update(session: AsyncSession, job_id: UUID) -> JobRecord | None:
    result = await session.execute(select(jobs_table).where(jobs_table.c.id == job_id))
    row = result.mappings().one_or_none()
    if row is None:
        return None
    return JobRecord(
        id=row["id"],
        run_id=row["run_id"],
        job_type=row["job_type"],
        payload=row["payload"],
        payload_hash=row["payload_hash"],
        idempotency_key=row["idempotency_key"],
        status=row["status"],
        timeout_seconds=row["timeout_seconds"],
        max_retries=row["max_retries"],
        trace_id=row["trace_id"],
        budget_cents=row["budget_cents"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


async def record_running(
    session: AsyncSession,
    job: JobRecord,
    *,
    worker_id: str,
    attempt_number: int,
) -> None:
    await _record_state_event(
        session,
        job,
        status="running",
        event_type="running",
        event_data={"worker_id": worker_id, "attempt_number": attempt_number},
    )


async def record_completed(
    session: AsyncSession,
    job: JobRecord,
    *,
    worker_id: str,
    attempt_number: int,
    result: dict[str, Any],
) -> FinalizationResult:
    return await finalize_job(
        session,
        job,
        status="completed",
        event_type="completed",
        event_data={
            "worker_id": worker_id,
            "attempt_number": attempt_number,
            "result": result,
        },
    )


async def record_retry_scheduled(
    session: AsyncSession,
    job: JobRecord,
    *,
    worker_id: str,
    attempt_number: int,
    next_attempt_number: int,
    error_class: str,
) -> None:
    await _record_state_event(
        session,
        job,
        status="queued",
        event_type="retry_scheduled",
        event_data={
            "worker_id": worker_id,
            "attempt_number": attempt_number,
            "next_attempt_number": next_attempt_number,
            "error_class": error_class,
            "retryable": True,
        },
    )


async def record_failed(
    session: AsyncSession,
    job: JobRecord,
    *,
    worker_id: str,
    attempt_number: int,
    error_class: str,
    retryable: bool,
) -> FinalizationResult:
    return await finalize_job(
        session,
        job,
        status="failed",
        event_type="failed",
        event_data={
            "worker_id": worker_id,
            "attempt_number": attempt_number,
            "error_class": error_class,
            "retryable": retryable,
        },
    )


async def record_timed_out(
    session: AsyncSession,
    job: JobRecord,
    *,
    worker_id: str,
    attempt_number: int,
) -> FinalizationResult:
    return await finalize_job(
        session,
        job,
        status="timed_out",
        event_type="timed_out",
        event_data={
            "worker_id": worker_id,
            "attempt_number": attempt_number,
            "error_class": "JobTimedOutError",
        },
    )


async def record_cancelled(
    session: AsyncSession,
    job: JobRecord,
    *,
    worker_id: str,
    attempt_number: int,
    cancelled_while: str,
) -> FinalizationResult:
    return await finalize_job(
        session,
        job,
        status="cancelled",
        event_type="cancelled",
        event_data={
            "worker_id": worker_id,
            "attempt_number": attempt_number,
            "cancelled_while": cancelled_while,
        },
    )


async def _record_state_event(
    session: AsyncSession,
    job: JobRecord,
    *,
    status: str,
    event_type: str,
    event_data: dict[str, Any],
) -> None:
    await session.execute(update(jobs_table).where(jobs_table.c.id == job.id).values(status=status))
    await session.execute(
        insert(job_events_table).values(
            job_id=job.id,
            run_id=job.run_id,
            event_type=event_type,
            event_data=event_data,
            trace_id=job.trace_id,
        )
    )
