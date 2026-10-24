"""ReelKit CLI.

    python -m reelkit discover "dragon short film" --out productions/_discovery
    python -m reelkit acquire <url> --license CC-BY-3.0 --name sintel.mp4
    python -m reelkit analyze sources/sintel.mp4
    python -m reelkit produce sintel-scales              # 480p preview + docs + QC
    python -m reelkit approve sintel-scales --note "ok"
    python -m reelkit final sintel-scales --master /path/Sintel.2010.1080p.mp4
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .util import load_config, run, sha256_file, write_json


def main() -> None:
    ap = argparse.ArgumentParser(prog="reelkit")
    ap.add_argument("--config")
    sub = ap.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("discover"); d.add_argument("query"); d.add_argument("--out", default="productions/_discovery")
    a = sub.add_parser("acquire"); a.add_argument("url"); a.add_argument("--license", required=True)
    a.add_argument("--name", required=True)
    z = sub.add_parser("analyze"); z.add_argument("source"); z.add_argument("--force", action="store_true")
    p = sub.add_parser("produce"); p.add_argument("slug")
    r = sub.add_parser("approve"); r.add_argument("slug"); r.add_argument("--note", default="")
    f = sub.add_parser("final"); f.add_argument("slug"); f.add_argument("--master")
    args = ap.parse_args()
    cfg = load_config(args.config)

    if args.cmd == "discover":
        from .discovery import discover
        res = discover(cfg, args.query, Path(args.out))
        print(json.dumps({"providers": res["providers"],
                          "top": [(c["title"], c["total"], c["license"]) for c in res["candidates"][:3]]}, indent=2))
    elif args.cmd == "acquire":
        from .discovery import license_ok
        if not license_ok(cfg, args.license):
            raise SystemExit(f"refusing: licence {args.license!r} is not in the allowed list")
        if any(h in args.url for h in ("youtube.com", "youtu.be", "vimeo.com")):
            # platform videos: only via yt-dlp, only if the platform itself reports a CC licence
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True}) as y:
                info = y.extract_info(args.url, download=False)
            if "creative commons" not in (info.get("license") or "").lower():
                raise SystemExit("refusing: platform does not report a Creative Commons licence")
            dest = cfg.sources_dir / args.name
            with yt_dlp.YoutubeDL({"quiet": True, "outtmpl": str(dest),
                                   "format": "bv*[height<=2160]+ba/b", "merge_output_format": "mp4"}) as y:
                y.download([args.url])
        else:
            dest = cfg.sources_dir / args.name
            run(["curl", "-sSL", "--fail", "-o", str(dest), args.url])
        rec = {"url": args.url, "license": args.license, "sha256": sha256_file(dest), "path": str(dest)}
        write_json(dest.with_suffix(".source.json"), rec)
        print(json.dumps(rec, indent=2))
    elif args.cmd == "analyze":
        from .analyze import analyze_source
        src = Path(args.source)
        src = src if src.is_absolute() else cfg.workspace / src
        res = analyze_source(cfg, src, force=args.force)
        print(json.dumps({"shots": len(res["shots"]), "contact_sheets": res["contact_sheets"]}, indent=2))
    elif args.cmd == "produce":
        from .produce import produce
        res = produce(cfg, args.slug)
        print(json.dumps({"output": res["output"], "qc": res["qc"]["status"], "render": res["render"]}, indent=2))
    elif args.cmd == "approve":
        from .produce import approve
        print(json.dumps(approve(cfg, args.slug, args.note), indent=2))
    elif args.cmd == "final":
        from .produce import render_final
        res = render_final(cfg, args.slug, Path(args.master) if args.master else None)
        print(json.dumps({"output": res["output"], "qc": res["qc"]["status"]}, indent=2))


if __name__ == "__main__":
    main()
