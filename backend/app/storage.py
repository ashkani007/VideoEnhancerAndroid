"""Object storage for sources and outputs. Credentials stay on the server; clients only ever
talk to the API, which streams files after checking the job owner."""
from __future__ import annotations

import os
import shutil
from typing import BinaryIO, Iterator, Protocol

from .config import Settings, get_settings


class Storage(Protocol):
    def put_file(self, key: str, path: str) -> None: ...
    def get_file(self, key: str, path: str) -> None: ...
    def size(self, key: str) -> int: ...
    def stream(self, key: str, start: int = 0, end: int | None = None, chunk: int = 1 << 20) -> Iterator[bytes]: ...
    def delete(self, key: str) -> None: ...
    def exists(self, key: str) -> bool: ...


class LocalStorage:
    def __init__(self, root: str):
        self.root = os.path.abspath(root)
        os.makedirs(self.root, exist_ok=True)

    def _path(self, key: str) -> str:
        p = os.path.abspath(os.path.join(self.root, key))
        if not p.startswith(self.root + os.sep):
            raise ValueError("invalid key")
        return p

    def put_file(self, key: str, path: str) -> None:
        dst = self._path(key)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copyfile(path, dst)

    def get_file(self, key: str, path: str) -> None:
        shutil.copyfile(self._path(key), path)

    def size(self, key: str) -> int:
        return os.path.getsize(self._path(key))

    def stream(self, key, start=0, end=None, chunk=1 << 20):
        with open(self._path(key), "rb") as f:
            f.seek(start)
            remaining = None if end is None else end - start + 1
            while remaining is None or remaining > 0:
                data = f.read(chunk if remaining is None else min(chunk, remaining))
                if not data:
                    return
                if remaining is not None:
                    remaining -= len(data)
                yield data

    def delete(self, key: str) -> None:
        try:
            os.remove(self._path(key))
        except FileNotFoundError:
            pass

    def exists(self, key: str) -> bool:
        return os.path.exists(self._path(key))


class S3Storage:
    def __init__(self, s: Settings):
        import boto3

        self.bucket = s.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=s.s3_endpoint_url,
            region_name=s.s3_region,
            aws_access_key_id=s.s3_access_key_id.get_secret_value() if s.s3_access_key_id else None,
            aws_secret_access_key=s.s3_secret_access_key.get_secret_value() if s.s3_secret_access_key else None,
        )

    def put_file(self, key, path):
        self.client.upload_file(path, self.bucket, key)

    def get_file(self, key, path):
        self.client.download_file(self.bucket, key, path)

    def size(self, key):
        return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])

    def stream(self, key, start=0, end=None, chunk=1 << 20):
        rng = f"bytes={start}-" + ("" if end is None else str(end))
        body: BinaryIO = self.client.get_object(Bucket=self.bucket, Key=key, Range=rng)["Body"]
        while data := body.read(chunk):
            yield data

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def exists(self, key):
        try:
            self.client.head_object(Bucket=self.bucket, Key=key)
            return True
        except Exception:
            return False


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        s = get_settings()
        _storage = S3Storage(s) if s.storage_backend == "s3" else LocalStorage(s.local_storage_dir)
    return _storage


def reset_for_tests() -> None:
    global _storage
    _storage = None
