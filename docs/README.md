# Agent Runtime Grid Docs

Status: active

## Purpose

This directory contains the Phase 1 governance, architecture, task, budget, evidence, and audit artifacts for Agent Runtime Grid.

## Start Here

- `docs/ARCHITECTURE.md` - canonical architecture, mode, runtime tier, scope, and boundaries.
- `docs/tasks.md` - forward implementation contract and task dependency chain.
- `docs/CODEX_PROMPT.md` - current Codex session state and next task.
- `docs/IMPLEMENTATION_CONTRACT.md` - immutable implementation rules.

## Current State

- Mode: Standard.
- Phase: 1 planning package bootstrapped.
- Next task: `T01: Project Skeleton`.
- Capability profiles: RAG OFF, Tool-Use OFF, Agentic OFF, Planning OFF, Compliance OFF.
- Runtime tier: T1 local Docker Compose.
- Default benchmark path: stub jobs with $0 model cost.

## Key Decisions

- `docs/DECISION_LOG.md#decision-index` - Standard mode, T1 runtime, deterministic control plane, stub-first budget, and capability profile decisions.

## Contracts, Proof, and Evals

- `docs/IMPLEMENTATION_CONTRACT.md` - implementation rules and forbidden actions.
- `docs/COST_BUDGET.md` - model and benchmark cost boundaries.
- `docs/EVIDENCE_INDEX.md` - durable evidence pointers.
- `docs/audit/PHASE1_AUDIT.md` - Phase 1 validation result.

## Active Tasks

- `docs/tasks.md#t01-project-skeleton` - first implementation task after Phase 1 validation passes.

## Known Gaps

- No application code exists yet; T01 creates the skeleton.
- CI workflow is structurally bootstrapped; T02 makes it runnable against the project skeleton.
- Cost telemetry is planned in T12; current live LLM thresholds are manual-review boundaries and runtime gates.

## Authority

This README is a navigation index. Canonical artifacts, tests, evals, ADRs, proof receipts, and review reports remain authoritative.
