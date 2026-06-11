from decimal import Decimal

import pytest

from agent_runtime_grid.jobs.failure_injection import (
    FailureMode,
    FailurePlan,
    payload_for_failure,
    should_retry,
    stub_cost_for_plan,
)
from agent_runtime_grid.jobs.stub import (
    PolicyValidationError,
    StubJobRunner,
    TransientRunnerError,
)


def test_fixed_seed_failure_plan_is_reproducible() -> None:
    first = FailurePlan.fixed_seed(seed=42, count=50)
    second = FailurePlan.fixed_seed(seed=42, count=50)

    assert first.counts() == second.counts()
    assert set(first.counts()) == set(FailureMode)
    assert sum(first.counts().values()) == 50


@pytest.mark.asyncio
async def test_injected_failure_classes_drive_retry_behavior() -> None:
    runner = StubJobRunner()

    assert should_retry(FailureMode.TRANSIENT) is True
    with pytest.raises(TransientRunnerError):
        await runner.run(payload_for_failure(FailureMode.TRANSIENT))

    assert should_retry(FailureMode.PERMANENT) is False
    with pytest.raises(PolicyValidationError):
        await runner.run(payload_for_failure(FailureMode.PERMANENT))


def test_stub_mode_records_zero_model_cost() -> None:
    plan = FailurePlan.fixed_seed(seed=7, count=25)

    cost = stub_cost_for_plan(plan)

    assert cost.model_calls == 0
    assert cost.estimated_cost_usd == Decimal("0")
