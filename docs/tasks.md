# Tasks - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-12
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

---

## T15: Root README and Evidence Path

State: done
Owner: codex
Phase: 5
Type: docs
Depends-On: T14

Objective: |
  Add the root operator documentation that explains what the runtime is, what it proves today, how to run it locally, where reports are written, and which limits are still explicit.

Acceptance-Criteria:
  - id: AC-1
    description: "The root README explains the local-first T1 runtime, Redis Streams dispatch, Postgres-backed lifecycle, worker execution, idempotent finalization, reports, and known limits."
    test: "rg -n \"local-first|T1 runtime|Redis Streams|Postgres|idempotent finalization|known limits\" README.md"
  - id: AC-2
    description: "README quickstart includes commands for dependency setup, local services, 100-job smoke run, 500-job reliability proof, and report inspection."
    test: "rg -n \"100-job|500-job|smoke|reliability proof|reports\" README.md docs/EVIDENCE_INDEX.md"
  - id: AC-3
    description: "Known limits are documented without claiming Temporal, Ray, Kubernetes, production sandboxing, SaaS, or autonomous swarm replacement."
    test: "rg -n \"Temporal|Ray|Kubernetes|production sandbox|SaaS|autonomous swarm\" docs/KNOWN_LIMITS.md README.md"

Files:
  - README.md
  - docs/EVIDENCE_INDEX.md
  - docs/ARCHITECTURE.md
  - docs/KNOWN_LIMITS.md
  - reports/README.md

Context-Refs:
  - docs/ARCHITECTURE.md#system-overview
  - docs/ARCHITECTURE.md#non-goals
  - docs/EVIDENCE_INDEX.md

---

## T16: Real Smoke Run Command

State: done
Owner: codex
Phase: 5
Type: benchmark
Depends-On: T15

Objective: |
  Add a single local smoke command that starts from a clean local run state, submits 100 stub jobs, processes them through the queue and workers, verifies lifecycle expectations, and writes a report from actual runtime state.

Acceptance-Criteria:
  - id: AC-1
    description: "`python -m agent_runtime_grid.cli smoke --jobs 100 --workers 4 --failure-rate 0 --mode stub --report reports/smoke.md` submits 100 jobs and processes them through Redis Streams and worker execution."
    test: "python -m pytest tests/integration/test_smoke_command.py::test_smoke_command_processes_jobs_through_runtime -q"
  - id: AC-2
    description: "The smoke report is generated from actual Postgres job/event state and artifact metadata, not hardcoded lifecycle counts."
    test: "python -m pytest tests/integration/test_smoke_command.py::test_smoke_report_uses_runtime_state -q"
  - id: AC-3
    description: "The command exits non-zero when submitted, terminal, duplicate-finalization, artifact-completeness, or cost expectations are violated."
    test: "python -m pytest tests/integration/test_smoke_command.py::test_smoke_command_fails_on_lifecycle_mismatch -q"

Files:
  - src/agent_runtime_grid/cli/smoke.py
  - src/agent_runtime_grid/cli/main.py
  - src/agent_runtime_grid/worker/loop.py
  - src/agent_runtime_grid/cli/benchmark.py
  - tests/integration/test_smoke_command.py
  - reports/README.md

Context-Refs:
  - docs/spec.md#feature-area-5-failure-injection-and-benchmark-reports
  - docs/ARCHITECTURE.md#data-flow
  - docs/IMPLEMENTATION_CONTRACT.md#stub-mode-is-default

---

## T17: Real 500-Job Reliability Proof

State: done
Owner: codex
Phase: 5
Type: benchmark
Depends-On: T16

Objective: |
  Convert the v1 proof benchmark from a supported configuration into a real end-to-end runtime run that submits 500 jobs, uses worker-concurrency equivalent to 20 workers, injects controlled failures, and writes a report from actual state.

Acceptance-Criteria:
  - id: AC-1
    description: "`python -m agent_runtime_grid.cli benchmark v1-proof --jobs 500 --workers 20 --failure-rate 0.10 --include-timeouts --repeat-idempotency-submissions --report reports/v1/reliability_report.md` creates and processes the requested workload."
    test: "python -m pytest tests/load/test_reliability_proof.py::test_v1_proof_runs_against_runtime_state -q"
  - id: AC-2
    description: "The report shows submitted jobs, lifecycle distribution, completion rate, retry count, timeout count, DLQ count, queue lag p95, execution duration p95, artifact completeness, estimated cost, failure classification, and idempotency proof."
    test: "python -m pytest tests/load/test_reliability_proof.py::test_v1_report_contains_required_runtime_evidence -q"
  - id: AC-3
    description: "Repeated idempotency submissions do not create duplicate terminal finalizations, and the report records `duplicate_finalization_count == 0`."
    test: "python -m pytest tests/load/test_reliability_proof.py::test_v1_proof_records_zero_duplicate_finalizations -q"

Files:
  - src/agent_runtime_grid/cli/benchmark.py
  - src/agent_runtime_grid/cli/main.py
  - src/agent_runtime_grid/jobs/failure_injection.py
  - tests/load/test_reliability_proof.py
  - reports/v1/.gitkeep
  - docs/EVIDENCE_INDEX.md

Context-Refs:
  - docs/ARCHITECTURE.md#cost-budget-and-attribution
  - docs/ARCHITECTURE.md#observability
  - docs/EVIDENCE_INDEX.md

---

## T18: Worker Crash and Stale Lease Recovery

State: done
Owner: codex
Phase: 6
Type: reliability
Depends-On: T17

Objective: |
  Prove that a job leased by a worker that exits before acknowledgement or finalization is detected as stale, recovered safely, requeued, and finalized once by another worker.

Acceptance-Criteria:
  - id: AC-1
    description: "A leased job whose worker stops before acknowledgement is detected as stale after the configured lease timeout."
    test: "python -m pytest tests/integration/test_stale_lease_recovery.py::test_stale_lease_is_detected -q"
  - id: AC-2
    description: "Recovery requeues the unfinished job exactly once per recovery cycle, preserves the event trail, and lets another worker complete it."
    test: "python -m pytest tests/integration/test_stale_lease_recovery.py::test_stale_job_requeues_and_completes_once -q"
  - id: AC-3
    description: "Repeated stale recovery respects retry limits, routes exhausted work to DLQ, and keeps terminal finalization idempotent."
    test: "python -m pytest tests/integration/test_stale_lease_recovery.py::test_exhausted_stale_recovery_routes_to_dlq_without_duplicate_finalization -q"

Files:
  - src/agent_runtime_grid/worker/lease.py
  - src/agent_runtime_grid/worker/recovery.py
  - src/agent_runtime_grid/queue/redis_streams.py
  - src/agent_runtime_grid/worker/state_machine.py
  - tests/integration/test_stale_lease_recovery.py
  - docs/FAILURE_MODES.md
  - reports/failure-injection/.gitkeep

Context-Refs:
  - docs/ARCHITECTURE.md#runtime-and-isolation-model
  - docs/IMPLEMENTATION_CONTRACT.md#idempotent-finalization
  - docs/IMPLEMENTATION_CONTRACT.md#job-state-is-database-authoritative

---

## T19: Backpressure and Queue Lag Metrics

State: done
Owner: codex
Phase: 6
Type: observability
Depends-On: T17

Objective: |
  Add runtime-derived queue and backpressure inspection so reports and metrics show queue depth, pending age, consumer lag, leased/running jobs, worker utilization, retry rate, DLQ count, queue wait, and execution duration.

Acceptance-Criteria:
  - id: AC-1
    description: "Queue inspection calculates queue depth, oldest pending age, consumer lag, leased jobs, running jobs, retry rate, DLQ count, p95 queue wait, and p95 execution duration from queue and database state."
    test: "python -m pytest tests/integration/test_queue_metrics.py::test_queue_backpressure_metrics_come_from_runtime_state -q"
  - id: AC-2
    description: "Prometheus output includes the backpressure metrics without raw payloads, API tokens, provider tokens, or secret-like labels."
    test: "python -m pytest tests/integration/test_queue_metrics.py::test_queue_metrics_exclude_secrets_and_payloads -q"
  - id: AC-3
    description: "Smoke and v1 reliability reports include a queue/backpressure section with p95 queue wait and p95 execution duration."
    test: "python -m pytest tests/load/test_reliability_proof.py::test_reports_include_backpressure_section -q"

Files:
  - src/agent_runtime_grid/queue/inspection.py
  - src/agent_runtime_grid/observability/metrics.py
  - src/agent_runtime_grid/cli/benchmark.py
  - tests/integration/test_queue_metrics.py
  - docs/OBSERVABILITY.md

Context-Refs:
  - docs/ARCHITECTURE.md#observability
  - docs/IMPLEMENTATION_CONTRACT.md#observability

---

## T20: API Auth and Local Boundary Proof

State: done
Owner: codex
Phase: 6
Type: security
Depends-On: T13

Objective: |
  Add executable tests and documentation proving that health stays public, mutation and inspection routes enforce token auth when configured, and no-token local mode is allowed only on localhost bindings.

Acceptance-Criteria:
  - id: AC-1
    description: "`GET /health` is public and returns only secret-free health status."
    test: "python -m pytest tests/integration/test_auth_boundary.py::test_health_is_public_and_secret_free -q"
  - id: AC-2
    description: "Mutation and inspection endpoints reject missing or wrong bearer tokens when `API_TOKEN` is configured."
    test: "python -m pytest tests/integration/test_auth_boundary.py::test_non_health_routes_require_configured_token -q"
  - id: AC-3
    description: "No-token mode is accepted only for localhost binding and rejected for non-local host binding."
    test: "python -m pytest tests/integration/test_auth_boundary.py::test_no_token_mode_requires_localhost_bind -q"

Files:
  - src/agent_runtime_grid/api/app.py
  - src/agent_runtime_grid/api/routes/jobs.py
  - src/agent_runtime_grid/config.py
  - tests/integration/test_auth_boundary.py
  - docs/SECURITY_BOUNDARIES.md
  - README.md

Context-Refs:
  - docs/ARCHITECTURE.md#security-boundaries
  - docs/IMPLEMENTATION_CONTRACT.md#authorization
  - docs/IMPLEMENTATION_CONTRACT.md#credentials-and-secrets

---

## T21: Artifact Integrity in Reports

State: done
Owner: codex
Phase: 6
Type: evidence
Depends-On: T17

Objective: |
  Make artifact completeness and integrity first-class report evidence by tying report rows to artifact path, SHA-256, size, job ID, run ID, attempt number, input digest, and creation time.

Acceptance-Criteria:
  - id: AC-1
    description: "Each completed job artifact has path, SHA-256, size, job ID, run ID, attempt number, input digest, and created-at metadata."
    test: "python -m pytest tests/integration/test_artifact_report_integrity.py::test_artifact_metadata_contains_integrity_fields -q"
  - id: AC-2
    description: "Benchmark reports include artifact completeness and integrity summaries derived from actual artifact metadata."
    test: "python -m pytest tests/integration/test_artifact_report_integrity.py::test_report_summarizes_artifact_integrity_from_metadata -q"
  - id: AC-3
    description: "A missing or hash-mismatched artifact causes the smoke or reliability command to exit non-zero."
    test: "python -m pytest tests/integration/test_artifact_report_integrity.py::test_report_generation_fails_on_missing_or_mismatched_artifact -q"

Files:
  - src/agent_runtime_grid/artifacts/store.py
  - src/agent_runtime_grid/cli/benchmark.py
  - tests/integration/test_artifact_report_integrity.py
  - docs/EVIDENCE_INDEX.md

Context-Refs:
  - docs/ARCHITECTURE.md#data-flow
  - docs/ARCHITECTURE.md#observability

---

## T22: Enforce Cost Budget Gates

State: done
Owner: codex
Phase: 6
Type: cost:budget
Depends-On: T12, T17

Objective: |
  Move from cost telemetry records to enforceable per-job, per-run, retry, and live-mode budget gates while keeping stub mode at zero model cost.

Acceptance-Criteria:
  - id: AC-1
    description: "Stub mode records zero cost and rejects any provider call during smoke or reliability runs."
    test: "python -m pytest tests/integration/test_budget_enforcement.py::test_stub_mode_blocks_provider_calls -q"
  - id: AC-2
    description: "Live mode requires explicit per-job and per-run budget configuration before dispatch."
    test: "python -m pytest tests/integration/test_budget_enforcement.py::test_live_mode_requires_explicit_budget -q"
  - id: AC-3
    description: "Budget overrun before dispatch or retry projection blocks the job, emits a budget-blocked event, and makes strict cost rollup exit non-zero."
    test: "python -m pytest tests/integration/test_budget_enforcement.py::test_budget_overrun_blocks_dispatch_and_rollup_fails_strict -q"

Files:
  - src/agent_runtime_grid/cost/telemetry.py
  - src/agent_runtime_grid/cost/rollup.py
  - src/agent_runtime_grid/worker/state_machine.py
  - src/agent_runtime_grid/worker/loop.py
  - src/agent_runtime_grid/cli/cost.py
  - tests/integration/test_budget_enforcement.py
  - docs/COST_BUDGET.md

Cost-Budget:
  scope: workflow
  max_cost_usd: 5
  max_model_calls: 500
  max_tool_calls: n/a
  max_retries: 2
  approval_required_when: "live mode enablement, model escalation, budget increase, retry expansion, or provider change"

Context-Refs:
  - docs/ARCHITECTURE.md#cost-budget-and-attribution
  - docs/COST_BUDGET.md#guardrails
  - docs/IMPLEMENTATION_CONTRACT.md#cost-budget-rules

---

## T23: Eval-Ground-Truth-Lab Integration

State: done
Owner: codex
Phase: 7
Type: integration
Depends-On: T17, T21

Objective: |
  Add an `eval_lab_case` job type that lets Agent Runtime Grid run evaluation cases produced by Eval-Ground-Truth-Lab and produce artifacts that can be consumed by the evaluation report flow.

Acceptance-Criteria:
  - id: AC-1
    description: "Runtime Grid accepts an `eval_lab_case` payload with dataset path, case ID, candidate ID, and stub-or-local execution mode without hardcoded absolute paths."
    test: "python -m pytest tests/integration/test_eval_lab_integration.py::test_eval_lab_case_payload_is_validated_without_hardcoded_paths -q"
  - id: AC-2
    description: "Each eval case runs as a normal queued job and writes an artifact containing case ID, runtime status, eval result path, quality status, attempt count, and latency."
    test: "python -m pytest tests/integration/test_eval_lab_integration.py::test_eval_lab_case_runs_and_writes_cross_linked_artifact -q"
  - id: AC-3
    description: "Runtime reliability reports and Eval-Ground-Truth-Lab output paths cross-link without coupling either project to a fixed local checkout."
    test: "python -m pytest tests/integration/test_eval_lab_integration.py::test_runtime_and_eval_reports_cross_link_without_fixed_checkout -q"

Files:
  - src/agent_runtime_grid/jobs/eval_lab.py
  - src/agent_runtime_grid/jobs/stub.py
  - src/agent_runtime_grid/artifacts/store.py
  - src/agent_runtime_grid/cli/benchmark.py
  - tests/integration/test_eval_lab_integration.py
  - docs/INTEGRATIONS.md

Context-Refs:
  - docs/ARCHITECTURE.md#external-integrations
  - docs/IMPLEMENTATION_CONTRACT.md#worker-network-and-secret-scope

---

## T24: gdev-agent Batch Simulation Job

State: done
Owner: codex
Phase: 7
Type: integration
Depends-On: T23

Objective: |
  Add a `gdev_webhook_eval` job type that runs a local batch of gdev-agent webhook evaluation cases through Runtime Grid and stores raw plus normalized response artifacts for downstream quality checks.

Acceptance-Criteria:
  - id: AC-1
    description: "A local deterministic run executes 50 `gdev_webhook_eval` jobs through Runtime Grid without paid model calls by default."
    test: "python -m pytest tests/integration/test_gdev_agent_integration.py::test_gdev_batch_runs_without_paid_model_calls -q"
  - id: AC-2
    description: "Each job artifact includes request hash, sanitized response, normalized fields, timing, attempt count, and runtime status."
    test: "python -m pytest tests/integration/test_gdev_agent_integration.py::test_gdev_job_artifacts_include_runtime_and_response_evidence -q"
  - id: AC-3
    description: "Runtime Grid reliability output and Eval-Ground-Truth-Lab quality output cross-link for the same gdev-agent case IDs."
    test: "python -m pytest tests/integration/test_gdev_agent_integration.py::test_gdev_runtime_and_eval_outputs_cross_link -q"

Files:
  - src/agent_runtime_grid/jobs/gdev_agent.py
  - src/agent_runtime_grid/jobs/eval_lab.py
  - src/agent_runtime_grid/artifacts/store.py
  - tests/integration/test_gdev_agent_integration.py
  - docs/INTEGRATIONS.md

Cost-Budget:
  scope: workflow
  max_cost_usd: 0
  max_model_calls: 0
  max_tool_calls: n/a
  max_retries: 2
  approval_required_when: "non-local network target, live model mode, or broader worker egress"

Context-Refs:
  - docs/ARCHITECTURE.md#external-integrations
  - docs/IMPLEMENTATION_CONTRACT.md#stub-mode-is-default
  - docs/IMPLEMENTATION_CONTRACT.md#worker-network-and-secret-scope

---

## T25: Failure Injection Report Pack

State: done
Owner: codex
Phase: 8
Type: evidence
Depends-On: T18, T19, T21

Objective: |
  Generate operator-readable failure-injection reports for transient retry, timeout, cancellation, stale worker recovery, duplicate finalization prevention, and DLQ routing.

Acceptance-Criteria:
  - id: AC-1
    description: "Report commands generate markdown files for transient retry, timeout, cancellation, stale worker recovery, duplicate finalization prevention, and DLQ routing."
    test: "python -m pytest tests/integration/test_failure_report_pack.py::test_failure_report_pack_writes_required_reports -q"
  - id: AC-2
    description: "Each report includes scenario, command, expected behavior, actual lifecycle, event trail, metrics, artifact evidence, and known limits."
    test: "python -m pytest tests/integration/test_failure_report_pack.py::test_failure_reports_include_required_sections -q"
  - id: AC-3
    description: "Failure report generation fails when actual lifecycle evidence does not match the scenario expectation."
    test: "python -m pytest tests/integration/test_failure_report_pack.py::test_failure_report_generation_fails_on_evidence_mismatch -q"

Files:
  - src/agent_runtime_grid/cli/failure_reports.py
  - src/agent_runtime_grid/cli/benchmark.py
  - tests/integration/test_failure_report_pack.py
  - docs/FAILURE_MODES.md
  - reports/failure-injection/.gitkeep

Context-Refs:
  - docs/ARCHITECTURE.md#observability
  - docs/EVIDENCE_INDEX.md
  - docs/IMPLEMENTATION_CONTRACT.md#idempotent-finalization

---

## T26: Case Study and Architecture Packaging

State: done
Owner: codex
Phase: 8
Type: docs
Depends-On: T17, T18, T19, T23, T24, T25

Objective: |
  Package the completed reliability and integration evidence into a concise case study, architecture diagram, known-limits update, and final evidence index for technical stakeholders.

Acceptance-Criteria:
  - id: AC-1
    description: "The case study explains the problem, API/Postgres/Redis/workers/artifacts/reports architecture, reliability mechanics, benchmark evidence, failure evidence, trade-offs, and production changes needed."
    test: "rg -n \"Problem|Architecture|Reliability|Benchmark|Failure|Trade-offs|Production\" docs/CASE_STUDY.md"
  - id: AC-2
    description: "Architecture diagram documentation shows API to Postgres to Redis Streams to workers to artifacts/reports, including Eval-Ground-Truth-Lab and gdev-agent integration points."
    test: "rg -n \"API|Postgres|Redis Streams|workers|artifacts|reports|Eval-Ground-Truth-Lab|gdev-agent\" docs/ARCHITECTURE_DIAGRAM.md"
  - id: AC-3
    description: "Known limits and evidence index are updated with real smoke, 500-job proof, stale-worker recovery, backpressure metrics, and integration report paths."
    test: "rg -n \"smoke|500-job|stale|backpressure|Eval-Ground-Truth-Lab|gdev-agent\" docs/KNOWN_LIMITS.md docs/EVIDENCE_INDEX.md"

Files:
  - docs/CASE_STUDY.md
  - docs/ARCHITECTURE_DIAGRAM.md
  - docs/KNOWN_LIMITS.md
  - docs/EVIDENCE_INDEX.md
  - README.md

Context-Refs:
  - docs/ARCHITECTURE.md
  - docs/EVIDENCE_INDEX.md
  - docs/FAILURE_MODES.md

---

## T27: Lease Renewal and Operator Repair CLI

State: done
Owner: codex
Phase: 9
Type: reliability
Depends-On: T18, T19

Objective: |
  Add explicit Redis pending-entry lease renewal plus operator-facing inspect and recover commands so active workers can prevent false stale recovery and local operators can inspect and repair stale leased jobs without reaching into Redis manually.

Acceptance-Criteria:
  - id: AC-1
    description: "Renewing a pending Redis Streams lease resets its idle age, prevents it from being detected as stale under the recovery threshold, and does not create lifecycle events."
    test: "python -m pytest tests/integration/test_operator_repair_cli.py::test_renew_pending_lease_prevents_false_stale_recovery -q"
  - id: AC-2
    description: "The operator inspect command reports queue depth, pending lease count, stale lease count, and oldest pending age from runtime state without exposing raw payloads or secrets."
    test: "python -m pytest tests/integration/test_operator_repair_cli.py::test_operator_inspect_reports_queue_state_without_payloads -q"
  - id: AC-3
    description: "The operator recover command invokes stale lease recovery, prints detected/requeued/DLQ/acknowledged counts, and leaves recovered work processable by a replacement worker."
    test: "python -m pytest tests/integration/test_operator_repair_cli.py::test_operator_recover_requeues_stale_work_for_replacement_worker -q"

Files:
  - src/agent_runtime_grid/queue/redis_streams.py
  - src/agent_runtime_grid/worker/lease.py
  - src/agent_runtime_grid/worker/recovery.py
  - src/agent_runtime_grid/cli/operator.py
  - src/agent_runtime_grid/cli/main.py
  - tests/integration/test_operator_repair_cli.py
  - docs/OPERATIONS.md
  - docs/KNOWN_LIMITS.md
  - docs/EVIDENCE_INDEX.md

Context-Refs:
  - docs/ARCHITECTURE.md#runtime-and-isolation-model
  - docs/IMPLEMENTATION_CONTRACT.md#job-state-is-database-authoritative
  - docs/IMPLEMENTATION_CONTRACT.md#async-redis
  - docs/FAILURE_MODES.md#stale-worker-lease

---

## T28: Automated Worker Heartbeat Lease Renewal

State: done
Owner: codex
Phase: 10
Type: reliability
Depends-On: T18, T27

Objective: |
  Add worker-owned heartbeat renewal for active Redis Streams leases so long-running jobs do not become stale while the worker is alive, without changing Postgres lifecycle authority or writing heartbeat lifecycle events.

Acceptance-Criteria:
  - id: AC-1
    description: "A worker processing a long-running job renews the pending Redis Streams lease often enough that stale recovery with a threshold above the heartbeat interval detects no stale lease while the job is active."
    test: "python -m pytest tests/integration/test_worker_heartbeat.py::test_worker_heartbeat_prevents_false_stale_recovery_for_long_job -q"
  - id: AC-2
    description: "Heartbeat renewal stops after terminal completion and the Redis entry is acknowledged, leaving no pending lease and no heartbeat lifecycle events."
    test: "python -m pytest tests/integration/test_worker_heartbeat.py::test_heartbeat_stops_after_terminal_acknowledgement -q"
  - id: AC-3
    description: "Disabling heartbeat preserves existing stale recovery behavior for a worker that is still running longer than the stale threshold."
    test: "python -m pytest tests/integration/test_worker_heartbeat.py::test_disabled_heartbeat_preserves_stale_recovery_behavior -q"

Files:
  - src/agent_runtime_grid/worker/loop.py
  - src/agent_runtime_grid/queue/redis_streams.py
  - tests/integration/test_worker_heartbeat.py
  - docs/OPERATIONS.md
  - docs/KNOWN_LIMITS.md
  - docs/EVIDENCE_INDEX.md

Context-Refs:
  - docs/ARCHITECTURE.md#runtime-and-isolation-model
  - docs/ARCHITECTURE.md#data-flow
  - docs/IMPLEMENTATION_CONTRACT.md#job-state-is-database-authoritative
  - docs/IMPLEMENTATION_CONTRACT.md#async-redis
  - docs/FAILURE_MODES.md#worker-crash-after-lease

---

## T29: Cross-Project Runtime Proof

State: done
Owner: codex
Phase: 11
Type: integration
Depends-On: T23, T24, T26, T28

Objective: |
  Add a full-stack proof command that ingests ready Eval-Ground-Truth-Lab dataset/report artifacts and ready gdev-agent artifacts, runs selected cases through Agent Runtime Grid as batch jobs, and writes a runtime reliability report with cross-project links.

Acceptance-Criteria:
  - id: AC-1
    description: "The full-stack proof runner validates existing Eval Lab report, gdev-agent artifact, and dataset paths before submitting Grid jobs."
    test: "python -m pytest tests/integration/test_full_stack_proof.py::test_full_stack_proof_validates_cross_project_artifacts -q"
  - id: AC-2
    description: "The proof run submits Eval Lab/gdev cases as normal `gdev_webhook_eval` jobs, processes them through Redis Streams and workers, and produces valid runtime artifacts."
    test: "python -m pytest tests/integration/test_full_stack_proof.py::test_full_stack_proof_runs_cases_through_grid -q"
  - id: AC-3
    description: "The generated report cross-links Eval Lab report path, gdev-agent artifact path, Grid run ID, lifecycle counts, artifact integrity, queue metrics, and known limits without exposing raw secret-like payload fields."
    test: "python -m pytest tests/integration/test_full_stack_proof.py::test_full_stack_report_cross_links_quality_and_runtime_evidence -q"

Files:
  - src/agent_runtime_grid/cli/proof.py
  - src/agent_runtime_grid/cli/main.py
  - tests/integration/test_full_stack_proof.py
  - docs/INTEGRATIONS.md
  - docs/CASE_STUDY.md
  - docs/EVIDENCE_INDEX.md
  - README.md
  - reports/README.md
  - reports/full-stack/.gitkeep

Cost-Budget:
  scope: workflow
  max_cost_usd: 0
  max_model_calls: 0
  max_tool_calls: n/a
  max_retries: 2
  approval_required_when: "live gdev-agent HTTP adapter, external egress, live model mode, or broader worker secret scope"

Context-Refs:
  - docs/ARCHITECTURE.md#external-integrations
  - docs/IMPLEMENTATION_CONTRACT.md#stub-mode-is-default
  - docs/IMPLEMENTATION_CONTRACT.md#worker-network-and-secret-scope
  - docs/INTEGRATIONS.md
