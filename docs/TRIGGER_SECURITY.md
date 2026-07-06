# Trigger Security

Status: active design contract

## Purpose

Triggers are runtime authority boundaries. A cron, webhook, event, or manual
operator command can create work, spend budget, and touch artifacts. Trigger
security is therefore part of the routine contract.

## Trigger Requirements

| Trigger type | Required controls |
|--------------|-------------------|
| Manual | Operator role, command audit, explicit environment, budget mode |
| Cron | Owner, timezone, overlap policy, missed-run behavior, disable switch |
| Webhook | HMAC/signature, timestamp, replay protection, payload size limit |
| Event | Source allowlist, idempotency key, dead-letter handling, schema version |

## Secret Handling

- Store only secret references in configs, jobs, traces, artifacts, and reports.
- Resolve secret values at the runtime boundary.
- Redact webhook signatures, tokens, API keys, and provider credentials.
- Tests must cover that secret-like input keys do not appear in reports.

## Replay Protection

Webhook and event triggers must define:

- deterministic idempotency key
- timestamp or nonce window when available
- duplicate handling behavior
- replay audit event

## Payload Rules

- Validate schema before enqueue.
- Reject unknown destructive or provider-dispatch fields.
- Enforce payload size limits.
- Store input digests instead of raw sensitive payloads in reports.

