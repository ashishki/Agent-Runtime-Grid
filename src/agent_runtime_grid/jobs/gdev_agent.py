from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from agent_runtime_grid.domain.jobs import payload_sha256


class GdevAgentPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class GdevWebhookEvalPayload:
    case_id: str
    candidate_id: str
    request: dict[str, Any]
    mode: str
    eval_result_path: Path


def validate_gdev_webhook_eval_payload(payload: dict[str, Any]) -> GdevWebhookEvalPayload:
    case_id = _required_str(payload, "case_id")
    candidate_id = str(payload.get("candidate_id") or payload.get("candidate") or "").strip()
    if not candidate_id:
        raise GdevAgentPayloadError("candidate_id is required")
    request = payload.get("request")
    if not isinstance(request, dict):
        raise GdevAgentPayloadError("request must be an object")
    mode = _required_str(payload, "mode")
    if mode not in {"stub", "local"}:
        raise GdevAgentPayloadError("mode must be one of: stub, local")
    eval_result_path = Path(
        str(
            payload.get(
                "eval_result_path",
                Path("reports") / "eval-lab" / candidate_id / f"{case_id}.json",
            )
        )
    )
    return GdevWebhookEvalPayload(
        case_id=case_id,
        candidate_id=candidate_id,
        request=request,
        mode=mode,
        eval_result_path=eval_result_path,
    )


async def run_gdev_webhook_eval(
    payload: dict[str, Any],
    *,
    attempt_number: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    case_payload = validate_gdev_webhook_eval_payload(payload)
    request_hash = payload_sha256(case_payload.request)
    normalized_fields = _normalize_request(case_payload.request)
    sanitized_response = _sanitized_response(case_payload.case_id, normalized_fields)
    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    artifact_payload = {
        "case_id": case_payload.case_id,
        "gdev_case_id": case_payload.case_id,
        "candidate_id": case_payload.candidate_id,
        "request_hash": request_hash,
        "sanitized_response": sanitized_response,
        "normalized_fields": normalized_fields,
        "runtime_status": "completed",
        "status": "completed",
        "quality_status": "pass",
        "runtime_attempts": attempt_number,
        "attempt_count": attempt_number,
        "latency_ms": latency_ms,
        "eval_result_path": str(case_payload.eval_result_path),
        "mode": case_payload.mode,
    }
    _write_eval_result(case_payload.eval_result_path, artifact_payload)
    return {
        "summary": "gdev_webhook_eval completed",
        "case_id": case_payload.case_id,
        "request_hash": request_hash,
        "quality_status": "pass",
        "eval_result_path": str(case_payload.eval_result_path),
        "artifact_payload": artifact_payload,
    }


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise GdevAgentPayloadError(f"{key} is required")
    return value


def _normalize_request(request: dict[str, Any]) -> dict[str, Any]:
    text = str(request.get("text") or request.get("message") or "").lower()
    if "refund" in text or "billing" in text:
        category = "billing"
        requires_human = False
        expected_status = "executed"
    elif "bug" in text or "error" in text or "spinner" in text:
        category = "bug_report"
        requires_human = False
        expected_status = "executed"
    elif "abuse" in text or "moderation" in text or "harass" in text:
        category = "moderation"
        requires_human = True
        expected_status = "pending"
    else:
        category = "webhook"
        requires_human = False
        expected_status = "executed"
    return {
        "category": category,
        "requires_human": requires_human,
        "expected_status": expected_status,
    }


def _sanitized_response(case_id: str, normalized_fields: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": normalized_fields["expected_status"],
        "category": normalized_fields["category"],
        "requires_human": normalized_fields["requires_human"],
        "response_hash": payload_sha256(
            {
                "case_id": case_id,
                "normalized_fields": normalized_fields,
            }
        ),
    }


def _write_eval_result(eval_result_path: Path, artifact_payload: dict[str, Any]) -> None:
    eval_result_path.parent.mkdir(parents=True, exist_ok=True)
    eval_result_path.write_text(
        json.dumps(
            {
                "case_id": artifact_payload["case_id"],
                "candidate_id": artifact_payload["candidate_id"],
                "quality_status": artifact_payload["quality_status"],
                "request_hash": artifact_payload["request_hash"],
                "normalized_fields": artifact_payload["normalized_fields"],
                "sanitized_response": artifact_payload["sanitized_response"],
            },
            sort_keys=True,
            indent=2,
        ),
        encoding="utf-8",
    )
