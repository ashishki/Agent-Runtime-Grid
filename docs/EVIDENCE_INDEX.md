# Evidence Index - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-11

Purpose:

- Index durable proof so agents can retrieve prior evidence quickly.
- Avoid repeated archaeology across tests, benchmark reports, review reports, and manual checks.

This file is not authoritative by itself. Every row must point to the real artifact that carries the evidence.

---

## When To Use

Maintain this file for:

- Phase 1 audit results.
- Runtime verification records for risky or boundary-changing tasks.
- Load-test and failure-injection reports.
- Cost telemetry reports once T12 exists.
- Review findings and fix evidence.

---

## Evidence Table

| Topic / Finding / Task | Artifact type | Location | Scope covered | Last verified | Canonical? |
|------------------------|---------------|----------|---------------|---------------|------------|
| Phase 1 validation | audit | `docs/audit/PHASE1_AUDIT.md` | Standard-mode planning package structure and consistency | 2026-06-11 | Yes |
| Phase 1 implementation review | review | `docs/audit/PHASE1_IMPLEMENTATION_REVIEW.md` | T01-T03 implementation, baseline, CI contract, security boundary checks | 2026-06-11 | Yes |
| Phase 2 implementation review | review | `docs/audit/PHASE2_IMPLEMENTATION_REVIEW.md` | T04-T09 implementation, persistence, queue, worker, finalization, artifacts/logs, timeout/cancellation checks | 2026-06-11 | Yes |
| Phase 3 implementation review | review | `docs/audit/PHASE3_IMPLEMENTATION_REVIEW.md` | T10-T12 implementation, observability, failure injection, and cost telemetry checks | 2026-06-11 | Yes |
| Phase 4 final review | review | `docs/audit/PHASE4_FINAL_REVIEW.md` | T13-T14 implementation and full T01-T14 baseline/policy review | 2026-06-11 | Yes |
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
| Phase 1 audit index | audit index | `docs/audit/AUDIT_INDEX.md` | Pointers to audit results | 2026-06-11 | Yes |

---

## Retrieval Rules

- Prefer rows that match the current task's `Context-Refs`, open findings, or active capability tags.
- If an evidence row points to a stale or missing artifact, fix the artifact or remove the row.
- Do not treat a journal note as proof when a test, eval, audit, or review report exists.
