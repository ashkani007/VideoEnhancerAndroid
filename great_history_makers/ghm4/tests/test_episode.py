#!/usr/bin/env python3
"""End-to-end test of the automated episode pipeline with STAND-IN results (no GPU here).

Simulates what the PC worker pushes (candidates + manifest, with crops of the approved illustration standing in for
generated images), then runs pick --auto, plates (automatic metadata + matte), annotations, storyboard and frame
rendering. Checks the automation, not image generation. Temporary job files are removed afterwards.

  python -m ghm4.tests.test_episode
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np

GHM = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EP_SRC = os.path.join(GHM, "episodes_v4", "napoleon_3scene_test", "episode.json")
MASTER = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "source", "napoleon_master.png")
MASTER_META = os.path.join(GHM, "GreatHistoryMakers", "Napoleon_Animation_Test", "source", "napoleon_master.json")
EP_ID = "zz_pipeline_test"


def run(*args):
    r = subprocess.run([sys.executable, "-m", "ghm4.episode", *args], cwd=GHM, capture_output=True, text=True)
    out = "\n".join(ln for ln in r.stdout.splitlines() if "Warning" not in ln)
    assert r.returncode == 0, out + r.stderr[-1500:]
    return out


def crop916(img, x0, y0, w):
    h = int(round(w * 16 / 9))
    return cv2.resize(img[y0:y0 + h, x0:x0 + w], (1152, 2048), interpolation=cv2.INTER_LANCZOS4)[:2016]


def main():
    tmp = tempfile.mkdtemp()
    jobfiles = []
    try:
        ep_dir = os.path.join(tmp, "ep")
        os.makedirs(ep_dir)
        spec = json.load(open(EP_SRC, encoding="utf-8"))
        spec["id"] = EP_ID
        json.dump(spec, open(os.path.join(ep_dir, "episode.json"), "w"), indent=1)
        print(run("jobs", ep_dir).splitlines()[0])
        state = json.load(open(os.path.join(ep_dir, "state.json")))
        jid = state["illustrate_job"]
        jobfiles += [os.path.join(GHM, "jobs", "queue", jid + ".json"), os.path.join(GHM, "jobs", "specs", jid + ".json"),
                     os.path.join(GHM, "jobs", "results", jid)]
        # --- simulate the worker's results (stand-in images)
        src = cv2.imread(MASTER)
        res = os.path.join(GHM, "jobs", "results", jid)
        os.makedirs(res)
        portrait = crop916(src, 160, 100, 470)
        battle = crop916(src, 450, 500, 491 - 15)
        imgs = {("b1_portrait", 1201): portrait, ("b1_portrait", 1202): cv2.GaussianBlur(portrait, (0, 0), 6),
                ("b2_battle", 2201): battle, ("b2_battle", 2202): cv2.GaussianBlur(battle, (0, 0), 6)}
        man = {"job_id": jid, "status": "done", "images": [], "errors": [], "system": {"gpu": "STAND-IN (test)", "vram_total_gb": 8.0}}
        for (shot, seed), im in imgs.items():
            f = f"{shot}_s{seed}.jpg"
            cv2.imwrite(os.path.join(res, f), im, [cv2.IMWRITE_JPEG_QUALITY, 92])
            man["images"].append({"shot": shot, "seed": seed, "file": f, "seconds": 0})
        json.dump(man, open(os.path.join(res, "manifest.json"), "w"))
        # --- pick (technical ranking must prefer the sharp candidates)
        out = run("pick", ep_dir, "--auto", "--no-upscale")
        state = json.load(open(os.path.join(ep_dir, "state.json")))
        assert state["picks"] == {"b1_portrait": "b1_portrait_s1201.jpg", "b2_battle": "b2_battle_s2201.jpg"}, state["picks"]
        # --- plates: automatic metadata + mattes
        out = run("plates", ep_dir)
        print(out)
        rep = json.load(open(os.path.join(ep_dir, "state.json")))["plates"]
        assert rep["b1_portrait"]["matte"], "portrait stand-in should get a matte"
        assert not rep["b2_battle"]["matte"], "battle plates have no foreground layer"
        assert rep["b2_battle"]["flags"] >= 2, "tricolour flags should be detected on the battlefield"
        assert "eyes (blink)" in rep["b1_portrait"]["annotate"]
        # --- annotation (eye outline + hand pivot), as Claude would write it after looking at the grid sheet
        run("sheet", ep_dir, "b1_portrait")
        meta = json.load(open(MASTER_META))
        k = 1152 / 470.0
        tx = lambda x, y: [round((x - 160) * k, 1), round((y - 100) * k, 1)]     # noqa: E731
        e = meta["eyes"][0]
        ann = {"b1_portrait": {"eyes": [{"upper": [tx(*p) for p in e["upper"]], "lower": [tx(*p) for p in e["lower"]],
                                         "close_y": tx(0, e["close_y"])[1], "skin": tx(*e["skin"][:2]) + tx(*e["skin"][2:])}],
                               "face": tx(445, 360),
                               "sway": [{"box": tx(500, 950) + tx(600, 1100), "pivot": tx(540, 940), "angle": 1.5, "rate": 0.4}]}}
        json.dump(ann, open(os.path.join(ep_dir, "annotations.json"), "w"))
        out = run("plates", ep_dir)
        assert "to annotate: eyes" not in out
        # --- storyboard timed to the narration
        out = run("storyboard", ep_dir)
        print(out)
        sb = json.load(open(os.path.join(ep_dir, "storyboard.json")))
        assert [s["start"] for s in sb["shots"]] == [0.0, 10.25, 12.82], [s["start"] for s in sb["shots"]]
        assert [t["type"] for t in sb["transitions"]] == ["whip", "ink"]
        assert sb["shots"][0].get("blink") and sb["shots"][1].get("puffs") and "CONFLICT" not in out
        # --- frames (blink visible, map, battle)
        sys.path.insert(0, GHM)
        from ghm4.render import Renderer
        R = Renderer(os.path.join(ep_dir, "storyboard.json"), 720, 1280)
        tb = sb["shots"][0]["blink"][0]
        open_f, shut_f = R.frame(tb - 0.3), R.frame(tb + 0.15)
        fr = [R.frame(t) for t in (2.0, 11.5, 14.0, 17.0)]
        assert all(np.isfinite(f).all() for f in fr + [open_f, shut_f])
        diff = float(np.abs(open_f - shut_f).max())
        assert diff > 0.15, f"blink not visible (max change {diff:.3f})"
        sheet = np.hstack([cv2.resize((f * 255).astype(np.uint8), (240, 427)) for f in [open_f, shut_f] + fr])
        os.makedirs(os.path.join(GHM, "ghm4", "tests", "out"), exist_ok=True)
        cv2.imwrite(os.path.join(GHM, "ghm4", "tests", "out", "episode_pipeline_standin.jpg"), cv2.cvtColor(sheet, cv2.COLOR_RGB2BGR))
        print("EPISODE PIPELINE TEST PASSED (stand-in images)")
    finally:
        for f in jobfiles:
            if os.path.isdir(f):
                shutil.rmtree(f, ignore_errors=True)
            elif os.path.exists(f):
                os.remove(f)
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    main()
