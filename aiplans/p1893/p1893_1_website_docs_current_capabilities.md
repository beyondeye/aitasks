---
Task: t1893_1_website_docs_current_capabilities.md
Parent Task: aitasks/t1893_screen_recording_skill_expansion.md
Sibling Tasks: aitasks/t1893/t1893_2_*.md … aitasks/t1893/t1893_14_*.md
Archived Sibling Plans: aiplans/archived/p1893/p1893_*_*.md
Base branch: main
Output branch: main
---

# Plan: website docs for `/aitask-screen-recording` (t1893_1)

## Context

t1887 shipped the `aitask-screen-recording` skill: the `info|bug|anim` helper,
`video_prep.py` plus `vp_core.py`, and SKILL.md with two references. The website
has no page for it; only the v0.36.1 blog post mentions it. t1893_1 (review item
E14) documents the current capabilities now, so every later t1893 child extends
existing pages.

**User decision (during planning):** use two kinds of page.

- A **skill reference page**: modes, flags, output layout, warnings,
  requirements.
- A **workflow section with subpages** for the actual use cases. Its layout is
  `workflows/screen-recordings/` with `_index.md`, `bug-report.md`,
  `animation.md` and `recording-tips.md`.

Every pending sibling still carries the old rule, "add a how-to section to the
skill page", so each one gets an `ait note` about the new layout.

This task is documentation only. Code and tests stay unchanged. One source of
truth is wrong and gets fixed (Step 3b): `references/animation.md` §6
overstates what `--time-scale` converts.

**Plan-review findings addressed:**

1. The time basis under `--time-scale` is now documented per output field,
   verified against the writers and checked by a scripted slowed-capture run.
2. Log alignment from `adb shell date` is labelled approximate.
3. `info` gets its own usage line, the shared options are scoped to
   `bug`/`anim`, and the flag check runs per mode.

Facts were checked during planning against:

- the real `<mode> --help` output;
- `video_prep.py`: `build_parser()`, `make_out_dir()`, `cmd_bug`, `cmd_anim`
  and `_write_anim_summary`;
- the `vp_core.analyze_frames()` warnings;
- AOSP `screenrecord.cpp`, which confirms the 180 s default and that
  `--time-limit 0` removes the limit.

## Files

1. **New:** `website/content/docs/skills/aitask-screen-recording.md`, the
   reference page.
2. **New:** `website/content/docs/workflows/screen-recordings/_index.md`, the
   overview.
3. **New:** `website/content/docs/workflows/screen-recordings/bug-report.md`.
4. **New:** `website/content/docs/workflows/screen-recordings/animation.md`.
5. **New:** `website/content/docs/workflows/screen-recordings/recording-tips.md`.
6. **Edit:** `website/content/docs/skills/_index.md`: add a row under
   `### Design` and widen its blurb.
7. **Edit:** `website/content/docs/workflows/_index.md`: add a new
   `## Screen Recordings` group.
8. **Edit:** `.claude/skills/aitask-screen-recording/references/animation.md`
   (§6) and `.claude/skills/aitask-screen-recording/SKILL.md` (one line): the
   time-scale correction in Step 3b.

All prose follows `documentation_conventions.md`:

- current state only;
- agent-generic wording; the "agents read images, not video" claim is hedged,
  because some agent CLIs may accept video directly (unverified);
- `{{< relref "/docs/..." >}}` for internal links.

## Step 1: skill reference page (`skills/aitask-screen-recording.md`)

The front matter follows the aitask-note.md pattern:

```yaml
title: "/aitask-screen-recording"
linkTitle: "/aitask-screen-recording"
weight: 115   # after brainstorm-discuss (110), Design group
description: "Turn a screen recording into contact sheets, key frames, a timeline and measured animation timing an agent can read"
maturity: [experimental]
depth: [intermediate]
```

Sections, in order:

- **Intro.**
  - What the skill produces and why: images for *what*, numbers for *when*
    and *how fast*.
  - It triggers when a recording is mentioned or attached.
- **`**Usage:**` block.** `info` gets its own line, because its parser accepts
  only `VIDEO` and `--help` (verified: `info x.mp4 --out /tmp/x` exits 2 with
  "unrecognized arguments"):

  ```
  /aitask-screen-recording                      # or just mention/attach a recording
  ./.aitask-scripts/aitask_screen_recording.sh info VIDEO
  ./.aitask-scripts/aitask_screen_recording.sh bug  VIDEO [--out DIR] [options]
  ./.aitask-scripts/aitask_screen_recording.sh anim VIDEO [--out DIR] [options]
  ./.aitask-scripts/aitask_screen_recording.sh <mode> --help
  ```

  Then the "run from project root" note.
- **`## Step-by-Step`.** For `bug` and `anim` only: pick a mode, run with
  `--out` in scratch space, read `summary.md`, then the sheets, then single
  frames as needed, then the data files, then report. `info` is a one-shot
  probe that writes no directory and no `summary.md`; say so.
- **`## Modes`.** A table:
  - `info`: probe only. JSON goes to stdout and a one-line summary to stderr.
    It takes no options and writes no files.
  - `bug` and `anim`, each with "use it when …".
  - A glitch inside an animation: `bug`, then `anim --window`.
- **`## Options`.** One table per mode, built from the real help. Columns:
  flag, default, effect.
  - Shared by **`bug` and `anim`** (not `info`), and labelled that way:
    `--out`, `--crop-top`, `--crop-bottom`, `--roi`, `--range`, `--decimate`.
  - bug: `--min-dwell` 0.4, `--interval` 1, `--brief-max` 0.12,
    `--max-frames` 40, `--per-sheet` 8, `--view-size` 1000,
    `--extract-audio`.
  - anim: `--window`, `--time-scale` 1, `--signal auto|edge|blend`, `--gap`
    0.12, `--pad` 0.25, `--min-frames` 2, `--max-segments` 8,
    `--max-view-frames` 30, `--per-sheet` 30, `--view-size` 800,
    `--analysis-pixels` 160000.
  - Note under the table: `--roi` takes source pixels in display orientation
    and overrides the crop flags.
- **`## Output layout`.**
  - The bug tree: `summary.md`, `run.json`, `timeline.tsv` (columns
    `idx, time_s, shown_for_s, why, file`), `sheet_NN.png`,
    `frames/NN_<t>s.png`, and optional `audio.wav`.
  - The anim tree: `summary.md`, `run.json`, then `sNN/` (or `w01/` with
    `--window`) holding `frames/fNNN_<t>s.png`, `sheet_NN.png`, `curve.tsv`,
    `fit.json`, and `plot.png` or `plot.svg`.
  - The default location is `$TMPDIR/video-prep/<stem>-<mode>` (`/tmp` when
    `TMPDIR` is unset); `--out` overrides it.
  - A non-empty directory is never overwritten: the output goes to `-2`, `-3`,
    and so on.
  - The last stdout line is `SUMMARY: <path>`.
- **`### Time basis under --time-scale`.** A table of which outputs are in
  recording time and which in real time, verified against the writers in
  `video_prep.py` (`cmd_anim`, `_fit_json`, `_write_curve_tsv`, `_write_plot`,
  `_write_anim_summary`) and `vp_core.scale_fit_time`:

  | Converted to real time (÷ N; spring stiffness × N²) | Left in recording time |
  |---|---|
  | `summary.md`: visible duration and its ± frame interval in the segment table; the `-> <ms>` result of the "visible change" line; every fit row (tween duration, spring settle time, stiffness, Compose preset, SwiftUI response) | `summary.md`: the "starts" column; the first-changed and settled timestamps and the frame interval on the "visible change" line; the segment window header; the cut times |
  | `fit.json`: `visible_duration_ms`, every `fits[]` entry (`duration_ms`, spring params, `compose`, `swiftui_response_s`) | `fit.json`: `window_s`, `frame_interval_ms` |
  | sheet labels: the second line, the ±ms relative to the motion start | sheet labels: the first line, the `<t>s` timestamp |
  | plot x-axis ("ms since fitted start (real time, /N)") | `curve.tsv`: `time_s` **and `t_rel_ms`** |
  | | frame filenames `fNNN_<t>s.png`, and the `--window` / `--range` arguments you pass (always in recording seconds) |

  Add the rule: implement the converted numbers, and pick `--window` /
  `--range` spans from recording-time values.
- **`## Warnings and limits`.** A table with the exact strings from the code,
  their meaning, and what to do about each:
  - bug: dropped picks / `--max-frames`;
  - bug: "Nothing on screen changed";
  - bug: no sheets (`magick` missing);
  - anim: travel spread;
  - anim: full-screen transition proxy;
  - anim: "returns to where it started";
  - anim: "no edge motion found";
  - anim: "video starts mid-motion";
  - anim: segments skipped (`--max-segments`);
  - anim: "fewer than 3 frames in the window";
  - anim: single-frame cuts;
  - anim: "nothing changed … of the window".

  Then the remaining limits from `references/animation.md` §7, and the image
  budget, stated generically: sheets are sized under common downscale limits,
  the summary estimates their token cost, and each frame costs about as much as
  a sheet.
- **`## Requirements`.**
  - ffmpeg and ffprobe 5.1+ on PATH are required; `ait setup` does not install
    them.
  - ImageMagick 7 `magick` is optional. Without it there are no contact sheets
    and the plot is SVG only.
- **`## Privacy`.**
  - Keep `--out` outside the repository.
  - Never copy the recording into the repository.
  - Nothing is uploaded.
- **`## Workflows`.** Links to the three workflow subpages and the overview.
- **`## Related`.** Links to `/aitask-explore` and `/aitask-create`, for
  turning findings into a task, and to `/aitask-pick`.

## Step 2: workflow section `workflows/screen-recordings/`

**`_index.md`**

- Front matter: `title: "Screen Recordings"`, `linkTitle: "Screen Recordings"`,
  `weight: 77` (near bug-report-intake 76),
  `description: "Hand your agent a screen recording: reproduce a bug or implement an animation from it"`,
  `depth: [intermediate]`.
- Body:
  - What the workflow is, with a short flow diagram:
    recording → helper → sheets, frames and numbers → agent reads → report
    or code.
  - Choosing a mode.
  - The reading order.
  - Privacy, in one line.
  - The requirements, with a link to the skill reference.
  - A list of the three subpages.
  - A **`## More use cases`** placeholder: one sentence saying that further
    walkthroughs are added as the skill grows. Unshipped features are not
    named.

**`bug-report.md`**: "Bug Report from a Recording", weight 10.

- **Before you start:** the capture checklist, linking to recording-tips.
- **Run bug mode,** with the command.
- **What the picks mean:**
  - start and end;
  - state (`--min-dwell`);
  - motion (`--interval`);
  - brief (`--brief-max`), which is often the bug.
- **Read the results:** `summary.md` → sheets → frames.
- **Turn it into a report:**
  - numbered steps that cite time and frame
    (`#4 at 5.50 s, frames/04_5.500s.png: …`);
  - visible facts kept separate from inferred causes;
  - then `/aitask-explore` or `/aitask-create` to file the task.
- **Narrow a noisy run.** A symptom→fix table:
  - `--crop-top` / `--crop-bottom`, for status-bar and nav-bar noise; the
    status bar is about 3–4 % of the height. The saved frames still show the
    full screen.
  - `--interval` and `--range`.
  - `--roi`.
  - `--decimate hi=256:lo=128:frac=0.1`, for small changes.
  - `--max-frames`: narrow with `--range` instead of raising the cap.
- **Audio and logs:**
  - audio is detected but not transcribed;
  - `--extract-audio` writes `audio.wav`;
  - `creation_time` is low-confidence;
  - **approximate** alignment with logs: run `adb shell date +%s.%N` right
    before starting the recording and capture logs with
    `adb logcat -v threadtime,epoch,usec`. The clock reading is not the first
    frame's wall-clock time: command and recorder start-up add an unmeasured
    offset. Label log↔frame matches made this way as approximate, and anchor
    them on a visible event, such as a tap shown by `show_touches`, that also
    appears in the log.
  - Exact alignment needs a verified shared timing reference. This page names
    none and adds no synchronisation tooling.
- **A bug inside an animation:** follow up with `anim --window`, linking to
  animation.md.

**`animation.md`**: "Animation from a Prototype Recording", weight 20.

- **Before you start:**
  - one motion per recording, with stillness before and after;
  - measure from source when you can;
  - a link to recording-tips.
- **Run anim mode.**
- **How it measures,** in four short steps:
  - segments, split by `--gap`, with cuts listed separately;
  - native frames plus `--pad`;
  - progress from 0 to 1;
  - the fits.
- **Check the segment:**
  - the sheet;
  - the geometry kind: `edge+`/`edge-`, `grow`/`shrink`, `fade/blend` or
    `returns`, and what each is exact for;
  - `--signal`.
- **Visible vs fitted duration:** implement the fitted one.
- **Choose a curve:**
  - fits within 0.005 RMSE of each other are a tie, so pick the platform's
    named curve;
  - use the custom cubic-bezier only when its RMSE is under half the best
    named curve's and more than 0.01 lower;
  - overshoot above 2 % means a spring (nearest Compose preset, SwiftUI
    response);
  - snap to a token only within one frame.
- **Translate to code:** the Compose, CSS and SwiftUI snippets from SKILL.md.
- **Isolate one element or span:**
  - `--roi`, from the frame-to-source factor and offset in the summary;
  - `--window START-END`: the first frame still before the motion, the last
    frame still after;
  - `--range`;
  - `--analysis-pixels`, for tiny motion;
  - a fade combined with a move: fit `--signal blend` and `--roi` plus
    `--signal edge`, and report both.
- **Slowed capture:**
  - set `animator_duration_scale N`, record, reset, then pass
    `--time-scale N`.
  - Say precisely what is converted. Durations, fits, spring stiffness (× N²),
    sheet-relative ms and the plot axis are converted. Timestamps, `curve.tsv`
    (`time_s`, `t_rel_ms`), `fit.json` `window_s` / `frame_interval_ms`,
    frame filenames and the `--window` / `--range` arguments stay in
    recording time. Link to the skill page's time-basis table.
  - **One worked example**, matching the existing
    `test_time_scale_converts_slowed_recording` fixture: a 300 ms CSS
    ease-out recorded at scale 5.
    - The motion spans about 1.5 s of the recording, so a `--window` must use
      recording seconds, for example `--window 0.3-2.3`.
    - `summary.md` and `fit.json` report about 300 ms.
    - In `curve.tsv`, the settled frame sits at about +1500 `t_rel_ms`. The
      file also holds still context frames before and after the motion, so
      its full extent, about −230 to +1720, is not the motion duration. Say
      that explicitly.
    - Implement 300 ms, not 1500.
    - Fill in the exact numbers from the verification run, not from this
      plan.
  - Results about N× too fast mean the app ignored the scale.
  - Durations 2–10× too long mean a scale was left on.
  - iOS Slow Animations: confirm the factor first.
- **Precision:** ±1 frame (±17 ms at 60 fps). Dropped frames make the timing
  coarser.

**`recording-tips.md`**: "Recording Tips", weight 30. Condensed from
`references/recording.md`.

- **For any recording:**
  - keep still around the action;
  - one thing per recording;
  - Do Not Disturb on;
  - 60 fps or more;
  - measure from source when you can.
- **Android:**
  - `show_touches`, `screenrecord --bit-rate 8M`, then `adb pull`.
  - `--size`.
  - `--time-limit`: the default is 180 s; from Android 14, `0` removes the
    limit.
  - Avoid `--bugreport`: it burns wall-clock time and a frame counter into
    every frame, so every frame registers as a change unless you crop it out.
  - `scrcpy --record … --show-touches`.
  - The slowed-animation commands.
  - logcat alongside the recording.
  - Jank vs design, with a Perfetto FrameTimeline note.
- **iOS:** Control Center capture, `xcrun simctl io booted recordVideo`, and
  Slow Animations.
- **Desktop and web:** OBS, `wf-recorder` and `ffmpeg -f x11grab`; the
  DevTools Animations panel.

## Step 3: index edits

**`skills/_index.md`**

- Change the Design blurb to: "Reason about design proposals before committing
  to one, and read designs and bugs out of screen recordings."
- Add this row:

  ```
  | [`/aitask-screen-recording`](aitask-screen-recording/) | Turn a screen recording into contact sheets, key frames and measured animation timing — for bug reports and for implementing motion |
  ```

**`workflows/_index.md`**

- Add a new group after `## Review & Quality`, using
  `[Screen Recordings](screen-recordings/)`, the same relative form the index
  already uses:

  ```markdown
  ## Screen Recordings

  Hand your agent a screen recording instead of describing it: reproduce a bug from a clip, or implement an animation from a prototype.

  - [Screen Recordings](screen-recordings/) — Overview: choosing a mode, reading order, privacy.
  - [Bug Report from a Recording](screen-recordings/bug-report/) — Key screens, brief glitch frames and a cited step-by-step report.
  - [Animation from a Prototype Recording](screen-recordings/animation/) — Measured duration, easing and spring fits, translated to code.
  - [Recording Tips](screen-recordings/recording-tips/) — Capture a recording that analyses well on Android, iOS and desktop.
  ```

## Step 3b: correct the skill reference's time-scale statement

`.claude/skills/aitask-screen-recording/references/animation.md` §6 says
`--time-scale N` "divides every reported time by N" and that "labels on sheets
and plots are in real time as well". The writers contradict both:

- timestamps, `curve.tsv`, `fit.json` `window_s` / `frame_interval_ms` and
  frame filenames stay in recording time;
- each sheet label's absolute `<t>s` stays in recording time; only its
  relative ms line is converted.

The task allows changing a source of truth that is wrong, so rewrite §6 as two
sentences:

- converted: durations, fits, stiffness × N², sheet-relative ms, plot axis;
- left in recording time: everything else listed above, and the
  `--window` / `--range` arguments.

Add one line to SKILL.md's anim section, after the `--time-scale 5` sentence:
"Timestamps, `curve.tsv` and `--window`/`--range` stay in recording time; only
durations and fits are converted."

The `.agents/` and `.opencode/` wrappers are thin pointers, so nothing to port.
Run `./.aitask-scripts/aitask_skill_verify.sh` before committing anyway, as the
child rules require.

## Step 4: notes to pending siblings (after the docs commit)

Each pending child gets one `./ait note` from t1893_1:

- t1893_2 … t1893_14 (13 notes), sent via the `/aitask-note` composition;
- the body goes in a quoted heredoc.

The body, roughly:

> The docs layout changed in t1893_1:
>
> - The reference lives at `website/content/docs/skills/aitask-screen-recording.md`
>   (modes, options tables, output layout, warnings, requirements).
> - The use-case walkthroughs live under
>   `website/content/docs/workflows/screen-recordings/` (`_index.md`,
>   `bug-report.md`, `animation.md`, `recording-tips.md`).
> - "Add a how-to section to the skill page" now means:
>   - add or extend a workflow subpage, and list it in the section `_index.md`
>     and in `workflows/_index.md`;
>   - add new flags, outputs and warnings to the skill reference tables.
>
> Written against commit <sha>.

The note is advisory. Its claims are tree-relative and dated by commit.

## Verification

- **Scripted flag check.**
  - Extract every `--flag` token from the five new pages.
  - Assert that each appears in the combined
    `aitask_screen_recording.sh {info,bug,anim} --help` output.
  - External-tool flags (`adb`, `screenrecord`, `logcat`, `scrcpy`, `simctl`,
    `x11grab`) go on an explicit allowlist and are checked by eye.
- **Per-mode flag check.** The scripted check runs per command line, not
  against the combined help. For every documented command that names a mode,
  the flags on it must appear in **that mode's** `--help`. This catches
  `info … --out`.
- **Time-basis check against the writers.** A scratch script (not committed)
  does the following:
  - encodes `synth.card_frames(synth.tween(synth.EASE_OUT, 0.5, 1.5), 2.6, "right")`
    with `tests/screen_recording_synth.py`;
  - runs `anim --time-scale 5` on it;
  - asserts that `fit.json` best tween `duration_ms` ≈ 300 and
    `visible_duration_ms` ≈ 300;
  - asserts that `window_s` and `frame_interval_ms` are unscaled (≈ 16.7 ms);
  - checks the motion interval in `curve.tsv`, not its full extent. The TSV
    also holds the still context frames around the motion (pad and fit
    anchors); a review run measured `t_rel_ms` from −233 to +1717, while the
    motion itself is about 1500. `t_rel_ms` = 0 is one frame before the first
    changed frame. Find the settled row: the first row after the motion whose
    `p_fitted_signal` is 1 or more within a small tolerance. Assert that its
    `t_rel_ms` ≈ `visible_duration_ms` × 5, within one recorded frame
    (16.7 ms). That proves the TSV is unscaled while the duration is
    converted;
  - asserts that frame filenames carry recording seconds;
  - when `magick` is present, checks that the `plot.svg` axis label contains
    "(real time, /5)".

  Also run `--window` in recording seconds on the same clip to confirm the
  worked example's window. Every row of the time-basis table is checked
  against this output and the writer code. Then, if ffmpeg is present, run
  `python3 tests/test_screen_recording_cli.py` once as a baseline sanity
  check. No code changes, so this is just a regression check of the
  environment.
- **Per-mode claims match the per-mode help:**
  - `--window`, `--time-scale` and `--signal` are anim-only;
  - `--extract-audio`, `--min-dwell` and `--interval` are bug-only;
  - the defaults in the Options tables match `build_parser()`.
- `cd website && python3 check_links.py --build` passes.
- `cd website && hugo build --gc --minify` passes.
- Optionally run `python3 check_link_relevance.py` and triage the new links.
- `./.aitask-scripts/aitask_skill_verify.sh` passes after the SKILL.md and
  `animation.md` edits.

## Step 9 (Post-Implementation)

- Commit the website files and the two skill-text edits as
  `documentation: Add screen-recording skill and workflow docs (t1893_1)`.
- Commit the plan via `aitask_task_commit.sh`.
- Send the sibling notes (Step 4).
- Archive via the task-workflow Step 9 flow.

## Risk

### Code-health risk: low
None identified. The change adds new docs pages and two index edits; no code,
skill or test changes.

### Goal-achievement risk: low
None identified. Two hazards are covered by the Verification steps:

- documented flags that drift from the code, covered by the per-command,
  per-mode flag check and the defaults check;
- mixed time bases under `--time-scale`, covered by the writer-verified
  time-basis table and the scripted slowed-capture run.

Log alignment is documented as approximate, with its provenance stated.
