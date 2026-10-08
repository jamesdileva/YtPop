"""Job context (D3): marks work running *under* a queue job.

S5/S9 services wrote their own TRANSCRIBE/RENDER job rows for
traceability. Since S13 the queue also creates a row for the same work,
so direct service calls double-count in the ops view. Services now skip
their row when this contextvar is set, and the resets are exception-safe.
"""

import contextvars

_active_job: contextvars.ContextVar[int | None] = contextvars.ContextVar(
    "ytpop_active_job", default=None
)


def set_active_job(job_id: int | None):
    """Install the active job id; returns a token for reset_active_job."""
    return _active_job.set(job_id)


def reset_active_job(token) -> None:
    _active_job.reset(token)


def active_job_id() -> int | None:
    return _active_job.get()


def running_under_job() -> bool:
    return _active_job.get() is not None
