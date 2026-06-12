import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.cli.benchmark import run_reliability_proof
from agent_runtime_grid.cli.smoke import run_smoke
from agent_runtime_grid.jobs.failure_injection import FailureMode
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.storage.models import metadata

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
        stream_name=f"proof-test-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"proof-test-jobs:{suffix}:dlq",
    )


@pytest.mark.asyncio
async def test_v1_proof_runs_against_runtime_state(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    result = await run_reliability_proof(
        session_factory=session_factory,
        queue=queue,
        jobs=500,
        workers=20,
        failure_rate=0.10,
        include_timeouts=True,
        repeat_idempotency_submissions=True,
        artifact_root=tmp_path / "artifacts",
        report_path=tmp_path / "reports" / "v1" / "reliability_report.md",
    )

    terminal_count = sum(
        result.report.lifecycle_counts[status]
        for status in ("completed", "failed", "timed_out", "cancelled")
    )

    assert result.report.submitted_jobs == 500
    assert terminal_count == 500
    assert result.report.injected_failure_count == 50
    assert result.report.retry_count > 0
    assert result.report.lifecycle_counts["timed_out"] > 0
    assert result.report.idempotency_replay_count > 0
    assert result.report.estimated_cost_usd == 0
    assert result.report_path.is_file()


@pytest.mark.asyncio
async def test_v1_report_contains_required_runtime_evidence(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    result = await run_reliability_proof(
        session_factory=session_factory,
        queue=queue,
        jobs=40,
        workers=8,
        failure_rate=0.20,
        include_timeouts=True,
        repeat_idempotency_submissions=True,
        artifact_root=tmp_path / "artifacts",
        report_path=tmp_path / "reports" / "v1" / "reliability_report.md",
    )

    report = result.report_path.read_text(encoding="utf-8")

    assert "# V1 Reliability Proof Report" in report
    assert "submitted_jobs:" in report
    assert "## lifecycle counts" in report
    assert "completion rate:" in report
    assert "retry count:" in report
    assert "timeout count:" in report
    assert "DLQ count:" in report
    assert "queue lag p95:" in report
    assert "execution duration p95:" in report
    assert "artifact completeness:" in report
    assert "estimated cost:" in report
    assert "failure classification:" in report
    assert "idempotency proof:" in report


@pytest.mark.asyncio
async def test_v1_proof_records_zero_duplicate_finalizations(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    result = await run_reliability_proof(
        session_factory=session_factory,
        queue=queue,
        jobs=40,
        workers=8,
        failure_rate=0.20,
        include_timeouts=True,
        repeat_idempotency_submissions=True,
        artifact_root=tmp_path / "artifacts",
        report_path=tmp_path / "reports" / "v1" / "reliability_report.md",
    )

    assert result.failure_plan.counts()[FailureMode.DUPLICATE_SUBMISSION] > 0
    assert result.report.idempotency_replay_count > 0
    assert result.report.duplicate_finalization_count == 0
    assert "duplicate_finalization_count == 0" in result.report_path.read_text(encoding="utf-8")


@pytest.mark.asyncio
async def test_reports_include_backpressure_section(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    smoke_result = await run_smoke(
        session_factory=session_factory,
        queue=queue,
        jobs=5,
        workers=2,
        failure_rate=0,
        mode="stub",
        artifact_root=tmp_path / "smoke-artifacts",
        report_path=tmp_path / "reports" / "smoke.md",
    )
    proof_result = await run_reliability_proof(
        session_factory=session_factory,
        queue=queue,
        jobs=20,
        workers=4,
        failure_rate=0.20,
        include_timeouts=True,
        repeat_idempotency_submissions=True,
        artifact_root=tmp_path / "proof-artifacts",
        report_path=tmp_path / "reports" / "v1" / "reliability_report.md",
    )

    smoke_report = smoke_result.report_path.read_text(encoding="utf-8")
    proof_report = proof_result.report_path.read_text(encoding="utf-8")

    for report in (smoke_report, proof_report):
        assert "## queue/backpressure" in report
        assert "p95 queue wait seconds:" in report
        assert "p95 execution seconds:" in report
