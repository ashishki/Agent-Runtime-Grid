from __future__ import annotations

import asyncio
import hashlib
import hmac
import http.client as http_client
import json
import os
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, parse, request

from agent_runtime_grid.domain.jobs import payload_sha256

GDEV_STATUSES = frozenset({"executed", "pending", "blocked", "error"})
LOCAL_GDEV_HOSTS = frozenset({"localhost", "127.0.0.1", "::1"})
DEFAULT_GDEV_WEBHOOK_SECRET_ENV = "GDEV_AGENT_WEBHOOK_SECRET"


class GdevAgentPayloadError(ValueError):
    pass


@dataclass(frozen=True)
class LocalGdevHttpResponse:
    status_code: int
    output: Any


@dataclass(frozen=True)
class GdevWebhookEvalPayload:
    case_id: str
    candidate_id: str
    request: dict[str, Any]
    mode: str
    eval_result_path: Path
    gdev_base_url: str | None = None
    gdev_tenant_slug: str | None = None
    gdev_tenant_id: str | None = None
    gdev_webhook_secret_env: str | None = None


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
    gdev_base_url = None
    gdev_tenant_slug = None
    gdev_tenant_id = None
    gdev_webhook_secret_env = None
    if mode == "local":
        gdev_base_url = _validate_local_base_url(_required_str(payload, "gdev_base_url"))
        gdev_tenant_slug = _required_str(payload, "gdev_tenant_slug")
        gdev_tenant_id = _required_str(payload, "gdev_tenant_id")
        gdev_webhook_secret_env = str(
            payload.get("gdev_webhook_secret_env") or DEFAULT_GDEV_WEBHOOK_SECRET_ENV
        ).strip()
        if not gdev_webhook_secret_env:
            raise GdevAgentPayloadError("gdev_webhook_secret_env is required")
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
        gdev_base_url=gdev_base_url,
        gdev_tenant_slug=gdev_tenant_slug,
        gdev_tenant_id=gdev_tenant_id,
        gdev_webhook_secret_env=gdev_webhook_secret_env,
    )


async def run_gdev_webhook_eval(
    payload: dict[str, Any],
    *,
    attempt_number: int,
    transport: Callable[[str, bytes, dict[str, str]], LocalGdevHttpResponse] | None = None,
) -> dict[str, Any]:
    started = time.perf_counter()
    case_payload = validate_gdev_webhook_eval_payload(payload)
    request_hash = payload_sha256(case_payload.request)
    if case_payload.mode == "local":
        live_response = await _invoke_local_gdev(case_payload, transport=transport)
        normalized_fields = _normalize_live_response(
            case_id=case_payload.case_id,
            response=live_response,
            measured_latency_ms=max(0, int((time.perf_counter() - started) * 1000)),
        )
        sanitized_response = _sanitized_live_response(
            case_id=case_payload.case_id,
            http_status=live_response.status_code,
            normalized_fields=normalized_fields,
        )
    else:
        normalized_fields = _normalize_request(case_payload.request)
        sanitized_response = _sanitized_response(case_payload.case_id, normalized_fields)
    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    quality_status = _quality_status(normalized_fields)
    artifact_payload = {
        "case_id": case_payload.case_id,
        "gdev_case_id": case_payload.case_id,
        "candidate_id": case_payload.candidate_id,
        "request_hash": request_hash,
        "sanitized_response": sanitized_response,
        "normalized_fields": normalized_fields,
        "runtime_status": "completed",
        "status": "completed",
        "quality_status": quality_status,
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
        "quality_status": quality_status,
        "eval_result_path": str(case_payload.eval_result_path),
        "artifact_payload": artifact_payload,
    }


def _required_str(payload: dict[str, Any], key: str) -> str:
    value = str(payload.get(key) or "").strip()
    if not value:
        raise GdevAgentPayloadError(f"{key} is required")
    return value


def _validate_local_base_url(value: str) -> str:
    parsed = parse.urlparse(value)
    if parsed.scheme != "http":
        raise GdevAgentPayloadError("gdev_base_url must use http for local proof")
    if parsed.hostname not in LOCAL_GDEV_HOSTS:
        raise GdevAgentPayloadError("gdev_base_url must point to localhost or loopback")
    if parsed.username or parsed.password:
        raise GdevAgentPayloadError("gdev_base_url must not include credentials")
    if parsed.path not in {"", "/"}:
        raise GdevAgentPayloadError("gdev_base_url must not include a path")
    return value.rstrip("/")


async def _invoke_local_gdev(
    case_payload: GdevWebhookEvalPayload,
    *,
    transport: Callable[[str, bytes, dict[str, str]], LocalGdevHttpResponse] | None,
) -> LocalGdevHttpResponse:
    if case_payload.gdev_base_url is None:
        raise GdevAgentPayloadError("gdev_base_url is required")
    body_payload = _build_local_webhook_payload(case_payload)
    body = json.dumps(body_payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    webhook_secret = _webhook_secret_from_env(case_payload.gdev_webhook_secret_env)
    headers = _signed_headers(
        body=body,
        tenant_slug=_required_local_value(case_payload.gdev_tenant_slug, "gdev_tenant_slug"),
        webhook_secret=webhook_secret,
    )
    post = transport or _post_signed_json_sync
    return await asyncio.to_thread(
        post,
        f"{case_payload.gdev_base_url}/webhook",
        body,
        headers,
    )


def _build_local_webhook_payload(case_payload: GdevWebhookEvalPayload) -> dict[str, Any]:
    text = case_payload.request.get("text")
    if not isinstance(text, str) or not text.strip():
        raise GdevAgentPayloadError("request.text is required for local gdev proof")
    metadata = case_payload.request.get("metadata")
    payload_metadata = dict(metadata) if isinstance(metadata, Mapping) else {}
    payload_metadata["eval_case_id"] = case_payload.case_id
    return {
        "request_id": _optional_string(case_payload.request.get("request_id"))
        or case_payload.case_id,
        "tenant_id": _required_local_value(case_payload.gdev_tenant_id, "gdev_tenant_id"),
        "message_id": _optional_string(case_payload.request.get("message_id"))
        or case_payload.case_id,
        "user_id": _optional_string(case_payload.request.get("user_id")),
        "text": text,
        "metadata": payload_metadata,
    }


def _required_local_value(value: str | None, key: str) -> str:
    if value is None or not value.strip():
        raise GdevAgentPayloadError(f"{key} is required")
    return value


def _webhook_secret_from_env(env_name: str | None) -> str:
    name = _required_local_value(env_name, "gdev_webhook_secret_env")
    webhook_secret = os.environ.get(name)
    if not webhook_secret:
        raise GdevAgentPayloadError(f"configured webhook secret env var is missing: {name}")
    return webhook_secret


def _signed_headers(
    *,
    body: bytes,
    tenant_slug: str,
    webhook_secret: str,
) -> dict[str, str]:
    signature = (
        "sha256="
        + hmac.new(
            webhook_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()
    )
    return {
        "Content-Type": "application/json",
        "X-Tenant-Slug": tenant_slug,
        "X-Webhook-Signature": signature,
    }


def _post_signed_json_sync(
    url: str,
    body: bytes,
    headers: dict[str, str],
) -> LocalGdevHttpResponse:
    http_request = request.Request(url, data=body, headers=headers, method="POST")
    try:
        with request.urlopen(http_request, timeout=30) as response:
            raw_body = response.read().decode("utf-8")
            return LocalGdevHttpResponse(
                status_code=response.status,
                output=_decode_json_body(raw_body),
            )
    except error.HTTPError as exc:
        raw_body = exc.read().decode("utf-8")
        return LocalGdevHttpResponse(
            status_code=exc.code,
            output=_decode_json_body(raw_body),
        )
    except (error.URLError, TimeoutError, http_client.HTTPException, OSError) as exc:
        return LocalGdevHttpResponse(
            status_code=599,
            output={
                "detail": f"{exc.__class__.__name__}: {exc}",
                "error_type": exc.__class__.__name__,
            },
        )


def _decode_json_body(raw_body: str) -> Any:
    if not raw_body:
        return None
    try:
        return json.loads(raw_body)
    except json.JSONDecodeError:
        return {"detail": raw_body}


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


def _normalize_live_response(
    *,
    case_id: str,
    response: LocalGdevHttpResponse,
    measured_latency_ms: int,
) -> dict[str, Any]:
    body = response.output
    if not isinstance(body, Mapping):
        return _invalid_live_output(
            case_id=case_id,
            reason="response body is not a structured object",
            latency_ms=measured_latency_ms,
        )
    if response.status_code >= 400:
        return _adapter_error_fields(
            case_id=case_id,
            body=body,
            latency_ms=measured_latency_ms,
        )
    required = _extract_required_fields(body)
    missing = [
        field
        for field in ("status", "category", "confidence", "requires_human")
        if field not in required
    ]
    if missing:
        return _invalid_live_output(
            case_id=case_id,
            reason=f"missing required fields: {', '.join(missing)}",
            latency_ms=measured_latency_ms,
        )
    status = required["status"]
    category = required["category"]
    confidence = _optional_float(required["confidence"])
    requires_human = required["requires_human"]
    if (
        not isinstance(status, str)
        or status not in GDEV_STATUSES
        or not isinstance(category, str)
        or not category
        or confidence is None
        or not isinstance(requires_human, bool)
    ):
        return _invalid_live_output(
            case_id=case_id,
            reason="invalid required field types or values",
            latency_ms=measured_latency_ms,
        )
    return {
        "case_id": case_id,
        "status": status,
        "category": category,
        "confidence": confidence,
        "requires_human": requires_human,
        "risk_reason": _extract_risk_reason(body),
        "guard_blocked": _optional_bool(body.get("guard_blocked"), default=status == "blocked"),
        "invalid_structured_output": False,
        "unsafe_auto_approval": _optional_bool(
            body.get("unsafe_auto_approval"),
            default=False,
        ),
        "cost_usd": _extract_cost(body),
        "latency_ms": measured_latency_ms,
        "adapter_error": status == "error",
    }


def _extract_required_fields(body: Mapping[str, Any]) -> dict[str, Any]:
    required: dict[str, Any] = {}
    status = body.get("status")
    if status is not None:
        required["status"] = status
    classification = body.get("classification")
    if isinstance(classification, Mapping):
        category = body.get("category", classification.get("category"))
        confidence = body.get("confidence", classification.get("confidence"))
    else:
        category = body.get("category")
        confidence = body.get("confidence")
    if category is not None:
        required["category"] = category
    if confidence is not None:
        required["confidence"] = confidence
    if "requires_human" in body:
        required["requires_human"] = body["requires_human"]
    elif isinstance(classification, Mapping) and isinstance(status, str):
        required["requires_human"] = _derive_requires_human(status, body)
    return required


def _derive_requires_human(status: str, body: Mapping[str, Any]) -> bool:
    if status in {"blocked", "error", "pending"}:
        return True
    if body.get("pending") is not None:
        return True
    action = body.get("action")
    return isinstance(action, Mapping) and action.get("risky") is True


def _adapter_error_fields(
    *,
    case_id: str,
    body: Mapping[str, Any],
    latency_ms: int,
) -> dict[str, Any]:
    reason = _extract_error_reason(body)
    if _is_guard_block_reason(reason):
        return {
            "case_id": case_id,
            "status": "blocked",
            "category": "guard_blocked",
            "confidence": 0.0,
            "requires_human": True,
            "risk_reason": reason,
            "guard_blocked": True,
            "invalid_structured_output": False,
            "unsafe_auto_approval": False,
            "cost_usd": _extract_cost(body),
            "latency_ms": latency_ms,
            "adapter_error": False,
        }
    return {
        "case_id": case_id,
        "status": "error",
        "category": "adapter_error",
        "confidence": 0.0,
        "requires_human": True,
        "risk_reason": reason,
        "guard_blocked": False,
        "invalid_structured_output": False,
        "unsafe_auto_approval": False,
        "cost_usd": _extract_cost(body),
        "latency_ms": latency_ms,
        "adapter_error": True,
    }


def _invalid_live_output(*, case_id: str, reason: str, latency_ms: int) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "status": "error",
        "category": "invalid_structured_output",
        "confidence": 0.0,
        "requires_human": True,
        "risk_reason": reason,
        "guard_blocked": False,
        "invalid_structured_output": True,
        "unsafe_auto_approval": False,
        "cost_usd": None,
        "latency_ms": latency_ms,
        "adapter_error": False,
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


def _sanitized_live_response(
    *,
    case_id: str,
    http_status: int,
    normalized_fields: dict[str, Any],
) -> dict[str, Any]:
    visible_fields = {
        "case_id": case_id,
        "http_status": http_status,
        "status": normalized_fields["status"],
        "category": normalized_fields["category"],
        "requires_human": normalized_fields["requires_human"],
        "guard_blocked": normalized_fields["guard_blocked"],
        "adapter_error": normalized_fields["adapter_error"],
        "invalid_structured_output": normalized_fields["invalid_structured_output"],
    }
    return {
        **visible_fields,
        "response_hash": payload_sha256(visible_fields),
    }


def _quality_status(normalized_fields: dict[str, Any]) -> str:
    if normalized_fields.get("adapter_error") or normalized_fields.get("invalid_structured_output"):
        return "fail"
    return "pass"


def _extract_cost(body: Mapping[str, Any]) -> float | None:
    cost = _optional_float(body.get("cost_usd"))
    if cost is not None:
        return cost
    usage = body.get("usage")
    if not isinstance(usage, Mapping):
        return None
    return _optional_float(usage.get("estimated_cost_usd"))


def _extract_risk_reason(body: Mapping[str, Any]) -> str:
    reason = _optional_string(body.get("risk_reason"))
    if reason:
        return reason
    action = body.get("action")
    if isinstance(action, Mapping):
        reason = _optional_string(action.get("risk_reason"))
        if reason:
            return reason
    pending = body.get("pending")
    if isinstance(pending, Mapping):
        reason = _optional_string(pending.get("reason"))
        if reason:
            return reason
    return ""


def _extract_error_reason(body: Mapping[str, Any]) -> str:
    reason = _optional_string(body.get("detail"))
    if reason:
        return reason
    return _optional_string(body.get("error") or body.get("message") or "http error")


def _is_guard_block_reason(reason: str) -> bool:
    lowered = reason.lower()
    return "guard" in lowered or "injection" in lowered


def _optional_bool(value: Any, *, default: bool) -> bool:
    return value if isinstance(value, bool) else default


def _optional_float(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        return None
    number = float(value)
    if number < 0:
        return None
    return number


def _optional_string(value: Any) -> str:
    return value if isinstance(value, str) else ""


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
