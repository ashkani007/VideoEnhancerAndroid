#!/usr/bin/env python3
"""Great History Makers local illustration worker (runs on the Windows PC next to ComfyUI).

It connects the cloud Claude Code session to the local GPU through the git repository, with no inbound ports:
  1. fetch the job branch (outbound HTTPS to GitHub only)
  2. for every jobs/queue/<id>.json without jobs/results/<id>/manifest.json: validate it (pure data, strict schema),
     build the graph from an allow-listed workflow template, run it on ComfyUI at 127.0.0.1:8188
  3. write images + manifest (GPU name, VRAM, timings) to jobs/results/<id>/, commit, pull --rebase, push

Jobs can never run code: the worker only accepts known keys and bounded values, only reads reference images inside
great_history_makers/, refuses non-loopback ComfyUI servers and refuses graphs containing node types outside
ALLOWED_NODES. Standard library only, plus Pillow (shipped with ComfyUI) for JPEG output and contact sheets.

  python ghm_worker.py --repo C:\\AI\\ghm-worker\\VideoEnhancerAndroid            # poll every 60 s until Ctrl+C
  python ghm_worker.py --repo ... --once                                           # process pending jobs, then exit
  python ghm_worker.py --repo ... --once --no-git                                  # local test: no fetch / push
  python ghm_worker.py --check                                                     # ComfyUI, GPU and model check only
"""
import argparse
import copy
import io
import ipaddress
import json
import os
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

WORKFLOWS = {                       # job "workflow" name -> template file (comfyui/workflows/)
    "sdxl_hires": "ghm_sdxl_hires_api.json",
    "sdxl_hires_ipadapter": "ghm_sdxl_hires_ipadapter_api.json",
    "sdxl_layout_ipadapter": "ghm_sdxl_layout_ipadapter_api.json",
    "upscale2x": "ghm_upscale2x_api.json",
}
ALLOWED_NODES = {"CheckpointLoaderSimple", "CLIPTextEncode", "EmptyLatentImage", "KSampler", "LatentUpscaleBy",
                 "VAEDecode", "VAEDecodeTiled", "VAEEncode", "SaveImage", "LoadImage", "LoraLoader",
                 "IPAdapterUnifiedLoader", "IPAdapterAdvanced", "UpscaleModelLoader", "ImageUpscaleWithModel",
                 "ImageScaleBy"}
JOB_KEYS = {"job_id", "kind", "created", "notes", "workflow", "defaults", "references", "shots", "output"}
SHOT_KEYS = {"id", "positive", "negative", "seeds", "width", "height", "steps", "cfg", "hires_scale", "hires_steps",
             "hires_denoise", "ipadapter_weight", "ipadapter_weight_type", "ipadapter_end_at", "init_image", "denoise",
             "loras", "notes", "sampler_name", "scheduler", "checkpoint"}
SAMPLERS = {"euler", "euler_ancestral", "dpmpp_2m", "dpmpp_2m_sde", "dpmpp_3m_sde", "dpmpp_sde", "uni_pc", "ddim"}
SCHEDULERS = {"normal", "karras", "exponential", "sgm_uniform", "simple", "beta"}
WEIGHT_TYPES = {"linear", "style transfer", "composition", "strong style transfer", "style and composition", "ease in-out"}
ID_RE = re.compile(r"^[a-z0-9][a-z0-9_\-]{2,63}$")
FILE_RE = re.compile(r"^[A-Za-z0-9_\-. ]{1,120}\.safetensors$|^[A-Za-z0-9_\-. ]{1,120}\.pth$")
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
MAX_IMAGES = 40


class JobError(ValueError):
    pass


# ------------------------------------------------------------------------------------------- validation
def _num(d, k, lo, hi, default, kind=float):
    v = d.get(k, default)
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not lo <= v <= hi:
        raise JobError(f"{k}={v!r} must be a number in [{lo}, {hi}]")
    return kind(v)


def _text(d, k, default="", limit=3000):
    v = d.get(k, default)
    if not isinstance(v, str) or len(v) > limit:
        raise JobError(f"{k} must be a string of at most {limit} characters")
    return v


def _repo_image(ghm_root, rel):
    """Reference images must be files inside great_history_makers/ (no absolute paths, no '..' escapes)."""
    if not isinstance(rel, str) or os.path.isabs(rel) or rel.startswith(("/", "\\")):
        raise JobError(f"reference {rel!r} must be a path relative to great_history_makers/")
    p = os.path.realpath(os.path.join(ghm_root, rel))
    if not p.startswith(os.path.realpath(ghm_root) + os.sep) or not p.lower().endswith(IMG_EXT):
        raise JobError(f"reference {rel!r} is outside great_history_makers/ or not an image")
    if not os.path.isfile(p) or os.path.getsize(p) > 25 * 1024 * 1024:
        raise JobError(f"reference {rel!r} is missing or larger than 25 MB")
    return p


def validate(job, ghm_root):
    """Returns a normalised job: a list of runs (shot, seed, parameters). Raises JobError on anything unexpected."""
    if not isinstance(job, dict) or set(job) - JOB_KEYS:
        raise JobError(f"unknown job keys: {sorted(set(job) - JOB_KEYS) if isinstance(job, dict) else job!r}")
    jid = job.get("job_id")
    if not isinstance(jid, str) or not ID_RE.match(jid):
        raise JobError("job_id must match [a-z0-9_-]{3,64}")
    if job.get("kind") not in ("illustrate", "upscale"):
        raise JobError("kind must be 'illustrate' or 'upscale'")
    wf = job.get("workflow")
    if wf not in WORKFLOWS:
        raise JobError(f"workflow must be one of {sorted(WORKFLOWS)}")
    if (job["kind"] == "upscale") != (wf == "upscale2x"):
        raise JobError("kind 'upscale' goes with workflow 'upscale2x' only")
    defaults = job.get("defaults", {})
    refs = job.get("references", {})
    out = job.get("output", {})
    if not all(isinstance(x, dict) for x in (defaults, refs, out)):
        raise JobError("defaults, references and output must be objects")
    if set(defaults) - SHOT_KEYS or set(refs) - {"style"} or set(out) - {"format", "quality", "contact_sheet"}:
        raise JobError("unknown keys in defaults, references or output")
    style = _repo_image(ghm_root, refs["style"]) if "style" in refs else None
    if "ipadapter" in WORKFLOWS[wf] and not style:
        raise JobError("IP-Adapter workflows need references.style")
    fmt = out.get("format", "jpg")
    if fmt not in ("jpg", "png"):
        raise JobError("output.format must be jpg or png")
    quality = int(_num(out, "quality", 70, 100, 92))
    shots = job.get("shots")
    if not isinstance(shots, list) or not 1 <= len(shots) <= 12:
        raise JobError("shots must be a list of 1-12 items")
    runs, ids = [], set()
    for s in shots:
        if not isinstance(s, dict) or set(s) - SHOT_KEYS:
            raise JobError(f"unknown shot keys: {sorted(set(s) - SHOT_KEYS) if isinstance(s, dict) else s!r}")
        p = dict(defaults, **s)
        sid = p.get("id")
        if not isinstance(sid, str) or not ID_RE.match(sid) or sid in ids:
            raise JobError(f"shot id {sid!r} invalid or duplicated")
        ids.add(sid)
        seeds = p.get("seeds", [1])
        if not isinstance(seeds, list) or not 1 <= len(seeds) <= 8 or not all(isinstance(x, int) and 0 <= x < 2 ** 48 for x in seeds):
            raise JobError(f"{sid}: seeds must be 1-8 integers")
        r = dict(id=sid, positive=_text(p, "positive"), negative=_text(p, "negative"),
                 width=int(_num(p, "width", 512, 1536, 768, int)), height=int(_num(p, "height", 512, 1536, 1344, int)),
                 steps=int(_num(p, "steps", 4, 60, 30, int)), cfg=_num(p, "cfg", 1.0, 15.0, 6.0),
                 hires_scale=_num(p, "hires_scale", 1.0, 2.0, 1.5), hires_steps=int(_num(p, "hires_steps", 4, 40, 20, int)),
                 hires_denoise=_num(p, "hires_denoise", 0.1, 0.7, 0.4), denoise=_num(p, "denoise", 0.2, 1.0, 0.72),
                 ipadapter_weight=_num(p, "ipadapter_weight", 0.0, 1.5, 0.6),
                 ipadapter_end_at=_num(p, "ipadapter_end_at", 0.1, 1.0, 1.0),
                 ipadapter_weight_type=p.get("ipadapter_weight_type", "style transfer"),
                 sampler_name=p.get("sampler_name", "dpmpp_2m"), scheduler=p.get("scheduler", "karras"),
                 checkpoint=p.get("checkpoint", "sd_xl_base_1.0.safetensors"), loras=p.get("loras", []), style=style)
        if job["kind"] == "illustrate" and not r["positive"].strip():
            raise JobError(f"{sid}: positive prompt is empty")
        if r["width"] % 64 or r["height"] % 64:
            raise JobError(f"{sid}: width and height must be multiples of 64")
        if r["sampler_name"] not in SAMPLERS or r["scheduler"] not in SCHEDULERS or r["ipadapter_weight_type"] not in WEIGHT_TYPES:
            raise JobError(f"{sid}: unknown sampler, scheduler or IP-Adapter weight type")
        if not isinstance(r["checkpoint"], str) or not FILE_RE.match(r["checkpoint"]):
            raise JobError(f"{sid}: checkpoint must be a plain .safetensors file name")
        if not isinstance(r["loras"], list) or len(r["loras"]) > 3:
            raise JobError(f"{sid}: loras must be a list of at most 3")
        for lo in r["loras"]:
            if not isinstance(lo, dict) or set(lo) - {"name", "strength"} or not FILE_RE.match(str(lo.get("name", ""))):
                raise JobError(f"{sid}: lora entries are {{name: file.safetensors, strength}}")
            _num(lo, "strength", -2.0, 2.0, 0.8)
        needs_init = wf in ("sdxl_layout_ipadapter", "upscale2x")
        r["init_image"] = _repo_image(ghm_root, p["init_image"]) if needs_init else None
        if needs_init and "init_image" not in p:
            raise JobError(f"{sid}: this workflow needs init_image")
        for seed in seeds:
            runs.append(dict(r, seed=seed))
    if len(runs) > MAX_IMAGES:
        raise JobError(f"{len(runs)} images requested; the limit per job is {MAX_IMAGES}")
    return dict(job_id=jid, kind=job["kind"], workflow=wf, runs=runs, format=fmt, quality=quality,
                contact_sheet=bool(out.get("contact_sheet", True)))


# ------------------------------------------------------------------------------------------- graph building
def by_title(graph, title):
    for k, n in graph.items():
        if n.get("_meta", {}).get("title") == title:
            return k, n["inputs"]
    return None, None


def build_graph(template, r, uploaded):
    g = copy.deepcopy(template)
    _, ck = by_title(g, "checkpoint")
    if ck is not None:
        ck["ckpt_name"] = r["checkpoint"]
    for title, text in (("positive", r["positive"]), ("negative", r["negative"])):
        _, n = by_title(g, title)
        if n is not None:
            n["text"] = text
    _, lat = by_title(g, "latent")
    if lat is not None:
        lat["width"], lat["height"] = r["width"], r["height"]
    for title, steps, denoise in (("base_sampler", r["steps"], None), ("hires_sampler", r["hires_steps"], r["hires_denoise"])):
        _, n = by_title(g, title)
        if n is not None:
            n.update(seed=r["seed"], steps=steps, cfg=r["cfg"], sampler_name=r["sampler_name"], scheduler=r["scheduler"])
            if denoise is not None:
                n["denoise"] = denoise
            elif "init_image" in uploaded and title == "base_sampler":
                n["denoise"] = r["denoise"]
    _, hs = by_title(g, "hires_scale")
    if hs is not None:
        hs["scale_by"] = r["hires_scale"]
    _, ip = by_title(g, "ipadapter")
    if ip is not None:
        ip.update(weight=r["ipadapter_weight"], weight_type=r["ipadapter_weight_type"], end_at=r["ipadapter_end_at"])
    for title, key in (("style_image", "style"), ("init_image", "init_image")):
        _, n = by_title(g, title)
        if n is not None:
            n["image"] = uploaded[key]
    _, sv = by_title(g, "save")
    sv["filename_prefix"] = f"GHM/{r['id']}_s{r['seed']}"
    # LoRAs: chain LoraLoader nodes after the checkpoint and re-point every model/clip consumer to the last one
    ck_id, _ = by_title(g, "checkpoint")
    if ck_id is not None and r["loras"]:
        src_m, src_c = [ck_id, 0], [ck_id, 1]
        new = []
        for i, lo in enumerate(r["loras"]):
            nid = f"lora{i}"
            g[nid] = {"class_type": "LoraLoader", "_meta": {"title": nid},
                      "inputs": {"model": src_m, "clip": src_c, "lora_name": lo["name"], "strength_model": lo.get("strength", 0.8),
                                 "strength_clip": lo.get("strength", 0.8)}}
            src_m, src_c = [nid, 0], [nid, 1]
            new.append(nid)
        for k, n in g.items():
            if k in new:
                continue
            for name, v in n["inputs"].items():
                if v == [ck_id, 0]:
                    n["inputs"][name] = src_m
                elif v == [ck_id, 1]:
                    n["inputs"][name] = src_c
    bad = {n["class_type"] for n in g.values()} - ALLOWED_NODES
    if bad:
        raise JobError(f"workflow uses node types outside the allow-list: {sorted(bad)}")
    return g


# ------------------------------------------------------------------------------------------- ComfyUI client
class Comfy:
    def __init__(self, server, allow_remote=False):
        host = urllib.parse.urlparse(server).hostname or ""
        try:
            loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
        except ValueError:
            loopback = False
        if not loopback and not allow_remote:
            raise SystemExit(f"refusing ComfyUI server {server}: only 127.0.0.1 / localhost is allowed")
        self.server = server.rstrip("/")
        self.client = str(uuid.uuid4())

    def get(self, path, raw=False, timeout=60):
        with urllib.request.urlopen(self.server + path, timeout=timeout) as r:
            data = r.read()
        return data if raw else json.loads(data)

    def post(self, path, payload):
        req = urllib.request.Request(self.server + path, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read())
        except urllib.error.HTTPError as e:
            raise JobError(f"ComfyUI rejected the graph: {e.read().decode(errors='replace')[:1500]}")

    def upload(self, path):
        name = "ghm_" + re.sub(r"[^A-Za-z0-9_.-]", "_", os.path.basename(path))
        boundary = uuid.uuid4().hex
        body = io.BytesIO()
        for field, value in (("overwrite", "true"), ("type", "input")):
            body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{field}\"\r\n\r\n{value}\r\n".encode())
        body.write(f"--{boundary}\r\nContent-Disposition: form-data; name=\"image\"; filename=\"{name}\"\r\n"
                   f"Content-Type: application/octet-stream\r\n\r\n".encode())
        body.write(open(path, "rb").read())
        body.write(f"\r\n--{boundary}--\r\n".encode())
        req = urllib.request.Request(self.server + "/upload/image", data=body.getvalue(),
                                     headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
        with urllib.request.urlopen(req, timeout=120) as r:
            res = json.loads(r.read())
        return f"{res['subfolder']}/{res['name']}" if res.get("subfolder") else res["name"]

    def run(self, graph, timeout=1200):
        pid = self.post("/prompt", {"prompt": graph, "client_id": self.client})["prompt_id"]
        t0 = time.time()
        while True:
            h = self.get(f"/history/{pid}")
            if pid in h:
                st = h[pid].get("status", {})
                if st.get("status_str") == "error":
                    msgs = [m for m in st.get("messages", []) if m and m[0] == "execution_error"]
                    raise JobError(f"ComfyUI execution error: {json.dumps(msgs)[:1500]}")
                if h[pid].get("outputs"):
                    break
            if time.time() - t0 > timeout:
                raise JobError(f"timed out after {timeout}s")
            time.sleep(1.0)
        imgs = []
        for out in h[pid]["outputs"].values():
            for im in out.get("images", []):
                q = urllib.parse.urlencode({"filename": im["filename"], "subfolder": im.get("subfolder", ""), "type": im.get("type", "output")})
                imgs.append(self.get(f"/view?{q}", raw=True))
        return imgs, round(time.time() - t0, 1)

    def stats(self):
        s = self.get("/system_stats")
        dev = (s.get("devices") or [{}])[0]
        return dict(gpu=dev.get("name"), vram_total_gb=round(dev.get("vram_total", 0) / 2 ** 30, 2),
                    vram_free_gb=round(dev.get("vram_free", 0) / 2 ** 30, 2),
                    comfyui=s.get("system", {}).get("comfyui_version"), python=s.get("system", {}).get("python_version"))

    def has_node(self, cls):
        try:
            return cls in self.get(f"/object_info/{urllib.parse.quote(cls)}")
        except Exception:
            return False

    def models(self, folder):
        try:
            return self.get(f"/models/{folder}")
        except Exception:
            return None


# ------------------------------------------------------------------------------------------- job execution
def save_image(data, path_noext, fmt, quality):
    if fmt == "png":
        open(path_noext + ".png", "wb").write(data)
        return path_noext + ".png"
    from PIL import Image
    Image.open(io.BytesIO(data)).convert("RGB").save(path_noext + ".jpg", quality=quality, subsampling=0, optimize=True)
    return path_noext + ".jpg"


def contact_sheet(files, out_path, cols=4, tile_w=300):
    from PIL import Image, ImageDraw
    ims = [Image.open(f).convert("RGB") for f in files]
    th = int(tile_w * ims[0].height / ims[0].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tile_w, rows * (th + 24)), (18, 18, 22))
    d = ImageDraw.Draw(sheet)
    for i, (im, f) in enumerate(zip(ims, files)):
        x, y = (i % cols) * tile_w, (i // cols) * (th + 24)
        sheet.paste(im.resize((tile_w, th)), (x, y + 24))
        d.text((x + 6, y + 5), os.path.basename(f), fill=(235, 225, 200))
    sheet.save(out_path, quality=88)


def process(job_path, ghm_root, comfy, keep_dir):
    raw = json.load(open(job_path, encoding="utf-8"))
    jid = raw.get("job_id", os.path.splitext(os.path.basename(job_path))[0])
    res_dir = os.path.join(ghm_root, "jobs", "results", str(jid) if ID_RE.match(str(jid)) else "invalid_job")
    os.makedirs(res_dir, exist_ok=True)
    manifest = dict(job_id=jid, status="failed", started=time.strftime("%Y-%m-%dT%H:%M:%S%z"), images=[], errors=[])
    try:
        if os.path.splitext(os.path.basename(job_path))[0] != jid:
            raise JobError("file name must be <job_id>.json")
        job = validate(raw, ghm_root)
        manifest["system"] = comfy.stats()
        tpl = json.load(open(os.path.join(ghm_root, "comfyui", "workflows", WORKFLOWS[job["workflow"]]), encoding="utf-8"))
        if "ipadapter" in job["workflow"] and not comfy.has_node("IPAdapterAdvanced"):
            raise JobError("ComfyUI_IPAdapter_plus is not installed (see SETUP_WINDOWS_RTX4060.md, step 5)")
        cache = {}
        files = []
        for r in job["runs"]:
            up = {}
            for key in ("style", "init_image"):
                if r.get(key):
                    if r[key] not in cache:
                        cache[r[key]] = comfy.upload(r[key])
                    up[key] = cache[r[key]]
            imgs, secs = comfy.run(build_graph(tpl, r, up))
            for k, data in enumerate(imgs):
                stem = f"{r['id']}_s{r['seed']}" + (f"_{k}" if k else "")
                if keep_dir:                                   # full-quality PNG stays on the PC (gitignored)
                    os.makedirs(os.path.join(keep_dir, jid), exist_ok=True)
                    open(os.path.join(keep_dir, jid, stem + ".png"), "wb").write(data)
                f = save_image(data, os.path.join(res_dir, stem), job["format"], job["quality"])
                files.append(f)
                manifest["images"].append(dict(shot=r["id"], seed=r["seed"], file=os.path.basename(f), seconds=secs))
            print(f"  {r['id']} seed {r['seed']}: {secs}s", flush=True)
        if job["contact_sheet"] and files:
            contact_sheet(files, os.path.join(res_dir, "contact_sheet.jpg"))
        manifest["status"] = "done"
    except urllib.error.URLError:
        raise                                                  # ComfyUI not reachable: no manifest, retried next round
    except (JobError, OSError, KeyError, json.JSONDecodeError) as e:
        manifest["errors"].append(f"{type(e).__name__}: {e}")
        print(f"  job {jid} failed: {e}", flush=True)
    manifest["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    json.dump(manifest, open(os.path.join(res_dir, "manifest.json"), "w", encoding="utf-8"), indent=1)
    return res_dir, manifest


# ------------------------------------------------------------------------------------------- git transport
def git(repo, *args, check=True):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    if check and r.returncode:
        raise RuntimeError(f"git {' '.join(args)} failed: {r.stderr.strip()[:800]}")
    return r.stdout.strip()


def sync(repo, branch):
    git(repo, "fetch", "--quiet", "origin", branch)
    if git(repo, "rev-parse", "--abbrev-ref", "HEAD") != branch:
        git(repo, "checkout", "--quiet", branch)
    git(repo, "rebase", "--quiet", f"origin/{branch}")


def publish(repo, branch, res_dir, jid):
    rel = os.path.relpath(res_dir, repo)
    git(repo, "add", "--", rel)
    if not git(repo, "status", "--porcelain", "--", rel):
        return
    git(repo, "-c", "user.name=GHM local worker", "-c", "user.email=ghm-worker@localhost", "commit", "--quiet", "-m",
        f"Illustration results: {jid}", "--", rel)
    for attempt in range(4):
        try:
            git(repo, "pull", "--quiet", "--rebase", "origin", branch)
            git(repo, "push", "--quiet", "origin", f"HEAD:{branch}")
            return
        except RuntimeError as e:
            print(f"  push attempt {attempt + 1} failed: {e}", flush=True)
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("could not push results; they are committed locally and will be pushed next round")


def pending(ghm_root):
    q = os.path.join(ghm_root, "jobs", "queue")
    if not os.path.isdir(q):
        return []
    out = []
    for f in sorted(os.listdir(q)):
        if f.endswith(".json"):
            jid = f[:-5]
            if not os.path.exists(os.path.join(ghm_root, "jobs", "results", jid, "manifest.json")):
                out.append(os.path.join(q, f))
    return out


def check(comfy):
    st = comfy.stats()
    print(json.dumps(st, indent=1))
    if st["vram_total_gb"] and st["vram_total_gb"] < 7.5:
        print("WARNING: less than 8 GB VRAM reported; start ComfyUI with --lowvram")
    for cls in ("IPAdapterAdvanced", "IPAdapterUnifiedLoader", "UpscaleModelLoader"):
        print(f"node {cls}: {'ok' if comfy.has_node(cls) else 'MISSING'}")
    for folder, need in (("checkpoints", "sd_xl_base_1.0.safetensors"), ("upscale_models", "RealESRGAN_x4plus.pth"),
                         ("ipadapter", "ip-adapter-plus_sdxl_vit-h.safetensors"),
                         ("clip_vision", "CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors")):
        have = comfy.models(folder)
        print(f"model {folder}/{need}: {'ok' if have is not None and need in have else ('unknown' if have is None else 'MISSING')}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", default=os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..")))
    ap.add_argument("--branch", default="ccr-1badfb87-5pxi90")
    ap.add_argument("--server", default="http://127.0.0.1:8188")
    ap.add_argument("--allow-remote-server", action="store_true", help="only for a ComfyUI on your own LAN/VPN")
    ap.add_argument("--interval", type=int, default=60)
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--no-git", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--keep", default=None, help="folder for full-quality PNG copies (default: comfyui/candidates)")
    a = ap.parse_args()
    comfy = Comfy(a.server, a.allow_remote_server)
    if a.check:
        check(comfy)
        return
    repo = os.path.abspath(a.repo)
    ghm_root = os.path.join(repo, "great_history_makers")
    keep = a.keep or os.path.join(ghm_root, "comfyui", "candidates")
    print(f"GHM worker: repo {repo}, branch {a.branch}, ComfyUI {a.server}. Ctrl+C to stop.", flush=True)
    while True:
        try:
            if not a.no_git:
                sync(repo, a.branch)
            for jp in pending(ghm_root):
                print(f"job {os.path.basename(jp)}", flush=True)
                res_dir, m = process(jp, ghm_root, comfy, keep)
                print(f"  -> {m['status']}, {len(m['images'])} images", flush=True)
                if not a.no_git:
                    publish(repo, a.branch, res_dir, m["job_id"])
        except (RuntimeError, urllib.error.URLError) as e:
            print(f"round failed: {e}", flush=True)
        if a.once:
            break
        time.sleep(a.interval)


if __name__ == "__main__":
    sys.exit(main())
