"""VRVision cloud processing API."""
from __future__ import annotations

import datetime as dt
import hashlib
import os
import re

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from . import db, tasks
from .auth import enforce_https, issue_token, require_client, verify_api_key
from .config import Settings, get_settings
from .db import Job, JobStatus, utcnow
from .media import MediaError, probe, validate_source
from .storage import get_storage

API_VERSION = "1.0.0"
CONSENT_TEXT_VERSION = "2026-10-01"
LAYOUTS = {"MONO", "SIDE_BY_SIDE", "TOP_BOTTOM"}
PROJECTIONS = {"FLAT", "EQUIRECT_180", "EQUIRECT_360"}

app = FastAPI(title="VRVision processing API", version=API_VERSION)


# ---------- schemas ----------

class TokenResponse(BaseModel):
    token: str
    expires_at: int


class QuoteRequest(BaseModel):
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    duration_ms: int = Field(gt=0)
    size_bytes: int = Field(gt=0)


class QuoteResponse(BaseModel):
    estimated_seconds: float
    estimated_cost: float | None
    currency: str | None
    max_upload_bytes: int
    max_duration_ms: int
    basis: str


class Consent(BaseModel):
    granted: bool
    text_version: str
    granted_at: dt.datetime


class CreateJob(BaseModel):
    consent: Consent
    file_name: str = Field(min_length=1, max_length=255)
    size_bytes: int = Field(gt=0)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    width: int = Field(gt=0)
    height: int = Field(gt=0)
    fps: float = Field(gt=0)
    duration_ms: int = Field(gt=0)
    layout: str
    projection: str
    out_width: int = Field(gt=0)
    out_height: int = Field(gt=0)
    denoise: bool = True
    sharpen_amount: float = Field(default=0.0, ge=0.0, le=1.0)
    preview_start_ms: int = Field(default=0, ge=0)


class JobView(BaseModel):
    id: str
    status: str
    phase: str
    progress: float
    stage: str
    error: str | None
    received_bytes: int
    size_bytes: int
    out_width: int
    out_height: int
    preview_available: bool
    output_available: bool
    result: dict | None
    expires_at: dt.datetime


def view(j: Job) -> JobView:
    return JobView(
        id=j.id, status=j.status, phase=j.phase, progress=j.progress, stage=j.stage, error=j.error,
        received_bytes=j.received_bytes, size_bytes=j.size_bytes, out_width=j.out_width, out_height=j.out_height,
        preview_available=j.preview_key is not None, output_available=j.output_key is not None,
        result=j.result, expires_at=j.expires_at,
    )


def owned_job(job_id: str, client: str) -> Job:
    with db.session() as s:
        job = s.get(Job, job_id)
    # Same response for "missing" and "not yours" so job ids can't be probed.
    if job is None or job.client != client:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Job not found")
    return job


# ---------- endpoints ----------

@app.get("/v1/health")
def health(settings: Settings = Depends(get_settings)) -> dict:
    return {
        "status": "ok",
        "version": API_VERSION,
        "sr_engine": settings.sr_engine,
        "consent_text_version": CONSENT_TEXT_VERSION,
        "preview_duration_ms": settings.preview_duration_ms,
        "retention_hours": settings.retention_hours,
    }


@app.post("/v1/auth/token", response_model=TokenResponse)
def token(request: Request, x_api_key: str | None = Header(default=None), settings: Settings = Depends(get_settings)):
    enforce_https(request, settings)
    client = verify_api_key(x_api_key, settings)
    tok, exp = issue_token(client, settings)
    return TokenResponse(token=tok, expires_at=exp)


@app.post("/v1/quote", response_model=QuoteResponse)
def quote(q: QuoteRequest, client: str = Depends(require_client), settings: Settings = Depends(get_settings)):
    frames = q.fps * q.duration_ms / 1000
    seconds = frames * (q.width * q.height / 1e6) / settings.throughput_mp_per_s
    cost = None
    if settings.price_per_gpu_minute is not None:
        cost = round(seconds / 60 * settings.price_per_gpu_minute, 2)
    return QuoteResponse(
        estimated_seconds=round(seconds, 1), estimated_cost=cost, currency=settings.currency if cost is not None else None,
        max_upload_bytes=settings.max_upload_bytes, max_duration_ms=settings.max_duration_ms,
        basis=f"{settings.throughput_mp_per_s} source MP/s configured by the operator",
    )


@app.post("/v1/jobs", status_code=status.HTTP_201_CREATED)
def create_job(body: CreateJob, client: str = Depends(require_client), settings: Settings = Depends(get_settings)):
    if not body.consent.granted:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Explicit consent to upload is required")
    if body.consent.text_version != CONSENT_TEXT_VERSION:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Consent text changed; current version {CONSENT_TEXT_VERSION}")
    if body.layout not in LAYOUTS or body.projection not in PROJECTIONS:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown layout or projection")
    if body.size_bytes > settings.max_upload_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "File exceeds the per-job upload limit")
    if body.duration_ms > settings.max_duration_ms:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Video exceeds the per-job duration limit")
    if body.width * body.height > settings.max_source_pixels:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Source resolution exceeds the server limit")
    if body.out_width > settings.max_output_width or body.out_height > settings.max_output_height:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Output resolution exceeds the server limit")
    if not (body.width <= body.out_width <= body.width * 4 and body.height <= body.out_height <= body.height * 4):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Output must be 1x to 4x the source size")
    with db.session() as s:
        active = s.query(Job).filter(
            Job.client == client,
            Job.status.in_([JobStatus.UPLOADING.value, JobStatus.QUEUED.value, JobStatus.PROCESSING.value]),
        ).count()
        if active >= settings.max_active_jobs_per_client:
            raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, "Too many active jobs")
        job = Job(
            client=client, consent_granted_at=body.consent.granted_at, consent_text_version=body.consent.text_version,
            file_name=os.path.basename(body.file_name), size_bytes=body.size_bytes, sha256=body.sha256,
            width=body.width, height=body.height, fps=body.fps, duration_ms=body.duration_ms,
            layout=body.layout, projection=body.projection, out_width=body.out_width, out_height=body.out_height,
            denoise=body.denoise, sharpen_amount=body.sharpen_amount,
            preview_start_ms=min(body.preview_start_ms, max(0, body.duration_ms - settings.preview_duration_ms)),
            expires_at=utcnow() + dt.timedelta(hours=settings.upload_expiry_hours),
        )
        s.add(job)
        s.commit()
        return {"id": job.id, "upload": {"chunk_bytes": settings.upload_chunk_bytes, "received_bytes": 0}}


@app.get("/v1/jobs/{job_id}", response_model=JobView)
def get_job(job_id: str, client: str = Depends(require_client)):
    return view(owned_job(job_id, client))


_RANGE = re.compile(r"^bytes (\d+)-(\d+)/(\d+)$")


@app.put("/v1/jobs/{job_id}/upload")
async def upload_chunk(job_id: str, request: Request, content_range: str = Header(...),
                       client: str = Depends(require_client), settings: Settings = Depends(get_settings)):
    """Appends one chunk. Content-Range must start exactly at the bytes already received, so an
    interrupted upload resumes by asking GET /v1/jobs/{id} for received_bytes."""
    job = owned_job(job_id, client)
    if job.status != JobStatus.UPLOADING.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Job is not accepting uploads")
    m = _RANGE.match(content_range)
    if not m:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Content-Range must be 'bytes start-end/total'")
    start, end, total = map(int, m.groups())
    if total != job.size_bytes or end < start or end >= total:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Content-Range does not match the declared file size")
    if start != job.received_bytes:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Expected offset {job.received_bytes}")
    if end - start + 1 > settings.upload_chunk_bytes:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Chunk too large")
    data = await request.body()
    if len(data) != end - start + 1:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Body length does not match Content-Range")
    os.makedirs(settings.upload_staging_dir, exist_ok=True)
    path = os.path.join(settings.upload_staging_dir, f"{job_id}.part")
    with open(path, "ab") as f:
        if f.tell() != start:
            f.truncate(start)
            f.seek(start)
        f.write(data)
    with db.session() as s:
        j = s.get(Job, job_id)
        j.received_bytes = end + 1
        s.commit()
        return {"received_bytes": j.received_bytes}


@app.post("/v1/jobs/{job_id}/upload/complete", response_model=JobView)
def complete_upload(job_id: str, client: str = Depends(require_client), settings: Settings = Depends(get_settings)):
    job = owned_job(job_id, client)
    if job.status != JobStatus.UPLOADING.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Upload already completed")
    if job.received_bytes != job.size_bytes:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Upload incomplete: {job.received_bytes}/{job.size_bytes} bytes")
    path = os.path.join(settings.upload_staging_dir, f"{job_id}.part")
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != job.sha256:
        _fail_and_purge(job_id, path, "Checksum mismatch; upload corrupted")
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Checksum mismatch; upload corrupted")
    try:
        p = probe(path)
        validate_source(p, settings)
        if p.variable_frame_rate:
            raise MediaError("Variable frame rate sources are not supported by the cloud worker; process locally instead")
    except MediaError as e:
        _fail_and_purge(job_id, path, str(e))
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    key = f"jobs/{job_id}/source"
    get_storage().put_file(key, path)
    os.remove(path)
    with db.session() as s:
        j = s.get(Job, job_id)
        j.source_key = key
        j.probe = p.raw | {"rotation": p.rotation, "audio": p.audio_codec, "duration_ms": p.duration_ms}
        j.status = JobStatus.QUEUED.value
        j.stage = "Queued for preview"
        j.expires_at = utcnow() + dt.timedelta(hours=settings.retention_hours)
        s.commit()
    task_id = tasks.enqueue(job_id, "preview")
    with db.session() as s:
        j = s.get(Job, job_id)
        j.task_id = task_id
        s.commit()
        return view(j)


def _fail_and_purge(job_id: str, path: str, error: str) -> None:
    if os.path.exists(path):
        os.remove(path)
    with db.session() as s:
        j = s.get(Job, job_id)
        j.status = JobStatus.FAILED.value
        j.error = error
        j.finished_at = utcnow()
        s.commit()


@app.post("/v1/jobs/{job_id}/full", response_model=JobView)
def start_full(job_id: str, client: str = Depends(require_client)):
    """Starts full processing after the user accepted the preview."""
    job = owned_job(job_id, client)
    if job.status != JobStatus.PREVIEW_READY.value:
        raise HTTPException(status.HTTP_409_CONFLICT, "Full processing starts only after a successful preview")
    with db.session() as s:
        j = s.get(Job, job_id)
        j.status = JobStatus.QUEUED.value
        j.phase = "full"
        j.stage = "Queued for full processing"
        s.commit()
    tid = tasks.enqueue(job_id, "full")
    with db.session() as s:
        j = s.get(Job, job_id)
        j.task_id = tid
        s.commit()
        return view(j)


@app.post("/v1/jobs/{job_id}/cancel", response_model=JobView)
def cancel(job_id: str, client: str = Depends(require_client)):
    job = owned_job(job_id, client)
    with db.session() as s:
        j = s.get(Job, job_id)
        j.cancel_requested = True
        if j.status in (JobStatus.UPLOADING.value, JobStatus.QUEUED.value, JobStatus.PREVIEW_READY.value):
            j.status = JobStatus.CANCELLED.value
            j.stage = "Cancelled"
            j.finished_at = utcnow()
        s.commit()
    if job.status != JobStatus.PROCESSING.value:
        tasks.delete_job_data(job_id)
    with db.session() as s:
        return view(s.get(Job, job_id))


@app.delete("/v1/jobs/{job_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(job_id: str, client: str = Depends(require_client)):
    """Deletes source, preview and output immediately (the user's 'delete now' choice)."""
    owned_job(job_id, client)
    with db.session() as s:
        j = s.get(Job, job_id)
        j.cancel_requested = True
        s.commit()
    tasks.delete_job_data(job_id)
    with db.session() as s:
        j = s.get(Job, job_id)
        j.status = JobStatus.EXPIRED.value
        j.stage = "Deleted by user"
        s.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.get("/v1/jobs/{job_id}/output")
def download(job_id: str, kind: str = "full", range_header: str | None = Header(default=None, alias="Range"),
             client: str = Depends(require_client)):
    job = owned_job(job_id, client)
    key = job.preview_key if kind == "preview" else job.output_key
    if key is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Output not available")
    storage = get_storage()
    size = storage.size(key)
    start, end = 0, size - 1
    code = status.HTTP_200_OK
    if range_header:
        m = re.match(r"^bytes=(\d+)-(\d*)$", range_header)
        if not m or int(m.group(1)) >= size:
            raise HTTPException(status.HTTP_416_RANGE_NOT_SATISFIABLE, "Bad range")
        start = int(m.group(1))
        end = min(int(m.group(2)) if m.group(2) else size - 1, size - 1)
        code = status.HTTP_206_PARTIAL_CONTENT
    headers = {"Accept-Ranges": "bytes", "Content-Length": str(end - start + 1),
               "Content-Disposition": f'attachment; filename="{kind}.mp4"'}
    if code == status.HTTP_206_PARTIAL_CONTENT:
        headers["Content-Range"] = f"bytes {start}-{end}/{size}"
    return StreamingResponse(storage.stream(key, start, end), status_code=code, media_type="video/mp4", headers=headers)
