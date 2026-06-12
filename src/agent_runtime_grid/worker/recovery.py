from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.finalization import TERMINAL_STATUSES
from agent_runtime_grid.worker.lease import (
    STALE_LEASE_EXHAUSTED_ERROR_CLASS,
    StaleLease,
)
from agent_runtime_grid.worker.state_machine import (
    load_job_for_update,
    record_failed,
    record_stale_lease_recovered,
)


@dataclass(frozen=True)
class StaleLeaseRecoveryResult:
    detected_count: int
    requeued_count: int
    dlq_count: int
    acknowledged_terminal_count: int
    acknowledged_missing_count: int


@dataclass(frozen=True)
class _RecoveryAction:
    kind: Literal["ack_missing", "ack_terminal", "requeue", "dlq"]
    lease: StaleLease
    requeued_message: QueueJobMessage | None = None


async def recover_stale_leases(
    *,
    queue: RedisStreamsQueue,
    session_factory: async_sessionmaker[AsyncSession],
    recovery_worker_id: str,
    stale_after_ms: int,
    count: int = 100,
) -> StaleLeaseRecoveryResult:
    stale_leases = await queue.find_stale_leases(stale_after_ms=stale_after_ms, count=count)

    requeued_count = 0
    dlq_count = 0
    acknowledged_terminal_count = 0
    acknowledged_missing_count = 0

    for lease in stale_leases:
        action = await _plan_recovery_action(
            lease=lease,
            session_factory=session_factory,
            recovery_worker_id=recovery_worker_id,
        )
        if action.kind == "requeue":
            assert action.requeued_message is not None
            await queue.publish_job(action.requeued_message)
            await _acknowledge_lease(queue, lease)
            requeued_count += 1
        elif action.kind == "dlq":
            await queue.move_to_dead_letter(
                lease.message,
                final_error_class=STALE_LEASE_EXHAUSTED_ERROR_CLASS,
                attempt_count=lease.message.attempt_number,
            )
            dlq_count += 1
        elif action.kind == "ack_terminal":
            await _acknowledge_lease(queue, lease)
            acknowledged_terminal_count += 1
        else:
            await _acknowledge_lease(queue, lease)
            acknowledged_missing_count += 1

    return StaleLeaseRecoveryResult(
        detected_count=len(stale_leases),
        requeued_count=requeued_count,
        dlq_count=dlq_count,
        acknowledged_terminal_count=acknowledged_terminal_count,
        acknowledged_missing_count=acknowledged_missing_count,
    )


async def _plan_recovery_action(
    *,
    lease: StaleLease,
    session_factory: async_sessionmaker[AsyncSession],
    recovery_worker_id: str,
) -> _RecoveryAction:
    async with session_factory() as session:
        async with session.begin():
            job = await load_job_for_update(session, UUID(lease.message.job_id))
            if job is None:
                return _RecoveryAction(kind="ack_missing", lease=lease)

            if job.status in TERMINAL_STATUSES:
                return _RecoveryAction(kind="ack_terminal", lease=lease)

            if lease.message.attempt_number <= job.max_retries:
                next_attempt_number = lease.message.attempt_number + 1
                stale_entry_id = lease.message.entry_id or ""
                await record_stale_lease_recovered(
                    session,
                    job,
                    recovery_worker_id=recovery_worker_id,
                    stale_consumer_name=lease.consumer_name,
                    stale_entry_id=stale_entry_id,
                    stale_idle_ms=lease.idle_ms,
                    delivery_count=lease.delivery_count,
                    attempt_number=lease.message.attempt_number,
                    next_attempt_number=next_attempt_number,
                )
                return _RecoveryAction(
                    kind="requeue",
                    lease=lease,
                    requeued_message=QueueJobMessage(
                        job_id=str(job.id),
                        run_id=str(job.run_id),
                        attempt_number=next_attempt_number,
                        trace_id=job.trace_id,
                    ),
                )

            await record_failed(
                session,
                job,
                worker_id=recovery_worker_id,
                attempt_number=lease.message.attempt_number,
                error_class=STALE_LEASE_EXHAUSTED_ERROR_CLASS,
                retryable=True,
            )
            return _RecoveryAction(kind="dlq", lease=lease)


async def _acknowledge_lease(queue: RedisStreamsQueue, lease: StaleLease) -> None:
    if lease.message.entry_id is not None:
        await queue.acknowledge(lease.message.entry_id)
