from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    Numeric,
    String,
    Table,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID

metadata = MetaData()

jobs_table = Table(
    "jobs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("job_type", String(64), nullable=False),
    Column("payload", JSONB, nullable=False),
    Column("payload_hash", String(64), nullable=False),
    Column("idempotency_key", String(255), nullable=False, unique=True),
    Column("status", String(32), nullable=False),
    Column("timeout_seconds", Integer, nullable=False),
    Column("max_retries", Integer, nullable=False),
    Column("trace_id", String(128), nullable=False),
    Column("budget_cents", Integer),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    Column(
        "updated_at",
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    ),
    CheckConstraint("timeout_seconds > 0", name="ck_jobs_timeout_positive"),
    CheckConstraint("max_retries >= 0", name="ck_jobs_max_retries_non_negative"),
)

job_events_table = Table(
    "job_events",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("event_data", JSONB, nullable=False),
    Column("trace_id", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

job_finalizations_table = Table(
    "job_finalizations",
    metadata,
    Column(
        "job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), primary_key=True
    ),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("status", String(32), nullable=False),
    Column("event_type", String(64), nullable=False),
    Column("trace_id", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

finalization_conflict_attempts_table = Table(
    "finalization_conflict_attempts",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("attempted_status", String(32), nullable=False),
    Column("attempted_event_type", String(64), nullable=False),
    Column("trace_id", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)

artifacts_table = Table(
    "artifacts",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("path", String(1024), nullable=False),
    Column("size_bytes", BigInteger, nullable=False),
    Column("sha256", String(64), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("job_id", "path", name="uq_artifacts_job_path"),
)

job_retry_records_table = Table(
    "job_retry_records",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("attempt_number", Integer, nullable=False),
    Column("error_class", String(128), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    UniqueConstraint("job_id", "attempt_number", name="uq_retry_job_attempt"),
    CheckConstraint("attempt_number > 0", name="ck_retry_attempt_positive"),
)

job_cost_records_table = Table(
    "job_cost_records",
    metadata,
    Column("id", BigInteger, primary_key=True, autoincrement=True),
    Column("job_id", UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False),
    Column("run_id", UUID(as_uuid=True), nullable=False),
    Column("model", String(128), nullable=False),
    Column("input_tokens", Integer, nullable=False, server_default="0"),
    Column("output_tokens", Integer, nullable=False, server_default="0"),
    Column("estimated_cost_usd", Numeric(12, 6), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
