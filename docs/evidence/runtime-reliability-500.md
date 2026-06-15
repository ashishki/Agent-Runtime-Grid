# Runtime Reliability 500 - Committed Evidence Snapshot

This is a stable evidence snapshot for the 500-job reliability proof. Generated
reports under `reports/` remain ignored by git; this file records the durable
expected evidence shape.

## Scope

- Mode: local deterministic `stub`
- Jobs: 500
- Workers: 20
- Injected failures: 10%
- Timeout cases: included
- Repeated idempotency submissions: included
- External model calls: 0

## Rerun Command

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli benchmark v1-proof \
  --jobs 500 \
  --workers 20 \
  --failure-rate 0.10 \
  --include-timeouts \
  --repeat-idempotency-submissions \
  --report reports/v1/reliability_report.md
```

## Evidence Snapshot

| Signal | Expected snapshot |
| --- | --- |
| submitted jobs | 500 |
| terminal jobs | 500 |
| injected failure count | 50 |
| retries | present for transient failures |
| timed out jobs | present when timeout cases are included |
| idempotency replay count | greater than 0 |
| duplicate finalization count | 0 |
| queue/backpressure section | present |
| artifact integrity rows | present |
| estimated model cost | `$0.00` |

## Known Limits

This is local reliability evidence under a deterministic workload. It does not
claim production scale, remote worker supervision, or exactly-once execution.

