"""Voiceover: local Kokoro TTS (no per-minute cost), one take per sentence,
with word timings estimated from the synthesized audio itself.

Kokoro-onnx does not expose alignments, so word times are derived by
splitting each sentence's audio at its internal pauses (commas, dashes) and
distributing words across the voiced spans by syllable weight. Accuracy is
typically within ~0.1-0.2 s per word, which is enough for 2-4 word captions.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import numpy as np

from .util import Cache, Config, run

SR = 24000


def _syllables(word: str) -> int:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return 1
    groups = re.findall(r"[aeiouy]+", w)
    n = len(groups)
    if w.endswith("e") and n > 1 and not w.endswith(("le", "ee")):
        n -= 1
    return max(1, n)


def ensure_models(cfg: Config) -> tuple[Path, Path]:
    model = cfg.models_dir / cfg.get("voice.model")
    voices = cfg.models_dir / cfg.get("voice.voices")
    base = cfg.get("voice.model_url")
    for p in (model, voices):
        if not p.exists():
            run(["curl", "-sSL", "--fail", "-o", str(p), base + p.name])
    return model, voices


class Voice:
    def __init__(self, cfg: Config, voice: str | None = None, speed: float | None = None):
        from kokoro_onnx import Kokoro  # lazy: heavy import

        model, voices = ensure_models(cfg)
        self.k = Kokoro(str(model), str(voices))
        self.voice = voice or cfg.get("voice.voice")
        self.speed = speed or cfg.get("voice.speed", 1.0)
        self.cache = Cache(cfg.cache_dir)
        self.audio_dir = cfg.cache_dir / "tts"
        self.audio_dir.mkdir(parents=True, exist_ok=True)

    def say(self, text: str, speed: float | None = None) -> tuple[Path, np.ndarray]:
        import soundfile as sf

        speed = speed or self.speed
        key = f"{self.voice}|{speed}|{text}"
        p = self.audio_dir / (hashlib.sha1(key.encode()).hexdigest()[:20] + ".wav")
        if not p.exists():
            audio, sr = self.k.create(text, voice=self.voice, speed=speed, lang="en-us")
            assert sr == SR
            sf.write(p, _trim(audio), SR)
        audio, _ = sf.read(p, dtype="float32")
        return p, audio


def _trim(a: np.ndarray, thr: float = 0.01, pad: float = 0.03) -> np.ndarray:
    idx = np.where(np.abs(a) > thr)[0]
    if len(idx) == 0:
        return a
    s = max(0, idx[0] - int(pad * SR))
    e = min(len(a), idx[-1] + int(pad * SR))
    return a[s:e]


def voiced_spans(a: np.ndarray, min_gap: float = 0.12) -> list[tuple[float, float]]:
    hop = int(0.01 * SR)
    env = np.array([np.sqrt(np.mean(a[i:i + hop] ** 2)) for i in range(0, len(a) - hop, hop)])
    on = env > max(0.012, env.max() * 0.06)
    spans, start, gap = [], None, 0
    for i, v in enumerate(on):
        if v:
            if start is None:
                start = i
            gap = 0
        elif start is not None:
            gap += 1
            if gap * 0.01 >= min_gap:
                spans.append((start * 0.01, (i - gap + 1) * 0.01))
                start, gap = None, 0
    if start is not None:
        spans.append((start * 0.01, len(on) * 0.01))
    return spans or [(0.0, len(a) / SR)]


def word_timings(text: str, a: np.ndarray) -> list[dict]:
    """Assign each word a [start, end] within the sentence audio."""
    words = text.split()
    spans = voiced_spans(a)
    # split words into phrases at punctuation so phrases can map to spans
    phrases, cur = [], []
    for w in words:
        cur.append(w)
        if re.search(r"[,;:—.!?]$", w) or w in ("—", "-"):
            phrases.append(cur)
            cur = []
    if cur:
        phrases.append(cur)
    # merge/split so number of phrases == number of spans when possible
    if len(phrases) != len(spans):
        spans = [(spans[0][0], spans[-1][1])]
        phrases = [words]
    out = []
    for ph, (s0, s1) in zip(phrases, spans):
        weights = np.array([_syllables(w) + 0.6 for w in ph], dtype=float)
        edges = s0 + (s1 - s0) * np.concatenate([[0], np.cumsum(weights) / weights.sum()])
        for w, a0, a1 in zip(ph, edges[:-1], edges[1:]):
            out.append({"word": w, "start": round(float(a0), 3), "end": round(float(a1), 3)})
    return out
