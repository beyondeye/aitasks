---
priority: high
effort: medium
depends: [t1893_8]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

Review item E3 (high value for Android bugs). To merge app logs with what the
screen showed, every timeline row needs a wall-clock time. The review proposed
talkthrough's confidence ladder. Plan review on t1888 tightened that ladder:
**recording-time metadata is often heuristic, and must be labelled as such
rather than presented as accurate.**

## Key files

- `video_prep.py`:
  - `probe()` (about lines 88–95) for container tags;
  - timeline and summary writing;
  - `run.json`.
- `vp_core.py`: pure ladder logic and logcat parsing, so they are testable
  without ffmpeg.

## Scope and acceptance

1. **A confidence ladder, with every inference labelled and none presented as
   exact.** The first rung that applies wins:
   1. `--recorded-at <ISO time with zone>` (user-supplied): `explicit`.
   2. QuickTime `com.apple.quicktime.creationdate` (local time with offset): `metadata`.
   3. Container `creation_time`: `heuristic`, **with no stated error bound**.
      - "start = creation_time − duration" is applied **only** under a recorder
        convention this task verifies. The recorder is identified from container
        tags or the encoder string, e.g. Android `screenrecord`.
      - Otherwise the value is reported as a timestamp of unknown meaning, and
        not converted.
   4. File mtime − duration: `heuristic`.
   5. Otherwise: `unknown`. Rows keep `t_ms` and leave `t_wall` empty.
2. Every row gets `t_ms`. `t_wall` is filled only when a rung applied.
   `run.json` records the source and its confidence.
3. `--log logcat.txt`:
   - parses `adb logcat -v threadtime,epoch,usec` output;
   - parses plain `threadtime` (`MM-DD HH:MM:SS.mmm`) only when `--recorded-at`
     supplies the year and zone;
   - interleaves log rows with frame rows in `timeline.tsv` and the summary;
   - offers a level and tag filter so the timeline stays readable.
4. **When the best source is heuristic, interleave anyway, but warn in the
   summary.** The warning:
   - names the source;
   - says the alignment may be off by more than a second (delayed finalisation,
     paused or edited recordings);
   - asks for `--recorded-at`, or a visible on-screen clock such as
     `screenrecord --bugreport`, wherever accuracy matters.

## Tests

Synthetic timestamps are chosen to **break** the convention, not only to match it:

- A fixture log with known epochs plus an explicit `--recorded-at` gives exact
  interleaving order.
- **Ambiguous metadata.** `creation_time` from an unidentified encoder gives
  `heuristic` or `unknown`, never `metadata`, and no fabricated start time.
- **Delayed finalisation.** A clip whose `creation_time` (set with
  `ffmpeg -metadata creation_time=`) lags the true end by several seconds. The
  output carries the heuristic label and the warning, and does not claim accuracy.
- A missing `creation_time` with no other source gives `unknown` and an empty
  `t_wall`.
- A logcat epoch parser test: right-aligned 19-character seconds field,
  `.uuuuuu`, plus the `.mmm` and `nsec` variants.

## Facts (verified 2026-10-05)

- **Android `creation_time`.** AOSP `MPEG4Writer::writeMvhdBox` reads the current
  clock (`time(NULL)`) when it writes the header at finalisation, so the value
  is around the *end* of recording, UTC, 1 s resolution. `screenrecord` sets no
  metadata itself.
  - The 1 s resolution is **not** a bound on alignment error. Finalisation can be
    delayed, and a remux or edit rewrites the value.
  - This comes from reading source; no Android doc states it. Describe it that way.
- **iOS.** `creation_time` (mvhd) is UTC. `com.apple.quicktime.creationdate` is
  local time with an offset, e.g. `2022-11-14T14:23:41+0100`. For iOS *screen*
  recordings (`RPReplay_Final<epoch>.MP4`), whether `creationdate` is present,
  and whether the filename epoch marks the start or the end, is **unverified**.
- **logcat.**
  - `adb logcat -v threadtime,epoch,usec` (equivalently `-v epoch -v usec`) prints
    whole epoch seconds right-aligned in a 19-character field (`%19lld`), then
    `.uuuuuu`.
  - `-T` / `-t` accept `'YYYY-MM-DD hh:mm:ss.mmm'` or epoch `'sssss.mmm'`.
  - Source: AOSP `system/logging` (`logcat.cpp`, `logprint.cpp`) and
    developer.android.com/tools/logcat.
- **`screenrecord --bugreport`** overlays local wall-clock `HH:MM:SS.mmm` plus
  `f=<frame#>` on every frame. This is a manual calibration aid; OCR (E10) is
  deferred.

## Docs

Add a how-to: "Align a recording with logcat". Cover:

- the capture commands;
- `--recorded-at`;
- what each confidence label means;
- when to trust the interleaving.

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
