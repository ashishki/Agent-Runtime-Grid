import os
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.domain.jobs import IdempotencyConflictError, JobSubmission
from agent_runtime_grid.storage.models import job_events_table, jobs_table, metadata
from agent_runtime_grid.storage.repositories import JobRepository

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)


@pytest_asyncio.fixture
async def session() -> AsyncIterator[AsyncSession]:
    engine = create_async_engine(os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL))
    lock_connection = await engine.connect()
    await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))

    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
            await connection.run_sync(metadata.create_all)

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        async with session_factory() as test_session:
            yield test_session

        async with engine.begin() as connection:
            await connection.run_sync(metadata.drop_all)
    finally:
        await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
        await lock_connection.close()
        await engine.dispose()


def _submission(
    *,
    idempotency_key: str = "job-key-1",
    payload: dict[str, object] | None = None,
) -> JobSubmission:
    return JobSubmission(
        job_type="stub.echo",
        payload=payload or {"message": "hello"},
        idempotency_key=idempotency_key,
        timeout_seconds=30,
        max_retries=2,
        trace_id="trace-001",
    )


@pytest.mark.asyncio
async def test_create_job_records_submitted_event(session: AsyncSession) -> None:
    repository = JobRepository(session)

    job = await repository.create_job(_submission())

    persisted_jobs = (await session.execute(select(jobs_table))).mappings().all()
    persisted_events = (await session.execute(select(job_events_table))).mappings().all()

    assert len(persisted_jobs) == 1
    assert persisted_jobs[0]["id"] == job.id
    assert persisted_jobs[0]["run_id"] == job.run_id
    assert persisted_jobs[0]["idempotency_key"] == "job-key-1"
    assert persisted_jobs[0]["timeout_seconds"] == 30
    assert persisted_jobs[0]["max_retries"] == 2
    assert persisted_jobs[0]["trace_id"] == "trace-001"

    assert len(persisted_events) == 1
    event = persisted_events[0]
    assert event["job_id"] == job.id
    assert event["run_id"] == job.run_id
    assert event["event_type"] == "submitted"
    assert event["trace_id"] == "trace-001"
    assert event["event_data"] == {
        "idempotency_key": "job-key-1",
        "timeout_seconds": 30,
        "max_retries": 2,
    }


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_returns_existing_job(session: AsyncSession) -> None:
    repository = JobRepository(session)

    first_job = await repository.create_job(_submission(idempotency_key="same-key"))
    second_job = await repository.create_job(_submission(idempotency_key="same-key"))

    job_count = await session.scalar(select(func.count()).select_from(jobs_table))
    event_count = await session.scalar(select(func.count()).select_from(job_events_table))

    assert second_job.id == first_job.id
    assert job_count == 1
    assert event_count == 1


@pytest.mark.asyncio
async def test_idempotency_key_payload_conflict_is_rejected(session: AsyncSession) -> None:
    repository = JobRepository(session)

    await repository.create_job(_submission(idempotency_key="conflict-key"))

    with pytest.raises(IdempotencyConflictError, match="conflict-key"):
        await repository.create_job(
            _submission(
                idempotency_key="conflict-key",
                payload={"message": "different"},
            )
        )

    job_count = await session.scalar(select(func.count()).select_from(jobs_table))
    event_count = await session.scalar(select(func.count()).select_from(job_events_table))

    assert job_count == 1
    assert event_count == 1
