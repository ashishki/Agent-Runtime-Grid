# Reports - Agent Runtime Grid

Generated reports live under this directory. Report contents are ignored by git so local benchmark and failure-injection output does not churn repository history.

Committed files in this directory describe report expectations and preserve empty directories.

## Current Reports

- `reports/load_smoke.md` - current smoke benchmark report path produced by the benchmark harness.
- `reports/smoke.md` - real 100-job smoke command output produced by T16.
- `reports/v1/reliability_report.md` - real 500-job reliability proof output produced by T17.
- `tests/integration/test_stale_lease_recovery.py` - executable stale-worker recovery proof produced by T18.
- `reports/ai_cost_rollup.md` - planned cost rollup output path used by the cost CLI.
- `reports/failure-injection/*.md` - failure scenario report pack produced by T25.
- `reports/full-stack/runtime_report.md` - cross-project runtime proof output produced by T29.

## Planned Reports

- Future reports are tracked in `docs/tasks.md`.

## Required Runtime Evidence

Reliability reports should include:

- submitted jobs
- lifecycle distribution
- completion rate
- retry count
- timeout count
- DLQ count
- duplicate-finalization count
- queue lag p95
- execution duration p95
- queue/backpressure section
- artifact completeness
- artifact integrity rows: path, SHA-256, size, job ID, run ID, attempt number, input digest, created-at
- estimated cost
- failure classification
- known limits for the run

Smoke and 500-job reliability proof reports are generated from actual runtime state.
