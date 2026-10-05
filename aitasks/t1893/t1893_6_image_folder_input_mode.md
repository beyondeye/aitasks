---
priority: medium
effort: medium
depends: [t1893_5]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

The user's request (note 1c to t1888, 2026-10-04) is to make manual
preprocessing easy end to end. That includes an input mode that takes a
**folder of images**, so bug-style review or anim measurement can run on a
curated sequence instead of the original video.

It builds on:

- the filename-timestamp parser from t1893_3;
- the extract → edit → feed flow from t1893_4.

## Key files

- `video_prep.py`:
  - `common()` (about lines 748–757): `video` currently must be a file;
  - `main()` (about lines 791–803) validates the input;
  - the bug and anim pipelines, which decode through ffmpeg.
- `vp_core.py`:
  - `analyze_frames(times, frames, w, h, *, signal, nominal_dt)` (about line 520);
  - `select_key_frames` (about line 58).

## Scope and acceptance

1. `bug DIR` and `anim DIR` accept a directory of images as well as a video.
   - Order and timing come from filename timestamps (the shared parser).
   - For sequences with no timestamps in their names, `--fps N` supplies the
     timing, and the summary says it is assumed.
   - A directory with neither is an error with a clear message.
2. Anim on a sequence where frames were deleted:
   - detect the gaps from Δt against the median frame interval;
   - warn in the summary, naming where the gaps are;
   - widen the reported duration uncertainty accordingly.

   The timing is never presented as native-frame accuracy when frames are
   missing.
3. Anim needs images of one size. Mixed sizes are an error that says which files
   differ. Bug mode accepts mixed sizes (it only reviews), but sheets follow
   t1893_4's letterboxing.
4. `run.json` records `input: images`, the timing source (filenames vs `--fps`)
   and the gap list.

## Tests

- Round trip: synthetic tween clip → `frames --range` → `anim DIR`. The fitted
  duration matches the video-path result within the existing tolerance.
- Delete every third frame. A gap warning appears, the uncertainty widens, and
  the curve is still the right family.
- `--fps` on untimestamped names works. Mixed sizes in anim are a clean error.

## Docs

Add a how-to: "Review or measure a curated image sequence". Cover:

- when to use it;
- how timing is derived;
- what the gap warning means for measured timing.

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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1893_1** id=2026-10-05T20:27:41Z.ee12b57977f5f20c06134926 from=t1893_1 from_verified=yes at=2026-10-05T20:27:41Z base=6cad6b0a893a6b2440a9151f6f8a72a923d7369e base_branch=main dirty=yes host=omg16
>
> | Docs layout for the screen-recording skill changed in t1893_1 (user decision during planning; docs commit 6cad6b0a8). Advisory context for this task's "Website documentation is part of the deliverable" rule:
> | 
> | - Reference material lives at website/content/docs/skills/aitask-screen-recording.md: Modes, per-mode Options tables (shared bug+anim / bug only / anim only), Output layout, "Time basis under --time-scale" table, "Warnings and limits" table (exact strings), Requirements, Privacy.
> | - Use-case walkthroughs live in a workflow section: website/content/docs/workflows/screen-recordings/ (_index.md overview, bug-report.md, animation.md, recording-tips.md).
> | - So "add a how-to section to the skill page" now plausibly means: add or extend a workflow subpage (list it in the section _index.md "Walkthroughs" list and in the "Screen Recordings" group of website/content/docs/workflows/_index.md), and add new flags / outputs / warnings to the skill page's reference tables. The section _index.md has a "More use cases" placeholder for this.
> | - Verification used in t1893_1, which may be reusable: a per-command-line, per-mode flag check against `<mode> --help` (catches e.g. `info ... --out`), plus checking claims against the writer code in video_prep.py rather than --help alone. Anything time-related under --time-scale should state its time basis (durations/fits are converted; timestamps, curve.tsv, window_s, frame names and --window/--range stay in recording time).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_1_*.md has the full notes.
