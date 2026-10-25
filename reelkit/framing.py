"""Shot-aware 9:16 framing.

For every clip we look at real frames (start / middle / end) from the copy
that will actually be rendered and find what must stay on screen:

* faces            — YuNet (OpenCV zoo, MIT), expanded to head-and-shoulders
* characters/props — YOLOX-S (OpenCV zoo, Apache-2.0): people and animals
* everything else  — spectral-residual saliency (OpenCV contrib), used when no
                     detector fires (dragons are not a COCO class)

Then the crop is chosen as the *widest* window that still keeps the subject
large, never narrower than the subject box (+margin), never narrower than the
upscale limit (no excessive digital zoom), and the full frame when the action
spans the frame. Height is never cropped, so heads are never cut.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import cv2
import numpy as np

from .util import Cache, Config

MODELS = {
    "face_detection_yunet_2023mar.onnx":
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
    "object_detection_yolox_2022nov.onnx":
        "https://media.githubusercontent.com/media/opencv/opencv_zoo/main/models/object_detection_yolox/object_detection_yolox_2022nov.onnx",
}
COCO_KEEP = {0: "person", 14: "bird", 15: "cat", 16: "dog", 17: "horse", 18: "sheep", 19: "cow",
             20: "elephant", 21: "bear", 22: "zebra", 23: "giraffe"}


def _ensure(cfg: Config, name: str) -> str:
    p = cfg.models_dir / name
    if not p.exists():
        subprocess.run(["curl", "-sSL", "--fail", "-o", str(p), MODELS[name]], check=True)
    return str(p)


class Detector:
    def __init__(self, cfg: Config):
        self.face = cv2.FaceDetectorYN.create(_ensure(cfg, "face_detection_yunet_2023mar.onnx"),
                                              "", (320, 320), 0.7)
        self.yolo = cv2.dnn.readNet(_ensure(cfg, "object_detection_yolox_2022nov.onnx"))
        self.sal = cv2.saliency.StaticSaliencySpectralResidual_create()
        strides = [8, 16, 32]
        grids, exp = [], []
        for s in strides:
            n = 640 // s
            xv, yv = np.meshgrid(np.arange(n), np.arange(n))
            grids.append(np.stack((xv, yv), 2).reshape(-1, 2))
            exp.append(np.full((n * n, 1), s))
        self.grids, self.strides = np.concatenate(grids), np.concatenate(exp)

    def faces(self, img: np.ndarray) -> list[list[float]]:
        h, w = img.shape[:2]
        scale = 640 / max(w, h) if max(w, h) < 640 else 1.0
        im = cv2.resize(img, None, fx=scale, fy=scale) if scale != 1.0 else img
        self.face.setInputSize((im.shape[1], im.shape[0]))
        _, out = self.face.detect(im)
        if out is None:
            return []
        return [[x / scale, y / scale, (x + bw) / scale, (y + bh) / scale, float(c)]
                for x, y, bw, bh, *_, c in out]

    def objects(self, img: np.ndarray, thr: float = 0.40) -> list[list[float]]:
        h, w = img.shape[:2]
        r = min(640 / h, 640 / w)
        pad = np.full((640, 640, 3), 114, np.uint8)
        pad[: int(h * r), : int(w * r)] = cv2.resize(img, (int(w * r), int(h * r)))
        blob = np.transpose(cv2.cvtColor(pad, cv2.COLOR_BGR2RGB), (2, 0, 1))[None].astype(np.float32)
        self.yolo.setInput(blob)
        o = self.yolo.forward()[0]
        xy = (o[:, :2] + self.grids) * self.strides
        wh = np.exp(o[:, 2:4]) * self.strides
        scores = o[:, 4:5] * o[:, 5:]
        cls = scores.argmax(1)
        conf = scores.max(1)
        keep = (conf > thr) & np.isin(cls, list(COCO_KEEP))
        boxes = np.concatenate([xy - wh / 2, wh], 1)[keep] / r
        conf, cls = conf[keep], cls[keep]
        idx = cv2.dnn.NMSBoxes(boxes.tolist(), conf.tolist(), thr, 0.45)
        out = []
        for i in np.array(idx).flatten():
            x, y, bw, bh = boxes[i]
            out.append([max(0, x), max(0, y), min(w, x + bw), min(h, y + bh), float(conf[i]), COCO_KEEP[int(cls[i])]])
        return out

    def salient(self, img: np.ndarray, mass: float = 0.7) -> list[float]:
        small = cv2.resize(img, (128, max(32, int(128 * img.shape[0] / img.shape[1]))))
        ok, m = self.sal.computeSaliency(small)
        m = cv2.GaussianBlur(m, (0, 0), 3)
        col = m.sum(0)
        c = np.cumsum(col) / (col.sum() + 1e-9)
        lo, hi = np.searchsorted(c, (1 - mass) / 2), np.searchsorted(c, 1 - (1 - mass) / 2)
        sx = img.shape[1] / small.shape[1]
        return [lo * sx, 0, (hi + 1) * sx, img.shape[0]]


def grab(path: str, t: float, w: int, h: int) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(0, t):.3f}", "-i", path, "-frames:v", "1",
           "-f", "rawvideo", "-pix_fmt", "bgr24", "-"]
    raw = subprocess.run(cmd, capture_output=True, check=True).stdout
    return np.frombuffer(raw[: w * h * 3], np.uint8).reshape(h, w, 3)


def _head_shoulders(f, w, h):
    x0, y0, x1, y1 = f[:4]
    fw, fh = x1 - x0, y1 - y0
    return [max(0, x0 - 0.5 * fw), max(0, y0 - 0.6 * fh), min(w, x1 + 0.5 * fw), min(h, y1 + 1.2 * fh)]


def _union(boxes):
    b = np.array(boxes)
    return [b[:, 0].min(), b[:, 1].min(), b[:, 2].max(), b[:, 3].max()]


def plan_clip(cfg: Config, det: Detector, rend: dict, src_in: float, src_out: float,
              W: int, H: int, max_up: float, hint: str | None = None) -> dict:
    cache = Cache(cfg.cache_dir)
    key = f"v5|{rend.get('sha256', rend['file'])}|{src_in:.3f}|{src_out:.3f}|{W}x{H}|{max_up}|{hint}"
    if (hit := cache.get("framing", key)) is not None:
        return hit
    sw, sh = rend["width"], rend["height"]
    times = [src_in + 0.12, (src_in + src_out) / 2, src_out - 0.12]
    per_frame, faces_all = [], []
    for t in times:
        img = grab(rend["file"], t - rend["offset"], sw, sh)
        faces = det.faces(img)
        objs = det.objects(img)
        subj = [_head_shoulders(f, sw, sh) for f in faces]
        for o in objs:
            # a body box that already contains a detected face is represented
            # by that face's head-and-shoulders box (close-ups would otherwise
            # read as frame-wide subjects)
            has_face = any(o[0] <= (f[0] + f[2]) / 2 <= o[2] and o[1] <= (f[1] + f[3]) / 2 <= o[3]
                           for f in faces)
            if not (o[5] == "person" and has_face):
                subj.append(o[:4])
        if subj:
            box, by = _union(subj), "detections"
        else:
            box = det.salient(img, mass=0.5)
            by = "saliency-scene" if box[2] - box[0] > 0.6 * sw else "saliency"
        per_frame.append({"t": round(t, 2), "box": [round(float(v), 1) for v in box], "by": by,
                          "faces": [[round(float(v), 1) for v in f[:4]] for f in faces],
                          "objects": [[*(round(float(v), 1) for v in o[:4]), o[5]] for o in objs]})
        faces_all += [f[:4] for f in faces]

    widths = [p["box"][2] - p["box"][0] for p in per_frame]
    union = _union([p["box"] for p in per_frame])
    scene = all(p["by"] == "saliency-scene" for p in per_frame)
    min_cw = max(sh * 9 / 16, W / max_up)                  # 9:16 floor, and zoom limit
    # keep every subject seen in the clip at once when that still fits a
    # vertical-friendly crop; otherwise follow them with a calm pan
    need = (union[2] - union[0]) * 1.12
    if need > 0.8 * sw:
        need = max(widths) * 1.12

    def layout(cw):
        cw = int(round(cw / 2) * 2)

        def centre(box):
            lo, hi = box[2] - cw / 2, box[0] + cw / 2       # positions keeping the box inside
            c = float(np.clip((box[0] + box[2]) / 2, min(lo, hi), max(lo, hi)))
            return float(np.clip(c, cw / 2, sw - cw / 2))

        if (union[2] - union[0]) * 1.12 <= cw:
            x0 = x1 = centre(union)
        else:
            x0, x1 = centre(per_frame[0]["box"]), centre(per_frame[-1]["box"])
            maxd = 0.06 * sw * (src_out - src_in)          # calm pans only
            x1 = x0 + float(np.clip(x1 - x0, -maxd, maxd))
        xs = [x0, (x0 + x1) / 2, x1]

        def inside(b, cx):
            left = cx - cw / 2
            return max(0.0, min(b[2], left + cw) - max(b[0], left)) / max(1e-6, b[2] - b[0])
        fcov = min([inside(f, xs[i]) for i, p in enumerate(per_frame) for f in p["faces"]], default=1.0)
        scov = min(inside(p["box"], xs[i]) for i, p in enumerate(per_frame))
        return cw, x0, x1, fcov, scov

    if hint == "wide" or scene or need > 0.8 * sw:
        cw = sw                                            # keep the whole composition
    elif hint == "tight":
        cw = min(sw, max(min_cw, sh * 9 / 16))
    else:
        cw = min(sw, max(min_cw, need))
    cw, x_start, x_end, face_cov, subj_cov = layout(cw)
    if (subj_cov < 0.95 or face_cov < 0.98) and cw < sw:
        cw, x_start, x_end, face_cov, subj_cov = layout(sw)   # never lose the subject
    up = W / cw
    fh = int(round(W * sh / cw / 2) * 2)
    mode = "fill" if fh >= 0.97 * H else ("full-frame" if cw >= sw else "subject-crop")
    res = {"rendition": rend["file"], "rend_w": sw, "rend_h": sh, "offset": rend["offset"],
           "crop_w": cw, "cx0": round(x_start / sw, 4), "cx1": round(x_end / sw, 4),
           "fg_h": fh, "upscale": round(up, 2), "mode": mode, "face_coverage": round(face_cov, 3),
           "subject_coverage": round(subj_cov, 3), "frames": per_frame}
    cache.put("framing", key, res)
    return res
