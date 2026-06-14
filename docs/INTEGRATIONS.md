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

## Full-Stack Artifact Proof

Command:

```bash
python -m agent_runtime_grid.cli proof full-stack \
  --eval-lab-dataset ../Eval-Ground-Truth-Lab/datasets/gdev_agent/triage_v1.jsonl \
  --eval-lab-report ../Eval-Ground-Truth-Lab/reports/gdev-agent/baseline_report.md \
  --gdev-artifact ../gdev-agent/eval/results/last_run.json \
  --jobs 20 \
  --workers 4 \
  --report reports/full-stack/runtime_report.md
```

Runtime behavior:

- The command validates the Eval Lab dataset path, Eval Lab quality report path, and gdev-agent artifact path before submitting work.
- Selected Eval Lab cases are converted into deterministic `gdev_webhook_eval` jobs.
- Jobs run through the same Redis Streams queue, worker lifecycle, Postgres state, artifact store, and report validation as other Grid workloads.
- The generated report links the Eval Lab quality report, the gdev-agent artifact path, the Grid run ID, lifecycle counts, artifact integrity rows, queue/backpressure metrics, and known limits.
- The default proof does not call gdev-agent over HTTP and does not make live model calls.
- Runtime artifacts store request hashes and sanitized responses, not raw secret-like request fields.

This is the current `full-stack-artifact-proof` mode. The CLI command remains
`proof full-stack` for compatibility, but the proof is a deterministic
cross-project artifact replay through Runtime Grid workers.

## Full-Stack Live-Local Mode

Command:

```bash
python -m agent_runtime_grid.cli proof full-stack-live-local \
  --eval-lab-dataset ../Eval-Ground-Truth-Lab/datasets/gdev_agent/triage_v1.jsonl \
  --eval-lab-report ../Eval-Ground-Truth-Lab/reports/gdev-agent/baseline_report.md \
  --gdev-artifact ../gdev-agent/eval/results/last_run.json \
  --gdev-base-url http://localhost:8000 \
  --gdev-webhook-secret-env GDEV_AGENT_WEBHOOK_SECRET \
  --jobs 20 \
  --workers 4 \
  --report reports/full-stack/live_local_runtime_report.md
```

Runtime behavior:

- The command uses the same Grid queue, worker lifecycle, Postgres state,
  artifact store, and reliability report path as artifact proof.
- Selected Eval Lab cases become `gdev_webhook_eval` jobs with `mode=local`.
- The worker calls only the operator-configured local `gdev-agent` base URL plus
  `/webhook`; dataset cases cannot define network destinations or commands.
- Webhook signing uses the configured environment-variable name. The secret
  value is not stored in job payloads, artifacts, or reports.
- Runtime Grid does not make live model calls. For reproducible evidence,
  `gdev-agent` should run in deterministic demo mode.
- Artifacts store request hashes, sanitized responses, normalized fields,
  timing, and Eval-compatible result paths.

Evidence:

- `tests/integration/test_full_stack_proof.py`
- `tests/integration/test_gdev_agent_integration.py`
- `src/agent_runtime_grid/cli/proof.py`
