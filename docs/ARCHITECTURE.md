# Architecture

Last updated: 2026-07-13. Status: alpha, local-first CLI/library.

## Supported runtime path

```text
Typer CLI or Python caller
  -> Postgres job registry, events, finalization guard, conflict records
  -> Redis Streams delivery and pending state
  -> bounded in-process worker pool
  -> allowlisted job adapter
  -> local artifacts
  -> Markdown + versioned JSON evidence + checksum manifest
```

Postgres is authoritative for lifecycle state. Redis is authoritative only for
delivery, leases, consumer lag, and DLQ state. At-least-once delivery is
expected; terminal writes are protected by a unique database guard.

## Runtime components

| Component | Responsibility | Current surface |
|---|---|---|
| `storage/` | Jobs, events, finalizations, conflict attempts, costs | Postgres/SQLAlchemy |
| `queue/` | Publish, lease, acknowledge, retry, pending recovery, DLQ | Redis Streams |
| `worker/` | Bounded execution, timeout, cancellation, retry, stale recovery | In-process async workers |
| `jobs/` | Deterministic stub and bounded Eval/gdev adapters | Allowlisted Python runners |
| `artifacts/` | JSON artifact write and byte-integrity validation | Local filesystem |
| `evidence.py` | Portable JSON bundle, SHA-256 manifest, strict verifier | CLI-generated evidence |
| `observability/` | In-process metrics, sanitized logs, trace records | Library surface only |
| `cli/` | Submit, inspect, smoke, reliability, proof, verification | Supported entry point |
| `api/` | Typed experimental endpoints | Not in default Compose/support contract |

The default Compose topology contains only Postgres and Redis. Workers are
started by proof commands. There is no claimed long-running worker service,
connected Prometheus deployment, or Grafana dashboard.

## Deterministic authority

Code, not model output, owns schema validation, job allowlisting, idempotency,
retry eligibility, timeout, cancellation, budgets, terminal transitions,
artifact hashing, and evidence verification. Optional AI behavior must stay
inside a bounded adapter with explicit inputs, outputs, cost, and side effects.

## Finalization semantics

The first terminal transaction creates one `job_finalizations` row, updates the
job, and appends one terminal event. A competing attempt is rejected by the
unique key and recorded in `finalization_conflict_attempts`.

These are deliberately different metrics:

- finalization conflict attempts may be non-zero under a race;
- duplicate terminal-event invariant violations must be zero.

Reports calculate both from Postgres, so the values persist across process
restarts. Idempotency-key replays are measured separately.

## Evidence model

Each real smoke, reliability, or full-stack proof writes three sibling files:

- `<run>.md` for review;
- `<run>.json` using `agent-runtime-grid.run-evidence.v1`;
- `<run>.manifest.json` with SHA-256 for the first two files.

The JSON records command configuration, deterministic seed where applicable,
source revision/dirty state, portable environment metadata, lifecycle metrics,
and artifact hashes. Absolute local paths are replaced with portable artifact or
input references. `agent-runtime-grid verify-evidence` rejects changed, missing,
duplicated, path-traversing, symlinked, or extra sidecar files.

This is tamper-evident local evidence, not immutable storage or an attestation by
an independent party.

## Destructive-operation boundary

Proof commands do not reset a database by default. The explicit
`--reset-local-database` option accepts only loopback/Compose hosts and the
`agent_runtime_grid` or `agent_runtime_grid_test` database names. It rejects
remote and unrelated databases even when the flag is present.

## Integrations

Eval Ground Truth Lab owns evaluation data and release decisions. gdev-agent owns
application behavior and tenant isolation. Runtime Grid may execute bounded
adapters or consume their supplied artifacts, but it does not import their code
or make either project depend on this runtime.

## Non-goals

- hosted control plane or production SLOs;
- exactly-once execution;
- untrusted arbitrary-code sandboxing;
- general scheduler or autonomous swarm;
- replacement for Temporal, Ray, Kubernetes, or Airflow;
- customer, tenant, or production-traffic claims.
