# License review

Review date: 2026-07-13. Project license decision: Apache-2.0.

The review inspected declared direct runtime dependencies, installed package
metadata in a clean project environment, and the two default Compose services.
All direct Python dependencies use permissive MIT, Apache-2.0, BSD-2-Clause, or
BSD-3-Clause terms compatible with distribution of this project's original code
under Apache-2.0.

| Dependency | Declared range | Observed license metadata |
|---|---|---|
| Alembic | `>=1.13,<2.0` | MIT |
| asyncpg | `>=0.29,<1.0` | Apache-2.0 |
| FastAPI | `>=0.115,<1.0` | MIT |
| OpenTelemetry API/SDK | `>=1.28,<2.0` | Apache-2.0 |
| prometheus-client | `>=0.21,<1.0` | Apache-2.0 AND BSD-2-Clause |
| Pydantic / pydantic-settings | `>=2.10,<3.0`, `>=2.6,<3.0` | MIT |
| redis-py | `>=5.2,<6.0` | MIT |
| SQLAlchemy | `>=2.0,<3.0` | MIT |
| Typer | `>=0.13,<1.0` | MIT |
| Uvicorn | `>=0.32,<1.0` | BSD-3-Clause |

Default services:

- PostgreSQL `16.14-alpine3.24` uses the PostgreSQL License; its Docker Official
  Image packaging is MIT. The Compose/CI image index digest starts `57c72fd2`.
- Redis `7.2.14-alpine3.21` is intentionally pinned to the 7.2 line and index
  digest `dfa18828...`. Redis 7.2
  and earlier remain BSD-3-Clause; 7.4 moved to source-available terms, so a
  broad `redis:7` tag is not acceptable for this OSS claim.

Primary references:

- https://www.postgresql.org/about/licence/
- https://github.com/docker-library/postgres
- https://redis.io/legal/licenses/
- https://hub.docker.com/_/redis

The machine-readable review snapshot is
`docs/license-review/direct-dependencies.json`. Container base packages and
transitive Python dependencies retain their own notices. Dependency updates must
rerun this review; this document is an engineering compatibility record, not
legal advice.
