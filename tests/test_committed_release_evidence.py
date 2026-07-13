from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from typer.testing import CliRunner

from agent_runtime_grid.cli.main import app
from agent_runtime_grid.evidence import (
    COMMITTED_RELEASE_MANIFEST,
    COMMITTED_RELEASE_MANIFEST_SHA256,
    EvidenceVerificationError,
    verify_committed_release_evidence,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_committed_release_evidence_binds_content_and_semantics() -> None:
    result = verify_committed_release_evidence(REPO_ROOT)

    assert result.manifest_path == COMMITTED_RELEASE_MANIFEST.as_posix()
    assert result.content_address == f"sha256:{COMMITTED_RELEASE_MANIFEST_SHA256}"
    assert result.source_revision == "ddf533b36bbca0fd90a3093984d0b3f36e8ebeab"
    assert result.submitted_jobs == 20
    assert result.valid_artifacts == 20


def test_committed_release_verifier_rejects_resealed_semantic_changes(tmp_path: Path) -> None:
    release_source = REPO_ROOT / COMMITTED_RELEASE_MANIFEST.parent
    release_copy = tmp_path / COMMITTED_RELEASE_MANIFEST.parent
    shutil.copytree(release_source, release_copy)

    data_path = release_copy / "runtime-smoke.json"
    payload = json.loads(data_path.read_text(encoding="utf-8"))
    payload["report"]["submitted_jobs"] = 19
    data_path.write_text(json.dumps(payload, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    manifest_path = release_copy / "runtime-smoke.manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for entry in manifest["files"]:
        if entry["path"] == data_path.name:
            entry["sha256"] = hashlib.sha256(data_path.read_bytes()).hexdigest()
    manifest_path.write_text(
        json.dumps(manifest, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )

    with pytest.raises(EvidenceVerificationError, match="content address mismatch"):
        verify_committed_release_evidence(tmp_path)


def test_committed_release_cli_reports_machine_readable_receipt() -> None:
    result = CliRunner().invoke(
        app,
        ["verify-committed-evidence", "--repository-root", str(REPO_ROOT)],
    )

    assert result.exit_code == 0, result.output
    receipt = json.loads(result.stdout)
    assert receipt == {
        "content_address": f"sha256:{COMMITTED_RELEASE_MANIFEST_SHA256}",
        "manifest_path": COMMITTED_RELEASE_MANIFEST.as_posix(),
        "source_revision": "ddf533b36bbca0fd90a3093984d0b3f36e8ebeab",
        "submitted_jobs": 20,
        "valid_artifacts": 20,
        "verified": True,
    }
