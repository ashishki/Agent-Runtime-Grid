from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_routine_contract_declares_required_runtime_boundaries() -> None:
    text = (REPO_ROOT / "docs" / "AUTONOMOUS_ROUTINE_CONTRACT.md").read_text(encoding="utf-8")

    for required in (
        "routine_name",
        "trigger_type",
        "idempotency_key",
        "secret_refs",
        "retry_policy",
        "timeout_seconds",
        "fallback_policy",
        "budget_policy",
        "monitoring_signals",
        "disable_switch",
    ):
        assert required in text


def test_trigger_security_declares_webhook_and_event_controls() -> None:
    text = (REPO_ROOT / "docs" / "TRIGGER_SECURITY.md").read_text(encoding="utf-8")

    for required in (
        "HMAC/signature",
        "replay protection",
        "idempotency key",
        "payload size limit",
        "secret references",
    ):
        assert required in text


def test_routine_reliability_report_contract_names_operational_metrics() -> None:
    text = (REPO_ROOT / "docs" / "evidence" / "routine-reliability-report.md").read_text(
        encoding="utf-8"
    )

    for required in (
        "success rate",
        "retry rate",
        "timeout rate",
        "DLQ rate",
        "cost per completed job",
        "p95 queue delay",
        "p95 runtime",
        "artifact integrity",
    ):
        assert required in text
