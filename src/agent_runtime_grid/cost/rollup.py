from __future__ import annotations

from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from agent_runtime_grid.cost.telemetry import CostTelemetryRecord, load_jsonl


def write_cost_rollup_report(input_path: Path, output_path: Path) -> Path:
    records = load_jsonl(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(render_cost_rollup(records), encoding="utf-8")
    return output_path


def render_cost_rollup(records: list[CostTelemetryRecord]) -> str:
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

    lines.append("")
    return "\n".join(lines)
