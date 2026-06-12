# Cost Budget - Agent Runtime Grid

Mode: Standard
Owner: project operator
Last updated: 2026-06-12

---

## Budget Scope

| Scope | Limit | Window | Enforcement |
|-------|-------|--------|-------------|
| Default stub benchmark run | $0 model cost | per run | block any provider call |
| Optional live LLM benchmark run | target below $5 | per run | manual approval before run; live dispatch requires explicit run and job budgets |
| Per job | configured by job type; default $0 in stub mode | per job | block dispatch when missing or above configured limit |
| Per project / month | unknown | monthly | approval required before recurring live LLM usage |
| Per agent / workflow | max 500 model calls for the v1 proof run when live mode is approved | per run | approval required for fan-out increase |

T22 adds runtime budget gates for provider calls, live dispatch, retry projection, and strict cost rollup thresholds. Live LLM execution still requires explicit approval and configuration before any provider call.

---

## Attribution Tags

Every LLM call or agent run must be attributable to:

- project
- run ID
- job ID
- job type
- task or workflow
- worker ID
- agent or role when applicable
- model
- provider
- user/operator or service account
- feature/workload
- environment

---

## Model Routing Budget

| Workload | Default model/class | Escalation allowed when | Cheaper fallback | Verification metric |
|----------|---------------------|--------------------------|------------------|---------------------|
| Runtime control plane | no model | never without ADR and human approval | deterministic code | policy/state tests pass |
| Stub benchmark jobs | deterministic fixture | not applicable | deterministic fixture | zero provider calls and zero cost |
| Optional live summarization/classification sample job | small or standard structured-output model | marked job requires stronger quality and operator approves budget | stub job or smaller model | benchmark stays below configured budget and task-specific quality test passes |

---

## Guardrails

- Max model calls per run: 0 in stub mode; 500 in approved live v1 proof run.
- Max tool calls per run: not applicable for v1 runtime control plane.
- Max retries per failing call: 2.
- Max parallel agents: not applicable for control plane; worker count is runtime config.
- Stop condition for repeated equivalent failures: stop after two equivalent implementation correction turns or after budget projection exceeds approved limit.
- Human approval threshold: any live LLM run, model escalation, retry expansion, fan-out increase, external egress enablement, or projected overrun.

---

## Required Measurements

- input tokens
- output tokens
- total tokens
- estimated cost
- latency
- retry count
- tool call count when applicable
- provider
- model
- run ID
- job ID
- worker ID
- result quality/eval outcome where available

---

## Telemetry

- Telemetry file: `docs/ai_cost_telemetry.jsonl`
- Entry schema: project-owned schema in `src/agent_runtime_grid/cost/telemetry.py`
- Rollup command:

```bash
python -m agent_runtime_grid.cli cost rollup \
  --input docs/ai_cost_telemetry.jsonl \
  --output reports/ai_cost_rollup.md \
  --strict
```

- CI threshold command after T22:

```bash
python -m agent_runtime_grid.cli cost rollup \
  --input docs/ai_cost_telemetry.jsonl \
  --output reports/ai_cost_rollup.md \
  --strict \
  --require-file \
  --max-total-cost 5 \
  --max-run-cost 5
```

After T22, strict rollup exits non-zero when `--strict` is set and the loaded telemetry exceeds `--max-total-cost` or `--max-run-cost`, or when `--require-file` is set and the telemetry file is missing.

---

## Enforcement

- Stub mode has `max_model_calls=0`; any provider call in stub mode raises `ProviderCallBlockedError`.
- Live dispatch requires both a configured run budget and a configured per-job budget.
- A live job without `budget_cents` is blocked before worker execution.
- A job whose `budget_cents` exceeds the per-job or run budget is blocked before worker execution.
- Retry projection checks the configured retry budget before requeueing a transient failure.
- Budget-blocked worker paths emit a terminal `budget_blocked` event and acknowledge the Redis message only after the database event is recorded.

---

## Approval Triggers

- Enabling `LLM_MODE=live`.
- Increasing the per-run live benchmark target above $5.
- Raising retry limits beyond 2 for model calls.
- Adding a new provider or model class.
- Adding LLM-directed tool calls or external side effects.
- Increasing fan-out, worker count, or benchmark size in a live LLM run.

---

## Review Rule

A cost-saving change is acceptable only when quality and latency stay within declared thresholds. A cheaper route that causes retries, rework, or lower pass rate is not a real saving.
