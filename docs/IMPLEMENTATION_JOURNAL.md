# Implementation Journal - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-11
Status: append-only

Purpose:

- Durable task and session continuity across agents and sessions.
- Records what changed, why, what evidence was collected, and what remains open.

This file is not the source of truth for architecture or policy. Use it as a retrieval surface and handoff log.

---

## Journal Entry Template

```markdown
### YYYY-MM-DD - TASK-ID - Short Title

- Scope: files, directories, or task IDs
- Why this work happened: reason or trigger
- Decisions applied: Decision Log or ADR refs, or "none"
- Evidence collected: tests, evals, review reports, manual checks
- Follow-ups: next task, open risk, or "none"
- Notes for next agent: only the context worth carrying forward
```

---

## Entries

### 2026-06-11 - Phase 1 - Standard Bootstrap

- Scope: `docs/`, `.github/workflows/ci.yml`
- Why this work happened: Initialize Agent Runtime Grid from the project brief using the AI Workflow Playbook as read-only reference.
- Decisions applied: `D-001`, `D-002`, `D-003`, `D-004`, `D-005`
- Evidence collected: `docs/audit/PHASE1_AUDIT.md` after validation
- Follow-ups: start `T01: Project Skeleton` after Phase 1 audit passes
- Notes for next agent: do not add live LLM calls during T01; keep default benchmark path stub-only and T1-local.

### 2026-06-11 - T01 - Project Skeleton

- Scope: `pyproject.toml`, `requirements.txt`, `requirements-dev.txt`, `docker-compose.yml`, `.gitignore`, `src/agent_runtime_grid/__init__.py`, `tests/test_bootstrap.py`, `tests/test_compose_contract.py`, `tests/test_repo_hygiene.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Implement the Phase 1 skeleton task so the repository has package metadata, local service outline, hygiene rules, and bootstrap verification.
- Decisions applied: T1-local runtime, stub mode default, no live LLM calls, no application behavior beyond T01 acceptance tests.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/test_bootstrap.py::test_package_imports -q`; `PATH=.venv/bin:$PATH python -m pytest tests/test_compose_contract.py::test_required_services_declared -q`; `PATH=.venv/bin:$PATH python -m pytest tests/test_repo_hygiene.py::test_gitignore_excludes_runtime_outputs -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`
- Follow-ups: start `T02: CI Setup`.
- Notes for next agent: this shell has `python3` but no system `python`; activate `.venv` or put `.venv/bin` on `PATH` before running the documented `python -m ...` commands.

### 2026-06-11 - T02 - CI Setup

- Scope: `.github/workflows/ci.yml`, `tests/test_ci_contract.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Make the GitHub Actions workflow contract testable and runnable against the T01 project skeleton.
- Decisions applied: Python 3.12 CI, Postgres 16 and Redis 7 service containers, stub-mode test environment, no live LLM calls.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/test_ci_contract.py::test_ci_has_required_gates -q`; `PATH=.venv/bin:$PATH python -m pytest tests/test_ci_contract.py::test_ci_service_env_matches_runtime_contract -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`
- Follow-ups: start `T03: Baseline API and Verification`.
- Notes for next agent: CI workflow uses local test placeholders only; no real credentials or live provider egress are configured.

### 2026-06-11 - T03 - Baseline API and Verification

- Scope: `src/agent_runtime_grid/api/app.py`, `src/agent_runtime_grid/config.py`, `tests/test_health.py`, `tests/test_settings.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Establish the first FastAPI surface, public health endpoint, shared settings loader, and repository baseline command for later tasks.
- Decisions applied: health route is intentionally public and secret-free per `docs/ARCHITECTURE.md#security-boundaries`; settings read environment variables only and do not load committed secret files.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/test_health.py::test_health_returns_ok -q`; `PATH=.venv/bin:$PATH python -m pytest tests/test_settings.py::test_settings_load_runtime_contract -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`
- Follow-ups: run Phase 1 boundary deep review before starting `T04: Job Domain Model and Persistence`.
- Notes for next agent: `python -m pytest -q` is now the canonical local baseline; current run reports 8 passing tests and one FastAPI/Starlette deprecation warning from `fastapi.testclient`.

### 2026-06-11 - Phase 1 Boundary - Implementation Review

- Scope: T01-T03 implementation, CI contract, baseline, security boundary, default stub mode, secret scan, and egress scan.
- Why this work happened: User requested uninterrupted development with deep review between phases before Phase 2.
- Decisions applied: no blocking finding means Phase 2 may start; independent PR review is still not replaced by this implementation audit.
- Evidence collected: `docs/audit/PHASE1_IMPLEMENTATION_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T04: Job Domain Model and Persistence`.
- Notes for next agent: phase review found no blocker or warning findings; one non-blocking dependency warning remains from `fastapi.testclient`.

### 2026-06-11 - T04 - Job Domain Model and Persistence

- Scope: `src/agent_runtime_grid/domain/jobs.py`, `src/agent_runtime_grid/storage/models.py`, `src/agent_runtime_grid/storage/repositories.py`, `src/agent_runtime_grid/storage/migrations/0001_jobs.sql`, `tests/integration/test_job_repository.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Implement durable Postgres-backed job submission state and idempotency behavior required before queue and worker tasks.
- Decisions applied: Postgres is authoritative for job state; repository uses SQLAlchemy Core expressions; duplicate idempotency keys with matching payloads return the existing job; mismatched payloads raise `IdempotencyConflictError`.
- Evidence collected: `docker-compose up -d postgres`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_job_repository.py::test_create_job_records_submitted_event -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_job_repository.py::test_duplicate_idempotency_key_returns_existing_job -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_job_repository.py::test_idempotency_key_payload_conflict_is_rejected -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`
- Follow-ups: start `T05: Queue Adapter`.
- Notes for next agent: T04 integration tests require Postgres. Locally, `docker-compose up -d postgres` starts the configured service; the test fixture uses a Postgres advisory lock so separately invoked acceptance tests do not race on schema setup.

### 2026-06-11 - T05 - Queue Adapter

- Scope: `src/agent_runtime_grid/queue/redis_streams.py`, `src/agent_runtime_grid/queue/types.py`, `tests/integration/test_queue_adapter.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Implement Redis Streams delivery primitives required before worker lifecycle processing.
- Decisions applied: Redis is delivery state only; all Redis access uses `redis.asyncio`; tests use unique stream names to avoid cross-test stream collisions.
- Evidence collected: `docker-compose up -d redis`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_queue_adapter.py::test_publish_job_entry -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_queue_adapter.py::test_lease_and_ack_job -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_queue_adapter.py::test_exhausted_job_moves_to_dlq -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T06: Worker Lifecycle and State Transitions`.
- Notes for next agent: Postgres and Redis are both running locally from `docker-compose`; current baseline is 14 passing tests.

### 2026-06-11 - T06 - Worker Lifecycle and State Transitions

- Scope: `src/agent_runtime_grid/worker/loop.py`, `src/agent_runtime_grid/worker/state_machine.py`, `src/agent_runtime_grid/jobs/stub.py`, `tests/integration/test_worker_lifecycle.py`, `tests/integration/test_job_repository.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Implement deterministic worker processing after job persistence and queue delivery primitives.
- Decisions applied: state transitions are code-owned; stub jobs do not call external providers; transient failures requeue within retry bounds; policy validation failures are non-retryable.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_worker_lifecycle.py::test_worker_completes_stub_job -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_worker_lifecycle.py::test_transient_error_requeues_until_retry_limit -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_worker_lifecycle.py::test_policy_error_is_not_retried -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T07: Idempotent Finalization and Duplicate Delivery Tests`.
- Notes for next agent: all Postgres integration fixtures now share advisory lock `7400` so parallel acceptance invocations cannot race schema setup.

### 2026-06-11 - T07 - Idempotent Finalization and Duplicate Delivery Tests

- Scope: `src/agent_runtime_grid/storage/finalization.py`, `src/agent_runtime_grid/storage/models.py`, `src/agent_runtime_grid/storage/migrations/0001_jobs.sql`, `src/agent_runtime_grid/worker/state_machine.py`, `src/agent_runtime_grid/worker/loop.py`, `tests/integration/test_idempotent_finalization.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Enforce database-guarded terminal transitions before artifacts, timeouts, and cancellation add more terminal paths.
- Decisions applied: `job_finalizations.job_id` is the database-level idempotency constraint; terminal event insertion happens only after the finalization guard succeeds; replayed messages for terminal jobs are acknowledged as no-ops.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_idempotent_finalization.py::test_racing_workers_produce_one_terminal_event -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_idempotent_finalization.py::test_replayed_message_after_finalization_is_noop -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_idempotent_finalization.py::test_duplicate_finalization_metric_stays_zero -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T08: Artifact and Log Store`.
- Notes for next agent: T07 added `job_finalizations` beyond the original task file list because the acceptance criteria and implementation contract require a database-level terminal idempotency constraint.

### 2026-06-11 - T08 - Artifact and Log Store

- Scope: `src/agent_runtime_grid/artifacts/store.py`, `src/agent_runtime_grid/logging.py`, `src/agent_runtime_grid/cli/cleanup.py`, `src/agent_runtime_grid/worker/loop.py`, `tests/integration/test_artifacts.py`, `tests/integration/test_logging.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Add local artifact and structured logging primitives before timeout/cancellation and benchmark tasks need durable outputs.
- Decisions applied: artifacts contain input digests and summaries instead of raw payloads; structured logs drop secret-like fields and sanitize malformed error class values.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_artifacts.py::test_stub_job_writes_json_artifact -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_artifacts.py::test_artifact_metadata_records_hash_and_size -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_logging.py::test_job_logs_are_structured_and_sanitized -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T09: Timeout and Cancellation Handling`.
- Notes for next agent: T08 modified `Worker` to accept an optional `ArtifactStore`; no artifact is written unless the worker is configured with one.

### 2026-06-11 - T09 - Timeout and Cancellation Handling

- Scope: `src/agent_runtime_grid/worker/cancellation.py`, `src/agent_runtime_grid/worker/timeouts.py`, `src/agent_runtime_grid/jobs/stub.py`, `src/agent_runtime_grid/worker/state_machine.py`, `src/agent_runtime_grid/worker/loop.py`, `tests/integration/test_timeout_cancellation.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Add deterministic timeout and cancellation terminal paths before observability and benchmark phases.
- Decisions applied: timeouts use bounded `asyncio.wait_for`; cancellation uses an in-process registry for local T1 runtime tests; terminal timeout/cancel events use the T07 finalization guard.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_timeout_cancellation.py::test_timeout_marks_job_timed_out -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_timeout_cancellation.py::test_cancel_queued_job_prevents_execution -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_timeout_cancellation.py::test_cancel_running_job_records_worker_shutdown -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: run Phase 2 boundary deep review before starting `T10: Observability Metrics and Tracing`.
- Notes for next agent: current baseline is 26 passing tests with one FastAPI/Starlette deprecation warning.

### 2026-06-11 - Phase 2 Boundary - Implementation Review

- Scope: T04-T09 implementation, acceptance evidence, persistence/queue/worker/finalization/timeout/artifact/log safety, and contract-risk scans.
- Why this work happened: User requested uninterrupted development with deep review between phases before Phase 3.
- Decisions applied: no blocking finding means Phase 3 may start; independent PR review is still not replaced by this implementation audit.
- Evidence collected: `docs/audit/PHASE2_IMPLEMENTATION_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T10: Observability Metrics and Tracing`.
- Notes for next agent: phase review found no blocker or warning findings; one non-blocking dependency warning remains from `fastapi.testclient`.

### 2026-06-11 - T10 - Observability Metrics and Tracing

- Scope: `src/agent_runtime_grid/observability/metrics.py`, `src/agent_runtime_grid/observability/tracing.py`, `tests/integration/test_metrics.py`, `tests/integration/test_tracing.py`, `tests/integration/test_observability_safety.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Establish shared observability primitives before failure injection, cost telemetry, benchmark reporting, and final audit phases.
- Decisions applied: metrics use a project-owned Prometheus registry; tracing stores sanitized attributes and drops secret-like or raw payload fields.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_metrics.py::test_required_runtime_metrics_exposed -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_tracing.py::test_job_trace_links_runtime_spans -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_observability_safety.py::test_observability_excludes_secrets_and_payloads -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T11: Failure Injection and Sample Jobs`.
- Notes for next agent: T10 provides primitives but does not yet wire every runtime callsite into spans/counters; later tasks can import these shared modules.

### 2026-06-11 - T11 - Failure Injection and Sample Jobs

- Scope: `src/agent_runtime_grid/jobs/failure_injection.py`, `src/agent_runtime_grid/jobs/stub.py`, `tests/integration/test_failure_injection.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Add reproducible failure scenario generation for later benchmark and report tasks.
- Decisions applied: failure plans use deterministic seeded RNG; transient injected failures are retryable; permanent injected failures map to non-retryable stub policy errors; stub telemetry stays at zero model calls and zero model cost.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_failure_injection.py::test_fixed_seed_failure_plan_is_reproducible -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_failure_injection.py::test_injected_failure_classes_drive_retry_behavior -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_failure_injection.py::test_stub_mode_records_zero_model_cost -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T12: Cost Telemetry Adapter`.
- Notes for next agent: no live model mode or external egress was enabled for T11.

### 2026-06-11 - T12 - Cost Telemetry Adapter

- Scope: `src/agent_runtime_grid/cost/telemetry.py`, `src/agent_runtime_grid/cost/rollup.py`, `src/agent_runtime_grid/cli/cost.py`, `tests/integration/test_cost_telemetry.py`, `docs/COST_BUDGET.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Add project-owned cost telemetry and rollup support before benchmark/report phases.
- Decisions applied: telemetry is provider-neutral data only; live LLM calls remain disabled unless separately configured and approved; budget overrun records a blocked event instead of dispatching.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_cost_telemetry.py::test_live_job_records_required_cost_fields -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_cost_telemetry.py::test_budget_overrun_blocks_live_dispatch -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_cost_telemetry.py::test_cost_rollup_report_contains_run_and_job_totals -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: run Phase 3 boundary deep review before starting `T13: CLI and API Batch Workflow`.
- Notes for next agent: no provider calls or live egress were added; cost report command writes local markdown from JSONL telemetry input.

### 2026-06-11 - Phase 3 Boundary - Implementation Review

- Scope: T10-T12 implementation, acceptance evidence, observability safety, failure injection determinism, and cost budget scans.
- Why this work happened: User requested uninterrupted development with deep review between phases before Phase 4.
- Decisions applied: no blocking finding means Phase 4 may start; independent PR review is still not replaced by this implementation audit.
- Evidence collected: `docs/audit/PHASE3_IMPLEMENTATION_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T13: CLI and API Batch Workflow`.
- Notes for next agent: phase review found no blocker or warning findings; one non-blocking dependency warning remains from `fastapi.testclient`.

### 2026-06-11 - T13 - CLI and API Batch Workflow

- Scope: `src/agent_runtime_grid/cli/main.py`, `src/agent_runtime_grid/api/routes/jobs.py`, `tests/integration/test_cli_batch.py`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Add operator-facing batch submission, status, and cleanup primitives before benchmark harness work.
- Decisions applied: batch submission uses one run ID for all jobs; status maps submitted/queued jobs to queued count; API routes include local token dependency when `API_TOKEN` is configured.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_cli_batch.py::test_submit_batch_creates_expected_job_count -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_cli_batch.py::test_status_reports_lifecycle_counts -q`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_cli_batch.py::test_cleanup_removes_artifacts_without_metadata_delete -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T14: Load Test Harness and Reliability Reports`.
- Notes for next agent: T13 tests exercise helper layer directly; API router is not yet mounted in `api/app.py`.

### 2026-06-11 - T14 - Load Test Harness and Reliability Reports

- Scope: `src/agent_runtime_grid/cli/benchmark.py`, `tests/load/test_benchmark_harness.py`, `reports/.gitkeep`, `.gitignore`, `docs/EVIDENCE_INDEX.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Add local smoke/v1 proof benchmark configuration and durable reliability report fields.
- Decisions applied: benchmark harness is deterministic and stub-only; reports include required reliability fields without live provider calls.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/load/test_benchmark_harness.py::test_smoke_benchmark_writes_report -q`; `PATH=.venv/bin:$PATH python -m pytest tests/load/test_benchmark_harness.py::test_v1_proof_config_accepts_required_scenario -q`; `PATH=.venv/bin:$PATH python -m pytest tests/load/test_benchmark_harness.py::test_report_contains_required_reliability_fields -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: run final Phase 4 deep review.
- Notes for next agent: `reports/.gitkeep` is intentionally unignored while generated report contents remain ignored.

### 2026-06-11 - Phase 4 Final - Implementation Review

- Scope: T13-T14 implementation, all task states, full baseline, lint/format, route auth, budget, egress, SQL, Redis, and secret scans.
- Why this work happened: Complete the requested uninterrupted development pass with deep review at the final phase boundary.
- Decisions applied: no blocking finding remains; independent PR review is still not replaced by this implementation audit.
- Evidence collected: `docs/audit/PHASE4_FINAL_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: independent review/CI run before merge.
- Notes for next agent: all planned tasks T01-T14 are done; local baseline is 41 passing tests with one non-blocking FastAPI/Starlette warning.
