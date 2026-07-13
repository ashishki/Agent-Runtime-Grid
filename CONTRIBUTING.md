# Contributing

Agent Runtime Grid accepts narrow, reproducible changes within its local runtime
boundary. Good contributions fix a demonstrated lifecycle defect, add a bounded
job adapter, strengthen evidence verification, or correct documentation.

Broad orchestration frameworks, hosted-control-plane features, provider demos,
and claims without reproducible evidence are out of scope.

## Local setup

```bash
python3 -m venv .venv
PATH=.venv/bin:$PATH python -m pip install -e . -r requirements-dev.txt
docker-compose up -d postgres redis
PATH=.venv/bin:$PATH ruff check src tests
PATH=.venv/bin:$PATH ruff format --check src tests
PATH=.venv/bin:$PATH python -m pytest -q
```

The integration suite creates and drops tables in the local
`agent_runtime_grid` or `agent_runtime_grid_test` database. Never point tests or
proof commands at production data.

## Change contract

1. Open a focused issue using the closest template.
2. Add a failing regression test before changing behavior.
3. Keep deterministic control decisions outside model/provider code.
4. Do not commit credentials, customer data, generated reports, or absolute
   local paths.
5. Update known limits and evidence semantics when a claim changes.
6. Run the full lint, format, and test commands above.

Pull requests should describe the invariant, the reproduction, the expected
failure before the change, and the verification after it. A passing test alone
does not justify a new product claim.
