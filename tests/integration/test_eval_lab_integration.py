import json
import os
from collections.abc import AsyncIterator
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import ArtifactStore
from agent_runtime_grid.cli.benchmark import render_reliability_report
from agent_runtime_grid.cli.smoke import build_smoke_report
from agent_runtime_grid.domain.jobs import JobRecord, JobSubmission
from agent_runtime_grid.jobs.eval_lab import validate_eval_lab_case_payload
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import job_events_table, metadata
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
        stream_name=f"eval-lab-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"eval-lab-jobs:{suffix}:dlq",
    )


def _write_dataset(root: Path) -> Path:
    dataset_path = root / "datasets" / "eval-lab" / "cases.jsonl"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    dataset_path.write_text(
        json.dumps(
            {
                "id": "case-1",
                "input": {"text": "classify this synthetic case"},
                "expected": {"quality_status": "pass"},
                "metadata": {"synthetic": True},
            },
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return dataset_path


async def _create_eval_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    payload: dict[str, object],
) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="eval_lab_case",
                payload=payload,
                idempotency_key=f"job-key-{uuid4().hex}",
                timeout_seconds=30,
                max_retries=1,
                trace_id="trace-eval-lab-001",
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


def _payload() -> dict[str, object]:
    return {
        "dataset_path": "datasets/eval-lab/cases.jsonl",
        "case_id": "case-1",
        "candidate_id": "candidate-local",
        "mode": "stub",
        "eval_result_path": "eval-results/candidate-local/case-1.json",
    }


def test_eval_lab_case_payload_is_validated_without_hardcoded_paths() -> None:
    payload = validate_eval_lab_case_payload(_payload())

    assert payload.dataset_path == Path("datasets/eval-lab/cases.jsonl")
    assert payload.eval_result_path == Path("eval-results/candidate-local/case-1.json")
    assert payload.case_id == "case-1"
    assert payload.candidate_id == "candidate-local"
    assert payload.mode == "stub"
    assert not payload.dataset_path.is_absolute()
    assert "/home/" not in str(payload.dataset_path)


@pytest.mark.asyncio
async def test_eval_lab_case_runs_and_writes_cross_linked_artifact(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_dataset(tmp_path)
    job = await _create_eval_job(session_factory, payload=_payload())
    await _publish_job(queue, job)
    worker = Worker(
        worker_id="worker-1",
        queue=queue,
        session_factory=session_factory,
        artifact_store=ArtifactStore(tmp_path / "artifacts"),
    )

    assert await worker.process_one() is True

    artifact_path = next((tmp_path / "artifacts" / str(job.id)).glob("*.json"))
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    eval_result = json.loads(
        (tmp_path / "eval-results" / "candidate-local" / "case-1.json").read_text(encoding="utf-8")
    )
    async with session_factory() as session:
        events = (
            await session.execute(
                select(job_events_table.c.event_type).order_by(job_events_table.c.id.asc())
            )
        ).all()

    assert [event.event_type for event in events] == ["submitted", "running", "completed"]
    assert artifact["case_id"] == "case-1"
    assert artifact["status"] == "completed"
    assert artifact["runtime_status"] == "completed"
    assert artifact["eval_result_path"] == "eval-results/candidate-local/case-1.json"
    assert artifact["quality_status"] == "pass"
    assert artifact["runtime_attempts"] == 1
    assert artifact["attempt_count"] == 1
    assert artifact["latency_ms"] >= 0
    assert eval_result["runtime_artifact_path"] == f"artifact://{job.id}/{artifact_path.name}"


@pytest.mark.asyncio
async def test_runtime_and_eval_reports_cross_link_without_fixed_checkout(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    _write_dataset(tmp_path)
    job = await _create_eval_job(session_factory, payload=_payload())
    await _publish_job(queue, job)
    artifact_root = tmp_path / "artifacts"
    worker = Worker(
        worker_id="worker-1",
        queue=queue,
        session_factory=session_factory,
        artifact_store=ArtifactStore(artifact_root),
    )
    assert await worker.process_one() is True

    report = await build_smoke_report(
        session_factory=session_factory,
        run_id=job.run_id,
        artifact_root=artifact_root,
        queue=queue,
        worker_count=1,
    )
    rendered_report = render_reliability_report(report)
    artifact_path = next((artifact_root / str(job.id)).glob("*.json"))
    eval_result_path = tmp_path / "eval-results" / "candidate-local" / "case-1.json"
    eval_result = json.loads(eval_result_path.read_text(encoding="utf-8"))

    assert f"path=artifact://{job.id}/{artifact_path.name}" in rendered_report
    assert "eval_result_path=eval-results/candidate-local/case-1.json" in rendered_report
    assert eval_result["runtime_artifact_path"] == f"artifact://{job.id}/{artifact_path.name}"
    assert "/home/ashishki/Documents/dev/ai-stack/projects/Eval-Ground-Truth-Lab" not in (
        rendered_report + json.dumps(eval_result, sort_keys=True)
    )
