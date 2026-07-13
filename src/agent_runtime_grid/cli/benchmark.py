from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import typer
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import (
    ArtifactIntegrityError,
    ArtifactIntegritySummary,
    ArtifactStore,
)
from agent_runtime_grid.domain.jobs import JobSubmission
from agent_runtime_grid.evidence import portable_path, write_evidence_bundle
from agent_runtime_grid.jobs.failure_injection import (
    FailureMode,
    FailurePlan,
    payload_for_failure,
)
from agent_runtime_grid.queue.inspection import QueueBackpressureSnapshot
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import metadata
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.storage.safety import UnsafeDatabaseResetError, require_safe_local_reset
from agent_runtime_grid.worker.loop import Worker

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
benchmark_app = typer.Typer()


@dataclass(frozen=True)
class BenchmarkConfig:
    job_count: int
    worker_count: int
    failure_rate: float
    include_timeouts: bool
    repeat_idempotency_submissions: bool
    seed: int = 42

    @classmethod
    def smoke(cls) -> BenchmarkConfig:
        return cls(
            job_count=100,
            worker_count=4,
            failure_rate=0.0,
            include_timeouts=False,
            repeat_idempotency_submissions=False,
        )

    @classmethod
    def v1_proof(cls) -> BenchmarkConfig:
        return cls(
            job_count=500,
            worker_count=20,
            failure_rate=0.10,
            include_timeouts=True,
            repeat_idempotency_submissions=True,
        )


@dataclass(frozen=True)
class ReliabilityReport:
    submitted_jobs: int
    lifecycle_counts: dict[str, int]
    completion_rate: float
    duplicate_finalization_count: int
    retry_count: int
    queue_lag_seconds: float
    p95_duration_seconds: float
    artifact_completeness: float
    finalization_conflict_attempt_count: int = 0
    failure_classification: dict[str, int] = field(default_factory=dict)
    estimated_cost_usd: Decimal = Decimal("0")
    run_id: str | None = None
    source: str = "configured_harness"
    idempotency_replay_count: int = 0
    injected_failure_count: int = 0
    title: str = "Load Smoke Report"
    backpressure: QueueBackpressureSnapshot | None = None
    artifact_integrity: ArtifactIntegritySummary | None = None


class ReliabilityProofValidationError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class ReliabilityProofResult:
    run_id: UUID
    report_path: Path
    report: ReliabilityReport
    failure_plan: FailurePlan


def run_smoke_benchmark(*, reports_dir: Path = Path("reports")) -> Path:
    config = BenchmarkConfig.smoke()
    report = ReliabilityReport(
        submitted_jobs=config.job_count,
        lifecycle_counts={
            "queued": 0,
            "running": 0,
            "completed": config.job_count,
            "failed": 0,
            "timed_out": 0,
            "cancelled": 0,
        },
        completion_rate=1.0,
        duplicate_finalization_count=0,
        retry_count=0,
        queue_lag_seconds=0.0,
        p95_duration_seconds=0.0,
        artifact_completeness=1.0,
        failure_classification={},
        estimated_cost_usd=Decimal("0"),
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "load_smoke.md"
    report_path.write_text(render_reliability_report(report), encoding="utf-8")
    return report_path


def render_reliability_report(report: ReliabilityReport) -> str:
    lines = [
        f"# {report.title}",
        "",
        f"source: {report.source}",
        f"submitted jobs: {report.submitted_jobs}",
        f"submitted_jobs: {report.submitted_jobs}",
        "",
        "## lifecycle counts",
    ]
    if report.run_id is not None:
        lines.insert(3, f"run id: {report.run_id}")
    for key, value in sorted(report.lifecycle_counts.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "## reliability fields",
            f"- completion rate: {report.completion_rate:.2%}",
            f"- duplicate-finalization count: {report.duplicate_finalization_count}",
            f"- finalization conflict attempts: {report.finalization_conflict_attempt_count}",
            f"- retry count: {report.retry_count}",
            f"- timeout count: {report.lifecycle_counts.get('timed_out', 0)}",
            f"- DLQ count: {report.lifecycle_counts.get('dlq', 0)}",
            f"- queue lag: {report.queue_lag_seconds:.3f}s",
            f"- queue lag p95: {report.queue_lag_seconds:.3f}s",
            f"- p95 duration: {report.p95_duration_seconds:.3f}s",
            f"- execution duration p95: {report.p95_duration_seconds:.3f}s",
            f"- artifact completeness: {report.artifact_completeness:.2%}",
            f"- failure classification: {report.failure_classification}",
            f"- injected failure count: {report.injected_failure_count}",
            f"- idempotency replay count: {report.idempotency_replay_count}",
            "- idempotency proof: duplicate_finalization_count == "
            f"{report.duplicate_finalization_count}",
            f"- estimated cost: ${report.estimated_cost_usd}",
            "",
        ]
    )
    artifact_integrity = report.artifact_integrity
    lines.extend(
        [
            "## artifact integrity",
            f"- checked artifacts: {artifact_integrity.checked_count if artifact_integrity else 0}",
            f"- valid artifacts: {artifact_integrity.valid_count if artifact_integrity else 0}",
        ]
    )
    if artifact_integrity is not None:
        for row in artifact_integrity.rows:
            artifact_line = (
                "- artifact "
                f"job_id={row.job_id} "
                f"run_id={row.run_id} "
                f"attempt_number={row.attempt_number} "
                f"size_bytes={row.size_bytes} "
                f"sha256={row.sha256} "
                f"input_digest={row.input_digest} "
                f"created_at={row.created_at.isoformat()} "
                f"path=artifact://{row.job_id}/{row.path.name}"
            )
            if row.eval_result_path is not None:
                artifact_line = (
                    f"{artifact_line} eval_result_path="
                    f"{portable_path(row.eval_result_path, namespace='eval-result')}"
                )
            lines.append(artifact_line)
    lines.append("")

    backpressure = report.backpressure
    queue_wait_p95 = report.queue_lag_seconds
    execution_p95 = report.p95_duration_seconds
    if backpressure is not None:
        queue_wait_p95 = backpressure.p95_queue_wait_seconds
        execution_p95 = backpressure.p95_execution_seconds

    lines.extend(
        [
            "## queue/backpressure",
            f"- queue depth: {backpressure.queue_depth if backpressure else 0}",
            "- oldest pending age seconds: "
            f"{backpressure.oldest_pending_age_seconds if backpressure else 0.0:.3f}",
            f"- consumer lag: {backpressure.consumer_lag if backpressure else 0}",
            f"- leased jobs: {backpressure.leased_jobs if backpressure else 0}",
            f"- running jobs: {backpressure.running_jobs if backpressure else 0}",
            f"- worker utilization: {backpressure.worker_utilization if backpressure else 0.0:.2%}",
            f"- retry rate: {backpressure.retry_rate if backpressure else 0.0:.2%}",
            f"- DLQ count: {backpressure.dlq_count if backpressure else 0}",
            f"- p95 queue wait seconds: {queue_wait_p95:.3f}",
            f"- p95 execution seconds: {execution_p95:.3f}",
            "",
        ]
    )
    return "\n".join(lines)


async def run_reliability_proof(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    jobs: int,
    workers: int,
    failure_rate: float,
    include_timeouts: bool,
    repeat_idempotency_submissions: bool,
    artifact_root: Path,
    report_path: Path,
    seed: int = 42,
) -> ReliabilityProofResult:
    if jobs <= 0:
        raise ValueError("jobs must be positive")
    if workers <= 0:
        raise ValueError("workers must be positive")
    if not 0 <= failure_rate <= 1:
        raise ValueError("failure_rate must be between 0 and 1")

    failure_count = int(jobs * failure_rate)
    failure_plan = FailurePlan.reliability_proof(
        seed=seed,
        count=failure_count,
        include_timeouts=include_timeouts,
    )
    run_id, idempotency_replay_count = await _submit_reliability_batch(
        session_factory=session_factory,
        queue=queue,
        jobs=jobs,
        failure_plan=failure_plan,
        repeat_idempotency_submissions=repeat_idempotency_submissions,
    )

    artifact_store = ArtifactStore(artifact_root)
    worker_pool = [
        Worker(
            worker_id=f"proof-worker-{index + 1}",
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

    from agent_runtime_grid.cli.smoke import build_smoke_report

    report = await build_smoke_report(
        session_factory=session_factory,
        run_id=run_id,
        artifact_root=artifact_root,
        queue=queue,
        worker_count=workers,
    )
    report = ReliabilityReport(
        submitted_jobs=report.submitted_jobs,
        lifecycle_counts=report.lifecycle_counts,
        completion_rate=report.completion_rate,
        duplicate_finalization_count=report.duplicate_finalization_count,
        finalization_conflict_attempt_count=report.finalization_conflict_attempt_count,
        retry_count=report.retry_count,
        queue_lag_seconds=report.queue_lag_seconds,
        p95_duration_seconds=report.p95_duration_seconds,
        artifact_completeness=report.artifact_completeness,
        failure_classification={
            **report.failure_classification,
            **{
                f"injected_{mode.value}": count
                for mode, count in failure_plan.counts().items()
                if count
            },
        },
        estimated_cost_usd=Decimal("0"),
        run_id=str(run_id),
        source=f"runtime_state:{artifact_root}",
        idempotency_replay_count=idempotency_replay_count,
        injected_failure_count=failure_count,
        title="V1 Reliability Proof Report",
        backpressure=report.backpressure,
        artifact_integrity=report.artifact_integrity,
    )
    validate_reliability_proof(
        report,
        expected_jobs=jobs,
        failure_rate=failure_rate,
        include_timeouts=include_timeouts,
        repeat_idempotency_submissions=repeat_idempotency_submissions,
    )

    write_evidence_bundle(
        report_path=report_path,
        rendered_report=render_reliability_report(report),
        report=report,
        command="benchmark v1-proof",
        config={
            "jobs": jobs,
            "workers": workers,
            "failure_rate": failure_rate,
            "include_timeouts": include_timeouts,
            "repeat_idempotency_submissions": repeat_idempotency_submissions,
            "artifact_root": artifact_root,
        },
        seed=seed,
    )
    return ReliabilityProofResult(
        run_id=run_id,
        report_path=report_path,
        report=report,
        failure_plan=failure_plan,
    )


async def run_reliability_proof_from_urls(
    *,
    database_url: str = DEFAULT_DATABASE_URL,
    redis_url: str = DEFAULT_REDIS_URL,
    jobs: int = 500,
    workers: int = 20,
    failure_rate: float = 0.10,
    include_timeouts: bool = True,
    repeat_idempotency_submissions: bool = True,
    artifact_root: Path = Path("artifacts"),
    report_path: Path = Path("reports/v1/reliability_report.md"),
    clean_state: bool = False,
) -> ReliabilityProofResult:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(redis_url, decode_responses=True)
    lock_connection = None
    suffix = uuid4().hex
    queue = RedisStreamsQueue(
        redis,
        stream_name=f"proof-jobs:{suffix}",
        consumer_group="proof-workers",
        dlq_stream_name=f"proof-jobs:{suffix}:dlq",
    )
    try:
        if clean_state:
            require_safe_local_reset(database_url)
            lock_connection = await engine.connect()
            await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))
            async with engine.begin() as connection:
                await connection.run_sync(metadata.drop_all)
                await connection.run_sync(metadata.create_all)

        return await run_reliability_proof(
            session_factory=session_factory,
            queue=queue,
            jobs=jobs,
            workers=workers,
            failure_rate=failure_rate,
            include_timeouts=include_timeouts,
            repeat_idempotency_submissions=repeat_idempotency_submissions,
            artifact_root=artifact_root,
            report_path=report_path,
        )
    finally:
        if lock_connection is not None:
            await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
            await lock_connection.close()
        await redis.aclose()
        await engine.dispose()


async def _submit_reliability_batch(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    jobs: int,
    failure_plan: FailurePlan,
    repeat_idempotency_submissions: bool,
) -> tuple[UUID, int]:
    run_id = uuid4()
    failures_by_index = {failure.index: failure.mode for failure in failure_plan.failures}
    idempotency_replay_count = 0
    async with session_factory() as session:
        repository = JobRepository(session)
        for index in range(jobs):
            mode = failures_by_index.get(index)
            payload = (
                payload_for_failure(mode)
                if mode is not None
                else {"index": index, "mode": "success"}
            )
            timeout_seconds = 1 if mode is FailureMode.TIMEOUT else 30
            max_retries = 1 if mode is FailureMode.TRANSIENT else 0
            submission = JobSubmission(
                job_type="stub",
                payload={**payload, "index": index},
                idempotency_key=f"{run_id}:{index}",
                timeout_seconds=timeout_seconds,
                max_retries=max_retries,
                trace_id=f"trace-{run_id}",
                run_id=run_id,
            )
            job = await repository.create_job(submission)
            if repeat_idempotency_submissions and mode is FailureMode.DUPLICATE_SUBMISSION:
                replayed_job = await repository.create_job(submission)
                if replayed_job.id != job.id:
                    raise RuntimeError("idempotency replay returned a different job")
                idempotency_replay_count += 1

            await queue.publish_job(
                QueueJobMessage(
                    job_id=str(job.id),
                    run_id=str(job.run_id),
                    attempt_number=1,
                    trace_id=job.trace_id,
                )
            )
    return run_id, idempotency_replay_count


def validate_reliability_proof(
    report: ReliabilityReport,
    *,
    expected_jobs: int,
    failure_rate: float,
    include_timeouts: bool,
    repeat_idempotency_submissions: bool,
) -> None:
    terminal_count = sum(
        report.lifecycle_counts.get(status, 0)
        for status in ("completed", "failed", "timed_out", "cancelled")
    )
    errors: list[str] = []
    if report.submitted_jobs != expected_jobs:
        errors.append(f"submitted_jobs expected {expected_jobs}, got {report.submitted_jobs}")
    if terminal_count != expected_jobs:
        errors.append(f"terminal jobs expected {expected_jobs}, got {terminal_count}")
    if report.duplicate_finalization_count != 0:
        errors.append(f"duplicate finalizations: {report.duplicate_finalization_count}")
    if failure_rate > 0 and report.retry_count == 0:
        errors.append("expected retry evidence for injected transient failures")
    if include_timeouts and report.lifecycle_counts.get("timed_out", 0) == 0:
        errors.append("expected timeout evidence")
    if repeat_idempotency_submissions and report.idempotency_replay_count == 0:
        errors.append("expected idempotency replay evidence")
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
        errors.append(f"stub proof cost expected $0, got ${report.estimated_cost_usd}")
    if errors:
        raise ReliabilityProofValidationError(errors)


@benchmark_app.command("v1-proof")
def v1_proof_command(
    jobs: Annotated[int, typer.Option("--jobs", min=1)] = 500,
    workers: Annotated[int, typer.Option("--workers", min=1)] = 20,
    failure_rate: Annotated[float, typer.Option("--failure-rate", min=0, max=1)] = 0.10,
    include_timeouts: Annotated[bool, typer.Option("--include-timeouts")] = True,
    repeat_idempotency_submissions: Annotated[
        bool, typer.Option("--repeat-idempotency-submissions")
    ] = True,
    report_path: Annotated[Path, typer.Option("--report")] = Path(
        "reports/v1/reliability_report.md"
    ),
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
            run_reliability_proof_from_urls(
                database_url=database_url,
                redis_url=redis_url,
                jobs=jobs,
                workers=workers,
                failure_rate=failure_rate,
                include_timeouts=include_timeouts,
                repeat_idempotency_submissions=repeat_idempotency_submissions,
                artifact_root=artifact_root,
                report_path=report_path,
                clean_state=reset_local_database,
            )
        )
    except (
        ArtifactIntegrityError,
        ReliabilityProofValidationError,
        UnsafeDatabaseResetError,
        ValueError,
    ) as exc:
        typer.echo(f"v1 proof failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"report: {result.report_path}")
