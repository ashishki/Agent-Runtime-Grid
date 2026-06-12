import os
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from typer.testing import CliRunner

from agent_runtime_grid.cli.benchmark import run_reliability_proof
from agent_runtime_grid.cli.cost import app as cost_app
from agent_runtime_grid.cli.smoke import run_smoke
from agent_runtime_grid.cost.telemetry import (
    BudgetExceededError,
    BudgetPolicy,
    CostTelemetryRecord,
    LiveBudgetRequiredError,
    ProviderCallBlockedError,
    append_jsonl,
)
from agent_runtime_grid.domain.jobs import JobSubmission
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import job_events_table, jobs_table, metadata
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.worker.loop import Worker

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
        stream_name=f"budget-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"budget-jobs:{suffix}:dlq",
    )


def _cost_record(*, cost: str, job_id: str = "job-1") -> CostTelemetryRecord:
    return CostTelemetryRecord(
        project="agent-runtime-grid",
        run_id="run-1",
        job_id=job_id,
        job_type="live.sample",
        worker_id="worker-1",
        model="example-model",
        provider="example-provider",
        input_tokens=10,
        output_tokens=5,
        estimated_cost_usd=Decimal(cost),
        retry_count=0,
        environment="test",
    )


@pytest.mark.asyncio
async def test_stub_mode_blocks_provider_calls(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    with pytest.raises(ProviderCallBlockedError, match="stub_provider_call_blocked"):
        BudgetPolicy.stub().validate_provider_call()

    smoke_result = await run_smoke(
        session_factory=session_factory,
        queue=queue,
        jobs=3,
        workers=2,
        failure_rate=0,
        mode="stub",
        artifact_root=tmp_path / "smoke-artifacts",
        report_path=tmp_path / "reports" / "smoke.md",
    )
    proof_result = await run_reliability_proof(
        session_factory=session_factory,
        queue=queue,
        jobs=10,
        workers=2,
        failure_rate=0,
        include_timeouts=False,
        repeat_idempotency_submissions=False,
        artifact_root=tmp_path / "proof-artifacts",
        report_path=tmp_path / "reports" / "v1" / "reliability_report.md",
    )

    assert smoke_result.report.estimated_cost_usd == Decimal("0")
    assert proof_result.report.estimated_cost_usd == Decimal("0")


def test_live_mode_requires_explicit_budget() -> None:
    missing_all = BudgetPolicy.live()
    with pytest.raises(LiveBudgetRequiredError, match="missing_live_run_or_job_budget"):
        missing_all.validate_dispatch(job_type="live.sample", budget_cents=1)

    missing_job = BudgetPolicy.live(run_budget_cents=500, per_job_budget_cents=100)
    with pytest.raises(LiveBudgetRequiredError, match="missing_job_budget"):
        missing_job.validate_dispatch(job_type="live.sample", budget_cents=None)

    with pytest.raises(BudgetExceededError, match="per_job_budget_overrun"):
        missing_job.validate_dispatch(job_type="live.sample", budget_cents=101)

    missing_job.validate_dispatch(job_type="live.sample", budget_cents=100)


@pytest.mark.asyncio
async def test_budget_overrun_blocks_dispatch_and_rollup_fails_strict(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    policy = BudgetPolicy.live(run_budget_cents=50, per_job_budget_cents=100)
    with pytest.raises(BudgetExceededError, match="run_budget_overrun"):
        policy.validate_dispatch(job_type="live.sample", budget_cents=51)

    async with session_factory() as session:
        repository = JobRepository(session)
        job = await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload={"mode": "transient_error"},
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=30,
                max_retries=1,
                trace_id="trace-budget-001",
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
    worker = Worker(
        worker_id="worker-1",
        queue=queue,
        session_factory=session_factory,
        budget_policy=BudgetPolicy.stub(retry_budget=0),
    )

    assert await worker.process_one() is True

    async with session_factory() as session:
        status = await session.scalar(select(jobs_table.c.status))
        events = (
            await session.execute(
                select(job_events_table.c.event_type, job_events_table.c.event_data).order_by(
                    job_events_table.c.id.asc()
                )
            )
        ).all()
    assert status == "failed"
    assert [event.event_type for event in events] == ["submitted", "running", "budget_blocked"]
    assert events[-1].event_data["reason"] == "retry_budget_overrun"
    assert await queue.lease_jobs(consumer_name="assert-worker", block_ms=10) == []

    telemetry_path = tmp_path / "docs" / "ai_cost_telemetry.jsonl"
    report_path = tmp_path / "reports" / "ai_cost_rollup.md"
    append_jsonl(telemetry_path, _cost_record(cost="0.06"))
    result = CliRunner().invoke(
        cost_app,
        [
            "--input",
            str(telemetry_path),
            "--output",
            str(report_path),
            "--strict",
            "--max-total-cost",
            "0.05",
        ],
    )

    assert result.exit_code == 1
    assert "total cost $0.06 exceeds limit $0.05" in result.stderr
    assert "violation: total cost $0.06 exceeds limit $0.05" in report_path.read_text(
        encoding="utf-8"
    )
