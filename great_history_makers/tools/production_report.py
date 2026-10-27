"""Milestone production report for external review (for example by another AI reviewer reading the repository).

    py tools/production_report.py reports/milestones/<milestone>.json [--no-frames]

Inputs:
- the milestone note (JSON, written by hand at each milestone): what was completed, problems, costs, next steps,
  decisions needed, and the globs of the rendered videos to report;
- facts measured here: every video is probed with ffprobe (exact filename, duration, resolution, frame rate, size,
  storage location, whether Git tracks it); the latest regression-test results are read from
  ghm4/tests/out/test_report.json (with the time of that run); QC reports next to the videos are summarised.
Outputs (all under reports/, small enough for Git):
- reports/latest.md            human-readable report
- reports/status.json          machine-readable status (schema "ghm-production-status/1")
- reports/previews/<video>_sheet.jpg      contact sheet: 12 frames with timestamps (960 px wide)
- reports/previews/<video>_t<sec>.jpg     4 low-resolution frames (480x270)
- reports/history/<date>_<milestone id>.md    copy of each milestone report
Safety: no credentials, no personal data; the remote URL is used only when it is a plain https://github.com/<owner>/<repo>
address. Large videos are never added to Git by this tool: a video over 95 MB that Git does not track is reported as
"local only" with no link unless the milestone note supplies an approved storage link.
"""
import argparse
import datetime as dt
import glob
import json
import os
import re
import subprocess
import sys

import cv2
import numpy as np

GHM = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORTS = os.path.join(GHM, "reports")
PREV = os.path.join(REPORTS, "previews")
GIT_LIMIT_MB = 95.0


def sh(*cmd, cwd=GHM):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)


def repo_info():
    url = sh("git", "remote", "get-url", "origin").stdout.strip()
    branch = sh("git", "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    commit = sh("git", "rev-parse", "--short", "HEAD").stdout.strip()
    top = sh("git", "rev-parse", "--show-toplevel").stdout.strip()
    m = re.fullmatch(r"https://github\.com/([\w.-]+)/([\w.-]+?)(\.git)?", url)
    vis = None
    return {"remote": f"https://github.com/{m.group(1)}/{m.group(2)}" if m else None, "branch": branch, "commit": commit,
            "subdir": os.path.relpath(GHM, top) if top else ".", "visibility": vis}


def probe(path):
    j = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames",
                                   "-of", "json", path], capture_output=True, text=True, check=True).stdout)
    v = next(s for s in j["streams"] if s["codec_type"] == "video")
    a = next((s for s in j["streams"] if s["codec_type"] == "audio"), None)
    num, den = (int(x) for x in v["r_frame_rate"].split("/"))
    return {"duration_s": round(float(j["format"]["duration"]), 3), "width": v["width"], "height": v["height"],
            "fps": round(num / den, 3), "frames": int(v.get("nb_frames", 0)) or None, "video_codec": v["codec_name"],
            "audio_codec": a["codec_name"] if a else None, "size_mb": round(int(j["format"]["size"]) / 1e6, 1)}


def grab(path, t, w):
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{t:.3f}", "-i", path, "-frames:v", "1", "-vf", f"scale={w}:-2",
                          "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True).stdout
    return cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)


def label(img, text):
    x, y = 7, img.shape[0] - 8
    cv2.rectangle(img, (x - 4, y - 14), (x + 9 * len(text) + 2, y + 5), (0, 0, 0), -1)      # solid backing, no ghosting
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (90, 210, 255), 1, cv2.LINE_AA)


def previews(path, info, stem):
    d = info["duration_s"]
    ts = [d * (k + 0.5) / 12 for k in range(12)]
    tiles = []
    for t in ts:
        im = grab(path, t, 320)
        if im is None:
            im = np.zeros((180, 320, 3), np.uint8)
        label(im, f"{int(t // 60)}:{t % 60:05.2f}")
        tiles.append(im)
    rows = [np.hstack(tiles[i:i + 3]) for i in range(0, 12, 3)]
    head = np.full((34, rows[0].shape[1], 3), 24, np.uint8)
    cv2.putText(head, f"{os.path.basename(path)}  {info['width']}x{info['height']}  {info['duration_s']:.2f}s", (8, 23),
                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (225, 236, 240), 1, cv2.LINE_AA)
    sheet = os.path.join(PREV, f"{stem}_sheet.jpg")
    cv2.imwrite(sheet, np.vstack([head] + rows), [cv2.IMWRITE_JPEG_QUALITY, 78])
    frames = []
    for t in (d * 0.15, d * 0.4, d * 0.65, d * 0.9):
        im = grab(path, t, 480)
        if im is not None:
            p = os.path.join(PREV, f"{stem}_t{t:07.2f}.jpg")
            cv2.imwrite(p, im, [cv2.IMWRITE_JPEG_QUALITY, 72])
            frames.append(os.path.relpath(p, GHM))
    return os.path.relpath(sheet, GHM), frames


def qc_for(path):
    """QC summary from a qc_report.json written for this video (map reels: map_reels/<ch>_qc/), if any."""
    stem = os.path.basename(path)
    m = re.search(r"_Ch(\d)_", stem)
    cands = glob.glob(os.path.join(os.path.dirname(path), "map_reels", f"ch{m.group(1)}_qc", "qc_report.json")) if m else []
    cands += glob.glob(os.path.join(os.path.dirname(path), "qc*", "qc_report.json"))
    if not cands:
        return None
    r = json.load(open(cands[0]))
    warns = [f for s in r.get("shots", []) for f in s.get("flags", []) if f[0] == "WARN"] + [g for g in r.get("global", []) if g[0] == "WARN"]
    return {"errors": r.get("errors", 0), "warnings": r.get("warnings", 0), "frames_checked": r.get("frames"),
            "warning_text": [w[1] for w in warns][:5], "report": os.path.relpath(cands[0], GHM)}


def tests():
    p = os.path.join(GHM, "ghm4", "tests", "out", "test_report.json")
    if not os.path.exists(p):
        return None
    r = json.load(open(p))
    when = dt.datetime.fromtimestamp(os.path.getmtime(p), dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return {"suite": "ghm4.tests.run_all", "run_at": when, "passed": sum(1 for v in r.values() if v.get("passed")),
            "total": len(r), "failed": [k for k, v in r.items() if not v.get("passed")]}


def fmt_dur(s):
    return f"{int(s // 60)}:{s % 60:05.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("milestone")
    ap.add_argument("--no-frames", action="store_true")
    a = ap.parse_args()
    ms = json.load(open(a.milestone, encoding="utf-8"))
    os.makedirs(PREV, exist_ok=True)
    os.makedirs(os.path.join(REPORTS, "history"), exist_ok=True)
    repo = repo_info()
    repo["visibility"] = ms.get("repository_visibility")
    tracked = set(sh("git", "ls-files").stdout.split("\n"))
    videos = []
    for g in ms.get("videos", []):
        for p in sorted(glob.glob(os.path.join(GHM, g))):
            rel = os.path.relpath(p, GHM)
            info = probe(p)
            stem = re.sub(r"[^\w.-]", "_", os.path.splitext(os.path.basename(p))[0])
            sheet, frames = (None, []) if a.no_frames else previews(p, info, stem)
            in_git = rel in tracked
            link = None
            if in_git and repo["remote"]:
                link = f"{repo['remote']}/blob/{repo['branch']}/{repo['subdir']}/{rel}".replace("/./", "/")
            ext = ms.get("external_links", {}).get(rel)
            storage = ("git" if in_git else ("approved_storage" if ext else ("local_only" if info["size_mb"] > GIT_LIMIT_MB else "local_untracked")))
            videos.append(dict(file=os.path.basename(p), path=rel, **info, in_git=in_git, storage=storage,
                               git_url=link, external_link=ext, contact_sheet=sheet, preview_frames=frames, qc=qc_for(p)))
    t = tests()
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    status = {"schema": "ghm-production-status/1", "generated_at": now, "repository": repo,
              "project": ms["project"], "milestone": {k: ms[k] for k in ("id", "title", "date") if k in ms},
              "overall_status": ms.get("overall_status"), "stages": ms.get("stages", []),
              "completed": ms.get("completed", []), "tests": t, "videos": videos,
              "problems": ms.get("problems", []), "costs": ms.get("costs", {}),
              "decisions_needed": ms.get("decisions_needed", []), "next_steps": ms.get("next_steps", []),
              "not_published": True}
    json.dump(status, open(os.path.join(REPORTS, "status.json"), "w"), indent=1, ensure_ascii=False)

    L = [f"# Production report: {ms['project']}", "",
         f"**Milestone:** {ms['title']} (`{ms['id']}`, {ms.get('date', now[:10])})  ",
         f"**Generated:** {now} from commit `{repo['commit']}` on branch `{repo['branch']}`  ",
         f"**Repository:** {repo['remote'] or '(local)'}"
         + (f" ({repo['visibility']})" if repo["visibility"] else "") + f", folder `{repo['subdir']}`  ",
         f"**Overall status:** {ms.get('overall_status', '')}", "",
         "Nothing has been published. The machine-readable version of this report is `reports/status.json`.", ""]
    if ms.get("stages"):
        L += ["## Stages", "| Stage | Status | Note |", "|---|---|---|"] + \
             [f"| {s['name']} | {s['status']} | {s.get('note', '')} |" for s in ms["stages"]] + [""]
    L += ["## Completed in this milestone"] + [f"- {c}" for c in ms.get("completed", [])] + [""]
    L += ["## Tests actually run"]
    if t:
        L.append(f"- Regression suite `{t['suite']}`, last run {t['run_at']}: **{t['passed']}/{t['total']} passed**"
                 + (f"; failed: {', '.join(t['failed'])}" if t["failed"] else "") + ".")
    L += [f"- {x}" for x in ms.get("tests_extra", [])] + [""]
    L += ["## Rendered videos", "| File | Duration | Resolution | Frames | Size | Storage | QC |", "|---|---|---|---|---|---|---|"]
    for v in videos:
        where = {"git": f"Git: [`{v['path']}`]({v['git_url']})" if v["git_url"] else f"Git: `{v['path']}`",
                 "approved_storage": f"[download]({v['external_link']})",
                 "local_only": f"local only (too large for GitHub), `{v['path']}`; no approved storage link",
                 "local_untracked": f"local, not in Git: `{v['path']}`"}[v["storage"]]
        q = v["qc"]
        qs = f"{q['errors']} error(s), {q['warnings']} warning(s)" if q else "–"
        L.append(f"| `{v['file']}` | {fmt_dur(v['duration_s'])} ({v['duration_s']} s) | {v['width']}×{v['height']} @ {v['fps']:g} fps | "
                 f"{v['frames'] or '–'} | {v['size_mb']} MB | {where} | {qs} |")
    L.append("")
    if not a.no_frames and videos:
        L += ["### Contact sheets (12 frames with timestamps each) and preview frames"]
        for v in videos:
            L.append(f"- `{v['file']}`: [contact sheet]({v['contact_sheet'].replace('reports/', '')}), frames: "
                     + ", ".join(f"[{os.path.basename(f).split('_t')[-1][:-4]} s]({f.replace('reports/', '')})" for f in v["preview_frames"]))
        L.append("")
    qc_warn = [(v["file"], w) for v in videos if v["qc"] for w in v["qc"]["warning_text"]]
    if qc_warn or ms.get("qc_notes"):
        L += ["### QC warnings and how they were checked"] + [f"- `{f}`: {w}" for f, w in qc_warn] + \
             [f"- {n}" for n in ms.get("qc_notes", [])] + [""]
    L += ["## Problems and fixes"] + [f"- {p}" for p in ms.get("problems", [])] + [""]
    c = ms.get("costs", {})
    L += ["## Costs"] + [f"- {x}" for x in c.get("lines", [])] + [""]
    L += ["## Decisions needed from the client"] + [f"{i}. {d}" for i, d in enumerate(ms.get("decisions_needed", []), 1)] + [""]
    L += ["## Next steps"] + [f"{i}. {d}" for i, d in enumerate(ms.get("next_steps", []), 1)] + [""]
    if ms.get("review_notes"):
        L += ["## Notes for the reviewer"] + [f"- {d}" for d in ms["review_notes"]] + [""]
    md = "\n".join(L) + "\n"
    open(os.path.join(REPORTS, "latest.md"), "w", encoding="utf-8").write(md)
    open(os.path.join(REPORTS, "history", f"{ms.get('date', now[:10])}_{ms['id']}.md"), "w", encoding="utf-8").write(md)
    total = sum(os.path.getsize(os.path.join(dp, f)) for dp, _, fs in os.walk(PREV) for f in fs) / 1e6
    print(f"reports/latest.md, reports/status.json; {len(videos)} videos; previews {total:.1f} MB")


if __name__ == "__main__":
    sys.exit(main())
