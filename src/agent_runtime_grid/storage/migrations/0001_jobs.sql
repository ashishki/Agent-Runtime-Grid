CREATE TABLE jobs (
    id uuid PRIMARY KEY,
    run_id uuid NOT NULL,
    job_type varchar(64) NOT NULL,
    payload jsonb NOT NULL,
    payload_hash varchar(64) NOT NULL,
    idempotency_key varchar(255) NOT NULL UNIQUE,
    status varchar(32) NOT NULL,
    timeout_seconds integer NOT NULL,
    max_retries integer NOT NULL,
    trace_id varchar(128) NOT NULL,
    budget_cents integer,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT ck_jobs_timeout_positive CHECK (timeout_seconds > 0),
    CONSTRAINT ck_jobs_max_retries_non_negative CHECK (max_retries >= 0)
);

CREATE TABLE job_events (
    id bigserial PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    event_type varchar(64) NOT NULL,
    event_data jsonb NOT NULL,
    trace_id varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE job_finalizations (
    job_id uuid PRIMARY KEY REFERENCES jobs(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    status varchar(32) NOT NULL,
    event_type varchar(64) NOT NULL,
    trace_id varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE finalization_conflict_attempts (
    id bigserial PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    attempted_status varchar(32) NOT NULL,
    attempted_event_type varchar(64) NOT NULL,
    trace_id varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE artifacts (
    id bigserial PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    path varchar(1024) NOT NULL,
    size_bytes bigint NOT NULL,
    sha256 varchar(64) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_artifacts_job_path UNIQUE (job_id, path)
);

CREATE TABLE job_retry_records (
    id bigserial PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    attempt_number integer NOT NULL,
    error_class varchar(128) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT uq_retry_job_attempt UNIQUE (job_id, attempt_number),
    CONSTRAINT ck_retry_attempt_positive CHECK (attempt_number > 0)
);

CREATE TABLE job_cost_records (
    id bigserial PRIMARY KEY,
    job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    run_id uuid NOT NULL,
    model varchar(128) NOT NULL,
    input_tokens integer NOT NULL DEFAULT 0,
    output_tokens integer NOT NULL DEFAULT 0,
    estimated_cost_usd numeric(12, 6) NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
