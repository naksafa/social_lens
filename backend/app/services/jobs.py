"""Background job abstraction.

The MVP runs jobs synchronously (datasets are small: a few hundred posts analyze in
~1-2 s). Services depend on the ``TaskRunner`` protocol, so an RQ/Celery-backed runner
can be dropped in later without touching callers.
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

JobStatus = Literal["queued", "running", "completed", "failed"]


@dataclass
class JobHandle:
    id: str
    status: JobStatus
    result: Any = None
    error: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


class TaskRunner(Protocol):
    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> JobHandle: ...


class SyncTaskRunner:
    """Executes the job inline and returns a completed handle (exceptions propagate)."""

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> JobHandle:
        result = fn(*args, **kwargs)
        return JobHandle(id=uuid.uuid4().hex, status="completed", result=result)


def get_task_runner() -> TaskRunner:
    return SyncTaskRunner()
