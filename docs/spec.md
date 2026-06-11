# Specification - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-11
Status: Draft

---

## Overview

Agent Runtime Grid provides a local, queue-driven runtime for submitting and operating many synthetic AI or agent jobs under controlled concurrency and failure. v1 proves operational behavior: durable job lifecycle state, worker leasing, retries, idempotent finalization, cancellation, timeouts, artifacts, logs, cost attribution, metrics, traces, and benchmark evidence.

The default demo path uses deterministic stub jobs so the full reliability benchmark can run without paid model calls. Optional live LLM jobs are gated by budget configuration and human approval.

---

## User Roles

| Role | Needs |
|------|-------|
| AI engineer / portfolio owner | Submit batches, run failure-injection scenarios, inspect evidence, and produce a credible runtime report. |
| Platform engineer | Inspect architecture, state transitions, idempotency behavior, worker isolation, metrics, and recovery semantics. |
| Hiring reviewer | Run one command, observe concurrent job execution, and verify reports without needing paid LLM access. |
| Future operator | Configure job types, budgets, worker counts, and external egress only within explicit approval boundaries. |

---

## Feature Area 1: Job Submission and Lifecycle API

Description: Operators can submit single jobs or batches through API and CLI. Each job has a type, payload, idempotency key, timeout, retry limit, budget boundary, and artifact expectations. The runtime exposes status, event timeline, cancellation, and artifact metadata.

Acceptance criteria:

1. `POST /jobs` accepts a valid stub job request and returns HTTP 202 with `job_id`, `status=queued`, and a trace ID.
2. Repeating `POST /jobs` with the same idempotency key and payload returns the original `job_id` without creating a second finalization record.
3. `GET /jobs/{job_id}` returns the latest status, retry count, worker ID when assigned, trace ID, and artifact references.
4. `POST /jobs/{job_id}/cancel` moves a queued job to `cancelled` or requests cancellation for a running job and records an event.
5. Invalid job type, timeout above configured bound, retry bound above configured maximum, or missing idempotency key returns HTTP 422 with a sanitized error body.

Out of scope:

- Full SaaS UI.
- Multi-tenant identity provider.
- Arbitrary user-uploaded executable code.

---

## Feature Area 2: Queue Dispatch and Worker Execution

Description: The runtime uses Redis Streams and a worker pool to process queued jobs with at-least-once delivery and idempotent finalization. Workers lease jobs, renew active work, execute bounded runners, and classify terminal states.

Acceptance criteria:

1. A worker can lease a queued job, mark it running, execute the stub runner, and finalize it as completed with exactly one terminal event.
2. A transient failure is retried no more than the job retry limit and records the retry reason and attempt number.
3. A non-retryable policy failure goes to failed without retry.
4. A stale running job whose worker lease expires is requeued or marked timed out according to configured failure class.
5. Replayed delivery of an already-finalized job does not create duplicate artifacts or terminal events.

Out of scope:

- Kubernetes Jobs.
- GPU scheduling.
- Persistent privileged workers.

---

## Feature Area 3: Logs, Artifacts, and Event Timeline

Description: Each job produces an immutable event timeline and may produce logs and artifacts under a local artifact root. Reports must be able to verify artifact completeness for a benchmark run.

Acceptance criteria:

1. Every job has an ordered event timeline containing submission, queue publish, lease, start, retry or failure when applicable, artifact write, and terminal finalization events.
2. Stub jobs write a small JSON artifact containing input digest, worker ID, attempt number, and result summary.
3. Artifact metadata records path, size, content hash, job ID, and creation timestamp.
4. Logs contain job ID, run ID, worker ID, trace ID, event type, and sanitized error class without secrets.
5. Cleanup command removes local artifacts and reports for a selected run without deleting job metadata unless explicitly requested.

Out of scope:

- Long-term artifact retention policy.
- Cloud object storage in v1.

---

## Feature Area 4: Observability and Cost Tracking

Description: The system emits operational metrics and traces for queue behavior, worker utilization, retries, failures, timeouts, artifacts, and optional LLM cost.

Acceptance criteria:

1. Prometheus metrics expose queue depth, queue lag, worker utilization, job duration histogram, retry count, timeout count, failure count, DLQ count, and duplicate-finalization count.
2. OpenTelemetry traces connect API submission, queue publish, worker lease, job execution, artifact write, and finalization through one trace ID.
3. Optional live LLM jobs record input tokens, output tokens, estimated cost, model, provider, retry count, and job attribution fields.
4. Stub mode records zero model cost and fails a test if a model provider is called.
5. Cost budget overrun blocks additional live LLM job dispatch for the run and records a budget event.

Out of scope:

- Provider billing reconciliation with external invoices.
- Production-grade cost dashboard.

---

## Feature Area 5: Failure Injection and Benchmark Reports

Description: Operators can run a synthetic benchmark that submits 100-500 jobs, configures worker count and failure rates, and writes a durable report.

Acceptance criteria:

1. A benchmark command submits a configurable number of stub jobs, defaulting to 100 for smoke runs and supporting 500 for the v1 proof run.
2. Failure injection supports transient failure, permanent failure, timeout, cancellation, and duplicate submission scenarios.
3. The benchmark report includes completion rate, duplicate-finalization count, retry count, timeout count, queue lag, p95 duration, failure classification, artifact completeness, and estimated cost.
4. With a fixed seed, the benchmark produces the same number of injected failure cases across repeated runs.
5. A reviewer can run the smoke benchmark locally without paid LLM credentials.

Out of scope:

- Public claims of production scale.
- Benchmarking external LLM quality.

---

## Feature Area 6: Runtime Safety and Approval Boundaries

Description: v1 keeps worker permissions narrow and blocks runtime expansion without a documented decision.

Acceptance criteria:

1. Workers default to local service egress only; optional LLM or GitHub egress requires explicit config and a human-approved job type.
2. Job containers do not perform runtime package installation or toolchain mutation.
3. New external side-effecting job types require a documented approval boundary before dispatch is allowed.
4. Secrets are loaded only from environment variables or uncommitted local `.env` files and are never logged.
5. Any proposal to move from T1 to T2/T3 requires an ADR and Phase 1 artifact update before implementation.

Out of scope:

- Secure sandboxing for arbitrary untrusted code.
- Compliance framework certification.
