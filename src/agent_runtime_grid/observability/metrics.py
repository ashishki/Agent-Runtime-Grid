from __future__ import annotations

from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, generate_latest


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
        self.worker_utilization = Gauge(
            "agent_runtime_grid_worker_utilization",
            "Worker utilization ratio.",
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


def required_metric_names() -> set[str]:
    return {
        "agent_runtime_grid_queue_depth",
        "agent_runtime_grid_queue_lag_seconds",
        "agent_runtime_grid_worker_utilization",
        "agent_runtime_grid_job_duration_seconds",
        "agent_runtime_grid_retry_total",
        "agent_runtime_grid_timeout_total",
        "agent_runtime_grid_failure_total",
        "agent_runtime_grid_dlq_total",
        "agent_runtime_grid_duplicate_finalization_total",
        "agent_runtime_grid_artifact_total",
        "agent_runtime_grid_estimated_cost_usd",
    }
