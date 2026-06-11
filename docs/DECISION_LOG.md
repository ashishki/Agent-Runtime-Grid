# Decision Log - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-11

Purpose:

- Lightweight retrieval surface for important decisions.
- Points to canonical sources such as architecture, contract, tasks, review reports, and future ADRs.

This file is not the source of truth. If an entry conflicts with a canonical document, the canonical document wins and this file must be corrected.

---

## Rules

- Keep entries short and link to the authoritative document or section.
- Record why a decision was made and what it replaced.
- Update this file when architecture, runtime, governance, budget, or major implementation direction changes.
- Mark superseded decisions explicitly instead of deleting them.

---

## Decision Index

| ID | Date | Status | Decision | Why it matters | Canonical source | Supersedes |
|----|------|--------|----------|----------------|------------------|------------|
| D-001 | 2026-06-11 | Active | Use Standard mode. | The project is infrastructure with queues, workers, retries, persistence, cost, and evidence needs, but v1 is local/demo and not compliance-heavy or privileged. | `docs/ARCHITECTURE.md#solution-shape` | none |
| D-002 | 2026-06-11 | Active | Use T1 Docker Compose runtime. | Local containers are needed for API, worker, Postgres, Redis, Prometheus, and Grafana, while T2/T3 privileges are out of scope. | `docs/ARCHITECTURE.md#runtime-and-isolation-model` | none |
| D-003 | 2026-06-11 | Active | Keep runtime control plane deterministic. | Scheduling, retries, idempotency, budget, and state transitions must be reproducible and testable. | `docs/ARCHITECTURE.md#deterministic-vs-llm-owned-subproblems` | none |
| D-004 | 2026-06-11 | Active | Default benchmark mode uses stub jobs with $0 model cost. | The reliability proof must be runnable by reviewers without paid LLM credentials. | `docs/COST_BUDGET.md#budget-scope` | none |
| D-005 | 2026-06-11 | Active | Capability profiles are OFF for v1. | RAG, Tool-Use, Agentic, Planning, and Compliance profile overhead is not justified for the deterministic control plane; future activation requires ADR and artifacts. | `docs/ARCHITECTURE.md#capability-profiles` | none |

---

## Retrieval Notes

- Read this file before changing architecture, runtime tier, cost boundaries, capability profiles, or retry/idempotency semantics.
- If a task has `Context-Refs`, prefer those entries over scanning this file top-to-bottom.
