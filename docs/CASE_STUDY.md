# Case study: separating delivery races from lifecycle defects

## Problem

At-least-once queues can deliver or process the same work more than once. A
runtime must show both that it observed contention and that contention did not
produce duplicate terminal state. A single counter hardcoded to zero cannot
support either conclusion.

## Implementation

Runtime Grid uses a unique Postgres row per job as the terminal guard. The first
transaction records the finalization and terminal event. A competing transaction
records a durable `finalization_conflict_attempts` row without updating lifecycle
state. Reports query that table and independently count duplicate terminal events.

Idempotency-key replay is a third concept: it returns an existing job before a
worker reaches finalization and is reported separately.

## Reproduction

```bash
docker-compose up -d postgres redis
PATH=.venv/bin:$PATH python -m pytest \
  tests/integration/test_idempotent_finalization.py -q
```

The race test requires one successful finalization, one persisted rejected
attempt, and zero duplicate terminal events. Replay and stale-recovery tests
require zero terminal defects while preserving their own event trails.

Run the local reliability proof and verify its machine-readable evidence:

```bash
PATH=.venv/bin:$PATH agent-runtime-grid benchmark v1-proof \
  --jobs 500 --workers 20 --failure-rate 0.10 \
  --include-timeouts --repeat-idempotency-submissions \
  --reset-local-database \
  --report reports/v1/reliability_report.md
PATH=.venv/bin:$PATH agent-runtime-grid verify-evidence \
  --manifest reports/v1/reliability_report.manifest.json
```

The proof is deterministic, local, synthetic, and zero-model-cost. It does not
establish production throughput, availability, or external adoption.
