from __future__ import annotations

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from agent_runtime_grid.artifacts.store import ArtifactStore
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
    ) -> None:
        self.worker_id = worker_id
        self._queue = queue
        self._session_factory = session_factory
        self._runner = runner or StubJobRunner()
        self._artifact_store = artifact_store
        self._cancellation_registry = cancellation_registry or CancellationRegistry()

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
                await record_running(
                    session,
                    job,
                    worker_id=self.worker_id,
                    attempt_number=message.attempt_number,
                )

            try:
                cancellation_event = self._cancellation_registry.event_for(str(job.id))
                result = await run_with_timeout(
                    self._runner.run(
                        job.payload,
                        cancellation_event=cancellation_event,
                    ),
                    timeout_seconds=job.timeout_seconds,
                )
            except TransientRunnerError as exc:
                await self._handle_transient_error(message, job, type(exc).__name__)
            except PolicyValidationError as exc:
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
                    result = {**result, "artifact_path": str(artifact_metadata.path)}
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

    async def _handle_transient_error(
        self,
        message: QueueJobMessage,
        job,
        error_class: str,
    ) -> None:
        async with self._session_factory() as session:
            if message.attempt_number <= job.max_retries:
                next_attempt_number = message.attempt_number + 1
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
