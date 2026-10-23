# Great History Makers autopilot

Daily 9:16 history Shorts produced in Claude Code cloud sessions, with the client approving scripts
weekly and every video before publishing. Lives entirely in `great_history_makers/` and stays separate
from the LensPrompt Android project in the same repository.

| File | Purpose |
|---|---|
| `AUTOPILOT.md` | Runbook the daily session follows (gates, steps, delivery) |
| `TOPICS.json` | Weekly script queue; only `approved` entries are produced |
| `batches/<week>/<id>/` | Script batch: `NARRATION.txt`, `CONCEPT.md` (storyboard + history check + sources), `episode.json` |
| `BUDGET.json` | Standing ElevenLabs budget (inactive until the client authorises it) |
| `LEDGER.json` | Credits actually spent |
| `pipeline.py` | Free stages after narration: check, align, timeline, render, brand, verify |
| `make_selftest.py` / `selftest_cyrus/` | End-to-end test on existing Episode 01 assets, no credits |
| `../tools/verify_delivery.py` | Objective delivery checks: narration audible and synced, captions aligned and burned in, original logo present |

## Flow
```
weekly:  Claude drafts 7 scripts  ->  client approves in TOPICS.json
daily:   09:00 Brussels scheduled cloud session (fresh)
         pick approved script -> pipeline check (free)
         -> ElevenLabs connector: estimate, then 1 take within BUDGET (paid)
         -> align -> shots/scenes -> timeline -> 720p preview + fixes -> 1080p final -> brand -> verify
         -> push branch ghm/daily/<date>-<id> -> notify client
client:  reviews the branded final -> publishes (manual)
```

## Costs (estimates)
- ElevenLabs eleven_v4: about 1 credit per character, priced by the connector at about $0.02 per 100 credits
  (Ep02: 838 credits = $0.168). The W44 scripts average about 690 characters.
- Claude: cloud sessions use the client's Claude plan; no separate container charge. Building new scenes is
  the expensive part. See the final report for the 30-video estimate.
- Rendering, music, SFX, alignment, branding: local and free.
