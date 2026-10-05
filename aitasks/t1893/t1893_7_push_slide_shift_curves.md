---
priority: high
effort: medium
depends: [t1893_6]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

Review item E5 (high value for animations; push and slide is the most common
transition type). v1 measures progress from bounding boxes of change against
the start and end pictures, which is exact for element slides including
overshoot, or from a blend ratio, which is exact for fades. A **full-screen**
push or slide changes every pixel, so neither signal is meaningful there, and
v1 falls back to the blend proxy. This child adds shift estimation for that case.

## Key files

- `vp_core.py`:
  - `diff_stats` (about line 151) and `edge_tracks` (about line 193);
  - `analyze_frames` (about line 520) and its `signal` selection (`auto|edge|blend`);
  - `fit_motion` (about line 432).
- `video_prep.py`: the anim `--signal` choices (about line 770 onward);
  `--analysis-pixels` (160_000).
- `tests/screen_recording_synth.py`:
  - `bug_frames()` (about line 161) already contains a push transition
    (FastOutSlowIn, 300 ms);
  - `_screen(c, kind, xoff=…)` (about line 137).

## Scope and acceptance

1. Add a `shift` progress signal. It estimates the horizontal or vertical
   displacement between each frame and the start/end pictures by **1-D profile
   matching**: correlate the column or row intensity profiles of downscaled
   frames. Keep it stdlib-only; downscaled rows are enough. Report progress as
   displacement divided by total displacement.
2. `--signal auto` picks `shift` when the change covers almost the whole frame and
   the content is translated rather than blended. `run.json` and the summary
   name the chosen signal and why. `--signal shift` forces it.
3. The confidence is reported, as a correlation peak quality. When it is low, the
   summary warns rather than presenting the curve as exact, for example for
   parallax, or content that changes during the push.

## Tests

- The existing push transition in `bug_frames` (FastOutSlowIn, 300 ms):
  - the fitted duration is within the existing ±12 ms tolerance;
  - FastOutSlowIn wins among the named curves;
  - `auto` selects `shift`.
- A left and a down variant, to exercise both axes.
- A negative case, a full-screen crossfade: `auto` does **not** choose `shift`.

## Docs

Extend the "implement an animation" how-to with full-screen transitions. Cover:

- what the `shift` signal measures;
- when it is chosen;
- how to read its confidence.

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

> **✉ note:t1893_1** id=2026-10-05T20:27:44Z.49f091b354ff73ebb249d468 from=t1893_1 from_verified=yes at=2026-10-05T20:27:44Z base=6cad6b0a893a6b2440a9151f6f8a72a923d7369e base_branch=main dirty=yes host=omg16
>
> | Docs layout for the screen-recording skill changed in t1893_1 (user decision during planning; docs commit 6cad6b0a8). Advisory context for this task's "Website documentation is part of the deliverable" rule:
> | 
> | - Reference material lives at website/content/docs/skills/aitask-screen-recording.md: Modes, per-mode Options tables (shared bug+anim / bug only / anim only), Output layout, "Time basis under --time-scale" table, "Warnings and limits" table (exact strings), Requirements, Privacy.
> | - Use-case walkthroughs live in a workflow section: website/content/docs/workflows/screen-recordings/ (_index.md overview, bug-report.md, animation.md, recording-tips.md).
> | - So "add a how-to section to the skill page" now plausibly means: add or extend a workflow subpage (list it in the section _index.md "Walkthroughs" list and in the "Screen Recordings" group of website/content/docs/workflows/_index.md), and add new flags / outputs / warnings to the skill page's reference tables. The section _index.md has a "More use cases" placeholder for this.
> | - Verification used in t1893_1, which may be reusable: a per-command-line, per-mode flag check against `<mode> --help` (catches e.g. `info ... --out`), plus checking claims against the writer code in video_prep.py rather than --help alone. Anything time-related under --time-scale should state its time basis (durations/fits are converted; timestamps, curve.tsv, window_s, frame names and --window/--range stay in recording time).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_1_*.md has the full notes.
