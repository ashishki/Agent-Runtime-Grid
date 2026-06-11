# ADR 0001 - Neutral Runtime Framing

Status: Accepted
Date: 2026-06-11

## Context

Project documentation contained wording that framed Agent Runtime Grid around external evaluation rather than runtime operations. The project should instead be described as an operator-facing runtime with local-first validation, synthetic data, and reproducible reliability evidence.

`docs/IMPLEMENTATION_CONTRACT.md` is immutable and requires an ADR for changes. The contract wording was updated editorially to use local-mode and synthetic-data terminology; the auth boundary and data policy are unchanged.

## Decision

Use neutral product and operations terminology across documentation:

- operators, platform engineers, and technical stakeholders
- sample jobs or stub jobs
- local-only or local mode
- synthetic data

## Consequences

- No runtime behavior changes.
- No security, auth, cost, or isolation rule changes.
- Future documentation should avoid positioning the system as an external-evaluation artifact.
