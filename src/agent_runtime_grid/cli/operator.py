from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

import typer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.queue.inspection import (
    QueueBackpressureSnapshot,
    inspect_queue_backpressure,
)
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.worker.recovery import (
    StaleLeaseRecoveryResult,
    recover_stale_leases,
)

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_STREAM_NAME = "jobs"
DEFAULT_CONSUMER_GROUP = "workers"
DEFAULT_DLQ_STREAM_NAME = "jobs:dlq"

app = typer.Typer()


@dataclass(frozen=True)
class OperatorQueueInspection:
    backpressure: QueueBackpressureSnapshot
    stale_lease_count: int


async def inspect_operator_queue(
    *,
    queue: RedisStreamsQueue,
    session_factory: async_sessionmaker[AsyncSession],
    stale_after_ms: int,
    run_id: UUID | None = None,
    worker_count: int | None = None,
) -> OperatorQueueInspection:
    backpressure = await inspect_queue_backpressure(
        queue=queue,
        session_factory=session_factory,
        run_id=run_id,
        worker_count=worker_count,
    )
    stale_leases = await queue.find_stale_leases(stale_after_ms=stale_after_ms)
    return OperatorQueueInspection(
        backpressure=backpressure,
        stale_lease_count=len(stale_leases),
    )


def render_operator_inspection(inspection: OperatorQueueInspection) -> str:
    backpressure = inspection.backpressure
    lines = [
        f"queue_depth: {backpressure.queue_depth}",
        f"pending_leases: {backpressure.leased_jobs}",
        f"stale_leases: {inspection.stale_lease_count}",
        f"oldest_pending_age_seconds: {backpressure.oldest_pending_age_seconds:.3f}",
        f"consumer_lag: {backpressure.consumer_lag}",
        f"running_jobs: {backpressure.running_jobs}",
        f"worker_utilization: {backpressure.worker_utilization:.2%}",
        f"retry_rate: {backpressure.retry_rate:.2%}",
        f"dlq_count: {backpressure.dlq_count}",
        f"p95_queue_wait_seconds: {backpressure.p95_queue_wait_seconds:.3f}",
        f"p95_execution_seconds: {backpressure.p95_execution_seconds:.3f}",
    ]
    return "\n".join(lines)


def render_recovery_result(result: StaleLeaseRecoveryResult) -> str:
    lines = [
        f"detected: {result.detected_count}",
        f"requeued: {result.requeued_count}",
        f"dlq: {result.dlq_count}",
        f"acknowledged_terminal: {result.acknowledged_terminal_count}",
        f"acknowledged_missing: {result.acknowledged_missing_count}",
    ]
    return "\n".join(lines)


async def inspect_from_urls(
    *,
    database_url: str = DEFAULT_DATABASE_URL,
    redis_url: str = DEFAULT_REDIS_URL,
    stream_name: str = DEFAULT_STREAM_NAME,
    consumer_group: str = DEFAULT_CONSUMER_GROUP,
    dlq_stream_name: str = DEFAULT_DLQ_STREAM_NAME,
    stale_after_ms: int = 60_000,
    run_id: UUID | None = None,
    worker_count: int | None = None,
) -> OperatorQueueInspection:
    engine = create_async_engine(database_url)
    redis = Redis.from_url(redis_url, decode_responses=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    queue = RedisStreamsQueue(
        redis,
        stream_name=stream_name,
        consumer_group=consumer_group,
        dlq_stream_name=dlq_stream_name,
    )
    try:
        return await inspect_operator_queue(
            queue=queue,
            session_factory=session_factory,
            stale_after_ms=stale_after_ms,
            run_id=run_id,
            worker_count=worker_count,
        )
    finally:
        await redis.aclose()
        await engine.dispose()


async def recover_from_urls(
    *,
    database_url: str = DEFAULT_DATABASE_URL,
    redis_url: str = DEFAULT_REDIS_URL,
    stream_name: str = DEFAULT_STREAM_NAME,
    consumer_group: str = DEFAULT_CONSUMER_GROUP,
    dlq_stream_name: str = DEFAULT_DLQ_STREAM_NAME,
    stale_after_ms: int = 60_000,
    recovery_worker_id: str = "operator-recovery",
    count: int = 100,
) -> StaleLeaseRecoveryResult:
    engine = create_async_engine(database_url)
    redis = Redis.from_url(redis_url, decode_responses=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    queue = RedisStreamsQueue(
        redis,
        stream_name=stream_name,
        consumer_group=consumer_group,
        dlq_stream_name=dlq_stream_name,
    )
    try:
        return await recover_stale_leases(
            queue=queue,
            session_factory=session_factory,
            recovery_worker_id=recovery_worker_id,
            stale_after_ms=stale_after_ms,
            count=count,
        )
    finally:
        await redis.aclose()
        await engine.dispose()


@app.command("inspect")
def inspect_command(
    database_url: Annotated[str, typer.Option("--database-url")] = DEFAULT_DATABASE_URL,
    redis_url: Annotated[str, typer.Option("--redis-url")] = DEFAULT_REDIS_URL,
    stream_name: Annotated[str, typer.Option("--stream-name")] = DEFAULT_STREAM_NAME,
    consumer_group: Annotated[str, typer.Option("--consumer-group")] = DEFAULT_CONSUMER_GROUP,
    dlq_stream_name: Annotated[str, typer.Option("--dlq-stream-name")] = DEFAULT_DLQ_STREAM_NAME,
    stale_after_ms: Annotated[int, typer.Option("--stale-after-ms")] = 60_000,
    run_id: Annotated[UUID | None, typer.Option("--run-id")] = None,
    worker_count: Annotated[int | None, typer.Option("--workers")] = None,
) -> None:
    inspection = asyncio.run(
        inspect_from_urls(
            database_url=database_url,
            redis_url=redis_url,
            stream_name=stream_name,
            consumer_group=consumer_group,
            dlq_stream_name=dlq_stream_name,
            stale_after_ms=stale_after_ms,
            run_id=run_id,
            worker_count=worker_count,
        )
    )
    typer.echo(render_operator_inspection(inspection))


@app.command("recover-stale")
def recover_stale_command(
    database_url: Annotated[str, typer.Option("--database-url")] = DEFAULT_DATABASE_URL,
    redis_url: Annotated[str, typer.Option("--redis-url")] = DEFAULT_REDIS_URL,
    stream_name: Annotated[str, typer.Option("--stream-name")] = DEFAULT_STREAM_NAME,
    consumer_group: Annotated[str, typer.Option("--consumer-group")] = DEFAULT_CONSUMER_GROUP,
    dlq_stream_name: Annotated[str, typer.Option("--dlq-stream-name")] = DEFAULT_DLQ_STREAM_NAME,
    stale_after_ms: Annotated[int, typer.Option("--stale-after-ms")] = 60_000,
    recovery_worker_id: Annotated[str, typer.Option("--recovery-worker-id")] = (
        "operator-recovery"
    ),
    count: Annotated[int, typer.Option("--count")] = 100,
) -> None:
    result = asyncio.run(
        recover_from_urls(
            database_url=database_url,
            redis_url=redis_url,
            stream_name=stream_name,
            consumer_group=consumer_group,
            dlq_stream_name=dlq_stream_name,
            stale_after_ms=stale_after_ms,
            recovery_worker_id=recovery_worker_id,
            count=count,
        )
    )
    typer.echo(render_recovery_result(result))
