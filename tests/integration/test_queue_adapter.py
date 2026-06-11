import os
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from redis.asyncio import Redis

from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage

DEFAULT_REDIS_URL = "redis://localhost:6379/0"


@pytest_asyncio.fixture
async def redis_client() -> AsyncIterator[Redis]:
    client = Redis.from_url(
        os.environ.get("REDIS_URL", DEFAULT_REDIS_URL),
        decode_responses=True,
    )
    try:
        yield client
    finally:
        await client.aclose()


@pytest.fixture
def stream_names() -> tuple[str, str]:
    suffix = uuid4().hex
    return f"jobs:{suffix}", f"jobs:{suffix}:dlq"


@pytest.fixture
def queue(redis_client: Redis, stream_names: tuple[str, str]) -> RedisStreamsQueue:
    stream_name, dlq_stream_name = stream_names
    return RedisStreamsQueue(
        redis_client,
        stream_name=stream_name,
        consumer_group="workers",
        dlq_stream_name=dlq_stream_name,
    )


def _message() -> QueueJobMessage:
    return QueueJobMessage(
        job_id=str(uuid4()),
        run_id=str(uuid4()),
        attempt_number=1,
        trace_id="trace-queue-001",
    )


@pytest.mark.asyncio
async def test_publish_job_entry(
    redis_client: Redis,
    queue: RedisStreamsQueue,
) -> None:
    message = _message()

    entry_id = await queue.publish_job(message)

    entries = await redis_client.xrange(queue.stream_name, min=entry_id, max=entry_id)

    assert len(entries) == 1
    assert entries[0][1] == {
        "job_id": message.job_id,
        "run_id": message.run_id,
        "attempt_number": "1",
        "trace_id": "trace-queue-001",
    }


@pytest.mark.asyncio
async def test_lease_and_ack_job(queue: RedisStreamsQueue) -> None:
    message = _message()
    await queue.publish_job(message)

    leased = await queue.lease_jobs(consumer_name="worker-1")

    assert len(leased) == 1
    assert leased[0].job_id == message.job_id
    assert leased[0].run_id == message.run_id
    assert leased[0].attempt_number == 1
    assert leased[0].trace_id == "trace-queue-001"
    assert leased[0].entry_id is not None

    acknowledged = await queue.acknowledge(leased[0].entry_id)

    assert acknowledged == 1


@pytest.mark.asyncio
async def test_exhausted_job_moves_to_dlq(
    redis_client: Redis,
    queue: RedisStreamsQueue,
) -> None:
    message = _message()
    await queue.publish_job(message)
    leased = await queue.lease_jobs(consumer_name="worker-1")

    dlq_entry_id = await queue.move_to_dead_letter(
        leased[0],
        final_error_class="TransientRunnerError",
        attempt_count=3,
    )

    dlq_entries = await redis_client.xrange(
        queue.dlq_stream_name,
        min=dlq_entry_id,
        max=dlq_entry_id,
    )

    assert len(dlq_entries) == 1
    assert dlq_entries[0][1] == {
        "job_id": message.job_id,
        "run_id": message.run_id,
        "attempt_number": "1",
        "trace_id": "trace-queue-001",
        "final_error_class": "TransientRunnerError",
        "attempt_count": "3",
    }
    assert leased[0].entry_id is not None
    assert await queue.acknowledge(leased[0].entry_id) == 0
