from agent_runtime_grid.observability.metrics import RuntimeMetrics, required_metric_names


def test_required_runtime_metrics_exposed() -> None:
    metrics = RuntimeMetrics()
    metrics.queue_depth.set(1)
    metrics.queue_lag_seconds.set(0.5)
    metrics.worker_utilization.set(0.25)
    metrics.job_duration_seconds.observe(0.1)
    metrics.retry_total.inc()
    metrics.timeout_total.inc()
    metrics.failure_total.inc()
    metrics.dlq_total.inc()
    metrics.finalization_conflict_attempt_total.inc()
    metrics.artifact_total.inc()
    metrics.estimated_cost_usd.inc(0)

    rendered = metrics.render()

    for metric_name in required_metric_names():
        assert metric_name in rendered
