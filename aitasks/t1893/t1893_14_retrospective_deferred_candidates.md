---
priority: low
effort: low
depends: [t1893_9, t1893_11, t1893_12, t1893_13]
issue_type: chore
status: Ready
labels: [claudeskills, task-planning]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

This is a retrospective evaluation child, per
`aidocs/framework/planning_conventions.md` ("Plan split: in-scope sibling
children…"). It runs once every other child of t1893 has landed and the skill has
been in daily use.

## Scope

1. Re-evaluate each deferred candidate from
   `aidocs/screen_recording_skill_design_review.md` §4 against real usage
   evidence:
   - **E6**: separate opacity and position channels;
   - **E10**: OCR mode (RapidOCR vs tesseract);
   - **E11**: sub-agent describers for recordings over about 2 minutes;
   - **E12**: Perfetto FrameTimeline;
   - **E13**: opt-in Gemini "describe". If kept, it must be strictly opt-in per
     file and never triggered by an API key in the environment.
2. Also check:
   - how often narration, folder input, the picker and logcat alignment were
     actually used;
   - whether the reported uncertainty, `heuristic` and "unverified" labels proved
     useful;
   - the state of t1165 (Chatlink video intake), which owns review item E8.
3. For each candidate, record a decision with its evidence: create a standalone
   task (`--followup-of` the parent), or record "no action" with the reason. Do
   not create tasks speculatively.

## Done when

The plan's Final Implementation Notes list every candidate with its decision and
the evidence behind it, plus any tasks created.

## Docs

Only if a decision changes the documented behaviour.

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
