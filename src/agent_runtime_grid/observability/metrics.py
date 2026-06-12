from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest

from agent_runtime_grid.queue.inspection import QueueBackpressureSnapshot


class RuntimeMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()
        self.queue_depth = Gauge(
            "agent_runtime_grid_queue_depth",
            "Current Redis stream queue depth.",
            registry=self.registry,
        )
        self.queue_lag_seconds = Gauge(
            "agent_runtime_grid_queue_lag_seconds",
            "Current age of the oldest queued job.",
            registry=self.registry,
        )
        self.queue_oldest_pending_age_seconds = Gauge(
            "agent_runtime_grid_queue_oldest_pending_age_seconds",
            "Age of the oldest pending leased Redis Streams entry.",
            registry=self.registry,
        )
        self.queue_consumer_lag = Gauge(
            "agent_runtime_grid_queue_consumer_lag",
            "Redis Streams consumer-group lag.",
            registry=self.registry,
        )
        self.queue_leased_jobs = Gauge(
            "agent_runtime_grid_queue_leased_jobs",
            "Redis Streams pending entries leased by workers.",
            registry=self.registry,
        )
        self.queue_running_jobs = Gauge(
            "agent_runtime_grid_queue_running_jobs",
            "Jobs currently marked running in Postgres.",
            registry=self.registry,
        )
        self.worker_utilization = Gauge(
            "agent_runtime_grid_worker_utilization",
            "Worker utilization ratio.",
            registry=self.registry,
        )
        self.queue_retry_rate = Gauge(
            "agent_runtime_grid_queue_retry_rate",
            "Retry decisions divided by submitted jobs.",
            registry=self.registry,
        )
        self.queue_dlq_count = Gauge(
            "agent_runtime_grid_queue_dlq_count",
            "Current Redis dead-letter stream length.",
            registry=self.registry,
        )
        self.queue_wait_p95_seconds = Gauge(
            "agent_runtime_grid_queue_wait_p95_seconds",
            "P95 time from submitted event to first running event.",
            registry=self.registry,
        )
        self.queue_execution_p95_seconds = Gauge(
            "agent_runtime_grid_queue_execution_p95_seconds",
            "P95 time from first running event to terminal event.",
            registry=self.registry,
        )
        self.job_duration_seconds = Histogram(
            "agent_runtime_grid_job_duration_seconds",
            "Job execution duration.",
            registry=self.registry,
        )
        self.retry_total = Counter(
            "agent_runtime_grid_retry_total",
            "Retry decisions recorded by the runtime.",
            registry=self.registry,
        )
        self.timeout_total = Counter(
            "agent_runtime_grid_timeout_total",
            "Timed-out jobs recorded by the runtime.",
            registry=self.registry,
        )
        self.failure_total = Counter(
            "agent_runtime_grid_failure_total",
            "Failed jobs recorded by the runtime.",
            registry=self.registry,
        )
        self.dlq_total = Counter(
            "agent_runtime_grid_dlq_total",
            "Jobs moved to the dead-letter stream.",
            registry=self.registry,
        )
        self.duplicate_finalization_total = Counter(
            "agent_runtime_grid_duplicate_finalization_total",
            "Actual duplicate terminal finalization defects.",
            registry=self.registry,
        )
        self.artifact_total = Counter(
            "agent_runtime_grid_artifact_total",
            "Artifacts written by the runtime.",
            registry=self.registry,
        )
        self.estimated_cost_usd = Counter(
            "agent_runtime_grid_estimated_cost_usd",
            "Estimated model cost in USD.",
            registry=self.registry,
        )

    def render(self) -> str:
        return generate_latest(self.registry).decode("utf-8")

    def record_backpressure_snapshot(self, snapshot: QueueBackpressureSnapshot) -> None:
        self.queue_depth.set(snapshot.queue_depth)
        self.queue_lag_seconds.set(snapshot.p95_queue_wait_seconds)
        self.queue_oldest_pending_age_seconds.set(snapshot.oldest_pending_age_seconds)
        self.queue_consumer_lag.set(snapshot.consumer_lag)
        self.queue_leased_jobs.set(snapshot.leased_jobs)
        self.queue_running_jobs.set(snapshot.running_jobs)
        self.worker_utilization.set(snapshot.worker_utilization)
        self.queue_retry_rate.set(snapshot.retry_rate)
        self.queue_dlq_count.set(snapshot.dlq_count)
        self.queue_wait_p95_seconds.set(snapshot.p95_queue_wait_seconds)
        self.queue_execution_p95_seconds.set(snapshot.p95_execution_seconds)


def required_metric_names() -> set[str]:
    return {
        "agent_runtime_grid_queue_depth",
        "agent_runtime_grid_queue_lag_seconds",
        "agent_runtime_grid_queue_oldest_pending_age_seconds",
        "agent_runtime_grid_queue_consumer_lag",
        "agent_runtime_grid_queue_leased_jobs",
        "agent_runtime_grid_queue_running_jobs",
        "agent_runtime_grid_worker_utilization",
        "agent_runtime_grid_queue_retry_rate",
        "agent_runtime_grid_queue_dlq_count",
        "agent_runtime_grid_queue_wait_p95_seconds",
        "agent_runtime_grid_queue_execution_p95_seconds",
        "agent_runtime_grid_job_duration_seconds",
        "agent_runtime_grid_retry_total",
        "agent_runtime_grid_timeout_total",
        "agent_runtime_grid_failure_total",
        "agent_runtime_grid_dlq_total",
        "agent_runtime_grid_duplicate_finalization_total",
        "agent_runtime_grid_artifact_total",
        "agent_runtime_grid_estimated_cost_usd",
    }
