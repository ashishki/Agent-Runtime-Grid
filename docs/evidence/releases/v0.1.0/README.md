# Runtime Grid v0.1.0 release evidence

This directory records a deterministic, zero-model-cost local smoke run made
from clean source revision `ddf533b36bbca0fd90a3093984d0b3f36e8ebeab`.
It is release evidence for the supported local CLI/library boundary, not a
production throughput, availability, customer, or external-adoption claim.

## Observed result

- 20 jobs submitted and 20 completed;
- 20 of 20 recorded artifacts passed integrity validation;
- zero failed, timed-out, cancelled, queued, running, or DLQ jobs at report time;
- zero retries, finalization conflicts, duplicate terminal events, or
  idempotency replays;
- estimated model cost: `$0` in `stub` mode;
- Postgres and Redis ran locally with four in-process workers.

The measured p95 execution and queue-wait values describe only this single
machine and run. They are retained in the report for reproducibility and must
not be interpreted as capacity or SLO evidence.

## Files and verification

- `runtime-smoke.md`: human-readable runtime report;
- `runtime-smoke.json`: schema-versioned run record with source, environment,
  configuration, lifecycle, artifact, and backpressure fields;
- `runtime-smoke.manifest.json`: SHA-256 manifest covering both report files.

Verify the committed bytes from the repository root:

```bash
PATH=.venv/bin:$PATH agent-runtime-grid verify-committed-evidence
PATH=.venv/bin:$PATH agent-runtime-grid verify-evidence \
  --manifest docs/evidence/releases/v0.1.0/runtime-smoke.manifest.json
```

The committed-evidence command additionally binds the exact manifest content
address, clean source revision, 20-job lifecycle result, zero-cost stub boundary,
and 20/20 recorded artifact-integrity result. The generic command remains useful
for newly generated bundles.

Expected manifest entries:

```text
runtime-smoke.md   dd755dd40c660218f8dd59f505d18e3ebbd3d900f75ceee0f9aca033c6289fd2
runtime-smoke.json 93863b224f7c07904b83883cd3c8e6a18c8983d2469216dbec87691d5529fbee
```

The manifest file itself has SHA-256
`07442b769fad42a1664cc3adc7a11d73cb2041ceb61f65e402087e096d5b12ed`.

## Reproduction boundary

The original run used Python 3.12.3 on Linux x86_64 and the following command
shape after starting the pinned Postgres and Redis Compose services:

```bash
REPRO_DIR="$(mktemp -d)"
PATH=.venv/bin:$PATH agent-runtime-grid smoke \
  --jobs 20 \
  --workers 4 \
  --mode stub \
  --reset-local-database \
  --artifact-root "$REPRO_DIR/artifacts" \
  --report "$REPRO_DIR/runtime-smoke.md"
PATH=.venv/bin:$PATH agent-runtime-grid verify-evidence \
  --manifest "$REPRO_DIR/runtime-smoke.manifest.json"
```

This reproduction path never overwrites the committed release directory. Remove
`$REPRO_DIR` after review; run identifiers, timestamps, job identifiers, and
timings are intentionally expected to differ.

The committed verifier proves the published run has not changed; the generic
verifier, test suite, and runtime invariants determine whether a new run is
internally valid.
