# Reports - Agent Runtime Grid

Generated reports live under this directory. Report contents are ignored by git
so local benchmark and failure-injection output does not churn repository
history.

Committed files in this directory describe report expectations and preserve
empty directories. Stable reviewer snapshots live under `docs/evidence/`.

## Current Reports

- `reports/load_smoke.md` - current smoke benchmark report path produced by the benchmark harness.
- `reports/smoke.md` - real 100-job smoke command output produced by T16.
- `reports/v1/reliability_report.md` - real 500-job reliability proof output produced by T17.
- `tests/integration/test_stale_lease_recovery.py` - executable stale-worker recovery proof produced by T18.
- `reports/ai_cost_rollup.md` - planned cost rollup output path used by the cost CLI.
- `reports/failure-injection/*.md` - failure scenario report pack produced by T25.
- `reports/full-stack/runtime_report.md` - cross-project artifact proof output produced by T29.
- `reports/full-stack/live_local_runtime_report.md` - optional full-stack live-local proof output produced by T31.
- `docs/evidence/runtime-smoke-100.md` - committed snapshot for the generated 100-job smoke report.
- `docs/evidence/runtime-reliability-500.md` - committed snapshot for the generated 500-job reliability report.
- `docs/evidence/full-stack-artifact-proof.md` - committed snapshot for the current cross-project artifact proof.
- `docs/evidence/full-stack-live-local.md` - committed snapshot for the optional live-local proof mode.
- `docs/evidence/failure-injection-pack-summary.md` - committed snapshot for the failure-injection report pack.

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

Smoke and 500-job reliability proof reports are generated from actual runtime
state. The committed snapshots are reviewer-facing summaries with rerun commands;
the generated reports remain the current-run outputs.
