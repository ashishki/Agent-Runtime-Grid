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

from agent_runtime_grid.cli.proof import (
    FullStackProofError,
    run_full_stack_proof,
    validate_cross_project_inputs,
)
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
        stream_name=f"full-stack-proof-jobs:{suffix}",
        consumer_group="workers",
        dlq_stream_name=f"full-stack-proof-jobs:{suffix}:dlq",
    )


def _write_eval_lab_dataset(root: Path, *, count: int = 3) -> Path:
    dataset_path = root / "eval-lab" / "datasets" / "gdev_agent" / "triage_v1.jsonl"
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    for index in range(count):
        rows.append(
            {
                "id": f"gdev-billing-refund-{index + 1:03d}",
                "input": {
                    "tenant_slug": "test-tenant-a",
                    "message_id": f"eval-billing-refund-{index + 1:03d}",
                    "user_id": f"eval-user-{index + 1:03d}",
                    "text": f"I was charged twice for gems and want refund #{index + 1}.",
                    "api_token": "secret-value",
                },
                "expected": {"quality_status": "pass"},
                "metadata": {"source": "eval-lab-ready-artifact"},
            }
        )
    dataset_path.write_text(
        "\n".join(json.dumps(row, sort_keys=True) for row in rows) + "\n",
        encoding="utf-8",
    )
    return dataset_path


def _write_eval_lab_report(root: Path) -> Path:
    report_path = root / "eval-lab" / "reports" / "gdev-agent" / "baseline_report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# gdev-agent Baseline Quality Report\n\nquality_status: pass\n",
        encoding="utf-8",
    )
    return report_path


def _write_gdev_artifact(root: Path) -> Path:
    artifact_path = root / "gdev-agent" / "eval" / "results" / "last_run.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(
        json.dumps(
            {
                "candidate_id": "gdev-agent-local",
                "status": "completed",
                "artifact_count": 3,
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
    return artifact_path


def test_full_stack_proof_validates_cross_project_artifacts(tmp_path: Path) -> None:
    dataset_path = _write_eval_lab_dataset(tmp_path)
    eval_report_path = _write_eval_lab_report(tmp_path)
    gdev_artifact_path = _write_gdev_artifact(tmp_path)

    inputs = validate_cross_project_inputs(
        eval_lab_dataset_path=dataset_path,
        eval_lab_report_path=eval_report_path,
        gdev_artifact_path=gdev_artifact_path,
        candidate_id=" gdev-agent-local ",
    )

    assert inputs.eval_lab_dataset_path == dataset_path
    assert inputs.eval_lab_report_path == eval_report_path
    assert inputs.gdev_artifact_path == gdev_artifact_path
    assert inputs.candidate_id == "gdev-agent-local"

    with pytest.raises(FullStackProofError, match="Eval Lab dataset not found"):
        validate_cross_project_inputs(
            eval_lab_dataset_path=tmp_path / "missing.jsonl",
            eval_lab_report_path=eval_report_path,
            gdev_artifact_path=gdev_artifact_path,
            candidate_id="gdev-agent-local",
        )


@pytest.mark.asyncio
async def test_full_stack_proof_runs_cases_through_grid(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    dataset_path = _write_eval_lab_dataset(tmp_path)
    eval_report_path = _write_eval_lab_report(tmp_path)
    gdev_artifact_path = _write_gdev_artifact(tmp_path)
    report_path = tmp_path / "reports" / "full-stack" / "runtime_report.md"

    result = await run_full_stack_proof(
        session_factory=session_factory,
        queue=queue,
        eval_lab_dataset_path=dataset_path,
        eval_lab_report_path=eval_report_path,
        gdev_artifact_path=gdev_artifact_path,
        jobs=3,
        workers=2,
        artifact_root=tmp_path / "artifacts",
        report_path=report_path,
        candidate_id="gdev-agent-local",
    )

    assert result.report.submitted_jobs == 3
    assert result.report.lifecycle_counts["completed"] == 3
    assert result.report.duplicate_finalization_count == 0
    assert result.report.artifact_integrity is not None
    assert result.report.artifact_integrity.valid_count == 3
    assert result.report.estimated_cost_usd == 0
    assert report_path.is_file()

    for case_id in result.selected_case_ids:
        eval_result_path = (
            report_path.parent / "eval-results" / "gdev-agent-local" / f"{case_id}.json"
        )
        eval_result = json.loads(eval_result_path.read_text(encoding="utf-8"))
        assert eval_result["case_id"] == case_id
        assert eval_result["candidate_id"] == "gdev-agent-local"
        assert eval_result["quality_status"] == "pass"


@pytest.mark.asyncio
async def test_full_stack_report_cross_links_quality_and_runtime_evidence(
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    tmp_path: Path,
) -> None:
    dataset_path = _write_eval_lab_dataset(tmp_path)
    eval_report_path = _write_eval_lab_report(tmp_path)
    gdev_artifact_path = _write_gdev_artifact(tmp_path)
    report_path = tmp_path / "reports" / "full-stack" / "runtime_report.md"

    result = await run_full_stack_proof(
        session_factory=session_factory,
        queue=queue,
        eval_lab_dataset_path=dataset_path,
        eval_lab_report_path=eval_report_path,
        gdev_artifact_path=gdev_artifact_path,
        jobs=2,
        workers=2,
        artifact_root=tmp_path / "artifacts",
        report_path=report_path,
        candidate_id="gdev-agent-local",
    )
    rendered_report = report_path.read_text(encoding="utf-8")

    assert "# Full Stack Runtime Proof" in rendered_report
    assert f"grid_run_id: {result.run_id}" in rendered_report
    assert f"Eval Lab quality report: `{eval_report_path}`" in rendered_report
    assert f"gdev-agent artifact path: `{gdev_artifact_path}`" in rendered_report
    assert "## Runtime Reliability" in rendered_report
    assert "## artifact integrity" in rendered_report
    assert "## queue/backpressure" in rendered_report
    assert "duplicate_finalization_count == 0" in rendered_report
    assert "gdev-billing-refund-001" in rendered_report
    assert "secret-value" not in rendered_report
    assert "api_token" not in rendered_report
