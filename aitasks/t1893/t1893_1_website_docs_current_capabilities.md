---
priority: high
effort: medium
depends: []
issue_type: documentation
status: Implementing
labels: [website, documentation, claudeskills]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:40
---

## Context

The user wants everything the v1 skill does documented on the website **now**,
not deferred. This is review item E14, promoted to an early, standalone task. It
is the first child of t1893. Every later child adds its own how-to section to the
page this task creates.

## Key files

- **New:** `website/content/docs/skills/aitask-screen-recording.md`.
- `website/content/docs/skills/_index.md`: add a row in the `## Skill Overview`
  category that fits best (likely "Design" or "Task Implementation"). Use the
  row form ``| [`/aitask-screen-recording`](aitask-screen-recording/) | … |``.
- Sources of truth, read and do not change unless they are wrong:
  - `.claude/skills/aitask-screen-recording/SKILL.md`;
  - `references/animation.md` and `references/recording.md`;
  - `video_prep.py` `build_parser()` (about line 740) for the real flags.

## Reference pattern

`website/content/docs/skills/aitask-note.md`:

- front matter: `title` / `linkTitle: "/aitask-screen-recording"`, `weight`,
  `description`, `maturity: [experimental]`, `depth: [intermediate]`;
- sections: intro, `**Usage:**`, Step-by-Step, Key Capabilities, When to Use,
  Related.

## Scope and acceptance

1. Explain what the skill does and why: coding agents read images. Hedge the
   claim that they can't read video, because the agy CLI may accept video
   directly (unverified, 2026-10-05). Describe the three modes `info`, `bug` and
   `anim`, and how the helper is invoked.
2. Add a **how-to section for each use case**:
   - a bug report from a recording (bug mode; reading `summary.md`, then the
     sheets, then individual frames; citing frames in reports);
   - implementing an animation from a prototype recording (anim mode; fitted vs
     visible duration; named curves, cubic-bezier and spring fits);
   - slowed capture with `--time-scale N`;
   - narrowing the analysis with `--crop-top` / `--crop-bottom` (status-bar clock
     noise), `--roi X,Y,W,H`, `--window START-END` (anim) and `--range START-END`;
   - recording tips (from `references/recording.md`: Android `screenrecord` /
     scrcpy, show taps, iOS, desktop);
   - limits, and how to read each warning the helper prints;
   - output layout (`summary.md`, `timeline.tsv`, `run.json`, `sheet_NN.png`,
     `frames/`, per-segment `curve.tsv`, `fit.json`, `plot.*`) and the current
     default location `$TMPDIR/video-prep/<stem>-<mode>`, which `--out` overrides.
3. List the requirements: ffmpeg and ffprobe are required; ImageMagick `magick` is
   optional (without it there are no sheets and the plot is SVG only).
4. Leave a clearly titled place where later children add their how-tos (frames,
   sheet, picker, and so on), but do not document unshipped features.

## Facts (verified 2026-10-05)

- Android `screenrecord`: the default `--time-limit` is 180 s. From Android 14
  the cap is gone and `0` means no limit. This comes from AOSP
  `cmds/screenrecord/screenrecord.cpp`; developer.android.com still says
  "Maximum: 180". `--bugreport` overlays local wall-clock `HH:MM:SS.mmm` and a
  frame counter on every frame.
- logcat with epoch timestamps: `adb logcat -v threadtime,epoch,usec`.
- Claude image limits (platform.claude.com, Vision page):
  - standard models: 1568 px **and** 1568 tokens;
  - Claude 4.7 and later: 2576 px and 4784 tokens;
  - token cost ≈ ⌈w/28⌉·⌈h/28⌉.

  Mention budgets generically on the page; don't hard-code per-model numbers.

## Verification

- Every flag named on the page appears in `aitask_screen_recording.sh <mode> --help`.
- `cd website && python3 check_links.py --build` passes.
- `hugo build --gc --minify` passes.
- Optionally run `python3 check_link_relevance.py` and triage what it reports.

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
