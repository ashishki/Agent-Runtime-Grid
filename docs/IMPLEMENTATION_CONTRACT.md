# Implementation Contract - Agent Runtime Grid

Status: **IMMUTABLE** - changes to this document require an Architectural Decision Record filed in `docs/adr/`.
Version: 1.0
Effective date: 2026-06-11

Any implementer or auditor may cite this document as the authority on implementation rules. Any finding that this contract was violated is automatically P1 unless a stricter severity is stated.

---

## Universal Rules

### SQL Safety

- All SQL is parameterized. Use SQLAlchemy expressions or `text()` with named parameters and a separate parameter dictionary.
- Never interpolate variables into SQL strings. This includes f-strings, `%` formatting, and `+` concatenation.
- Never concatenate table names, column names, or `ORDER BY` clauses from request input.
- Violation: automatic P1.

### Async Redis

- Redis is accessed only from async code paths.
- Use `redis.asyncio`; do not use the synchronous Redis client in API or worker code.
- Do not wrap synchronous Redis calls in executors as a workaround.
- Violation: automatic P1.

### Authorization

- `GET /health` is intentionally public and must not reveal secrets or internal state.
- All non-health API routes enforce local token authentication when `API_TOKEN` is configured.
- If local mode disables auth, the app must bind only to localhost and tests must verify that boundary.
- New public routes require a comment citing the design decision.
- Violation: automatic P1.

### Credentials and Secrets

- No credentials, API keys, tokens, passwords, or secrets in source code, comments, tests, fixtures, docs, logs, metrics, traces, or committed config.
- Test placeholders may use obvious non-secret strings such as `test-token`.
- All real secrets come from environment variables or uncommitted local `.env` files.
- `.env` files must be ignored by git.
- Violation: automatic P1 and security incident.

### PII and Sensitive Data Policy

- v1 uses synthetic data only.
- Do not log raw job payloads, provider API keys, GitHub tokens, API tokens, external credentials, or user-supplied secret-like fields.
- Metrics labels and span attributes must use job IDs, run IDs, worker IDs, event classes, and hashes rather than raw payload content.
- Violation: automatic P1 for secrets; P2 for non-secret payload leakage.

### Shared Tracing Module

- One shared tracing module: `src/agent_runtime_grid/observability/tracing.py`.
- Code that creates spans imports from the shared module.
- No inline noop span implementations in feature modules.
- No copy-pasted tracer initialization in API, worker, queue, storage, or job modules.
- Violation: P2; escalates to P1 at age cap.

### CI Gate

- CI must pass before any PR is merged.
- A PR with failing CI is not merged.
- CI flakiness is fixed or isolated before merge; do not bypass the gate.
- Phase 1 must include CI workflow structure; T02 makes it runnable against the project skeleton.
- Violation: automatic P1.

### Observability

- Every external call to Postgres, Redis, HTTP APIs, or LLM providers must be wrapped in a span with trace ID and operation name.
- For each external call type, emit success/error counters and latency histograms.
- `GET /health` returns `{"status":"ok"}` with HTTP 200 when the app is healthy.
- Required runtime metrics include queue depth, queue lag, worker utilization, job duration, retry count, timeout count, failure count, DLQ count, duplicate-finalization count, artifact count, and estimated cost.
- Violation: P2 for missing instrumentation; P1 for broken health behavior.

---

## Project-Specific Rules

### Job State Is Database-Authoritative

Postgres job state and the append-only event log are the source of truth. Redis stream state is a delivery mechanism and must not be treated as final lifecycle authority.

Violation: P1.

### Idempotent Finalization

Every terminal transition must be guarded by a database-level idempotency constraint. At-least-once delivery is expected; duplicate finalization is a P1 defect.

Violation: P1.

### Deterministic Runtime Control Plane

Scheduling, worker leasing, retry eligibility, cancellation, timeout, idempotency, budget enforcement, and artifact persistence are deterministic code paths. Do not delegate these decisions to an LLM.

Violation: P1.

### Stub Mode Is Default

The default benchmark and smoke test path must not call paid model providers. Live LLM mode requires explicit configuration, budget boundary, and approval.

Violation: P1 for unapproved model call.

### Worker Network and Secret Scope

Workers receive only the network access and environment variables required by the selected job type. Broad credential inheritance is forbidden.

Violation: P1.

---

## Continuity and Retrieval Rules

- Canonical truth lives in architecture, contract, tasks, CODEX prompt state, ADRs, audit reports, evidence artifacts, code, tests, and CI results.
- `docs/DECISION_LOG.md`, `docs/IMPLEMENTATION_JOURNAL.md`, and `docs/EVIDENCE_INDEX.md` are retrieval surfaces, not authority over canonical files.
- Generated memory, chat summaries, semantic search results, and context packets must cite canonical repo paths before influencing implementation or review.
- Required lookup triggers: runtime-tier changes, budget changes, external egress changes, retry/idempotency changes, open finding resolution, benchmark baseline changes, and architecture changes.
- Closing P1/P2 findings, changing benchmark baselines, or superseding decisions requires canonical file updates.

---

## Control Surface and Runtime Boundaries

| Boundary | Rule |
|----------|------|
| Secrets scope | Secrets are environment-only; workers receive allowlisted env vars by job type. |
| Network egress | Default local service traffic only. LLM or GitHub egress requires explicit config and human approval. |
| Privileged actions | External side effects, budget increases, egress expansion, runtime mutation, and remote/cloud promotion require human approval. |
| Runtime mutation | v1 workers do not install packages, mutate toolchains, or execute arbitrary untrusted code at runtime. |
| Persistence | Job registry and events persist in Postgres. Artifacts persist under local artifact root. Redis is delivery state. |
| Auditability | Job lifecycle events, retries, timeouts, cancellation, finalization, budget blocks, and external provider usage are recorded. |

### Runtime Tier Guardrails

- Implement only within the T1 runtime tier declared in `docs/ARCHITECTURE.md`.
- Runtime-tier expansion is a governance change, not an implementation detail.
- Do not add T2/T3 behavior such as privileged containers, broad shell mutation, ad-hoc package installs, or persistent mutable autonomous workers without ADR and human approval.

---

## Cost Budget Rules

- Default stub mode has $0 model cost.
- Optional live LLM jobs require `LLM_MODE=live`, configured provider credentials, and budget approval.
- Recurring, live, multi-agent, dynamic, or materially costly AI usage must update `docs/COST_BUDGET.md`.
- Every AI/model task must have a per-run or per-task budget boundary.
- Model escalation, retry expansion, tool-call expansion, parallel fan-out, or dynamic workflow changes require a matching budget update or human approval.
- Until T12 adds telemetry, thresholds are manual-review boundaries and runtime config gates.
- Enforceable thresholds must name a telemetry source and rollup/check command before CI treats them as hard gates.

Violation: P1 for missing budget on active AI/model work; P0 if an unapproved overrun creates production, customer, or billing risk.

---

## Mandatory Pre-Task Protocol

1. Read `docs/IMPLEMENTATION_CONTRACT.md`.
2. Read `docs/CODEX_PROMPT.md` and identify `Next Task`.
3. Read the target task in `docs/tasks.md`.
4. Read task `Context-Refs`; do not broaden context unless required by lookup triggers.
5. Capture the current baseline with `python -m pytest -q` once T03 establishes tests. Before T03, run the most specific available test command.
6. Run `ruff check` and `ruff format --check` once T01/T02 add project tooling.
7. Implement only files listed by the task unless a blocking dependency is discovered; if scope must expand, update the task or stop for approval.
8. Run task-specific tests and the current baseline before marking work ready for review.
9. Record material evidence in `docs/IMPLEMENTATION_JOURNAL.md` and update `docs/CODEX_PROMPT.md` at phase boundaries.

---

## Forbidden Actions

- SQL interpolation or string-built SQL.
- Skipping baseline capture after T03 establishes the baseline.
- Self-closing review findings without code verification.
- Deferring CI setup past Phase 1.
- Unauthorized runtime-tier expansion.
- Adding live model calls to the default stub benchmark.
- Logging secrets, raw tokens, or raw job payloads.
- Broadening worker network egress or secret scope without approval.
- Weakening tests, acceptance criteria, or verification commands to pass a task.
- Replacing deterministic runtime control decisions with LLM judgment.

---

## Profile Rules

All capability profiles are OFF for v1:

- RAG: OFF.
- Tool-Use: OFF.
- Agentic: OFF.
- Planning: OFF.
- Compliance: OFF.

If any profile becomes active, update `docs/ARCHITECTURE.md`, `docs/CODEX_PROMPT.md`, this contract, `docs/tasks.md`, and the corresponding evaluation artifact before implementation.
