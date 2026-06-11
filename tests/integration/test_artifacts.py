import hashlib
import json
import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import ArtifactStore
from agent_runtime_grid.domain.jobs import JobSubmission, payload_sha256
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
        stream_name=f"artifact-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"artifact-jobs:{suffix}:dlq",
    )


async def _create_job(session_factory: async_sessionmaker[AsyncSession]):
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="stub.echo",
                payload={"message": "ok"},
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=30,
                max_retries=1,
                trace_id="trace-artifact-001",
            )
        )


@pytest.mark.asyncio
async def test_stub_job_writes_json_artifact(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path,
) -> None:
    job = await _create_job(session_factory)
    await queue.publish_job(
        QueueJobMessage(
            job_id=str(job.id),
            run_id=str(job.run_id),
            attempt_number=1,
            trace_id=job.trace_id,
        )
    )
    store = ArtifactStore(tmp_path / "artifacts")
    worker = Worker(
        worker_id="worker-1",
        queue=queue,
        session_factory=session_factory,
        artifact_store=store,
    )

    assert await worker.process_one() is True

    artifact_paths = list((tmp_path / "artifacts" / str(job.id)).glob("*.json"))
    assert len(artifact_paths) == 1
    artifact = json.loads(artifact_paths[0].read_text(encoding="utf-8"))
    assert artifact["input_digest"] == payload_sha256(job.payload)
    assert artifact["worker_id"] == "worker-1"
    assert artifact["attempt_number"] == 1
    assert artifact["result_summary"] == "stub job completed"
    assert "message" not in json.dumps(artifact)


@pytest.mark.asyncio
async def test_artifact_metadata_records_hash_and_size(
    session_factory: async_sessionmaker[AsyncSession],
    tmp_path,
) -> None:
    job = await _create_job(session_factory)
    store = ArtifactStore(tmp_path / "artifacts")

    metadata_record = store.write_stub_job_artifact(
        job,
        worker_id="worker-1",
        attempt_number=1,
        result={"summary": "stub job completed"},
    )

    artifact_bytes = metadata_record.path.read_bytes()
    assert metadata_record.path.exists()
    assert metadata_record.size_bytes == len(artifact_bytes)
    assert metadata_record.sha256 == hashlib.sha256(artifact_bytes).hexdigest()
    assert metadata_record.job_id == str(job.id)
    assert metadata_record.created_at.tzinfo is not None
