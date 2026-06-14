import asyncio
import hashlib
import hmac
import json
import os
from collections.abc import AsyncIterator
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import ArtifactStore
from agent_runtime_grid.cli.benchmark import render_reliability_report
from agent_runtime_grid.cli.smoke import build_smoke_report
from agent_runtime_grid.cost.telemetry import BudgetPolicy, ProviderCallBlockedError
from agent_runtime_grid.domain.jobs import JobRecord, JobSubmission, payload_sha256
from agent_runtime_grid.jobs.gdev_agent import (
    GdevAgentPayloadError,
    LocalGdevHttpResponse,
    run_gdev_webhook_eval,
    validate_gdev_webhook_eval_payload,
)
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import metadata
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.worker.loop import Worker

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
LOCAL_GDEV_BASE_URL = "http://localhost:8000"


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
        stream_name=f"gdev-agent-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"gdev-agent-jobs:{suffix}:dlq",
    )


def _payload(index: int) -> dict[str, object]:
    case_id = f"gdev-case-{index:03d}"
    return {
        "case_id": case_id,
        "candidate_id": "gdev-agent-local",
        "mode": "stub",
        "request": {
            "message_id": f"message-{index:03d}",
            "tenant_slug": "tenant-a",
            "text": f"Customer asks about billing refund case {index:03d}.",
            "api_token": "test-token",
        },
        "eval_result_path": f"eval-results/gdev-agent-local/{case_id}.json",
    }


def _local_payload(tmp_path: Path) -> dict[str, object]:
    return {
        "case_id": "gdev-local-case-001",
        "candidate_id": "gdev-agent-local",
        "mode": "local",
        "request": {
            "message_id": "message-local-001",
            "tenant_slug": "test-tenant-a",
            "user_id": "eval-user-001",
            "text": "I was charged twice and need a refund review.",
            "api_token": "test-token",
        },
        "eval_result_path": str(tmp_path / "eval-results" / "gdev-local-case-001.json"),
        "gdev_base_url": LOCAL_GDEV_BASE_URL,
        "gdev_tenant_slug": "test-tenant-a",
        "gdev_tenant_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "gdev_webhook_secret_env": "GDEV_TEST_WEBHOOK_SECRET",
    }


async def _create_gdev_job(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    run_id: UUID,
    index: int,
) -> JobRecord:
    async with session_factory() as session:
        repository = JobRepository(session)
        return await repository.create_job(
            JobSubmission(
                job_type="gdev_webhook_eval",
                payload=_payload(index),
                idempotency_key=f"{run_id}:{index}",
                timeout_seconds=30,
                max_retries=1,
                trace_id=f"trace-{run_id}",
                run_id=run_id,
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


async def _process_all(
    *,
    queue: RedisStreamsQueue,
    session_factory: async_sessionmaker[AsyncSession],
    artifact_root: Path,
    workers: int,
) -> None:
    worker_pool = [
        Worker(
            worker_id=f"gdev-worker-{index + 1}",
            queue=queue,
            session_factory=session_factory,
            artifact_store=ArtifactStore(artifact_root),
        )
        for index in range(workers)
    ]
    while True:
        processed = await asyncio.gather(*(worker.process_one() for worker in worker_pool))
        if not any(processed):
            break


@pytest.mark.asyncio
async def test_gdev_batch_runs_without_paid_model_calls(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ProviderCallBlockedError):
        BudgetPolicy.stub().validate_provider_call()
    run_id = uuid4()
    for index in range(50):
        job = await _create_gdev_job(session_factory, run_id=run_id, index=index)
        await _publish_job(queue, job)

    await _process_all(
        queue=queue,
        session_factory=session_factory,
        artifact_root=tmp_path / "artifacts",
        workers=5,
    )
    report = await build_smoke_report(
        session_factory=session_factory,
        run_id=run_id,
        artifact_root=tmp_path / "artifacts",
        queue=queue,
        worker_count=5,
    )

    assert report.submitted_jobs == 50
    assert report.lifecycle_counts["completed"] == 50
    assert report.artifact_integrity is not None
    assert report.artifact_integrity.valid_count == 50
    assert report.estimated_cost_usd == Decimal("0")


@pytest.mark.asyncio
async def test_gdev_job_artifacts_include_runtime_and_response_evidence(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = uuid4()
    job = await _create_gdev_job(session_factory, run_id=run_id, index=1)
    await _publish_job(queue, job)

    await _process_all(
        queue=queue,
        session_factory=session_factory,
        artifact_root=tmp_path / "artifacts",
        workers=1,
    )

    artifact_path = next((tmp_path / "artifacts" / str(job.id)).glob("*.json"))
    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    expected_request_hash = payload_sha256(_payload(1)["request"])

    assert artifact["case_id"] == "gdev-case-001"
    assert artifact["request_hash"] == expected_request_hash
    assert "api_token" not in json.dumps(artifact)
    assert artifact["sanitized_response"]["category"] == "billing"
    assert artifact["normalized_fields"] == {
        "category": "billing",
        "requires_human": False,
        "expected_status": "executed",
    }
    assert artifact["runtime_status"] == "completed"
    assert artifact["attempt_count"] == 1
    assert artifact["runtime_attempts"] == 1
    assert artifact["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_gdev_runtime_and_eval_outputs_cross_link(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    monkeypatch.chdir(tmp_path)
    run_id = uuid4()
    job = await _create_gdev_job(session_factory, run_id=run_id, index=2)
    await _publish_job(queue, job)
    artifact_root = tmp_path / "artifacts"

    await _process_all(
        queue=queue,
        session_factory=session_factory,
        artifact_root=artifact_root,
        workers=1,
    )
    report = await build_smoke_report(
        session_factory=session_factory,
        run_id=run_id,
        artifact_root=artifact_root,
        queue=queue,
        worker_count=1,
    )
    rendered_report = render_reliability_report(report)
    artifact_path = next((artifact_root / str(job.id)).glob("*.json"))
    eval_result_path = tmp_path / "eval-results" / "gdev-agent-local" / "gdev-case-002.json"
    eval_result = json.loads(eval_result_path.read_text(encoding="utf-8"))

    assert "gdev-case-002" in artifact_path.read_text(encoding="utf-8")
    assert f"path={artifact_path}" in rendered_report
    assert "eval_result_path=eval-results/gdev-agent-local/gdev-case-002.json" in rendered_report
    assert eval_result["case_id"] == "gdev-case-002"
    assert eval_result["runtime_artifact_path"] == str(artifact_path)


@pytest.mark.asyncio
async def test_gdev_local_mode_posts_signed_webhook_without_raw_payload(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("GDEV_TEST_WEBHOOK_SECRET", "test-token")
    observed: dict[str, object] = {}

    def transport(
        url: str,
        body: bytes,
        headers: dict[str, str],
    ) -> LocalGdevHttpResponse:
        observed["url"] = url
        observed["body"] = body
        observed["headers"] = headers
        return LocalGdevHttpResponse(
            status_code=200,
            output={
                "status": "pending",
                "classification": {"category": "billing", "confidence": 0.92},
                "requires_human": True,
                "guard_blocked": False,
                "unsafe_auto_approval": False,
                "cost_usd": 0.0,
            },
        )

    result = await run_gdev_webhook_eval(
        _local_payload(tmp_path),
        attempt_number=1,
        transport=transport,
    )

    body = observed["body"]
    assert isinstance(body, bytes)
    headers = observed["headers"]
    assert isinstance(headers, dict)
    expected_signature = (
        "sha256="
        + hmac.new(
            b"test-token",
            body,
            hashlib.sha256,
        ).hexdigest()
    )
    webhook_payload = json.loads(body.decode("utf-8"))
    eval_result_path = tmp_path / "eval-results" / "gdev-local-case-001.json"
    eval_result = json.loads(eval_result_path.read_text(encoding="utf-8"))
    rendered_evidence = json.dumps(result, sort_keys=True) + json.dumps(
        eval_result,
        sort_keys=True,
    )

    assert observed["url"] == f"{LOCAL_GDEV_BASE_URL}/webhook"
    assert headers["X-Tenant-Slug"] == "test-tenant-a"
    assert headers["X-Webhook-Signature"] == expected_signature
    assert webhook_payload["tenant_id"] == "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"
    assert webhook_payload["metadata"]["eval_case_id"] == "gdev-local-case-001"
    assert result["quality_status"] == "pass"
    assert eval_result["sanitized_response"]["category"] == "billing"
    assert eval_result["normalized_fields"]["requires_human"] is True
    assert "test-token" not in rendered_evidence
    assert "api_token" not in rendered_evidence
    assert "I was charged twice" not in rendered_evidence


def test_gdev_local_mode_rejects_non_local_base_url(tmp_path: Path) -> None:
    payload = _local_payload(tmp_path)
    payload["gdev_base_url"] = "https://example.com"

    with pytest.raises(GdevAgentPayloadError, match="localhost|loopback|http"):
        validate_gdev_webhook_eval_payload(payload)
