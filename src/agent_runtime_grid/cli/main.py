from __future__ import annotations

import asyncio
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated
from uuid import UUID, uuid4

import typer
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.domain.jobs import JobSubmission
from agent_runtime_grid.evidence import (
    EvidenceVerificationError,
    verify_committed_release_evidence,
    verify_evidence_manifest,
)
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import job_events_table, jobs_table
from agent_runtime_grid.storage.repositories import JobRepository

app = typer.Typer()

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
LIFECYCLE_COUNT_KEYS = (
    "queued",
    "running",
    "completed",
    "failed",
    "timed_out",
    "cancelled",
    "retry",
    "dlq",
)


@dataclass(frozen=True)
class BatchSubmissionResult:
    run_id: UUID
    job_count: int


def create_session_factory(
    database_url: str = DEFAULT_DATABASE_URL,
) -> async_sessionmaker[AsyncSession]:
    engine = create_async_engine(database_url)
    return async_sessionmaker(engine, expire_on_commit=False)


async def submit_batch(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    count: int,
    job_type: str,
    timeout_seconds: int = 30,
    max_retries: int = 1,
) -> BatchSubmissionResult:
    run_id = uuid4()
    async with session_factory() as session:
        repository = JobRepository(session)
        for index in range(count):
            job = await repository.create_job(
                JobSubmission(
                    job_type=job_type,
                    payload={"index": index, "mode": "success"},
                    idempotency_key=f"{run_id}:{index}",
                    timeout_seconds=timeout_seconds,
                    max_retries=max_retries,
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
    return BatchSubmissionResult(run_id=run_id, job_count=count)


async def lifecycle_counts(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    run_id: UUID,
) -> dict[str, int]:
    counts = dict.fromkeys(LIFECYCLE_COUNT_KEYS, 0)
    async with session_factory() as session:
        status_rows = (
            await session.execute(
                select(jobs_table.c.status, func.count())
                .where(jobs_table.c.run_id == run_id)
                .group_by(jobs_table.c.status)
            )
        ).all()
        for status, count in status_rows:
            key = "queued" if status in {"submitted", "queued"} else status
            if key in counts:
                counts[key] += count

        retry_count = await session.scalar(
            select(func.count())
            .select_from(job_events_table)
            .where(
                job_events_table.c.run_id == run_id,
                job_events_table.c.event_type == "retry_scheduled",
            )
        )
    counts["retry"] = int(retry_count or 0)
    return counts


def format_status(counts: dict[str, int]) -> str:
    labels = {
        "queued": "queued",
        "running": "running",
        "completed": "completed",
        "failed": "failed",
        "timed_out": "timed out",
        "cancelled": "cancelled",
        "retry": "retry",
        "dlq": "DLQ",
    }
    return "\n".join(f"{labels[key]}: {counts.get(key, 0)}" for key in LIFECYCLE_COUNT_KEYS)


def cleanup_run_outputs(
    *,
    run_id: UUID,
    artifact_root: Path,
    reports_root: Path,
) -> list[Path]:
    removed: list[Path] = []
    for path in (artifact_root / str(run_id), reports_root / f"{run_id}.md"):
        if path.is_dir():
            shutil.rmtree(path)
            removed.append(path)
        elif path.exists():
            path.unlink()
            removed.append(path)
    return removed


@app.command("submit-batch")
def submit_batch_command(
    count: Annotated[int, typer.Option("--count")],
    job_type: Annotated[str, typer.Option("--job-type")],
    database_url: Annotated[str, typer.Option("--database-url")] = DEFAULT_DATABASE_URL,
    redis_url: Annotated[str, typer.Option("--redis-url")] = DEFAULT_REDIS_URL,
) -> None:
    asyncio.run(_submit_batch_command(count, job_type, database_url, redis_url))


async def _submit_batch_command(
    count: int,
    job_type: str,
    database_url: str,
    redis_url: str,
) -> None:
    session_factory = create_session_factory(database_url)
    redis = Redis.from_url(redis_url, decode_responses=True)
    try:
        queue = RedisStreamsQueue(redis)
        result = await submit_batch(
            session_factory=session_factory,
            queue=queue,
            count=count,
            job_type=job_type,
        )
        typer.echo(f"run_id: {result.run_id}")
        typer.echo(f"jobs: {result.job_count}")
    finally:
        await redis.aclose()


@app.command("status")
def status_command(
    run_id: Annotated[UUID, typer.Option("--run-id")],
    database_url: Annotated[str, typer.Option("--database-url")] = DEFAULT_DATABASE_URL,
) -> None:
    counts = asyncio.run(
        lifecycle_counts(session_factory=create_session_factory(database_url), run_id=run_id)
    )
    typer.echo(format_status(counts))


@app.command("cleanup")
def cleanup_command(
    run_id: Annotated[UUID, typer.Option("--run-id")],
    artifact_root: Annotated[Path, typer.Option("--artifact-root")] = Path("artifacts"),
    reports_root: Annotated[Path, typer.Option("--reports-root")] = Path("reports"),
) -> None:
    for removed in cleanup_run_outputs(
        run_id=run_id,
        artifact_root=artifact_root,
        reports_root=reports_root,
    ):
        typer.echo(f"removed: {removed}")


@app.command("verify-evidence")
def verify_evidence_command(
    manifest: Annotated[Path, typer.Option("--manifest")],
) -> None:
    try:
        verify_evidence_manifest(manifest)
    except EvidenceVerificationError as exc:
        typer.echo(f"evidence verification failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"verified: {manifest}")


@app.command("verify-committed-evidence")
def verify_committed_evidence_command(
    repository_root: Annotated[Path, typer.Option("--repository-root")] = Path("."),
) -> None:
    try:
        result = verify_committed_release_evidence(repository_root)
    except EvidenceVerificationError as exc:
        typer.echo(f"committed evidence verification failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(
        json.dumps(
            {
                "content_address": result.content_address,
                "manifest_path": result.manifest_path,
                "source_revision": result.source_revision,
                "submitted_jobs": result.submitted_jobs,
                "valid_artifacts": result.valid_artifacts,
                "verified": True,
            },
            sort_keys=True,
        )
    )


from agent_runtime_grid.cli.benchmark import benchmark_app  # noqa: E402
from agent_runtime_grid.cli.cost import app as cost_app  # noqa: E402
from agent_runtime_grid.cli.failure_reports import app as failure_reports_app  # noqa: E402
from agent_runtime_grid.cli.operator import app as operator_app  # noqa: E402
from agent_runtime_grid.cli.proof import proof_app  # noqa: E402
from agent_runtime_grid.cli.smoke import smoke_command  # noqa: E402

app.add_typer(benchmark_app, name="benchmark")
app.add_typer(cost_app, name="cost")
app.add_typer(failure_reports_app, name="failure-reports")
app.add_typer(operator_app, name="operator")
app.add_typer(proof_app, name="proof")
app.command("smoke")(smoke_command)
