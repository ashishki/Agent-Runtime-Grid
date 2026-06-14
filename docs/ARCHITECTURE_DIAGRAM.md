# Architecture Diagram

## Runtime Path

```text
                           +---------------------+
                           | API / CLI           |
                           | submit, status,     |
                           | smoke, benchmark,   |
                           | failure reports     |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | Postgres            |
                           | jobs, events,       |
                           | finalizations, cost |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | Redis Streams       |
                           | queue, pending,     |
                           | consumer lag, DLQ   |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | workers             |
                           | lease, timeout,     |
                           | cancel, retry,      |
                           | stale recovery      |
                           +----------+----------+
                                      |
                 +--------------------+--------------------+
                 |                    |                    |
                 v                    v                    v
       +----------------+    +----------------+    +----------------+
       | stub jobs      |    | eval_lab_case  |    | gdev_webhook_ |
       | deterministic  |    | Eval-Ground-  |    | eval           |
       | local runner   |    | Truth-Lab      |    | gdev-agent     |
       |                |    | integration    |    | integration    |
       +-------+--------+    +-------+--------+    +-------+--------+
               |                     |                     |
               +---------------------+---------------------+
                                     |
                                     v
                           +---------------------+
                           | artifacts           |
                           | path, SHA-256,      |
                           | size, input digest, |
                           | attempt metadata    |
                           +----------+----------+
                                      |
                                      v
                           +---------------------+
                           | reports             |
                           | smoke, 500-job,     |
                           | failure injection,  |
                           | artifact proof,     |
                           | cost rollup         |
                           +---------------------+
```

## Evidence Flow

```text
Eval-Ground-Truth-Lab cases
  -> eval_lab_case jobs
  -> Redis Streams
  -> workers
  -> runtime artifacts
  -> Eval Lab result path cross-link
  -> reliability reports

gdev-agent webhook cases
  -> gdev_webhook_eval jobs
  -> Redis Streams
  -> workers
  -> sanitized response artifacts
  -> Eval Lab-compatible result path
  -> reliability reports

Full-stack artifact proof
  -> ready Eval Lab dataset/report paths
  -> ready gdev-agent artifact path
  -> selected gdev_webhook_eval jobs
  -> runtime artifacts and report cross-links
  -> future live-local mode remains separate
```

## Authority Boundaries

| Area | Authority |
|------|-----------|
| Lifecycle state | Postgres jobs and event log |
| Delivery state | Redis Streams pending and consumer-group state |
| Terminal finalization | Postgres finalization guard |
| Queue/backpressure metrics | Redis Streams plus Postgres event timing |
| Artifacts | Local artifact store with integrity metadata |
| Reports | Generated from runtime state and validated scenario evidence |
| Cost gates | Budget policy plus strict cost rollup |
