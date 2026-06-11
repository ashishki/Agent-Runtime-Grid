from decimal import Decimal

from agent_runtime_grid.cli.benchmark import (
    BenchmarkConfig,
    ReliabilityReport,
    render_reliability_report,
    run_smoke_benchmark,
)


def test_smoke_benchmark_writes_report(tmp_path) -> None:
    report_path = run_smoke_benchmark(reports_dir=tmp_path / "reports")

    report = report_path.read_text(encoding="utf-8")
    assert report_path.name == "load_smoke.md"
    assert "submitted jobs: 100" in report
    assert "- completed: 100" in report
    assert "p95 duration:" in report


def test_v1_proof_config_accepts_required_scenario() -> None:
    config = BenchmarkConfig.v1_proof()

    assert config.job_count == 500
    assert config.worker_count == 20
    assert config.failure_rate == 0.10
    assert config.include_timeouts is True
    assert config.repeat_idempotency_submissions is True


def test_report_contains_required_reliability_fields() -> None:
    report = render_reliability_report(
        ReliabilityReport(
            submitted_jobs=500,
            lifecycle_counts={"completed": 450, "failed": 50},
            completion_rate=0.9,
            duplicate_finalization_count=0,
            retry_count=12,
            queue_lag_seconds=0.25,
            p95_duration_seconds=1.5,
            artifact_completeness=0.98,
            failure_classification={"transient": 30, "permanent": 20},
            estimated_cost_usd=Decimal("0"),
        )
    )

    assert "completion rate:" in report
    assert "duplicate-finalization count:" in report
    assert "retry count:" in report
    assert "queue lag:" in report
    assert "p95 duration:" in report
    assert "artifact completeness:" in report
    assert "failure classification:" in report
    assert "estimated cost:" in report
