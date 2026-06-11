from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

SECRET_ATTRIBUTE_PARTS = ("token", "secret", "password", "credential", "api_key", "key")
RAW_PAYLOAD_ATTRIBUTE_PARTS = ("payload", "prompt", "response_body")

JOB_TRACE_OPERATIONS = (
    "api.submit",
    "queue.publish",
    "worker.lease",
    "job.execute",
    "artifact.write",
    "job.finalize",
)


@dataclass(frozen=True)
class SpanRecord:
    trace_id: str
    operation_name: str
    attributes: dict[str, Any]


class InMemoryTracer:
    def __init__(self) -> None:
        self.spans: list[SpanRecord] = []

    @contextmanager
    def span(self, *, trace_id: str, operation_name: str, **attributes: Any):
        sanitized = sanitize_span_attributes(attributes)
        try:
            yield
        finally:
            self.spans.append(
                SpanRecord(
                    trace_id=trace_id,
                    operation_name=operation_name,
                    attributes=sanitized,
                )
            )


def record_job_lifecycle_trace(
    tracer: InMemoryTracer,
    *,
    trace_id: str,
    job_id: str,
    run_id: str,
) -> list[SpanRecord]:
    for operation_name in JOB_TRACE_OPERATIONS:
        with tracer.span(
            trace_id=trace_id,
            operation_name=operation_name,
            job_id=job_id,
            run_id=run_id,
        ):
            pass
    return tracer.spans


def sanitize_span_attributes(attributes: dict[str, Any]) -> dict[str, Any]:
    sanitized: dict[str, Any] = {}
    for key, value in attributes.items():
        normalized = key.lower()
        if any(part in normalized for part in SECRET_ATTRIBUTE_PARTS):
            continue
        if any(part in normalized for part in RAW_PAYLOAD_ATTRIBUTE_PARTS):
            continue
        sanitized[key] = value
    return sanitized
