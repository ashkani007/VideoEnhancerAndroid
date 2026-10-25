"""ReelKit's own cinematic underscore.

The narration's emotional arc (one `mood` per sentence, written with the
script) becomes a cue sheet; each cue is composed from a small palette of
synthesised instruments and placed so that musical changes land on the story
moments that cause them. Everything is generated here with numpy, so the
score is original work with no licence to track and no per-use cost.

Moods: mystery, tender, wonder, tension, journey, dread, action, silence,
grief. Key: D minor throughout so cues crossfade without clashing.
"""

from __future__ import annotations

import numpy as np

SR = 48000
RNG = np.random.default_rng(11)


def hz(m: float) -> float:
    return 440.0 * 2 ** ((m - 69) / 12)


def _t(d: float) -> np.ndarray:
    return np.arange(int(d * SR)) / SR


def _env(n: int, a: float, r: float, curve: float = 1.0) -> np.ndarray:
    e = np.ones(n)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, 1, na) ** curve
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** curve
    return e


def _lowpass(x: np.ndarray, fc: float, order: float = 2.0) -> np.ndarray:
    X = np.fft.rfft(x, axis=0)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    g = 1 / np.sqrt(1 + (f / fc) ** (2 * order))
    return np.fft.irfft(X * (g[:, None] if x.ndim == 2 else g), n=len(x), axis=0)


def _bandpass(x, lo, hi):
    X = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR)
    X[(f < lo) | (f > hi)] *= 0.02
    return np.fft.irfft(X, n=len(x))


# ------------------------------------------------------------------ instruments


def pad(notes, d, bright=0.5, a=1.4, r=1.6):
    t = _t(d)
    out = np.zeros((len(t), 2))
    for i, m in enumerate(notes):
        for k, det in enumerate((-0.07, 0.0, 0.07)):
            f = hz(m + det)
            v = np.zeros_like(t)
            for h in range(1, 13):
                if f * h > 9000:
                    break
                v += np.sin(2 * np.pi * f * h * t + RNG.uniform(0, 6.28)) / h ** (1.9 - bright)
            pan = 0.5 + 0.35 * ((i + k) % 3 - 1) / 1
            out[:, 0] += v * (1 - pan)
            out[:, 1] += v * pan
    out *= _env(len(t), a, r, 1.5)[:, None]
    out = _lowpass(out, 900 + 2200 * bright)
    return out / (len(notes) * 3)


def piano(m, d=2.5, vel=1.0):
    t = _t(d)
    f0 = hz(m)
    v = np.zeros_like(t)
    for k in range(1, 9):
        fk = f0 * k * np.sqrt(1 + 0.0004 * k * k)
        if fk > 12000:
            break
        v += np.sin(2 * np.pi * fk * t) * np.exp(-t * (0.9 + 0.7 * k)) / k ** 1.4
    v *= _env(len(t), 0.004, 0.25)
    click = RNG.standard_normal(len(t)) * np.exp(-t * 300) * 0.02
    v = (v + click) * vel
    return np.stack([v, v], 1) * 0.5


def pluck(m, d=0.45, vel=1.0):
    t = _t(d)
    f0 = hz(m)
    v = np.zeros_like(t)
    for k in range(1, 10):
        v += np.sin(2 * np.pi * f0 * k * t) * np.exp(-t * (4 + 3.5 * k)) / k
    v *= _env(len(t), 0.003, 0.06) * vel
    return np.stack([v, v], 1) * 0.6


def drone(m, d):
    t = _t(d)
    f = hz(m)
    lfo = 0.75 + 0.25 * np.sin(2 * np.pi * 0.11 * t)
    v = (np.sin(2 * np.pi * f * t) + 0.35 * np.sin(2 * np.pi * 2 * f * t + 1)
         + 0.15 * np.sin(2 * np.pi * 3.01 * f * t)) * lfo
    air = _bandpass(RNG.standard_normal(len(t)), 200, 900) * 0.05
    v = (v + air) * _env(len(t), 2.0, 2.0)
    return np.stack([v, v * 0.97], 1) * 0.5


def shimmer(notes, d):
    t = _t(d)
    out = np.zeros((len(t), 2))
    for i, m in enumerate(notes):
        trem = 0.6 + 0.4 * np.sin(2 * np.pi * (4.5 + i) * t + i)
        v = np.sin(2 * np.pi * hz(m) * t) * trem
        out[:, i % 2] += v
        out[:, (i + 1) % 2] += v * 0.4
    return out * _env(len(t), 2.5, 2.0)[:, None] * 0.12


def tom(d=1.0, f0=95, vel=1.0):
    t = _t(d)
    f = f0 * (0.62 + 0.38 * np.exp(-t * 18))
    v = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 5)
    v += _lowpass(RNG.standard_normal(len(t)), 900) * np.exp(-t * 40) * 0.6
    return np.stack([v, v], 1) * 0.7 * vel


def heartbeat(d=1.0):
    t = _t(d)
    beat = lambda s: np.sin(2 * np.pi * 52 * (t - s)) * np.exp(-np.clip(t - s, 0, None) * 22) * (t >= s)
    v = beat(0.0) + 0.7 * beat(0.28)
    return np.stack([v, v], 1) * 0.8


def braam(m=26, d=3.5):
    t = _t(d)
    v = np.zeros_like(t)
    for mm, g in ((m, 1.0), (m + 12, 0.6), (m + 19, 0.35)):
        f = hz(mm)
        for h in range(1, 18):
            v += g * np.sin(2 * np.pi * f * h * t * (1 + 0.002 * h)) / h
    v = _lowpass(v, 700) * np.exp(-t * 1.1) * _env(len(t), 0.02, 0.8)
    sub = np.sin(2 * np.pi * 36 * t) * np.exp(-t * 2.2)
    v = v / (np.abs(v).max() + 1e-9) + 0.8 * sub
    return np.stack([v, v], 1) * 0.6


def riser(d=2.0):
    t = _t(d)
    n = RNG.standard_normal(len(t))
    v = np.zeros_like(t)
    seg = int(0.1 * SR)
    for i in range(0, len(t), seg):          # stepped band sweep 300 Hz -> 4 kHz
        fr = 300 * (4000 / 300) ** (i / len(t))
        v[i:i + seg] = _bandpass(n[i:i + seg], fr * 0.8, fr * 1.25)
    v *= (t / d) ** 2
    return np.stack([v, v], 1) * 0.5


def _add(buf, x, at):
    s = int(at * SR)
    if s >= len(buf):
        return
    x = x[: len(buf) - s]
    buf[s:s + len(x)] += x


# ------------------------------------------------------------------ cues

D = 50  # D3
PROG_TENDER = [[46, 53, 57, 62], [41, 48, 57, 60], [48, 55, 60, 64], [50, 57, 60, 65]]   # Bb F C Dm
PROG_GRIEF = [[43, 50, 55, 58], [38, 50, 53, 57], [46, 50, 53, 58], [45, 52, 57, 61]]    # Gm Dm Bb A
PROG_JOURNEY = [[38, 50, 53, 57], [34, 46, 53, 58], [41, 48, 57, 60], [36, 48, 55, 60]]  # Dm Bb F C


def cue(mood: str, d: float, intensity: float = 1.0) -> np.ndarray:
    buf = np.zeros((int(d * SR), 2))
    if mood == "silence":
        return buf
    if mood == "mystery":
        _add(buf, drone(26, d), 0)
        _add(buf, shimmer([86, 88], d) * 0.8, 0.3)
        for i, m in enumerate([62, 69, 65]):
            _add(buf, piano(m, 3.0, 0.35), 0.6 + i * 2.2)
    elif mood in ("tender", "wonder"):
        bar = 60 / 72 * 4
        bright = 0.75 if mood == "wonder" else 0.45
        for b in range(int(np.ceil(d / bar))):
            ch = PROG_TENDER[b % 4]
            _add(buf, pad(ch, bar + 1.6, bright) * 0.9, b * bar)
            arp = [ch[1] + 12, ch[2] + 12, ch[3] + 12, ch[2] + 12]
            for j in range(8):
                _add(buf, piano(arp[j % 4], 1.6, 0.28 + 0.1 * (j % 4 == 0)), b * bar + j * bar / 8)
        if mood == "wonder":
            _add(buf, shimmer([81, 86], d) * 0.7, 0)
    elif mood == "tension":
        eighth = 60 / 96 / 2
        _add(buf, pad([38, 50, 51], d, 0.3, a=0.6) * 1.1, 0)
        for j in range(int(d / eighth)):
            acc = 1.0 if j % 4 == 0 else 0.6
            _add(buf, pluck(38 + (12 if j % 8 == 7 else 0), 0.35, acc * (0.5 + 0.5 * j * eighth / d)), j * eighth)
        _add(buf, riser(min(2.5, d)) * 0.25, max(0, d - 2.5))
    elif mood == "journey":
        beat = 60 / 96
        bar = beat * 4
        pattern = [38, 38, 45, 38, 41, 38, 45, 50]
        for b in range(int(np.ceil(d / bar))):
            ch = PROG_JOURNEY[b % 4]
            _add(buf, pad([c + 12 for c in ch[1:]], bar + 1.2, 0.55, a=0.4) * 0.8, b * bar)
            for j in range(8):
                _add(buf, pluck(pattern[j] + (ch[0] - 38), 0.4, 0.7 + 0.3 * (j == 0)), b * bar + j * beat / 2)
            ramp = min(1.0, 0.4 + 0.6 * b * bar / max(d, 1e-3))
            _add(buf, tom(1.0, 92, 0.8 * ramp), b * bar)
            _add(buf, tom(1.0, 120, 0.5 * ramp), b * bar + 2 * beat)
            _add(buf, tom(0.6, 140, 0.35 * ramp), b * bar + 3.5 * beat)
    elif mood == "dread":
        _add(buf, drone(26, d) * 1.1, 0)
        _add(buf, shimmer([87, 86], d) * 0.6, 0.5)
        for k in range(int(d / 1.0)):
            _add(buf, heartbeat(1.0) * (0.5 + 0.5 * k / max(1, d)), 0.4 + k * 1.0)
    elif mood == "action":
        s16 = 60 / 120 / 4
        _add(buf, pad([38, 50, 53, 57], d, 0.5, a=0.2) * 0.9, 0)
        for j in range(int(d / s16)):
            _add(buf, pluck(50 if j % 4 else 38, 0.2, 0.55 + 0.45 * (j % 4 == 0)), j * s16)
        for j in range(int(d / (s16 * 4))):
            _add(buf, tom(0.8, 100 if j % 2 == 0 else 130, 0.9), j * s16 * 4)
    elif mood == "grief":
        bar = 60 / 60 * 4
        mel = [69, 65, 64, 62, 65, 64, 62, 61]
        for b in range(int(np.ceil(d / bar))):
            _add(buf, pad(PROG_GRIEF[b % 4], bar + 2.0, 0.35, a=1.8, r=2.0) * 0.9, b * bar)
            for j in range(2):
                _add(buf, piano(mel[(2 * b + j) % len(mel)], 3.5, 0.45), b * bar + j * bar / 2 + 0.2)
    # level each mood to its own loudness target so cues sit consistently
    act = buf[np.abs(buf).max(1) > 1e-4]
    if len(act):
        rms = np.sqrt((act ** 2).mean())
        buf *= 10 ** (MOOD_DB.get(mood, -20) / 20) / (rms + 1e-9)
    return buf * intensity


MOOD_DB = {"mystery": -21, "tender": -22, "wonder": -21, "tension": -19, "journey": -18,
           "dread": -20, "action": -17, "grief": -21}


def reverb(x: np.ndarray, seconds: float = 2.8, wet: float = 0.32) -> np.ndarray:
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = np.stack([_lowpass(RNG.standard_normal(n), 5000) * np.exp(-t * 6.9 / seconds) for _ in range(2)], 1)
    ir[: int(0.02 * SR)] = 0
    ir /= np.sqrt((ir ** 2).sum(0))
    size = 1 << (len(x) + n - 1).bit_length()
    y = np.fft.irfft(np.fft.rfft(x, size, axis=0) * np.fft.rfft(ir, size, axis=0), size, axis=0)[: len(x)]
    return (1 - wet) * x + wet * y * 3


def compose(cues: list[dict], total: float, hits: list[float]) -> np.ndarray:
    """cues: [{"mood", "start", "end"}] in seconds. Equal-power crossfades
    (1.2 s, 0.5 s into silence) at every boundary; hits are braams."""
    out = np.zeros((int((total + 3) * SR), 2))
    for i, c in enumerate(cues):
        nxt = cues[i + 1]["mood"] if i + 1 < len(cues) else None
        xf_in = 0.5 if c["mood"] == "silence" or (i and cues[i - 1]["mood"] == "silence") else 1.2
        xf_out = 0.5 if nxt == "silence" or c["mood"] == "silence" else 1.2
        start = max(0.0, c["start"] - xf_in / 2)
        d = (c["end"] + (xf_out / 2 if nxt else 2.5)) - start
        x = cue(c["mood"], d, c.get("intensity", 1.0))
        e = np.ones(len(x))
        ni, no = int(xf_in * SR), int(xf_out * SR if nxt else 2.5 * SR)
        if i and ni:
            e[:ni] = np.sin(np.linspace(0, np.pi / 2, ni))
        e[-no:] *= np.cos(np.linspace(0, np.pi / 2, no))
        _add(out, x * e[:, None], start)
    for h in hits:
        _add(out, braam(26, 3.5) * 0.55, max(0, h - 0.03))
    out = reverb(out)
    out = out[: int(total * SR)]
    return (out / (np.abs(out).max() + 1e-9) * 0.7).astype(np.float32)
