"""Optional Claude API integration for unattended runs.

Used for: ranking discovery candidates, captioning contact sheets, and
drafting the narration + shot plan. When no Anthropic credentials are
available, `ask_json` writes the prompt to `<out>.prompt.md` and raises
`NeedsAnswer`; an operator (or an agent session) writes `<out>` and the
pipeline resumes. Answers are cached by prompt hash either way.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import re
from pathlib import Path

from .util import Cache, Config


class NeedsAnswer(RuntimeError):
    pass


def _client():
    try:
        import anthropic
    except ImportError:
        return None
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
            or os.environ.get("ANTHROPIC_PROFILE")):
        return None
    return anthropic.Anthropic()


def ask_json(cfg: Config, prompt: str, out: Path, images: list[Path] | None = None,
             model_key: str = "llm.model", effort: str = "medium") -> dict:
    cache = Cache(cfg.cache_dir)
    model = cfg.get(model_key)
    key = hashlib.sha256((model + prompt + "".join(str(i) for i in images or [])).encode()).hexdigest()
    if out.exists():
        return json.loads(out.read_text())
    if (hit := cache.get("llm", key)) is not None:
        out.write_text(json.dumps(hit, indent=2))
        return hit

    client = _client()
    if client is None:
        out.with_suffix(".prompt.md").write_text(
            prompt + "\n\nImages:\n" + "\n".join(str(i) for i in images or []))
        raise NeedsAnswer(f"No Anthropic credentials: answer {out.with_suffix('.prompt.md')} into {out}")

    content = []
    for img in images or []:
        content.append({"type": "image", "source": {
            "type": "base64", "media_type": "image/jpeg",
            "data": base64.standard_b64encode(Path(img).read_bytes()).decode()}})
    content.append({"type": "text", "text": prompt + "\n\nReply with a single JSON object only."})

    resp = client.beta.messages.create(
        model=model,
        max_tokens=16000,
        output_config={"effort": effort},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
        messages=[{"role": "user", "content": content}],
    )
    if resp.stop_reason == "refusal":
        raise RuntimeError(f"model declined: {getattr(resp, 'stop_details', None)}")
    text = "".join(b.text for b in resp.content if b.type == "text")
    m = re.search(r"\{.*\}", text, re.S)
    data = json.loads(m.group(0) if m else text)
    cache.put("llm", key, data)
    out.write_text(json.dumps(data, indent=2))
    return data
