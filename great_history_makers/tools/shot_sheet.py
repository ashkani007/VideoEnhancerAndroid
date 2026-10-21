#!/usr/bin/env python3
"""Contact sheet with one labelled frame from the middle of every shot of a rendered episode."""
import json
import os
import subprocess
import sys

import cv2
import numpy as np


def main(ep_dir, video, out, cols=5, w=216):
    cfg = json.load(open(os.path.join(ep_dir, "episode.json")))
    h = int(w * 16 / 9)
    tiles = []
    for i, s in enumerate(cfg["scenes"]):
        t = s["start"] + s["duration"] * 0.55
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", video, "-frames:v", "1", "-vf",
                              f"scale={w}:{h}", "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], capture_output=True,
                             check=True).stdout
        img = np.frombuffer(raw, np.uint8).reshape(h, w, 3).copy()
        cv2.rectangle(img, (0, 0), (w, 26), (20, 14, 10), -1)
        cv2.putText(img, f"{i + 1}. {s['id'][3:]}  {s['start']:.1f}s", (6, 18), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (230, 240, 250), 1, cv2.LINE_AA)
        tiles.append(img)
    while len(tiles) % cols:
        tiles.append(np.zeros_like(tiles[0]))
    rows = [np.hstack(tiles[k:k + cols]) for k in range(0, len(tiles), cols)]
    cv2.imwrite(out, np.vstack(rows))
    print(out)


if __name__ == "__main__":
    main(*sys.argv[1:4])
