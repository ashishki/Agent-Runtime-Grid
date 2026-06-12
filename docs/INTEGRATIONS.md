# Integrations

Agent Runtime Grid keeps integrations as normal job types that run through the same queue, worker, artifact, budget, and report mechanics as stub jobs.

## Eval-Ground-Truth-Lab

Job type: `eval_lab_case`

Payload fields:

- `dataset_path`: JSONL dataset path. Relative paths are supported and preferred for portable runs.
- `case_id`: case identifier to load from the JSONL dataset.
- `candidate_id`: candidate system/version label. `candidate` is accepted as a compatibility alias.
- `mode`: `stub`, `local`, or `stub-or-local-http`.
- `eval_result_path`: optional path for the Eval Lab result JSON. If omitted, the runtime uses `reports/eval-lab/{candidate_id}/{case_id}.json`.

Runtime behavior:

- The worker loads the case from JSONL without importing the Eval-Ground-Truth-Lab checkout.
- The default path performs deterministic local work only and makes no paid model calls.
- The completed runtime artifact includes case ID, candidate ID, dataset path, runtime status, Eval Lab result path, quality status, attempt count, and latency.
- The runtime artifact metadata is still validated for path, SHA-256, size, job ID, run ID, attempt number, input digest, and created-at.
- When `eval_result_path` is supplied, the Eval Lab result JSON is updated with `runtime_artifact_path` so downstream reports can cross-link back to Runtime Grid evidence.

Evidence:

- `tests/integration/test_eval_lab_integration.py`

## gdev-agent

Job type: `gdev_webhook_eval`

Payload fields:

- `case_id`: gdev-agent evaluation case ID.
- `candidate_id`: candidate system/version label. `candidate` is accepted as a compatibility alias.
- `mode`: `stub` or `local`.
- `request`: webhook-style request object. Runtime artifacts store a request hash, not the raw request.
- `eval_result_path`: optional path for Eval Lab-compatible result JSON.

Runtime behavior:

- The default path is deterministic and local. It does not call paid model providers.
- The runner computes a request hash, deterministic normalized fields, and a sanitized response.
- Runtime artifacts include request hash, sanitized response, normalized fields, timing, attempt count, runtime status, quality status, and Eval Lab result path.
- Eval result JSON receives `runtime_artifact_path`, so Eval Lab output and Runtime Grid reliability evidence cross-link on the same case ID.

Evidence:

- `tests/integration/test_gdev_agent_integration.py`
