from decimal import Decimal
from uuid import uuid4

from agent_runtime_grid.cost.rollup import write_cost_rollup_report
from agent_runtime_grid.cost.telemetry import (
    CostTelemetryLedger,
    CostTelemetryRecord,
    append_jsonl,
)


def _record(*, cost: str = "0.01", job_id: str | None = None) -> CostTelemetryRecord:
    return CostTelemetryRecord(
        project="agent-runtime-grid",
        run_id="run-1",
        job_id=job_id or str(uuid4()),
        job_type="live.sample",
        worker_id="worker-1",
        model="example-model",
        provider="example-provider",
        input_tokens=10,
        output_tokens=5,
        estimated_cost_usd=Decimal(cost),
        retry_count=1,
        environment="test",
    )


def test_live_job_records_required_cost_fields() -> None:
    record = _record()

    assert record.to_json_dict() == {
        "project": "agent-runtime-grid",
        "run_id": "run-1",
        "job_id": record.job_id,
        "job_type": "live.sample",
        "worker_id": "worker-1",
        "model": "example-model",
        "provider": "example-provider",
        "input_tokens": 10,
        "output_tokens": 5,
        "estimated_cost_usd": "0.01",
        "retry_count": 1,
        "environment": "test",
    }


def test_budget_overrun_blocks_live_dispatch() -> None:
    ledger = CostTelemetryLedger(run_budget_usd=Decimal("0.05"), max_model_calls=500)

    assert ledger.record_live_job(_record(cost="0.04", job_id="job-1")) is True
    assert ledger.record_live_job(_record(cost="0.02", job_id="job-2")) is False

    assert ledger.total_cost_usd == Decimal("0.04")
    assert len(ledger.budget_blocked_events) == 1
    assert ledger.budget_blocked_events[0].job_id == "job-2"
    assert ledger.budget_blocked_events[0].reason == "budget_overrun"


def test_cost_rollup_report_contains_run_and_job_totals(tmp_path) -> None:
    telemetry_path = tmp_path / "docs" / "ai_cost_telemetry.jsonl"
    report_path = tmp_path / "reports" / "ai_cost_rollup.md"
    append_jsonl(telemetry_path, _record(cost="0.01", job_id="job-1"))
    append_jsonl(telemetry_path, _record(cost="0.02", job_id="job-2"))

    write_cost_rollup_report(telemetry_path, report_path)

    report = report_path.read_text(encoding="utf-8")
    assert "# AI Cost Rollup" in report
    assert "`run-1`: $0.03" in report
    assert "`job-1`: $0.01" in report
    assert "`job-2`: $0.02" in report
