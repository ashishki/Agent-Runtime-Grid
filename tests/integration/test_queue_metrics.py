import os
from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.domain.jobs import JobRecord, JobSubmission
from agent_runtime_grid.observability.metrics import RuntimeMetrics
from agent_runtime_grid.queue.inspection import (
    QueueBackpressureSnapshot,
    inspect_queue_backpressure,
)
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import metadata
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.worker.loop import Worker
from agent_runtime_grid.worker.state_machine import (
    load_job_for_update,
    record_retry_scheduled,
    record_running,
)

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


@pytest_asyncio.fixture
async def session_factory() -> AsyncIterator[async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    lock_connection = await engine.connect()
    await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)

        yield async_sessionmaker(engine, expire_on_commit=False)

        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
    finally:
        await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
        await lock_connection.close()
        await engine.dispose()


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(
        os.environ.get("REDIS_URL", DEFAULT_REDIS_URL),
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def queue(redis_client: Redis) -> RedisStreamsQueue:
    suffix = uuid4().hex
    return RedisStreamsQueue(
        redis_client,
        stream_name=f"queue-metrics-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"queue-metrics-jobs:{suffix}:dlq",
    )


async def _create_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: UUID,
    index: int,
    max_retries: int = 1,
) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload={"index": index, "message": "ok"},
                idempotency_key=f"{run_id}:{index}",
                timeout_seconds=30,
                max_retries=max_retries,
                trace_id=f"trace-{run_id}",
                run_id=run_id,
            )
        )


async def _publish_job(queue: RedisStreamsQueue, job: JobRecord) -> str:
    return await queue.publish_job(
        QueueJobMessage(
            job_id=str(job.id),
            run_id=str(job.run_id),
            attempt_number=1,
            trace_id=job.trace_id,
        )
    )


@pytest.mark.asyncio
async def test_queue_backpressure_metrics_come_from_runtime_state(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
) -> None:
    run_id = uuid4()
    completed_job = await _create_job(session_factory, run_id=run_id, index=1)
    await _publish_job(queue, completed_job)
    worker = Worker(worker_id="metrics-worker", queue=queue, session_factory=session_factory)
    assert await worker.process_one() is True

    leased_job = await _create_job(session_factory, run_id=run_id, index=2)
    queued_job = await _create_job(session_factory, run_id=run_id, index=3)
    retry_job = await _create_job(session_factory, run_id=run_id, index=4)
    await _publish_job(queue, leased_job)
    await _publish_job(queue, queued_job)
    leased = await queue.lease_jobs(consumer_name="crashed-worker", block_ms=10)
    assert len(leased) == 1

    async with session_factory() as session:
        async with session.begin():
            locked_leased_job = await load_job_for_update(session, leased_job.id)
            assert locked_leased_job is not None
            await record_running(
                session,
                locked_leased_job,
                worker_id="crashed-worker",
                attempt_number=1,
            )
            locked_retry_job = await load_job_for_update(session, retry_job.id)
            assert locked_retry_job is not None
            await record_retry_scheduled(
                session,
                locked_retry_job,
                worker_id="metrics-worker",
                attempt_number=1,
                next_attempt_number=2,
                error_class="TransientRunnerError",
            )

    snapshot = await inspect_queue_backpressure(
        queue=queue,
        session_factory=session_factory,
        run_id=run_id,
        worker_count=4,
    )

    assert snapshot.queue_depth == 2
    assert snapshot.leased_jobs == 1
    assert snapshot.consumer_lag == 1
    assert snapshot.running_jobs == 1
    assert snapshot.worker_utilization == 0.25
    assert snapshot.retry_rate == 0.25
    assert snapshot.dlq_count == 0
    assert snapshot.oldest_pending_age_seconds >= 0
    assert snapshot.p95_queue_wait_seconds >= 0
    assert snapshot.p95_execution_seconds >= 0


def test_queue_metrics_exclude_secrets_and_payloads() -> None:
    metrics = RuntimeMetrics()
    metrics.record_backpressure_snapshot(
        QueueBackpressureSnapshot(
            queue_depth=2,
            oldest_pending_age_seconds=1.5,
            consumer_lag=1,
            leased_jobs=1,
            running_jobs=1,
            worker_utilization=0.25,
            retry_rate=0.25,
            dlq_count=0,
            p95_queue_wait_seconds=0.2,
            p95_execution_seconds=0.5,
        )
    )

    rendered = metrics.render()

    assert "agent_runtime_grid_queue_oldest_pending_age_seconds" in rendered
    assert "agent_runtime_grid_queue_consumer_lag" in rendered
    assert "agent_runtime_grid_queue_leased_jobs" in rendered
    assert "agent_runtime_grid_queue_running_jobs" in rendered
    assert "agent_runtime_grid_queue_retry_rate" in rendered
    assert "agent_runtime_grid_queue_dlq_count" in rendered
    assert "agent_runtime_grid_queue_wait_p95_seconds" in rendered
    assert "agent_runtime_grid_queue_execution_p95_seconds" in rendered
    assert "api_token" not in rendered
    assert "provider_token" not in rendered
    assert "raw_payload" not in rendered
    assert "secret-value" not in rendered
