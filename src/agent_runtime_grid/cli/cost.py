from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer

from agent_runtime_grid.cost.rollup import write_cost_rollup_report

app = typer.Typer()
DEFAULT_TELEMETRY_PATH = Path("docs/ai_cost_telemetry.jsonl")
DEFAULT_ROLLUP_PATH = Path("reports/ai_cost_rollup.md")


@app.command()
def rollup(
    input_path: Annotated[Path, typer.Option("--input")] = DEFAULT_TELEMETRY_PATH,
    output_path: Annotated[Path, typer.Option("--output")] = DEFAULT_ROLLUP_PATH,
) -> None:
    write_cost_rollup_report(input_path, output_path)
