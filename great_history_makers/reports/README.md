# Production reports (for independent review)

After every completed production milestone, `tools/production_report.py` regenerates:

| File | Content |
|---|---|
| `latest.md` | Human-readable report: stages, completed work, tests actually run (with the time of the last regression run), every rendered video (exact filename, duration, resolution, frame count, size, storage location, QC result), problems and fixes, costs, decisions needed, next steps |
| `status.json` | The same, machine-readable (schema `ghm-production-status/1`) |
| `previews/<video>_sheet.jpg` | Contact sheet per rendered video: 12 frames with timestamps (960 px wide) |
| `previews/<video>_t<seconds>.jpg` | 4 low-resolution frames per video (480×270) |
| `history/<date>_<milestone>.md` | Archive of every milestone report |
| `milestones/<milestone>.json` | The hand-written milestone note the report is built from (measured facts are added by the tool) |

**Rules:**
- Videos over 95 MB are never added to Git. They are listed as "local only" unless an approved storage link is given in the milestone note.
- No credentials, personal files or paid source assets are stored here.
- Nothing is published automatically.

Regenerate a report with: `python tools/production_report.py reports/milestones/<milestone>.json`
