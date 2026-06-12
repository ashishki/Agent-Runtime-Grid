# Security Boundaries

Agent Runtime Grid is a local-first runtime. Its v1 API boundary is intentionally small and deterministic.

## Public Health

`GET /health` is public by design. It returns only:

```json
{"status": "ok"}
```

It must not include settings, connection strings, credentials, environment values, job payloads, queue details, or internal lifecycle state.

## Local Token Auth

All non-health API routes require bearer-token authentication when `API_TOKEN` is configured.

Protected routes today:

- `POST /jobs/batch`
- `GET /jobs/runs/{run_id}/status`

Requests without the configured bearer token are rejected with HTTP 401.

## Localhost-Only No-Token Mode

No-token mode is accepted only when `API_BIND_HOST` is a localhost binding:

- `127.0.0.1`
- `localhost`
- `::1`

If `API_TOKEN` is unset and `API_BIND_HOST` is non-local, app creation fails before serving requests. This prevents accidentally exposing unauthenticated mutation or inspection routes on `0.0.0.0` or another network-reachable interface.

## Evidence

Executable proof lives in `tests/integration/test_auth_boundary.py`:

- public, secret-free health response
- protected mutation and inspection routes when a token is configured
- localhost-only no-token mode
