from __future__ import annotations

from dataclasses import dataclass

from agent_runtime_grid.queue.types import QueueJobMessage

STALE_LEASE_ERROR_CLASS = "StaleWorkerLeaseError"
STALE_LEASE_EXHAUSTED_ERROR_CLASS = "StaleLeaseExhaustedError"


@dataclass(frozen=True)
class StaleLease:
    message: QueueJobMessage
    consumer_name: str
    idle_ms: int
    delivery_count: int
