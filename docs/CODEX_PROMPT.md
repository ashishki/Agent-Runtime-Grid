# CODEX_PROMPT.md

Version: 1.0
Date: 2026-06-11
Phase: 1

This file is the project handoff state for Codex sessions. Repository files, tests, audit reports, and CI results are authoritative.

---

## Current State

- **Project:** Agent Runtime Grid
- **Mode:** Standard
- **Phase:** 1
- **Baseline:** 0 passing tests (pre-implementation)
- **Ruff:** configured in planned T01/T02, not yet runnable
- **Last CI run:** not yet run
- **Last updated:** 2026-06-11
- **Session tokens (approx):** not tracked
- **Cumulative phase tokens (approx):** not tracked
- **Session cost (approx):** not tracked
- **Cumulative phase cost (approx):** not tracked
- **Budget status:** within Phase 1 planning budget; implementation defaults to stub mode with $0 model cost

---

## Continuity Pointers

- **Architecture:** `docs/ARCHITECTURE.md`
- **Implementation contract:** `docs/IMPLEMENTATION_CONTRACT.md`
- **Tasks:** `docs/tasks.md`
- **Decision log:** `docs/DECISION_LOG.md`
- **Implementation journal:** `docs/IMPLEMENTATION_JOURNAL.md`
- **Evidence index:** `docs/EVIDENCE_INDEX.md`
- **Cost budget:** `docs/COST_BUDGET.md`
- **Audit reports:** `docs/audit/`
- **Task-scoped context:** read `Context-Refs` in `docs/tasks.md` before broad searching

---

## Instructions for Codex

Before starting any implementation task:

1. Read `docs/IMPLEMENTATION_CONTRACT.md`.
2. Read this file and identify `Next Task`.
3. Read the matching task block in `docs/tasks.md`.
4. Read only the task's `Context-Refs` unless architecture, runtime, cost, security, or open findings require broader context.
5. Run the current baseline command before editing once T03 establishes it; before T03, run the most specific available tests named by the task.
6. Run `ruff check`, `ruff format --check`, and task-specific tests before marking a task ready for review once those commands exist.
7. Update this file and `docs/IMPLEMENTATION_JOURNAL.md` at phase boundaries or when a task materially changes baseline, cost, runtime, or open findings.

Implementation agents do not self-review meaningful changes. Review findings are resolved through follow-up tasks or explicit fix-queue items.

---

## Next Task

**T01: Project Skeleton**

Narrow task digest:

- Create Python package skeleton, dependency files, Docker Compose outline, repository hygiene files, and bootstrap tests.
- Keep default runtime local and T1.
- Do not add live LLM calls.
- Do not add application behavior beyond the skeleton and tests named in T01.
- Verification target: T01 acceptance criteria in `docs/tasks.md`.

---

## Fix Queue

empty

---

## Correction Budget

- Max implementation correction turns: 2.
- Max test-healing turns: 2 for normal tasks.
- Escalate after repeated equivalent failure output, increased failure count, out-of-scope file need, budget exhaustion, or any proposal to weaken tests or acceptance criteria.
- Preserve command output and changed-file evidence before any correction turn.

---

## Cost Budget State

- Budget artifact: `docs/COST_BUDGET.md`
- Telemetry source: none yet; T12 adds project-owned telemetry
- Last rollup: not run
- Default stub run budget: $0 model cost
- Optional live LLM benchmark target: below $5 per full benchmark run
- Per-job budget: configurable by job type; unavailable until implemented
- Monthly project budget: unknown; requires human approval before any recurring live LLM usage
- Approval required before: live LLM mode, model escalation, fan-out increase, retry expansion, tool-call expansion, external egress, or budget overrun
- Last recorded AI/model cost: none

If the next task would exceed the declared budget, increase model class, increase retry/fan-out/tool-call limits, add recurring AI usage, or enable external egress, stop for approval before implementation.

---

## Open Findings

none

---

## Profile State: RAG

- RAG Status: OFF
- Active corpora: n/a
- Retrieval baseline: n/a
- Open retrieval findings: none
- Index schema version: n/a
- Pending reindex actions: none
- Retrieval-related next tasks: none
- Retrieval-driven tasks: none

---

## Tool-Use State

- Tool-Use Profile: OFF
- Registered tool schemas: n/a
- Unsafe-action guardrails: n/a
- Open tool findings: none

---

## Agentic State

- Agentic Profile: OFF
- Active agent roles: n/a
- Loop termination contract version: n/a
- Cross-iteration state mechanism: n/a
- Open agent findings: none

---

## Planning State

- Planning Profile: OFF
- Plan schema version: n/a
- Plan validation method: n/a
- Open plan findings: none

---

## Compliance State

- Compliance Status: OFF
- Active frameworks: n/a
- Controls implemented: n/a
- Controls partial: n/a
- Controls not started: n/a
- Evidence artifact: n/a
- Open compliance findings: none

---

## Evaluation State

- Active capability evals: none
- Runtime reliability reports: planned in T14
- Cost telemetry report: planned in T12
- Phase 1 validation: `docs/audit/PHASE1_AUDIT.md`

---

## Phase History

### 2026-06-11 - Phase 1 Bootstrap

- Selected Standard mode.
- Created initial architecture, spec, task contract, implementation contract, cost budget, continuity docs, evidence index, and CI workflow.
- Next implementation task is T01.
