---
priority: low
effort: medium
depends: [t1893_7]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

The user answered "mixed / unsure" to "Compose springs or tweens?" (2026-10-05),
and asked for this at **low priority**, after E5 (t1893_7), independently of the
deferred E6.

v1's spring fit assumes the motion starts from rest. That is wrong for
interrupted or retargeted animations and for flings, which start with a nonzero
initial velocity. A zero-velocity fit then mis-estimates stiffness and damping.

## Key files

- `vp_core.py`:
  - `spring` (about line 336);
  - `fit_motion` (about line 432), which picks the nearest Compose preset and a
    SwiftUI response;
  - `scale_fit_time` (about line 492).
- `tests/screen_recording_synth.py`: `spring_progress(k, z, t0)` (about line 89).
- `tests/test_screen_recording_core.py`: the existing spring tests (stiffness
  within 15 %, damping within 0.07, overshoot within 3 points).

## Scope and acceptance

1. Extend the spring model with an initial velocity v0, in progress units per
   second. Fit (stiffness, damping, v0) when it explains the curve meaningfully
   better than v0 = 0, using a stated model-selection criterion such as a
   residual improvement threshold or an information criterion.
2. **Keep the existing zero-velocity behaviour.** The existing tests and
   outputs for spring clips that start from rest stay unchanged: same chosen
   model, same presets, same numbers within tolerance.
3. `fit.json` reports `v0` and **its uncertainty**, and says when v0 and
   stiffness are not separately identifiable (a short visible tail, a clipped
   start). In that case the summary warns, and the zero-velocity fit stays the
   recommendation.
4. The summary says when a nonzero v0 was chosen and what it implies for the
   implementation, e.g. "animate with an initial velocity, or the motion is
   interrupted".

## Tests

- Extend `spring_progress` with a `v0` parameter. Synthetic recordings with known
  v0 (positive and negative) recover v0 within a stated tolerance, with
  stiffness and damping still within the existing tolerances.
- v0 = 0 clips: the existing assertions pass unchanged, and v0 is not selected.
- An ambiguous case (a heavily clipped start) reports non-identifiability rather
  than a confident v0.

## Docs

Add a section on when this fit is useful (interrupted or retargeted animations,
flings, gesture-driven motion) and how its uncertainty is reported and should be
read.

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

> **✉ note:t1893_1** id=2026-10-05T20:27:49Z.f3c4ed30f8988f1011422e0a from=t1893_1 from_verified=yes at=2026-10-05T20:27:49Z base=a7295cd3db2f9219c94b28dcaee663f925e6d94e base_branch=main dirty=no host=omg16
>
> | Docs layout for the screen-recording skill changed in t1893_1 (user decision during planning; docs commit 6cad6b0a8). Advisory context for this task's "Website documentation is part of the deliverable" rule:
> | 
> | - Reference material lives at website/content/docs/skills/aitask-screen-recording.md: Modes, per-mode Options tables (shared bug+anim / bug only / anim only), Output layout, "Time basis under --time-scale" table, "Warnings and limits" table (exact strings), Requirements, Privacy.
> | - Use-case walkthroughs live in a workflow section: website/content/docs/workflows/screen-recordings/ (_index.md overview, bug-report.md, animation.md, recording-tips.md).
> | - So "add a how-to section to the skill page" now plausibly means: add or extend a workflow subpage (list it in the section _index.md "Walkthroughs" list and in the "Screen Recordings" group of website/content/docs/workflows/_index.md), and add new flags / outputs / warnings to the skill page's reference tables. The section _index.md has a "More use cases" placeholder for this.
> | - Verification used in t1893_1, which may be reusable: a per-command-line, per-mode flag check against `<mode> --help` (catches e.g. `info ... --out`), plus checking claims against the writer code in video_prep.py rather than --help alone. Anything time-related under --time-scale should state its time basis (durations/fits are converted; timestamps, curve.tsv, window_s, frame names and --window/--range stay in recording time).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_1_*.md has the full notes.
