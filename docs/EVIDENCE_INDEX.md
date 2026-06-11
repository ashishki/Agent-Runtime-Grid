# Evidence Index - Agent Runtime Grid

Version: 1.0
Last updated: 2026-06-11

Purpose:

- Index durable proof so agents can retrieve prior evidence quickly.
- Avoid repeated archaeology across tests, benchmark reports, review reports, and manual checks.

This file is not authoritative by itself. Every row must point to the real artifact that carries the evidence.

---

## When To Use

Maintain this file for:

- Phase 1 audit results.
- Runtime verification records for risky or boundary-changing tasks.
- Load-test and failure-injection reports.
- Cost telemetry reports once T12 exists.
- Review findings and fix evidence.

---

## Evidence Table

| Topic / Finding / Task | Artifact type | Location | Scope covered | Last verified | Canonical? |
|------------------------|---------------|----------|---------------|---------------|------------|
| Phase 1 validation | audit | `docs/audit/PHASE1_AUDIT.md` | Standard-mode planning package structure and consistency | 2026-06-11 | Yes |
| Phase 1 audit index | audit index | `docs/audit/AUDIT_INDEX.md` | Pointers to audit results | 2026-06-11 | Yes |

---

## Retrieval Rules

- Prefer rows that match the current task's `Context-Refs`, open findings, or active capability tags.
- If an evidence row points to a stale or missing artifact, fix the artifact or remove the row.
- Do not treat a journal note as proof when a test, eval, audit, or review report exists.
