from __future__ import annotations

from decimal import Decimal
from pathlib import Path
from typing import Annotated

import typer

from agent_runtime_grid.cost.rollup import CostRollupViolation, write_cost_rollup_report

app = typer.Typer()
DEFAULT_TELEMETRY_PATH = Path("docs/ai_cost_telemetry.jsonl")
DEFAULT_ROLLUP_PATH = Path("reports/ai_cost_rollup.md")


@app.command()
def rollup(
    input_path: Annotated[Path, typer.Option("--input")] = DEFAULT_TELEMETRY_PATH,
    output_path: Annotated[Path, typer.Option("--output")] = DEFAULT_ROLLUP_PATH,
    strict: Annotated[bool, typer.Option("--strict")] = False,
    require_file: Annotated[bool, typer.Option("--require-file")] = False,
    max_total_cost: Annotated[str | None, typer.Option("--max-total-cost")] = None,
    max_run_cost: Annotated[str | None, typer.Option("--max-run-cost")] = None,
) -> None:
    try:
        write_cost_rollup_report(
            input_path,
            output_path,
            strict=strict,
            require_file=require_file,
            max_total_cost=Decimal(max_total_cost) if max_total_cost is not None else None,
            max_run_cost=Decimal(max_run_cost) if max_run_cost is not None else None,
        )
    except CostRollupViolation as exc:
        typer.echo(f"cost rollup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
