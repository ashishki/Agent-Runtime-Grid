# Observability

Agent Runtime Grid exposes operational state from Redis Streams and Postgres without including raw payloads, credentials, provider tokens, or secret-like labels.

## Queue And Backpressure Metrics

`src/agent_runtime_grid/queue/inspection.py` builds a `QueueBackpressureSnapshot` from runtime state.

Redis-derived fields:

- `queue_depth`: Redis consumer-group pending entries plus consumer lag.
- `oldest_pending_age_seconds`: maximum idle age among pending stream entries.
- `consumer_lag`: Redis Streams consumer-group lag for messages not yet delivered to workers.
- `leased_jobs`: Redis Streams pending entries for the worker consumer group.
- `dlq_count`: current dead-letter stream length.

Postgres-derived fields:

- `running_jobs`: jobs currently marked `running`.
- `retry_rate`: `retry_scheduled` events divided by submitted jobs for the selected run.
- `p95_queue_wait_seconds`: p95 time from `submitted` to first `running`.
- `p95_execution_seconds`: p95 time from first `running` to the first terminal event.

Worker-derived field:

- `worker_utilization`: `running_jobs / worker_count`, capped at 1.0 when a worker count is supplied.

## Prometheus Surface

`RuntimeMetrics.record_backpressure_snapshot()` maps the snapshot to gauges without dynamic labels:

- `agent_runtime_grid_queue_depth`
- `agent_runtime_grid_queue_oldest_pending_age_seconds`
- `agent_runtime_grid_queue_consumer_lag`
- `agent_runtime_grid_queue_leased_jobs`
- `agent_runtime_grid_queue_running_jobs`
- `agent_runtime_grid_worker_utilization`
- `agent_runtime_grid_queue_retry_rate`
- `agent_runtime_grid_queue_dlq_count`
- `agent_runtime_grid_queue_wait_p95_seconds`
- `agent_runtime_grid_queue_execution_p95_seconds`

Existing counters and histograms still cover retries, timeouts, failures, duplicate finalization, artifacts, estimated cost, and job duration.

## Reports

Smoke and v1 reliability reports include a `queue/backpressure` section. The section is generated from the same `QueueBackpressureSnapshot` when a real queue is available. Configured-only reports fall back to zero queue values and keep the legacy reliability fields for compatibility.

The report timing fields use these definitions:

- queue wait: `submitted -> running`
- execution duration: `running -> terminal`
