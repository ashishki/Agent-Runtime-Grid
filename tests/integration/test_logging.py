import json
from uuid import uuid4

from agent_runtime_grid.logging import job_log_record


def test_job_logs_are_structured_and_sanitized() -> None:
    record = job_log_record(
        job_id=str(uuid4()),
        run_id=str(uuid4()),
        worker_id="worker-1",
        trace_id="trace-log-001",
        event_type="failed",
        error_class="PolicyValidationError",
        api_token="test-token",
        safe_count=1,
    )

    assert {
        "job_id",
        "run_id",
        "worker_id",
        "trace_id",
        "event_type",
        "error_class",
    } <= set(record)
    assert record["error_class"] == "PolicyValidationError"
    assert record["safe_count"] == 1
    assert "api_token" not in record
    assert "test-token" not in json.dumps(record)

    sanitized = job_log_record(
        job_id=str(uuid4()),
        run_id=str(uuid4()),
        worker_id="worker-1",
        trace_id="trace-log-002",
        event_type="failed",
        error_class="PolicyValidationError token=test-token",
    )
    assert sanitized["error_class"] == "SanitizedError"
