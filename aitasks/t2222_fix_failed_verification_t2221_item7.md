---
priority: medium
effort: medium
depends: [1893_5]
issue_type: bug
status: Ready
labels: [verification, bug]
anchor: 1887
followup_kind: verification_failure
created_at: 2026-11-06 14:40
updated_at: 2026-11-06 14:40
---

## Failed verification item from t1893_5

> Light and dark themes are readable; the layout holds at phone width

### Source

- **Manual-verification task:** `aitasks/t2221_manual_verification_pick_visual_frame_picker_followup.md` (item #7)
- **Origin feature task:** t1893_5
- **Origin archived plan:** `aiplans/archived/p1893/p1893_5_pick_visual_frame_picker.md`

### Commits that introduced the failing behavior

- e4619f8ff feature: Add the pick visual frame picker (t1893_5)

### Files touched by those commits

- .aitask-scripts/aitask_screen_recording.sh
- .aitask-scripts/screen_recording/pick_logic.js
- .aitask-scripts/screen_recording/pick_page.html
- .aitask-scripts/screen_recording/pick_ui.js
- .aitask-scripts/screen_recording/video_prep.py
- .aitask-scripts/screen_recording/vp_pick.py
- .claude/skills/aitask-screen-recording/SKILL.md
- tests/test_screen_recording_cli.py
- tests/test_screen_recording_core.py
- website/content/docs/skills/aitask-screen-recording.md
- website/content/docs/workflows/_index.md
- website/content/docs/workflows/screen-recordings/_index.md
- website/content/docs/workflows/screen-recordings/pick-frames.md

### Findings (measured 2026-11-06, commit e4619f8ff)

The failing half of the item is **text contrast on the accent-coloured buttons
and badges** in `pick_page.html`. All of them put white (`#fff`) text on an
accent token, and in dark mode those tokens are lightened, which drops the
contrast. Ratios were measured with headless Chromium (WCAG relative luminance,
`prefers-color-scheme` emulated). The target is WCAG AA, 4.5:1 for normal text;
the badges are 11px bold and the button text is 13px, so the large-text 3:1
exception does not apply.

| element | CSS | light | dark |
|---|---|---|---|
| Copy button (`button.act.primary`) | `#fff` on `--sel` | 5.55 | **2.74** (`#6c9cf0`) |
| S badge (`.badge.start`) | `#fff` on `--start` | **4.38** (`#1f8a4c`) | **2.25** (`#4cc27f`) |
| E badge (`.badge.end`) | `#fff` on `--end` | 5.44 | **3.03** (`#ef6b5b`) |
| + badge (`.badge.check`) | `#fff` on `--sel` | 5.55 | **2.74** (`#6c9cf0`) |
| N badge (`.badge.note`) | `#fff` on `--muted` | not measured | not measured (`#a0a097` in dark looks low too) |

Bold = below 4.5:1. The light-theme S badge is in scope as well: 4.38:1 is below
the 4.5:1 target.

All other text measured at or above 5.0:1 in both themes (header, group headings,
card names and labels, preview info, ROI status, note field, other buttons, copy
block, `kbd`).

### Passing half — keep it

The phone-width part of the item **passed** and must not regress: at 390 px,
`document.documentElement.scrollWidth == innerWidth` and no element extends past
the right edge; the grid becomes 2 columns and the side panel (preview, note,
buttons, copy block) stacks below the grid, per the `max-width: 820px` media
queries. The light theme is otherwise fine.

### Fix direction (suggested, not prescribed)

- Give the accent fills their own text colour in dark mode (dark ink on the
  lightened accents), or keep white text and use darker fills for the badge and
  primary-button backgrounds only, leaving `--sel`/`--start`/`--end` for borders
  and outlines.
- Darken the light-theme `--start` slightly so white on it reaches 4.5:1.
- Check the N badge (`--muted` fill) in both themes as well.
- Add a regression check that computes these ratios in both colour schemes
  (the existing headless-Chromium page test in `tests/test_screen_recording_cli.py`
  is the natural home), plus the 390 px no-overflow check.

The full measurement log is in `aiplans/p2221_manual_verification_auto.md`
(item 7) until t2221 is archived, then under `aiplans/archived/`.

### Next steps

Reproduce the failure locally (see the commits and files above, and the origin archived plan for implementation context), identify the offending change, and fix. This task was auto-generated from a manual-verification failure in t2221 item #7.
