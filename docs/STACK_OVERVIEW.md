# AI Systems Reliability Stack

Agent Runtime Grid is the runtime layer in a three-project local evidence stack
for reliable AI/agent systems.

## System Map

| Layer | Repository | Role | Current evidence |
| --- | --- | --- | --- |
| Governed workflow | `gdev-agent` | Multi-tenant support-triage workflow with webhook intake, guardrails, approval, audit, cost, and observability controls. | Local Compose demo, 285-test repository baseline, 180-case internal smoke eval. |
| Quality layer | `Eval-Ground-Truth-Lab` | Deterministic regression evaluation framework for structured output, routing, unsafe auto-approval, cost, latency, and adapter behavior. | 55-case live local gdev-agent integration baseline with zero validator failures. |
| Runtime layer | `Agent-Runtime-Grid` | Queue-backed runtime for running many AI/agent jobs with retries, timeouts, idempotent finalization, artifacts, metrics, and cost controls. | 100-job smoke, 500-job reliability proof, failure-injection reports, and cross-project artifact proof. |

## What Runtime Grid Adds

Eval Lab can call gdev-agent directly for quality evaluation. Runtime Grid adds
execution reliability for running many agent/eval jobs:

```text
submit batch
  -> Redis Streams dispatch
  -> bounded workers
  -> Postgres lifecycle state
  -> local artifacts
  -> queue/backpressure metrics
  -> reliability report
```

## Current Cross-Project Mode

The current command is an artifact-linked proof:

```text
proof full-stack
  -> validate ready Eval Lab dataset/report paths
  -> validate ready gdev-agent artifact path
  -> submit selected cases as Grid jobs
  -> run deterministic workers
  -> write runtime artifacts and report cross-links
```

This is better described as `full-stack-artifact-proof`. The CLI command remains
`proof full-stack` for compatibility, but it does not call live gdev-agent over
HTTP and does not make live model calls by default.

## Future Live-Local Mode

A future `full-stack-live-local` mode would use Grid workers to trigger the live
local quality path:

```text
Runtime Grid worker
  -> Eval Lab runner or gdev HTTP adapter
  -> local gdev-agent /webhook
  -> Eval Lab validators
  -> Grid runtime artifacts
  -> cross-linked quality and reliability report
```

That mode needs explicit egress, budget, timeout, and artifact boundaries before
it is implemented.

## Agent And Provider Model

An agent is a bounded job type with input/output schemas, allowed tools,
provider policy, budget, timeout, guardrails, and eval coverage.

Default evidence mode stays deterministic:

- Runtime Grid `stub` mode for CI, smoke, reliability, and failure injection.
- gdev-agent `demo` mode for local workflow evaluation.
- Eval Lab fake/budgeted providers for optional non-authoritative judge tests.

Future live providers should be routed through an explicit model router, not
called directly from runtime control-plane code. Runtime decisions such as
scheduling, retries, finalization, cost gates, and report pass/fail status must
remain deterministic.

## What Is Not Claimed

This stack is v1 local evidence. It does not claim external adoption, hosted
operations, exactly-once execution, production sandboxing, production SLOs, or
an autonomous swarm.

