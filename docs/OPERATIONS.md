# Operations - Agent Runtime Grid

Last updated: 2026-06-12

This page documents local T1 operator commands. These commands inspect Redis Streams delivery state and Postgres lifecycle state, but Postgres remains authoritative for job lifecycle decisions.

## Queue Inspection

Inspect queue and pending lease state:

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli operator inspect \
  --database-url "$DATABASE_URL" \
  --redis-url "$REDIS_URL" \
  --stream-name jobs \
  --consumer-group workers \
  --dlq-stream-name jobs:dlq \
  --stale-after-ms 60000
```

Output fields:

- `queue_depth`
- `pending_leases`
- `stale_leases`
- `oldest_pending_age_seconds`
- `consumer_lag`
- `running_jobs`
- `worker_utilization`
- `retry_rate`
- `dlq_count`
- `p95_queue_wait_seconds`
- `p95_execution_seconds`

The command does not print raw job payloads, tokens, provider credentials, or secret-like fields.

## Stale Lease Recovery

Recover stale pending Redis entries:

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli operator recover-stale \
  --database-url "$DATABASE_URL" \
  --redis-url "$REDIS_URL" \
  --stream-name jobs \
  --consumer-group workers \
  --dlq-stream-name jobs:dlq \
  --stale-after-ms 60000 \
  --recovery-worker-id operator-recovery
```

The command prints:

- `detected`
- `requeued`
- `dlq`
- `acknowledged_terminal`
- `acknowledged_missing`

Recovery rules:

- Missing jobs are acknowledged in Redis only.
- Already terminal jobs are acknowledged in Redis only.
- Non-terminal jobs with retry budget remaining emit `stale_lease_recovered`, requeue the next attempt, and acknowledge the stale entry.
- Non-terminal jobs with exhausted retry budget are finalized as failed and moved to the Redis dead-letter stream.

## Lease Renewal

Runtime code can renew a pending Redis Streams lease with `RedisStreamsQueue.renew_pending_lease`. Renewal resets the pending entry idle age, prevents false stale recovery under the configured threshold, and does not write lifecycle events.

Executable proof:

```bash
PATH=.venv/bin:$PATH python -m pytest tests/integration/test_operator_repair_cli.py -q
```

## Boundaries

- These commands are local T1 operator tools.
- They do not enable live model calls.
- They do not add worker network egress.
- They do not mutate job payloads or artifacts.
- Redis remains delivery state; Postgres remains lifecycle authority.
