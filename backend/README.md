# VRVision processing backend

FastAPI API + Celery worker that runs the same Real-ESRGAN model as the app (see
`../docs/MODELS.md`). **No hosted instance exists**; you run it yourself. Nothing here is free
or deployed by this project.

## Run locally (development)

```bash
cd backend
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt          # needs ffmpeg/ffprobe on PATH
python -m pytest -q                          # 28 tests, incl. real inference end to end

export VRV_API_KEYS=dev-key VRV_TOKEN_SECRET=$(python -c "import secrets;print(secrets.token_urlsafe(48))")
uvicorn app.main:app --reload                # API on :8000, SQLite + local file storage
celery -A app.tasks worker --concurrency=1   # needs Redis (VRV_REDIS_URL)
```

## Docker Compose (API, CPU worker, scheduler, PostgreSQL, Redis, MinIO)

```bash
cp .env.example .env    # set every secret
docker compose up --build
```

GPU worker (NVIDIA Container Toolkit required; PyTorch + original checkpoints, downloaded and
SHA-256-checked at build time):

```bash
docker compose -f docker-compose.yml -f docker-compose.gpu.yml up --build
```

Status: the API image is built and smoke-tested in CI and the compose files are validated; the
complete stack and the GPU image have not been run by the author.

## Production checklist

- Terminate TLS in a reverse proxy (Caddy, nginx, Traefik) and set `VRV_REQUIRE_HTTPS=true`.
- Generate a unique API key per user/device; rotate `VRV_TOKEN_SECRET` to revoke all tokens.
- Use managed PostgreSQL and S3-compatible storage with server-side encryption and a bucket
  lifecycle rule as a backstop for the retention policy.
- Set `VRV_THROUGHPUT_MP_PER_S` from a measurement on your worker; only set
  `VRV_PRICE_PER_GPU_MINUTE` if you actually charge.
- Run `celery beat` (retention cleanup every 15 minutes).

## API (v1)

All endpoints except `/v1/health` and `/v1/auth/token` need `Authorization: Bearer <token>`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/v1/health` | Status, engine, consent text version, retention hours |
| POST | `/v1/auth/token` | `X-API-Key` → 15-minute HS256 token |
| POST | `/v1/quote` | Time (and price, if configured) estimate from metadata only |
| POST | `/v1/jobs` | Create a job. Requires `consent: {granted: true, text_version, granted_at}`; validates layout, size, duration, output scale (1–4×) and active-job quota |
| PUT | `/v1/jobs/{id}/upload` | Append a chunk; `Content-Range: bytes start-end/total` must start at the server's `received_bytes` |
| POST | `/v1/jobs/{id}/upload/complete` | SHA-256 check, ffprobe validation, store, queue the 10-second preview |
| GET | `/v1/jobs/{id}` | Status, progress, stage, error, `received_bytes`, result (model, timings, validation) |
| POST | `/v1/jobs/{id}/full` | Start full processing after the user accepted the preview |
| POST | `/v1/jobs/{id}/cancel` | Cancel; data deleted |
| DELETE | `/v1/jobs/{id}` | Delete source, preview and output now |
| GET | `/v1/jobs/{id}/output?kind=preview\|full` | Download (HTTP Range supported) |

Jobs are visible only to the API key that created them (others get 404).

## Retention policy

| Data | Deleted |
|---|---|
| Incomplete upload | `VRV_UPLOAD_EXPIRY_HOURS` (default 6 h) after job creation |
| Source, preview, output | `VRV_RETENTION_HOURS` (default 24 h) after upload completion / job end |
| Anything | Immediately on `DELETE /v1/jobs/{id}`, on cancel, or when the app's *delete after download* option is on (default) |
| Failed uploads (checksum/format) | Immediately |

Job rows (metadata, consent timestamp and text version, status) remain for auditing; their
file references are cleared.

## Processing details

FFmpeg decodes frames in coded orientation (`-noautorotate`) as RGB24; each frame is upscaled
per eye with tiled inference (same contract as the app); FFmpeg encodes HEVC (`libx265`, CRF
`VRV_ENCODE_CRF`, preset `VRV_ENCODE_PRESET`) at the source's average frame rate with the
source's display rotation, BT.709 tags, and the source audio (AAC copied, otherwise re-encoded
to AAC). Optional sharpening is FFmpeg's conventional `unsharp` filter on luma. The output is
validated with ffprobe (resolution, frame count, audio) before it is made available.
