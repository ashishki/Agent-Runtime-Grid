import json

from agent_runtime_grid.observability.metrics import RuntimeMetrics
from agent_runtime_grid.observability.tracing import InMemoryTracer


def test_observability_excludes_secrets_and_payloads() -> None:
    tracer = InMemoryTracer()
    with tracer.span(
        trace_id="trace-safe-001",
        operation_name="job.execute",
        job_id="job-1",
        api_token="test-token",
        raw_payload={"message": "do-not-record"},
    ):
        pass

    rendered_spans = json.dumps([span.attributes for span in tracer.spans], sort_keys=True)
    rendered_metrics = RuntimeMetrics().render()

    assert "test-token" not in rendered_spans
    assert "do-not-record" not in rendered_spans
    assert "api_token" not in rendered_spans
    assert "raw_payload" not in rendered_spans
    assert "test-token" not in rendered_metrics
    assert "do-not-record" not in rendered_metrics
