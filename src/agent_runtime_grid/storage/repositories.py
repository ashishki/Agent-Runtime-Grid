from __future__ import annotations

from typing import Any

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_runtime_grid.domain.jobs import (
    IdempotencyConflictError,
    JobEventRecord,
    JobRecord,
    JobSubmission,
)
from agent_runtime_grid.storage.models import job_events_table, jobs_table


class JobRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_job(self, submission: JobSubmission) -> JobRecord:
        async with self._session.begin():
            existing = await self._get_by_idempotency_key(submission.idempotency_key)
            if existing is not None:
                if existing.payload_hash != submission.payload_hash:
                    raise IdempotencyConflictError(submission.idempotency_key)
                return existing

            inserted_job = await self._session.execute(
                insert(jobs_table)
                .values(
                    id=submission.job_id,
                    run_id=submission.run_id,
                    job_type=submission.job_type,
                    payload=submission.payload,
                    payload_hash=submission.payload_hash,
                    idempotency_key=submission.idempotency_key,
                    status="submitted",
                    timeout_seconds=submission.timeout_seconds,
                    max_retries=submission.max_retries,
                    trace_id=submission.trace_id,
                    budget_cents=submission.budget_cents,
                )
                .returning(jobs_table)
            )
            job = _job_record_from_mapping(inserted_job.mappings().one())

            await self._session.execute(
                insert(job_events_table).values(
                    job_id=job.id,
                    run_id=job.run_id,
                    event_type="submitted",
                    event_data={
                        "idempotency_key": job.idempotency_key,
                        "timeout_seconds": job.timeout_seconds,
                        "max_retries": job.max_retries,
                    },
                    trace_id=job.trace_id,
                )
            )

        return job

    async def get_by_idempotency_key(self, idempotency_key: str) -> JobRecord | None:
        return await self._get_by_idempotency_key(idempotency_key)

    async def _get_by_idempotency_key(self, idempotency_key: str) -> JobRecord | None:
        result = await self._session.execute(
            select(jobs_table).where(jobs_table.c.idempotency_key == idempotency_key)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None
        return _job_record_from_mapping(row)

    async def list_events_for_job(self, job_id: object) -> list[JobEventRecord]:
        result = await self._session.execute(
            select(job_events_table)
            .where(job_events_table.c.job_id == job_id)
            .order_by(job_events_table.c.id.asc())
        )
        return [_job_event_record_from_mapping(row) for row in result.mappings()]


def _job_record_from_mapping(row: Any) -> JobRecord:
    return JobRecord(
        id=row["id"],
        run_id=row["run_id"],
        job_type=row["job_type"],
        payload=row["payload"],
        payload_hash=row["payload_hash"],
        idempotency_key=row["idempotency_key"],
        status=row["status"],
        timeout_seconds=row["timeout_seconds"],
        max_retries=row["max_retries"],
        trace_id=row["trace_id"],
        budget_cents=row["budget_cents"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _job_event_record_from_mapping(row: Any) -> JobEventRecord:
    return JobEventRecord(
        id=row["id"],
        job_id=row["job_id"],
        run_id=row["run_id"],
        event_type=row["event_type"],
        event_data=row["event_data"],
        trace_id=row["trace_id"],
        created_at=row["created_at"],
    )
