# Agent Runtime Grid

Agent Runtime Grid is a local-first T1 runtime for executing batches of AI and agent jobs with queue-backed dispatch, durable state, bounded retries, timeouts, cancellation, idempotent finalization, artifacts, logs, metrics, cost telemetry, and reliability reports.

The project is built around a deterministic control plane. Scheduling, Redis Streams dispatch, Postgres-backed lifecycle state, retry policy, budget boundaries, and terminal state transitions are owned by code. Optional AI behavior belongs inside bounded sample job payloads, not inside runtime control decisions.

## Why This Exists

AI and agent workloads often start as one-off scripts. That breaks down when operators need to run many jobs, recover from partial failure, prove what happened, and compare reliability across runs.

Agent Runtime Grid provides the execution layer for that shape of work:

- submit many jobs as one run
- dispatch through Redis Streams
- process with bounded workers
- persist lifecycle and event history in Postgres
- retry transient failures
- stop timed-out or cancelled work
- prevent duplicate terminal finalization
- write artifacts and reports
- keep default execution in stub mode with zero model cost

## What Works Today

The current implementation proves the core runtime mechanics:

- job submission and idempotency-key handling
- Postgres job registry and append-only event log
- Redis Streams publish, lease, acknowledge, and DLQ paths
- worker lifecycle state transitions
- transient retry and non-retryable policy failure handling
- timeout and cancellation terminal paths
- idempotent finalization with a database guard
- JSON artifacts with input digests
- sanitized structured job log records
- runtime metrics and in-memory trace spans
- queue and backpressure inspection
- deterministic failure injection plans
- cost telemetry records and rollup output
- enforceable stub/live budget gates and strict cost rollup checks
- batch CLI helpers and benchmark report rendering
- Eval-Ground-Truth-Lab case execution through normal queue/workers
- deterministic gdev-agent webhook evaluation jobs
- full-stack artifact proof command that ingests ready Eval Lab and gdev-agent
  artifacts, runs selected cases through Grid workers, and writes cross-linked
  runtime evidence
- failure-injection report pack generation
- committed reviewer snapshots under `docs/evidence/` for smoke, reliability,
  failure-injection, and cross-project artifact proof surfaces
- operator queue inspection, stale recovery, and pending lease renewal primitives
- automated worker heartbeat renewal for active long-running jobs

Current baseline: `80 passed` with one upstream FastAPI/Starlette deprecation warning.

## Quickstart

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv .venv
PATH=.venv/bin:$PATH python -m pip install -e . -r requirements-dev.txt
```

Start local services:

```bash
docker-compose up -d postgres redis
```

Run the baseline:

```bash
PATH=.venv/bin:$PATH python -m pytest -q
PATH=.venv/bin:$PATH ruff check
PATH=.venv/bin:$PATH ruff format --check
```

Run the current smoke report harness:

```bash
PATH=.venv/bin:$PATH python -m pytest tests/load/test_benchmark_harness.py::test_smoke_benchmark_writes_report -q
```

Run the real 100-job smoke command:

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli smoke \
  --jobs 100 \
  --workers 4 \
  --failure-rate 0 \
  --mode stub \
  --report reports/smoke.md
```

Run the real 500-job reliability proof:

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli benchmark v1-proof \
  --jobs 500 \
  --workers 20 \
  --failure-rate 0.10 \
  --include-timeouts \
  --repeat-idempotency-submissions \
  --report reports/v1/reliability_report.md
```

The smoke and 500-job reliability proof commands now run end to end through local Redis Streams, workers, Postgres state, artifacts, and report validation.

Run the cross-project artifact proof once Eval Lab and gdev-agent artifacts exist:

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli proof full-stack \
  --eval-lab-dataset ../Eval-Ground-Truth-Lab/datasets/gdev_agent/triage_v1.jsonl \
  --eval-lab-report ../Eval-Ground-Truth-Lab/reports/gdev-agent/baseline_report.md \
  --gdev-artifact ../gdev-agent/eval/results/last_run.json \
  --jobs 20 \
  --workers 4 \
  --report reports/full-stack/runtime_report.md
```

This submits selected Eval Lab/gdev cases as normal Grid jobs, dispatches them
through Redis Streams, completes them with workers, writes artifacts and
Eval-compatible result JSON, then renders one report linking quality evidence
and runtime reliability evidence. This is `full-stack-artifact-proof`: it uses
ready artifacts and deterministic jobs by default. It does not call live
gdev-agent over HTTP. A future `full-stack-live-local` mode would make workers
trigger Eval Lab or gdev-agent HTTP execution end to end.

## Architecture

The runtime path is:

```text
API / CLI
  -> Postgres job registry and event log
  -> Redis Streams queue
  -> worker runtime
  -> job runner
  -> artifact store
  -> metrics, traces, and reports
```

Core references:

- `docs/ARCHITECTURE.md` - canonical architecture and runtime boundaries
- `docs/ARCHITECTURE_DIAGRAM.md` - compact runtime and evidence-flow diagram
- `docs/STACK_OVERVIEW.md` - three-project stack map and live/artifact proof split
- `docs/CASE_STUDY.md` - concise reliability and integration case study
- `docs/IMPLEMENTATION_CONTRACT.md` - immutable implementation rules
- `docs/tasks.md` - task plan and acceptance criteria
- `docs/EVIDENCE_INDEX.md` - evidence and verification pointers
- `docs/KNOWN_LIMITS.md` - known limits and non-goals
- `docs/SECURITY_BOUNDARIES.md` - API auth and local bind safety rules
- `docs/OBSERVABILITY.md` - queue/backpressure metrics and report definitions
- `docs/INTEGRATIONS.md` - Eval Lab and gdev-agent integration boundaries
- `docs/OPERATIONS.md` - local operator commands for queue inspection and stale recovery
- `reports/README.md` - report locations and expectations
- `docs/evidence/` - committed reviewer snapshots for generated report surfaces

## Operational Guarantees

Current local guarantees:

- durable job lifecycle state is Postgres-authoritative
- Redis Streams is treated as delivery state, not final lifecycle authority
- terminal state changes are guarded by idempotent finalization
- default stub execution makes no paid model calls
- secrets and raw job payloads must not appear in logs, metrics, traces, or committed config
- health is public and secret-free
- non-health API routes require `API_TOKEN` when configured
- no-token API mode is allowed only on localhost bindings
- stub mode blocks provider calls and live dispatch requires explicit budgets
- local mode stays inside T1 Docker Compose boundaries

Planned proof gaps are tracked in `docs/tasks.md`:

- T16 real 100-job smoke command - implemented
- T17 real 500-job reliability proof - implemented
- T18 worker crash and stale lease recovery - implemented
- T19 backpressure and queue lag metrics - implemented
- T20 API auth and local boundary proof - implemented
- T21 artifact integrity in reports - implemented
- T22 cost budget gates - implemented
- T23 Eval-Ground-Truth-Lab integration - implemented
- T24 gdev-agent batch simulation - implemented
- T25 failure-injection report pack - implemented
- T29 cross-project runtime proof - implemented

## Reports

Reports are written under `reports/`. Generated report contents are ignored by
git so local benchmark output does not churn history. Stable placeholders,
report documentation, and curated committed snapshots under `docs/evidence/`
are committed for reviewer inspection.

Evidence index: `docs/EVIDENCE_INDEX.md`.

Report guide: `reports/README.md`.

Committed snapshots:

- `docs/evidence/runtime-smoke-100.md`
- `docs/evidence/runtime-reliability-500.md`
- `docs/evidence/full-stack-artifact-proof.md`
- `docs/evidence/failure-injection-pack-summary.md`

## Known Limits

The current known limits are intentional and documented in `docs/KNOWN_LIMITS.md`.

Short version:

- not a Temporal replacement
- not a Ray replacement
- not a Kubernetes replacement
- not a production sandbox for arbitrary untrusted code
- not a SaaS or multi-tenant billing system
- not an autonomous swarm
- not exactly-once execution

The v1 target is narrower: local-first reliability evidence for many AI and agent jobs under queue, worker, retry, timeout, cancellation, artifact, cost, and reporting controls.
