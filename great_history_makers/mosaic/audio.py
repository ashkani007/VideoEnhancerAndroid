"""Procedural, royalty-free score and sound effects (100% synthesised here, so there
are no licensing questions), plus narration mixing with music ducking.

The score is a slow drone with a ney-like flute line in a Hijaz-type mode. It is an
evocative modern choice: the actual music of 6th-century BCE Babylon/Persia is not
reconstructable in detail."""
import os
import wave

import numpy as np
from scipy import signal

SR = 48000
MODES = {"hijaz": [0, 1, 4, 5, 7, 8, 10, 12], "phrygian": [0, 1, 3, 5, 7, 8, 10, 12]}


def _env(n, a, r):
    e = np.ones(n, np.float32)
    na, nr = min(n, int(a * SR)), min(n, int(r * SR))
    if na:
        e[:na] = np.linspace(0, 1, na) ** 1.5
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr) ** 1.5
    return e


def _bp(x, lo, hi, order=2):
    sos = signal.butter(order, [lo, hi], btype="band", fs=SR, output="sos")
    return signal.sosfilt(sos, x).astype(np.float32)


def _lp(x, f, order=2):
    return signal.sosfilt(signal.butter(order, f, fs=SR, output="sos"), x).astype(np.float32)


def _place(buf, x, t0, gain=1.0, pan=0.0):
    i = int(t0 * SR)
    if i < 0:
        x, i = x[-i:], 0
    if i >= len(buf) or len(x) == 0:
        return
    x = x[: len(buf) - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    buf[i:i + len(x), 0] += x * gain * l * 1.414
    buf[i:i + len(x), 1] += x * gain * r * 1.414


def drone(D, f0, rng):
    t = np.arange(int(D * SR)) / SR
    out = np.zeros((len(t), 2), np.float32)
    for f, g, pan in [(f0 / 2, 0.5, -0.3), (f0 * 0.75, 0.32, 0.3), (f0, 0.18, 0.0)]:
        vib = 0.003 * np.sin(2 * np.pi * 0.21 * t + rng.uniform(0, 6))
        ph = 2 * np.pi * f * np.cumsum(1 + vib) / SR
        tone = sum(np.sin(k * ph) / k ** 1.3 for k in range(1, 9)).astype(np.float32)
        trem = 0.8 + 0.2 * np.sin(2 * np.pi * 0.13 * t + rng.uniform(0, 6))
        _place(out, _lp(tone * trem, 1400), 0, g, pan)
    return out * _env(len(t), 2.5, 2.0)[:, None]


def ney(f, dur, rng):
    n = int(dur * SR)
    t = np.arange(n) / SR
    vib = 1 + 0.006 * np.sin(2 * np.pi * 5.2 * t) * np.clip(t / 0.5, 0, 1)
    ph = 2 * np.pi * f * np.cumsum(vib) / SR
    tone = np.sin(ph) + 0.25 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph)
    breath = _bp(rng.normal(0, 1, n).astype(np.float32), f * 0.8, min(f * 4, 20000)) * 0.35
    return (tone + breath).astype(np.float32) * _env(n, 0.18, min(0.6, dur * 0.5))


def frame_drum(rng, low=True):
    n = int(0.45 * SR)
    t = np.arange(n) / SR
    f = 55 + 70 * np.exp(-t * 25) if low else 180 + 200 * np.exp(-t * 40)
    body = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * (9 if low else 18))
    slap = _bp(rng.normal(0, 1, n).astype(np.float32), 600, 3500) * np.exp(-t * 60) * 0.3
    return (body + slap).astype(np.float32)


def footstep(rng):
    n = int(0.16 * SR)
    t = np.arange(n) / SR
    x = _bp(rng.normal(0, 1, n).astype(np.float32), 120, 1200) * np.exp(-t * 35)
    return x + 0.6 * np.sin(2 * np.pi * 70 * t).astype(np.float32) * np.exp(-t * 40)


def noise_bed(D, rng, lo, hi, mod_hz, depth, seed_off=0):
    n = int(D * SR)
    x = _bp(rng.normal(0, 1, n).astype(np.float32), lo, hi)
    t = np.arange(n) / SR
    m = 1 - depth + depth * (0.5 + 0.5 * np.sin(2 * np.pi * mod_hz * t + seed_off)) * \
        (0.6 + 0.4 * np.sin(2 * np.pi * mod_hz * 0.37 * t + 1.3 + seed_off))
    return x * m.astype(np.float32)


def sfx(kind, spec, rng, D):
    s, e = spec.get("start", 0.0), spec.get("end", D)
    L = max(0.05, e - s)
    if kind == "wind":
        x = np.stack([noise_bed(L, rng, 150, 900, 0.18, 0.7), noise_bed(L, rng, 150, 900, 0.21, 0.7, 2)], 1)
        return x * _env(len(x), 0.8, 0.8)[:, None] * 0.7, s
    if kind == "crowd":
        layers = [noise_bed(L, rng, 300 + 80 * i, 1500 + 200 * i, 2.5 + i * 0.7, 0.8, i) for i in range(4)]
        x = np.stack([layers[0] + layers[2], layers[1] + layers[3]], 1) * 0.4
        return x * _env(len(x), 1.0, 1.0)[:, None], s
    if kind == "water":
        n = int(L * SR)
        x = np.zeros((n, 2), np.float32)
        t = 0.0
        while t < L - 0.6:
            m = int(rng.uniform(0.25, 0.6) * SR)
            b = _bp(rng.normal(0, 1, m).astype(np.float32), 250, rng.uniform(1200, 2600)) * \
                np.sin(np.linspace(0, np.pi, m)).astype(np.float32) ** 2
            _place(x, b, t, rng.uniform(0.3, 0.7), rng.uniform(-0.6, 0.6))
            t += rng.uniform(0.15, 0.45)
        return x * _env(n, 1.2, 1.0)[:, None], s
    if kind == "march":
        n = int(L * SR)
        x = np.zeros((n, 2), np.float32)
        step = spec.get("period", 1.1) / 2
        t = 0.0
        while t < L:
            for _ in range(5):  # several soldiers, slightly out of step
                _place(x, footstep(rng), t + rng.normal(0, 0.025) + 0.03, rng.uniform(0.2, 0.45),
                       rng.uniform(-0.7, 0.7))
            _place(x, frame_drum(rng), t, 0.5 if int(round(t / step)) % 2 == 0 else 0.0)
            t += step
        return x * _env(n, 0.5, 0.6)[:, None], s
    if kind == "whoosh":
        n = int(1.0 * SR)
        tt = np.linspace(0, 1, n)
        x = rng.normal(0, 1, n).astype(np.float32)
        out = np.zeros(n, np.float32)
        for k in range(10):  # sweeping band
            a, b = int(k * n / 10), int((k + 1) * n / 10)
            fc = 300 + 2500 * np.sin(np.pi * (k + 0.5) / 10)
            out[a:b] = _bp(x, fc * 0.7, fc * 1.4)[a:b]
        out *= (np.sin(np.pi * tt) ** 2).astype(np.float32)
        return np.stack([out, out[::-1] * 0.6 + out * 0.4], 1) * 0.6, s
    if kind == "chime":
        n = int(2.5 * SR)
        t = np.arange(n) / SR
        x = sum(np.sin(2 * np.pi * f * t) * np.exp(-t * d) * g
                for f, d, g in [(587.3, 1.6, 0.6), (880.0, 2.2, 0.35), (1318.5, 3.0, 0.2), (1712.0, 4.0, 0.12)])
        x = x.astype(np.float32) * _env(n, 0.005, 0.3)
        return np.stack([x, x], 1) * 0.5, s
    raise ValueError(kind)


MELODY = [  # (time, scale degree index, duration)
    (1.2, 4, 1.8), (3.2, 3, 0.9), (4.2, 2, 1.0), (5.4, 1, 0.8), (6.3, 0, 2.4),
    (10.6, 4, 1.1), (11.8, 5, 0.9), (12.8, 4, 1.6), (14.6, 3, 0.9), (15.6, 2, 1.0), (16.8, 1, 0.8),
    (17.7, 0, 2.2),
]


def score(cfg, D):
    m = cfg.get("music", {})
    rng = np.random.default_rng(m.get("seed", 1))
    f0 = m.get("root_hz", 146.83)
    mode = MODES[m.get("mode", "hijaz")]
    out = drone(D, f0, rng) * 0.55
    for (t0, deg, dur) in m.get("melody", MELODY):
        if t0 < D:
            f = f0 * 2 * 2 ** (mode[deg] / 12)
            _place(out, ney(f, dur, rng), t0, 0.16, 0.15)
    # soft hand-drum pulse under scenes 2-3 (adds momentum without drama)
    for t in np.arange(5.0, 15.0, 1.1):
        _place(out, frame_drum(rng, low=True), t, 0.09)
    return out


def read_wav(path):
    with wave.open(path, "rb") as w:
        sr, ch, sw = w.getframerate(), w.getnchannels(), w.getsampwidth()
        data = np.frombuffer(w.readframes(w.getnframes()), {2: np.int16, 4: np.int32}[sw])
    x = data.reshape(-1, ch).astype(np.float32) / (32768.0 if sw == 2 else 2147483648.0)
    if ch == 1:
        x = np.repeat(x, 2, 1)
    if sr != SR:
        x = signal.resample_poly(x, SR, sr, axis=0).astype(np.float32)
    return x


def write_wav(path, x):
    x = np.clip(x, -1, 1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype(np.int16).tobytes())


def build_mix(ep_dir, cfg, out_path):
    D = cfg["duration"]
    acfg = cfg.get("audio", {})
    n = int(D * SR)
    mix = np.zeros((n, 2), np.float32)
    music = score(acfg, D)[:n]
    rng = np.random.default_rng(99)
    fx_bus = np.zeros((n, 2), np.float32)
    for spec in acfg.get("sfx", []):
        x, t0 = sfx(spec["type"], spec, rng, D)
        _place(fx_bus, x[:, 0], t0, spec.get("gain", 0.5), -0.3)
        _place(fx_bus, x[:, 1], t0, spec.get("gain", 0.5), 0.3)
    narr_path = os.path.join(ep_dir, acfg.get("narration_file", "audio/narration.wav"))
    has_voice = os.path.exists(narr_path)
    duck = np.ones(n, np.float32)
    if has_voice:
        v = read_wav(narr_path)[:n]
        env = np.abs(v).mean(1)
        env = _lp(env, 4.0, 1)
        duck = (1 - 0.55 * np.clip(env / (env.max() + 1e-6) * 4, 0, 1)).astype(np.float32)
        mix[: len(v)] += v * 1.0
    mix += music * duck[:, None] * 0.9 + fx_bus * (0.75 if has_voice else 1.0)
    fade = _env(n, 0.3, 0.8)
    mix *= fade[:, None]
    peak = np.abs(mix).max()
    if peak > 0:
        mix *= 0.89 / peak
    write_wav(out_path, mix)
    return has_voice
