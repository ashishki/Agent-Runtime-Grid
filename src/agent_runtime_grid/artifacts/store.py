from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_runtime_grid.domain.jobs import JobRecord, payload_sha256


@dataclass(frozen=True)
class ArtifactMetadata:
    path: Path
    size_bytes: int
    sha256: str
    job_id: str
    created_at: datetime


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

        content = {
            "job_id": str(job.id),
            "run_id": str(job.run_id),
            "input_digest": payload_sha256(job.payload),
            "worker_id": worker_id,
            "attempt_number": attempt_number,
            "result_summary": result.get("summary", ""),
        }
        encoded = json.dumps(content, sort_keys=True, indent=2).encode("utf-8")
        artifact_path.write_bytes(encoded)

        return ArtifactMetadata(
            path=artifact_path,
            size_bytes=len(encoded),
            sha256=hashlib.sha256(encoded).hexdigest(),
            job_id=str(job.id),
            created_at=datetime.now(UTC),
        )
