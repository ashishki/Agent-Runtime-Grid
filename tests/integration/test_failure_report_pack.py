from pathlib import Path

import pytest

from agent_runtime_grid.cli.failure_reports import (
    FailureReportValidationError,
    FailureScenarioReport,
    default_failure_scenarios,
    write_failure_report_pack,
)

EXPECTED_REPORTS = {
    "transient-retry.md",
    "timeout.md",
    "cancellation.md",
    "stale-worker.md",
    "duplicate-finalization.md",
    "dlq.md",
}


def test_failure_report_pack_writes_required_reports(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports" / "failure-injection"

    written_paths = write_failure_report_pack(output_dir=output_dir)

    assert {path.name for path in written_paths} == EXPECTED_REPORTS
    assert {path.name for path in output_dir.glob("*.md")} == EXPECTED_REPORTS


def test_failure_reports_include_required_sections(tmp_path: Path) -> None:
    output_dir = tmp_path / "reports" / "failure-injection"
    write_failure_report_pack(output_dir=output_dir)

    for path in output_dir.glob("*.md"):
        report = path.read_text(encoding="utf-8")
        assert "## Scenario" in report
        assert "## Command" in report
        assert "## Expected Behavior" in report
        assert "## Actual Lifecycle" in report
        assert "## Event Trail" in report
        assert "## Metrics" in report
        assert "## Artifact Evidence" in report
        assert "## Known Limits" in report


def test_failure_report_generation_fails_on_evidence_mismatch(tmp_path: Path) -> None:
    scenario = default_failure_scenarios()[0]
    mismatched = FailureScenarioReport(
        slug=scenario.slug,
        title=scenario.title,
        command=scenario.command,
        expected_behavior=scenario.expected_behavior,
        expected_lifecycle=scenario.expected_lifecycle,
        actual_lifecycle=("submitted", "completed"),
        event_trail=scenario.event_trail,
        metrics=scenario.metrics,
        artifact_evidence=scenario.artifact_evidence,
        known_limits=scenario.known_limits,
    )

    with pytest.raises(FailureReportValidationError, match="does not match expected"):
        write_failure_report_pack(
            output_dir=tmp_path / "reports" / "failure-injection",
            scenarios=(mismatched,),
        )
