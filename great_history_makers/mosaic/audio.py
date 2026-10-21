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
    if kind == "fire":
        n = int(L * SR)
        x = np.stack([noise_bed(L, rng, 80, 700, 1.3, 0.5), noise_bed(L, rng, 80, 700, 1.7, 0.5, 1)], 1) * 0.5
        for _ in range(int(L * 9)):  # crackles
            c = int(rng.uniform(0, max(1, n - 800)))
            m = int(rng.uniform(80, 500))
            x[c:c + m] += (_bp(rng.normal(0, 1, m).astype(np.float32), 1500, 6000) * np.exp(-np.linspace(0, 6, m)))[:, None] * rng.uniform(0.3, 0.9)
        return x * _env(n, 0.3, 0.4)[:, None], s
    if kind == "flutter":
        n = int(L * SR)
        tt = np.arange(n) / SR
        m = (0.5 + 0.5 * np.sin(2 * np.pi * 5.5 * tt) * np.sin(2 * np.pi * 0.7 * tt)) ** 2
        x = _bp(rng.normal(0, 1, n).astype(np.float32), 300, 2400) * m.astype(np.float32) * 0.5
        return np.stack([x, x[::-1]], 1) * _env(n, 0.4, 0.4)[:, None], s
    if kind == "hooves":
        n = int(L * SR)
        x = np.zeros((n, 2), np.float32)
        t = 0.0
        while t < L:
            for k in range(3):
                _place(x, footstep(rng) * 0.8, t + k * 0.09 + rng.normal(0, 0.01), rng.uniform(0.3, 0.6), rng.uniform(-0.5, 0.5))
            t += 0.6
        return x * _env(n, 0.3, 0.4)[:, None], s
    if kind in ("taps", "stylus"):
        n = int(L * SR)
        x = np.zeros((n, 2), np.float32)
        per = spec.get("period", 0.9)
        t = spec.get("offset", 0.0)
        while t < L:
            m = int((0.07 if kind == "taps" else 0.12) * SR)
            tt = np.arange(m) / SR
            if kind == "taps":
                hit = (np.sin(2 * np.pi * 1900 * tt) * 0.5 + _bp(rng.normal(0, 1, m).astype(np.float32), 800, 5000)) * np.exp(-tt * 70)
            else:
                hit = _bp(rng.normal(0, 1, m).astype(np.float32), 2500, 9000) * np.sin(np.pi * tt / tt[-1]) * 0.6
            _place(x, hit.astype(np.float32), t, 0.8, -0.2)
            t += per
        return x, s
    if kind == "clink":
        n = int(L * SR)
        x = np.zeros((n, 2), np.float32)
        for _ in range(spec.get("count", 20)):
            m = int(0.25 * SR)
            tt = np.arange(m) / SR
            f = rng.uniform(2200, 4200)
            hit = (np.sin(2 * np.pi * f * tt) + 0.5 * np.sin(2 * np.pi * f * 1.51 * tt)) * np.exp(-tt * rng.uniform(18, 30))
            _place(x, hit.astype(np.float32), rng.uniform(0, L - 0.25), rng.uniform(0.2, 0.6), rng.uniform(-0.8, 0.8))
        return x, s
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
    # soft hand-drum pulse under the campaign section (momentum without drama)
    for t in np.arange(m.get("drum_from", 5.0), m.get("drum_to", 15.0), 1.1):
        _place(out, frame_drum(rng, low=True), t, 0.09)
    return out * m.get("gain", 1.0) / 0.5 if "gain" in m else out


def read_audio(path):
    """Any format FFmpeg reads (mp3, wav, m4a) -> float32 stereo at SR. Content untouched."""
    import subprocess
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "2", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).reshape(-1, 2).copy()


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


def _rms_db(x):
    return 20 * np.log10(np.sqrt(np.mean(np.square(x))) + 1e-9)


def build_mix(ep_dir, cfg, out_path):
    """Stem-levelled mix. The narration is the reference and is never edited (no cuts,
    no time-stretch, only one overall gain). Music and SFX are levelled relative to it:
    the bed sits `bed_under_voice_db` below the voice while words are spoken and rises
    to `bed_in_pauses_db` below it in pauses, with smooth 150 ms ramps."""
    D = cfg["duration"]
    acfg = cfg.get("audio", {})
    n = int(D * SR)
    music = score(acfg, D)[:n]
    rng = np.random.default_rng(99)
    fx_bus = np.zeros((n, 2), np.float32)
    for spec in acfg.get("sfx", []):
        x, t0 = sfx(spec["type"], spec, rng, D)
        _place(fx_bus, x[:, 0], t0, spec.get("gain", 0.5), -0.3)
        _place(fx_bus, x[:, 1], t0, spec.get("gain", 0.5), 0.3)
    narr_path = os.path.join(ep_dir, acfg.get("narration_file", "audio/narration.wav"))
    has_voice = os.path.exists(narr_path)
    bed = music * acfg.get("music_level", 1.0) + fx_bus * acfg.get("sfx_level", 0.8)
    mix = np.zeros((n, 2), np.float32)
    if has_voice:
        v = read_audio(narr_path)[:n]
        voice = np.zeros((n, 2), np.float32)
        voice[: len(v)] = v
        env = np.abs(voice).mean(1)
        speaking = _lp(env, 6.0, 1) > (0.08 * np.percentile(env, 99))
        vref = _rms_db(voice[speaking])
        bref = _rms_db(bed[np.any(bed != 0, axis=1)]) if np.any(bed) else -120
        under = acfg.get("bed_under_voice_db", 20.0)
        pause = acfg.get("bed_in_pauses_db", 11.0)
        target = np.where(speaking, vref - under, vref - pause).astype(np.float32)
        k = int(0.15 * SR)
        target = np.convolve(target, np.ones(k, np.float32) / k, mode="same")
        gain_db = target - bref
        mix += voice + bed * (10 ** (gain_db / 20))[:, None]
    else:
        mix += bed
    mix *= _env(n, 0.05, 0.6)[:, None]
    peak = np.abs(mix).max()
    if peak > 0.97:
        mix *= 0.97 / peak
    write_wav(out_path, mix)
    return has_voice
