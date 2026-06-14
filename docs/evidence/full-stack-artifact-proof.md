# Full-Stack Artifact Proof - Committed Evidence Snapshot

This snapshot names the current cross-project mode precisely. The CLI command is
`proof full-stack`, but the behavior is artifact-linked runtime proof, not live
HTTP end-to-end execution.

## Scope

- Input: ready Eval Lab gdev-agent dataset path
- Input: ready Eval Lab gdev-agent baseline report path
- Input: ready gdev-agent internal eval artifact path
- Runtime: selected cases become `gdev_webhook_eval` jobs
- Workers: deterministic local Grid workers
- External model calls: 0
- Live gdev-agent HTTP calls: 0 by default

## Rerun Command

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli proof full-stack \
  --eval-lab-dataset ../Eval-Ground-Truth-Lab/datasets/gdev_agent/triage_v1.jsonl \
  --eval-lab-report ../Eval-Ground-Truth-Lab/reports/gdev-agent/baseline_report.md \
  --gdev-artifact ../gdev-agent/eval/results/last_run.json \
  --jobs 20 \
  --workers 4 \
  --report reports/full-stack/runtime_report.md
```

## Evidence Snapshot

| Signal | Expected snapshot |
| --- | --- |
| selected cases | 20 by default command |
| lifecycle authority | Postgres |
| delivery state | Redis Streams |
| runtime artifacts | request hash, sanitized response, normalized fields, timing, attempts, status |
| cross-links | Eval Lab quality report, gdev-agent artifact path, Grid run ID |
| duplicate finalization count | 0 |
| secret handling | raw secret-like request fields omitted from report |

## Related Live-Local Mode

`proof full-stack-live-local` is implemented as a separate optional mode. It
runs Grid workers that call a locally running `gdev-agent` `/webhook` endpoint,
while keeping dataset-controlled egress and secrets forbidden.
