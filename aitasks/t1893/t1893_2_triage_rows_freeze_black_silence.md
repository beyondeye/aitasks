---
priority: high
effort: low
depends: [t1893_1]
issue_type: feature
status: Ready
labels: [python, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

Review item E2 (high value, small effort). Bug recordings often show a hung
app (frozen screen), a black flash or a silent gap. v1's dwell-based selection
does not label any of these. Today mcp-video-analyzer *drops* black frames;
this child must not, because the black frame may be the bug.

## Key files

- `.aitask-scripts/screen_recording/video_prep.py`:
  - the bug-mode pipeline (`select_key_frames` call site, timeline writing around
    lines 312–384);
  - `run.json` writing (around lines 731–734);
  - `probe()` (around lines 88–95) for stream detection.
- `.aitask-scripts/screen_recording/vp_core.py`: put the pure parsing of the
  detector logs here, so it can be tested without ffmpeg.
- `tests/screen_recording_synth.py`, `tests/test_screen_recording_cli.py` and
  `_core.py`.

## Scope and acceptance

1. Run three ffmpeg detectors in bug mode:
   - `freezedetect=n=-60dB:d=2` (the defaults; expose a flag for the minimum
     duration);
   - `blackdetect=d=0.1:pic_th=0.98:pix_th=0.10` (set `d` explicitly, because
     the default is 2.0 s and would miss flashes);
   - `silencedetect` (`n=-60dB`, `d=2` default), **only when the video has an
     audio stream**.
2. Emit one row per interval into `timeline.tsv`, `summary.md` and `run.json`.
   Each row has a start, an end and the kind (`freeze` / `black` / `silence`).
3. **Black intervals are never lost, but images stay bounded.** This resolves
   "never drop black frames" against `--max-frames`:
   - *every* detected freeze, black and silence interval is kept in the timeline
     and in `run.json`, whatever the frame budget;
   - one representative frame per black interval is picked, ranked **above**
     motion picks inside the `--max-frames` budget;
   - if there are more black intervals than the budget allows, the extra
     intervals keep their timeline rows but get no image. `run.json` records
     `cap_hit: true`, and the summary reports the omitted count and suggests
     narrowing with `--range`;
   - never drop a black interval silently, and never exceed the budget silently.
4. Parse the detector output from ffmpeg's log with the same pts-based timestamps
   v1 uses. Never compute time as index × rate.

## Tests

- A synthetic clip with a frozen span and a black span at known times: each
  interval is detected within ±1 frame.
- Audio: mux a `sine` source with a silent gap (via lavfi) onto a synthetic clip.
  The silence interval is detected; a clip without audio emits no silence rows
  and no error.
- **Budget conflict:** a clip with more black intervals than `--max-frames`.
  Every interval is in `timeline.tsv`, the image count is ≤ the budget,
  `cap_hit` is true, and the omitted count is correct.
- Pure-parse unit tests for the detector-log parser in `_core.py` (no ffmpeg).

## Facts (verified 2026-10-05 against FFmpeg source)

| Filter | Defaults | Logs |
|---|---|---|
| `freezedetect` | `n`/`noise` 0.001 (−60 dB), `d` 2 s | metadata keys `lavfi.freezedetect.freeze_start`, `freeze_duration`, `freeze_end` |
| `blackdetect` | `d` 2.0, `pic_th` 0.98, `pix_th` 0.10 | `black_start: black_end: black_duration:` |
| `silencedetect` | `n` 0.001 (−60 dB), `d` 2 s | `silence_start:` and `silence_end: \| silence_duration:` |

## Docs

Add a how-to: "Spot a hang, a black flash or a silent gap". Cover what each row
means, why black frames are always represented, and what to do when `cap_hit`
is reported.

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

> **✉ note:t1893_1** id=2026-10-05T20:27:32Z.09e7240951f4083f2e303fbb from=t1893_1 from_verified=yes at=2026-10-05T20:27:32Z base=6cad6b0a893a6b2440a9151f6f8a72a923d7369e base_branch=main dirty=yes host=omg16
>
> | Docs layout for the screen-recording skill changed in t1893_1 (user decision during planning; docs commit 6cad6b0a8). Advisory context for this task's "Website documentation is part of the deliverable" rule:
> | 
> | - Reference material lives at website/content/docs/skills/aitask-screen-recording.md: Modes, per-mode Options tables (shared bug+anim / bug only / anim only), Output layout, "Time basis under --time-scale" table, "Warnings and limits" table (exact strings), Requirements, Privacy.
> | - Use-case walkthroughs live in a workflow section: website/content/docs/workflows/screen-recordings/ (_index.md overview, bug-report.md, animation.md, recording-tips.md).
> | - So "add a how-to section to the skill page" now plausibly means: add or extend a workflow subpage (list it in the section _index.md "Walkthroughs" list and in the "Screen Recordings" group of website/content/docs/workflows/_index.md), and add new flags / outputs / warnings to the skill page's reference tables. The section _index.md has a "More use cases" placeholder for this.
> | - Verification used in t1893_1, which may be reusable: a per-command-line, per-mode flag check against `<mode> --help` (catches e.g. `info ... --out`), plus checking claims against the writer code in video_prep.py rather than --help alone. Anything time-related under --time-scale should state its time basis (durations/fits are converted; timestamps, curve.tsv, window_s, frame names and --window/--range stay in recording time).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_1_*.md has the full notes.
