from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import typer
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import (
    ArtifactIntegrityError,
    ArtifactIntegritySummary,
    ArtifactMetadata,
    ArtifactStore,
    validate_artifact_integrity,
)
from agent_runtime_grid.cli.benchmark import ReliabilityReport, render_reliability_report
from agent_runtime_grid.domain.jobs import JobSubmission
from agent_runtime_grid.evidence import write_evidence_bundle
from agent_runtime_grid.queue.inspection import inspect_queue_backpressure
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.finalization import (
    duplicate_terminal_event_count,
    finalization_conflict_attempt_count,
)
from agent_runtime_grid.storage.models import job_events_table, jobs_table, metadata
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.storage.safety import UnsafeDatabaseResetError, require_safe_local_reset
from agent_runtime_grid.worker.loop import Worker

TERMINAL_STATUSES = frozenset({"completed", "failed", "timed_out", "cancelled"})
DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


class SmokeValidationError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class SmokeRunResult:
    run_id: UUID
    report_path: Path
    report: ReliabilityReport


async def run_smoke(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    jobs: int,
    workers: int,
    failure_rate: float,
    mode: str,
    artifact_root: Path,
    report_path: Path,
) -> SmokeRunResult:
    if jobs <= 0:
        raise ValueError("jobs must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if mode != "stub":
        raise ValueError("smoke command only supports stub mode")
    if failure_rate != 0:
        raise ValueError("smoke command requires failure_rate=0; use benchmark proof tasks")

    run_id = await _submit_smoke_batch(
        session_factory=session_factory,
        queue=queue,
        count=jobs,
    )
    artifact_store = ArtifactStore(artifact_root)
    worker_pool = [
        Worker(
            worker_id=f"smoke-worker-{index + 1}",
            queue=queue,
            session_factory=session_factory,
            artifact_store=artifact_store,
        )
        for index in range(workers)
    ]

    while True:
        processed = await asyncio.gather(*(worker.process_one() for worker in worker_pool))
        if not any(processed):
            break

    report = await build_smoke_report(
        session_factory=session_factory,
        run_id=run_id,
        artifact_root=artifact_root,
        queue=queue,
        worker_count=workers,
    )
    validate_smoke_report(report, expected_jobs=jobs)

    write_evidence_bundle(
        report_path=report_path,
        rendered_report=render_reliability_report(report),
        report=report,
        command="smoke",
        config={
            "jobs": jobs,
            "workers": workers,
            "failure_rate": failure_rate,
            "mode": mode,
            "artifact_root": artifact_root,
        },
    )
    return SmokeRunResult(run_id=run_id, report_path=report_path, report=report)


async def _submit_smoke_batch(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    count: int,
) -> UUID:
    run_id = uuid4()
    async with session_factory() as session:
        repository = JobRepository(session)
        for index in range(count):
            job = await repository.create_job(
                JobSubmission(
                    job_type="stub",
                    payload={"index": index, "mode": "success"},
                    idempotency_key=f"{run_id}:{index}",
                    timeout_seconds=30,
                    max_retries=1,
                    trace_id=f"trace-{run_id}",
                    run_id=run_id,
                )
            )
            await queue.publish_job(
                QueueJobMessage(
                    job_id=str(job.id),
                    run_id=str(job.run_id),
                    attempt_number=1,
                    trace_id=job.trace_id,
                )
            )
    return run_id


async def run_smoke_from_urls(
    *,
    database_url: str = DEFAULT_DATABASE_URL,
    redis_url: str = DEFAULT_REDIS_URL,
    jobs: int = 100,
    workers: int = 4,
    failure_rate: float = 0,
    mode: str = "stub",
    artifact_root: Path = Path("artifacts"),
    report_path: Path = Path("reports/smoke.md"),
    clean_state: bool = False,
) -> SmokeRunResult:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(redis_url, decode_responses=True)
    lock_connection = None
    suffix = uuid4().hex
    queue = RedisStreamsQueue(
        redis,
        stream_name=f"smoke-jobs:{suffix}",
        consumer_group="smoke-workers",
        dlq_stream_name=f"smoke-jobs:{suffix}:dlq",
    )
    try:
        if clean_state:
            require_safe_local_reset(database_url)
            lock_connection = await engine.connect()
            await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))
            async with engine.begin() as connection:
                await connection.run_sync(metadata.drop_all)
                await connection.run_sync(metadata.create_all)

        return await run_smoke(
            session_factory=session_factory,
            queue=queue,
            jobs=jobs,
            workers=workers,
            failure_rate=failure_rate,
            mode=mode,
            artifact_root=artifact_root,
            report_path=report_path,
        )
    finally:
        if lock_connection is not None:
            await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
            await lock_connection.close()
        await redis.aclose()
        await engine.dispose()


async def build_smoke_report(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
    artifact_root: Path,
    queue: RedisStreamsQueue | None = None,
    worker_count: int | None = None,
) -> ReliabilityReport:
    async with session_factory() as session:
        submitted_jobs = int(
            await session.scalar(
                select(func.count()).select_from(jobs_table).where(jobs_table.c.run_id == run_id)
            )
            or 0
        )
        lifecycle_counts = {
            "queued": 0,
            "running": 0,
            "completed": 0,
            "failed": 0,
            "timed_out": 0,
            "cancelled": 0,
            "dlq": 0,
        }
        status_rows = (
            await session.execute(
                select(jobs_table.c.status, func.count())
                .where(jobs_table.c.run_id == run_id)
                .group_by(jobs_table.c.status)
            )
        ).all()
        for status, count in status_rows:
            key = "queued" if status in {"submitted", "queued"} else status
            if key in lifecycle_counts:
                lifecycle_counts[key] += int(count)

        event_result = await session.execute(
            select(
                job_events_table.c.job_id,
                job_events_table.c.event_type,
                job_events_table.c.event_data,
                job_events_table.c.created_at,
            )
            .where(job_events_table.c.run_id == run_id)
            .order_by(job_events_table.c.id.asc())
        )
        event_rows = event_result.mappings().all()
        duplicate_finalizations = await duplicate_terminal_event_count(session, run_id=run_id)
        conflict_attempts = await finalization_conflict_attempt_count(session, run_id=run_id)

    events_by_job: dict[UUID, list[dict[str, object]]] = defaultdict(list)
    for row in event_rows:
        events_by_job[row["job_id"]].append(
            {
                "event_type": row["event_type"],
                "event_data": row["event_data"],
                "created_at": row["created_at"],
            }
        )

    queue_waits: list[float] = []
    execution_durations: list[float] = []
    completed_artifacts = 0
    completed_jobs = lifecycle_counts["completed"]
    artifact_rows: list[ArtifactMetadata] = []
    failure_classification: dict[str, int] = defaultdict(int)
    retry_count = 0

    for job_id, events in events_by_job.items():
        submitted_at = _first_event_time(events, "submitted")
        running_at = _first_event_time(events, "running")
        terminal_event = _first_terminal_event(events)
        if submitted_at is not None and running_at is not None:
            queue_waits.append(max(0.0, (running_at - submitted_at).total_seconds()))
        if running_at is not None and terminal_event is not None:
            execution_durations.append(
                max(0.0, (terminal_event["created_at"] - running_at).total_seconds())
            )

        for event in events:
            event_type = event["event_type"]
            if event_type == "retry_scheduled":
                retry_count += 1
            if event_type == "failed":
                event_data = event["event_data"]
                if isinstance(event_data, dict) and event_data.get("retryable") is True:
                    failure_classification["transient"] += 1
                elif isinstance(event_data, dict) and event_data.get("retryable") is False:
                    failure_classification["permanent"] += 1
                else:
                    failure_classification["failed"] += 1
            if event_type == "timed_out":
                failure_classification["timeout"] += 1
            if event_type == "cancelled":
                failure_classification["cancelled"] += 1
            if event_type == "completed":
                event_data = event["event_data"]
                if isinstance(event_data, dict):
                    result = event_data.get("result")
                    if isinstance(result, dict):
                        artifact = result.get("artifact")
                        if not isinstance(artifact, dict):
                            raise ArtifactIntegrityError(
                                f"missing artifact metadata for completed job {job_id}"
                            )
                        metadata = ArtifactMetadata.from_dict(artifact)
                        validate_artifact_integrity(metadata)
                        artifact_rows.append(metadata)
                        completed_artifacts += 1

    artifact_completeness = 1.0
    if completed_jobs:
        artifact_completeness = completed_artifacts / completed_jobs

    completion_rate = 0.0
    if submitted_jobs:
        completion_rate = completed_jobs / submitted_jobs
    backpressure = None
    if queue is not None:
        backpressure = await inspect_queue_backpressure(
            queue=queue,
            session_factory=session_factory,
            run_id=run_id,
            worker_count=worker_count,
        )

    return ReliabilityReport(
        submitted_jobs=submitted_jobs,
        lifecycle_counts=lifecycle_counts,
        completion_rate=completion_rate,
        duplicate_finalization_count=duplicate_finalizations,
        finalization_conflict_attempt_count=conflict_attempts,
        retry_count=retry_count,
        queue_lag_seconds=(
            backpressure.p95_queue_wait_seconds if backpressure else _p95(queue_waits)
        ),
        p95_duration_seconds=(
            backpressure.p95_execution_seconds if backpressure else _p95(execution_durations)
        ),
        artifact_completeness=artifact_completeness,
        failure_classification=dict(failure_classification),
        estimated_cost_usd=Decimal("0"),
        run_id=str(run_id),
        source=f"runtime_state:{artifact_root.name}",
        backpressure=backpressure,
        artifact_integrity=ArtifactIntegritySummary(
            checked_count=len(artifact_rows),
            valid_count=completed_artifacts,
            rows=tuple(artifact_rows),
        ),
    )


def validate_smoke_report(report: ReliabilityReport, *, expected_jobs: int) -> None:
    terminal_count = sum(report.lifecycle_counts.get(status, 0) for status in TERMINAL_STATUSES)
    errors: list[str] = []
    if report.submitted_jobs != expected_jobs:
        errors.append(f"submitted_jobs expected {expected_jobs}, got {report.submitted_jobs}")
    if terminal_count != expected_jobs:
        errors.append(f"terminal jobs expected {expected_jobs}, got {terminal_count}")
    if report.lifecycle_counts.get("completed", 0) != expected_jobs:
        errors.append(
            "completed jobs expected "
            f"{expected_jobs}, got {report.lifecycle_counts.get('completed', 0)}"
        )
    if report.duplicate_finalization_count != 0:
        errors.append(f"duplicate finalizations: {report.duplicate_finalization_count}")
    if report.artifact_completeness < 1:
        errors.append(f"artifact completeness below 100%: {report.artifact_completeness:.2%}")
    if report.artifact_integrity is not None:
        if report.artifact_integrity.checked_count != report.lifecycle_counts.get("completed", 0):
            errors.append(
                "artifact integrity checked "
                f"{report.artifact_integrity.checked_count} of "
                f"{report.lifecycle_counts.get('completed', 0)} completed jobs"
            )
        if report.artifact_integrity.valid_count != report.artifact_integrity.checked_count:
            errors.append("artifact integrity validation did not cover all checked artifacts")
    if report.estimated_cost_usd != Decimal("0"):
        errors.append(f"stub mode cost expected $0, got ${report.estimated_cost_usd}")
    if errors:
        raise SmokeValidationError(errors)


def smoke_command(
    jobs: Annotated[int, typer.Option("--jobs", min=1)] = 100,
    workers: Annotated[int, typer.Option("--workers", min=1)] = 4,
    failure_rate: Annotated[float, typer.Option("--failure-rate", min=0, max=1)] = 0,
    mode: Annotated[str, typer.Option("--mode")] = "stub",
    report_path: Annotated[Path, typer.Option("--report")] = Path("reports/smoke.md"),
    artifact_root: Annotated[Path, typer.Option("--artifact-root")] = Path("artifacts"),
    database_url: Annotated[str, typer.Option("--database-url")] = DEFAULT_DATABASE_URL,
    redis_url: Annotated[str, typer.Option("--redis-url")] = DEFAULT_REDIS_URL,
    reset_local_database: Annotated[
        bool,
        typer.Option("--reset-local-database", help="Drop and recreate only the local dev DB."),
    ] = False,
) -> None:
    try:
        result = asyncio.run(
            run_smoke_from_urls(
                database_url=database_url,
                redis_url=redis_url,
                jobs=jobs,
                workers=workers,
                failure_rate=failure_rate,
                mode=mode,
                artifact_root=artifact_root,
                report_path=report_path,
                clean_state=reset_local_database,
            )
        )
    except (
        ArtifactIntegrityError,
        SmokeValidationError,
        UnsafeDatabaseResetError,
        ValueError,
    ) as exc:
        typer.echo(f"smoke failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"report: {result.report_path}")


def _first_event_time(
    events: list[dict[str, object]],
    event_type: str,
) -> datetime | None:
    for event in events:
        if event["event_type"] == event_type:
            return event["created_at"]
    return None


def _first_terminal_event(events: list[dict[str, object]]) -> dict[str, object] | None:
    for event in events:
        if event["event_type"] in TERMINAL_STATUSES:
            return event
    return None


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    sorted_values = sorted(values)
    index = int((len(sorted_values) - 1) * 0.95)
    return sorted_values[index]
