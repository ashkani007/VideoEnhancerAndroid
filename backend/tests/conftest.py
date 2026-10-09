import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

API_KEY = "test-key-0123456789abcdef"


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("VRV_API_KEYS", API_KEY + ",other-client-key-xyz")
    monkeypatch.setenv("VRV_TOKEN_SECRET", "s" * 48)
    monkeypatch.setenv("VRV_DATABASE_URL", f"sqlite:///{tmp_path}/t.db")
    monkeypatch.setenv("VRV_LOCAL_STORAGE_DIR", str(tmp_path / "objects"))
    monkeypatch.setenv("VRV_UPLOAD_STAGING_DIR", str(tmp_path / "uploads"))
    monkeypatch.setenv("VRV_WORK_DIR", str(tmp_path / "work"))
    monkeypatch.setenv("VRV_MODEL_DIR", os.path.join(ROOT, "models"))
    monkeypatch.setenv("VRV_TILE", "64")
    monkeypatch.setenv("VRV_UPLOAD_CHUNK_BYTES", str(64 * 1024))
    monkeypatch.setenv("VRV_ENCODE_PRESET", "ultrafast")
    from app import config, db, storage

    config.get_settings.cache_clear()
    db.reset_for_tests()
    storage.reset_for_tests()
    yield tmp_path
    db.reset_for_tests()
    storage.reset_for_tests()
    config.get_settings.cache_clear()


@pytest.fixture()
def client(env, monkeypatch):
    from fastapi.testclient import TestClient

    from app import main, tasks

    queued = []

    def inline(job_id, phase):
        queued.append((job_id, phase))
        tasks.run_job(job_id, phase)  # run the real worker synchronously
        return f"inline-{len(queued)}"

    monkeypatch.setattr(tasks, "enqueue", inline)
    c = TestClient(main.app)
    c.queued = queued
    return c


def token(c, key=API_KEY) -> dict:
    r = c.post("/v1/auth/token", headers={"X-API-Key": key})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['token']}"}


def make_clip(path: str, seconds: float = 2.5, fps: int = 10, eye: str = "64x64", audio: bool = True, identical_eyes: bool = True) -> str:
    """SBS test clip: two eyes side by side (identical when identical_eyes) with AAC audio."""
    w, h = eye.split("x")
    if identical_eyes:
        graph = f"testsrc2=size={eye}:rate={fps}:duration={seconds},split[a][b];[a][b]hstack"
    else:
        graph = (f"testsrc2=size={eye}:rate={fps}:duration={seconds}[a];"
                 f"mandelbrot=size={eye}:rate={fps},trim=duration={seconds}[b];[a][b]hstack")
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", graph]
    if audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-c:a", "aac", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-g", str(fps), path]
    subprocess.run(cmd, check=True)
    return path
