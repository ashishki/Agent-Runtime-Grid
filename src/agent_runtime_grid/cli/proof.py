from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Annotated, Any
from uuid import UUID, uuid4

import typer
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from agent_runtime_grid.artifacts.store import ArtifactStore
from agent_runtime_grid.cli.benchmark import ReliabilityReport, render_reliability_report
from agent_runtime_grid.cli.smoke import build_smoke_report
from agent_runtime_grid.domain.jobs import JobSubmission
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.models import metadata
from agent_runtime_grid.storage.repositories import JobRepository
from agent_runtime_grid.worker.loop import Worker

DEFAULT_DATABASE_URL = (
    "postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:5432/agent_runtime_grid"
)
DEFAULT_REDIS_URL = "redis://localhost:6379/0"
DEFAULT_CANDIDATE_ID = "gdev-agent-local"

proof_app = typer.Typer()


class FullStackProofError(RuntimeError):
    pass


@dataclass(frozen=True)
class CrossProjectInputs:
    eval_lab_dataset_path: Path
    eval_lab_report_path: Path
    gdev_artifact_path: Path
    candidate_id: str


@dataclass(frozen=True)
class FullStackProofResult:
    run_id: UUID
    report_path: Path
    report: ReliabilityReport
    inputs: CrossProjectInputs
    selected_case_ids: tuple[str, ...]


async def run_full_stack_proof(
    *,
    session_factory: async_sessionmaker[AsyncSession],
    queue: RedisStreamsQueue,
    eval_lab_dataset_path: Path,
    eval_lab_report_path: Path,
    gdev_artifact_path: Path,
    jobs: int,
    workers: int,
    artifact_root: Path,
    report_path: Path,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
) -> FullStackProofResult:
    inputs = validate_cross_project_inputs(
        eval_lab_dataset_path=eval_lab_dataset_path,
        eval_lab_report_path=eval_lab_report_path,
        gdev_artifact_path=gdev_artifact_path,
        candidate_id=candidate_id,
    )
    cases = _load_eval_lab_cases(inputs.eval_lab_dataset_path, limit=jobs)
    if not cases:
        raise FullStackProofError("dataset contains no runnable cases")
    if workers <= 0:
        raise FullStackProofError("workers must be positive")

    run_id = uuid4()
    eval_result_dir = report_path.parent / "eval-results" / inputs.candidate_id
    async with session_factory() as session:
        repository = JobRepository(session)
        for case in cases:
            case_id = _case_id(case)
            request = _case_request(case)
            job = await repository.create_job(
                JobSubmission(
                    job_type="gdev_webhook_eval",
                    payload={
                        "case_id": case_id,
                        "candidate_id": inputs.candidate_id,
                        "mode": "stub",
                        "request": request,
                        "eval_result_path": str(eval_result_dir / f"{case_id}.json"),
                    },
                    idempotency_key=f"{run_id}:{case_id}",
                    timeout_seconds=30,
                    max_retries=1,
                    trace_id=f"trace-{run_id}",
                    run_id=run_id,
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

    artifact_store = ArtifactStore(artifact_root)
    worker_pool = [
        Worker(
            worker_id=f"full-stack-worker-{index + 1}",
            queue=queue,
            session_factory=session_factory,
            artifact_store=artifact_store,
        )
        for index in range(workers)
    ]
    while True:
        processed = await asyncio.gather(*(worker.process_one() for worker in worker_pool))
        if not any(processed):
            break

    report = await build_smoke_report(
        session_factory=session_factory,
        run_id=run_id,
        artifact_root=artifact_root,
        queue=queue,
        worker_count=workers,
    )
    report = replace(report, title="Full Stack Runtime Reliability")
    validate_full_stack_report(report=report, expected_jobs=len(cases))

    result = FullStackProofResult(
        run_id=run_id,
        report_path=report_path,
        report=report,
        inputs=inputs,
        selected_case_ids=tuple(_case_id(case) for case in cases),
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(render_full_stack_report(result), encoding="utf-8")
    return result


def validate_cross_project_inputs(
    *,
    eval_lab_dataset_path: Path,
    eval_lab_report_path: Path,
    gdev_artifact_path: Path,
    candidate_id: str,
) -> CrossProjectInputs:
    if not eval_lab_dataset_path.is_file():
        raise FullStackProofError(f"Eval Lab dataset not found: {eval_lab_dataset_path}")
    if not eval_lab_report_path.is_file():
        raise FullStackProofError(f"Eval Lab report not found: {eval_lab_report_path}")
    if not gdev_artifact_path.exists():
        raise FullStackProofError(f"gdev-agent artifact path not found: {gdev_artifact_path}")
    normalized_candidate_id = candidate_id.strip()
    if not normalized_candidate_id:
        raise FullStackProofError("candidate_id is required")
    return CrossProjectInputs(
        eval_lab_dataset_path=eval_lab_dataset_path,
        eval_lab_report_path=eval_lab_report_path,
        gdev_artifact_path=gdev_artifact_path,
        candidate_id=normalized_candidate_id,
    )


def validate_full_stack_report(*, report: ReliabilityReport, expected_jobs: int) -> None:
    errors: list[str] = []
    if report.submitted_jobs != expected_jobs:
        errors.append(f"submitted_jobs expected {expected_jobs}, got {report.submitted_jobs}")
    if report.lifecycle_counts.get("completed", 0) != expected_jobs:
        errors.append(
            f"completed_jobs expected {expected_jobs}, "
            f"got {report.lifecycle_counts.get('completed', 0)}"
        )
    if report.duplicate_finalization_count != 0:
        errors.append(f"duplicate finalization count is {report.duplicate_finalization_count}")
    if report.artifact_integrity is None:
        errors.append("artifact integrity summary missing")
    elif report.artifact_integrity.valid_count != expected_jobs:
        errors.append(
            f"valid artifacts expected {expected_jobs}, got {report.artifact_integrity.valid_count}"
        )
    if errors:
        raise FullStackProofError("; ".join(errors))


def render_full_stack_report(result: FullStackProofResult) -> str:
    input_paths = result.inputs
    lines = [
        "# Full Stack Runtime Proof",
        "",
        f"grid_run_id: {result.run_id}",
        f"candidate_id: {input_paths.candidate_id}",
        f"eval_lab_dataset_path: {input_paths.eval_lab_dataset_path}",
        f"eval_lab_report_path: {input_paths.eval_lab_report_path}",
        f"gdev_artifact_path: {input_paths.gdev_artifact_path}",
        f"selected_cases: {len(result.selected_case_ids)}",
        "",
        "## Cross-Project Links",
        "",
        f"- Eval Lab quality report: `{input_paths.eval_lab_report_path}`",
        f"- gdev-agent artifact path: `{input_paths.gdev_artifact_path}`",
        f"- Grid runtime report: `{result.report_path}`",
        f"- Grid run ID: `{result.run_id}`",
        "",
        "## Selected Cases",
        "",
    ]
    for case_id in result.selected_case_ids:
        lines.append(f"- `{case_id}`")
    lines.extend(
        [
            "",
            "## Runtime Reliability",
            "",
            render_reliability_report(result.report),
            "",
            "## Known Limits",
            "",
            "- This proof uses local deterministic Grid execution.",
            "- gdev-agent is represented through ready artifact paths and deterministic "
            "`gdev_webhook_eval` jobs.",
            "- No live model calls or non-local worker egress are enabled by default.",
        ]
    )
    return "\n".join(lines)


async def run_full_stack_from_urls(
    *,
    database_url: str = DEFAULT_DATABASE_URL,
    redis_url: str = DEFAULT_REDIS_URL,
    eval_lab_dataset_path: Path,
    eval_lab_report_path: Path,
    gdev_artifact_path: Path,
    jobs: int,
    workers: int,
    artifact_root: Path,
    report_path: Path,
    candidate_id: str = DEFAULT_CANDIDATE_ID,
    clean_state: bool = True,
) -> FullStackProofResult:
    engine = create_async_engine(database_url)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = Redis.from_url(redis_url, decode_responses=True)
    lock_connection = None
    suffix = uuid4().hex
    queue = RedisStreamsQueue(
        redis,
        stream_name=f"full-stack-jobs:{suffix}",
        consumer_group="full-stack-workers",
        dlq_stream_name=f"full-stack-jobs:{suffix}:dlq",
    )
    try:
        if clean_state:
            lock_connection = await engine.connect()
            await lock_connection.execute(text("SELECT pg_advisory_lock(7400)"))
            async with engine.begin() as connection:
                await connection.run_sync(metadata.drop_all)
                await connection.run_sync(metadata.create_all)

        return await run_full_stack_proof(
            session_factory=session_factory,
            queue=queue,
            eval_lab_dataset_path=eval_lab_dataset_path,
            eval_lab_report_path=eval_lab_report_path,
            gdev_artifact_path=gdev_artifact_path,
            jobs=jobs,
            workers=workers,
            artifact_root=artifact_root,
            report_path=report_path,
            candidate_id=candidate_id,
        )
    finally:
        if lock_connection is not None:
            await lock_connection.execute(text("SELECT pg_advisory_unlock(7400)"))
            await lock_connection.close()
        await redis.aclose()
        await engine.dispose()


@proof_app.command("full-stack")
def full_stack_command(
    eval_lab_dataset: Annotated[Path, typer.Option("--eval-lab-dataset")],
    eval_lab_report: Annotated[Path, typer.Option("--eval-lab-report")],
    gdev_artifact: Annotated[Path, typer.Option("--gdev-artifact")],
    jobs: Annotated[int, typer.Option("--jobs", min=1)] = 20,
    workers: Annotated[int, typer.Option("--workers", min=1)] = 4,
    candidate_id: Annotated[str, typer.Option("--candidate-id")] = DEFAULT_CANDIDATE_ID,
    artifact_root: Annotated[Path, typer.Option("--artifact-root")] = Path("artifacts/full-stack"),
    report_path: Annotated[Path, typer.Option("--report")] = Path(
        "reports/full-stack/runtime_report.md"
    ),
    database_url: Annotated[str, typer.Option("--database-url")] = DEFAULT_DATABASE_URL,
    redis_url: Annotated[str, typer.Option("--redis-url")] = DEFAULT_REDIS_URL,
) -> None:
    try:
        result = asyncio.run(
            run_full_stack_from_urls(
                database_url=database_url,
                redis_url=redis_url,
                eval_lab_dataset_path=eval_lab_dataset,
                eval_lab_report_path=eval_lab_report,
                gdev_artifact_path=gdev_artifact,
                jobs=jobs,
                workers=workers,
                candidate_id=candidate_id,
                artifact_root=artifact_root,
                report_path=report_path,
            )
        )
    except FullStackProofError as exc:
        typer.echo(f"full-stack proof failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"run_id: {result.run_id}")
    typer.echo(f"jobs: {result.report.submitted_jobs}")
    typer.echo(f"completed: {result.report.lifecycle_counts.get('completed', 0)}")
    typer.echo(f"report: {result.report_path}")


def _load_eval_lab_cases(dataset_path: Path, *, limit: int) -> list[dict[str, Any]]:
    if limit <= 0:
        raise FullStackProofError("jobs must be positive")
    cases: list[dict[str, Any]] = []
    for line_number, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise FullStackProofError(
                f"dataset line {line_number} is not valid JSON: {dataset_path}"
            ) from exc
        if not isinstance(case, dict):
            raise FullStackProofError(f"dataset line {line_number} is not a JSON object")
        cases.append(case)
        if len(cases) >= limit:
            break
    return cases


def _case_id(case: dict[str, Any]) -> str:
    case_id = str(case.get("id") or "").strip()
    if not case_id:
        raise FullStackProofError("dataset case is missing id")
    return case_id


def _case_request(case: dict[str, Any]) -> dict[str, Any]:
    input_value = case.get("input")
    if isinstance(input_value, dict):
        return dict(input_value)
    request = {
        "message_id": case.get("message_id") or _case_id(case),
        "tenant_slug": case.get("tenant_slug") or "synthetic-eval",
        "text": case.get("text") or "",
    }
    return {key: value for key, value in request.items() if value is not None}
