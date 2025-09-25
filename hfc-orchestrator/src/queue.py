import os
from typing import Any

from redis import Redis
from rq import Queue
from rq.job import Job

REDIS_URL = os.getenv("REDIS_URL")
if not REDIS_URL:
    raise RuntimeError("REDIS_URL not set")

redis_conn = Redis.from_url(REDIS_URL)
q_default = Queue("default", connection=redis_conn)


def enqueue(job_type: str, payload: dict[str, Any] | None, correlation_id: str | None = None) -> str:
    """Enqueue a job executed by src.worker.run_job and return the RQ job id."""

    payload = payload or {}
    rq_job = q_default.enqueue(
        "src.worker.run_job",
        None,
        job_type,
        payload,
        correlation_id,
        description=f"{job_type}:{correlation_id or ''}".strip(":"),
        retry=None,
    )
    return rq_job.id


def get_job(job_id: str) -> Job:
    """Fetch an RQ job by id."""

    return Job.fetch(job_id, connection=redis_conn)
