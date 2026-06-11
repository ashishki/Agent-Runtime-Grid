from __future__ import annotations

import asyncio
from collections.abc import Awaitable


class JobTimedOutError(TimeoutError):
    pass


async def run_with_timeout[T](awaitable: Awaitable[T], *, timeout_seconds: int) -> T:
    try:
        return await asyncio.wait_for(awaitable, timeout=timeout_seconds)
    except TimeoutError as exc:
        raise JobTimedOutError("job exceeded configured timeout") from exc
