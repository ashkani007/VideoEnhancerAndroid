#!/usr/bin/env python3
"""Plumbing test for ghm_worker.py: a mock ComfyUI API + a throw-away git remote (no GPU, no real images).

  python comfyui/worker/test_worker.py

Checks: job validation (accepts the queued Napoleon job, rejects malicious ones), graph building against every
template (links resolve, LoRA rewiring, allow-list), image upload, prompt/history/view round trip, manifest and
contact sheet, and the git fetch -> results commit -> push loop. The mock returns flat grey test images; it says
nothing about image quality.
"""
import http.server
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading

HERE = os.path.dirname(os.path.abspath(__file__))
GHM = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
import ghm_worker as W  # noqa: E402

REQUIRED = {"KSampler": {"model", "seed", "steps", "cfg", "sampler_name", "scheduler", "positive", "negative", "latent_image", "denoise"},
            "CLIPTextEncode": {"text", "clip"}, "VAEDecodeTiled": {"samples", "vae", "tile_size", "overlap"},
            "IPAdapterAdvanced": {"model", "ipadapter", "image", "weight", "weight_type", "start_at", "end_at"},
            "LoraLoader": {"model", "clip", "lora_name", "strength_model", "strength_clip"}, "SaveImage": {"images", "filename_prefix"}}
SEEN = []


class Mock(http.server.BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def send(self, obj, ctype="application/json"):
        data = obj if isinstance(obj, bytes) else json.dumps(obj).encode()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path == "/system_stats":
            return self.send({"system": {"comfyui_version": "mock", "python_version": "3.12"},
                              "devices": [{"name": "cuda:0 NVIDIA GeForce RTX 4060 (mock)", "vram_total": 8 * 2 ** 30, "vram_free": 7 * 2 ** 30}]})
        if self.path.startswith("/object_info/"):
            return self.send({self.path.split("/")[-1]: {}})
        if self.path.startswith("/models/"):
            return self.send(["sd_xl_base_1.0.safetensors", "RealESRGAN_x4plus.pth"])
        if self.path.startswith("/history/"):
            return self.send({"p1": {"status": {"status_str": "success"}, "outputs": {"9": {"images": [{"filename": "x.png", "type": "output"}]}}}})
        if self.path.startswith("/view"):
            from PIL import Image
            b = io.BytesIO()
            Image.new("RGB", (1152, 2016), (90, 90, 96)).save(b, "PNG")
            return self.send(b.getvalue(), "image/png")
        self.send_error(404)

    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        if self.path == "/upload/image":
            name = re.search(rb'filename="([^"]+)"', body).group(1).decode()
            return self.send({"name": name, "subfolder": "", "type": "input"})
        if self.path == "/prompt":
            g = json.loads(body)["prompt"]
            for k, n in g.items():
                miss = REQUIRED.get(n["class_type"], set()) - set(n["inputs"])
                assert not miss, f"{k} {n['class_type']} misses {miss}"
                for v in n["inputs"].values():
                    if isinstance(v, list) and len(v) == 2 and isinstance(v[0], str):
                        assert v[0] in g, f"dangling link {v}"
            SEEN.append(g)
            return self.send({"prompt_id": "p1"})
        self.send_error(404)


def expect_reject(job, why):
    try:
        W.validate(job, GHM)
    except W.JobError as e:
        print(f"  rejected ({why}): {e}")
        return
    raise AssertionError(f"accepted a bad job: {why}")


def main():
    job = json.load(open(os.path.join(GHM, "jobs", "queue", "napoleon_test3_v1.json"), encoding="utf-8"))
    v = W.validate(job, GHM)
    assert len(v["runs"]) == 12
    print("validation: the Napoleon job is valid (12 runs)")
    bad = json.loads(json.dumps(job))
    bad["references"]["style"] = "../../../../etc/passwd"
    expect_reject(bad, "path escape")
    bad = json.loads(json.dumps(job))
    bad["workflow"] = "my_custom_graph"
    expect_reject(bad, "unknown workflow")
    bad = json.loads(json.dumps(job))
    bad["shots"][0]["command"] = "del C:\\"
    expect_reject(bad, "unknown key")
    bad = json.loads(json.dumps(job))
    bad["shots"][0]["seeds"] = list(range(9))
    expect_reject(bad, "too many seeds")
    bad = json.loads(json.dumps(job))
    bad["shots"][0]["loras"] = [{"name": "..\\..\\evil.safetensors"}]
    expect_reject(bad, "lora path")
    try:
        W.Comfy("http://203.0.113.5:8188")
        raise AssertionError("accepted a public ComfyUI address")
    except SystemExit as e:
        print(f"  rejected (non-loopback server): {e}")

    # graph templates: LoRA rewiring + allow-list
    r = dict(v["runs"][0], loras=[{"name": "napoleon_v1.safetensors", "strength": 0.8}])
    tpl = json.load(open(os.path.join(GHM, "comfyui", "workflows", "ghm_sdxl_hires_ipadapter_api.json")))
    g = W.build_graph(tpl, r, {"style": "ghm_ref.png"})
    assert g["11"]["inputs"]["model"] == ["lora0", 0] and g["2"]["inputs"]["clip"] == ["lora0", 1]
    tpl_bad = dict(tpl, x={"class_type": "ExecutePythonCode", "_meta": {"title": "x"}, "inputs": {}})
    try:
        W.build_graph(tpl_bad, v["runs"][0], {"style": "a.png"})
        raise AssertionError("allow-list not enforced")
    except W.JobError as e:
        print(f"  rejected (node allow-list): {e}")
    for wf, extra in (("sdxl_layout_ipadapter", {"init_image": "assets/references/napoleon_style_reference_01.png"}),
                      ("upscale2x", {"init_image": "assets/references/napoleon_style_reference_01.png"}),
                      ("sdxl_hires", {})):
        j = {"job_id": "t_" + wf, "kind": "upscale" if wf == "upscale2x" else "illustrate", "workflow": wf,
             "references": {"style": "assets/references/napoleon_style_reference_01.png"},
             "shots": [dict({"id": "s01", "positive": "test", "seeds": [1]}, **extra)]}
        rr = W.validate(j, GHM)["runs"][0]
        g = W.build_graph(json.load(open(os.path.join(GHM, "comfyui", "workflows", W.WORKFLOWS[wf]))), rr,
                          {"style": "a.png", "init_image": "b.png"})
        for k, n in g.items():
            assert not REQUIRED.get(n["class_type"], set()) - set(n["inputs"]), (wf, k)
            for val in n["inputs"].values():
                assert not (isinstance(val, list) and len(val) == 2 and isinstance(val[0], str) and val[0] not in g), (wf, val)
        if wf == "sdxl_layout_ipadapter":
            assert g["5"]["inputs"]["denoise"] == 0.72 and g["13"]["inputs"]["image"] == "b.png"
    print("graph building: LoRA rewiring, node allow-list and all four templates ok")

    # end-to-end: mock ComfyUI + temporary git remote
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Mock)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_address[1]}"
    tmp = tempfile.mkdtemp()
    try:
        remote, work = os.path.join(tmp, "remote.git"), os.path.join(tmp, "work")
        sh = lambda *c, cwd=None: subprocess.run(c, cwd=cwd, check=True, capture_output=True, text=True).stdout  # noqa: E731
        sh("git", "init", "-q", "--bare", "-b", "main", remote)
        seed = os.path.join(tmp, "seed")
        for rel in ("comfyui/workflows", "assets/references", "jobs/queue"):
            shutil.copytree(os.path.join(GHM, rel), os.path.join(seed, "great_history_makers", rel))
        sh("git", "init", "-q", "-b", "testbranch", cwd=seed)
        sh("git", "add", "-A", cwd=seed)
        sh("git", "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", "seed", cwd=seed)
        sh("git", "push", "-q", remote, "testbranch", cwd=seed)
        sh("git", "clone", "-q", "-b", "testbranch", remote, work)
        out = subprocess.run([sys.executable, os.path.join(HERE, "ghm_worker.py"), "--repo", work, "--branch", "testbranch",
                              "--server", url, "--once", "--keep", os.path.join(tmp, "keep")], capture_output=True, text=True)
        print(out.stdout.strip().splitlines()[-1])
        assert out.returncode == 0, out.stderr
        check = os.path.join(tmp, "check")
        sh("git", "clone", "-q", "-b", "testbranch", remote, check)
        m = json.load(open(os.path.join(check, "great_history_makers", "jobs", "results", "napoleon_test3_v1", "manifest.json")))
        assert m["status"] == "done" and len(m["images"]) == 12, m
        assert os.path.exists(os.path.join(check, "great_history_makers", "jobs", "results", "napoleon_test3_v1", "contact_sheet.jpg"))
        assert len(SEEN) == 12 and SEEN[0]["10"]["inputs"]["image"].startswith("ghm_")
        print(f"end-to-end: 12 graphs accepted, results pushed to the remote ({m['system']['gpu']}, {m['system']['vram_total_gb']} GB)")
        out2 = subprocess.run([sys.executable, os.path.join(HERE, "ghm_worker.py"), "--repo", work, "--branch", "testbranch",
                               "--server", url, "--once"], capture_output=True, text=True)
        assert len(SEEN) == 12, "a finished job was run twice"
        print("idempotence: a finished job is not run again")
    finally:
        srv.shutdown()
        shutil.rmtree(tmp, ignore_errors=True)
    print("ALL WORKER TESTS PASSED")


if __name__ == "__main__":
    main()
