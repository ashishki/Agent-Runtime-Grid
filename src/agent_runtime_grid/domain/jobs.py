from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


def canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def payload_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256(canonical_payload(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class JobSubmission:
    job_type: str
    payload: dict[str, Any]
    idempotency_key: str
    timeout_seconds: int
    max_retries: int
    trace_id: str
    budget_cents: int | None = None
    job_id: UUID = field(default_factory=uuid4)
    run_id: UUID = field(default_factory=uuid4)

    @property
    def payload_hash(self) -> str:
        return payload_sha256(self.payload)


@dataclass(frozen=True)
class JobRecord:
    id: UUID
    run_id: UUID
    job_type: str
    payload: dict[str, Any]
    payload_hash: str
    idempotency_key: str
    status: str
    timeout_seconds: int
    max_retries: int
    trace_id: str
    budget_cents: int | None
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class JobEventRecord:
    id: int
    job_id: UUID
    run_id: UUID
    event_type: str
    event_data: dict[str, Any]
    trace_id: str
    created_at: datetime


class IdempotencyConflictError(ValueError):
    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"idempotency key {idempotency_key!r} already exists for a different payload"
        )
        self.idempotency_key = idempotency_key
