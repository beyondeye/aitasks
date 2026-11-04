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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1893_1** id=2026-10-05T20:27:51Z.1cea6de8aa5ee940b215ed71 from=t1893_1 from_verified=yes at=2026-10-05T20:27:51Z base=a7295cd3db2f9219c94b28dcaee663f925e6d94e base_branch=main dirty=no host=omg16
>
> | Docs layout for the screen-recording skill changed in t1893_1 (user decision during planning; docs commit 6cad6b0a8). Advisory context for this task's "Website documentation is part of the deliverable" rule:
> | 
> | - Reference material lives at website/content/docs/skills/aitask-screen-recording.md: Modes, per-mode Options tables (shared bug+anim / bug only / anim only), Output layout, "Time basis under --time-scale" table, "Warnings and limits" table (exact strings), Requirements, Privacy.
> | - Use-case walkthroughs live in a workflow section: website/content/docs/workflows/screen-recordings/ (_index.md overview, bug-report.md, animation.md, recording-tips.md).
> | - So "add a how-to section to the skill page" now plausibly means: add or extend a workflow subpage (list it in the section _index.md "Walkthroughs" list and in the "Screen Recordings" group of website/content/docs/workflows/_index.md), and add new flags / outputs / warnings to the skill page's reference tables. The section _index.md has a "More use cases" placeholder for this.
> | - Verification used in t1893_1, which may be reusable: a per-command-line, per-mode flag check against `<mode> --help` (catches e.g. `info ... --out`), plus checking claims against the writer code in video_prep.py rather than --help alone. Anything time-related under --time-scale should state its time basis (durations/fits are converted; timestamps, curve.tsv, window_s, frame names and --window/--range stay in recording time).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_1_*.md has the full notes.

> **✉ note:t1893_2** id=2026-11-04T16:10:25Z.1a9d420e0bd8d57b70dd89f9 from=t1893_2 from_verified=yes at=2026-11-04T16:10:25Z base=6042779808cd0febd56020cf7c08f398bf2582e2 base_branch=main dirty=yes host=omg16
>
> | Timeline basis for bug-mode output (from t1893_2, code commit 0dee3ebb3). Advisory context for the wall-clock ladder / logcat merge:
> | 
> | - Every bug-mode frame time and every freeze/black/silence interval time (timeline.tsv, summary.md, run.json, frame file names) is on ffmpeg's NORMALISED timeline. Without -copyts, ffmpeg subtracts the input's format start_time (probe()["start_time"]) before filtering, so these times start near 0. They are not raw container pts. Measured: an mpegts clip with start_time=1.433333 decodes from 0. A logcat merge that assumes raw pts would be off by start_time.
> | - ffprobe packet times are raw. core.video_span() normalises them (pts - start_time), takes coverage from the packet with the latest presentation time (demux order is not presentation order with B-frames), and cross-checks the origin against the first kept frame, failing closed.
> | - probe() resolves ONE video stream (the default-disposition track, else the first): probe()["vindex"]. Every video ffmpeg/ffprobe call maps it (_vmap()), so a multi-track file is measured on one track throughout.
> | - run.json records video_end_s / video_end_proven (the end of the analysed video span, from that stream's packets, not the container duration, which can be a longer audio track's).
> | - Known gap, not fixed there: cmd_anim still uses end_t = start_time + duration (follow-up t2202).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_2_*.md ("Notes for sibling tasks") has the details.

> **✉ note:t2202** id=2026-11-04T17:10:01Z.46e39d8bb95d1a6dc2097116 from=t2202 from_verified=yes at=2026-11-04T17:10:01Z base=df7647f796a4869f15e2b057d683c2b6909634a8 base_branch=main dirty=yes host=omg16
>
> | Update to the t1893_2 note above (advisory). It said "Known gap, not fixed there: cmd_anim still uses end_t = start_time + duration (follow-up t2202)". That gap is now closed by code commit df7647f79.
> | 
> | - cmd_anim (.aitask-scripts/screen_recording/video_prep.py) now clamps each motion segment's window end with core.video_span(video_packets(...), start_time, range_end=..., ranged=..., first_kept_t, last_kept_t, container_end=info["duration"]).end_t. This is the same call cmd_bug makes. It is computed only when there is at least one segment. The --window path never used the end and is unchanged.
> | - So anim window ends (summary.md "window a-b s" headings, fit.json window_s) are on ffmpeg's NORMALISED timeline (format start_time subtracted), the same basis as bug-mode times. They are bounded by the video stream's own packets, not by a longer audio track's container duration.
> | - Measured on a 0.9 s clip settling at 0.8 s: a start_time=5 clip and a clip with 3 s of audio both gave a window end of 1.05 before the fix and 0.9 after.
> | - anim run.json still does NOT record video_end_s / video_end_proven (bug mode only). If the video end cannot be proven, anim silently falls back to min(container duration, --range end).
> | 
> | Tree-relative claims, dated by this note's base commit. The archived plan aiplans/archived/p2202_*.md has the details.
