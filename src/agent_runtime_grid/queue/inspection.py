from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.storage.finalization import TERMINAL_STATUSES
from agent_runtime_grid.storage.models import job_events_table, jobs_table


@dataclass(frozen=True)
class QueueBackpressureSnapshot:
    queue_depth: int
    oldest_pending_age_seconds: float
    consumer_lag: int
    leased_jobs: int
    running_jobs: int
    worker_utilization: float
    retry_rate: float
    dlq_count: int
    p95_queue_wait_seconds: float
    p95_execution_seconds: float


async def inspect_queue_backpressure(
    *,
    queue: RedisStreamsQueue,
    session_factory: async_sessionmaker[AsyncSession],
    run_id: UUID | None = None,
    worker_count: int | None = None,
    pending_sample_size: int = 1000,
) -> QueueBackpressureSnapshot:
    await queue.ensure_consumer_group()
    group_info = await _consumer_group_info(queue)
    leased_jobs = _as_int(group_info.get("pending"))
    consumer_lag = _as_int(group_info.get("lag"))
    pending_entries = await queue._redis.xpending_range(
        queue.stream_name,
        queue.consumer_group,
        min="-",
        max="+",
        count=pending_sample_size,
    )
    oldest_pending_age_seconds = 0.0
    if pending_entries:
        oldest_pending_age_seconds = (
            max(_as_int(entry.get("time_since_delivered")) for entry in pending_entries) / 1000
        )

    dlq_count = int(await queue._redis.xlen(queue.dlq_stream_name))
    database_metrics = await _database_backpressure_metrics(
        session_factory=session_factory,
        run_id=run_id,
    )
    running_jobs = database_metrics.running_jobs
    worker_utilization = 0.0
    if worker_count is not None and worker_count > 0:
        worker_utilization = min(1.0, running_jobs / worker_count)

    return QueueBackpressureSnapshot(
        queue_depth=leased_jobs + consumer_lag,
        oldest_pending_age_seconds=oldest_pending_age_seconds,
        consumer_lag=consumer_lag,
        leased_jobs=leased_jobs,
        running_jobs=running_jobs,
        worker_utilization=worker_utilization,
        retry_rate=database_metrics.retry_rate,
        dlq_count=dlq_count,
        p95_queue_wait_seconds=database_metrics.p95_queue_wait_seconds,
        p95_execution_seconds=database_metrics.p95_execution_seconds,
    )


@dataclass(frozen=True)
class _DatabaseBackpressureMetrics:
    running_jobs: int
    retry_rate: float
    p95_queue_wait_seconds: float
    p95_execution_seconds: float


async def _consumer_group_info(queue: RedisStreamsQueue) -> dict[str, object]:
    groups = await queue._redis.xinfo_groups(queue.stream_name)
    for group in groups:
        if group.get("name") == queue.consumer_group:
            return group
    return {"pending": 0, "lag": 0}


async def _database_backpressure_metrics(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    run_id: UUID | None,
) -> _DatabaseBackpressureMetrics:
    job_filters = []
    event_filters = []
    if run_id is not None:
        job_filters.append(jobs_table.c.run_id == run_id)
        event_filters.append(job_events_table.c.run_id == run_id)

    async with session_factory() as session:
        submitted_jobs = int(
            await session.scalar(select(func.count()).select_from(jobs_table).where(*job_filters))
            or 0
        )
        running_jobs = int(
            await session.scalar(
                select(func.count())
                .select_from(jobs_table)
                .where(jobs_table.c.status == "running", *job_filters)
            )
            or 0
        )
        retry_count = int(
            await session.scalar(
                select(func.count())
                .select_from(job_events_table)
                .where(job_events_table.c.event_type == "retry_scheduled", *event_filters)
            )
            or 0
        )
        event_rows = (
            (
                await session.execute(
                    select(
                        job_events_table.c.job_id,
                        job_events_table.c.event_type,
                        job_events_table.c.created_at,
                    )
                    .where(*event_filters)
                    .order_by(job_events_table.c.id.asc())
                )
            )
            .mappings()
            .all()
        )

    queue_waits: list[float] = []
    execution_durations: list[float] = []
    events_by_job: dict[UUID, list[dict[str, object]]] = defaultdict(list)
    for row in event_rows:
        events_by_job[row["job_id"]].append(
            {
                "event_type": row["event_type"],
                "created_at": row["created_at"],
            }
        )

    for events in events_by_job.values():
        submitted_at = _first_event_time(events, "submitted")
        running_at = _first_event_time(events, "running")
        terminal_at = _first_terminal_event_time(events)
        if submitted_at is not None and running_at is not None:
            queue_waits.append(max(0.0, (running_at - submitted_at).total_seconds()))
        if running_at is not None and terminal_at is not None:
            execution_durations.append(max(0.0, (terminal_at - running_at).total_seconds()))

    retry_rate = 0.0
    if submitted_jobs:
        retry_rate = retry_count / submitted_jobs

    return _DatabaseBackpressureMetrics(
        running_jobs=running_jobs,
        retry_rate=retry_rate,
        p95_queue_wait_seconds=_p95(queue_waits),
        p95_execution_seconds=_p95(execution_durations),
    )


def _first_event_time(
    events: list[dict[str, object]],
    event_type: str,
) -> datetime | None:
    for event in events:
        if event["event_type"] == event_type:
            created_at = event["created_at"]
            if isinstance(created_at, datetime):
                return created_at
    return None


def _first_terminal_event_time(events: list[dict[str, object]]) -> datetime | None:
    for event in events:
        if event["event_type"] in TERMINAL_STATUSES:
            created_at = event["created_at"]
            if isinstance(created_at, datetime):
                return created_at
    return None


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * 0.95)
    return sorted_values[index]


def _as_int(value: object) -> int:
    if value is None:
        return 0
    return int(value)
