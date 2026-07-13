# Decision Log - Agent Runtime Grid

Version: 1.0
Last updated: 2026-07-13

Purpose:

- Lightweight retrieval surface for important decisions.
- Points to canonical sources such as architecture, evidence artifacts, benchmark reports, and ADRs.

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
| D-001 | 2026-06-11 | Active | Use Standard mode. | The project is infrastructure with queues, workers, retries, persistence, cost, and evidence needs, but v1 is local-only and not compliance-heavy or privileged. | `docs/ARCHITECTURE.md#solution-shape` | none |
| D-002 | 2026-06-11 | Superseded | Use a six-service T1 Docker Compose runtime. | API/worker containers only imported the package and dashboards had no connected scrape path. | `docs/ARCHITECTURE.md#runtime-components` | none |
| D-003 | 2026-06-11 | Active | Keep runtime control plane deterministic. | Scheduling, retries, idempotency, budget, and state transitions must be reproducible and testable. | `docs/ARCHITECTURE.md#deterministic-vs-llm-owned-subproblems` | none |
| D-004 | 2026-06-11 | Active | Default benchmark mode uses stub jobs with $0 model cost. | The reliability proof must be runnable by operators without paid LLM credentials. | `docs/COST_BUDGET.md#budget-scope` | none |
| D-005 | 2026-06-11 | Active | Capability profiles are OFF for v1. | RAG, Tool-Use, Agentic, Planning, and Compliance profile overhead is not justified for the deterministic control plane; future activation requires ADR and artifacts. | `docs/ARCHITECTURE.md#capability-profiles` | none |
| D-006 | 2026-06-11 | Active | Use neutral operator/platform framing. | Documentation must describe the system as an operator-facing runtime, not as an external-evaluation artifact. | `docs/adr/0001-neutral-runtime-framing.md` | none |
| D-007 | 2026-07-13 | Active | Support a CLI/library runtime with Postgres and Redis as the only default Compose services. | It matches the runnable implementation and removes placeholder service claims. | `docs/ARCHITECTURE.md#supported-runtime-path` | D-002 |
| D-008 | 2026-07-13 | Active | Persist rejected finalization attempts separately from duplicate terminal-event defects. | Contention evidence and invariant violations have different meanings and must survive restart. | `docs/ARCHITECTURE.md#finalization-semantics` | none |
| D-009 | 2026-07-13 | Active | Emit portable, tamper-evident Markdown/JSON evidence bundles. | A reviewer can verify run bytes without trusting absolute local paths or prose alone. | `docs/ARCHITECTURE.md#evidence-model` | none |

---

## Retrieval Notes

- Read this file before changing architecture, runtime tier, cost boundaries, capability profiles, or retry/idempotency semantics.
