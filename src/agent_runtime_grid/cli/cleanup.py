from __future__ import annotations

import shutil
from pathlib import Path

import typer

app = typer.Typer()


def cleanup_runtime_outputs(
    *,
    artifact_root: Path = Path("artifacts"),
    reports_root: Path = Path("reports"),
) -> list[Path]:
    removed: list[Path] = []
    for path in (artifact_root, reports_root):
        if path.exists():
            shutil.rmtree(path)
            removed.append(path)
    return removed


@app.command()
def local(
    artifact_root: Path = Path("artifacts"),
    reports_root: Path = Path("reports"),
) -> None:
    cleanup_runtime_outputs(artifact_root=artifact_root, reports_root=reports_root)
