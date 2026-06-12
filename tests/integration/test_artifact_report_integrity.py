import hashlib
import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import (
    ArtifactIntegrityError,
    ArtifactStore,
    validate_artifact_integrity,
)
from agent_runtime_grid.cli.smoke import build_smoke_report, run_smoke
from agent_runtime_grid.domain.jobs import JobRecord, JobSubmission, payload_sha256
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import metadata
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
        stream_name=f"artifact-integrity-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"artifact-integrity-jobs:{suffix}:dlq",
    )


async def _create_job(session_factory: async_sessionmaker[AsyncSession]) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload={"message": "ok"},
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=30,
                max_retries=1,
                trace_id="trace-artifact-integrity-001",
            )
        )


async def _publish_job(queue: RedisStreamsQueue, job: JobRecord) -> None:
    await queue.publish_job(
        QueueJobMessage(
            job_id=str(job.id),
            run_id=str(job.run_id),
            attempt_number=1,
            trace_id=job.trace_id,
        )
    )


@pytest.mark.asyncio
async def test_artifact_metadata_contains_integrity_fields(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path: Path,
) -> None:
    job = await _create_job(session_factory)
    store = ArtifactStore(tmp_path / "artifacts")

    metadata_record = store.write_stub_job_artifact(
        job,
        worker_id="worker-1",
        attempt_number=1,
        result={"summary": "stub job completed"},
    )

    artifact = json.loads(metadata_record.path.read_text(encoding="utf-8"))
    artifact_bytes = metadata_record.path.read_bytes()
    metadata_dict = metadata_record.to_dict()

    assert metadata_dict["path"] == str(metadata_record.path)
    assert metadata_dict["size_bytes"] == len(artifact_bytes)
    assert metadata_dict["sha256"] == hashlib.sha256(artifact_bytes).hexdigest()
    assert metadata_dict["job_id"] == str(job.id)
    assert metadata_dict["run_id"] == str(job.run_id)
    assert metadata_dict["attempt_number"] == 1
    assert metadata_dict["input_digest"] == payload_sha256(job.payload)
    assert metadata_dict["created_at"] == metadata_record.created_at.isoformat()
    assert artifact["created_at"] == metadata_record.created_at.isoformat()
    validate_artifact_integrity(metadata_record)


@pytest.mark.asyncio
async def test_report_summarizes_artifact_integrity_from_metadata(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    result = await run_smoke(
        session_factory=session_factory,
        queue=queue,
        jobs=3,
        workers=2,
        failure_rate=0,
        mode="stub",
        artifact_root=tmp_path / "artifacts",
        report_path=tmp_path / "reports" / "smoke.md",
    )

    report = result.report_path.read_text(encoding="utf-8")

    assert result.report.artifact_integrity is not None
    assert result.report.artifact_integrity.checked_count == 3
    assert result.report.artifact_integrity.valid_count == 3
    assert "## artifact integrity" in report
    assert "- checked artifacts: 3" in report
    assert "- valid artifacts: 3" in report
    assert "job_id=" in report
    assert "run_id=" in report
    assert "attempt_number=1" in report
    assert "size_bytes=" in report
    assert "sha256=" in report
    assert "input_digest=" in report
    assert "created_at=" in report


@pytest.mark.asyncio
async def test_report_generation_fails_on_missing_or_mismatched_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    job = await _create_job(session_factory)
    artifact_root = tmp_path / "artifacts"
    await _publish_job(queue, job)
    worker = Worker(
        worker_id="worker-1",
        queue=queue,
        session_factory=session_factory,
        artifact_store=ArtifactStore(artifact_root),
    )
    assert await worker.process_one() is True

    artifact_path = next((artifact_root / str(job.id)).glob("*.json"))
    original_bytes = artifact_path.read_bytes()
    tampered_bytes = bytearray(original_bytes)
    tampered_bytes[tampered_bytes.index(ord("s"))] = ord("S")
    artifact_path.write_bytes(bytes(tampered_bytes))

    with pytest.raises(ArtifactIntegrityError, match="sha256 mismatch"):
        await build_smoke_report(
            session_factory=session_factory,
            run_id=job.run_id,
            artifact_root=artifact_root,
        )

    artifact_path.write_bytes(original_bytes)
    artifact_path.unlink()
    with pytest.raises(ArtifactIntegrityError, match="missing artifact"):
        await build_smoke_report(
            session_factory=session_factory,
            run_id=job.run_id,
            artifact_root=artifact_root,
        )
