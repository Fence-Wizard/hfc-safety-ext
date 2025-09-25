from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from rq.job import NoSuchJobError

from src.queue import enqueue, get_job

app = FastAPI(title="HFC Master Orchestrator", version="0.1.0")


@app.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


class JobIn(BaseModel):
    job_type: str
    payload: dict[str, Any]
    correlation_id: str | None = None


@app.post("/jobs", status_code=202)
def create_job(job: JobIn) -> dict[str, str]:
    job_id = enqueue(job.job_type, job.payload, job.correlation_id)
    return {"id": job_id, "status": "queued"}


@app.get("/jobs/{job_id}")
def read_job(job_id: str) -> dict[str, Any]:
    try:
        rq_job = get_job(job_id)
    except NoSuchJobError as exc:  # pragma: no cover - thin wrapper
        raise HTTPException(status_code=404, detail="job not found") from exc

    status = rq_job.get_status(refresh=True)
    result: Any = None
    try:
        result = rq_job.result
    except Exception:  # pragma: no cover - defensive
        result = None

    return {"id": rq_job.id, "status": status, "result": result}
