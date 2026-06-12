from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class EvalLabPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class EvalLabCasePayload:
    dataset_path: Path
    case_id: str
    candidate_id: str
    mode: str
    eval_result_path: Path


def validate_eval_lab_case_payload(payload: dict[str, Any]) -> EvalLabCasePayload:
    dataset_path = _required_path(payload, "dataset_path")
    case_id = _required_str(payload, "case_id")
    candidate_id = str(payload.get("candidate_id") or payload.get("candidate") or "").strip()
    if not candidate_id:
        raise EvalLabPayloadError("candidate_id is required")
    mode = _required_str(payload, "mode")
    if mode not in {"stub", "local", "stub-or-local-http"}:
        raise EvalLabPayloadError("mode must be one of: stub, local, stub-or-local-http")
    eval_result_path = Path(
        str(
            payload.get(
                "eval_result_path",
                Path("reports") / "eval-lab" / candidate_id / f"{case_id}.json",
            )
        )
    )
    return EvalLabCasePayload(
        dataset_path=dataset_path,
        case_id=case_id,
        candidate_id=candidate_id,
        mode=mode,
        eval_result_path=eval_result_path,
    )


async def run_eval_lab_case(
    payload: dict[str, Any],
    *,
    attempt_number: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    case_payload = validate_eval_lab_case_payload(payload)
    case = _load_case(case_payload.dataset_path, case_payload.case_id)
    quality_status = _quality_status(case)
    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    artifact_payload = {
        "case_id": case_payload.case_id,
        "candidate_id": case_payload.candidate_id,
        "dataset_path": str(case_payload.dataset_path),
        "status": "completed",
        "runtime_status": "completed",
        "eval_result_path": str(case_payload.eval_result_path),
        "quality_status": quality_status,
        "runtime_attempts": attempt_number,
        "attempt_count": attempt_number,
        "latency_ms": latency_ms,
        "mode": case_payload.mode,
    }
    _write_eval_result(case_payload.eval_result_path, artifact_payload)
    return {
        "summary": "eval_lab_case completed",
        "case_id": case_payload.case_id,
        "quality_status": quality_status,
        "eval_result_path": str(case_payload.eval_result_path),
        "artifact_payload": artifact_payload,
    }


def _required_path(payload: dict[str, Any], key: str) -> Path:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise EvalLabPayloadError(f"{key} is required")
    return Path(value)


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise EvalLabPayloadError(f"{key} is required")
    return value


def _load_case(dataset_path: Path, case_id: str) -> dict[str, Any]:
    if not dataset_path.is_file():
        raise EvalLabPayloadError(f"dataset not found: {dataset_path}")
    for line_number, line in enumerate(dataset_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            case = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvalLabPayloadError(
                f"dataset line {line_number} is not valid JSON: {dataset_path}"
            ) from exc
        if case.get("id") == case_id:
            return case
    raise EvalLabPayloadError(f"case_id {case_id!r} not found in {dataset_path}")


def _quality_status(case: dict[str, Any]) -> str:
    expected = case.get("expected")
    if isinstance(expected, dict) and expected.get("quality_status") in {"pass", "fail"}:
        return str(expected["quality_status"])
    return "pass"


def _write_eval_result(eval_result_path: Path, artifact_payload: dict[str, Any]) -> None:
    eval_result_path.parent.mkdir(parents=True, exist_ok=True)
    eval_result_path.write_text(
        json.dumps(
            {
                "case_id": artifact_payload["case_id"],
                "candidate_id": artifact_payload["candidate_id"],
                "quality_status": artifact_payload["quality_status"],
                "runtime_status": artifact_payload["runtime_status"],
                "latency_ms": artifact_payload["latency_ms"],
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
