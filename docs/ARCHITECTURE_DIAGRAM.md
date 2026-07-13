# Architecture diagram

```text
                    supported caller
                  CLI / Python library
                          |
                          v
                +-------------------+
                | Postgres          |
                | jobs + events     |
                | terminal guard    |
                | conflict attempts |
                +---------+---------+
                          |
                          v
                +-------------------+
                | Redis Streams     |
                | delivery + leases |
                | lag + DLQ         |
                +---------+---------+
                          |
                          v
                +-------------------+
                | bounded workers   |
                | timeout + retry   |
                | cancellation      |
                +---------+---------+
                          |
              +-----------+-----------+
              |           |           |
              v           v           v
          stub jobs   Eval adapter  gdev adapter
              |           |           |
              +-----------+-----------+
                          |
                          v
                artifacts + SHA-256
                          |
                          v
             Markdown + JSON + manifest
                          |
                          v
                 strict local verifier
```

Authority boundaries:

| Concern | Authority |
|---|---|
| Lifecycle and terminal state | Postgres |
| Delivery and pending state | Redis Streams |
| Runtime policy | Deterministic Python code |
| Evaluation release decision | Eval Ground Truth Lab |
| Workload behavior/isolation | Workload repository |
| Evidence bytes | Local bundle plus SHA-256 manifest |

The API module, remote workers, dashboards, and hosted execution are outside the
supported diagram because they are not default runnable product surfaces.
