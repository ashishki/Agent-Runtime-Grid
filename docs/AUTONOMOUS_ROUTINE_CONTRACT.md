# Autonomous Routine Contract

Status: active design contract
Scope: bounded T1 routines executed by Agent Runtime Grid

## Purpose

Agent Runtime Grid can run bounded jobs on behalf of higher-level workflows. A
routine is allowed only when trigger, runtime, idempotency, secrets, retry,
timeout, fallback, monitoring, and budget are explicit.

This contract preserves the project boundary: Grid is a local-first T1 runtime
with durable state and reliability evidence. It is not a Temporal, Ray, or
Kubernetes replacement and not an autonomous swarm.

## Routine Record

| Field | Required | Notes |
|-------|----------|-------|
| `routine_name` | yes | Stable name used in logs, metrics, reports |
| `owner` | yes | Human owner for incidents and budget decisions |
| `trigger_type` | yes | `manual`, `cron`, `webhook`, or `event` |
| `trigger_source` | yes | Schedule, webhook route, queue/topic, or operator command |
| `input_schema_version` | yes | Versioned payload contract |
| `idempotency_key` | yes | Required for replay and duplicate prevention |
| `runtime_tier` | yes | Expected to stay T1 unless architecture changes |
| `secret_refs` | yes | Names of env/vault refs, never secret values |
| `retry_policy` | yes | Max attempts and retryable failure classes |
| `timeout_seconds` | yes | Job-level timeout |
| `cancellation_policy` | yes | What happens on operator or system cancellation |
| `fallback_policy` | yes | Dead-letter, manual review, retry later, or disable |
| `budget_policy` | yes | Stub/live mode, provider-call boundary, cost cap |
| `monitoring_signals` | yes | Success, retry, timeout, DLQ, cost, p95 delay/runtime |
| `disable_switch` | yes | How an operator stops the routine |

## Deployment Gate

A routine is not deployable until:

- input schema validates before enqueue
- idempotency key is deterministic and collision-reviewed
- secrets are injected by reference and redacted from traces/artifacts
- retry policy is bounded and idempotency-safe
- timeout and cancellation behavior are tested
- fallback and dead-letter handling are documented
- success/retry/timeout/DLQ/cost/p95 queue delay/p95 runtime metrics exist
- budget gate blocks live/provider dispatch without explicit approval

## Runtime Mapping

| Contract area | Grid primitive |
|---------------|----------------|
| Durable lifecycle | Postgres job registry and event log |
| Delivery | Redis Streams queue |
| Idempotency | job idempotency key and finalization guard |
| Retry | worker retry policy and event trail |
| Timeout/cancellation | worker timeout and cancellation paths |
| Fallback | DLQ, failed terminal state, operator repair commands |
| Artifacts | JSON artifact store with digests |
| Monitoring | metrics, queue inspection, reports |
| Cost | cost telemetry and rollup |

