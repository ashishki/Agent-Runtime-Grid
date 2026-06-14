# Failure Injection Pack - Committed Evidence Snapshot

This is a stable reviewer snapshot for the failure-injection report pack.
Generated reports under `reports/failure-injection/` remain ignored by git.

## Rerun Command

```bash
PATH=.venv/bin:$PATH python -m agent_runtime_grid.cli failure-reports write-pack \
  --output-dir reports/failure-injection
```

## Covered Scenarios

| Scenario | Evidence expectation |
| --- | --- |
| transient retry | retry event trail and eventual terminal state |
| timeout | timed-out lifecycle without completed artifact claim |
| cancellation | cancelled lifecycle and bounded worker behavior |
| stale worker recovery | stale pending lease detection and requeue/DLQ policy |
| duplicate finalization prevention | one terminal finalization despite replay/race pressure |
| DLQ routing | exhausted retry path reaches dead-letter queue |

## Report Shape

Each generated scenario report should include:

- scenario
- command
- expected behavior
- actual lifecycle
- event trail
- metrics
- artifact evidence
- known limits

## Known Limits

This pack is deterministic local failure evidence. It is not remote chaos
testing, production incident evidence, or proof of arbitrary untrusted-code
sandboxing.

