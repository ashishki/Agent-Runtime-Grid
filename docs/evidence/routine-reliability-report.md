# Routine Reliability Report Contract

Status: starter evidence contract
Scope: generated routine reliability reports

## Required Fields

Generated routine reliability reports should include:

| Field | Meaning |
|-------|---------|
| routine name | Stable routine identifier |
| trigger type | manual, cron, webhook, or event |
| run window | Time range or proof run ID |
| submitted jobs | Number of jobs accepted |
| success rate | Completed jobs divided by submitted jobs |
| retry rate | Jobs that retried at least once |
| timeout rate | Jobs that reached timeout |
| DLQ rate | Jobs routed to dead-letter stream |
| cost per completed job | Total estimated cost divided by completed jobs |
| p95 queue delay | Queue wait p95 |
| p95 runtime | Execution duration p95 |
| fallback count | Manual review, retry-later, or disabled fallback events |
| artifact integrity | Artifact path, SHA-256, size, job/run/attempt, input digest |
| known limits | Boundaries and non-production claims |

## Recommended Smoke

Future CLI shape:

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli routine smoke \
  --routine support-kb-refresh \
  --trigger cron \
  --jobs 100 \
  --failure-rate 0.05 \
  --report reports/routines/support-kb-refresh.md
```

This is a roadmap contract. It documents the evidence shape without expanding
the current runtime into a scheduler.

