import datetime as dt
import hashlib
import os
import subprocess

import numpy as np

from conftest import API_KEY, make_clip, token


def consent(granted=True, version="2026-10-01"):
    return {"granted": granted, "text_version": version, "granted_at": dt.datetime.now(dt.timezone.utc).isoformat()}


def job_body(path, **over):
    data = open(path, "rb").read()
    body = {
        "consent": consent(), "file_name": os.path.basename(path), "size_bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(), "width": 128, "height": 64, "fps": 10.0,
        "duration_ms": 2500, "layout": "SIDE_BY_SIDE", "projection": "EQUIRECT_180",
        "out_width": 256, "out_height": 128, "denoise": True, "sharpen_amount": 0.0, "preview_start_ms": 0,
    }
    body.update(over)
    return body


def upload(c, h, job_id, data, chunk=64 * 1024, start=0, stop=None):
    """Uploads data[start:stop] in chunks; Content-Range always declares the full size."""
    off = start
    stop = len(data) if stop is None else stop
    while off < stop:
        part = data[off:min(off + chunk, stop)]
        r = c.put(f"/v1/jobs/{job_id}/upload", content=part,
                  headers={**h, "Content-Range": f"bytes {off}-{off + len(part) - 1}/{len(data)}"})
        assert r.status_code == 200, r.text
        off += len(part)


def ffprobe(path):
    import json
    out = subprocess.run(["ffprobe", "-v", "error", "-count_packets", "-print_format", "json", "-show_streams", path],
                         check=True, capture_output=True).stdout
    return json.loads(out)["streams"]


def test_health_needs_no_auth(client):
    r = client.get("/v1/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_auth_required_and_keys_checked(client):
    assert client.post("/v1/auth/token").status_code == 401
    assert client.post("/v1/auth/token", headers={"X-API-Key": "nope"}).status_code == 401
    assert client.get("/v1/jobs/x").status_code == 401
    assert client.get("/v1/jobs/x", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_expired_token_rejected(client, env):
    import jwt
    import time
    t = jwt.encode({"sub": "c", "exp": int(time.time()) - 5, "typ": "vrv"}, "s" * 48, algorithm="HS256")
    assert client.get("/v1/jobs/x", headers={"Authorization": f"Bearer {t}"}).json()["detail"] == "Token expired"


def test_consent_is_mandatory(client, env):
    h = token(client)
    clip = make_clip(str(env / "c.mp4"))
    r = client.post("/v1/jobs", json=job_body(clip, consent=consent(granted=False)), headers=h)
    assert r.status_code == 400
    r = client.post("/v1/jobs", json=job_body(clip, consent=consent(version="old")), headers=h)
    assert r.status_code == 409


def test_quotas_and_limits(client, env):
    h = token(client)
    clip = make_clip(str(env / "c.mp4"))
    assert client.post("/v1/jobs", json=job_body(clip, size_bytes=10**12), headers=h).status_code == 413
    assert client.post("/v1/jobs", json=job_body(clip, out_width=128 * 5), headers=h).status_code == 422
    assert client.post("/v1/jobs", json=job_body(clip, layout="WEIRD"), headers=h).status_code == 422
    for _ in range(2):
        assert client.post("/v1/jobs", json=job_body(clip), headers=h).status_code == 201
    assert client.post("/v1/jobs", json=job_body(clip), headers=h).status_code == 429


def test_jobs_are_private_to_their_client(client, env):
    h = token(client)
    other = token(client, "other-client-key-xyz")
    clip = make_clip(str(env / "c.mp4"))
    jid = client.post("/v1/jobs", json=job_body(clip), headers=h).json()["id"]
    assert client.get(f"/v1/jobs/{jid}", headers=other).status_code == 404
    assert client.delete(f"/v1/jobs/{jid}", headers=other).status_code == 404


def test_resumable_upload_rejects_wrong_offsets_and_resumes(client, env):
    h = token(client)
    clip = make_clip(str(env / "c.mp4"))
    data = open(clip, "rb").read()
    jid = client.post("/v1/jobs", json=job_body(clip), headers=h).json()["id"]
    # First chunk, then a simulated network interruption.
    upload(client, h, jid, data, chunk=5000, stop=5000)
    # Re-sending an old range is refused; client must resume from received_bytes.
    r = client.put(f"/v1/jobs/{jid}/upload", content=data[:100], headers={**h, "Content-Range": f"bytes 0-99/{len(data)}"})
    assert r.status_code == 409
    received = client.get(f"/v1/jobs/{jid}", headers=h).json()["received_bytes"]
    assert received == 5000
    # Completing early is refused.
    assert client.post(f"/v1/jobs/{jid}/upload/complete", headers=h).status_code == 409
    upload(client, h, jid, data, start=received)
    assert client.get(f"/v1/jobs/{jid}", headers=h).json()["received_bytes"] == len(data)


def test_checksum_mismatch_and_corrupt_files_fail_cleanly(client, env):
    h = token(client)
    clip = make_clip(str(env / "c.mp4"))
    data = open(clip, "rb").read()
    jid = client.post("/v1/jobs", json=job_body(clip, sha256="0" * 64), headers=h).json()["id"]
    upload(client, h, jid, data)
    r = client.post(f"/v1/jobs/{jid}/upload/complete", headers=h)
    assert r.status_code == 422 and "Checksum" in r.text
    assert client.get(f"/v1/jobs/{jid}", headers=h).json()["status"] == "FAILED"
    assert not os.listdir(env / "uploads")

    junk = env / "junk.mp4"
    junk.write_bytes(os.urandom(20000))
    jid = client.post("/v1/jobs", json=job_body(str(junk)), headers=h).json()["id"]
    upload(client, h, jid, junk.read_bytes())
    r = client.post(f"/v1/jobs/{jid}/upload/complete", headers=h)
    assert r.status_code == 422 and "readable" in r.text


def test_preview_then_full_with_real_inference(client, env):
    h = token(client)
    clip = make_clip(str(env / "sbs.mp4"), seconds=2.5, fps=10)
    data = open(clip, "rb").read()
    jid = client.post("/v1/jobs", json=job_body(clip), headers=h).json()["id"]
    upload(client, h, jid, data)
    r = client.post(f"/v1/jobs/{jid}/upload/complete", headers=h)
    assert r.status_code == 200, r.text
    j = client.get(f"/v1/jobs/{jid}", headers=h).json()
    assert j["status"] == "PREVIEW_READY", j
    assert j["result"]["model"] == "Real-ESRGAN general v3 compact"
    assert j["result"]["validation"]["ok"]

    # Preview download with HTTP range support.
    r = client.get(f"/v1/jobs/{jid}/output?kind=preview", headers={**h, "Range": "bytes=0-99"})
    assert r.status_code == 206 and len(r.content) == 100
    prev = env / "preview.mp4"
    prev.write_bytes(client.get(f"/v1/jobs/{jid}/output?kind=preview", headers=h).content)
    streams = ffprobe(str(prev))
    v = next(s for s in streams if s["codec_type"] == "video")
    assert (v["width"], v["height"]) == (256, 128)
    assert int(v["nb_read_packets"]) == 25  # whole 2.5 s clip < 10 s preview
    assert any(s["codec_type"] == "audio" for s in streams)

    # Stereo: identical eyes in -> identical eyes out (each eye processed separately).
    frame = subprocess.run(["ffmpeg", "-v", "error", "-i", str(prev), "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                           check=True, capture_output=True).stdout
    img = np.frombuffer(frame, np.uint8).reshape(128, 256, 3).astype(int)
    # The source is lossy H.264, so its halves already differ slightly; the output's eye
    # difference must stay of the same order (no SR-induced divergence between eyes).
    # Exact eye equality for identical inputs is asserted in test_sr.py.
    src_frame = subprocess.run(["ffmpeg", "-v", "error", "-i", clip, "-frames:v", "1", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                               check=True, capture_output=True).stdout
    src = np.frombuffer(src_frame, np.uint8).reshape(64, 128, 3).astype(int)
    src_diff = np.abs(src[:, :64] - src[:, 64:]).mean()
    out_diff = np.abs(img[:, :128] - img[:, 128:]).mean()
    print(f"eye difference: source {src_diff:.2f}, output {out_diff:.2f}")
    assert out_diff < 2 * src_diff + 1.0

    # User accepts the preview -> full processing.
    r = client.post(f"/v1/jobs/{jid}/full", headers=h)
    assert r.status_code == 200
    j = client.get(f"/v1/jobs/{jid}", headers=h).json()
    assert j["status"] == "SUCCEEDED", j
    assert j["output_available"]
    out = env / "full.mp4"
    out.write_bytes(client.get(f"/v1/jobs/{jid}/output", headers=h).content)
    v = next(s for s in ffprobe(str(out)) if s["codec_type"] == "video")
    assert int(v["nb_read_packets"]) == 25 and v["codec_name"] == "hevc"


def test_full_requires_preview_and_cancel_deletes_data(client, env):
    h = token(client)
    clip = make_clip(str(env / "c.mp4"))
    jid = client.post("/v1/jobs", json=job_body(clip), headers=h).json()["id"]
    assert client.post(f"/v1/jobs/{jid}/full", headers=h).status_code == 409
    upload(client, h, jid, open(clip, "rb").read(), chunk=3000, stop=3000)
    r = client.post(f"/v1/jobs/{jid}/cancel", headers=h)
    assert r.json()["status"] == "CANCELLED"
    assert not os.path.exists(env / "uploads" / f"{jid}.part")


def test_delete_and_retention_cleanup(client, env):
    from app import db, tasks
    from app.db import Job
    h = token(client)
    clip = make_clip(str(env / "c.mp4"), seconds=1.0)
    data = open(clip, "rb").read()
    jid = client.post("/v1/jobs", json=job_body(clip, duration_ms=1000), headers=h).json()["id"]
    upload(client, h, jid, data)
    assert client.post(f"/v1/jobs/{jid}/upload/complete", headers=h).status_code == 200
    objects = env / "objects" / "jobs" / jid
    assert sorted(os.listdir(objects)) == ["preview.mp4", "source"]

    # Retention: pretend the job expired.
    with db.session() as s:
        s.get(Job, jid).expires_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(minutes=1)
        s.commit()
    assert tasks.cleanup_expired() == 1
    assert os.listdir(objects) == []
    assert client.get(f"/v1/jobs/{jid}", headers=h).json()["status"] == "EXPIRED"
    assert client.get(f"/v1/jobs/{jid}/output?kind=preview", headers=h).status_code == 404

    # Explicit delete.
    jid2 = client.post("/v1/jobs", json=job_body(clip, duration_ms=1000), headers=h).json()["id"]
    upload(client, h, jid2, data)
    client.post(f"/v1/jobs/{jid2}/upload/complete", headers=h)
    assert client.delete(f"/v1/jobs/{jid2}", headers=h).status_code == 204
    assert os.listdir(env / "objects" / "jobs" / jid2) == []


def test_quote_reports_basis_and_no_fake_price(client):
    h = token(client)
    r = client.post("/v1/quote", json={"width": 1920, "height": 1080, "fps": 30, "duration_ms": 60000, "size_bytes": 10**8}, headers=h)
    assert r.status_code == 200
    q = r.json()
    assert q["estimated_cost"] is None and q["currency"] is None
    assert q["estimated_seconds"] > 0
