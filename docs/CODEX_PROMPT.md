# CODEX_PROMPT.md

Version: 1.0
Date: 2026-06-12
Phase: 8

This file is the project handoff state for Codex sessions. Repository files, tests, audit reports, and CI results are authoritative.

---

## Current State

- **Project:** Agent Runtime Grid
- **Mode:** Standard
- **Phase:** 8
- **Baseline:** 71 passing tests after T25 (`python -m pytest -q`)
- **Ruff:** configured in T01; `ruff check` and `ruff format --check` pass locally
- **Last CI run:** not yet run
- **Last updated:** 2026-06-12
- **Session tokens (approx):** not tracked
- **Cumulative phase tokens (approx):** not tracked
- **Session cost (approx):** not tracked
- **Cumulative phase cost (approx):** not tracked
- **Budget status:** within roadmap planning budget; default runtime remains stub mode with $0 model cost

---

## Continuity Pointers

- **Architecture:** `docs/ARCHITECTURE.md`
- **Implementation contract:** `docs/IMPLEMENTATION_CONTRACT.md`
- **Tasks:** `docs/tasks.md`
- **Decision log:** `docs/DECISION_LOG.md`
- **Implementation journal:** `docs/IMPLEMENTATION_JOURNAL.md`
- **Evidence index:** `docs/EVIDENCE_INDEX.md`
- **Cost budget:** `docs/COST_BUDGET.md`
- **Audit reports:** `docs/audit/`
- **Task-scoped context:** read `Context-Refs` in `docs/tasks.md` before broad searching

---

## Instructions for Codex

Before starting any implementation task:

1. Read `docs/IMPLEMENTATION_CONTRACT.md`.
2. Read this file and identify `Next Task`.
3. Read the matching task block in `docs/tasks.md`.
4. Read only the task's `Context-Refs` unless architecture, runtime, cost, security, or open findings require broader context.
5. Run the current baseline command before editing once T03 establishes it; before T03, run the most specific available tests named by the task.
6. Run `ruff check`, `ruff format --check`, and task-specific tests before marking a task ready for review once those commands exist.
7. Update this file and `docs/IMPLEMENTATION_JOURNAL.md` at phase boundaries or when a task materially changes baseline, cost, runtime, or open findings.

Implementation agents do not self-review meaningful changes. Review findings are resolved through follow-up tasks or explicit fix-queue items.

---

## Next Task

**Post-Review State**

Narrow task digest:

- T01-T26 are complete and final Phase 8 review passed.
- Next operator action is commit/push or future roadmap planning.
- Do not add live model calls.
- Current baseline is 71 passing tests after T26 and final review.

---

## Fix Queue

empty

---

## Correction Budget

- Max implementation correction turns: 2.
- Max test-healing turns: 2 for normal tasks.
- Escalate after repeated equivalent failure output, increased failure count, out-of-scope file need, budget exhaustion, or any proposal to weaken tests or acceptance criteria.
- Preserve command output and changed-file evidence before any correction turn.

---

## Cost Budget State

- Budget artifact: `docs/COST_BUDGET.md`
- Telemetry source: `src/agent_runtime_grid/cost/telemetry.py`
- Last rollup: not run
- Default stub run budget: $0 model cost
- Optional live LLM benchmark target: below $5 per full benchmark run
- Per-job budget: configurable by job type; enforcement planned in T22
- Monthly project budget: unknown; requires human approval before any recurring live LLM usage
- Approval required before: live LLM mode, model escalation, fan-out increase, retry expansion, tool-call expansion, external egress, or budget overrun
- Last recorded AI/model cost: none

If the next task would exceed the declared budget, increase model class, increase retry/fan-out/tool-call limits, add recurring AI usage, or enable external egress, stop for approval before implementation.

---

## Open Findings

none

---

## Profile State: RAG

- RAG Status: OFF
- Active corpora: n/a
- Retrieval baseline: n/a
- Open retrieval findings: none
- Index schema version: n/a
- Pending reindex actions: none
- Retrieval-related next tasks: none
- Retrieval-driven tasks: none

---

## Tool-Use State

- Tool-Use Profile: OFF
- Registered tool schemas: n/a
- Unsafe-action guardrails: n/a
- Open tool findings: none

---

## Agentic State

- Agentic Profile: OFF
- Active agent roles: n/a
- Loop termination contract version: n/a
- Cross-iteration state mechanism: n/a
- Open agent findings: none

---

## Planning State

- Planning Profile: OFF
- Plan schema version: n/a
- Plan validation method: n/a
- Open plan findings: none

---

## Compliance State

- Compliance Status: OFF
- Active frameworks: n/a
- Controls implemented: n/a
- Controls partial: n/a
- Controls not started: n/a
- Evidence artifact: n/a
- Open compliance findings: none

---

## Evaluation State

- Active capability evals: none
- Runtime reliability reports: planned in T14
- Cost telemetry report: planned in T12
- Phase 1 validation: `docs/audit/PHASE1_AUDIT.md`

---

## Phase History

### 2026-06-11 - Phase 1 Bootstrap

- Selected Standard mode.
- Created initial architecture, spec, task contract, implementation contract, cost budget, continuity docs, evidence index, and CI workflow.
- Next implementation task is T01.

### 2026-06-11 - T01 Project Skeleton

- Added Python package skeleton, dependency files, Docker Compose outline, repository hygiene rules, and bootstrap tests.
- Local baseline is now 4 passing tests.
- Ruff gates pass locally.
- Next implementation task is T02.

### 2026-06-11 - T02 CI Setup

- Added CI contract tests and tightened the GitHub Actions Postgres health check.
- Local baseline is now 6 passing tests.
- Ruff gates pass locally.
- Next implementation task is T03.

### 2026-06-11 - T03 Baseline API and Verification

- Added FastAPI app surface, public health endpoint, env-only settings loader, and health/settings tests.
- Local baseline is now 8 passing tests.
- Ruff gates pass locally.
- Next step is Phase 1 boundary review before T04.

### 2026-06-11 - Phase 1 Boundary Review

- Ran Phase 1 implementation deep review for T01-T03.
- Review artifact: `docs/audit/PHASE1_IMPLEMENTATION_REVIEW.md`.
- Result: PASS with no blocking findings.
- Phase advanced to 2; next implementation task is T04.

### 2026-06-11 - T04 Job Domain Model and Persistence

- Added job domain records, SQLAlchemy Postgres tables, static migration SQL, and async job repository.
- Repository creates one job plus one submitted event, returns existing jobs for duplicate matching idempotency keys, and raises deterministic conflicts for mismatched duplicate payloads.
- Local baseline is now 11 passing tests with Postgres running.
- Ruff gates pass locally.
- Next implementation task is T05.

### 2026-06-11 - T05 Queue Adapter

- Added async Redis Streams queue adapter and queue message types.
- Queue adapter publishes jobs, leases through consumer groups, acknowledges messages, and moves exhausted jobs to DLQ.
- Local baseline is now 14 passing tests with Postgres and Redis running.
- Ruff gates pass locally.
- Next implementation task is T06.

### 2026-06-11 - T06 Worker Lifecycle and State Transitions

- Added deterministic stub runner, worker state-machine helpers, and single-message worker processing loop.
- Worker records running/completed/failed/retry events, acknowledges processed queue entries, and requeues transient failures within retry bounds.
- Local baseline is now 17 passing tests with Postgres and Redis running.
- Ruff gates pass locally.
- Next implementation task is T07.

### 2026-06-11 - T07 Idempotent Finalization and Duplicate Delivery Tests

- Added database-level terminal finalization guard with `job_finalizations`.
- Worker acknowledges replayed messages for already terminal jobs without writing another terminal event.
- Duplicate-finalization metric remains zero in duplicate-delivery tests.
- Local baseline is now 20 passing tests with Postgres and Redis running.
- Ruff gates pass locally.
- Next implementation task is T08.

### 2026-06-11 - T08 Artifact and Log Store

- Added local artifact store, structured sanitized log record helper, and cleanup CLI.
- Successful stub worker path can write JSON artifacts with input digest and result summary without raw payload content.
- Local baseline is now 23 passing tests with Postgres and Redis running.
- Ruff gates pass locally.
- Next implementation task is T09.

### 2026-06-11 - T09 Timeout and Cancellation Handling

- Added deterministic timeout and cancellation helpers plus worker handling for `timed_out` and `cancelled` terminal states.
- Timed-out jobs do not write completed artifacts; queued and running cancellation paths record audit events.
- Local baseline is now 26 passing tests with Postgres and Redis running.
- Ruff gates pass locally.
- Next step is Phase 2 boundary review before T10.

### 2026-06-11 - Phase 2 Boundary Review

- Ran Phase 2 implementation deep review for T04-T09.
- Review artifact: `docs/audit/PHASE2_IMPLEMENTATION_REVIEW.md`.
- Result: PASS with no blocking findings.
- Phase advanced to 3; next implementation task is T10.

### 2026-06-11 - T10 Observability Metrics and Tracing

- Added shared metrics registry renderer and in-memory tracing helper with sanitized span attributes.
- Metrics expose required runtime counters/gauges/histogram names.
- Trace helper links required lifecycle operation names under one trace ID.
- Local baseline is now 29 passing tests.
- Ruff gates pass locally.
- Next implementation task is T11.

### 2026-06-11 - T11 Failure Injection and Sample Jobs

- Added deterministic failure plan generation, failure payload mapping, retry policy mapping, and zero-cost stub telemetry.
- Stub runner now supports permanent injected failures as non-retryable policy errors.
- Local baseline is now 32 passing tests.
- Ruff gates pass locally.
- Next implementation task is T12.

### 2026-06-11 - T12 Cost Telemetry Adapter

- Added provider-neutral cost telemetry records, budget-block ledger, rollup renderer, and cost CLI command.
- Updated `docs/COST_BUDGET.md` telemetry language to reflect T12 implementation.
- Local baseline is now 35 passing tests.
- Ruff gates pass locally.
- Next step is Phase 3 boundary review before T13.

### 2026-06-11 - Phase 3 Boundary Review

- Ran Phase 3 implementation deep review for T10-T12.
- Review artifact: `docs/audit/PHASE3_IMPLEMENTATION_REVIEW.md`.
- Result: PASS with no blocking findings.
- Phase advanced to 4; next implementation task is T13.

### 2026-06-11 - T13 CLI and API Batch Workflow

- Added batch submission/status/cleanup helper layer, Typer commands, and token-guarded jobs API router skeleton.
- Batch submission creates one run ID, persists jobs, and publishes Redis queue entries.
- Local baseline is now 38 passing tests.
- Ruff gates pass locally.
- Next implementation task is T14.

### 2026-06-11 - T14 Load Test Harness and Reliability Reports

- Added deterministic benchmark config and reliability report renderer.
- Smoke benchmark writes `reports/load_smoke.md`; v1 proof config supports required scale/failure settings.
- Local baseline is now 41 passing tests.
- Ruff gates pass locally.
- Next step is final Phase 4 review.

### 2026-06-11 - Phase 4 Final Review

- Ran final implementation deep review for T13-T14 and full T01-T14 baseline.
- Review artifact: `docs/audit/PHASE4_FINAL_REVIEW.md`.
- Result: PASS with no blocking findings.
- All planned tasks are complete.

### 2026-06-12 - T15 Root README and Evidence Path

- Added root operator README, known limits, reports guide, and evidence index updates.
- Next implementation task is T16.

### 2026-06-12 - T16 Real Smoke Run Command

- Added real stub-only smoke command that submits jobs, runs workers, writes artifacts, validates lifecycle expectations, and renders a report from runtime state.
- Local baseline became 44 passing tests.
- Next implementation task is T17.

### 2026-06-12 - T17 Real 500-Job Reliability Proof

- Added real v1 reliability proof command and load tests for 500 jobs, worker concurrency, injected failures, timeouts, idempotency replay, artifacts, and report validation.
- Local baseline became 47 passing tests.
- Next step was Phase 5 boundary review.

### 2026-06-12 - Phase 5 Boundary Review

- Ran Phase 5 implementation review for T15-T17.
- Review artifact: `docs/audit/PHASE5_IMPLEMENTATION_REVIEW.md`.
- Result: PASS with no blocking findings.
- Phase advanced to 6; next implementation task is T18.

### 2026-06-12 - T18 Worker Crash and Stale Lease Recovery

- Added Redis pending-entry stale lease detection and recovery service.
- Recovery records `stale_lease_recovered` when retry budget remains, requeues exactly one next-attempt message per recovery cycle, and sends exhausted stale leases to DLQ after idempotent failed finalization.
- Local baseline is expected to be 50 passing tests after full verification.
- Next implementation task is T19.

### 2026-06-12 - T19 Backpressure and Queue Lag Metrics

- Added `QueueBackpressureSnapshot` inspection from Redis Streams and Postgres event state.
- Prometheus metrics now include queue depth, pending age, consumer lag, leased/running jobs, retry rate, DLQ count, p95 queue wait, and p95 execution duration without dynamic labels.
- Smoke and v1 reliability reports now include a `queue/backpressure` section.
- Local baseline is expected to be 53 passing tests after full verification.
- Next implementation task is T20.

### 2026-06-12 - T20 API Auth and Local Boundary Proof

- Added startup validation for localhost-only no-token API mode through `API_BIND_HOST`.
- Added integration tests for public health, bearer-token protected non-health routes, and non-local no-token rejection.
- Added `docs/SECURITY_BOUNDARIES.md` and README pointers.
- Local baseline is expected to be 56 passing tests after full verification.
- Next implementation task is T21.

### 2026-06-12 - T21 Artifact Integrity in Reports

- Added artifact metadata fields for run ID, attempt number, input digest, created-at, path, size, and SHA-256.
- Completed events now include artifact metadata, and report generation validates file existence, size, SHA-256, and JSON identity fields.
- Smoke and v1 reliability reports now include `## artifact integrity` rows.
- Local baseline is expected to be 59 passing tests after full verification.
- Next implementation task is T22.

### 2026-06-12 - T22 Enforce Cost Budget Gates

- Added `BudgetPolicy` gates for stub provider-call blocking, live dispatch budget requirements, per-job/run budget overrun, and retry projection.
- Worker blocked budget paths now finalize with a terminal `budget_blocked` event.
- Cost rollup supports `--strict`, `--require-file`, `--max-total-cost`, and `--max-run-cost`; top-level CLI exposes `cost rollup`.
- Local baseline is expected to be 62 passing tests after full verification.
- Next implementation task is T23.

### 2026-06-12 - T23 Eval-Ground-Truth-Lab Integration

- Added `eval_lab_case` job type with JSONL case loading, relative path support, deterministic local result generation, and artifact payload fields.
- Runtime artifacts and Eval Lab result JSON now cross-link without importing or hardcoding the sibling checkout.
- Added `docs/INTEGRATIONS.md`.
- Local baseline is expected to be 65 passing tests after full verification.
- Next implementation task is T24.

### 2026-06-12 - T24 gdev-agent Batch Simulation Job

- Added deterministic `gdev_webhook_eval` job type with request hashing, sanitized response, normalized fields, timing, attempts, runtime status, and Eval Lab output cross-links.
- Added a 50-job runtime batch test with zero provider calls by default.
- Updated integration docs.
- Local baseline is expected to be 68 passing tests after full verification.
- Next implementation task is T25.

### 2026-06-12 - Phase 7 Boundary Review

- Ran Phase 7 implementation review for T23-T24.
- Review artifact: `docs/audit/PHASE7_IMPLEMENTATION_REVIEW.md`.
- Result: PASS with no blocking findings.
- Phase advanced to 8; next implementation task is T25.

### 2026-06-12 - T25 Failure Injection Report Pack

- Added `failure-reports write-pack` command.
- Generated report definitions for transient retry, timeout, cancellation, stale worker recovery, duplicate finalization prevention, and DLQ routing.
- Report generation validates actual lifecycle evidence before writing.
- Local baseline is expected to be 71 passing tests after full verification.
- Next implementation task is T26.

### 2026-06-12 - T26 Case Study and Architecture Packaging

- Added `docs/CASE_STUDY.md` and `docs/ARCHITECTURE_DIAGRAM.md`.
- Updated known limits, evidence index, and README packaging pointers.
- All tasks T01-T26 are marked done.
- Next step is final Phase 8 review, verification, commits, and push.

### 2026-06-12 - Phase 8 Final Review

- Ran final implementation review for T25-T26 and final T01-T26 task state.
- Review artifact: `docs/audit/PHASE8_FINAL_REVIEW.md`.
- Result: PASS with no blocking findings.
- Repository is ready for granular commits and push.
