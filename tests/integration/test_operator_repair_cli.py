import asyncio
import os
from collections.abc import Mapping
from dataclasses import dataclass
from uuid import UUID, uuid4

from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typer.testing import CliRunner

from agent_runtime_grid.cli.main import app
from agent_runtime_grid.domain.jobs import JobRecord, JobSubmission
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import (
    job_events_table,
    job_finalizations_table,
    jobs_table,
    metadata,
)
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.worker.loop import Worker
from agent_runtime_grid.worker.recovery import recover_stale_leases
from agent_runtime_grid.worker.state_machine import load_job_for_update, record_running

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"


@dataclass(frozen=True)
class OperatorTestState:
    database_url: str
    redis_url: str
    stream_name: str
    consumer_group: str
    dlq_stream_name: str
    run_id: UUID
    leased_entry_id: str


def test_renew_pending_lease_prevents_false_stale_recovery() -> None:
    state = asyncio.run(_prepare_pending_state(max_retries=1))
    try:
        result = asyncio.run(_renew_and_attempt_recovery(state))
    finally:
        asyncio.run(_cleanup_state(state))

    assert result["stale_before_renewal"] == 1
    assert result["renewed"] is True
    assert result["recovery_detected"] == 0
    assert result["events"] == ["submitted", "running"]
    assert result["finalization_count"] == 0


def test_operator_inspect_reports_queue_state_without_payloads() -> None:
    state = asyncio.run(
        _prepare_pending_state(
            max_retries=1,
            queued_job_count=1,
            payload={"api_token": "secret-value", "raw_payload": "do-not-render"},
        )
    )
    try:
        result = CliRunner().invoke(
            app,
            [
                "operator",
                "inspect",
                "--database-url",
                state.database_url,
                "--redis-url",
                state.redis_url,
                "--stream-name",
                state.stream_name,
                "--consumer-group",
                state.consumer_group,
                "--dlq-stream-name",
                state.dlq_stream_name,
                "--stale-after-ms",
                "0",
                "--run-id",
                str(state.run_id),
                "--workers",
                "4",
            ],
        )
    finally:
        asyncio.run(_cleanup_state(state))

    assert result.exit_code == 0, result.output
    assert "queue_depth: 2" in result.output
    assert "pending_leases: 1" in result.output
    assert "stale_leases: 1" in result.output
    assert "consumer_lag: 1" in result.output
    assert "running_jobs: 1" in result.output
    assert "secret-value" not in result.output
    assert "raw_payload" not in result.output
    assert "api_token" not in result.output


def test_operator_recover_requeues_stale_work_for_replacement_worker() -> None:
    state = asyncio.run(_prepare_pending_state(max_retries=1))
    try:
        result = CliRunner().invoke(
            app,
            [
                "operator",
                "recover-stale",
                "--database-url",
                state.database_url,
                "--redis-url",
                state.redis_url,
                "--stream-name",
                state.stream_name,
                "--consumer-group",
                state.consumer_group,
                "--dlq-stream-name",
                state.dlq_stream_name,
                "--stale-after-ms",
                "0",
                "--recovery-worker-id",
                "operator-recovery",
            ],
        )
        processed = asyncio.run(_process_recovered_work(state))
    finally:
        asyncio.run(_cleanup_state(state))

    assert result.exit_code == 0, result.output
    assert "detected: 1" in result.output
    assert "requeued: 1" in result.output
    assert "dlq: 0" in result.output
    assert processed["processed"] is True
    assert processed["status"] == "completed"
    assert processed["events"] == [
        "submitted",
        "running",
        "stale_lease_recovered",
        "running",
        "completed",
    ]
    assert processed["finalization_count"] == 1


async def _prepare_pending_state(
    *,
    max_retries: int,
    queued_job_count: int = 0,
    payload: Mapping[str, object] | None = None,
) -> OperatorTestState:
    database_url = os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
    redis_url = os.environ.get("REDIS_URL", DEFAULT_REDIS_URL)
    engine = create_async_engine(database_url)
    redis = Redis.from_url(redis_url, decode_responses=True)
    lock_connection = await engine.connect()
    stream_suffix = uuid4().hex
    stream_name = f"operator-jobs:{stream_suffix}"
    consumer_group = "operator-workers"
    dlq_stream_name = f"operator-jobs:{stream_suffix}:dlq"
    run_id = uuid4()

    try:
        await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        queue = RedisStreamsQueue(
            redis,
            stream_name=stream_name,
            consumer_group=consumer_group,
            dlq_stream_name=dlq_stream_name,
        )
        leased_job = await _create_job(
            session_factory,
            run_id=run_id,
            index=0,
            max_retries=max_retries,
            payload=payload or {"message": "ok"},
        )
        await _publish_job(queue, leased_job)
        leased = await queue.lease_jobs(consumer_name="crashed-worker", block_ms=10)
        assert len(leased) == 1
        assert leased[0].entry_id is not None

        async with session_factory() as session:
            async with session.begin():
                locked_job = await load_job_for_update(session, leased_job.id)
                assert locked_job is not None
                await record_running(
                    session,
                    locked_job,
                    worker_id="crashed-worker",
                    attempt_number=1,
                )

        for index in range(queued_job_count):
            queued_job = await _create_job(
                session_factory,
                run_id=run_id,
                index=index + 1,
                max_retries=max_retries,
                payload={"message": "queued"},
            )
            await _publish_job(queue, queued_job)

        return OperatorTestState(
            database_url=database_url,
            redis_url=redis_url,
            stream_name=stream_name,
            consumer_group=consumer_group,
            dlq_stream_name=dlq_stream_name,
            run_id=run_id,
            leased_entry_id=leased[0].entry_id,
        )
    finally:
        await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
        await lock_connection.close()
        await redis.aclose()
        await engine.dispose()


async def _create_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: UUID,
    index: int,
    max_retries: int,
    payload: Mapping[str, object],
) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload=dict(payload),
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


async def _renew_and_attempt_recovery(state: OperatorTestState) -> dict[str, object]:
    engine = create_async_engine(state.database_url)
    redis = Redis.from_url(state.redis_url, decode_responses=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    queue = RedisStreamsQueue(
        redis,
        stream_name=state.stream_name,
        consumer_group=state.consumer_group,
        dlq_stream_name=state.dlq_stream_name,
    )
    try:
        await asyncio.sleep(0.02)
        stale_before = await queue.find_stale_leases(stale_after_ms=1)
        renewed = await queue.renew_pending_lease(
            entry_id=state.leased_entry_id,
            consumer_name="crashed-worker",
        )
        recovery = await recover_stale_leases(
            queue=queue,
            session_factory=session_factory,
            recovery_worker_id="operator-recovery",
            stale_after_ms=1_000,
        )
        return {
            "stale_before_renewal": len(stale_before),
            "renewed": renewed,
            "recovery_detected": recovery.detected_count,
            "events": await _event_types(session_factory),
            "finalization_count": await _finalization_count(session_factory),
        }
    finally:
        await redis.aclose()
        await engine.dispose()


async def _process_recovered_work(state: OperatorTestState) -> dict[str, object]:
    engine = create_async_engine(state.database_url)
    redis = Redis.from_url(state.redis_url, decode_responses=True)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    queue = RedisStreamsQueue(
        redis,
        stream_name=state.stream_name,
        consumer_group=state.consumer_group,
        dlq_stream_name=state.dlq_stream_name,
    )
    try:
        worker = Worker(
            worker_id="replacement-worker",
            queue=queue,
            session_factory=session_factory,
        )
        processed = await worker.process_one()
        return {
            "processed": processed,
            "status": await _job_status(session_factory),
            "events": await _event_types(session_factory),
            "finalization_count": await _finalization_count(session_factory),
        }
    finally:
        await redis.aclose()
        await engine.dispose()


async def _event_types(session_factory: async_sessionmaker[AsyncSession]) -> list[str]:
    async with session_factory() as session:
        rows = (
            await session.execute(
                select(job_events_table.c.event_type).order_by(job_events_table.c.id.asc())
            )
        ).scalars()
    return list(rows)


async def _job_status(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        status = await session.scalar(select(jobs_table.c.status))
    assert status is not None
    return status


async def _finalization_count(session_factory: async_sessionmaker[AsyncSession]) -> int:
    async with session_factory() as session:
        count = await session.scalar(select(func.count()).select_from(job_finalizations_table))
    assert count is not None
    return count


async def _cleanup_state(state: OperatorTestState) -> None:
    engine = create_async_engine(state.database_url)
    redis = Redis.from_url(state.redis_url, decode_responses=True)
    lock_connection = await engine.connect()
    try:
        await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
        await redis.delete(state.stream_name, state.dlq_stream_name)
    finally:
        await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
        await lock_connection.close()
        await redis.aclose()
        await engine.dispose()
