"""Premultiplied-alpha compositing of transformed sprites (ROI-only warps)."""
import cv2
import numpy as np


def composite(frame, premult, M, opacity=1.0):
    """frame: HxWx3 float32 [0,1]. premult: hxwx4 uint8. M: 3x3 sprite px -> frame px."""
    h, w = premult.shape[:2]
    H, W = frame.shape[:2]
    corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], float) @ M.T
    x0 = max(0, int(np.floor(corners[:, 0].min())) - 1)
    y0 = max(0, int(np.floor(corners[:, 1].min())) - 1)
    x1 = min(W, int(np.ceil(corners[:, 0].max())) + 1)
    y1 = min(H, int(np.ceil(corners[:, 1].max())) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    A = M.copy()
    A[0, 2] -= x0
    A[1, 2] -= y0
    warped = cv2.warpAffine(premult, A[:2], (x1 - x0, y1 - y0), flags=cv2.INTER_LINEAR,
                            borderMode=cv2.BORDER_CONSTANT, borderValue=(0, 0, 0, 0))
    f = warped.astype(np.float32) * (opacity / 255.0)
    roi = frame[y0:y1, x0:x1]
    roi *= 1.0 - f[..., 3:4]
    roi += f[..., :3]


def wave_deform(premult, t, amp, wavelength, speed=1.0, axis="y", phase=0.0, power=1.4,
                anchor=0.0, secondary=0.35):
    """Gentle cloth motion. axis='y': cloth hangs downward from anchor row (fraction of
    height) and sways sideways; axis='x': banner flies from a pole at x=anchor and
    ripples vertically. amp/wavelength in sprite pixels. The displacement is a few
    tiles at most, so the tesserae bend slightly but remain recognisable."""
    h, w = premult.shape[:2]
    X, Y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))
    k = 2 * np.pi / wavelength
    om = 2 * np.pi * speed
    if axis == "y":
        u = np.clip((Y - anchor * h) / max(1.0, (1 - anchor) * h), 0, 1) ** power
        d = amp * u * (np.sin(k * Y - om * t + phase) + secondary * np.sin(2.3 * k * Y - 1.7 * om * t + phase * 2))
        mx, my = X - d, Y
    else:
        dist = np.abs(X - anchor * w)
        u = np.clip(dist / max(1.0, w), 0, 1) ** power
        d = amp * u * (np.sin(k * dist - om * t + phase) + secondary * np.sin(2.1 * k * dist - 1.6 * om * t))
        mx, my = X, Y - d
    return cv2.remap(premult, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
