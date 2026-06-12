from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from agent_runtime_grid.domain.jobs import JobRecord


class BudgetPolicyError(RuntimeError):
    def __init__(
        self,
        *,
        reason: str,
        attempted_cost_usd: Decimal = Decimal("0"),
        budget_limit_usd: Decimal = Decimal("0"),
    ) -> None:
        self.reason = reason
        self.attempted_cost_usd = attempted_cost_usd
        self.budget_limit_usd = budget_limit_usd
        super().__init__(reason)


class ProviderCallBlockedError(BudgetPolicyError):
    pass


class LiveBudgetRequiredError(BudgetPolicyError):
    pass


class BudgetExceededError(BudgetPolicyError):
    pass


@dataclass(frozen=True)
class BudgetPolicy:
    mode: str = "stub"
    run_budget_cents: int | None = None
    per_job_budget_cents: int | None = None
    retry_budget: int = 2
    max_model_calls: int = 0

    @classmethod
    def stub(cls, *, retry_budget: int = 2) -> BudgetPolicy:
        return cls(
            mode="stub",
            run_budget_cents=0,
            per_job_budget_cents=0,
            retry_budget=retry_budget,
            max_model_calls=0,
        )

    @classmethod
    def live(
        cls,
        *,
        run_budget_cents: int | None = None,
        per_job_budget_cents: int | None = None,
        retry_budget: int = 2,
        max_model_calls: int = 500,
    ) -> BudgetPolicy:
        return cls(
            mode="live",
            run_budget_cents=run_budget_cents,
            per_job_budget_cents=per_job_budget_cents,
            retry_budget=retry_budget,
            max_model_calls=max_model_calls,
        )

    def validate_provider_call(self) -> None:
        if self.mode == "stub":
            raise ProviderCallBlockedError(reason="stub_provider_call_blocked")

    def validate_job_dispatch(self, job: JobRecord) -> None:
        self.validate_dispatch(job_type=job.job_type, budget_cents=job.budget_cents)

    def validate_dispatch(self, *, job_type: str, budget_cents: int | None) -> None:
        if self.mode == "stub":
            if job_type.startswith("live."):
                raise ProviderCallBlockedError(reason="stub_live_job_blocked")
            return

        if self.mode != "live":
            raise BudgetPolicyError(reason=f"unsupported_budget_mode:{self.mode}")
        if self.run_budget_cents is None or self.per_job_budget_cents is None:
            raise LiveBudgetRequiredError(reason="missing_live_run_or_job_budget")
        if budget_cents is None:
            raise LiveBudgetRequiredError(reason="missing_job_budget")
        if budget_cents > self.per_job_budget_cents:
            raise BudgetExceededError(
                reason="per_job_budget_overrun",
                attempted_cost_usd=_cents_to_usd(budget_cents),
                budget_limit_usd=_cents_to_usd(self.per_job_budget_cents),
            )
        if budget_cents > self.run_budget_cents:
            raise BudgetExceededError(
                reason="run_budget_overrun",
                attempted_cost_usd=_cents_to_usd(budget_cents),
                budget_limit_usd=_cents_to_usd(self.run_budget_cents),
            )

    def validate_retry(self, *, next_attempt_number: int) -> None:
        retry_count_after_projection = next_attempt_number - 1
        if retry_count_after_projection > self.retry_budget:
            raise BudgetExceededError(
                reason="retry_budget_overrun",
                attempted_cost_usd=Decimal("0"),
                budget_limit_usd=Decimal("0"),
            )


@dataclass(frozen=True)
class CostTelemetryRecord:
    project: str
    run_id: str
    job_id: str
    job_type: str
    worker_id: str
    model: str
    provider: str
    input_tokens: int
    output_tokens: int
    estimated_cost_usd: Decimal
    retry_count: int
    environment: str

    def to_json_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["estimated_cost_usd"] = str(self.estimated_cost_usd)
        return data


@dataclass(frozen=True)
class BudgetBlockedEvent:
    run_id: str
    job_id: str
    reason: str
    attempted_cost_usd: Decimal
    budget_limit_usd: Decimal

    def to_json_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "job_id": self.job_id,
            "reason": self.reason,
            "attempted_cost_usd": str(self.attempted_cost_usd),
            "budget_limit_usd": str(self.budget_limit_usd),
        }


class CostTelemetryLedger:
    def __init__(
        self,
        *,
        run_budget_usd: Decimal,
        max_model_calls: int = 500,
    ) -> None:
        self.run_budget_usd = run_budget_usd
        self.max_model_calls = max_model_calls
        self.records: list[CostTelemetryRecord] = []
        self.budget_blocked_events: list[BudgetBlockedEvent] = []

    @property
    def total_cost_usd(self) -> Decimal:
        return sum((record.estimated_cost_usd for record in self.records), Decimal("0"))

    def record_live_job(self, record: CostTelemetryRecord) -> bool:
        projected_cost = self.total_cost_usd + record.estimated_cost_usd
        projected_calls = len(self.records) + 1
        if projected_cost > self.run_budget_usd:
            self._record_budget_block(record, "budget_overrun", projected_cost)
            return False
        if projected_calls > self.max_model_calls:
            self._record_budget_block(record, "model_call_limit", projected_cost)
            return False

        self.records.append(record)
        return True

    def _record_budget_block(
        self,
        record: CostTelemetryRecord,
        reason: str,
        attempted_cost_usd: Decimal,
    ) -> None:
        self.budget_blocked_events.append(
            BudgetBlockedEvent(
                run_id=record.run_id,
                job_id=record.job_id,
                reason=reason,
                attempted_cost_usd=attempted_cost_usd,
                budget_limit_usd=self.run_budget_usd,
            )
        )


def append_jsonl(path: Path, record: CostTelemetryRecord) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as output:
        output.write(json.dumps(record.to_json_dict(), sort_keys=True))
        output.write("\n")


def load_jsonl(path: Path) -> list[CostTelemetryRecord]:
    records: list[CostTelemetryRecord] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        data = json.loads(line)
        records.append(
            CostTelemetryRecord(
                project=data["project"],
                run_id=data["run_id"],
                job_id=data["job_id"],
                job_type=data["job_type"],
                worker_id=data["worker_id"],
                model=data["model"],
                provider=data["provider"],
                input_tokens=int(data["input_tokens"]),
                output_tokens=int(data["output_tokens"]),
                estimated_cost_usd=Decimal(data["estimated_cost_usd"]),
                retry_count=int(data["retry_count"]),
                environment=data["environment"],
            )
        )
    return records


def _cents_to_usd(cents: int) -> Decimal:
    return Decimal(cents) / Decimal(100)
