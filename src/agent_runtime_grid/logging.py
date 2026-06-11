from __future__ import annotations

from typing import Any

SECRET_FIELD_PARTS = ("token", "secret", "password", "credential", "api_key", "key")


def job_log_record(
    *,
    job_id: str,
    run_id: str,
    worker_id: str,
    trace_id: str,
    event_type: str,
    error_class: str | None = None,
    **fields: Any,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "job_id": job_id,
        "run_id": run_id,
        "worker_id": worker_id,
        "trace_id": trace_id,
        "event_type": event_type,
    }
    if error_class is not None:
        record["error_class"] = sanitize_error_class(error_class)

    for key, value in fields.items():
        if _is_secret_like_field(key):
            continue
        record[key] = value

    return record


def sanitize_error_class(error_class: str) -> str:
    if not error_class or not error_class.replace("_", "").replace(".", "").isalnum():
        return "SanitizedError"
    return error_class


def _is_secret_like_field(key: str) -> bool:
    normalized = key.lower()
    return any(part in normalized for part in SECRET_FIELD_PARTS)
