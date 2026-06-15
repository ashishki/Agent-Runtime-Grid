# Evidence Index - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-14

Purpose:

- Index durable proof so operators and maintainers can retrieve prior evidence quickly.
- Avoid repeated archaeology across tests, benchmark reports, and manual checks.

This file is not authoritative by itself. Every row must point to the real artifact that carries the evidence.

---

## When To Use

Maintain this file for:

- Runtime verification records for risky or boundary-changing tasks.
- Load-test and failure-injection reports.
- Cost telemetry reports once T12 exists.

---

## Evidence Table

| Topic / Finding / Task | Artifact type | Location | Scope covered | Last verified | Canonical? |
|------------------------|---------------|----------|---------------|---------------|------------|
| T04 job repository | integration tests | `tests/integration/test_job_repository.py` | Postgres job creation, submitted event append, idempotency-key replay and conflict behavior | 2026-06-11 | Yes |
| T05 queue adapter | integration tests | `tests/integration/test_queue_adapter.py` | Redis Streams publish, lease, acknowledge, and DLQ behavior | 2026-06-11 | Yes |
| T06 worker lifecycle | integration tests | `tests/integration/test_worker_lifecycle.py` | Stub worker success, transient retry/requeue, and policy failure state transitions | 2026-06-11 | Yes |
| T07 idempotent finalization | integration tests | `tests/integration/test_idempotent_finalization.py` | Racing terminal finalization, replayed queue no-op, and duplicate-finalization metric invariant | 2026-06-11 | Yes |
| T08 artifacts and logs | integration tests | `tests/integration/test_artifacts.py`, `tests/integration/test_logging.py` | JSON artifact write/metadata hashing and sanitized structured job log records | 2026-06-11 | Yes |
| T09 timeout and cancellation | integration tests | `tests/integration/test_timeout_cancellation.py` | Timed-out jobs, queued cancellation, and running cancellation terminal paths | 2026-06-11 | Yes |
| T10 observability | integration tests | `tests/integration/test_metrics.py`, `tests/integration/test_tracing.py`, `tests/integration/test_observability_safety.py` | Required metric exposure, linked trace spans, and observability secret/payload filtering | 2026-06-11 | Yes |
| T11 failure injection | integration tests | `tests/integration/test_failure_injection.py` | Fixed-seed failure plan reproducibility, retry mapping, and zero-cost stub mode | 2026-06-11 | Yes |
| T12 cost telemetry | integration tests | `tests/integration/test_cost_telemetry.py` | Required cost fields, budget-block event, and cost rollup report output | 2026-06-11 | Yes |
| T13 CLI batch workflow | integration tests | `tests/integration/test_cli_batch.py` | Batch submission count/run ID, lifecycle status formatting, and cleanup preserving metadata | 2026-06-11 | Yes |
| T14 load benchmark harness | load tests | `tests/load/test_benchmark_harness.py`, `reports/.gitkeep` | Smoke report generation, v1 proof config, and required reliability report fields | 2026-06-11 | Yes |
| T15 root operator docs | documentation | `README.md`, `docs/KNOWN_LIMITS.md`, `reports/README.md` | Operator overview, quickstart path, report locations, and explicit known limits | 2026-06-12 | Yes |
| T16 real smoke command | integration tests, CLI check | `tests/integration/test_smoke_command.py`, `src/agent_runtime_grid/cli/smoke.py`, `reports/smoke.md` | Real 100-job smoke path through Postgres, Redis Streams, workers, artifacts, validation, and runtime-state report generation | 2026-06-12 | Yes |
| T17 real 500-job reliability proof | load tests, CLI check | `tests/load/test_reliability_proof.py`, `src/agent_runtime_grid/cli/benchmark.py`, `reports/v1/reliability_report.md` | Real 500-job proof path through Postgres, Redis Streams, workers, injected failures, timeout cases, idempotency replay, artifacts, validation, and runtime-state report generation | 2026-06-12 | Yes |
| T18 stale lease recovery | integration tests, documentation | `tests/integration/test_stale_lease_recovery.py`, `src/agent_runtime_grid/worker/recovery.py`, `docs/FAILURE_MODES.md` | Redis pending stale lease detection, DB-authoritative recovery, exact requeue per recovery cycle, DLQ exhaustion, preserved event trail, and idempotent terminal finalization | 2026-06-12 | Yes |
| T19 queue/backpressure metrics | integration and load tests, documentation | `tests/integration/test_queue_metrics.py`, `tests/load/test_reliability_proof.py::test_reports_include_backpressure_section`, `src/agent_runtime_grid/queue/inspection.py`, `docs/OBSERVABILITY.md` | Runtime-derived queue depth, oldest pending age, consumer lag, leased/running jobs, worker utilization, retry rate, DLQ count, p95 queue wait, p95 execution duration, Prometheus gauges, and report section | 2026-06-12 | Yes |
| T20 API auth boundary | integration tests, documentation | `tests/integration/test_auth_boundary.py`, `src/agent_runtime_grid/api/app.py`, `src/agent_runtime_grid/api/routes/jobs.py`, `docs/SECURITY_BOUNDARIES.md` | Secret-free public health, token-required mutation and inspection routes when configured, and localhost-only no-token API mode | 2026-06-12 | Yes |
| T21 artifact report integrity | integration tests | `tests/integration/test_artifact_report_integrity.py`, `src/agent_runtime_grid/artifacts/store.py`, `src/agent_runtime_grid/cli/benchmark.py`, `src/agent_runtime_grid/cli/smoke.py` | Artifact metadata fields for path, SHA-256, size, job ID, run ID, attempt number, input digest, created-at; report integrity rows; missing/hash-mismatched artifact failure path | 2026-06-12 | Yes |
| T22 cost budget gates | integration tests, CLI check, documentation | `tests/integration/test_budget_enforcement.py`, `src/agent_runtime_grid/cost/telemetry.py`, `src/agent_runtime_grid/cost/rollup.py`, `src/agent_runtime_grid/worker/loop.py`, `docs/COST_BUDGET.md` | Stub provider-call blocking, live dispatch budget requirements, retry-budget block with `budget_blocked` event, and strict cost rollup non-zero threshold behavior | 2026-06-12 | Yes |
| T23 Eval Lab integration | integration tests, documentation | `tests/integration/test_eval_lab_integration.py`, `src/agent_runtime_grid/jobs/eval_lab.py`, `src/agent_runtime_grid/artifacts/store.py`, `docs/INTEGRATIONS.md` | `eval_lab_case` payload validation, queued worker execution, cross-linked runtime artifact and Eval Lab result paths, and no fixed checkout coupling | 2026-06-12 | Yes |
| T24 gdev-agent batch simulation | integration tests, documentation | `tests/integration/test_gdev_agent_integration.py`, `src/agent_runtime_grid/jobs/gdev_agent.py`, `docs/INTEGRATIONS.md` | 50-job deterministic gdev webhook batch, zero provider calls by default, request hash, sanitized response, normalized fields, runtime timing, attempts, status, and Eval Lab cross-links | 2026-06-12 | Yes |
| T25 failure report pack | integration tests, CLI check, reports | `tests/integration/test_failure_report_pack.py`, `src/agent_runtime_grid/cli/failure_reports.py`, `reports/failure-injection/*.md`, `docs/FAILURE_MODES.md` | Markdown reports for transient retry, timeout, cancellation, stale worker recovery, duplicate finalization prevention, and DLQ routing with lifecycle validation | 2026-06-12 | Yes |
| T26 case study packaging | documentation | `docs/CASE_STUDY.md`, `docs/ARCHITECTURE_DIAGRAM.md`, `docs/KNOWN_LIMITS.md`, `README.md` | Problem, architecture, reliability, benchmark, failure, trade-offs, production changes, runtime diagram, integration points, and final packaging pointers | 2026-06-12 | Yes |
| T27 lease renewal and operator repair CLI | integration tests, CLI check, documentation | `tests/integration/test_operator_repair_cli.py`, `src/agent_runtime_grid/queue/redis_streams.py`, `src/agent_runtime_grid/cli/operator.py`, `docs/OPERATIONS.md` | Redis pending-entry lease renewal, operator queue inspection without payload exposure, stale recovery command output, and replacement-worker completion after repair | 2026-06-12 | Yes |
| T28 automated worker heartbeat lease renewal | integration tests, documentation | `tests/integration/test_worker_heartbeat.py`, `src/agent_runtime_grid/worker/loop.py`, `docs/OPERATIONS.md`, `docs/FAILURE_MODES.md` | Active worker heartbeat prevents false stale recovery for long jobs, stops after terminal acknowledgement, and disabled heartbeat preserves stale recovery behavior for failure injection | 2026-06-12 | Yes |
| T29 cross-project runtime proof | integration tests, CLI command, documentation | `tests/integration/test_full_stack_proof.py`, `src/agent_runtime_grid/cli/proof.py`, `docs/INTEGRATIONS.md`, `README.md` | Ready Eval Lab dataset/report and gdev-agent artifact path validation, selected case submission as Grid jobs, Redis Streams worker processing, artifact integrity, queue/backpressure report fields, and secret-like request field exclusion | 2026-06-14 | Yes |
| T30 stack overview and committed evidence snapshots | documentation | `docs/STACK_OVERVIEW.md`, `docs/evidence/*.md`, `README.md`, `reports/README.md` | Maps three-project stack, names current default mode as full-stack artifact proof, and commits stable evidence snapshots outside ignored generated reports | 2026-06-14 | Yes |
| T31 full-stack live-local proof | integration tests, CLI command, documentation | `tests/integration/test_full_stack_proof.py`, `tests/integration/test_gdev_agent_integration.py`, `src/agent_runtime_grid/cli/proof.py`, `src/agent_runtime_grid/jobs/gdev_agent.py`, `docs/INTEGRATIONS.md` | Optional localhost gdev-agent `/webhook` execution through Grid workers with operator-supplied local config, env-only webhook secret lookup, sanitized artifacts, and no Runtime Grid live model calls | 2026-06-14 | Yes |
| T32 operator-run live-local snapshot | local proof, documentation | `docs/evidence/full-stack-live-local.md`, `.gitignore` | Operator-run local gdev-agent demo-mode proof completed 20/20 queued HTTP jobs through Runtime Grid and fixed generated full-stack report ignore rules | 2026-06-15 | Yes |

---

## Report Paths

| Report | Location | Status | Notes |
|--------|----------|--------|-------|
| Current smoke harness report | `reports/load_smoke.md` | implemented harness output | Generated locally; contents ignored by git. |
| 100-job smoke report | `reports/smoke.md` | implemented in T16 | Generated from actual runtime state. Contents ignored by git. |
| 100-job smoke snapshot | `docs/evidence/runtime-smoke-100.md` | committed evidence snapshot | Stable summary and rerun command for the ignored generated smoke report. |
| 500-job reliability proof | `reports/v1/reliability_report.md` | implemented in T17; backpressure section added in T19; artifact integrity rows added in T21 | Includes lifecycle, retry, timeout, DLQ, idempotency, artifact integrity, queue lag, execution duration, backpressure, and cost evidence. Contents ignored by git. |
| 500-job reliability snapshot | `docs/evidence/runtime-reliability-500.md` | committed evidence snapshot | Stable summary and rerun command for the ignored generated reliability report. |
| Stale lease recovery proof | `tests/integration/test_stale_lease_recovery.py` | implemented in T18; report included in T25 | Executable proof for worker crash after lease plus human-readable failure report coverage. |
| Failure injection report pack | `reports/failure-injection/*.md` | implemented in T25 | Includes scenario, command, expected behavior, actual lifecycle, event trail, metrics, artifacts, and known limits. |
| Failure injection snapshot | `docs/evidence/failure-injection-pack-summary.md` | committed evidence snapshot | Stable summary of the generated failure-injection pack. |
| Full-stack artifact proof | `reports/full-stack/runtime_report.md` | implemented in T29 | Generated from selected Eval Lab/gdev artifacts run through Grid; contents ignored by git. |
| Full-stack artifact snapshot | `docs/evidence/full-stack-artifact-proof.md` | committed evidence snapshot | Stable summary and rerun command for current cross-project artifact proof; live-local mode is a separate optional proof. |
| Full-stack live-local proof | `reports/full-stack/live_local_runtime_report.md` | implemented in T31 | Generated by selected Eval Lab/gdev cases run through Grid workers that call local gdev-agent `/webhook`; contents ignored by git. |
| Full-stack live-local snapshot | `docs/evidence/full-stack-live-local.md` | committed evidence snapshot | Stable summary, boundary notes, rerun command, and 2026-06-15 operator-run result for optional local HTTP proof mode. |

---

## Retrieval Rules

- Prefer rows that match the current task's `Context-Refs`, open findings, or active capability tags.
- If an evidence row points to a stale or missing artifact, fix the artifact or remove the row.
- Do not treat a journal note as proof when a test, eval, audit, or report exists.
