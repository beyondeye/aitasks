---
priority: high
effort: low
depends: [t1893_3]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

The user's request (note 1b to t1888, 2026-10-04): labelled contact sheets built
from **any folder of images, including user-edited ones**, with labels taken
from the filename timestamps.

Today an edited image cannot be fed back. Sheets come only from the original
video, inside bug or anim mode. This child completes the documented
**extract → edit → feed** flow:

1. `frames` (t1893_3);
2. hand edits: crop, annotate, delete;
3. `sheet`;
4. the agent reads the sheets.

## Key files

- `video_prep.py`:
  - `sheet_layout()` and `contact_sheets()` (about lines 186–215);
  - `SHEET_MAX_EDGE = 1600` (line 30);
  - `have_magick()` (about lines 182–183);
  - `build_parser()`.
- The shared filename-timestamp parser from t1893_3, in `vp_core.py`.

## Scope and acceptance

1. `aitask_screen_recording.sh sheet DIR [--per-sheet N] [--out DIR]` builds
   labelled sheets from every image in DIR (png, jpg, webp), ordered by the
   parsed timestamp.
2. Each label carries the parsed time and the **Δms to the previous image**. A
   deleted frame shows up as a larger Δ.
3. A file whose name carries no timestamp falls back to name order with an index
   label, and the summary says so. It is never silently assigned a time.
4. Images of different sizes (because the user cropped them) are letterboxed into
   tiles; nothing is stretched. Sheets stay within `SHEET_MAX_EDGE`.
5. Output: `sheet_NN.png`, plus a small manifest of tiles and labels, and a
   one-line token estimate.
6. Without `magick`, exit non-zero with a clear message. The install hint itself
   is t1893_13's job.

## Tests

- A folder of synthetic PNGs named by `t<ms>`, with one cropped (different size)
  and one deleted. Assert:
  - the sheet count;
  - the tile order;
  - the label text in the manifest, including the larger Δ at the gap.
- A folder with untimestamped names: index labels, and a warning in the summary.
- Skip the sheet assertions when `magick` is absent; keep the manifest and order
  logic testable without it.

## Docs

Add a how-to: "Prepare images by hand, then feed them to the agent". Describe the
full flow:

- `frames --range` to extract;
- edit in any tool, keeping the timestamp in the filename;
- `sheet DIR`;
- the agent reads the sheets.

Also say what the labels mean.

## Rules for every child of t1893

These apply to every child of t1893 (screen-recording skill expansion). They are
copied here so the task stands alone.

- **Website documentation is part of the deliverable.**
  - Update `website/content/docs/skills/aitask-screen-recording.md` (created by
    t1893_1) with a **how-to section for each use case this task enables**.
  - Follow `aidocs/framework/documentation_conventions.md`:
    - current state only, no "previously" prose;
    - agent-generic wording;
    - `{{< relref "/docs/..." >}}` for internal links.
  - After editing, run `cd website && python3 check_links.py --build` and
    `hugo build --gc --minify`.
- **Skill text.** Update `.claude/skills/aitask-screen-recording/SKILL.md` and
  `references/` to match.
  - The `.agents/skills/`, `.opencode/skills/` and `.opencode/commands/` wrappers
    are thin pointers to the Claude skill.
  - Run `./.aitask-scripts/aitask_skill_verify.sh` before committing.
- **Tests.**
  - Use synthetic recordings with known ground truth, built with
    `tests/screen_recording_synth.py` (`Canvas`, `encode(..., vfr=)`, `tween`,
    `spring_progress`, `card_frames`, `bug_frames`).
  - Add them to `tests/test_screen_recording_cli.py` / `_core.py`. Skip when
    ffmpeg/ffprobe are absent, as the existing classes do with
    `@unittest.skipUnless(HAVE_FFMPEG, ...)`.
  - Run with `bash tests/run_all_python_tests.sh --test-dir <dir>`, or run the
    modules directly.
- **Whitelists.**
  - New *subcommands or flags* of `./.aitask-scripts/aitask_screen_recording.sh`
    need no whitelist changes.
  - **A new `.aitask-scripts/*.sh` helper that a skill calls must ship all 5
    whitelist touchpoints as an explicit deliverable**
    (`aidocs/framework/aitasks_extension_points.md`, "Adding a new helper
    script"):
    - `.claude/settings.local.json`
    - `.codex/rules/default.rules`
    - `seed/claude_settings.local.json`
    - `seed/codex_rules.default.rules`
    - `seed/opencode_config.seed.json`
- **Privacy and footprint** (t1887 decisions):
  - never copy a source recording into the repository;
  - never upload anything;
  - ffmpeg stays an optional runtime dependency that the skill reports, never an
    `ait setup` install.
- **Inferred values carry their provenance.**
  - Timestamps, coordinates and measurement windows are exported as exact only
    when the inputs prove them. Otherwise they are labelled (`heuristic`,
    `unknown`, "unverified"), or the export is disabled with a visible reason.
  - Where two requirements can conflict (keep everything vs a budget), state the
    overflow behaviour and add a fixture that forces the conflict.
  - Fixtures must not be chosen to match the assumption under test.
- **Check every documented flag** against the real `<mode> --help` output.
- **Facts below were verified on 2026-10-05** (sources named). Re-check any fact
  this task relies on before writing it into code or docs.
- Background: `aidocs/screen_recording_skill_design_review.md` and the archived
  t1887 plan (`aiplans/archived/p1887_add_screen_recording_skill.md`). The
  parent t1893 records the decisions and the order.
