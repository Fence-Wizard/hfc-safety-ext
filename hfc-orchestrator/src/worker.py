from __future__ import annotations

import logging
from typing import Any, Callable

from rq import get_current_job

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def noop_handler(payload: dict[str, Any]) -> dict[str, Any]:
    return {"echo": payload}


HANDLERS: dict[str, Callable[[dict[str, Any]], Any]] = {
    "noop": noop_handler,
}


def register_handler(job_type: str, handler: Callable[[dict[str, Any]], Any]) -> None:
    """Register a callable to handle the given job type."""

    HANDLERS[job_type] = handler


def run_job(job_id: str | None, job_type: str, payload: dict[str, Any] | None = None, correlation_id: str | None = None) -> Any:
    """Entry point invoked by RQ workers."""

    payload = payload or {}
    handler = HANDLERS.get(job_type)
    if handler is None:
        raise ValueError(f"No handler registered for job type '{job_type}'")

    current = get_current_job()
    resolved_job_id = job_id or (current.id if current else "unknown")
    logger.info("Running job %s type=%s correlation=%s", resolved_job_id, job_type, correlation_id)

    result = handler(payload)

    logger.info("Job %s finished", resolved_job_id)
    return result
