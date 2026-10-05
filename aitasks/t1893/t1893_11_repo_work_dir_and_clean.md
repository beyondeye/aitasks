---
priority: medium
effort: low
depends: [t1893_10]
issue_type: enhancement
status: Ready
labels: [python, ait_setup, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

This is review item E7, **redefined by the user** (2026-10-05). The review asked
whether outputs should be stored as task attachments or artifacts. The user
chose neither: outputs go to a **framework-managed temporary directory, like the
existing `.aitask-explain/`** (and `.aitask-shadow/`). Today the default is
`$TMPDIR/video-prep/<stem>-<mode>`.

## Key files

- `video_prep.py`: `make_out_dir` (about lines 238–246); the default output root;
  `build_parser()` (a new `clean` subparser).
- `.gitignore`: add `.aitask-screen-recording/`. Existing entries such as
  `.aitask-explain/` and `.aitask-shadow/` are the precedent.
- `.aitask-scripts/aitask_setup.sh`: add an idempotent rule writer modelled on
  `setup_shadow_store_gitignore()` (about line 2446), and wire it into setup the
  way that one is.
- **Read `aidocs/framework/aitasks_extension_points.md` before editing
  `aitask_setup.sh`.**
- Reference for cleanup: `.aitask-scripts/aitask_explain_cleanup.sh`
  (keep-newest-per-key, `--dry-run`).

## Scope and acceptance

1. The default output root becomes `<repo root>/.aitask-screen-recording/<stem>-<mode>[-N]`.
   The existing "never reuse a non-empty dir" rule stays. `--out` still overrides.
2. **Don't claim a directory is gitignored without checking.** Before writing
   there, the helper runs `git check-ignore -q`.
   - If the directory is not ignored, or the cwd is not a git repository, fall
     back to `$TMPDIR/video-prep/` and print a one-line warning naming the reason.
   - Never write derived output into an unignored path.
3. **`ait setup` adds the `.gitignore` rule in user projects.** It is idempotent,
   commits the same way as the shadow rule, and includes a comment line
   explaining the directory.
4. **`clean [--older-than DUR] [--dry-run] [--all]`** subcommand:
   - prunes run directories under the root;
   - refuses any path that resolves outside the root (symlinks included);
   - prints what it removed, or would remove.

   A subcommand needs no whitelist entries. If a separate `.sh` helper is chosen
   instead, it must ship the 5-touchpoint whitelist checklist.
5. Only derived outputs ever land here. The source recording is never copied into
   the tree. The picker's `src/` snapshot of frames is derived output and is fine.
6. Update SKILL.md, where it currently suggests `--out <scratchpad>/video-prep/...`
   and mentions `$TMPDIR/video-prep/`.

## Tests

- In a scratch git repo with the rule present: output lands under
  `.aitask-screen-recording/`.
- Without the rule, or outside a repo: output falls back to `$TMPDIR`, with the
  warning.
- `clean`:
  - `--dry-run` removes nothing;
  - `--older-than` honours mtimes;
  - a symlink pointing outside the root is refused.
- The setup rule writer is idempotent: running it twice adds one rule. Bash test
  per `tests/` conventions; follow the subshell counter rule in CLAUDE.md if
  needed.

## Docs

Update "where outputs go", and add a how-to: "Clean up old runs".

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

> **✉ note:t1893_1** id=2026-10-05T20:27:55Z.5d53d5f61114283a66befa80 from=t1893_1 from_verified=yes at=2026-10-05T20:27:55Z base=a7295cd3db2f9219c94b28dcaee663f925e6d94e base_branch=main dirty=no host=omg16
>
> | Docs layout for the screen-recording skill changed in t1893_1 (user decision during planning; docs commit 6cad6b0a8). Advisory context for this task's "Website documentation is part of the deliverable" rule:
> | 
> | - Reference material lives at website/content/docs/skills/aitask-screen-recording.md: Modes, per-mode Options tables (shared bug+anim / bug only / anim only), Output layout, "Time basis under --time-scale" table, "Warnings and limits" table (exact strings), Requirements, Privacy.
> | - Use-case walkthroughs live in a workflow section: website/content/docs/workflows/screen-recordings/ (_index.md overview, bug-report.md, animation.md, recording-tips.md).
> | - So "add a how-to section to the skill page" now plausibly means: add or extend a workflow subpage (list it in the section _index.md "Walkthroughs" list and in the "Screen Recordings" group of website/content/docs/workflows/_index.md), and add new flags / outputs / warnings to the skill page's reference tables. The section _index.md has a "More use cases" placeholder for this.
> | - Verification used in t1893_1, which may be reusable: a per-command-line, per-mode flag check against `<mode> --help` (catches e.g. `info ... --out`), plus checking claims against the writer code in video_prep.py rather than --help alone. Anything time-related under --time-scale should state its time basis (durations/fits are converted; timestamps, curve.tsv, window_s, frame names and --window/--range stay in recording time).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_1_*.md has the full notes.
