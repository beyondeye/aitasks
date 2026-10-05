---
priority: high
effort: medium
depends: [t1893_2]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

This covers review item E4 (the `frame` drill-down command, ms-named files and
`cap_hit`) together with the user's request for a `frames` subcommand (note 1a,
relayed to t1888 on 2026-10-04). The user wants to **produce frames, post-process
them by hand (crop, annotate, delete), and then feed them to the agent**.

Today bug mode writes only the frames it picks (`--max-frames`, `--view-size`
1000 px), and anim mode writes the motion ±2 frames, capped by
`--max-view-frames` 30 at 800 px.

This child is the foundation for:

- `sheet` (t1893_4);
- the visual picker (t1893_5);
- folder input (t1893_6).

## Key files

- `video_prep.py`:
  - `build_parser()` (about line 740) gets a new `frames` subparser;
  - `make_out_dir` (about lines 238–246);
  - frame extraction and naming (bug about line 312, anim about line 481);
  - `run.json` (about lines 731–734);
  - `token_estimate()` (about lines 227–235) and `TOKEN_TILE = 28` (line 31).
- `vp_core.py`: the shared filename-timestamp parser (pure, so it is testable).
- `tests/`: the VFR synthetic clip via `encode(..., vfr=True)`.

## Scope and acceptance

1. `aitask_screen_recording.sh frames VIDEO (--range A-B | --at T[,T…]) [--roi X,Y,W,H | --crop-top N --crop-bottom N] [--max-frames N] [--out DIR]`.
   - It writes **every native frame** in the range, or the frame at each `--at`
     time, at **full resolution** (optionally cropped).
   - Decode with `-fps_mode passthrough` (ffmpeg ≥ 5.1).
2. **Filenames carry integer milliseconds taken from the showinfo pts**, e.g.
   `t00007040.png`. Never derive time as index × rate.
3. **A `frames.tsv` manifest with image→source geometry.** For each frame it
   records:
   - `t_ms` and the file name;
   - source video width and height;
   - crop offset (x, y) and crop size;
   - output scale;
   - **the SHA-256 of the image file as written**.

   The hash binds the geometry record to that exact content. t1893_5 trusts the
   geometry only while the current image still hashes to the recorded value.
   bug and anim record the same geometry and hash for the frames they write, in
   `run.json` or a per-frame manifest.
4. **`cap_hit`** in `run.json`:
   - `frames` sets it when `--max-frames` truncates the range;
   - bug sets it from `--max-frames`;
   - anim sets it from `--max-view-frames` and `--max-segments`.

   The summary says what was omitted and how to narrow the range.
5. **One shared filename-timestamp parser** that accepts the new `t<ms>` form and
   the existing `NN_5.500s.png` (bug) and `fNNN_5.500s.png` (anim) names. Keep
   the existing bug/anim names: they already carry millisecond precision and
   SKILL.md cites them.
6. **Image budget.** Print a per-frame token estimate (⌈w/28⌉·⌈h/28⌉, kept in the
   one existing constant). Warn when full-resolution frames exceed the readers'
   limits:
   - Claude standard models: 1568 px and 1568 tokens;
   - Claude 4.7+: 2576 px and 4784 tokens;
   - for example, a 1080×2400 phone frame is downscaled on the standard tier.

## Tests

- Extract at known pts from a synthetic clip, and compare pixels with the frame
  the synthetic generator produced.
- VFR clip: the filename and manifest times match the real pts, not
  index × rate.
- With `--roi`: the manifest geometry is correct, and the hash matches the
  written file.
- `--max-frames` truncation sets `cap_hit`.
- Unit-test the parser on all three name forms, plus garbage names (rejected,
  not misread).

## Facts (verified 2026-10-05)

- `-fps_mode` arrived in ffmpeg 5.1. `-vsync` was deprecated from 5.1 and
  **removed in 9.0** ("Unrecognized option 'vsync'"). Source: FFmpeg
  `fftools/ffmpeg_opt.c` across release branches.
- Claude vision limits are as in point 6 (platform.claude.com Vision page).
  Requests with more than 20 images **reject** oversized images; ≤ 2000 px is safe.

## Docs

Add a how-to: "Extract exact frames for close inspection", covering:

- the full-resolution drill-down at an exact millisecond;
- the meaning of `frames.tsv`;
- token cost;
- that the geometry is valid only for unedited frames.

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
