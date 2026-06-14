# Known Limits - Agent Runtime Grid

Last updated: 2026-06-14

Agent Runtime Grid is a local-first T1 runtime. The project is intentionally scoped to prove queue-backed execution, durable lifecycle state, deterministic worker behavior, artifacts, logs, metrics, cost telemetry, and reliability reports for batches of AI or agent jobs.

## Non-Goals

Agent Runtime Grid is not:

- a Temporal replacement
- a Ray replacement
- a Kubernetes replacement
- an Airflow replacement
- a managed batch platform
- a production sandbox for arbitrary untrusted code
- a SaaS product
- a multi-tenant billing system
- an autonomous swarm
- an exactly-once execution system

v1 targets at-least-once delivery with idempotent finalization.

## Current Proof Limits

- The real smoke command runs end to end locally, but it is not a remote deployment proof.
- The 500-job reliability proof runs end to end locally, but it is still local T1 evidence rather than a production scale claim.
- Worker crash, Redis pending-entry lease renewal, automated worker heartbeat renewal during long job execution, and local operator repair commands are implemented.
- Backpressure metrics are runtime-derived from Redis Streams and Postgres event timing, but dashboarding and alert policy are still local documentation paths.
- Artifact integrity is validated in reports, but durable object storage beyond local filesystem is not implemented.
- Cost telemetry and budget gates are implemented for local runtime policy, but recurring live provider usage still requires explicit approval.
- Eval-Ground-Truth-Lab and gdev-agent integrations are deterministic local paths; live network adapters are not enabled by default.
- The current cross-project proof is `full-stack-artifact-proof`: it validates
  ready Eval Lab/gdev artifacts and runs deterministic Grid jobs. It does not
  call live gdev-agent over HTTP by default.
- `full-stack-live-local` is implemented for an operator-run local
  `gdev-agent` service, but it is still local T1 evidence. It is not remote
  deployment proof, and it expects `gdev-agent` to run in deterministic demo
  mode for reproducible no-model-cost evidence.
- Failure-injection reports are generated from validated scenario evidence; remote chaos testing is not claimed.

## Local Runtime Boundary

The runtime is local-first and T1:

- Postgres and Redis run through Docker Compose.
- Workers execute known job runners from the repository.
- Runtime containers do not install packages or mutate toolchains at job execution time.
- External LLM and GitHub API calls are disabled unless explicitly configured and approved.
- Default stub mode must remain zero model cost.

## Production Changes Needed

Before remote or trusted operation, the project would need:

- stronger auth and deployment configuration
- durable artifact storage beyond local filesystem
- remote worker supervision and orchestration
- backpressure and queue lag dashboards
- explicit egress and secret allowlists per job type
- production migration workflow
- operational runbooks
- remote CI evidence for the full reliability proof
- remote or scheduled live-local execution with explicit egress, timeout,
  budget, and artifact-retention policy

These are tracked as future work, not current claims.
