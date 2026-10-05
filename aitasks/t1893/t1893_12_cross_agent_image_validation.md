---
priority: medium
effort: medium
depends: [t1893_5]
issue_type: chore
status: Ready
labels: [codex, opencode, codeagent, claudeskills]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

Review item E9. Framework promotion is already done: the helper is in all 5
whitelist touchpoints, and thin wrappers were generated with
`aitask_audit_wrappers.sh` in:

- `.agents/skills/aitask-screen-recording/` (Codex and agy);
- `.opencode/skills/aitask-screen-recording/`;
- `.opencode/commands/aitask-screen-recording.md`.

What remains unverified is **how each agent actually reads the sheets and
frames**. This child depends on the picker (t1893_5), so the new AskUserQuestion
step is validated too.

## Known gap, found during t1888 planning

`.agents/skills/codex_tool_mapping.md:9` maps `Read(file)` to
`functions.exec_command("cat <file>")`. **Codex therefore cannot view the
contact sheets through the wrapper today.** Codex does have
`functions.view_image` (`aidocs/codeagents/codexcli_tools.md:142-146`).

## Key files

- `.agents/skills/codex_tool_mapping.md` and
  `.opencode/skills/opencode_tool_mapping.md`. **These are shared by all skills;
  assess the impact of any change.**
- `.claude/skills/aitask-screen-recording/SKILL.md` (the "Read the results in
  this order" section, about lines 52–62).
- `aidocs/codeagents/*_tools.md`.
- `video_prep.py`: `SHEET_MAX_EDGE = 1600` (line 30).

## Scope and acceptance

1. **Codex.**
   - Add an image-reading mapping: images map to `functions.view_image(path)`,
     one path per call. Images are not read with `cat`.
   - Make SKILL.md name the **exact paths** to view, because the Codex model
     often won't call `view_image` unless a path is spelled out
     (openai/codex#12439).
2. **OpenCode.** `read` returns jpeg/png/gif/webp as attachments, but **not
   SVG**. Make sure SKILL.md points every agent at `plot.png`, not `plot.svg`
   (`plot.png` exists only when `magick` is present; say so).
3. **agy.**
   - Images are read via `@path` references, or by asking the agent to open them.
   - The CLI *may* accept video directly (pasting a screen recording is
     documented); this is unverified.
   - Measure it. If video works, hedge the skill's premise ("coding agents read
     images, not video") rather than state it absolutely.
4. **Claude image tiers.**
   - Standard models (e.g. Haiku 4.5, Sonnet 4.6, Opus 4.6) allow 1568 px **and**
     1568 tokens, so a 1600×1600 sheet is downscaled to about 1092 px. Claude 4.7
     and later allow 2576 px and 4784 tokens.
   - Measure label legibility (`-pointsize 15`) on a standard-tier model.
   - Decide whether `SHEET_MAX_EDGE` should drop to ≤ 1568 or become tier-aware.
     Record the decision and its evidence.
5. **AskUserQuestion mapping** for the picker question (t1893_5):
   - Codex `request_user_input`: ≤ 3 questions, 4 options each, available in
     default mode;
   - OpenCode `ask`.

   Verify that the question renders and that the answer routes correctly.
6. **Manual runs.** One run per agent (Codex, OpenCode, agy) on a fixture
   recording, in bug and anim modes, following the skill end to end. Record the
   per-agent results in the plan's final notes.

## Facts (verified 2026-10-05)

- **Codex `view_image`** (codex-rs source): "Attach a local image (by filesystem
  path)". One required `path`, plus optional `detail` (`high` / `original`).
  Images are resized to a max of 2048 px / 2500 patches at high detail, or
  6000 px / 10000 patches at original. Accepts PNG, JPEG, GIF and WebP. It fails
  on Windows under the sandbox (#31248).
- **OpenCode `read`** (`packages/opencode/src/tool/read.ts`): images become
  base64 data-URL attachments with no size cap. It returns an error text when the
  model lacks image input.
- **agy** (antigravity.google CLI docs and changelog 1.2.14 / 1.2.17): `@path`
  references; scales PNG, JPEG and WebP to fit its limits.
- **Claude vision** (platform.claude.com Vision page): the two tiers above.
  Requests with more than 20 images **reject** oversized images rather than
  downscaling them; ≤ 2000 px is safe. Max 600 images per API request (100 for
  200k-context models), 20 per claude.ai message. 10 MB per image.

## Docs

Add a per-agent notes section on the website page: how each agent views sheets,
known limits, and the video caveat for agy. This is an allowed exception to the
generic-agent prose rule, because the list *is* the documentation (see
`aidocs/framework/documentation_conventions.md`).

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

> **✉ note:t1893_1** id=2026-10-05T20:27:57Z.361e3d54760ece90acfe1d64 from=t1893_1 from_verified=yes at=2026-10-05T20:27:57Z base=a7295cd3db2f9219c94b28dcaee663f925e6d94e base_branch=main dirty=no host=omg16
>
> | Docs layout for the screen-recording skill changed in t1893_1 (user decision during planning; docs commit 6cad6b0a8). Advisory context for this task's "Website documentation is part of the deliverable" rule:
> | 
> | - Reference material lives at website/content/docs/skills/aitask-screen-recording.md: Modes, per-mode Options tables (shared bug+anim / bug only / anim only), Output layout, "Time basis under --time-scale" table, "Warnings and limits" table (exact strings), Requirements, Privacy.
> | - Use-case walkthroughs live in a workflow section: website/content/docs/workflows/screen-recordings/ (_index.md overview, bug-report.md, animation.md, recording-tips.md).
> | - So "add a how-to section to the skill page" now plausibly means: add or extend a workflow subpage (list it in the section _index.md "Walkthroughs" list and in the "Screen Recordings" group of website/content/docs/workflows/_index.md), and add new flags / outputs / warnings to the skill page's reference tables. The section _index.md has a "More use cases" placeholder for this.
> | - Verification used in t1893_1, which may be reusable: a per-command-line, per-mode flag check against `<mode> --help` (catches e.g. `info ... --out`), plus checking claims against the writer code in video_prep.py rather than --help alone. Anything time-related under --time-scale should state its time basis (durations/fits are converted; timestamps, curve.tsv, window_s, frame names and --window/--range stay in recording time).
> | 
> | Tree-relative claims, dated by the base commit recorded on this note. The archived plan aiplans/archived/p1893/p1893_1_*.md has the full notes.
