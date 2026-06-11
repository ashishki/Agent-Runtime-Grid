# Tasks - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-11
Mode: Standard

Task state values: `planned`, `in_progress`, `blocked`, `done`.

---

## T01: Project Skeleton

State: done
Owner: codex
Phase: 1
Type: none
Depends-On: none

Objective: |
  Create the Python project skeleton, dependency files, package layout, test layout, Docker Compose service outline, and repository hygiene files needed for the runtime implementation.

Acceptance-Criteria:
  - id: AC-1
    description: "The package `agent_runtime_grid` imports from `src/agent_runtime_grid/__init__.py`, and the bootstrap test verifies the package version is exposed."
    test: "python -m pytest tests/test_bootstrap.py::test_package_imports -q"
  - id: AC-2
    description: "`docker-compose.yml` declares API, worker, Postgres, Redis, Prometheus, and Grafana services with no real secrets committed."
    test: "python -m pytest tests/test_compose_contract.py::test_required_services_declared -q"
  - id: AC-3
    description: "Repository hygiene rules exclude `.env`, local artifacts, local reports, Python caches, and coverage output."
    test: "python -m pytest tests/test_repo_hygiene.py::test_gitignore_excludes_runtime_outputs -q"

Files:
  - pyproject.toml
  - requirements.txt
  - requirements-dev.txt
  - docker-compose.yml
  - .gitignore
  - src/agent_runtime_grid/__init__.py
  - tests/test_bootstrap.py
  - tests/test_compose_contract.py
  - tests/test_repo_hygiene.py

Context-Refs:
  - docs/ARCHITECTURE.md#file-layout
  - docs/ARCHITECTURE.md#tech-stack
  - docs/IMPLEMENTATION_CONTRACT.md#mandatory-pre-task-protocol

---

## T02: CI Setup

State: done
Owner: codex
Phase: 1
Type: none
Depends-On: T01

Objective: |
  Make the GitHub Actions workflow execute the project bootstrap checks with Python 3.12, Ruff lint, Ruff format verification, pytest, and Postgres and Redis services.

Acceptance-Criteria:
  - id: AC-1
    description: "The CI workflow contains checkout, Python 3.12 setup, dependency install, `ruff check`, `ruff format --check`, and `python -m pytest` steps."
    test: "python -m pytest tests/test_ci_contract.py::test_ci_has_required_gates -q"
  - id: AC-2
    description: "The CI workflow declares Postgres and Redis service containers with health checks and exposes matching `DATABASE_URL` and `REDIS_URL` values to tests."
    test: "python -m pytest tests/test_ci_contract.py::test_ci_service_env_matches_runtime_contract -q"

Files:
  - .github/workflows/ci.yml
  - tests/test_ci_contract.py

Context-Refs:
  - docs/ARCHITECTURE.md#runtime-contract
  - docs/IMPLEMENTATION_CONTRACT.md#ci-gate

---

## T03: Baseline API and Verification

State: done
Owner: codex
Phase: 1
Type: none
Depends-On: T01, T02

Objective: |
  Add the first FastAPI app surface, shared settings, health endpoint, and baseline tests so future tasks have a known passing test count and a stable verification command.

Acceptance-Criteria:
  - id: AC-1
    description: "`GET /health` returns HTTP 200 with body `{\"status\":\"ok\"}` and does not require authentication."
    test: "python -m pytest tests/test_health.py::test_health_returns_ok -q"
  - id: AC-2
    description: "The settings module loads `DATABASE_URL`, `REDIS_URL`, `ARTIFACT_ROOT`, and optional auth/model variables without reading committed secret files."
    test: "python -m pytest tests/test_settings.py::test_settings_load_runtime_contract -q"
  - id: AC-3
    description: "The repository baseline command runs all current tests successfully."
    test: "python -m pytest -q"

Files:
  - src/agent_runtime_grid/api/app.py
  - src/agent_runtime_grid/config.py
  - tests/test_health.py
  - tests/test_settings.py
  - docs/CODEX_PROMPT.md

Context-Refs:
  - docs/ARCHITECTURE.md#security-boundaries
  - docs/IMPLEMENTATION_CONTRACT.md#mandatory-pre-task-protocol

---

## T04: Job Domain Model and Persistence

State: done
Owner: codex
Phase: 2
Type: none
Depends-On: T03

Objective: |
  Define job, run, event, artifact, retry, and cost domain models plus Postgres persistence tables and repository methods for job lifecycle state.

Acceptance-Criteria:
  - id: AC-1
    description: "A valid job submission persists one job row and one append-only `submitted` event with job ID, run ID, idempotency key, timeout, retry limit, and trace ID."
    test: "python -m pytest tests/integration/test_job_repository.py::test_create_job_records_submitted_event -q"
  - id: AC-2
    description: "A duplicate idempotency key with identical payload returns the existing job ID and does not insert a second job row."
    test: "python -m pytest tests/integration/test_job_repository.py::test_duplicate_idempotency_key_returns_existing_job -q"
  - id: AC-3
    description: "A duplicate idempotency key with different payload is rejected with a deterministic conflict error."
    test: "python -m pytest tests/integration/test_job_repository.py::test_idempotency_key_payload_conflict_is_rejected -q"

Files:
  - src/agent_runtime_grid/domain/jobs.py
  - src/agent_runtime_grid/storage/models.py
  - src/agent_runtime_grid/storage/repositories.py
  - src/agent_runtime_grid/storage/migrations/
  - tests/integration/test_job_repository.py

Context-Refs:
  - docs/ARCHITECTURE.md#data-flow
  - docs/IMPLEMENTATION_CONTRACT.md#sql-safety

---

## T05: Queue Adapter

State: done
Owner: codex
Phase: 2
Type: none
Depends-On: T04

Objective: |
  Implement the Redis Streams queue adapter for publishing jobs, leasing pending work, acknowledging completed work, and moving exhausted jobs to a dead-letter stream.

Acceptance-Criteria:
  - id: AC-1
    description: "Publishing a job writes one stream entry containing job ID, run ID, attempt number, and trace ID."
    test: "python -m pytest tests/integration/test_queue_adapter.py::test_publish_job_entry -q"
  - id: AC-2
    description: "A worker consumer can lease a queued job and acknowledge it after a repository finalization succeeds."
    test: "python -m pytest tests/integration/test_queue_adapter.py::test_lease_and_ack_job -q"
  - id: AC-3
    description: "A job whose retry limit is exhausted is moved to the dead-letter stream with final error class and attempt count."
    test: "python -m pytest tests/integration/test_queue_adapter.py::test_exhausted_job_moves_to_dlq -q"

Files:
  - src/agent_runtime_grid/queue/redis_streams.py
  - src/agent_runtime_grid/queue/types.py
  - tests/integration/test_queue_adapter.py

Context-Refs:
  - docs/ARCHITECTURE.md#runtime-and-isolation-model
  - docs/IMPLEMENTATION_CONTRACT.md#async-redis

---

## T06: Worker Lifecycle and State Transitions

State: done
Owner: codex
Phase: 2
Type: none
Depends-On: T04, T05

Objective: |
  Build the worker loop that leases queued jobs, records running state, renews leases, executes bounded job runners, and applies deterministic terminal transitions.

Acceptance-Criteria:
  - id: AC-1
    description: "A worker processing a successful stub job records `running` then `completed` events and acknowledges the queue entry."
    test: "python -m pytest tests/integration/test_worker_lifecycle.py::test_worker_completes_stub_job -q"
  - id: AC-2
    description: "A transient runner error records retry metadata and requeues the job until the configured retry limit is reached."
    test: "python -m pytest tests/integration/test_worker_lifecycle.py::test_transient_error_requeues_until_retry_limit -q"
  - id: AC-3
    description: "A policy validation error records a non-retryable failed state without queue requeue."
    test: "python -m pytest tests/integration/test_worker_lifecycle.py::test_policy_error_is_not_retried -q"

Files:
  - src/agent_runtime_grid/worker/loop.py
  - src/agent_runtime_grid/worker/state_machine.py
  - src/agent_runtime_grid/jobs/stub.py
  - tests/integration/test_worker_lifecycle.py

Context-Refs:
  - docs/ARCHITECTURE.md#deterministic-vs-llm-owned-subproblems
  - docs/IMPLEMENTATION_CONTRACT.md#project-specific-rules

---

## T07: Idempotent Finalization and Duplicate Delivery Tests

State: done
Owner: codex
Phase: 2
Type: none
Depends-On: T06

Objective: |
  Enforce one terminal finalization per job and idempotency key even when queue delivery, worker retry, or API submission is repeated.

Acceptance-Criteria:
  - id: AC-1
    description: "Two workers racing to finalize the same job result in exactly one terminal event and one artifact set."
    test: "python -m pytest tests/integration/test_idempotent_finalization.py::test_racing_workers_produce_one_terminal_event -q"
  - id: AC-2
    description: "A replayed queue message for a finalized job is acknowledged without writing another terminal event."
    test: "python -m pytest tests/integration/test_idempotent_finalization.py::test_replayed_message_after_finalization_is_noop -q"
  - id: AC-3
    description: "The duplicate-finalization metric remains zero during the duplicate-delivery scenario."
    test: "python -m pytest tests/integration/test_idempotent_finalization.py::test_duplicate_finalization_metric_stays_zero -q"

Files:
  - src/agent_runtime_grid/storage/finalization.py
  - src/agent_runtime_grid/worker/state_machine.py
  - tests/integration/test_idempotent_finalization.py

Context-Refs:
  - docs/ARCHITECTURE.md#minimum-viable-control-surface
  - docs/IMPLEMENTATION_CONTRACT.md#project-specific-rules

---

## T08: Artifact and Log Store

State: done
Owner: codex
Phase: 2
Type: none
Depends-On: T06

Objective: |
  Add local artifact storage, artifact metadata hashing, structured job logs, and cleanup commands for local runs.

Acceptance-Criteria:
  - id: AC-1
    description: "A successful stub job writes a JSON artifact with input digest, worker ID, attempt number, and result summary."
    test: "python -m pytest tests/integration/test_artifacts.py::test_stub_job_writes_json_artifact -q"
  - id: AC-2
    description: "Artifact metadata records path, size, SHA-256 hash, job ID, and creation timestamp."
    test: "python -m pytest tests/integration/test_artifacts.py::test_artifact_metadata_records_hash_and_size -q"
  - id: AC-3
    description: "Structured logs include job ID, run ID, worker ID, trace ID, event type, and sanitized error class without secret values."
    test: "python -m pytest tests/integration/test_logging.py::test_job_logs_are_structured_and_sanitized -q"

Files:
  - src/agent_runtime_grid/artifacts/store.py
  - src/agent_runtime_grid/logging.py
  - src/agent_runtime_grid/cli/cleanup.py
  - tests/integration/test_artifacts.py
  - tests/integration/test_logging.py

Context-Refs:
  - docs/ARCHITECTURE.md#logs-artifacts-and-event-timeline
  - docs/IMPLEMENTATION_CONTRACT.md#credentials-and-secrets

---

## T09: Timeout and Cancellation Handling

State: done
Owner: codex
Phase: 2
Type: none
Depends-On: T06, T08

Objective: |
  Implement deterministic timeout and cancellation paths for queued and running jobs, including event records, runner interruption, and artifact cleanup boundaries.

Acceptance-Criteria:
  - id: AC-1
    description: "A job exceeding its timeout records a `timed_out` event and terminal status without writing a completed artifact."
    test: "python -m pytest tests/integration/test_timeout_cancellation.py::test_timeout_marks_job_timed_out -q"
  - id: AC-2
    description: "Cancelling a queued job records `cancelled` and prevents worker execution."
    test: "python -m pytest tests/integration/test_timeout_cancellation.py::test_cancel_queued_job_prevents_execution -q"
  - id: AC-3
    description: "Cancelling a running job requests runner shutdown and records the cancellation event with worker ID."
    test: "python -m pytest tests/integration/test_timeout_cancellation.py::test_cancel_running_job_records_worker_shutdown -q"

Files:
  - src/agent_runtime_grid/worker/cancellation.py
  - src/agent_runtime_grid/worker/timeouts.py
  - tests/integration/test_timeout_cancellation.py

Context-Refs:
  - docs/ARCHITECTURE.md#data-flow
  - docs/IMPLEMENTATION_CONTRACT.md#control-surface-and-runtime-boundaries

---

## T10: Observability Metrics and Tracing

State: done
Owner: codex
Phase: 3
Type: none
Depends-On: T07, T09

Objective: |
  Add shared tracing and Prometheus metrics for queue lag, worker utilization, job duration, retries, failures, timeouts, DLQ count, duplicate finalization, artifacts, and cost fields.

Acceptance-Criteria:
  - id: AC-1
    description: "The metrics endpoint exposes queue depth, queue lag, worker utilization, job duration histogram, retry count, timeout count, failure count, DLQ count, and duplicate-finalization count."
    test: "python -m pytest tests/integration/test_metrics.py::test_required_runtime_metrics_exposed -q"
  - id: AC-2
    description: "A submitted job trace contains spans for API submission, queue publish, worker lease, job execution, artifact write, and finalization with one trace ID."
    test: "python -m pytest tests/integration/test_tracing.py::test_job_trace_links_runtime_spans -q"
  - id: AC-3
    description: "No span attribute or metric label contains API tokens, provider tokens, or raw job payloads."
    test: "python -m pytest tests/integration/test_observability_safety.py::test_observability_excludes_secrets_and_payloads -q"

Files:
  - src/agent_runtime_grid/observability/metrics.py
  - src/agent_runtime_grid/observability/tracing.py
  - tests/integration/test_metrics.py
  - tests/integration/test_tracing.py
  - tests/integration/test_observability_safety.py

Context-Refs:
  - docs/ARCHITECTURE.md#observability
  - docs/IMPLEMENTATION_CONTRACT.md#observability

---

## T11: Failure Injection and Sample Jobs

State: done
Owner: codex
Phase: 3
Type: none
Depends-On: T10

Objective: |
  Add deterministic stub job runners and failure-injection modes for transient failure, permanent failure, timeout, cancellation, and duplicate submission scenarios.

Acceptance-Criteria:
  - id: AC-1
    description: "A fixed-seed failure plan produces the same counts for transient, permanent, timeout, cancellation, and duplicate-submission cases across repeated runs."
    test: "python -m pytest tests/integration/test_failure_injection.py::test_fixed_seed_failure_plan_is_reproducible -q"
  - id: AC-2
    description: "Transient injected failures retry within configured bounds and permanent injected failures do not retry."
    test: "python -m pytest tests/integration/test_failure_injection.py::test_injected_failure_classes_drive_retry_behavior -q"
  - id: AC-3
    description: "Stub mode records zero model calls and zero model cost for all injected scenarios."
    test: "python -m pytest tests/integration/test_failure_injection.py::test_stub_mode_records_zero_model_cost -q"

Files:
  - src/agent_runtime_grid/jobs/failure_injection.py
  - src/agent_runtime_grid/jobs/stub.py
  - tests/integration/test_failure_injection.py

Context-Refs:
  - docs/ARCHITECTURE.md#inference-model-strategy
  - docs/COST_BUDGET.md#budget-scope

---

## T12: Cost Telemetry Adapter

State: done
Owner: codex
Phase: 3
Type: cost:telemetry
Depends-On: T10, T11

Objective: |
  Add provider-neutral AI cost telemetry records and report generation for optional live LLM sample jobs while keeping stub mode at zero cost.

Acceptance-Criteria:
  - id: AC-1
    description: "A live LLM job records project, run ID, job ID, job type, worker ID, model, provider, input tokens, output tokens, estimated cost, retry count, and environment."
    test: "python -m pytest tests/integration/test_cost_telemetry.py::test_live_job_records_required_cost_fields -q"
  - id: AC-2
    description: "A configured per-run budget overrun blocks additional live LLM dispatch and records a budget-blocked event."
    test: "python -m pytest tests/integration/test_cost_telemetry.py::test_budget_overrun_blocks_live_dispatch -q"
  - id: AC-3
    description: "The cost report command writes `reports/ai_cost_rollup.md` from telemetry input and includes per-run and per-job totals."
    test: "python -m pytest tests/integration/test_cost_telemetry.py::test_cost_rollup_report_contains_run_and_job_totals -q"

Files:
  - src/agent_runtime_grid/cost/telemetry.py
  - src/agent_runtime_grid/cost/rollup.py
  - src/agent_runtime_grid/cli/cost.py
  - tests/integration/test_cost_telemetry.py
  - docs/COST_BUDGET.md

Cost-Budget:
  scope: workflow
  max_cost_usd: 5
  max_model_calls: 500
  max_tool_calls: n/a
  max_retries: 2
  approval_required_when: "model escalation, fan-out increase, retry expansion, or budget overrun"

Context-Refs:
  - docs/ARCHITECTURE.md#cost-budget-and-attribution
  - docs/COST_BUDGET.md#telemetry

---

## T13: CLI and API Batch Workflow

State: done
Owner: codex
Phase: 4
Type: none
Depends-On: T11, T12

Objective: |
  Provide operator commands and API paths for submitting batches, monitoring status, cancelling jobs, cleaning local artifacts, and exporting run reports.

Acceptance-Criteria:
  - id: AC-1
    description: "`agent-runtime-grid submit-batch --count 100 --job-type stub` creates one run and 100 queued jobs."
    test: "python -m pytest tests/integration/test_cli_batch.py::test_submit_batch_creates_expected_job_count -q"
  - id: AC-2
    description: "`agent-runtime-grid status --run-id <id>` prints queued, running, completed, failed, timed out, cancelled, retry, and DLQ counts."
    test: "python -m pytest tests/integration/test_cli_batch.py::test_status_reports_lifecycle_counts -q"
  - id: AC-3
    description: "`agent-runtime-grid cleanup --run-id <id>` removes local artifacts and reports for the run while preserving job metadata."
    test: "python -m pytest tests/integration/test_cli_batch.py::test_cleanup_removes_artifacts_without_metadata_delete -q"

Files:
  - src/agent_runtime_grid/cli/main.py
  - src/agent_runtime_grid/api/routes/jobs.py
  - tests/integration/test_cli_batch.py

Context-Refs:
  - docs/spec.md#feature-area-1-job-submission-and-lifecycle-api
  - docs/spec.md#feature-area-5-failure-injection-and-benchmark-reports

---

## T14: Load Test Harness and Reliability Reports

State: done
Owner: codex
Phase: 4
Type: none
Depends-On: T13

Objective: |
  Add the smoke and v1 proof benchmark harness that submits 100-500 synthetic jobs, configures worker count and failure rates, then writes durable reliability reports.

Acceptance-Criteria:
  - id: AC-1
    description: "The smoke benchmark submits 100 stub jobs, waits for terminal states, and writes `reports/load_smoke.md` with lifecycle counts and p95 duration."
    test: "python -m pytest tests/load/test_benchmark_harness.py::test_smoke_benchmark_writes_report -q"
  - id: AC-2
    description: "The v1 proof benchmark supports 500 jobs, 20 workers, 10% injected failures, timeout cases, and repeated idempotency-key submissions."
    test: "python -m pytest tests/load/test_benchmark_harness.py::test_v1_proof_config_accepts_required_scenario -q"
  - id: AC-3
    description: "The generated report includes completion rate, duplicate-finalization count, retry count, queue lag, p95 duration, artifact completeness, failure classification, and estimated cost."
    test: "python -m pytest tests/load/test_benchmark_harness.py::test_report_contains_required_reliability_fields -q"

Files:
  - src/agent_runtime_grid/cli/benchmark.py
  - tests/load/test_benchmark_harness.py
  - reports/.gitkeep
  - docs/EVIDENCE_INDEX.md

Context-Refs:
  - docs/ARCHITECTURE.md#problem-fit-and-adoption-reality
  - docs/EVIDENCE_INDEX.md
