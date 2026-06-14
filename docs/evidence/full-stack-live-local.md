# Full-Stack Live-Local Proof - Committed Evidence Snapshot

This snapshot documents the optional local HTTP proof mode. Generated report
contents under `reports/full-stack/` remain ignored by git.

## Scope

- Input: ready Eval Lab gdev-agent dataset path
- Input: ready Eval Lab gdev-agent baseline report path
- Input: ready gdev-agent artifact path
- Runtime: selected cases become `gdev_webhook_eval` jobs with `mode=local`
- Workers: Grid workers call the operator-configured local gdev-agent
  `/webhook`
- External model calls by Runtime Grid: 0
- Network scope: localhost/loopback gdev-agent URL only
- Secret scope: webhook secret value is read from an environment variable and
  is not stored in job payloads, artifacts, or reports

## Rerun Command

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli proof full-stack-live-local \
  --eval-lab-dataset ../Eval-Ground-Truth-Lab/datasets/gdev_agent/triage_v1.jsonl \
  --eval-lab-report ../Eval-Ground-Truth-Lab/reports/gdev-agent/baseline_report.md \
  --gdev-artifact ../gdev-agent/eval/results/last_run.json \
  --gdev-base-url http://localhost:8000 \
  --gdev-webhook-secret-env GDEV_AGENT_WEBHOOK_SECRET \
  --jobs 20 \
  --workers 4 \
  --report reports/full-stack/live_local_runtime_report.md
```

## Evidence Snapshot

| Signal | Expected snapshot |
| --- | --- |
| proof mode | `full-stack-live-local` |
| lifecycle authority | Postgres |
| delivery state | Redis Streams |
| worker egress | operator-configured localhost gdev-agent `/webhook` only |
| runtime artifacts | request hash, sanitized response, normalized fields, timing, attempts, status |
| cross-links | Eval Lab quality report, gdev-agent artifact path, Grid run ID |
| duplicate finalization count | 0 |
| secret handling | webhook secret value omitted from payloads, reports, and artifacts |

## Limits

This is local T1 evidence, not hosted operations or remote deployment proof. For
reproducible no-model-cost runs, start `gdev-agent` in deterministic demo mode.
