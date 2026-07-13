# Agent Runtime Grid

Agent Runtime Grid is an alpha, local-first execution and reliability harness for
batches of AI and agent jobs. Its control path is deterministic: Postgres owns
lifecycle state, Redis Streams owns delivery state, and workers enforce bounded
retry, timeout, cancellation, budget, artifact, and terminal-state rules.

This repository is the optional runtime component in the portfolio. It is not a
hosted service, a production claim, or a dependency of Eval Ground Truth Lab.

## Start here: a five-minute local proof

Prerequisites: Python 3.12, Docker, and Docker Compose.

```bash
python3 -m venv .venv
PATH=.venv/bin:$PATH python -m pip install -e . -r requirements-dev.txt
docker-compose up -d postgres redis
PATH=.venv/bin:$PATH agent-runtime-grid smoke \
  --jobs 20 \
  --workers 4 \
  --mode stub \
  --reset-local-database \
  --report reports/smoke.md
```

`--reset-local-database` is deliberately explicit. The command refuses to drop
remote or unrelated databases. Do not point the proof commands at production
infrastructure.

Verify the implementation before trusting a report:

```bash
PATH=.venv/bin:$PATH ruff check src tests
PATH=.venv/bin:$PATH ruff format --check src tests
PATH=.venv/bin:$PATH python -m pytest -q
```

## What is implemented

- idempotent batch submission and Postgres lifecycle/event records;
- Redis Streams publish, lease, acknowledge, retry, stale recovery, and DLQ paths;
- bounded workers with timeout and cancellation terminal paths;
- a database terminal-finalization guard;
- separate persistent counts for rejected finalization attempts and actual
  duplicate terminal-event invariant violations;
- content-digested JSON artifacts and integrity checks;
- deterministic failure injection and zero-cost stub execution;
- cost records and enforceable budget boundaries;
- queue/backpressure inspection and in-process metrics/traces;
- smoke, reliability, failure-injection, Eval Lab, and gdev artifact proof paths.

The default Compose file starts only the dependencies used by these paths:
Postgres and Redis. Earlier placeholder `api`, `worker`, Prometheus, and Grafana
services were removed because they did not run or observe the product.

## Product boundary

```text
CLI or Python caller
  -> Postgres job registry and append-only event history
  -> Redis Streams delivery queue
  -> bounded in-process worker pool
  -> job adapter
  -> artifacts + reliability evidence
```

The FastAPI module remains experimental library code and is not part of the
default runnable surface. There is no long-running worker service contract yet.
Metrics can be rendered in process; this repository does not claim a connected
dashboard deployment.

## Reliability proof

The larger deterministic proof injects retry, timeout, and idempotency cases:

```bash
PATH=.venv/bin:$PATH agent-runtime-grid benchmark v1-proof \
  --jobs 500 \
  --workers 20 \
  --failure-rate 0.10 \
  --include-timeouts \
  --repeat-idempotency-submissions \
  --reset-local-database \
  --report reports/v1/reliability_report.md
```

The proof uses stub jobs and reports an estimated model cost of zero. It is local
reliability evidence, not load capacity or production SLO evidence.

## Relationship to the portfolio

- [Eval Ground Truth Lab](https://github.com/ashishki/Eval-Ground-Truth-Lab)
  owns datasets, comparison, and release gates. Runtime Grid is optional.
- [gdev-agent](https://github.com/ashishki/gdev-agent) is one reference workload;
  its own repository owns tenant isolation, application behavior, and quality.
- AI Workflow Playbook is a governance companion, not a runtime dependency.
- The planned `ai-workflow-reliability-lab` umbrella pins compatible component
  releases; it does not absorb this repository or its history.

Cross-project artifact proof commands are documented in
[`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md). They consume explicitly supplied
local artifacts and do not prove a hosted integration.

## Evidence and interpretation

Generated reports live under `reports/` and are ignored by default. Curated
snapshots under [`docs/evidence/`](docs/evidence/) show report shape, while the
[`evidence index`](docs/EVIDENCE_INDEX.md) states how to reproduce them. A
committed snapshot is illustrative until its command, source revision, inputs,
and checksums are independently verified.

Important evidence terms:

- `idempotency replay` means the same submission key returned the existing job;
- `finalization conflict attempt` means the DB guard rejected a competing
  terminal write;
- `duplicate terminal event` means an invariant violation and must remain zero;
- `artifact integrity` validates recorded bytes, not the semantic quality of an
  agent response.

## Known limits

Runtime Grid is not:

- a hosted or multi-tenant SaaS;
- a Kubernetes, Temporal, or Ray replacement;
- exactly-once execution;
- a production sandbox for untrusted arbitrary code;
- a general autonomous-agent framework;
- evidence of customer traffic, production scale, or an external user.

The current supported boundary is a local CLI/library proof with Postgres,
Redis, deterministic adapters, and inspectable evidence. See
[`docs/KNOWN_LIMITS.md`](docs/KNOWN_LIMITS.md) for the longer list.

## Open-source scope

The project is licensed under Apache-2.0. The direct dependency and service
license review is recorded in [`docs/LICENSE_REVIEW.md`](docs/LICENSE_REVIEW.md).
Contributions are intentionally limited to reproducible runtime defects,
bounded adapters, evidence verification, and documentation corrections; see
[`CONTRIBUTING.md`](CONTRIBUTING.md) and [`SECURITY.md`](SECURITY.md).

## Reference documents

- [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md)
- [`docs/ARCHITECTURE_DIAGRAM.md`](docs/ARCHITECTURE_DIAGRAM.md)
- [`docs/EVIDENCE_INDEX.md`](docs/EVIDENCE_INDEX.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/SECURITY_BOUNDARIES.md`](docs/SECURITY_BOUNDARIES.md)
- [`docs/OBSERVABILITY.md`](docs/OBSERVABILITY.md)
- [`reports/README.md`](reports/README.md)
