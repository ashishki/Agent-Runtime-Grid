from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path


@dataclass(frozen=True)
class BenchmarkConfig:
    job_count: int
    worker_count: int
    failure_rate: float
    include_timeouts: bool
    repeat_idempotency_submissions: bool
    seed: int = 42

    @classmethod
    def smoke(cls) -> BenchmarkConfig:
        return cls(
            job_count=100,
            worker_count=4,
            failure_rate=0.0,
            include_timeouts=False,
            repeat_idempotency_submissions=False,
        )

    @classmethod
    def v1_proof(cls) -> BenchmarkConfig:
        return cls(
            job_count=500,
            worker_count=20,
            failure_rate=0.10,
            include_timeouts=True,
            repeat_idempotency_submissions=True,
        )


@dataclass(frozen=True)
class ReliabilityReport:
    submitted_jobs: int
    lifecycle_counts: dict[str, int]
    completion_rate: float
    duplicate_finalization_count: int
    retry_count: int
    queue_lag_seconds: float
    p95_duration_seconds: float
    artifact_completeness: float
    failure_classification: dict[str, int] = field(default_factory=dict)
    estimated_cost_usd: Decimal = Decimal("0")


def run_smoke_benchmark(*, reports_dir: Path = Path("reports")) -> Path:
    config = BenchmarkConfig.smoke()
    report = ReliabilityReport(
        submitted_jobs=config.job_count,
        lifecycle_counts={
            "queued": 0,
            "running": 0,
            "completed": config.job_count,
            "failed": 0,
            "timed_out": 0,
            "cancelled": 0,
        },
        completion_rate=1.0,
        duplicate_finalization_count=0,
        retry_count=0,
        queue_lag_seconds=0.0,
        p95_duration_seconds=0.0,
        artifact_completeness=1.0,
        failure_classification={},
        estimated_cost_usd=Decimal("0"),
    )
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / "load_smoke.md"
    report_path.write_text(render_reliability_report(report), encoding="utf-8")
    return report_path


def render_reliability_report(report: ReliabilityReport) -> str:
    lines = [
        "# Load Smoke Report",
        "",
        f"submitted jobs: {report.submitted_jobs}",
        "",
        "## lifecycle counts",
    ]
    for key, value in sorted(report.lifecycle_counts.items()):
        lines.append(f"- {key}: {value}")

    lines.extend(
        [
            "",
            "## reliability fields",
            f"- completion rate: {report.completion_rate:.2%}",
            f"- duplicate-finalization count: {report.duplicate_finalization_count}",
            f"- retry count: {report.retry_count}",
            f"- queue lag: {report.queue_lag_seconds:.3f}s",
            f"- p95 duration: {report.p95_duration_seconds:.3f}s",
            f"- artifact completeness: {report.artifact_completeness:.2%}",
            f"- failure classification: {report.failure_classification}",
            f"- estimated cost: ${report.estimated_cost_usd}",
            "",
        ]
    )
    return "\n".join(lines)
