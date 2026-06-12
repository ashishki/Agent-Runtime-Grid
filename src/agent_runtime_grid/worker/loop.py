from __future__ import annotations

import asyncio
from uuid import UUID

from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_runtime_grid.artifacts.store import ArtifactStore
from agent_runtime_grid.cost.telemetry import BudgetPolicy, BudgetPolicyError
from agent_runtime_grid.jobs.eval_lab import EvalLabPayloadError, run_eval_lab_case
from agent_runtime_grid.jobs.gdev_agent import GdevAgentPayloadError, run_gdev_webhook_eval
from agent_runtime_grid.jobs.stub import (
    PolicyValidationError,
    StubJobRunner,
    TransientRunnerError,
)
from agent_runtime_grid.queue.redis_streams import RedisStreamsQueue
from agent_runtime_grid.queue.types import QueueJobMessage
from agent_runtime_grid.storage.finalization import TERMINAL_STATUSES
from agent_runtime_grid.worker.cancellation import (
    CancellationRegistry,
    JobCancelledError,
)
from agent_runtime_grid.worker.state_machine import (
    load_job_for_update,
    record_budget_blocked,
    record_cancelled,
    record_completed,
    record_failed,
    record_retry_scheduled,
    record_running,
    record_timed_out,
)
from agent_runtime_grid.worker.timeouts import JobTimedOutError, run_with_timeout


class Worker:
    def __init__(
        self,
        *,
        worker_id: str,
        queue: RedisStreamsQueue,
        session_factory: async_sessionmaker[AsyncSession],
        runner: StubJobRunner | None = None,
        artifact_store: ArtifactStore | None = None,
        cancellation_registry: CancellationRegistry | None = None,
        budget_policy: BudgetPolicy | None = None,
        lease_renewal_interval_seconds: float | None = 5.0,
    ) -> None:
        self.worker_id = worker_id
        self._queue = queue
        self._session_factory = session_factory
        self._runner = runner or StubJobRunner()
        self._artifact_store = artifact_store
        self._cancellation_registry = cancellation_registry or CancellationRegistry()
        self._budget_policy = budget_policy or BudgetPolicy.stub()
        self._lease_renewal_interval_seconds = lease_renewal_interval_seconds

    async def process_one(self) -> bool:
        leased_jobs = await self._queue.lease_jobs(consumer_name=self.worker_id, count=1)
        if not leased_jobs:
            return False

        message = leased_jobs[0]
        await self._process_message(message)
        return True

    async def _process_message(self, message: QueueJobMessage) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                job = await load_job_for_update(session, UUID(message.job_id))
                if job is None:
                    if message.entry_id is not None:
                        await self._queue.acknowledge(message.entry_id)
                    return
                if job.status in TERMINAL_STATUSES:
                    if message.entry_id is not None:
                        await self._queue.acknowledge(message.entry_id)
                    return
                try:
                    self._budget_policy.validate_job_dispatch(job)
                except BudgetPolicyError as exc:
                    await record_budget_blocked(
                        session,
                        job,
                        worker_id=self.worker_id,
                        attempt_number=message.attempt_number,
                        reason=exc.reason,
                        attempted_cost_usd=exc.attempted_cost_usd,
                        budget_limit_usd=exc.budget_limit_usd,
                    )
                    if message.entry_id is not None:
                        await self._queue.acknowledge(message.entry_id)
                    return
                await record_running(
                    session,
                    job,
                    worker_id=self.worker_id,
                    attempt_number=message.attempt_number,
                )

            heartbeat_task = self._start_lease_heartbeat(message)
            try:
                cancellation_event = self._cancellation_registry.event_for(str(job.id))
                if job.job_type == "eval_lab_case":
                    job_coro = run_eval_lab_case(
                        job.payload,
                        attempt_number=message.attempt_number,
                    )
                elif job.job_type == "gdev_webhook_eval":
                    job_coro = run_gdev_webhook_eval(
                        job.payload,
                        attempt_number=message.attempt_number,
                    )
                else:
                    job_coro = self._runner.run(
                        job.payload,
                        cancellation_event=cancellation_event,
                    )
                result = await run_with_timeout(
                    job_coro,
                    timeout_seconds=job.timeout_seconds,
                )
            except TransientRunnerError as exc:
                await self._handle_transient_error(message, job, type(exc).__name__)
            except (EvalLabPayloadError, GdevAgentPayloadError, PolicyValidationError) as exc:
                await self._handle_policy_error(message, job, type(exc).__name__)
            except JobTimedOutError:
                await self._handle_timeout(message, job)
            except JobCancelledError:
                await self._handle_cancellation(message, job)
            else:
                if self._artifact_store is not None:
                    artifact_metadata = self._artifact_store.write_stub_job_artifact(
                        job,
                        worker_id=self.worker_id,
                        attempt_number=message.attempt_number,
                        result=result,
                    )
                    result = {
                        **result,
                        "artifact_path": str(artifact_metadata.path),
                        "artifact": artifact_metadata.to_dict(),
                    }
                async with session.begin():
                    await record_completed(
                        session,
                        job,
                        worker_id=self.worker_id,
                        attempt_number=message.attempt_number,
                        result=result,
                    )
                if message.entry_id is not None:
                    await self._queue.acknowledge(message.entry_id)
            finally:
                await self._stop_lease_heartbeat(heartbeat_task)

    async def _handle_transient_error(
        self,
        message: QueueJobMessage,
        job,
        error_class: str,
    ) -> None:
        async with self._session_factory() as session:
            if message.attempt_number <= job.max_retries:
                next_attempt_number = message.attempt_number + 1
                try:
                    self._budget_policy.validate_retry(next_attempt_number=next_attempt_number)
                except BudgetPolicyError as exc:
                    async with session.begin():
                        await record_budget_blocked(
                            session,
                            job,
                            worker_id=self.worker_id,
                            attempt_number=message.attempt_number,
                            reason=exc.reason,
                            attempted_cost_usd=exc.attempted_cost_usd,
                            budget_limit_usd=exc.budget_limit_usd,
                        )
                    if message.entry_id is not None:
                        await self._queue.acknowledge(message.entry_id)
                    return
                async with session.begin():
                    await record_retry_scheduled(
                        session,
                        job,
                        worker_id=self.worker_id,
                        attempt_number=message.attempt_number,
                        next_attempt_number=next_attempt_number,
                        error_class=error_class,
                    )
                await self._queue.publish_job(
                    QueueJobMessage(
                        job_id=str(job.id),
                        run_id=str(job.run_id),
                        attempt_number=next_attempt_number,
                        trace_id=job.trace_id,
                    )
                )
            else:
                async with session.begin():
                    await record_failed(
                        session,
                        job,
                        worker_id=self.worker_id,
                        attempt_number=message.attempt_number,
                        error_class=error_class,
                        retryable=True,
                    )

        if message.entry_id is not None:
            await self._queue.acknowledge(message.entry_id)

    def _start_lease_heartbeat(self, message: QueueJobMessage) -> asyncio.Task[None] | None:
        if message.entry_id is None:
            return None
        if (
            self._lease_renewal_interval_seconds is None
            or self._lease_renewal_interval_seconds <= 0
        ):
            return None
        return asyncio.create_task(
            self._renew_lease_until_cancelled(
                entry_id=message.entry_id,
                interval_seconds=self._lease_renewal_interval_seconds,
            )
        )

    async def _stop_lease_heartbeat(self, heartbeat_task: asyncio.Task[None] | None) -> None:
        if heartbeat_task is None:
            return
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass

    async def _renew_lease_until_cancelled(
        self,
        *,
        entry_id: str,
        interval_seconds: float,
    ) -> None:
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await self._queue.renew_pending_lease(
                    entry_id=entry_id,
                    consumer_name=self.worker_id,
                )
            except RedisError:
                continue

    async def _handle_timeout(self, message: QueueJobMessage, job) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await record_timed_out(
                    session,
                    job,
                    worker_id=self.worker_id,
                    attempt_number=message.attempt_number,
                )

        if message.entry_id is not None:
            await self._queue.acknowledge(message.entry_id)

    async def _handle_cancellation(self, message: QueueJobMessage, job) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await record_cancelled(
                    session,
                    job,
                    worker_id=self.worker_id,
                    attempt_number=message.attempt_number,
                    cancelled_while="running",
                )

        if message.entry_id is not None:
            await self._queue.acknowledge(message.entry_id)

    async def _handle_policy_error(
        self,
        message: QueueJobMessage,
        job,
        error_class: str,
    ) -> None:
        async with self._session_factory() as session:
            async with session.begin():
                await record_failed(
                    session,
                    job,
                    worker_id=self.worker_id,
                    attempt_number=message.attempt_number,
                    error_class=error_class,
                    retryable=False,
                )

        if message.entry_id is not None:
            await self._queue.acknowledge(message.entry_id)
