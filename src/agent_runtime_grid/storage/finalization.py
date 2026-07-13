from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from agent_runtime_grid.domain.jobs import JobRecord
from agent_runtime_grid.storage.models import (
    finalization_conflict_attempts_table,
    job_events_table,
    job_finalizations_table,
    jobs_table,
)

TERMINAL_STATUSES = frozenset({"completed", "failed", "timed_out", "cancelled"})


@dataclass(frozen=True)
class FinalizationResult:
    finalized: bool
    conflict_recorded: bool = False


async def finalize_job(
    session: AsyncSession,
    job: JobRecord,
    *,
    status: str,
    event_type: str,
    event_data: dict[str, Any],
) -> FinalizationResult:
    if status not in TERMINAL_STATUSES:
        raise ValueError(f"{status!r} is not a terminal status")

    inserted_finalization = await session.execute(
        postgres_insert(job_finalizations_table)
        .values(
            job_id=job.id,
            run_id=job.run_id,
            status=status,
            event_type=event_type,
            trace_id=job.trace_id,
        )
        .on_conflict_do_nothing(index_elements=[job_finalizations_table.c.job_id])
        .returning(job_finalizations_table.c.job_id)
    )
    if inserted_finalization.scalar_one_or_none() is None:
        await session.execute(
            insert(finalization_conflict_attempts_table).values(
                job_id=job.id,
                run_id=job.run_id,
                attempted_status=status,
                attempted_event_type=event_type,
                trace_id=job.trace_id,
            )
        )
        return FinalizationResult(finalized=False, conflict_recorded=True)

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
    return FinalizationResult(finalized=True)


async def finalization_conflict_attempt_count(
    session: AsyncSession,
    *,
    run_id: Any | None = None,
) -> int:
    statement = select(func.count()).select_from(finalization_conflict_attempts_table)
    if run_id is not None:
        statement = statement.where(finalization_conflict_attempts_table.c.run_id == run_id)
    return int(await session.scalar(statement) or 0)


async def duplicate_terminal_event_count(
    session: AsyncSession,
    *,
    run_id: Any | None = None,
) -> int:
    statement = select(job_events_table.c.job_id).where(
        job_events_table.c.event_type.in_(TERMINAL_STATUSES)
    )
    if run_id is not None:
        statement = statement.where(job_events_table.c.run_id == run_id)
    duplicate_jobs = (
        statement.group_by(job_events_table.c.job_id).having(func.count() > 1).subquery()
    )
    return int(await session.scalar(select(func.count()).select_from(duplicate_jobs)) or 0)
