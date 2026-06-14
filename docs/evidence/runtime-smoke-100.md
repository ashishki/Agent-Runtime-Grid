# Runtime Smoke 100 - Committed Evidence Snapshot

This is a stable reviewer snapshot for the real 100-job smoke proof. Generated
reports under `reports/` remain ignored by git to avoid local run churn.

## Scope

- Mode: local deterministic `stub`
- Jobs: 100
- Workers: 4
- Failure rate: 0
- External model calls: 0
- Runtime path: Postgres lifecycle state, Redis Streams dispatch, workers,
  artifact store, report validation

## Rerun Command

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli smoke \
  --jobs 100 \
  --workers 4 \
  --failure-rate 0 \
  --mode stub \
  --report reports/smoke.md
```

## Evidence Snapshot

| Signal | Expected snapshot |
| --- | --- |
| submitted jobs | 100 |
| terminal jobs | 100 |
| duplicate finalization count | 0 |
| artifact completeness | 100% for completed jobs |
| estimated model cost | `$0.00` |
| report source | runtime Postgres state plus artifact metadata |

## Known Limits

This is local T1 runtime evidence. It is not a production deployment, remote
worker, or production capacity claim.

