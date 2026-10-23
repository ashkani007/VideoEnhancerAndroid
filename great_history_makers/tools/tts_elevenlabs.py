#!/usr/bin/env python3
"""Generate an episode narration with the ElevenLabs API (paid: needs explicit client approval).

  python tools/tts_elevenlabs.py episodes/<id>                 # dry run: voice, model, characters, quota
  python tools/tts_elevenlabs.py episodes/<id> --confirm       # spend credits, write audio/narration.mp3

The API key is read ONLY from the environment variable ELEVENLABS_API_KEY (cloud: environment
settings -> secrets/variables; local: `set ELEVENLABS_API_KEY=...` or an untracked .env loaded by
your shell). It is never written to disk, logged or committed.

Text comes from the episode's NARRATION.txt, sent unchanged. Voice and model come from
episode.json "tts" ({"voice_id": ..., "model_id": ...}) or the flags --voice / --model.
After generation run tools/align_narration.py and re-time the shots to the real audio.
"""
import argparse
import json
import os
import shutil
import ssl
import sys
import urllib.request

API = "https://api.elevenlabs.io/v1"


def _ctx():
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    return ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()


def _req(path, key, body=None):
    req = urllib.request.Request(API + path, data=json.dumps(body).encode() if body else None,
                                 headers={"xi-api-key": key, "Content-Type": "application/json"},
                                 method="POST" if body else "GET")
    return urllib.request.urlopen(req, context=_ctx(), timeout=300)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("episode")
    ap.add_argument("--voice")
    ap.add_argument("--model")
    ap.add_argument("--out", default="audio/narration.mp3")
    ap.add_argument("--confirm", action="store_true", help="actually generate (spends credits)")
    a = ap.parse_args()
    cfg = json.load(open(os.path.join(a.episode, "episode.json")))
    tts = cfg.get("tts", {})
    voice = a.voice or tts.get("voice_id")
    model = a.model or tts.get("model_id", "eleven_multilingual_v2")
    text = open(os.path.join(a.episode, "NARRATION.txt"), encoding="utf-8").read().strip()
    if not voice:
        sys.exit("no voice: set episode.json tts.voice_id or pass --voice")
    print(f"voice {voice} | model {model} | {len(text)} characters | {len(text.split())} words")
    key = os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        sys.exit("ELEVENLABS_API_KEY is not set; add it as an environment secret (never paste it into code or chat)")
    try:
        sub = json.load(_req("/user/subscription", key))
        print(f"quota: {sub.get('character_count')} / {sub.get('character_limit')} characters used")
    except Exception as e:  # key may lack the user_read permission
        print(f"quota: unavailable ({e.__class__.__name__})")
    if not a.confirm:
        print("dry run only. Re-run with --confirm after the client approves the spend.")
        return
    out = os.path.join(a.episode, a.out)
    os.makedirs(os.path.dirname(out), exist_ok=True)
    if os.path.exists(out):
        shutil.copy2(out, out + ".bak")
    with _req(f"/text-to-speech/{voice}?output_format=mp3_44100_128", key,
              {"text": text, "model_id": model}) as r, open(out, "wb") as f:
        shutil.copyfileobj(r, f)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
