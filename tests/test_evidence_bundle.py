import json
from decimal import Decimal
from pathlib import Path

import pytest

from agent_runtime_grid.cli.benchmark import ReliabilityReport
from agent_runtime_grid.evidence import (
    EvidenceVerificationError,
    portable_path,
    verify_evidence_manifest,
    write_evidence_bundle,
)


def _report() -> ReliabilityReport:
    return ReliabilityReport(
        submitted_jobs=1,
        lifecycle_counts={"completed": 1},
        completion_rate=1,
        duplicate_finalization_count=0,
        finalization_conflict_attempt_count=1,
        retry_count=0,
        queue_lag_seconds=0,
        p95_duration_seconds=0,
        artifact_completeness=1,
        estimated_cost_usd=Decimal("0"),
        run_id="run-1",
    )


def test_evidence_bundle_is_machine_readable_and_verifiable(tmp_path: Path) -> None:
    bundle = write_evidence_bundle(
        report_path=tmp_path / "runtime.md",
        rendered_report="# Runtime\n",
        report=_report(),
        command="smoke",
        config={"jobs": 1, "artifact_root": Path("artifacts")},
        seed=42,
    )

    verify_evidence_manifest(bundle.manifest_path)
    payload = json.loads(bundle.data_path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "agent-runtime-grid.run-evidence.v1"
    assert payload["report"]["finalization_conflict_attempt_count"] == 1
    assert payload["seed"] == 42
    assert not Path(payload["config"]["artifact_root"]).is_absolute()


@pytest.mark.parametrize("target", ["report", "data"])
def test_verifier_rejects_modified_evidence(tmp_path: Path, target: str) -> None:
    bundle = write_evidence_bundle(
        report_path=tmp_path / "runtime.md",
        rendered_report="# Runtime\n",
        report=_report(),
        command="smoke",
        config={},
    )
    path = bundle.report_path if target == "report" else bundle.data_path
    path.write_text("tampered", encoding="utf-8")

    with pytest.raises(EvidenceVerificationError, match="sha256 mismatch"):
        verify_evidence_manifest(bundle.manifest_path)


def test_verifier_rejects_missing_and_extra_sidecars(tmp_path: Path) -> None:
    bundle = write_evidence_bundle(
        report_path=tmp_path / "runtime.md",
        rendered_report="# Runtime\n",
        report=_report(),
        command="smoke",
        config={},
    )
    bundle.data_path.unlink()
    with pytest.raises(EvidenceVerificationError, match="missing evidence"):
        verify_evidence_manifest(bundle.manifest_path)

    bundle = write_evidence_bundle(
        report_path=tmp_path / "second.md",
        rendered_report="# Runtime\n",
        report=_report(),
        command="smoke",
        config={},
    )
    (tmp_path / "second.unexpected").write_text("extra", encoding="utf-8")
    with pytest.raises(EvidenceVerificationError, match="unexpected evidence"):
        verify_evidence_manifest(bundle.manifest_path)


def test_portable_path_redacts_absolute_paths_outside_checkout(tmp_path: Path) -> None:
    assert portable_path(tmp_path / "private" / "report.json", namespace="input") == (
        "input://report.json"
    )
