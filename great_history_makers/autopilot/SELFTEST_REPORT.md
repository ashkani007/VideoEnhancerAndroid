# Autopilot self-test (2026-10-23): no paid calls

**Input:** Episode 01 (Cyrus V3) client narration and scenes, used read-only through `autopilot/selftest_cyrus`.
**Run:** `pipeline.py align → timeline → render → brand → verify` (720×1280 preview).

| Stage | Result |
|---|---|
| Alignment | 142 segments, identical to the approved V3 alignment (max difference 0.00 s); line starts within 0.021 s of audio pauses |
| Number reading | "539 BCE" form chosen automatically from candidates; on a copy of Ep02 the four years were chosen correctly and reproduced its alignment exactly |
| Timeline | 18 shots cut from word indices; cuts moved at most 0.34 s versus V3 (now always in a pause) |
| Render | 1720 frames in 367 s (408 s with mix and QC). QC: one borderline "flicker" flag at 10.07 s = a deliberate fast camera move across the marching column (frame difference 7.23 vs threshold 7.22; the same content measures 7.2–8.8 in the approved V3). Not a defect |
| Brand | Original logo watermark and end card applied |
| Verify | PASSED: H.264 720×1280 30 fps, AAC 48 kHz; narration corr 0.977, offset 0.0 ms, speech −14.3 dBFS; 20/20 caption cues detected, cue start vs first word 0 ms, wording identical to the transcript; watermark NCC 0.885 (off-position 0.08), end card NCC 0.997 |

## Negative controls (the verifier must fail these)
| File | Expected failure | Result |
|---|---|---|
| Unbranded master | logo | FAIL logo (NCC −0.02) |
| Audio replaced with silence | narration | FAIL narration (−180 dBFS) |
| Audio delayed 300 ms | narration | FAIL narration (offset 300 ms, corr still 0.976) |
| Audio stream removed | container + narration | FAIL both |
| Caption band painted over | captions | FAIL captions (0/20 cues) |

## Fixes made during the test
- Verifier used the container duration; with longer audio it sampled past the last frame. Now uses the video stream duration.
- `timeline` moved cuts but not their transitions. Transitions now follow their cut.
- `render` continued after a QC flag. It now stops so the frames are inspected before branding.
