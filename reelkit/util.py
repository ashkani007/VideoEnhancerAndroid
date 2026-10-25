"""Shared helpers: config, content-addressed cache, subprocess wrappers."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

PKG_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = PKG_DIR / "config.toml"


@dataclass
class Config:
    workspace: Path
    cache_dir: Path
    sources_dir: Path
    models_dir: Path
    productions_dir: Path
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, dotted: str, default: Any = None) -> Any:
        node: Any = self.raw
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node


def load_config(path: str | os.PathLike | None = None) -> Config:
    path = Path(path or os.environ.get("REELKIT_CONFIG", DEFAULT_CONFIG))
    raw = tomllib.loads(path.read_text())
    ws = Path(os.environ.get("REELKIT_WORKSPACE", raw["paths"]["workspace"])).expanduser()
    cfg = Config(
        workspace=ws,
        cache_dir=ws / "cache",
        sources_dir=ws / "sources",
        models_dir=ws / "models",
        productions_dir=ws / "productions",
        raw=raw,
    )
    for d in (cfg.cache_dir, cfg.sources_dir, cfg.models_dir, cfg.productions_dir):
        d.mkdir(parents=True, exist_ok=True)
    return cfg


# --------------------------------------------------------------------------- cache


class Cache:
    """Tiny JSON cache keyed by (namespace, key). Survives across productions so
    search results and footage analysis are paid for once per source."""

    def __init__(self, root: Path):
        self.root = root

    def _path(self, ns: str, key: str) -> Path:
        digest = hashlib.sha1(key.encode()).hexdigest()[:20]
        return self.root / ns / f"{digest}.json"

    def get(self, ns: str, key: str) -> Any | None:
        p = self._path(ns, key)
        if p.exists():
            return json.loads(p.read_text())["value"]
        return None

    def put(self, ns: str, key: str, value: Any) -> Any:
        p = self._path(ns, key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps({"key": key, "value": value}, indent=1, default=float))
        return value


def sha256_file(path: Path, chunk: int = 1 << 20) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while b := f.read(chunk):
            h.update(b)
    return h.hexdigest()


# --------------------------------------------------------------------------- processes


def run(cmd: list[str], *, capture: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    proc = subprocess.run(cmd, capture_output=capture, text=True)
    if check and proc.returncode != 0:
        tail = (proc.stderr or "")[-3000:]
        raise RuntimeError(f"command failed ({proc.returncode}): {' '.join(cmd[:6])} ...\n{tail}")
    return proc


def ffprobe(path: Path) -> dict:
    out = run(["ffprobe", "-v", "error", "-show_format", "-show_streams", "-of", "json", str(path)]).stdout
    return json.loads(out)


def media_duration(path: Path) -> float:
    return float(ffprobe(path)["format"]["duration"])


def detect_video_encoder(prefer_gpu: bool = True) -> dict:
    """Pick NVENC when an NVIDIA GPU is actually usable (RTX 4060 on the
    production box), else libx264. Probes with a 1-frame encode because ffmpeg
    builds often list h264_nvenc even when no GPU/driver is present."""
    if prefer_gpu and shutil.which("nvidia-smi"):
        probe = subprocess.run(
            ["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=256x256:d=0.1",
             "-c:v", "h264_nvenc", "-f", "null", "-"],
            capture_output=True, text=True,
        )
        if probe.returncode == 0:
            return {"name": "h264_nvenc", "gpu": True,
                    "args": lambda crf: ["-c:v", "h264_nvenc", "-preset", "p5", "-tune", "hq",
                                         "-rc", "vbr", "-cq", str(crf), "-b:v", "0"]}
    return {"name": "libx264", "gpu": False,
            "args": lambda crf: ["-c:v", "libx264", "-preset", "medium", "-crf", str(crf)]}


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=float))


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text())
