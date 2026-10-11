"""Media storage abstraction. Local filesystem for development, S3-compatible for production.
Images are re-encoded server-side, which strips EXIF metadata (including GPS)."""
import io
import os
import time
import uuid
from urllib.parse import quote

from PIL import Image, ImageOps

from app.config import get_settings
from app.errors import AppError, bad_request
from app.security import sign_media

MAX_BYTES = 8 * 1024 * 1024
MAX_DIM = 1600
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}


def sanitize_image(data: bytes) -> bytes:
    if len(data) > MAX_BYTES:
        raise bad_request("too_large", "Photos must be 8 MB or smaller")
    try:
        img = Image.open(io.BytesIO(data))
        if img.format not in ALLOWED_FORMATS:
            raise bad_request("unsupported_format", "Use JPEG, PNG or WebP")
        img = ImageOps.exif_transpose(img).convert("RGB")
    except AppError:
        raise
    except Exception:
        raise bad_request("invalid_image", "That file is not a valid image")
    img.thumbnail((MAX_DIM, MAX_DIM))
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=86, optimize=True)  # fresh encode: no EXIF/GPS
    return out.getvalue()


class Storage:
    def put(self, key: str, data: bytes, content_type: str) -> None:
        raise NotImplementedError

    def get(self, key: str) -> bytes | None:
        raise NotImplementedError

    def delete(self, key: str) -> None:
        raise NotImplementedError

    def url(self, key: str, ttl: int = 3600) -> str:
        raise NotImplementedError


class LocalStorage(Storage):
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key: str) -> str:
        p = os.path.abspath(os.path.join(self.root, key))
        if not p.startswith(self.root + os.sep):
            raise ValueError("invalid key")
        return p

    def put(self, key, data, content_type):
        p = self._path(key)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(data)

    def get(self, key):
        try:
            with open(self._path(key), "rb") as f:
                return f.read()
        except (FileNotFoundError, ValueError):
            return None

    def delete(self, key):
        try:
            os.remove(self._path(key))
        except (FileNotFoundError, ValueError):
            pass

    def url(self, key, ttl=3600):
        exp = int(time.time()) + ttl
        exp -= exp % 600  # stable URLs for 10 min windows so clients can cache
        exp += 600
        base = get_settings().public_base_url.rstrip("/")
        return f"{base}/media/{quote(key)}?exp={exp}&sig={sign_media(key, exp)}"


class S3Storage(Storage):  # pragma: no cover - requires S3 credentials
    def __init__(self):
        import boto3  # optional dependency

        s = get_settings()
        self.bucket = s.s3_bucket
        self.client = boto3.client("s3", endpoint_url=s.s3_endpoint_url)

    def put(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key):
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def url(self, key, ttl=3600):
        return self.client.generate_presigned_url("get_object", Params={"Bucket": self.bucket, "Key": key}, ExpiresIn=ttl)


_storage: Storage | None = None


def storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage() if s.storage_backend == "s3" else LocalStorage(s.local_media_dir)
    return _storage


def new_photo_key(user_id: uuid.UUID) -> str:
    return f"photos/{user_id}/{uuid.uuid4().hex}.jpg"
