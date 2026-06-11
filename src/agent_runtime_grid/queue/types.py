from dataclasses import dataclass


@dataclass(frozen=True)
class QueueJobMessage:
    job_id: str
    run_id: str
    attempt_number: int
    trace_id: str
    entry_id: str | None = None

    def to_stream_fields(self) -> dict[str, str]:
        return {
            "job_id": self.job_id,
            "run_id": self.run_id,
            "attempt_number": str(self.attempt_number),
            "trace_id": self.trace_id,
        }


@dataclass(frozen=True)
class DeadLetterMessage:
    job_id: str
    run_id: str
    attempt_number: int
    trace_id: str
    final_error_class: str
    attempt_count: int
    entry_id: str | None = None
