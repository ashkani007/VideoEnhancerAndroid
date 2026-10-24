"""Content discovery: find openly licensed narrative films, score them for
Shorts potential, and keep only sources ReelKit may legally reuse.

Providers return `Candidate` dicts. Every provider result is cached (per query,
7 days) so a monthly run of 30-60 Shorts re-queries nothing it already knows.
Network failures are recorded per provider instead of aborting discovery —
in a restricted network you still get the curated + reachable results.

License policy: only CC0 / public domain / CC-BY / CC-BY-SA are eligible.
NC and ND licenses are rejected (monetised Shorts are commercial, and a recap
edit is a derivative). "Standard YouTube license" is never eligible.
"""

from __future__ import annotations

import json
import time
import urllib.parse
from dataclasses import asdict, dataclass, field
from pathlib import Path

import requests

from .util import Cache, Config, write_json

UA = {"User-Agent": "ReelKit/0.1 (open-license discovery)"}
TTL = 7 * 86400

STORY_RUBRIC = {
    "hook": "Can the first 3 seconds pose an irresistible question? (0-5)",
    "conflict": "Mystery, suspense, a surprising decision or emotional conflict (0-5)",
    "visual": "Is the story told clearly in pictures, readable after a 9:16 crop? (0-5)",
    "payoff": "A satisfying reveal / twist / ending that fits in 60 s (0-5)",
    "fit_60s": "Can the arc be compressed to 45-60 s without lying about it? (0-5)",
}


@dataclass
class Candidate:
    title: str
    provider: str
    url: str
    license: str
    license_url: str = ""
    year: int | None = None
    duration_s: float | None = None
    max_height: int | None = None
    download_urls: list[str] = field(default_factory=list)
    synopsis: str = ""
    scores: dict = field(default_factory=dict)
    notes: str = ""
    reachable_here: bool | None = None

    @property
    def total(self) -> float:
        return sum(self.scores.values()) if self.scores else 0.0


def license_ok(cfg: Config, lic: str) -> bool:
    lic = lic.upper().replace(" ", "-")
    if any(x in lic for x in ("NC", "ND", "STANDARD", "ALL-RIGHTS")):
        return False
    return any(lic.startswith(a) for a in cfg.get("discovery.allowed_licenses"))


# --------------------------------------------------------------------- providers


def curated_open_movies(cfg: Config, query: str) -> list[Candidate]:
    path = Path(__file__).with_name("catalog.json")
    return [Candidate(**c) for c in json.loads(path.read_text())]


def internet_archive(cfg: Config, query: str) -> list[Candidate]:
    q = (f"({query}) AND mediatype:movies AND "
         "(licenseurl:*creativecommons.org/licenses/by/* OR licenseurl:*publicdomain*)")
    url = "https://archive.org/advancedsearch.php?" + urllib.parse.urlencode({
        "q": q, "fl[]": ["identifier", "title", "licenseurl", "year", "description", "downloads"],
        "rows": 50, "sort[]": "downloads desc", "output": "json"}, doseq=True)
    docs = requests.get(url, headers=UA, timeout=30).json()["response"]["docs"]
    out = []
    for d in docs:
        lic_url = d.get("licenseurl", "")
        lic = ("PD" if "publicdomain" in lic_url else
               "CC-BY-SA" if "/by-sa/" in lic_url else "CC-BY" if "/by/" in lic_url else lic_url)
        desc = d.get("description", "")
        out.append(Candidate(
            title=d.get("title", d["identifier"]), provider="internet_archive",
            url=f"https://archive.org/details/{d['identifier']}", license=lic, license_url=lic_url,
            year=int(str(d.get("year", "0"))[:4] or 0) or None,
            synopsis=(desc if isinstance(desc, str) else " ".join(desc))[:600]))
    return out


def wikimedia_commons(cfg: Config, query: str) -> list[Candidate]:
    api = "https://commons.wikimedia.org/w/api.php"
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6,
              "gsrsearch": f"{query} filetype:video", "gsrlimit": 50, "prop": "imageinfo",
              "iiprop": "url|size|extmetadata"}
    pages = requests.get(api, params=params, headers=UA, timeout=30).json().get("query", {}).get("pages", {})
    out = []
    for p in pages.values():
        ii = (p.get("imageinfo") or [{}])[0]
        md = ii.get("extmetadata", {})
        out.append(Candidate(
            title=p["title"].removeprefix("File:"), provider="wikimedia_commons",
            url=ii.get("descriptionurl", ""), license=md.get("LicenseShortName", {}).get("value", "?"),
            license_url=md.get("LicenseUrl", {}).get("value", ""),
            duration_s=ii.get("duration"), max_height=ii.get("height"),
            download_urls=[ii["url"]] if "url" in ii else []))
    return out


def youtube_cc(cfg: Config, query: str) -> list[Candidate]:
    """YouTube search restricted to videos the uploader marked CC-BY.
    Uses yt-dlp metadata only (no download here)."""
    import yt_dlp  # optional dependency

    opts = {"quiet": True, "skip_download": True, "extract_flat": False, "noplaylist": True}
    out = []
    with yt_dlp.YoutubeDL(opts) as y:
        res = y.extract_info(f"ytsearch25:{query} creative commons", download=False)
        for e in res.get("entries", []):
            lic = (e.get("license") or "").lower()
            if "creative commons" not in lic:
                continue
            out.append(Candidate(
                title=e["title"], provider="youtube_cc", url=e["webpage_url"], license="CC-BY",
                license_url="https://creativecommons.org/licenses/by/3.0/legalcode",
                duration_s=e.get("duration"), max_height=e.get("height"),
                synopsis=(e.get("description") or "")[:600]))
    return out


PROVIDERS = {
    "curated_open_movies": curated_open_movies,
    "internet_archive": internet_archive,
    "wikimedia_commons": wikimedia_commons,
    "youtube_cc": youtube_cc,
}


def discover(cfg: Config, query: str, out_dir: Path) -> dict:
    cache = Cache(cfg.cache_dir)
    found, report = [], {}
    for name in cfg.get("discovery.providers"):
        key = f"{name}|{query}"
        hit = cache.get("discovery", key)
        if hit and time.time() - hit["at"] < TTL:
            cands = [Candidate(**c) for c in hit["items"]]
            report[name] = {"status": "cached", "count": len(cands)}
        else:
            try:
                cands = PROVIDERS[name](cfg, query)
                cache.put("discovery", key, {"at": time.time(), "items": [asdict(c) for c in cands]})
                report[name] = {"status": "ok", "count": len(cands)}
            except Exception as e:  # network policy, missing optional dep, API change
                cands = []
                report[name] = {"status": "unavailable", "error": f"{type(e).__name__}: {e}"[:300]}
        found += cands

    eligible = [c for c in found if license_ok(cfg, c.license)]
    rejected = [c for c in found if not license_ok(cfg, c.license)]
    eligible.sort(key=lambda c: c.total, reverse=True)
    result = {
        "query": query,
        "providers": report,
        "rubric": STORY_RUBRIC,
        "candidates": [asdict(c) | {"total": c.total} for c in eligible],
        "rejected_for_license": [{"title": c.title, "license": c.license, "url": c.url} for c in rejected],
    }
    write_json(out_dir / "discovery.json", result)
    return result
