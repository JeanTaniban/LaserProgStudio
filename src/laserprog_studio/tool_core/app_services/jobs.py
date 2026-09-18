"""Small synchronous job manager used by ToolContext."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import time
from typing import Any, Callable

JobWork = Callable[[Callable[[float, str | None], None]], Any]


class JobState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass(slots=True)
class Job:
    id: str
    label: str
    state: JobState = JobState.PENDING
    progress: float = 0.0
    message: str = ""
    result: Any = None
    error: str | None = None
    started_at: float | None = None
    finished_at: float | None = None
    cancel_requested: bool = False

    def update(self, value: float, message: str | None = None) -> None:
        self.progress = max(0.0, min(1.0, float(value)))
        if message is not None:
            self.message = str(message)

    def cancel(self) -> None:
        self.cancel_requested = True
        if self.state in {JobState.PENDING, JobState.RUNNING}:
            self.state = JobState.CANCELLED
            self.finished_at = time.time()


class JobManager:
    """Small job API.

    It executes work synchronously for now, but exposes the same progress/cancel
    shape a future threaded backend can keep.  This avoids blocking external tool
    authors on Qt threading details while keeping tests deterministic.
    """

    def __init__(self) -> None:
        self._ctx: Any | None = None
        self._counter = 0
        self._jobs: dict[str, Job] = {}

    def bind_context(self, ctx: Any) -> "JobManager":
        self._ctx = ctx
        return self

    def start(self, label: str, work: JobWork | Callable[[], Any]) -> Job:
        self._counter += 1
        job = Job(id=f"job:{self._counter}", label=str(label), state=JobState.RUNNING, started_at=time.time())
        self._jobs[job.id] = job
        status = getattr(self._ctx, "status", None)
        try:
            if callable(getattr(status, "progress", None)):
                status.progress(job.label, 0.0)
            def _progress(value: float, message: str | None = None) -> None:
                job.update(value, message)
                if callable(getattr(status, "progress", None)):
                    status.progress(message or job.label, job.progress)
            try:
                job.result = work(_progress)  # type: ignore[misc]
            except TypeError:
                job.result = work()  # type: ignore[operator]
            if job.state != JobState.CANCELLED:
                job.state = JobState.DONE
                job.update(1.0, job.message or "Done")
                if callable(getattr(status, "info", None)):
                    status.info(f"{job.label}: done")
        except Exception as exc:
            job.state = JobState.FAILED
            job.error = str(exc)
            if callable(getattr(status, "error", None)):
                status.error(f"{job.label}: {exc}")
        finally:
            job.finished_at = time.time()
        return job

    def get(self, job_id: str) -> Job | None:
        return self._jobs.get(str(job_id))

    def jobs(self) -> tuple[Job, ...]:
        return tuple(self._jobs.values())

    def cancel(self, job_id: str) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.cancel()
        return True
