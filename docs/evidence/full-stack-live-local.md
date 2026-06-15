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

## Latest Operator-Run Snapshot

Date: 2026-06-15

Setup:

- `gdev-agent` ran in deterministic `LLM_MODE=demo` through a temporary local
  Compose project with the API exposed at `http://localhost:8000`.
- `gdev-agent` demo flow passed before the proof run: health, auth, signed
  webhook, pending approval, approval execution, and metrics.
- Runtime Grid used local Compose Postgres/Redis on `localhost:5432` and
  `localhost:6379`.
- The webhook secret value was provided only through the named environment
  variable and was not committed.

Generated report:

- `reports/full-stack/live_local_runtime_report.md`
- ignored by git; this snapshot is the committed evidence surface

Result:

| Signal | Observed value |
| --- | --- |
| Grid run ID | `c4276927-3159-46fe-9a1c-f166bc40f4a4` |
| selected cases | 20 |
| completed jobs | 20 |
| failed jobs | 0 |
| DLQ count | 0 |
| retry count | 0 |
| timeout count | 0 |
| duplicate finalization count | 0 |
| checked artifacts | 20 |
| valid artifacts | 20 |
| completion rate | 100.00% |
| artifact completeness | 100.00% |
| queue lag p95 | 11.141s |
| execution duration p95 | 2.858s |
| estimated Runtime Grid model cost | $0 |

Selected slices: the first 20 `triage_v1` cases, covering billing refund,
account access, bug report, and moderation report cases. Runtime Grid made local
HTTP calls to `gdev-agent`; model/provider behavior remained owned by
`gdev-agent` demo mode.

## Limits

This is local T1 evidence, not hosted operations or remote deployment proof. For
reproducible no-model-cost runs, start `gdev-agent` in deterministic demo mode.
