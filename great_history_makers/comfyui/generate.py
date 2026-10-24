#!/usr/bin/env python3
"""Queue a prompt file through a local ComfyUI server and collect the images (Python standard library only).

  python generate.py prompts\\napoleon_character_v1.json
  python generate.py prompts\\napoleon_character_v1.json --workflow workflows\\napoleon_sdxl_upscale_api.json
  python generate.py prompts\\napoleon_character_v1.json --server http://127.0.0.1:8188 --out candidates

Start ComfyUI first (run_nvidia_gpu.bat). Each seed in the prompt file becomes one image. Results are copied
to <out>/<prompt name>/ with the seed in the filename, plus a run log (prompt, seed, time per image).
"""
import argparse
import copy
import json
import os
import time
import urllib.parse
import urllib.request
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))


def call(server, path, data=None):
    req = urllib.request.Request(server + path, data=json.dumps(data).encode() if data is not None else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def fetch(server, image):
    q = urllib.parse.urlencode({"filename": image["filename"], "subfolder": image.get("subfolder", ""),
                                "type": image.get("type", "output")})
    with urllib.request.urlopen(f"{server}/view?{q}", timeout=60) as r:
        return r.read()


def fill(workflow, spec, seed):
    """Put the prompt text, negative, size, sampler settings and seed into the API-format workflow."""
    wf = copy.deepcopy(workflow)
    for node in wf.values():
        ins, kind = node["inputs"], node["class_type"]
        if kind == "CLIPTextEncode":
            if ins.get("text") == "POSITIVE":
                ins["text"] = spec["positive"]
            elif ins.get("text") == "NEGATIVE":
                ins["text"] = spec["negative"]
        elif kind == "EmptyLatentImage":
            ins["width"], ins["height"] = spec.get("width", 768), spec.get("height", 1344)
        elif kind == "KSampler":
            ins["seed"] = seed
            ins["steps"] = spec.get("steps", ins["steps"])
            ins["cfg"] = spec.get("cfg", ins["cfg"])
        elif kind == "SaveImage":
            ins["filename_prefix"] = f"GHM/{spec['name']}_s{seed}" + ("_2x" if "2x" in ins["filename_prefix"] else "")
    return wf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("prompts")
    ap.add_argument("--workflow", default=os.path.join(HERE, "workflows", "napoleon_sdxl_api.json"))
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--out", default=os.path.join(HERE, "candidates"))
    ap.add_argument("--timeout", type=float, default=900)
    a = ap.parse_args()
    spec = json.load(open(a.prompts, encoding="utf-8"))
    workflow = json.load(open(a.workflow, encoding="utf-8"))
    out = os.path.join(a.out, spec["name"])
    os.makedirs(out, exist_ok=True)
    client = str(uuid.uuid4())
    log = []
    for seed in spec["seeds"]:
        t0 = time.time()
        pid = call(a.server, "/prompt", {"prompt": fill(workflow, spec, seed), "client_id": client})["prompt_id"]
        while True:
            hist = call(a.server, f"/history/{pid}")
            if pid in hist and hist[pid].get("outputs"):
                break
            if time.time() - t0 > a.timeout:
                raise SystemExit(f"timed out waiting for seed {seed}")
            time.sleep(1.0)
        saved = []
        for node_out in hist[pid]["outputs"].values():
            for img in node_out.get("images", []):
                name = os.path.join(out, img["filename"].replace("/", "_"))
                open(name, "wb").write(fetch(a.server, img))
                saved.append(os.path.basename(name))
        dt = round(time.time() - t0, 1)
        log.append(dict(seed=seed, seconds=dt, files=saved))
        print(f"seed {seed}: {dt}s -> {', '.join(saved)}", flush=True)
    json.dump(dict(prompt=spec, workflow=os.path.basename(a.workflow), runs=log), open(os.path.join(out, "run_log.json"), "w"),
              indent=1)
    print(f"done: {len(log)} images in {out}")


if __name__ == "__main__":
    main()
