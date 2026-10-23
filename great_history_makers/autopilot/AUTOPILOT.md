# Great History Makers autopilot: daily runbook

This file is the instruction set for the scheduled daily session (09:00 Europe/Brussels, **not active
until the client authorises it**). A human-started session can follow it too. Read
`great_history_makers/CLAUDE.md` and the memory files first; every non-negotiable there still applies.

## Scope and separation
- Work only inside `great_history_makers/`. Never touch the Android/LensPrompt project files at the
  repository root (`VideoEnhancerAndroid_GitHubBuild.zip`, `.github/workflows/build-apk.yml`).
- Never push to `main` (the APK workflow runs on `main`). Each run uses its own branch
  `ghm/daily/<YYYY-MM-DD>-<episode-id>` created from the latest GHM branch.
- Never modify `episodes/ep02_napoleon/` or its outputs until the client approves its preview.

## Approval gates (hard rules)
| Action | Allowed when |
|---|---|
| Use a script | Its entry in `autopilot/TOPICS.json` has `status: "approved"` (client-approved weekly batch) |
| ElevenLabs generation | The client's standing budget in `autopilot/BUDGET.json` is `active: true`, the estimate fits the per-video and monthly caps, and only **1 take** is generated |
| Publish anywhere | Never automatically. YouTube auto-publishing is not authorised |
| Recurring jobs | Never create, enable or change scheduled tasks from a daily run |

If any gate fails: stop, write the reason to the run report and notify the client. Do not work around it.

## Daily steps
1. **Pick** the first `approved` topic in `autopilot/TOPICS.json` that has no `produced` date.
   If none is left, report "queue empty" and stop.
2. **Set up** `episodes/<episode-id>/` from the batch folder (`NARRATION.txt`, `episode.json`, `CONCEPT.md`).
   Write `HISTORY.md` from the concept's history check (established, propaganda, disputed, reconstruction).
3. **Pre-flight (free):** `python autopilot/pipeline.py check episodes/<id>`. It must report `ok: true`
   (length 50–63 s, every word pronounceable, voice id set).
4. **Narration (paid, gated):**
   - Price it: ElevenLabs connector `creative_generate_speech` with `estimate_only: true`,
     voice `Gfpl8Yo74Is0W6cPUWWT`, model `eleven_v4`, the NARRATION.txt text unchanged (one line per row).
   - If the estimate is within `BUDGET.json`, generate once with `generations_count: 1`. Never retry
     a generation call; on failure stop and report.
   - Download the take to `episodes/<id>/audio/narration.mp3`. Log credits in `autopilot/LEDGER.json`.
5. **Align (free):** `python autopilot/pipeline.py align episodes/<id>`. It picks the spoken form of each
   number, aligns every word and cross-checks line starts against the audio pauses (`ok` must be true).
6. **Storyboard and scenes:** write `episode.json` `shots` (`at_word` per shot, 14–18 distinct shots, one
   camera intent each) and `scenes.py` from the concept, reusing `mosaic/` libraries (turnrig, shotkit,
   napoleonic costumes as a pattern). Follow STYLE_BIBLE and LESSONS_LEARNED. No re-skinned shots from
   earlier episodes.
7. **Timeline (free):** `python autopilot/pipeline.py timeline episodes/<id>`; then set titles, SFX and
   music cues relative to the new scene starts.
8. **Preview:** `python autopilot/pipeline.py render episodes/<id>` then inspect the contact sheet
   (`tools/shot_sheet.py`) and fix visual defects (faces in the caption band, exposed edges, flat shots).
9. **Final:** `python autopilot/pipeline.py render episodes/<id> --final`, then `brand` and `verify` with
   `--final`. `verify` must pass (audible synced narration, aligned captions, original logo).
10. **Deliver:** deliverables in `output/<id>/deliverables/` (branded MP4 under 100 MB, SRT, contact sheet,
    thumbnail, storyboard, QA report, YouTube metadata). Commit code and metadata; commit the branded
    final only (no masters). Push the run branch.
11. **Learn:** append to LESSONS_LEARNED / FAILED_EXPERIMENTS, add the EPISODE_HISTORY entry, mark the
    topic `produced: <date>` in TOPICS.json.
12. **Report:** a short summary to the client: link to the branch, verify results, credits spent,
    anything that needs a decision. Publishing waits for the client.

## Time budget
Preview render about 7 min, final about 25 min, alignment under 1 min. Scene authoring is the long step.
If a run cannot finish, push what exists with a clear `WIP` report rather than delivering a broken video.
