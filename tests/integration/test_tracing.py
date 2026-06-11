from uuid import uuid4

from agent_runtime_grid.observability.tracing import (
    JOB_TRACE_OPERATIONS,
    InMemoryTracer,
    record_job_lifecycle_trace,
)


def test_job_trace_links_runtime_spans() -> None:
    trace_id = "trace-observability-001"
    spans = record_job_lifecycle_trace(
        InMemoryTracer(),
        trace_id=trace_id,
        job_id=str(uuid4()),
        run_id=str(uuid4()),
    )

    assert [span.operation_name for span in spans] == list(JOB_TRACE_OPERATIONS)
    assert {span.trace_id for span in spans} == {trace_id}
    assert all("job_id" in span.attributes for span in spans)
    assert all("run_id" in span.attributes for span in spans)
