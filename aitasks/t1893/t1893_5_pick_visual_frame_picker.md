---
priority: high
effort: medium
depends: [t1893_4]
issue_type: feature
status: Ready
labels: [python, claudeskills, ui]
anchor: 1887
created_at: 2026-10-05 17:18
updated_at: 2026-10-05 17:18
---

## Context

The user's request (note 2 to t1888, 2026-10-05): a **visual frame picker**, in
HTML and JS, for choosing which animation frames go to the code agent. The
requested flow:

1. The skill extracts frames into a temporary directory.
2. The agent asks whether the user wants to pick frames.
3. If yes, a helper builds an HTML+JS page and opens it.
4. The user selects a subset visually, copies the selection, and pastes it into
   the agent window.

This depends on `frames` (t1893_3), which provides the geometry and hash
manifest, and on `sheet` (t1893_4), which the agent can use to build a sheet of
just the selection.

## Reference implementation (another repository)

`thinking_app#443`, a task in project `thinking_app`, built
`tools/verification/screenshot-review-gallery.sh` and the Python builder
`screenshot-review-gallery.py` (about 1300 lines; read at commit 215e9e4).
Resolve the project with `./ait projects resolve thinking_app`. Never use a
sibling-directory path. What to borrow:

- **No server.** One self-contained static `<out>/index.html`; `--open` opens it.
- **Snapshot first.** Input images are copied and hashed into `<out>/src/` before
  anything is derived, so a concurrent rewrite can't mix versions. The output
  dir is owned and cleaned through a ledger.
- **Browser state is fingerprinted.** Per-card state lives in `localStorage`,
  keyed by a fingerprint of the compared bytes, so a rebuild with new pixels
  starts clean. All storage access is wrapped in try/catch.
- **Clipboard with fallback.** Copy uses `navigator.clipboard.writeText`; when
  that is unavailable, the page shows the text for manual copy.

## Key files

- `video_prep.py`: a new `pick` subparser, plus the HTML builder. Keep the builder
  in Python with the page template embedded, or in a sibling module under
  `.aitask-scripts/screen_recording/`.
- `.claude/skills/aitask-screen-recording/SKILL.md`: the "pick frames?" step.
- `aidocs/framework/skill_authoring_conventions.md`, for the AskUserQuestion
  rules (the visibility rule: everything needed to answer goes inside the widget).
- The tool mappings for the other agents:
  - `.agents/skills/codex_tool_mapping.md`: `request_user_input`, ≤ 3 questions
    and 4 options;
  - `.opencode/skills/opencode_tool_mapping.md`: `ask`.

## Scope and acceptance

1. **Invocation.** `aitask_screen_recording.sh pick <frames-dir|run-dir> [--open] [--out DIR]`
   writes `index.html` with an embedded JSON manifest (paths, t_ms, labels,
   geometry). There is no server.
2. **UI:**
   - a thumbnail grid labelled with time and Δms;
   - click and shift-click range selection;
   - keyboard navigation;
   - a large preview.
3. **The copy block** is paste-ready plain text: the **absolute paths** of the
   selected frames, with t_ms, Δms and an optional per-frame note. The agent then
   reads those paths, which works for every agent.
4. **A selection is not a measurement window, and the picker certifies nothing.**
   - By default the block labels first…last as a **viewing range**.
   - The user can explicitly mark a start frame and an end frame. Only then does
     the block add `--window A-B`, labelled **"user-marked endpoints
     (unverified)"**.
   - There is **no automatic still/settled validation**. A local pixel check
     cannot tell a settled frame from a spring turning point, subpixel motion or
     a duplicated capture frame.
   - The anim run's own endpoint diagnostics stay the authority. SKILL.md tells
     the agent to check them before trusting a user-marked window.
5. **ROI export needs provenance bound to content.**
   - A dragged rectangle becomes `--roi X,Y,W,H` in **source-video pixels** only
     through t1893_3's geometry record (crop offset, scale, source dimensions).
   - That record is trusted only while the hash of the picker's `src/` snapshot
     of the image equals the SHA-256 recorded at extraction.
   - With no record, or a hash mismatch, the source ROI export is **disabled**
     with a visible reason. A mismatch catches any edit, including crop then
     resize back to the same dimensions, and a translation within the same canvas.
   - The page may still offer a rectangle in that image's own pixels, labelled
     as such.
   - Supplying a corrected transform for an edited image is out of scope; record
     that as a documented limitation.
6. **Opener.** One function with a per-platform table: Linux `xdg-open`, macOS
   `open`, and WSL (detect as `ait_is_wsl` does in
   `.aitask-scripts/lib/terminal_compat.sh`). The repo has no existing opener
   helper. With **no display** (an SSH session, or no `DISPLAY`/`WAYLAND_DISPLAY`
   on Linux), print the page path and exit 0. The agent then falls back to
   selecting frames itself; the skill never fails.
7. **SKILL.md.** After extraction, ask whether the user wants to pick frames
   visually, using AskUserQuestion with everything needed inside the widget. On
   "yes", run `pick --open` and wait for the pasted block. On "no", or with no
   display, the agent selects frames itself. Check how this question maps onto
   Codex `request_user_input` and OpenCode `ask`. t1893_12 validates it end to end.
8. **Robustness.** Wrap `localStorage` in try/catch and key it by a content
   fingerprint. When the Clipboard API is unavailable, show the text for manual
   copy.

## Tests

Test the Python builder's output contract. The window and ROI rules live in the
builder and are embedded as data, so they can be tested without JS:

- The manifest holds the expected paths, t_ms, labels and geometry. The `src/`
  snapshot hashes match.
- **A mid-motion-only selection** yields a viewing range and no `--window`.
- **A selection spanning a spring turning point or a duplicated frame pair, with
  no user marks**, is never labelled settled and emits no `--window`.
- User-marked endpoints emit `--window` with the "unverified" label.
- **A `frames --roi` crop with its hash intact** maps a rectangle correctly to
  source pixels, checked against a synthetic element's known position.
- **A same-dimensions geometric edit** (crop then resize back, or a translation
  within the canvas) disables the source ROI export through the hash mismatch.
- **An input with no geometry record** disables the source ROI export.
- No-display fallback: with the opener stubbed and no `DISPLAY`, it prints the
  path and exits 0.

A node-based JS test is this task's call.

At Step 8c, offer a manual-verification follow-up for the real-browser UI:
selection, keyboard, clipboard and the rectangle.

## Docs

Add a how-to: "Pick frames visually and hand them to the agent", covering:

- the flow and the copy block;
- the viewing range vs user-marked window, and what "unverified" means;
- when ROI export is disabled, and why;
- the no-display fallback.

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
