from __future__ import annotations

import asyncio
from typing import Any

from agent_runtime_grid.worker.cancellation import JobCancelledError


class TransientRunnerError(RuntimeError):
    pass


class PolicyValidationError(ValueError):
    pass


class StubJobRunner:
    async def run(
        self,
        payload: dict[str, Any],
        *,
        cancellation_event: asyncio.Event | None = None,
    ) -> dict[str, Any]:
        mode = payload.get("mode", "success")
        if mode == "transient_error":
            raise TransientRunnerError("stub transient failure")
        if mode in {"policy_error", "permanent_error"}:
            raise PolicyValidationError("stub policy validation failure")
        if mode == "sleep":
            await self._sleep(payload, cancellation_event=cancellation_event)
        return {
            "summary": "stub job completed",
            "input_keys": sorted(payload),
        }

    async def _sleep(
        self,
        payload: dict[str, Any],
        *,
        cancellation_event: asyncio.Event | None,
    ) -> None:
        duration_seconds = float(payload.get("duration_seconds", 1))
        loop = asyncio.get_running_loop()
        deadline = loop.time() + duration_seconds
        while loop.time() < deadline:
            if cancellation_event is not None and cancellation_event.is_set():
                raise JobCancelledError("stub job cancellation requested")
            await asyncio.sleep(min(0.05, max(0, deadline - loop.time())))
