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

### 2026-06-11 - Roadmap Expansion from External Assessment

- Scope: `docs/tasks.md`, `docs/CODEX_PROMPT.md`, `docs/IMPLEMENTATION_JOURNAL.md`
- Why this work happened: Convert the assessment gaps into concrete planned tasks without changing runtime code.
- Decisions applied: added T15-T26 for root documentation, real smoke command, real 500-job reliability proof, stale lease recovery, backpressure metrics, auth boundary proof, artifact integrity evidence, cost budget enforcement, Eval-Ground-Truth-Lab integration, gdev-agent batch simulation, failure report pack, and case-study packaging.
- Evidence collected: documentation-only update; verification should include forbidden-framing scan and markdown/diff checks.
- Follow-ups: start `T15: Root README and Evidence Path`.
- Notes for next agent: keep default execution in stub mode, preserve local T1 boundaries, and run deep review between roadmap phases.

### 2026-06-12 - T15 - Root README and Evidence Path

- Scope: `README.md`, `docs/KNOWN_LIMITS.md`, `reports/README.md`, `docs/EVIDENCE_INDEX.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Make the project understandable from the repository root and document the current evidence path before real smoke and reliability proof work.
- Decisions applied: root docs use neutral operator/platform language; report docs distinguish current harness evidence from planned end-to-end smoke and reliability runs.
- Evidence collected: `rg -n "local-first|T1 runtime|Redis Streams|Postgres|idempotent finalization|known limits" README.md`; `rg -n "100-job|500-job|smoke|reliability proof|reports" README.md docs/EVIDENCE_INDEX.md`; `rg -n "Temporal|Ray|Kubernetes|production sandbox|SaaS|autonomous swarm" docs/KNOWN_LIMITS.md README.md`; forbidden-framing scan.
- Follow-ups: start `T16: Real Smoke Run Command`.
- Notes for next agent: T15 changed documentation only; runtime baseline remains 41 passing tests.

### 2026-06-12 - T16 - Real Smoke Run Command

- Scope: `src/agent_runtime_grid/cli/smoke.py`, `src/agent_runtime_grid/cli/main.py`, `src/agent_runtime_grid/cli/__init__.py`, `src/agent_runtime_grid/cli/__main__.py`, `src/agent_runtime_grid/cli/benchmark.py`, `tests/integration/test_smoke_command.py`, `README.md`, `reports/README.md`, `docs/EVIDENCE_INDEX.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`, `pyproject.toml`
- Why this work happened: Turn the smoke path into a real local run through Postgres, Redis Streams, workers, artifacts, validation, and report generation.
- Decisions applied: smoke remains stub-only with `failure_rate=0`; clean-state CLI runs use the same Postgres advisory lock as tests to avoid schema reset races; editable install is documented so `python -m agent_runtime_grid.cli smoke` works from the checkout.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_smoke_command.py::test_smoke_command_processes_jobs_through_runtime tests/integration/test_smoke_command.py::test_smoke_report_uses_runtime_state tests/integration/test_smoke_command.py::test_smoke_command_fails_on_lifecycle_mismatch -q`; `PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli smoke --jobs 3 --workers 2 --failure-rate 0 --mode stub --artifact-root /tmp/arg-smoke-artifacts-editable --report /tmp/arg-smoke-editable.md`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`
- Follow-ups: start `T17: Real 500-Job Reliability Proof`.
- Notes for next agent: local baseline is now 44 passing tests with one non-blocking FastAPI/Starlette warning.

### 2026-06-12 - T17 - Real 500-Job Reliability Proof

- Scope: `src/agent_runtime_grid/cli/benchmark.py`, `src/agent_runtime_grid/cli/main.py`, `src/agent_runtime_grid/jobs/failure_injection.py`, `src/agent_runtime_grid/cli/smoke.py`, `tests/load/test_reliability_proof.py`, `reports/v1/.gitkeep`, `README.md`, `reports/README.md`, `docs/KNOWN_LIMITS.md`, `docs/EVIDENCE_INDEX.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Convert the v1 proof from config/report shape into a real runtime run with 500 jobs, 20 workers, controlled failures, timeout cases, repeated idempotency submissions, artifacts, validation, and report generation from actual state.
- Decisions applied: v1 proof remains stub-only and $0 cost; failure plan is deterministic and includes transient, permanent, timeout, and idempotency replay cases; report rendering includes queue lag p95, execution duration p95, DLQ count, timeout count, failure classification, and idempotency proof.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/load/test_reliability_proof.py -q`; `PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli benchmark v1-proof --jobs 40 --workers 8 --failure-rate 0.20 --include-timeouts --repeat-idempotency-submissions --artifact-root /tmp/arg-proof-artifacts --report /tmp/arg-proof.md`; `PATH=.venv/bin:$PATH ruff check src/agent_runtime_grid/cli/benchmark.py src/agent_runtime_grid/jobs/failure_injection.py tests/load/test_reliability_proof.py`
- Follow-ups: run Phase 5 boundary deep review before starting `T18: Worker Crash and Stale Lease Recovery`.
- Notes for next agent: T17 load tests include a real 500-job runtime proof; expect the targeted test file to take around one minute locally.

### 2026-06-12 - Phase 5 Boundary - Implementation Review

- Scope: T15-T17 implementation, acceptance evidence, documentation packaging, smoke command, real 500-job reliability proof, stub-mode budget, SQL/Redis safety, forbidden framing, and secret scans.
- Why this work happened: User requested deep review between phases before starting Phase 6.
- Decisions applied: no blocking or warning findings means Phase 6 may start.
- Evidence collected: `docs/audit/PHASE5_IMPLEMENTATION_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T18: Worker Crash and Stale Lease Recovery`.
- Notes for next agent: Phase 5 review found no blocker or warning findings; one non-blocking dependency warning remains from `fastapi.testclient`.

### 2026-06-12 - T18 - Worker Crash and Stale Lease Recovery

- Scope: `src/agent_runtime_grid/worker/lease.py`, `src/agent_runtime_grid/worker/recovery.py`, `src/agent_runtime_grid/queue/redis_streams.py`, `src/agent_runtime_grid/worker/state_machine.py`, `tests/integration/test_stale_lease_recovery.py`, `docs/FAILURE_MODES.md`, `reports/failure-injection/.gitkeep`
- Why this work happened: Prove recovery semantics for a worker that leases work, records `running`, and exits before acknowledgement or finalization.
- Decisions applied: Redis pending entries identify stale delivery; Postgres remains lifecycle authority; recovery records `stale_lease_recovered` before requeue, acknowledges stale entries after requeue, and finalizes exhausted stale leases as failed before moving them to the Redis DLQ.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_stale_lease_recovery.py -q`
- Follow-ups: run full baseline and start `T19: Backpressure and Queue Lag Metrics`.
- Notes for next agent: stale recovery uses the same retry budget convention as transient retries, where attempt `N` may schedule `N+1` only while `N <= max_retries`.

### 2026-06-12 - T19 - Backpressure and Queue Lag Metrics

- Scope: `src/agent_runtime_grid/queue/inspection.py`, `src/agent_runtime_grid/observability/metrics.py`, `src/agent_runtime_grid/cli/smoke.py`, `src/agent_runtime_grid/cli/benchmark.py`, `tests/integration/test_queue_metrics.py`, `tests/load/test_reliability_proof.py`, `docs/OBSERVABILITY.md`
- Why this work happened: Add runtime-derived queue and backpressure visibility to reports and Prometheus output.
- Decisions applied: queue depth is consumer-group pending plus lag; p95 queue wait is `submitted -> running`; p95 execution duration is `running -> terminal`; Prometheus backpressure gauges use no dynamic labels.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_queue_metrics.py tests/integration/test_metrics.py tests/integration/test_observability_safety.py tests/load/test_reliability_proof.py::test_reports_include_backpressure_section -q`
- Follow-ups: run full baseline and start `T20: API Auth and Local Boundary Proof`.
- Notes for next agent: the legacy reliability fields remain in reports, but `## queue/backpressure` is now the precise operational section.

### 2026-06-12 - T20 - API Auth and Local Boundary Proof

- Scope: `src/agent_runtime_grid/api/app.py`, `src/agent_runtime_grid/api/routes/jobs.py`, `src/agent_runtime_grid/config.py`, `tests/integration/test_auth_boundary.py`, `docs/SECURITY_BOUNDARIES.md`, `README.md`
- Why this work happened: Prove the API's local safety boundary with executable tests and documentation.
- Decisions applied: health remains public and secret-free; non-health routes require bearer auth when `API_TOKEN` is configured; app creation rejects no-token mode unless `API_BIND_HOST` is localhost.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_auth_boundary.py tests/test_health.py tests/test_settings.py -q`
- Follow-ups: run full baseline and start `T21: Artifact Integrity in Reports`.
- Notes for next agent: `API_BIND_HOST` defaults to `127.0.0.1`, so existing local test and CLI paths continue to work without setting a token.

### 2026-06-12 - T21 - Artifact Integrity in Reports

- Scope: `src/agent_runtime_grid/artifacts/store.py`, `src/agent_runtime_grid/worker/loop.py`, `src/agent_runtime_grid/cli/smoke.py`, `src/agent_runtime_grid/cli/benchmark.py`, `tests/integration/test_artifact_report_integrity.py`, `tests/integration/test_artifacts.py`, `reports/README.md`
- Why this work happened: Make report artifact evidence verifiable beyond a file-exists completeness check.
- Decisions applied: completed event results now carry artifact metadata; report generation validates path existence, size, SHA-256, and JSON identity fields; missing or tampered artifacts raise `ArtifactIntegrityError`.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_artifact_report_integrity.py tests/integration/test_artifacts.py tests/integration/test_smoke_command.py tests/load/test_reliability_proof.py::test_v1_report_contains_required_runtime_evidence tests/load/test_benchmark_harness.py::test_report_contains_required_reliability_fields -q`
- Follow-ups: run full baseline and start `T22: Enforce Cost Budget Gates`.
- Notes for next agent: artifact integrity rows are rendered under `## artifact integrity` in smoke and v1 reliability reports.

### 2026-06-12 - T22 - Enforce Cost Budget Gates

- Scope: `src/agent_runtime_grid/cost/telemetry.py`, `src/agent_runtime_grid/cost/rollup.py`, `src/agent_runtime_grid/cli/cost.py`, `src/agent_runtime_grid/cli/main.py`, `src/agent_runtime_grid/worker/state_machine.py`, `src/agent_runtime_grid/worker/loop.py`, `tests/integration/test_budget_enforcement.py`, `docs/COST_BUDGET.md`
- Why this work happened: Move cost controls from telemetry-only records to enforceable runtime and rollup gates.
- Decisions applied: stub mode blocks provider calls; live dispatch requires run and job budgets; retry projection can block requeue; blocked worker paths emit terminal `budget_blocked`; strict cost rollup writes violations and exits non-zero.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_budget_enforcement.py tests/integration/test_cost_telemetry.py tests/integration/test_worker_lifecycle.py::test_transient_error_requeues_until_retry_limit -q`; `PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli cost rollup --help`
- Follow-ups: run full baseline and start `T23: Eval-Ground-Truth-Lab Integration`.
- Notes for next agent: top-level CLI now registers `cost rollup`; threshold options are parsed as strings and converted to `Decimal` inside the command because Typer does not support `Decimal` parameters directly.

### 2026-06-12 - T23 - Eval-Ground-Truth-Lab Integration

- Scope: `src/agent_runtime_grid/jobs/eval_lab.py`, `src/agent_runtime_grid/worker/loop.py`, `src/agent_runtime_grid/artifacts/store.py`, `src/agent_runtime_grid/cli/benchmark.py`, `tests/integration/test_eval_lab_integration.py`, `docs/INTEGRATIONS.md`
- Why this work happened: Let Runtime Grid execute Eval-Ground-Truth-Lab cases as normal queued jobs without fixed local checkout coupling.
- Decisions applied: `eval_lab_case` reads JSONL cases directly, supports relative paths, writes deterministic local eval result JSON, and cross-links Eval Lab output to runtime artifact evidence.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_eval_lab_integration.py tests/integration/test_artifact_report_integrity.py -q`
- Follow-ups: run full baseline and start `T24: gdev-agent Batch Simulation Job`.
- Notes for next agent: the Eval Lab runner intentionally does not import the sibling Eval-Ground-Truth-Lab package; this keeps the integration path portable.

### 2026-06-12 - T24 - gdev-agent Batch Simulation Job

- Scope: `src/agent_runtime_grid/jobs/gdev_agent.py`, `src/agent_runtime_grid/worker/loop.py`, `src/agent_runtime_grid/artifacts/store.py`, `tests/integration/test_gdev_agent_integration.py`, `docs/INTEGRATIONS.md`
- Why this work happened: Connect Runtime Grid, Eval Lab-style outputs, and gdev-agent-style webhook cases through the same queue/worker/artifact path.
- Decisions applied: `gdev_webhook_eval` is deterministic by default, stores request hashes instead of raw requests, writes sanitized response and normalized fields, and cross-links Eval output to runtime artifact evidence.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_gdev_agent_integration.py tests/integration/test_eval_lab_integration.py -q`
- Follow-ups: run full baseline and start `T25: Failure Injection Report Pack`.
- Notes for next agent: no gdev-agent process or network call is required in the default path; live/local HTTP expansion would need a future explicit budget and egress task.

### 2026-06-12 - Phase 7 Boundary - Implementation Review

- Scope: T23-T24 integration work, artifact cross-linking, local execution boundaries, fixed-path coupling, egress, cost, and evidence state.
- Why this work happened: User requested deep review between phases before starting Phase 8.
- Decisions applied: no blocking or warning findings means Phase 8 may start.
- Evidence collected: `docs/audit/PHASE7_IMPLEMENTATION_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_eval_lab_integration.py tests/integration/test_gdev_agent_integration.py -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: start `T25: Failure Injection Report Pack`.
- Notes for next agent: Phase 7 default paths are deterministic and local; live adapter expansion remains out of scope.

### 2026-06-12 - T25 - Failure Injection Report Pack

- Scope: `src/agent_runtime_grid/cli/failure_reports.py`, `src/agent_runtime_grid/cli/main.py`, `tests/integration/test_failure_report_pack.py`, `docs/FAILURE_MODES.md`, `reports/README.md`
- Why this work happened: Make failure-injection evidence operator-readable as report files rather than only executable tests.
- Decisions applied: report generation validates actual lifecycle evidence against expected lifecycle before writing; mismatches fail generation.
- Evidence collected: `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_failure_report_pack.py -q`; `PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli failure-reports write-pack --output-dir /tmp/arg-failure-reports`
- Follow-ups: run full baseline and start `T26: Case Study and Architecture Packaging`.
- Notes for next agent: reports are generated under ignored `reports/failure-injection/*.md`; `.gitkeep` preserves the directory.

### 2026-06-12 - T26 - Case Study and Architecture Packaging

- Scope: `docs/CASE_STUDY.md`, `docs/ARCHITECTURE_DIAGRAM.md`, `docs/KNOWN_LIMITS.md`, `docs/EVIDENCE_INDEX.md`, `README.md`
- Why this work happened: Package completed reliability and integration evidence into a concise operator-facing narrative.
- Decisions applied: case study separates current local T1 proof from production changes needed; architecture diagram includes API, Postgres, Redis Streams, workers, artifacts, reports, Eval Lab, and gdev-agent integration points.
- Evidence collected: T26 acceptance `rg` checks; full verification pending.
- Follow-ups: run final verification and final Phase 8 review.
- Notes for next agent: T01-T26 are now marked done; generated report contents remain ignored by git.

### 2026-06-12 - Phase 8 Final Review

- Scope: T25-T26 implementation, final T01-T26 task state, full baseline, quality gates, prohibited framing scan, known limits, evidence index, and packaging docs.
- Why this work happened: Close the uninterrupted development pass with the requested phase-boundary deep review.
- Decisions applied: no blocking or warning findings remain; repository is ready for granular commits and push.
- Evidence collected: `docs/audit/PHASE8_FINAL_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: commit granular changes and push.
- Notes for next agent: local baseline is 71 passing tests with one non-blocking FastAPI/Starlette deprecation warning.

### 2026-06-12 - T27 - Lease Renewal and Operator Repair CLI

- Scope: `src/agent_runtime_grid/queue/redis_streams.py`, `src/agent_runtime_grid/cli/operator.py`, `src/agent_runtime_grid/cli/main.py`, `tests/integration/test_operator_repair_cli.py`, `docs/OPERATIONS.md`, `docs/KNOWN_LIMITS.md`, `docs/FAILURE_MODES.md`, `docs/EVIDENCE_INDEX.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Continue from the completed T01-T26 roadmap by taking the next local T1 reliability gap from known limits: active lease renewal and operator repair commands.
- Decisions applied: T27 remains local-only, uses Redis pending-entry state only as delivery evidence, keeps Postgres as the lifecycle authority, and renders operator output without raw payload or secret-like fields.
- Evidence collected: pre-edit baseline `PATH=.venv/bin:$PATH python -m pytest -q` passed with 71 tests and one FastAPI/Starlette warning; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_operator_repair_cli.py -q`; `PATH=.venv/bin:$PATH ruff check src/agent_runtime_grid/cli/operator.py src/agent_runtime_grid/queue/redis_streams.py tests/integration/test_operator_repair_cli.py`.
- Follow-ups: run full Phase 9 verification and review.
- Notes for next agent: do not add live model calls or non-local network egress for T27.

### 2026-06-12 - Phase 9 Boundary - Implementation Review

- Scope: T27 implementation, acceptance tests, full baseline, quality gates, task ledger, local operator output safety, and runtime egress review.
- Why this work happened: User requested deep review between phases before continuing.
- Decisions applied: no blocking or warning findings remain; T27 is ready to commit and push.
- Evidence collected: `docs/audit/PHASE9_IMPLEMENTATION_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_operator_repair_cli.py -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: commit granular changes and push.
- Notes for next agent: local baseline is 74 passing tests with one non-blocking FastAPI/Starlette deprecation warning.

### 2026-06-12 - T28 - Automated Worker Heartbeat Lease Renewal

- Scope: `src/agent_runtime_grid/worker/loop.py`, `tests/integration/test_worker_heartbeat.py`, `docs/OPERATIONS.md`, `docs/KNOWN_LIMITS.md`, `docs/FAILURE_MODES.md`, `docs/EVIDENCE_INDEX.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: Close the remaining local worker reliability gap where a live long-running worker can appear stale if no pending-entry renewal occurs during execution.
- Decisions applied: T28 keeps Redis as delivery state and Postgres as lifecycle authority; heartbeat renewal runs only while the runner is active, stops after terminal handling, does not create lifecycle events, and does not enable new network egress.
- Evidence collected: pre-edit baseline `PATH=.venv/bin:$PATH python -m pytest -q` passed with 74 tests and one FastAPI/Starlette warning; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_worker_heartbeat.py -q`; `PATH=.venv/bin:$PATH ruff check src/agent_runtime_grid/worker/loop.py tests/integration/test_worker_heartbeat.py`.
- Follow-ups: run full Phase 10 verification and review.
- Notes for next agent: do not add live model calls or non-local network egress for T28.

### 2026-06-12 - Phase 10 Boundary - Implementation Review

- Scope: T28 implementation, heartbeat acceptance tests, neighboring operator repair coverage, full baseline, quality gates, task ledger, local runtime boundary, and runtime egress review.
- Why this work happened: User requested deep review between phases before continuing.
- Decisions applied: no blocking or warning findings remain; T28 is ready to commit and push.
- Evidence collected: `docs/audit/PHASE10_IMPLEMENTATION_REVIEW.md`; `PATH=.venv/bin:$PATH python -m pytest tests/integration/test_worker_heartbeat.py tests/integration/test_operator_repair_cli.py -q`; `PATH=.venv/bin:$PATH python -m pytest -q`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`
- Follow-ups: commit granular changes and push.
- Notes for next agent: local baseline is 77 passing tests with one non-blocking FastAPI/Starlette deprecation warning.

### 2026-06-14 - T29 - Cross-Project Runtime Proof

- Scope: `docs/tasks.md`, `docs/CODEX_PROMPT.md`
- Why this work happened: gdev-agent and Eval-Ground-Truth-Lab now have ready artifacts, so Grid needs to prove it can run and cross-link those workloads as the execution runtime layer.
- Decisions applied: T29 stays local-first and stub/default; it ingests existing artifact paths and runs deterministic Grid jobs without live model calls or broader worker egress.
- Evidence collected: initial baseline with default ports failed because `gdev-agent` owns local Postgres/Redis ports; isolated Grid test services were started on `127.0.0.1:55432` and `127.0.0.1:56379`.
- Follow-ups: run baseline on isolated Grid services, implement full-stack proof, focused tests, Phase 11 review, commits, and push.
- Notes for next agent: use explicit `DATABASE_URL=postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:55432/agent_runtime_grid` and `REDIS_URL=redis://localhost:56379/0` while gdev-agent services occupy default ports.

### 2026-06-14 - T29 - Cross-Project Runtime Proof Complete

- Scope: `src/agent_runtime_grid/cli/proof.py`, `src/agent_runtime_grid/cli/main.py`, `tests/integration/test_full_stack_proof.py`, `README.md`, `docs/INTEGRATIONS.md`, `docs/CASE_STUDY.md`, `docs/EVIDENCE_INDEX.md`, `docs/tasks.md`, `docs/CODEX_PROMPT.md`, `reports/README.md`, `reports/full-stack/.gitkeep`
- Why this work happened: Close the Grid side of the ready gdev-agent and Eval Lab artifact flow with a command that validates those artifacts, runs selected cases through Grid, and writes cross-linked runtime evidence.
- Decisions applied: `proof full-stack` remains deterministic and local by default; selected Eval Lab cases become `gdev_webhook_eval` jobs, not live HTTP calls; report evidence uses artifact metadata and request hashes instead of raw request fields.
- Evidence collected: `DATABASE_URL=postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:55432/agent_runtime_grid REDIS_URL=redis://localhost:56379/0 PATH=.venv/bin:$PATH python -m pytest tests/integration/test_full_stack_proof.py -q`; `PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli proof full-stack --database-url postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:55432/agent_runtime_grid --redis-url redis://localhost:56379/0 --eval-lab-dataset ../Eval-Ground-Truth-Lab/datasets/gdev_agent/triage_v1.jsonl --eval-lab-report ../Eval-Ground-Truth-Lab/reports/gdev-agent/baseline_report.md --gdev-artifact ../gdev-agent/eval/results/last_run.json --jobs 3 --workers 2 --artifact-root /tmp/arg-full-stack-artifacts --report /tmp/arg-full-stack/runtime_report.md`; `PATH=.venv/bin:$PATH ruff check`; `PATH=.venv/bin:$PATH ruff format --check`; `git diff --check`; `DATABASE_URL=postgresql+asyncpg://agent_runtime_grid:local-dev-password@localhost:55432/agent_runtime_grid REDIS_URL=redis://localhost:56379/0 PATH=.venv/bin:$PATH python -m pytest -q`
- Follow-ups: remote-server runbook or live/local adapter expansion only as a separate task with explicit egress and budget approval.
- Notes for next agent: local baseline is 80 passing tests with one non-blocking FastAPI/Starlette deprecation warning; use explicit isolated service URLs when adjacent projects own the default ports.

### 2026-06-14 - T30 - Stack Overview And Committed Evidence Snapshots

- Scope: `README.md`, `docs/STACK_OVERVIEW.md`, `docs/INTEGRATIONS.md`,
  `docs/CASE_STUDY.md`, `docs/KNOWN_LIMITS.md`, `docs/EVIDENCE_INDEX.md`,
  `docs/ARCHITECTURE_DIAGRAM.md`, `docs/CODEX_PROMPT.md`,
  `docs/tasks.md`, `docs/evidence/`, and `reports/README.md`.
- Why this work happened: The runtime proof was inspectable through commands
  and tests, but generated reports are intentionally ignored by git. A reviewer
  also could misread `proof full-stack` as live HTTP end-to-end execution.
- Decisions applied: Current cross-project mode is now framed as
  full-stack artifact proof. `full-stack-live-local` is reserved for future work
  with explicit egress, timeout, budget, and artifact boundaries.
- Evidence collected: Committed snapshots were added for the 100-job smoke
  proof, 500-job reliability proof, full-stack artifact proof, and
  failure-injection pack. No runtime behavior, provider calls, egress, or budget
  policy changed.
- Follow-ups: Implement live-local full-stack mode only as a separate task with
  explicit approval boundaries.
- Notes for next agent: `docs/evidence/` is the stable reviewer surface;
  `reports/` remains the current-run generated output surface and is still
  ignored by git.

### 2026-06-14 - Phase 11 Boundary - Implementation Review

- Scope: T29 implementation, cross-project artifact validation, full-stack proof report, isolated-port baseline, quality gates, local runtime boundary, and runtime egress review.
- Why this work happened: User requested deep review between phases before continuing.
- Decisions applied: no blocking or warning findings remain; T29 is ready to commit and push.
- Evidence collected: `docs/audit/PHASE11_IMPLEMENTATION_REVIEW.md`; T29 acceptance tests; manual adjacent-artifact proof command; full baseline; ruff gates; diff check; task ledger scan; prohibited framing scan; runtime egress review.
- Follow-ups: commit granular changes and push.
- Notes for next agent: generated full-stack reports remain ignored by git; committed docs describe command usage and evidence paths only.

### 2026-06-14 - T31 - Full-Stack Live-Local Proof Mode

- Scope: `src/agent_runtime_grid/jobs/gdev_agent.py`,
  `src/agent_runtime_grid/cli/proof.py`,
  `tests/integration/test_gdev_agent_integration.py`,
  `tests/integration/test_full_stack_proof.py`, `README.md`,
  `docs/INTEGRATIONS.md`, `docs/STACK_OVERVIEW.md`,
  `docs/CASE_STUDY.md`, `docs/KNOWN_LIMITS.md`,
  `docs/EVIDENCE_INDEX.md`, `docs/evidence/full-stack-artifact-proof.md`,
  `docs/evidence/full-stack-live-local.md`, `reports/README.md`,
  `docs/tasks.md`, and `docs/CODEX_PROMPT.md`.
- Why this work happened: The stack needed a real local HTTP mode distinct from
  artifact proof, so Runtime Grid can execute selected Eval Lab/gdev cases as
  worker jobs that call a locally running `gdev-agent` `/webhook`.
- Decisions applied: `proof full-stack` remains artifact proof; live-local is a
  separate command. Dataset cases cannot define network destinations or secrets;
  workers accept only operator-configured localhost/loopback gdev URLs and read
  the webhook secret value from an environment variable. Runtime Grid still
  makes no live model calls.
- Evidence collected: focused tests cover local HMAC signing, localhost-only URL
  validation, env-only webhook secret lookup, sanitized artifacts/reports, and
  live-local full-stack Grid execution with mocked local transport. Full local
  gate passed with `PATH=.venv/bin:$PATH python -m pytest -q` -> 83 passed and
  one upstream FastAPI/Starlette warning; `ruff check` and
  `ruff format --check` passed.
- Follow-ups: Promote a committed live-local report only after an operator-run
  local gdev-agent demo-mode run is executed and reviewed.
- Notes for next agent: generated `reports/full-stack/live_local_runtime_report.md`
  remains ignored by git; `docs/evidence/full-stack-live-local.md` is the stable
  reviewer snapshot.
