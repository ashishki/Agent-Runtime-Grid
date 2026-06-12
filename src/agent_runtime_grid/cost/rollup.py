from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from agent_runtime_grid.cost.telemetry import CostTelemetryRecord, load_jsonl


@dataclass(frozen=True)
class CostRollupViolation(RuntimeError):
    errors: tuple[str, ...]

    def __str__(self) -> str:
        return "; ".join(self.errors)


def write_cost_rollup_report(
    input_path: Path,
    output_path: Path,
    *,
    strict: bool = False,
    require_file: bool = False,
    max_total_cost: Decimal | None = None,
    max_run_cost: Decimal | None = None,
) -> Path:
    if require_file and not input_path.is_file():
        raise CostRollupViolation((f"missing telemetry file: {input_path}",))

    records = load_jsonl(input_path) if input_path.exists() else []
    errors = validate_cost_rollup(
        records,
        max_total_cost=max_total_cost,
        max_run_cost=max_run_cost,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_cost_rollup(records, errors=errors), encoding="utf-8")
    if strict and errors:
        raise CostRollupViolation(tuple(errors))
    return output_path


def render_cost_rollup(
    records: list[CostTelemetryRecord],
    *,
    errors: list[str] | None = None,
) -> str:
    run_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    job_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for record in records:
        run_totals[record.run_id] += record.estimated_cost_usd
        job_totals[record.job_id] += record.estimated_cost_usd

    lines = ["# AI Cost Rollup", "", "## Per-Run Totals", ""]
    for run_id, total in sorted(run_totals.items()):
        lines.append(f"- `{run_id}`: ${total}")

    lines.extend(["", "## Per-Job Totals", ""])
    for job_id, total in sorted(job_totals.items()):
        lines.append(f"- `{job_id}`: ${total}")

    if errors:
        lines.extend(["", "## Strict Check", ""])
        for error in errors:
            lines.append(f"- violation: {error}")

    lines.append("")
    return "\n".join(lines)


def validate_cost_rollup(
    records: list[CostTelemetryRecord],
    *,
    max_total_cost: Decimal | None = None,
    max_run_cost: Decimal | None = None,
) -> list[str]:
    errors: list[str] = []
    total_cost = sum((record.estimated_cost_usd for record in records), Decimal("0"))
    if max_total_cost is not None and total_cost > max_total_cost:
        errors.append(f"total cost ${total_cost} exceeds limit ${max_total_cost}")

    if max_run_cost is not None:
        run_totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
        for record in records:
            run_totals[record.run_id] += record.estimated_cost_usd
        for run_id, run_total in sorted(run_totals.items()):
            if run_total > max_run_cost:
                errors.append(f"run {run_id} cost ${run_total} exceeds limit ${max_run_cost}")
    return errors
