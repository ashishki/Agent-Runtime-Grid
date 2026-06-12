from __future__ import annotations

from collections.abc import Mapping

from redis.asyncio import Redis
from redis.exceptions import ResponseError

from agent_runtime_grid.queue.types import DeadLetterMessage, QueueJobMessage
from agent_runtime_grid.worker.lease import StaleLease


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

    async def find_stale_leases(
        self,
        *,
        stale_after_ms: int,
        count: int = 100,
    ) -> list[StaleLease]:
        await self.ensure_consumer_group()
        pending_entries = await self._redis.xpending_range(
            self.stream_name,
            self.consumer_group,
            min="-",
            max="+",
            count=count,
            idle=stale_after_ms,
        )
        stale_entries: list[StaleLease] = []
        for pending in pending_entries:
            entry_id = pending["message_id"]
            stream_entries = await self._redis.xrange(self.stream_name, min=entry_id, max=entry_id)
            if not stream_entries:
                continue

            _stream_entry_id, fields = stream_entries[0]
            stale_entries.append(
                StaleLease(
                    message=_queue_message_from_stream_entry(entry_id, fields),
                    consumer_name=pending["consumer"],
                    idle_ms=pending["time_since_delivered"],
                    delivery_count=pending["times_delivered"],
                )
            )
        return stale_entries

    async def renew_pending_lease(
        self,
        *,
        entry_id: str,
        consumer_name: str,
    ) -> bool:
        await self.ensure_consumer_group()
        renewed_entry_ids = await self._redis.xclaim(
            self.stream_name,
            self.consumer_group,
            consumer_name,
            min_idle_time=0,
            message_ids=[entry_id],
            justid=True,
        )
        return entry_id in renewed_entry_ids

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
