---
priority: low
effort: low
depends: [t1893_1]
issue_type: enhancement
status: Ready
labels: [ait_setup, python]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

Review item E15. ffmpeg is **not** installed by `ait setup`, and t1887 decided it
should stay a runtime requirement the skill reports, not a framework dependency.
Today the only error is a bare `error: ffprobe not found on PATH` (exit 1),
raised by `run()` catching `FileNotFoundError` (`video_prep.py` about lines
41–45), with no hint about how to install it. A missing `magick` silently
degrades: no sheets, and SVG-only plots.

## Key files

- `video_prep.py`: `run()` (about lines 41–45), `probe()`, `have_magick()` (about
  lines 182–183), `main()` (about lines 791–803).
- `.aitask-scripts/aitask_setup.sh`:
  - `detect_os()` (about line 155; values `macos`, `wsl`, `arch`, `debian`,
    `fedora`);
  - the optional-tool warning precedent for docker (about lines 270–275);
  - per-OS install switches such as `_install_lazygit()` (about lines 4106–4121).

## Scope and acceptance

1. **Preflight in `video_prep.py`**, before `probe()`:
   - check `ffmpeg` and `ffprobe`, and `magick` where the mode needs sheets;
   - on a miss, print **per-OS install commands** (brew / apt / dnf / pacman /
     WSL), detected the same way `detect_os()` is;
   - keep the existing exit code (1).
2. **Version check.** The helper relies on `-fps_mode`, which needs ffmpeg ≥ 5.1.
   An older ffmpeg gets a clear message.
3. **Optional `ait setup` notice.** One `Optional:` line, like the docker
   warning, saying the screen-recording skill needs ffmpeg and ImageMagick.
   **Never install them.**
4. A missing `magick` keeps working without sheets, but the summary now carries
   the install hint as well as the current "read frames/ directly" line.

## Tests

- Run with a `PATH` that hides ffmpeg: the hint appears, the exit code is 1, and
  nothing is written before the failure. The existing
  `test_bad_inputs_fail_cleanly` pattern applies.
- A fake old `ffmpeg -version` on PATH triggers the version message.
- A missing `magick` hint appears in `summary.md`.

## Facts (verified 2026-10-05)

`-fps_mode` arrived in ffmpeg 5.1, and `-vsync` was removed in 9.0. Source:
FFmpeg `fftools/ffmpeg_opt.c` across release branches.

## Docs

Add a "Requirements" section on the website page, with install commands per OS
and what degrades without ImageMagick.

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
