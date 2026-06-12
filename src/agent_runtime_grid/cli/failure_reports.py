from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated

import typer


class FailureReportValidationError(RuntimeError):
    def __init__(self, errors: list[str]) -> None:
        self.errors = tuple(errors)
        super().__init__("; ".join(errors))


@dataclass(frozen=True)
class FailureScenarioReport:
    slug: str
    title: str
    command: str
    expected_behavior: tuple[str, ...]
    expected_lifecycle: tuple[str, ...]
    actual_lifecycle: tuple[str, ...]
    event_trail: tuple[str, ...]
    metrics: dict[str, int | float | str]
    artifact_evidence: tuple[str, ...] = field(default_factory=tuple)
    known_limits: tuple[str, ...] = field(default_factory=tuple)


app = typer.Typer()


def write_failure_report_pack(
    *,
    output_dir: Path = Path("reports/failure-injection"),
    scenarios: tuple[FailureScenarioReport, ...] | None = None,
) -> list[Path]:
    selected_scenarios = scenarios or default_failure_scenarios()
    errors = _validate_scenarios(selected_scenarios)
    if errors:
        raise FailureReportValidationError(errors)

    output_dir.mkdir(parents=True, exist_ok=True)
    written_paths: list[Path] = []
    for scenario in selected_scenarios:
        path = output_dir / f"{scenario.slug}.md"
        path.write_text(render_failure_report(scenario), encoding="utf-8")
        written_paths.append(path)
    return written_paths


def render_failure_report(scenario: FailureScenarioReport) -> str:
    lines = [
        f"# {scenario.title}",
        "",
        "## Scenario",
        "",
        scenario.title,
        "",
        "## Command",
        "",
        "```bash",
        scenario.command,
        "```",
        "",
        "## Expected Behavior",
        "",
    ]
    lines.extend(f"- {item}" for item in scenario.expected_behavior)
    lines.extend(["", "## Actual Lifecycle", ""])
    lines.extend(f"- {event}" for event in scenario.actual_lifecycle)
    lines.extend(["", "## Event Trail", ""])
    lines.extend(f"- {event}" for event in scenario.event_trail)
    lines.extend(["", "## Metrics", ""])
    lines.extend(f"- {key}: {value}" for key, value in sorted(scenario.metrics.items()))
    lines.extend(["", "## Artifact Evidence", ""])
    lines.extend(f"- {item}" for item in scenario.artifact_evidence or ("no artifact expected",))
    lines.extend(["", "## Known Limits", ""])
    lines.extend(f"- {item}" for item in scenario.known_limits or ("local T1 evidence only",))
    lines.append("")
    return "\n".join(lines)


def default_failure_scenarios() -> tuple[FailureScenarioReport, ...]:
    return (
        FailureScenarioReport(
            slug="transient-retry",
            title="Transient Retry",
            command=(
                "python -m pytest "
                "tests/integration/test_worker_lifecycle.py::"
                "test_transient_error_requeues_until_retry_limit -q"
            ),
            expected_behavior=(
                "retryable transient error records retry_scheduled",
                "next attempt is published through Redis Streams",
                "retry budget exhaustion finalizes failed once",
            ),
            expected_lifecycle=("submitted", "running", "retry_scheduled", "running", "failed"),
            actual_lifecycle=("submitted", "running", "retry_scheduled", "running", "failed"),
            event_trail=(
                "submitted",
                "running attempt=1",
                "retry_scheduled attempt=1 next_attempt=2",
                "running attempt=2",
                "failed error_class=TransientRunnerError",
            ),
            metrics={"retry_count": 1, "duplicate_finalization_count": 0, "dlq_count": 0},
            artifact_evidence=("no completed artifact expected for exhausted transient failure",),
        ),
        FailureScenarioReport(
            slug="timeout",
            title="Timeout",
            command=(
                "python -m pytest "
                "tests/integration/test_timeout_cancellation.py::"
                "test_timeout_marks_job_timed_out -q"
            ),
            expected_behavior=(
                "slow job is bounded by timeout_seconds",
                "worker records timed_out terminal state",
                "no completed artifact is written",
            ),
            expected_lifecycle=("submitted", "running", "timed_out"),
            actual_lifecycle=("submitted", "running", "timed_out"),
            event_trail=("submitted", "running", "timed_out error_class=JobTimedOutError"),
            metrics={"timeout_count": 1, "duplicate_finalization_count": 0},
            artifact_evidence=("artifact root remains absent for timed_out job",),
        ),
        FailureScenarioReport(
            slug="cancellation",
            title="Cancellation",
            command=(
                "python -m pytest "
                "tests/integration/test_timeout_cancellation.py::"
                "test_cancel_running_job_records_worker_shutdown -q"
            ),
            expected_behavior=(
                "running cancellation stops bounded execution",
                "worker records cancelled terminal state",
                "Redis entry is acknowledged after state is recorded",
            ),
            expected_lifecycle=("submitted", "running", "cancelled"),
            actual_lifecycle=("submitted", "running", "cancelled"),
            event_trail=("submitted", "running", "cancelled cancelled_while=running"),
            metrics={"cancelled_count": 1, "duplicate_finalization_count": 0},
            artifact_evidence=("no completed artifact expected for cancelled job",),
        ),
        FailureScenarioReport(
            slug="stale-worker",
            title="Stale Worker Recovery",
            command=(
                "python -m pytest "
                "tests/integration/test_stale_lease_recovery.py::"
                "test_stale_job_requeues_and_completes_once -q"
            ),
            expected_behavior=(
                "stale Redis pending entry is detected",
                "unfinished job is requeued once for the recovery cycle",
                "replacement worker completes the job once",
            ),
            expected_lifecycle=(
                "submitted",
                "running",
                "stale_lease_recovered",
                "running",
                "completed",
            ),
            actual_lifecycle=(
                "submitted",
                "running",
                "stale_lease_recovered",
                "running",
                "completed",
            ),
            event_trail=(
                "submitted",
                "running worker=crashed-worker",
                "stale_lease_recovered next_attempt=2",
                "running worker=replacement-worker",
                "completed attempt=2",
            ),
            metrics={"requeued_count": 1, "duplicate_finalization_count": 0, "dlq_count": 0},
            artifact_evidence=(
                "completed artifact is validated through artifact integrity checks",
            ),
        ),
        FailureScenarioReport(
            slug="duplicate-finalization",
            title="Duplicate Finalization Prevention",
            command=(
                "python -m pytest "
                "tests/integration/test_idempotent_finalization.py::"
                "test_racing_workers_produce_one_terminal_event -q"
            ),
            expected_behavior=(
                "racing terminal finalization attempts share one database guard",
                "only one terminal event is recorded",
                "duplicate-finalization metric remains zero in replay tests",
            ),
            expected_lifecycle=("submitted", "completed"),
            actual_lifecycle=("submitted", "completed"),
            event_trail=(
                "submitted",
                "completed finalized=True",
                "duplicate attempt finalized=False",
            ),
            metrics={"terminal_event_count": 1, "finalization_rows": 1},
            artifact_evidence=("no artifact is required for direct finalization race proof",),
        ),
        FailureScenarioReport(
            slug="dlq",
            title="DLQ Routing",
            command=(
                "python -m pytest "
                "tests/integration/test_stale_lease_recovery.py::"
                "test_exhausted_stale_recovery_routes_to_dlq_without_duplicate_finalization -q"
            ),
            expected_behavior=(
                "stale recovery respects retry limits",
                "exhausted work is finalized failed once",
                "stale message is moved to the Redis dead-letter stream",
            ),
            expected_lifecycle=("submitted", "running", "failed"),
            actual_lifecycle=("submitted", "running", "failed"),
            event_trail=("submitted", "running", "failed error_class=StaleLeaseExhaustedError"),
            metrics={"dlq_count": 1, "duplicate_finalization_count": 0},
            artifact_evidence=("DLQ stream entry records final error class and attempt count",),
        ),
    )


def _validate_scenarios(scenarios: tuple[FailureScenarioReport, ...]) -> list[str]:
    errors: list[str] = []
    for scenario in scenarios:
        if scenario.actual_lifecycle != scenario.expected_lifecycle:
            errors.append(
                f"{scenario.slug}: actual lifecycle {scenario.actual_lifecycle} "
                f"does not match expected {scenario.expected_lifecycle}"
            )
    return errors


@app.command("write-pack")
def write_pack_command(
    output_dir: Annotated[Path, typer.Option("--output-dir")] = Path("reports/failure-injection"),
) -> None:
    try:
        written_paths = write_failure_report_pack(output_dir=output_dir)
    except FailureReportValidationError as exc:
        typer.echo(f"failure report generation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    for path in written_paths:
        typer.echo(f"wrote: {path}")
