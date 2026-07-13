# Runtime Grid OSS and truth-repair verification

Date: 2026-07-13. Scope: pre-commit verification worktree.

## Product boundary repaired

- Default Compose now contains only Postgres and Redis.
- Placeholder API/worker containers and unconnected Prometheus/Grafana services
  were removed.
- The API module is documented as experimental library code, not a deployed
  service.
- Proof commands require an explicit reset flag and refuse remote or unrelated
  database targets.

## Finalization evidence repaired

- Rejected competing terminal writes are stored in
  `finalization_conflict_attempts`.
- Duplicate terminal events are queried independently and remain an invariant
  violation.
- Idempotency submission replays remain a third, separate measure.
- Race, replay, stale recovery, smoke, and reliability tests exercise the
  distinction.

## Open-source review

- Project license: Apache-2.0.
- Direct Python dependency metadata: MIT, Apache-2.0, BSD-2-Clause, or
  BSD-3-Clause; see `docs/LICENSE_REVIEW.md`.
- PostgreSQL image: `16.14-alpine3.24`, index digest
  `57c72fd2a128e416c7fcc499958864df5301e940bca0a56f58fddf30ffc07777`.
- Redis image: `7.2.14-alpine3.21`, index digest
  `dfa18828cbc07b3ae6a95ec7343f6c214fdee2d836197b4be8e9904420762cd8`.
- Redis 7.2 was selected because that line remains BSD-3-Clause; the previous
  broad `redis:7` tag resolved to a source-available 7.4 image.

The old Redis 7.4 RDB was incompatible with Redis 7.2. Before recreating the
test/runtime volume, a mode-600 archive was created and verified:

```text
redis-data-before-7.2.14.tgz
sha256 da33fb988b42288d269eacce9b759d6546da0b8c6684bb580bacc7c13ee86b13
contents: dump.rdb
```

No Postgres volume was removed.

## Verification

Pinned services:

```text
PostgreSQL 16.14: healthy
Redis 7.2.14: healthy
redis-cli ping: PONG
```

Repository checks:

```text
ruff format --check src tests: pass
ruff check src tests: pass
pytest tests -q: 97 passed, 1 upstream Starlette deprecation warning
git diff --check: pass
```

Wheel inspection:

```text
agent_runtime_grid-0.1.0-py3-none-any.whl
sha256 e2742f2dbef6292227615f06a5c6d9734e12455fc345a9667561bf713974c65b
Apache LICENSE included: yes
console entry point included: yes
storage/migrations/0001_jobs.sql included: yes
```

Real local smoke:

```text
run_id: 3a62f6b7-8da3-4710-bd50-6b2e76b86f13
jobs: 20
completed: 20
artifact completeness: 100%
duplicate terminal events: 0
estimated model cost: 0
manifest verification: pass
Markdown sha256: 96031d045d9248efcf4feeb01815245d33ccd01814d8429806d7dbec92dcfbce
JSON sha256: 54d8a40bb8c0e9ce0c984753d12697c3e71349860f422875d6b89adb9ea04ac0
manifest sha256: 5f8d4f9ffeefbdd001acfa182d2c191142bc00c6f8c44519f761bbaa7654dc58
absolute-path/secret marker scan: no matches
```

The smoke bundle was generated before the atomic commit, so its JSON correctly
marks the source worktree dirty. Release evidence must be regenerated from the
tag and must report `dirty: false`.

## Claim boundary

This verifies a local synthetic CLI/library runtime. It does not establish a
hosted service, production throughput, an availability SLO, an external user,
or independent attestation.
