from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any


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
