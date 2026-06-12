from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from agent_runtime_grid.domain.jobs import JobRecord, payload_sha256


@dataclass(frozen=True)
class ArtifactMetadata:
    path: Path
    size_bytes: int
    sha256: str
    job_id: str
    run_id: str
    attempt_number: int
    input_digest: str
    created_at: datetime
    eval_result_path: str | None = None

    def to_dict(self) -> dict[str, str | int]:
        data: dict[str, str | int] = {
            "path": str(self.path),
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
            "job_id": self.job_id,
            "run_id": self.run_id,
            "attempt_number": self.attempt_number,
            "input_digest": self.input_digest,
            "created_at": self.created_at.isoformat(),
        }
        if self.eval_result_path is not None:
            data["eval_result_path"] = self.eval_result_path
        return data

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> Self:
        return cls(
            path=Path(str(value["path"])),
            size_bytes=int(value["size_bytes"]),
            sha256=str(value["sha256"]),
            job_id=str(value["job_id"]),
            run_id=str(value["run_id"]),
            attempt_number=int(value["attempt_number"]),
            input_digest=str(value["input_digest"]),
            created_at=datetime.fromisoformat(str(value["created_at"])),
            eval_result_path=(
                str(value["eval_result_path"])
                if value.get("eval_result_path") is not None
                else None
            ),
        )


@dataclass(frozen=True)
class ArtifactIntegritySummary:
    checked_count: int
    valid_count: int
    rows: tuple[ArtifactMetadata, ...]


class ArtifactIntegrityError(RuntimeError):
    pass


class ArtifactStore:
    def __init__(self, root: Path | str) -> None:
        self.root = Path(root)

    def write_stub_job_artifact(
        self,
        job: JobRecord,
        *,
        worker_id: str,
        attempt_number: int,
        result: dict[str, Any],
    ) -> ArtifactMetadata:
        artifact_dir = self.root / str(job.id)
        artifact_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = artifact_dir / f"attempt-{attempt_number}.json"
        created_at = datetime.now(UTC)
        input_digest = payload_sha256(job.payload)
        artifact_payload = result.get("artifact_payload")
        if artifact_payload is not None and not isinstance(artifact_payload, dict):
            raise TypeError("artifact_payload must be a dictionary when provided")
        eval_result_path = None
        if (
            isinstance(artifact_payload, dict)
            and artifact_payload.get("eval_result_path") is not None
        ):
            eval_result_path = str(artifact_payload["eval_result_path"])

        content = {
            "job_id": str(job.id),
            "run_id": str(job.run_id),
            "input_digest": input_digest,
            "worker_id": worker_id,
            "attempt_number": attempt_number,
            "created_at": created_at.isoformat(),
            "result_summary": result.get("summary", ""),
        }
        if artifact_payload is not None:
            content.update(artifact_payload)
        encoded = json.dumps(content, sort_keys=True, indent=2).encode("utf-8")
        artifact_path.write_bytes(encoded)
        if eval_result_path is not None:
            _upsert_eval_result_cross_link(
                eval_result_path=Path(eval_result_path),
                artifact_path=artifact_path,
                artifact_payload=artifact_payload or {},
            )

        return ArtifactMetadata(
            path=artifact_path,
            size_bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
            job_id=str(job.id),
            run_id=str(job.run_id),
            attempt_number=attempt_number,
            input_digest=input_digest,
            created_at=created_at,
            eval_result_path=eval_result_path,
        )


def validate_artifact_integrity(metadata: ArtifactMetadata) -> None:
    if not metadata.path.is_file():
        raise ArtifactIntegrityError(f"missing artifact: {metadata.path}")

    artifact_bytes = metadata.path.read_bytes()
    actual_size = len(artifact_bytes)
    if actual_size != metadata.size_bytes:
        raise ArtifactIntegrityError(
            f"artifact size mismatch for {metadata.path}: "
            f"expected {metadata.size_bytes}, got {actual_size}"
        )

    actual_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    if actual_sha256 != metadata.sha256:
        raise ArtifactIntegrityError(
            f"artifact sha256 mismatch for {metadata.path}: "
            f"expected {metadata.sha256}, got {actual_sha256}"
        )

    try:
        content = json.loads(artifact_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ArtifactIntegrityError(f"artifact is not valid JSON: {metadata.path}") from exc

    expected_fields: dict[str, object] = {
        "job_id": metadata.job_id,
        "run_id": metadata.run_id,
        "attempt_number": metadata.attempt_number,
        "input_digest": metadata.input_digest,
        "created_at": metadata.created_at.isoformat(),
    }
    if metadata.eval_result_path is not None:
        expected_fields["eval_result_path"] = metadata.eval_result_path
    for field, expected in expected_fields.items():
        if content.get(field) != expected:
            raise ArtifactIntegrityError(
                f"artifact field {field} mismatch for {metadata.path}: "
                f"expected {expected!r}, got {content.get(field)!r}"
            )


def _upsert_eval_result_cross_link(
    *,
    eval_result_path: Path,
    artifact_path: Path,
    artifact_payload: dict[str, Any],
) -> None:
    eval_result_path.parent.mkdir(parents=True, exist_ok=True)
    if eval_result_path.exists():
        try:
            result = json.loads(eval_result_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            result = {}
    else:
        result = {}
    result.update(
        {
            "case_id": artifact_payload.get("case_id"),
            "quality_status": artifact_payload.get("quality_status"),
            "runtime_artifact_path": str(artifact_path),
        }
    )
    eval_result_path.write_text(json.dumps(result, sort_keys=True, indent=2), encoding="utf-8")
