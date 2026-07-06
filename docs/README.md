# Agent Runtime Grid Docs

Status: active

## Purpose

This directory contains architecture, budget, evidence, operations, integration,
and known-limit artifacts for Agent Runtime Grid.

## Start Here

- `docs/ARCHITECTURE.md` - canonical architecture, mode, runtime tier, scope, and boundaries.
- `docs/STACK_OVERVIEW.md` - three-project reliability stack map.
- `docs/EVIDENCE_INDEX.md` - durable evidence pointers.
- `docs/AUTONOMOUS_ROUTINE_CONTRACT.md` - bounded routine trigger/runtime contract.
- `docs/TRIGGER_SECURITY.md` - trigger security controls for manual, cron,
  webhook, and event starts.
- `docs/KNOWN_LIMITS.md` - explicit local and production-boundary limits.

## Current State

- Mode: Standard.
- Phase: local v1 evidence baseline complete.
- Capability profiles: RAG OFF, Tool-Use OFF, Agentic OFF, Planning OFF, Compliance OFF.
- Runtime tier: T1 local Docker Compose.
- Default benchmark path: stub jobs with $0 model cost.

## Key Decisions

- `docs/DECISION_LOG.md#decision-index` - Standard mode, T1 runtime, deterministic control plane, stub-first budget, and capability profile decisions.

## Contracts, Proof, and Evals

- `docs/COST_BUDGET.md` - model and benchmark cost boundaries.
- `docs/EVIDENCE_INDEX.md` - durable evidence pointers.
- `docs/evidence/` - committed evidence snapshots for generated report surfaces.
- `docs/evidence/routine-reliability-report.md` - starter contract for future
  routine reliability reports.

## Known Gaps

- Runtime proof is local-first and deterministic by default.
- Generated reports under `reports/` remain ignored; committed snapshots live in
  `docs/evidence/`.
- Live-local gdev-agent proof is optional and operator-run.
- Routine contracts are deployment evidence templates only; Grid remains a T1
  runtime, not a general scheduler or autonomous swarm.

## Authority

This README is a navigation index. Canonical artifacts, tests, evals, ADRs,
proof receipts, and report artifacts remain authoritative.
