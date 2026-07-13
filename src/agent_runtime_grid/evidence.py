from __future__ import annotations

import hashlib
import json
import os
import platform
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

RUN_EVIDENCE_SCHEMA = "agent-runtime-grid.run-evidence.v1"
MANIFEST_SCHEMA = "agent-runtime-grid.evidence-manifest.v1"
COMMITTED_RELEASE_MANIFEST = Path("docs/evidence/releases/v0.1.0/runtime-smoke.manifest.json")
COMMITTED_RELEASE_MANIFEST_SHA256 = (
    "07442b769fad42a1664cc3adc7a11d73cb2041ceb61f65e402087e096d5b12ed"
)
COMMITTED_RELEASE_SOURCE_REVISION = "ddf533b36bbca0fd90a3093984d0b3f36e8ebeab"


class EvidenceVerificationError(RuntimeError):
    pass


@dataclass(frozen=True)
class EvidenceBundle:
    report_path: Path
    data_path: Path
    manifest_path: Path


@dataclass(frozen=True)
class CommittedEvidenceVerification:
    manifest_path: str
    content_address: str
    source_revision: str
    submitted_jobs: int
    valid_artifacts: int


def portable_path(value: str | Path, *, namespace: str = "artifact") -> str:
    path = Path(value)
    if not path.is_absolute():
        return path.as_posix()
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return f"{namespace}://{path.name}"


def portable_artifact_path(*, job_id: str, path: str | Path) -> str:
    return f"artifact://{job_id}/{Path(path).name}"


def write_evidence_bundle(
    *,
    report_path: Path,
    rendered_report: str,
    report: Any,
    command: str,
    config: dict[str, Any],
    seed: int | None = None,
) -> EvidenceBundle:
    if report_path.suffix != ".md":
        raise ValueError("evidence report path must end in .md")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    data_path = report_path.with_suffix(".json")
    manifest_path = report_path.with_name(f"{report_path.stem}.manifest.json")
    payload = {
        "schema_version": RUN_EVIDENCE_SCHEMA,
        "generated_at": datetime.now(UTC).isoformat(),
        "command": command,
        "config": _json_safe(config),
        "seed": seed,
        "source_revision": _source_revision(),
        "environment": {
            "python": platform.python_version(),
            "implementation": platform.python_implementation(),
            "platform": platform.system(),
            "machine": platform.machine(),
        },
        "report": _report_payload(report),
    }

    _atomic_write(report_path, rendered_report.encode("utf-8"))
    _atomic_write(
        data_path,
        (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    manifest = {
        "schema_version": MANIFEST_SCHEMA,
        "files": [
            {"path": report_path.name, "sha256": _sha256(report_path)},
            {"path": data_path.name, "sha256": _sha256(data_path)},
        ],
    }
    _atomic_write(
        manifest_path,
        (json.dumps(manifest, sort_keys=True, indent=2) + "\n").encode("utf-8"),
    )
    verify_evidence_manifest(manifest_path)
    return EvidenceBundle(
        report_path=report_path,
        data_path=data_path,
        manifest_path=manifest_path,
    )


def verify_evidence_manifest(manifest_path: Path) -> None:
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceVerificationError(f"cannot read manifest: {manifest_path}") from exc
    if manifest.get("schema_version") != MANIFEST_SCHEMA:
        raise EvidenceVerificationError("unsupported evidence manifest schema")

    stem_suffix = ".manifest.json"
    if not manifest_path.name.endswith(stem_suffix):
        raise EvidenceVerificationError("manifest name must end in .manifest.json")
    stem = manifest_path.name[: -len(stem_suffix)]
    expected_names = {f"{stem}.md", f"{stem}.json"}
    entries = manifest.get("files")
    if not isinstance(entries, list) or len(entries) != len(expected_names):
        raise EvidenceVerificationError("manifest must contain the report and JSON data")

    declared_names: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise EvidenceVerificationError("invalid manifest file entry")
        name = entry.get("path")
        expected_sha256 = entry.get("sha256")
        if not isinstance(name, str) or Path(name).name != name:
            raise EvidenceVerificationError("manifest paths must be sibling file names")
        if name in declared_names:
            raise EvidenceVerificationError(f"duplicate manifest path: {name}")
        declared_names.add(name)
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            raise EvidenceVerificationError(f"invalid sha256 for {name}")
        candidate = manifest_path.parent / name
        if candidate.is_symlink():
            raise EvidenceVerificationError(f"evidence file must not be a symlink: {name}")
        if not candidate.is_file():
            raise EvidenceVerificationError(f"missing evidence file: {name}")
        if _sha256(candidate) != expected_sha256:
            raise EvidenceVerificationError(f"sha256 mismatch: {name}")

    if declared_names != expected_names:
        raise EvidenceVerificationError("manifest file set does not match its report stem")
    allowed_sidecars = expected_names | {manifest_path.name}
    actual_sidecars = {
        candidate.name
        for candidate in manifest_path.parent.iterdir()
        if candidate.is_file() and candidate.name.startswith(f"{stem}.")
    }
    unexpected = actual_sidecars - allowed_sidecars
    if unexpected:
        raise EvidenceVerificationError(
            f"unexpected evidence sidecar(s): {', '.join(sorted(unexpected))}"
        )


def verify_committed_release_evidence(repository_root: Path) -> CommittedEvidenceVerification:
    root = repository_root.resolve()
    manifest_path = root / COMMITTED_RELEASE_MANIFEST
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise EvidenceVerificationError(
            f"committed release manifest is missing or unsafe: {COMMITTED_RELEASE_MANIFEST}"
        )

    manifest_sha256 = _sha256(manifest_path)
    if manifest_sha256 != COMMITTED_RELEASE_MANIFEST_SHA256:
        raise EvidenceVerificationError(
            "committed release manifest content address mismatch: "
            f"expected {COMMITTED_RELEASE_MANIFEST_SHA256}, got {manifest_sha256}"
        )
    verify_evidence_manifest(manifest_path)

    data_path = manifest_path.with_name("runtime-smoke.json")
    try:
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceVerificationError(f"cannot read committed release data: {data_path}") from exc
    _verify_committed_release_semantics(payload)

    report = payload["report"]
    artifact_integrity = report["artifact_integrity"]
    return CommittedEvidenceVerification(
        manifest_path=COMMITTED_RELEASE_MANIFEST.as_posix(),
        content_address=f"sha256:{COMMITTED_RELEASE_MANIFEST_SHA256}",
        source_revision=COMMITTED_RELEASE_SOURCE_REVISION,
        submitted_jobs=report["submitted_jobs"],
        valid_artifacts=artifact_integrity["valid_count"],
    )


def _verify_committed_release_semantics(payload: Any) -> None:
    if not isinstance(payload, dict):
        raise EvidenceVerificationError("committed release data must be a JSON object")

    expected_top_level = {
        "schema_version": RUN_EVIDENCE_SCHEMA,
        "command": "smoke",
        "seed": None,
        "source_revision": {
            "commit": COMMITTED_RELEASE_SOURCE_REVISION,
            "dirty": False,
        },
        "config": {
            "artifact_root": "artifacts",
            "failure_rate": 0.0,
            "jobs": 20,
            "mode": "stub",
            "workers": 4,
        },
        "environment": {
            "implementation": "CPython",
            "machine": "x86_64",
            "platform": "Linux",
            "python": "3.12.3",
        },
    }
    for field, expected in expected_top_level.items():
        _require_committed_value(payload.get(field), expected, field)

    report = payload.get("report")
    if not isinstance(report, dict):
        raise EvidenceVerificationError("committed release report must be a JSON object")
    expected_report = {
        "title": "Load Smoke Report",
        "source": "runtime_state:artifacts",
        "submitted_jobs": 20,
        "lifecycle_counts": {
            "cancelled": 0,
            "completed": 20,
            "dlq": 0,
            "failed": 0,
            "queued": 0,
            "running": 0,
            "timed_out": 0,
        },
        "completion_rate": 1.0,
        "duplicate_terminal_event_count": 0,
        "finalization_conflict_attempt_count": 0,
        "retry_count": 0,
        "artifact_completeness": 1.0,
        "failure_classification": {},
        "estimated_cost_usd": "0",
        "idempotency_replay_count": 0,
        "injected_failure_count": 0,
    }
    for field, expected in expected_report.items():
        _require_committed_value(report.get(field), expected, f"report.{field}")

    backpressure = report.get("backpressure")
    if not isinstance(backpressure, dict):
        raise EvidenceVerificationError("committed release backpressure must be a JSON object")
    for field in (
        "consumer_lag",
        "dlq_count",
        "leased_jobs",
        "oldest_pending_age_seconds",
        "queue_depth",
        "retry_rate",
        "running_jobs",
        "worker_utilization",
    ):
        _require_committed_value(backpressure.get(field), 0, f"report.backpressure.{field}")
    _require_committed_value(
        report.get("queue_lag_seconds"),
        backpressure.get("p95_queue_wait_seconds"),
        "report.queue_lag_seconds",
    )
    _require_committed_value(
        report.get("p95_duration_seconds"),
        backpressure.get("p95_execution_seconds"),
        "report.p95_duration_seconds",
    )

    artifact_integrity = report.get("artifact_integrity")
    if not isinstance(artifact_integrity, dict):
        raise EvidenceVerificationError("committed release artifact integrity must be an object")
    _require_committed_value(
        artifact_integrity.get("checked_count"), 20, "report.artifact_integrity.checked_count"
    )
    _require_committed_value(
        artifact_integrity.get("valid_count"), 20, "report.artifact_integrity.valid_count"
    )
    artifacts = artifact_integrity.get("artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 20:
        raise EvidenceVerificationError(
            "committed release artifact integrity must contain exactly 20 rows"
        )

    run_id = report.get("run_id")
    if not isinstance(run_id, str) or not run_id:
        raise EvidenceVerificationError("committed release run_id must be a non-empty string")
    job_ids: set[str] = set()
    for index, artifact in enumerate(artifacts):
        if not isinstance(artifact, dict):
            raise EvidenceVerificationError(f"committed artifact row {index} must be an object")
        job_id = artifact.get("job_id")
        if not isinstance(job_id, str) or not job_id or job_id in job_ids:
            raise EvidenceVerificationError(
                f"committed artifact row {index} has a missing or duplicate job_id"
            )
        job_ids.add(job_id)
        _require_committed_value(artifact.get("run_id"), run_id, f"artifact[{index}].run_id")
        _require_committed_value(
            artifact.get("path"),
            f"artifact://{job_id}/attempt-1.json",
            f"artifact[{index}].path",
        )
        _require_committed_value(
            artifact.get("attempt_number"), 1, f"artifact[{index}].attempt_number"
        )
        _require_committed_value(
            artifact.get("eval_result_path"), None, f"artifact[{index}].eval_result_path"
        )
        if not _is_sha256(artifact.get("sha256")):
            raise EvidenceVerificationError(f"artifact[{index}].sha256 must be lowercase SHA-256")
        if not _is_sha256(artifact.get("input_digest")):
            raise EvidenceVerificationError(
                f"artifact[{index}].input_digest must be lowercase SHA-256"
            )
        size_bytes = artifact.get("size_bytes")
        if not isinstance(size_bytes, int) or size_bytes <= 0:
            raise EvidenceVerificationError(f"artifact[{index}].size_bytes must be positive")


def _require_committed_value(actual: Any, expected: Any, field: str) -> None:
    if actual != expected:
        raise EvidenceVerificationError(
            "committed release semantic mismatch for "
            f"{field}: expected {expected!r}, got {actual!r}"
        )


def _is_sha256(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _report_payload(report: Any) -> dict[str, Any]:
    artifact_integrity = getattr(report, "artifact_integrity", None)
    artifact_rows: list[dict[str, Any]] = []
    if artifact_integrity is not None:
        for row in artifact_integrity.rows:
            artifact_rows.append(
                {
                    "path": portable_artifact_path(job_id=row.job_id, path=row.path),
                    "size_bytes": row.size_bytes,
                    "sha256": row.sha256,
                    "job_id": row.job_id,
                    "run_id": row.run_id,
                    "attempt_number": row.attempt_number,
                    "input_digest": row.input_digest,
                    "created_at": row.created_at.isoformat(),
                    "eval_result_path": (
                        portable_path(row.eval_result_path, namespace="eval-result")
                        if row.eval_result_path is not None
                        else None
                    ),
                }
            )
    backpressure = getattr(report, "backpressure", None)
    return {
        "title": report.title,
        "run_id": report.run_id,
        "source": report.source,
        "submitted_jobs": report.submitted_jobs,
        "lifecycle_counts": report.lifecycle_counts,
        "completion_rate": report.completion_rate,
        "duplicate_terminal_event_count": report.duplicate_finalization_count,
        "finalization_conflict_attempt_count": report.finalization_conflict_attempt_count,
        "retry_count": report.retry_count,
        "queue_lag_seconds": report.queue_lag_seconds,
        "p95_duration_seconds": report.p95_duration_seconds,
        "artifact_completeness": report.artifact_completeness,
        "failure_classification": report.failure_classification,
        "estimated_cost_usd": str(report.estimated_cost_usd),
        "idempotency_replay_count": report.idempotency_replay_count,
        "injected_failure_count": report.injected_failure_count,
        "backpressure": asdict(backpressure) if backpressure is not None else None,
        "artifact_integrity": {
            "checked_count": artifact_integrity.checked_count if artifact_integrity else 0,
            "valid_count": artifact_integrity.valid_count if artifact_integrity else 0,
            "artifacts": artifact_rows,
        },
    }


def _source_revision() -> dict[str, Any]:
    commit = _git_output("rev-parse", "HEAD")
    status = _git_output("status", "--porcelain=v1", "--untracked-files=no")
    return {
        "commit": commit or "unavailable",
        "dirty": bool(status) if status is not None else None,
    }


def _git_output(*arguments: str) -> str | None:
    result = subprocess.run(
        ["git", *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Path):
        return portable_path(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return value


def _atomic_write(path: Path, content: bytes) -> None:
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as file:
        temporary_path = Path(file.name)
        try:
            file.write(content)
            file.flush()
            os.fsync(file.fileno())
        except BaseException:
            temporary_path.unlink(missing_ok=True)
            raise
    os.replace(temporary_path, path)
    if sys.platform != "win32":
        directory_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
