# Architecture - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-11
Status: Draft

---

## System Overview

Agent Runtime Grid is a queue-driven runtime for executing many AI or agent jobs with durable state, bounded worker execution, retries, timeouts, idempotent finalization, artifacts, logs, cost tracking, and observability. It serves AI engineers, platform engineers, and operators who need evidence that agent workloads can be operated under concurrency and failure. The control plane is deterministic: scheduling, state transitions, retry policy, budget enforcement, and audit events are code-owned, while optional AI behavior is limited to bounded sample job payloads.

---

## Problem Fit and Adoption Reality

### Problem-First Entry Gate

| Question | Answer |
|----------|--------|
| Concrete operational pain | AI and agent workflows are often run as scripts or ad hoc one-off jobs that fail silently, duplicate work, lose intermediate state, and lack retry, timeout, cost, and observability semantics under concurrent load. |
| Current workaround | Operators run scripts manually, schedule simple cron jobs, call LLM APIs synchronously, inspect logs by hand, and rerun failed tasks manually. |
| Why existing process is insufficient | Scripts, ordinary CI, and manual SOPs do not prove dispatch reliability, backpressure handling, worker isolation, lifecycle control, idempotency, cost attribution, or recovery after partial failure. |
| First user / operator who feels the pain | The operator running agent simulations and evaluation batches; secondarily an AI platform or agent infrastructure team evaluating runtime behavior. |
| What would make v1 not worth adopting | A single synchronous FastAPI wrapper, no concurrent worker execution, untestable retry/idempotency semantics, or cosmetic observability that cannot support a failure report. |
| First proof of value | Run 500 synthetic jobs with 20 workers, 10% injected failures, timeout cases, and repeated idempotency-key submissions; report completion rate, duplicate-finalization count, retry count, queue lag, p95 duration, cost, and artifact completeness. |

### Adoption Reality Gate

| Boundary | Decision |
|----------|----------|
| Work AI is expected to improve | Optional sample jobs may use AI for repo analysis, ticket classification, summarization, or synthetic agent tasks. The runtime itself does not use AI for scheduling or policy decisions. |
| Work AI will not replace | Human ownership remains required for job definitions, safety policies, budget ceilings, tool permissions, high-risk approval, and interpretation of failure reports. |
| Claims not allowed before evidence | Do not claim this replaces Temporal, Ray, Kubernetes, Airflow, managed batch systems, production sandboxing, or exactly-once execution. Do not claim a fully autonomous agent swarm. |
| Local-to-production evidence required | Before trusted or remote operation, collect load-test reports, failure-injection reports, idempotency evidence, budget telemetry, and approval-boundary review for any external side-effecting job type. |

---

## Solution Shape

| Decision | Selection | Justification |
|----------|-----------|---------------|
| Primary shape | Hybrid decomposition | The control plane is deterministic and workflow-oriented, while individual sample jobs may contain bounded AI behavior behind explicit job-type contracts. |
| Governance level | Standard | The project is non-trivial infrastructure with persistent state, queues, workers, cost, and evidence needs, but v1 is local-only, non-compliance, and not a privileged production autonomous runtime. |
| Runtime tier | T1 | Local Docker Compose services and bounded worker containers are required for Postgres, Redis, and worker isolation. T2/T3 are not justified because v1 forbids privileged containers, untrusted arbitrary code execution, and persistent mutable autonomous workers. |

### Rejected Lower-Complexity Options

| Rejected option | Why it is insufficient |
|-----------------|------------------------|
| Single synchronous FastAPI wrapper | It cannot exercise queue lag, worker concurrency, retry isolation, cancellation, or at-least-once delivery behavior. |
| Manual scripts plus log inspection | It leaves idempotency, retries, artifacts, and cost attribution unverifiable under repeated failure. |
| Cron-only batch runner | It lacks durable per-job lifecycle events, worker leases, backpressure visibility, and controlled requeue after crash. |
| External scheduler as the whole project | It would hide the runtime behavior and implementation evidence that v1 is meant to validate; external systems may be referenced later, not treated as the v1 proof. |

### Minimum Viable Control Surface

- Explicit job schema validation, allowed job types, timeout bounds, retry bounds, budget bounds, and artifact size limits.
- Durable job registry, immutable event log, worker lease semantics, and idempotent finalization keyed by job ID and idempotency key.
- Docker Compose service boundary for API, worker, Postgres, Redis, Prometheus, and Grafana.
- Human approval for new external side effects, budget increases, broader tool permissions, new network egress, and remote/cloud runtime promotion.

### Human Approval Boundaries

| Boundary | Human approval required? | Why |
|----------|--------------------------|-----|
| Enabling a new job type with external side effects | Yes | The runtime can amplify duplicate external writes under retries. |
| Increasing per-run or per-job budget ceilings | Yes | Live LLM mode can spend money across many jobs and retries. |
| Allowing new network egress domains from workers | Yes | Egress expands data, security, and cost exposure. |
| Enabling shell, package, or toolchain mutation inside job containers | Yes | Mutation moves the runtime toward T2 behavior and requires stronger isolation. |
| Promoting from local mode to remote/cloud operation | Yes | Blast radius, secrets, auth, and recovery expectations change. |
| Dispatching configured local stub jobs within bounds | No | This is the normal deterministic runtime path. |

### Deterministic vs LLM-Owned Subproblems

| Subproblem | Owner | Reason |
|------------|-------|--------|
| Job schema validation, allowed job types, budget limits, timeout bounds, retry bounds, artifact size limits | Deterministic | These are policy constraints that must be reproducible and testable. |
| Queue selection, worker leasing, retry eligibility, cancellation, state transitions, DLQ routing | Deterministic | Runtime control behavior must not vary with model output. |
| Cost calculation, token aggregation, queue lag, p50/p95/p99 metrics, retry counters | Deterministic | Measurements must be auditable and comparable across runs. |
| Sample job summarization, repo analysis, or ticket classification | Optional LLM inside job payload | AI behavior is isolated to job work and governed by job-type budget and tool boundaries. |

### Runtime and Isolation Model

| Property | Decision |
|----------|----------|
| Isolation boundary | T1 container boundary for API, worker, Postgres, Redis, Prometheus, and Grafana in Docker Compose. |
| Persistence model | Postgres stores job registry and event log; local filesystem or MinIO-compatible storage stores artifacts; Redis Streams stores queue state. |
| Network model | Default local service-to-service traffic only. External LLM or GitHub API egress is disabled unless explicitly enabled by config and human approval. |
| Secrets model | Secrets come from environment variables or local uncommitted `.env` files. Workers receive only job-type-specific allowlisted variables. |
| Runtime mutation boundary | Runtime containers do not install packages or mutate toolchains at job execution time in v1. Sample jobs run from prebuilt images. |
| Rollback / recovery model | Rebuild containers from source, requeue unfinished jobs after stale worker lease, mark timed-out jobs deterministically, preserve event log, and rerun datasets with the same seed. |

T0 is insufficient because the project needs local service dependencies and bounded worker containers. T2/T3 are out of scope for v1.

---

## Inference / Model Strategy

| Path / Task | Model class | Why this class | Fallback / escalation | Budget / latency constraint |
|-------------|-------------|----------------|-----------------------|-----------------------------|
| Runtime scheduler, state machine, retries, idempotency, budget enforcement | No model | These paths must be deterministic and testable. | None. Model use here requires an ADR and human approval. | $0. |
| Default stub benchmark jobs | Stub model or deterministic fixture | The v1 reliability proof must run without paid API calls. | None required. | $0 default run. |
| Optional live LLM sample jobs | Small or standard structured-output model | The job may classify, summarize, or analyze text, but quality demands are modest and bounded. | Stronger model only for marked jobs with approval and cost budget update. | Target below $5 per full benchmark run; per-job budget configurable. |

---

## Cost Budget and Attribution

| Budget Scope | Limit | Approval Trigger | Attribution Fields | Evidence Location |
|--------------|-------|------------------|--------------------|-------------------|
| Default stub benchmark run | $0 | Any model call during stub mode | project, run_id, job_id, job_type, worker_id, model, environment | `docs/COST_BUDGET.md` |
| Optional live LLM benchmark run | Target below $5 per full run | Projected or actual spend above configured run limit | project, run_id, job_id, job_type, worker_id, model, operator, environment | `docs/COST_BUDGET.md`; future telemetry from T12 |
| Per job | Configurable, default disabled in stub mode | Model escalation, retry expansion, tool-call expansion, or job-type budget increase | project, task/workflow, agent/role, model, operator, feature/workload, environment | `docs/COST_BUDGET.md` |

Until T12 adds project-owned cost telemetry, cost thresholds are manual-review boundaries and runtime config gates, not CI-enforced rollups.

---

## Capability Profiles

| Profile | Status | Evaluation Artifact | Justification |
|---------|--------|---------------------|---------------|
| RAG | OFF | `docs/retrieval_eval.md` | v1 runtime does not need retrieval-backed answers. Any retrieval inside future sample jobs requires an ADR and profile activation. |
| Tool-Use | OFF | `docs/tool_eval.md` | The runtime records and constrains job tools deterministically. LLM-directed unsafe tool selection is out of scope for v1. |
| Agentic | OFF | `docs/agent_eval.md` | The control plane is not an agent loop. It runs jobs but does not let a model plan scheduling, retries, or safety decisions. |
| Planning | OFF | `docs/plan_eval.md` | The product output is job execution and evidence reports, not structured plans for downstream execution. |
| Compliance | OFF | `docs/compliance_eval.md` | No named compliance framework applies to v1 synthetic local data. Standard security and audit controls still apply. |

---

## Component Table

| Component | File / Directory | Responsibility |
|-----------|------------------|----------------|
| API control plane | `src/agent_runtime_grid/api/` | Job submission, status, cancellation, health, and artifact metadata endpoints. |
| Domain models | `src/agent_runtime_grid/domain/` | Job, run, worker, event, retry, timeout, and artifact types. |
| Persistence | `src/agent_runtime_grid/storage/` | Postgres repositories for job registry, event log, idempotency records, and cost records. |
| Queue adapter | `src/agent_runtime_grid/queue/` | Redis Streams publish, lease, ack, retry, and DLQ operations. |
| Worker runtime | `src/agent_runtime_grid/worker/` | Worker loop, lease renewal, timeout enforcement, job execution, cancellation handling. |
| Job runners | `src/agent_runtime_grid/jobs/` | Stub jobs, failure injection, optional live LLM sample jobs, and artifact writers. |
| Observability | `src/agent_runtime_grid/observability/` | Prometheus metrics, OpenTelemetry tracing, structured logs, shared tracing helper. |
| CLI | `src/agent_runtime_grid/cli/` | Batch submission, benchmark execution, cleanup, and report commands. |
| Tests | `tests/` | Unit, integration, idempotency, failure-injection, and load harness tests. |
| Reports | `reports/` | Load-test, failure-injection, and cost rollup outputs. |

---

## Data Flow

1. Operator submits a job or batch through the CLI or API with a job type, payload, idempotency key, timeout, retry limit, and optional budget.
2. API validates schema and policy bounds, writes the job registry row and append-only event, then publishes the job to Redis Streams.
3. Worker leases a queued job, writes a running event, starts the bounded runner, emits metrics and trace spans, and renews the lease while active.
4. Runner writes logs and artifacts to local artifact storage and reports usage/cost metadata through the worker.
5. Worker finalizes the job through an idempotent database transaction, ensuring one terminal finalization for the job and idempotency key.
6. Retry-eligible transient failures are requeued within configured bounds; timeout, cancellation, policy failure, and exhausted retry cases go to terminal states or DLQ.
7. Operator inspects API state, artifacts, logs, Prometheus/Grafana dashboards, and generated benchmark reports.

---

## Tech Stack

| Area | Choice | Rationale |
|------|--------|-----------|
| Language | Python 3.12 | Strong FastAPI, async, Pydantic, SQLAlchemy, pytest, and infrastructure tooling ecosystem. |
| API | FastAPI | Suitable for typed request/response APIs, async handlers, and health/status endpoints. |
| Validation | Pydantic v2 | Enforces job schemas and policy bounds before persistence or queue dispatch. |
| Database | Postgres 16 | Durable job registry, idempotency constraints, event log, and reporting queries. |
| ORM / migrations | SQLAlchemy 2.x and Alembic | Explicit async persistence and versioned schema evolution. |
| Queue | Redis Streams | Lightweight local queue with consumer groups, pending entries, and retry/DLQ patterns. |
| Worker runtime | Async Python workers in Docker Compose | Matches T1 runtime and local benchmark goal without Kubernetes complexity. |
| Artifacts | Local filesystem first, MinIO-compatible interface later | Keeps v1 runnable locally while preserving a path to object storage. |
| Observability | Prometheus, Grafana, OpenTelemetry | Supports queue lag, worker utilization, job duration, retries, cost, and traces. |
| CLI | Typer | Batch submission and benchmark workflows are operator-facing commands. |
| Tests | pytest, pytest-asyncio, httpx | Covers async API, worker, queue, persistence, and integration behavior. |
| Load testing | Locust or k6 | Generates 100-500 job benchmark evidence and report artifacts. |

---

## Observability

- Metrics: queue depth, queue lag, worker utilization, job duration, retry count, timeout count, failure rate, DLQ count, duplicate-finalization count, artifact completeness, token usage, and estimated cost.
- Traces: API submission, queue publish, worker lease, job execution, artifact write, finalization, retry, timeout, and cancellation spans use `src/agent_runtime_grid/observability/tracing.py`.
- Logs: structured logs include job ID, run ID, worker ID, event type, trace ID, and sanitized error class. Secrets and raw external tokens are never logged.
- Reports: benchmark and failure-injection commands write durable reports under `reports/`.

---

## Security Boundaries

- `GET /health` is intentionally public and returns only health status.
- Mutation and inspection endpoints use local token auth when `API_TOKEN` is configured; local mode may disable auth only when bound to localhost.
- No real sensitive data is used in v1; datasets are synthetic.
- Secrets are environment-only and `.env` files are ignored.
- Workers receive scoped env allowlists per job type and no broad host credential mount.
- External network calls are disabled by default. Enabling LLM or GitHub API calls requires explicit config and human approval.

---

## External Integrations

| Integration | Required for v1 default? | Credentials | Boundary |
|-------------|--------------------------|-------------|----------|
| OpenAI or other LLM provider | No | Optional API key via environment variable | Disabled in stub mode; enabled only for marked live LLM jobs and budget-gated. |
| GitHub API | No | Optional token via environment variable | Optional repo-analysis sample job; disabled unless configured. |
| Prometheus / Grafana | Yes, local containers | No external credentials | Local observability stack. |
| MinIO-compatible object store | No | Optional local credentials | Future artifact backend; local filesystem first. |

---

## File Layout

```text
.
├── .github/workflows/ci.yml
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── requirements-dev.txt
├── src/agent_runtime_grid/
│   ├── api/
│   ├── cli/
│   ├── domain/
│   ├── jobs/
│   ├── observability/
│   ├── queue/
│   ├── storage/
│   └── worker/
├── tests/
│   ├── integration/
│   ├── load/
│   └── unit/
├── docs/
│   ├── ARCHITECTURE.md
│   ├── COST_BUDGET.md
│   ├── DECISION_LOG.md
│   ├── EVIDENCE_INDEX.md
│   ├── KNOWN_LIMITS.md
│   ├── README.md
│   ├── STACK_OVERVIEW.md
│   ├── spec.md
│   └── evidence/
└── reports/
```

---

## Runtime Contract

| Env var | Required | Used by | Purpose |
|---------|----------|---------|---------|
| `DATABASE_URL` | Yes | API, worker, tests | Postgres connection string. |
| `REDIS_URL` | Yes | API, worker, tests | Redis Streams connection string. |
| `ARTIFACT_ROOT` | Yes | Worker, API | Local artifact storage root. |
| `API_TOKEN` | No when bound to localhost, yes outside local-only operation | API | Local token auth for non-health routes. |
| `WORKER_CONCURRENCY` | No | Worker | Number of concurrent jobs per worker process. |
| `JOB_DEFAULT_TIMEOUT_SECONDS` | No | API, worker | Default timeout applied when job type does not specify one. |
| `JOB_MAX_RETRIES` | No | API, worker | Upper bound for retryable failures. |
| `LLM_MODE` | No | Job runners | `stub` by default; `live` requires budget approval. |
| `OPENAI_API_KEY` or provider-specific key | No | Optional live LLM jobs | Required only when `LLM_MODE=live` and a provider is configured. |
| `GITHUB_TOKEN` | No | Optional repo-analysis jobs | Required only for GitHub API sample jobs. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | No | API, worker | Optional trace export target. |
| `PROMETHEUS_PORT` | No | API, worker | Metrics endpoint port. |

---

## Continuity and Retrieval Model

- Canonical truth: `docs/ARCHITECTURE.md`, ADRs when created, evidence artifacts, code, tests, benchmark reports, and CI results.
- Retrieval convenience: `docs/DECISION_LOG.md`, `docs/EVIDENCE_INDEX.md`, `docs/STACK_OVERVIEW.md`, `docs/KNOWN_LIMITS.md`, and benchmark reports.
- Scoped retrieval rule: consult the architecture, decision log, and evidence index before broad searching.
- Required lookup triggers: architecture changes, runtime-tier changes, cost-budget changes, external egress/tool permission changes, retry/idempotency semantics changes, open finding resolution, and benchmark baseline changes.
- Generated context packets or semantic indexes are not in use for v1; if added later, they are navigation surfaces only and must cite canonical files.

---

## Non-Goals

- Not a replacement for Temporal, Ray, Kubernetes, Airflow, or managed batch systems.
- Not production-ready for arbitrary untrusted code execution.
- Not exactly-once execution; v1 targets at-least-once execution with idempotent finalization.
- Not a full SaaS UI, multi-tenant billing system, or compliance product.
- Not a fully autonomous agent swarm; scheduling and safety decisions remain deterministic.
- Not a T2/T3 privileged runtime unless a future ADR changes mode, runtime tier, and evidence requirements.
