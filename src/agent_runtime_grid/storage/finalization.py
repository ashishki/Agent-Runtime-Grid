from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy import insert, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.ext.asyncio import AsyncSession

from agent_runtime_grid.domain.jobs import JobRecord
from agent_runtime_grid.storage.models import (
    job_events_table,
    job_finalizations_table,
    jobs_table,
)

TERMINAL_STATUSES = frozenset({"completed", "failed", "timed_out", "cancelled"})
_duplicate_finalization_metric = 0


@dataclass(frozen=True)
class FinalizationResult:
    finalized: bool


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
        return FinalizationResult(finalized=False)

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


def duplicate_finalization_metric_value() -> int:
    return _duplicate_finalization_metric


def reset_duplicate_finalization_metric_for_tests() -> None:
    global _duplicate_finalization_metric
    _duplicate_finalization_metric = 0
