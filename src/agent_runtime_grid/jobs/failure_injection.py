from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum
from typing import Any


class FailureMode(StrEnum):
    TRANSIENT = "transient"
    PERMANENT = "permanent"
    TIMEOUT = "timeout"
    CANCELLATION = "cancellation"
    DUPLICATE_SUBMISSION = "duplicate_submission"


@dataclass(frozen=True)
class InjectedFailure:
    index: int
    mode: FailureMode


@dataclass(frozen=True)
class FailurePlan:
    seed: int
    failures: tuple[InjectedFailure, ...]

    @classmethod
    def fixed_seed(cls, *, seed: int, count: int) -> FailurePlan:
        rng = random.Random(seed)
        modes = list(FailureMode)
        failures = tuple(
            InjectedFailure(index=index, mode=rng.choice(modes)) for index in range(count)
        )
        return cls(seed=seed, failures=failures)

    @classmethod
    def reliability_proof(
        cls,
        *,
        seed: int,
        count: int,
        include_timeouts: bool,
    ) -> FailurePlan:
        modes = [
            FailureMode.TRANSIENT,
            FailureMode.PERMANENT,
            FailureMode.DUPLICATE_SUBMISSION,
        ]
        if include_timeouts:
            modes.append(FailureMode.TIMEOUT)

        indexes = list(range(count))
        random.Random(seed).shuffle(indexes)
        failures = tuple(
            InjectedFailure(index=index, mode=modes[position % len(modes)])
            for position, index in enumerate(indexes)
        )
        return cls(seed=seed, failures=tuple(sorted(failures, key=lambda failure: failure.index)))

    def counts(self) -> dict[FailureMode, int]:
        counted = Counter(failure.mode for failure in self.failures)
        return {mode: counted.get(mode, 0) for mode in FailureMode}


@dataclass(frozen=True)
class StubCostRecord:
    model_calls: int
    estimated_cost_usd: Decimal


def payload_for_failure(mode: FailureMode) -> dict[str, Any]:
    if mode is FailureMode.TRANSIENT:
        return {"mode": "transient_error"}
    if mode is FailureMode.PERMANENT:
        return {"mode": "permanent_error"}
    if mode is FailureMode.TIMEOUT:
        return {"mode": "sleep", "duration_seconds": 2}
    if mode is FailureMode.CANCELLATION:
        return {"mode": "sleep", "duration_seconds": 5}
    if mode is FailureMode.DUPLICATE_SUBMISSION:
        return {"mode": "success", "duplicate_submission": True}
    raise ValueError(f"unsupported failure mode: {mode}")


def should_retry(mode: FailureMode) -> bool:
    return mode is FailureMode.TRANSIENT


def stub_cost_for_plan(plan: FailurePlan) -> StubCostRecord:
    return StubCostRecord(model_calls=0, estimated_cost_usd=Decimal("0"))
