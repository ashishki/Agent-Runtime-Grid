# Case Study - Agent Runtime Grid

## Problem

AI and agent workloads often begin as scripts. Scripts are hard to trust once the workload becomes a batch: operators need durable state, queue-backed dispatch, retry boundaries, timeout behavior, cancellation, artifacts, cost control, and evidence that the run behaved as expected.

Agent Runtime Grid provides a local-first T1 execution runtime for running many AI, agent, and evaluation jobs with deterministic control-plane behavior.

## Architecture

The runtime path is:

```text
API / CLI
  -> Postgres job registry and event log
  -> Redis Streams dispatch
  -> bounded workers
  -> job runners
  -> artifacts, metrics, traces, and reports
```

Postgres is the lifecycle authority. Redis Streams is delivery state. Workers execute known local job types and write terminal state through an idempotent finalization guard. Artifacts are written to local storage with SHA-256, size, input digest, job ID, run ID, attempt number, and created-at evidence.

## Reliability

Implemented reliability mechanics:

- idempotency-key replay and conflict detection
- Redis Streams publish, lease, acknowledge, retry, and DLQ behavior
- worker state transitions for submitted, running, completed, failed, timed out, and cancelled jobs
- stale lease recovery for workers that exit after lease and before acknowledgement
- duplicate terminal finalization prevention through a database uniqueness guard
- budget-blocked terminal events for dispatch or retry projection failures
- queue/backpressure inspection from Redis and Postgres state

## Benchmark

The real smoke command runs 100 jobs through local Redis Streams, workers, Postgres state, artifact generation, validation, and report rendering:

```bash
python -m agent_runtime_grid.cli smoke \
  --jobs 100 \
  --workers 4 \
  --failure-rate 0 \
  --mode stub \
  --report reports/smoke.md
```

The v1 reliability proof runs 500 jobs with worker concurrency, controlled failures, timeout cases, repeated idempotency submissions, artifacts, and runtime-state report generation:

```bash
python -m agent_runtime_grid.cli benchmark v1-proof \
  --jobs 500 \
  --workers 20 \
  --failure-rate 0.10 \
  --include-timeouts \
  --repeat-idempotency-submissions \
  --report reports/v1/reliability_report.md
```

Current local baseline: 80 passing tests with one upstream FastAPI/Starlette deprecation warning.

## Failure

Failure evidence is packaged by:

```bash
python -m agent_runtime_grid.cli failure-reports write-pack \
  --output-dir reports/failure-injection
```

The report pack covers:

- transient retry
- timeout
- cancellation
- stale worker recovery
- duplicate finalization prevention
- DLQ routing

Each report includes scenario, command, expected behavior, actual lifecycle, event trail, metrics, artifact evidence, and known limits.

## Integrations

Eval-Ground-Truth-Lab integration uses `eval_lab_case` jobs. Runtime Grid loads JSONL cases, executes deterministic local evaluation work, writes runtime artifacts, and cross-links Eval Lab result paths without importing or hardcoding a sibling checkout.

gdev-agent integration uses `gdev_webhook_eval` jobs. Runtime Grid runs deterministic local webhook evaluation cases through the same queue and worker path, stores request hashes and sanitized responses, writes normalized fields, and cross-links Eval Lab-compatible result output.

The current full-stack artifact proof command connects ready artifacts from both
adjacent projects:

```bash
python -m agent_runtime_grid.cli proof full-stack \
  --eval-lab-dataset ../Eval-Ground-Truth-Lab/datasets/gdev_agent/triage_v1.jsonl \
  --eval-lab-report ../Eval-Ground-Truth-Lab/reports/gdev-agent/baseline_report.md \
  --gdev-artifact ../gdev-agent/eval/results/last_run.json \
  --jobs 20 \
  --workers 4 \
  --report reports/full-stack/runtime_report.md
```

That command validates the Eval Lab and gdev-agent evidence paths, submits
selected cases as Grid jobs, runs them through Redis Streams and workers, writes
artifacts and Eval-compatible result JSON, and produces one runtime report that
cross-links quality evidence with lifecycle, artifact, idempotency, and
queue/backpressure evidence.

It is artifact-linked proof by default, not live HTTP end to end. The optional
`proof full-stack-live-local` mode makes workers call a locally running
`gdev-agent` `/webhook` endpoint with operator-supplied localhost config and a
webhook secret read from an environment variable.

## Trade-offs

This project is intentionally not a Temporal, Ray, Kubernetes, Airflow, or managed batch platform replacement. It proves local T1 reliability mechanics and evidence paths, not remote production orchestration.

The runtime uses at-least-once delivery with idempotent finalization, not exactly-once execution. Redis Streams can redeliver; Postgres finalization decides terminal lifecycle truth.

## Production

Before remote or trusted production operation, the runtime would need:

- deployment-grade auth and configuration management
- remote CI evidence for full 500-job reliability proof
- durable artifact storage beyond local filesystem
- production-grade worker process supervision and runbook automation
- explicit egress and secret allowlists per job type
- migration workflow and schema versioning
- dashboards and runbooks for on-call operation
- resource isolation for untrusted or third-party job code
