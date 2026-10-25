# Illustration job queue: how the cloud session and the local PC exchange work

## The short version
The cloud Claude Code session cannot reach your PC, and your PC should not be reachable from the internet.
Both sides therefore talk only **outward to GitHub** over HTTPS, using the repository as a mailbox:

1. Claude writes a job (pure data: prompts, seeds, sizes) to `jobs/queue/<job_id>.json` and pushes it.
2. Your PC runs `comfyui/worker/ghm_worker.py` while you want it to. It fetches the branch, validates the job, runs it on
   ComfyUI bound to `127.0.0.1`, and pushes `jobs/results/<job_id>/` (images, contact sheet, `manifest.json`).
3. Claude pulls the results, reviews them, and queues the next job (for example a 2× upscale of the chosen candidates).

No inbound port, no tunnel, no VPN, no remote desktop. ComfyUI never sees anything except the worker on the same machine.

## Security model
| Risk | Control |
|---|---|
| ComfyUI exposed to the internet | It stays on 127.0.0.1; the worker refuses any non-loopback server unless `--allow-remote-server` is passed |
| A job runs code on the PC | Jobs are data only. Strict schema: unknown keys are rejected; numbers are bounded (size ≤ 1536, steps ≤ 60, ≤ 8 seeds per shot, ≤ 40 images per job) |
| A job reads private files | Reference images must be image files inside `great_history_makers/` (no absolute paths, no `..`, ≤ 25 MB) |
| A workflow template is tampered with | Templates come from an allow-list of four names, and every graph is checked against an allow-list of core node types plus IP-Adapter before it is sent to ComfyUI |
| Stolen GitHub credentials | Use a fine-grained token limited to this one repository with *Contents: read/write* only and an expiry; it lives in Windows Credential Manager, never in the repo |
| Unattended activity | Nothing is scheduled. The worker runs only while its window is open (`--once` runs a single pass) |
| Images or prompts leak | **The repository must be private.** It is public today (see `comfyui/SETUP_WINDOWS_RTX4060.md`, step 0) |
| Paid services | The worker only talks to local ComfyUI and GitHub. It has no API keys and calls no paid service |

Trust boundary: anyone who can push to the branch can queue jobs. Keep push access to yourself (and this Claude session).

## Alternatives considered
| Option | Verdict |
|---|---|
| **Git job queue (this)** | Recommended: works with the cloud session today, asynchronous, auditable history, only outbound HTTPS |
| **Claude Code on the PC** (Claude Desktop app, or `claude remote-control` in the repo folder, which then appears in the Claude Code app) | Good for hands-on sessions: that session runs on your PC and can call ComfyUI at 127.0.0.1 directly. The cloud session still cannot reach the PC; the two sessions share work through the repo |
| Port forwarding / ngrok / Cloudflare quick tunnel to ComfyUI | Rejected: ComfyUI has no authentication; a public URL would let anyone run graphs and custom-node code on your PC |
| Private VPN (Tailscale, WireGuard) | Unnecessary here: the cloud container is not on your VPN, and the queue already needs no inbound access |
| Cloud storage bucket | Possible later for large files (see below); needs a credential on both sides |

## Size budget
Candidates are pushed as JPEG (quality 92, about 0.5–1 MB at 1152 × 2016); upscaled plates as JPEG 95 (about 2–4 MB at
2304 × 4032). A 60-second episode with 10 plates plus 40 candidates is about 50–60 MB. Before monthly volume (30–60 videos),
move `jobs/results/` to Git LFS or a private bucket so the repository does not grow by gigabytes.

## Files
- `queue/<job_id>.json`: written by `python -m ghm4.illustrate job <spec>` (validated with the worker's own checks).
- `specs/<job_id>.json`: the human-readable spec (shot framing, scene, lighting, characters, seeds) the job was built from.
- `results/<job_id>/manifest.json`: status, GPU name, VRAM, ComfyUI version, seconds per image, errors.
- Job ids are immutable: a changed job gets a new id (`_v2`), so results always match the job that produced them.
