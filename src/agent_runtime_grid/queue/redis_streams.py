from __future__ import annotations

from collections.abc import Mapping

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from agent_runtime_grid.queue.types import DeadLetterMessage, QueueJobMessage


class RedisStreamsQueue:
    def __init__(
        self,
        redis: Redis,
        *,
        stream_name: str = "jobs",
        consumer_group: str = "workers",
        dlq_stream_name: str = "jobs:dlq",
    ) -> None:
        self._redis = redis
        self.stream_name = stream_name
        self.consumer_group = consumer_group
        self.dlq_stream_name = dlq_stream_name

    async def ensure_consumer_group(self) -> None:
        try:
            await self._redis.xgroup_create(
                self.stream_name,
                self.consumer_group,
                id="0-0",
                mkstream=True,
            )
        except ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def publish_job(self, message: QueueJobMessage) -> str:
        return await self._redis.xadd(self.stream_name, message.to_stream_fields())

    async def lease_jobs(
        self,
        *,
        consumer_name: str,
        count: int = 1,
        block_ms: int = 100,
    ) -> list[QueueJobMessage]:
        await self.ensure_consumer_group()
        response = await self._redis.xreadgroup(
            self.consumer_group,
            consumer_name,
            streams={self.stream_name: ">"},
            count=count,
            block=block_ms,
        )
        if not response:
            return []

        leased: list[QueueJobMessage] = []
        for _stream_name, entries in response:
            for entry_id, fields in entries:
                leased.append(_queue_message_from_stream_entry(entry_id, fields))
        return leased

    async def acknowledge(self, entry_id: str) -> int:
        return await self._redis.xack(self.stream_name, self.consumer_group, entry_id)

    async def move_to_dead_letter(
        self,
        message: QueueJobMessage,
        *,
        final_error_class: str,
        attempt_count: int,
    ) -> str:
        dead_letter = DeadLetterMessage(
            job_id=message.job_id,
            run_id=message.run_id,
            attempt_number=message.attempt_number,
            trace_id=message.trace_id,
            final_error_class=final_error_class,
            attempt_count=attempt_count,
            entry_id=message.entry_id,
        )
        dlq_entry_id = await self._redis.xadd(
            self.dlq_stream_name,
            {
                "job_id": dead_letter.job_id,
                "run_id": dead_letter.run_id,
                "attempt_number": str(dead_letter.attempt_number),
                "trace_id": dead_letter.trace_id,
                "final_error_class": dead_letter.final_error_class,
                "attempt_count": str(dead_letter.attempt_count),
            },
        )
        if message.entry_id is not None:
            await self.acknowledge(message.entry_id)
        return dlq_entry_id


def _queue_message_from_stream_entry(
    entry_id: str,
    fields: Mapping[str, str],
) -> QueueJobMessage:
    return QueueJobMessage(
        job_id=fields["job_id"],
        run_id=fields["run_id"],
        attempt_number=int(fields["attempt_number"]),
        trace_id=fields["trace_id"],
        entry_id=entry_id,
    )
