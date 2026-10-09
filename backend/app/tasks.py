"""Celery tasks: preview/full processing and retention cleanup.

The task bodies are plain functions (run_job, cleanup_expired) so they can be tested without
a broker; Celery only schedules them.
"""
from __future__ import annotations

import datetime as dt
import logging
import os
import shutil
import tempfile

from celery import Celery

from . import db
from .config import get_settings
from .db import Job, JobStatus, utcnow
from .media import probe, validate_output
from .storage import get_storage

log = logging.getLogger("vrvision.worker")

settings = get_settings()
celery_app = Celery("vrvision", broker=settings.redis_url, backend=None)
celery_app.conf.update(
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_time_limit=6 * 3600,
    beat_schedule={"cleanup": {"task": "vrvision.cleanup", "schedule": 900.0}},
)


class JobCancelled(Exception):
    pass


def _update(job_id: str, **fields) -> Job | None:
    with db.session() as s:
        job = s.get(Job, job_id)
        if job is None:
            return None
        for k, v in fields.items():
            setattr(job, k, v)
        s.commit()
        return job


def _cancel_requested(job_id: str) -> bool:
    with db.session() as s:
        job = s.get(Job, job_id)
        return job is None or job.cancel_requested


def run_job(job_id: str, phase: str) -> None:
    """Processes the 10-second preview or the full video for a job."""
    from worker.pipeline import Cancelled, EncodeSettings, process
    from worker.sr import load_engine

    st = get_settings()
    storage = get_storage()
    with db.session() as s:
        job = s.get(Job, job_id)
        if job is None or job.cancel_requested or job.source_key is None:
            return
        job.status = JobStatus.PROCESSING.value
        job.phase = phase
        job.progress = 0.0
        job.stage = "Preparing"
        s.commit()
        snapshot = {c: getattr(job, c) for c in ("source_key", "layout", "out_width", "out_height", "denoise",
                                                  "sharpen_amount", "preview_start_ms", "id", "audio_expected")
                    if hasattr(job, c)}
    work = tempfile.mkdtemp(prefix=f"job-{job_id}-", dir=_ensure(st.work_dir))
    try:
        src = os.path.join(work, "source")
        storage.get_file(snapshot["source_key"], src)
        p = probe(src)
        engine = load_engine(st, bool(snapshot["denoise"]))
        out = os.path.join(work, f"{phase}.mp4")
        is_preview = phase == "preview"

        def progress(done: int, total: int) -> None:
            if done % 5 == 0 or done == total:
                _update(job_id, progress=min(done / max(total, 1), 0.99), stage=f"Enhancing frame {done} of ~{total}")

        result = process(
            src, out, p, engine, snapshot["layout"], snapshot["out_width"], snapshot["out_height"],
            start_ms=snapshot["preview_start_ms"] if is_preview else 0,
            duration_ms=st.preview_duration_ms if is_preview else None,
            sharpen_amount=float(snapshot["sharpen_amount"]),
            enc=EncodeSettings(st.encode_codec, st.encode_preset, st.encode_crf),
            on_progress=progress,
            should_cancel=lambda: _cancel_requested(job_id),
        )
        _update(job_id, stage="Validating output")
        validation = validate_output(out, snapshot["out_width"], snapshot["out_height"], result["frames"], expect_audio=p.audio_codec is not None)
        if not validation["ok"]:
            raise RuntimeError("Output validation failed: " + "; ".join(validation["problems"]))
        key = f"jobs/{job_id}/{phase}.mp4"
        storage.put_file(key, out)
        info = getattr(engine, "model_info", None) or {"name": "Real-ESRGAN general v3 compact (PyTorch)", "version": "v0.2.5.0"}
        res = {**result, "validation": validation, "model": info.get("name"), "model_version": info.get("version"),
               "engine": type(engine).__name__, "providers": getattr(engine, "providers", None),
               "output_bytes": os.path.getsize(out)}
        fields = {"progress": 1.0, "stage": "Done", "result": res, "error": None}
        if is_preview:
            fields.update(status=JobStatus.PREVIEW_READY.value, preview_key=key)
        else:
            fields.update(status=JobStatus.SUCCEEDED.value, output_key=key, finished_at=utcnow(),
                          expires_at=utcnow() + dt.timedelta(hours=st.retention_hours))
        _update(job_id, **fields)
    except Cancelled:
        _update(job_id, status=JobStatus.CANCELLED.value, stage="Cancelled", finished_at=utcnow())
        delete_job_data(job_id)
    except Exception as e:  # report every failure to the client; never leave a job "processing"
        log.exception("job %s failed", job_id)
        _update(job_id, status=JobStatus.FAILED.value, error=str(e)[:1000], stage="Failed", finished_at=utcnow(),
                expires_at=utcnow() + dt.timedelta(hours=st.retention_hours))
    finally:
        shutil.rmtree(work, ignore_errors=True)


def delete_job_data(job_id: str) -> None:
    """Deletes every stored object for a job (source, preview, output)."""
    storage = get_storage()
    st = get_settings()
    with db.session() as s:
        job = s.get(Job, job_id)
        if job is None:
            return
        for key in (job.source_key, job.preview_key, job.output_key):
            if key:
                storage.delete(key)
        staging = os.path.join(st.upload_staging_dir, f"{job_id}.part")
        if os.path.exists(staging):
            os.remove(staging)
        job.source_key = job.preview_key = job.output_key = None
        s.commit()


def cleanup_expired(now: dt.datetime | None = None) -> int:
    """Retention policy: delete data of expired jobs and mark them EXPIRED."""
    now = now or utcnow()
    count = 0
    with db.session() as s:
        ids = [j.id for j in s.query(Job).filter(Job.expires_at <= now, Job.status != JobStatus.EXPIRED.value).all()]
    for job_id in ids:
        delete_job_data(job_id)
        _update(job_id, status=JobStatus.EXPIRED.value, stage="Deleted by retention policy")
        count += 1
    return count


def _ensure(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


@celery_app.task(name="vrvision.process")
def process_task(job_id: str, phase: str) -> None:
    run_job(job_id, phase)


@celery_app.task(name="vrvision.cleanup")
def cleanup_task() -> int:
    return cleanup_expired()


def enqueue(job_id: str, phase: str) -> str | None:
    """Queues processing; returns the task id. Overridable in tests."""
    return process_task.delay(job_id, phase).id
