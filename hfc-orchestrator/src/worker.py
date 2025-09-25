from __future__ import annotations

import logging
import time
from typing import Any, Callable

from .config import get_settings
from .database import session_scope
from .job_service import (
    JobNotFoundError,
    dequeue_next_job,
    get_job,
    mark_job_failed,
    mark_job_succeeded,
)


settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))
logger = logging.getLogger(__name__)


def noop_handler(payload: dict[str, Any]) -> dict[str, Any]:
    return {"echo": payload}


HANDLERS: dict[str, Callable[[dict[str, Any]], dict[str, Any] | None]] = {
    "noop": noop_handler,
}


def run_forever() -> None:
    logger.info("Worker started")
    idle_sleep = settings.worker_poll_interval
    while True:
        job_data: dict[str, Any] | None = None
        with session_scope() as session:
            job = dequeue_next_job(session)
            if job is None:
                job_data = None
            else:
                job_data = {
                    "id": job.id,
                    "job_type": job.job_type,
                    "payload": job.payload or {},
                }
        if job_data is None:
            time.sleep(idle_sleep)
            continue

        job_id = job_data["id"]
        job_type = job_data["job_type"]
        payload = job_data["payload"]
        handler = HANDLERS.get(job_type)
        if handler is None:
            error = f"No handler registered for job type '{job_type}'"
            logger.error(error)
            with session_scope() as session:
                try:
                    job = get_job(session, job_id)
                    mark_job_failed(session, job, error)
                except JobNotFoundError:
                    logger.warning("Job %s disappeared before it could be marked failed", job_id)
            continue

        try:
            result = handler(payload) or {}
        except Exception as exc:  # noqa: BLE001
            logger.exception("Job %s failed", job_id)
            with session_scope() as session:
                try:
                    job = get_job(session, job_id)
                    mark_job_failed(session, job, str(exc))
                except JobNotFoundError:
                    logger.warning("Job %s missing when marking failure", job_id)
            continue

        with session_scope() as session:
            try:
                job = get_job(session, job_id)
                mark_job_succeeded(session, job, result)
                logger.info("Job %s succeeded", job_id)
            except JobNotFoundError:
                logger.warning("Job %s missing when marking success", job_id)


if __name__ == "__main__":
    try:
        run_forever()
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
