---
Task: t2278_4_tmux_composite_backend.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-16 18:30
---

# Plan: t2278_4: multi-pane windows and the monitor-family scenes

## Context

Children 2 and 3 shipped the agent-driven capture tool under
`website/screenshots/`: an isolated tmux server per session (`session.py`),
single-pane SVG export (`svg_export.py`), recipes recorded from a clean
discovery session and gated by a fresh replay (`recipe.py`, `cli.py`), and
crop/overlays on cell rectangles (`svgpost.py`). Everything captures **one
pane**. The monitor family (monitor, minimonitor, sitrep) only makes sense as a
**window of several panes** beside believable agent panes. This child extends a
session to several panes and windows, stitches a window into one image, and
records the scenes that need it.

Read first: parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`
(revised 2026-11-15), the archived plans of children 2 and 3 (their "Notes for
sibling tasks" are the API contract), `aidocs/framework/tmux_gateway.md`
(policy 5).

## Verification of the existing plan (2026-11-16)

Checked against the code. Still valid: every file the plan names exists; all
six markers exist (`installation/terminal-setup.md:41`,
`tuis/monitor/_index.md:48` and `:86`, `tuis/monitor/how-to.md:140`,
`tuis/minimonitor/_index.md:14`, `tuis/minimonitor/how-to.md:402`,
`tuis/sitrep/_index.md:12`); `website/` is clean (t2316's `svg_export.py`
change is committed). Findings that change the plan:

1. **Diffviewer is in the real switcher.** `lib/tui_registry.py` marks
   `diffviewer` `in_switcher=True`, so both switcher scenes would show
   "Diff Viewer", which CLAUDE.md keeps out of user-facing docs. **User
   decision:** open a separate task to hide it first; this task does **not**
   capture `tui_switcher_from_monitor` / `tui_switcher_from_minimonitor`.
   CLAUDE.md also says diffviewer "must remain switchable via `j` until the
   brainstorm integration lands", so the new task must reconcile that rule
   (its own planning decides how; it must not be silently broken here).
2. **The monitor marker asks for a shadow column.** Its alt text is "numbered
   callouts on the header, session bar, pane list, preview and shadow columns,
   and footer". So the selected agent needs a shadow companion: a pane
   stamped `@aitask_shadow_target=<agent pane id>`
   (`monitor_core.SHADOW_TARGET_OPTION`), normally spawned by `e` in the
   monitor/minimonitor through `spawn_shadow`.
3. **How the monitor family recognises agents** (from `monitor_core.py` and
   `agent_launch_utils.py`): an agent is a window whose name starts with
   `agent-` (`DEFAULT_AGENT_PREFIXES`); the task id comes from the window name
   (`task_id_from_window_name`, e.g. `agent-pick-14`); a session counts as an
   aitasks session by its `@aitask_project_root` stamp (set by `ait ide`) or
   by a pane vote (panes whose cwd is inside a project). Our panes start in the
   sample project, so the vote alone should recognise the session.
4. **The session name is on screen.** `session.TMUX_SESSION = "shots"` would
   show in the monitor's session bar and `── session ──` dividers. It must be
   the invented project name (`lumen`), and the dataset must set
   `tmux.default_session: lumen` or the monitor offers its rename dialog.
5. **A pane's `PATH` is not set by `-e`** (`aidocs/framework/tmux_gateway.md`
   policy 4, measured): a pane created by an unattached client gets **that
   client's** `PATH`, which overrides `-e PATH=…`; a pane created through an
   attached control client (`tmux -C`, which the monitor uses) gets the
   **server's global** `PATH`. All other variables come from the server's
   global environment. The agent binary is a bare name
   (`aitask_codeagent.sh` `get_cli_binary` → `claude`, resolved on `PATH`), so
   a stand-in `PATH` that does not reach the launched process starts the
   user's **real** agent. The `PATH` must be pinned on the launched command,
   in the server's global environment, and checked, failing closed (step 1).
8. **Pane borders depend on options.** A fresh `-f /dev/null` server has
   `pane-border-indicators colour`, which colours only **half** of the border
   in a window with exactly two panes (tmux 3.8 man page) — the minimonitor
   scene's layout. The stitcher must match the server's configuration, so the
   configuration is pinned and the rule is checked against a real tmux render
   (steps 1, 4, 7).
9. **Pane captures assume the session size.** `session.screen_rows` and
   `cli.export` size every capture from `sess.size`, which stays the window
   size after a split shrinks the main pane, so a pane image would be padded
   and its rectangles validated against the wrong bounds (step 3).
6. **`tests/lib/fake_composer_agent.py` imports `tests/review_loop_fixtures`**,
   and `sample_project` must not import from `tests/` (pinned by
   `tests/test_screenshots_sample_project.py`). The dataset writes its own
   self-contained stand-in script, reusing the composer grammar documented
   there, not the file.
7. There is no tmux client attached to the private server, so anything that
   calls `switch-client` / `attach` (`ait ide`'s attach, the switcher's
   "focus") may fail or no-op there. Step 1 finds out per route.

## Steps

### Pre-phase (risk mitigations)

P1. **`launch_route_probe` — probe every real launch route before writing any
    verb** (inline pre-phase, see `## Risk`). In a scratchpad script on child
    2's session primitives, with the `PATH` pinned as step 1 specifies (on the
    pane's argv and in the server's global environment, never only `-e`) and
    a stand-in `claude` that **logs its identity** (step 2: role, argv,
    `$TMUX_PANE`, pid to `.standin/log`), try each route the four scenes need
    and record, per route, "real route works" or "needs a hand-built window"
    plus what was missing. **A route passes only on stand-in identity, not on
    pane creation:** every agent / shadow pane the route created has a log
    record with the expected role and its `$TMUX_PANE`, and that record's pid
    is the pane's process or a descendant of `#{pane_pid}`. A pane with no
    record is a failure — it may be the user's real agent: the probe kills the
    server at once and reports. Routes:
    - board pick on an `Implementing` task → `agent-pick-<n>` window with the
      stand-in, and the auto-spawned 40-column minimonitor
      (`agent_launch_utils.maybe_spawn_minimonitor`);
    - `./ait sitrep` → `agent-sitrep` window with the stand-in agent, the
      sitrep TUI below at 40%, a full-height minimonitor on the right
      (geometry as in `tests/test_sitrep_window_live.sh:113-222`);
    - `./ait ide` inside the session → a `monitor` window running the real
      monitor (with no attached client);
    - `e` in the monitor on a focused agent → a shadow pane stamped
      `@aitask_shadow_target`, running the stand-in.
    Also record how the framework resolves the agent command (code-agent
    config, model probes) so the shim answers whatever it is asked.
    **Stop rule (from the task):** if the minimonitor does not list the
    stand-in as an agent, or the result does not look like real use, stop and
    report to the user before building anything else. A route that works only
    by hand-building is acceptable only if the hand-built window carries the
    same names and pane options the real code sets; otherwise report it.

1. **Session name, environment, first window** (`website/screenshots/session.py`).
   - `TMUX_SESSION` becomes `sample_project.PROJECT_NAME` (`lumen`).
   - **Stand-in `PATH`, pinned three ways (finding 5), all through
     `TmuxClient`:** when the dataset has a stand-in bin dir
     (`<project>/.standin/bin`), `pane_path = <bin>:<inherited PATH>`.
     1. *On the launched process:* every pane this tool creates (first pane,
        `pane split`, `window new`) runs `env -u COLUMNS -u LINES
        PATH=<pane_path> bash --noprofile --norc`, so its shell and the TUI it
        runs have the stand-in first whatever `PATH` tmux chose; the TUI's own
        unattached tmux clients then pass it to the panes they create.
     2. *In the server's global environment:* right after `start_server`,
        `set-environment -g PATH <pane_path>`, so panes created through a
        control client (the monitor) get it too.
     3. *Setup commands* (`session.setup`, a subprocess) get the same `PATH`.
     **Fail closed:** before the session is handed out, `shutil.which(
     "claude", path=pane_path)` must be the stand-in file, else the server is
     killed and `start` raises. P1 and the live test check identity per route
     (step 2's log). `-e PATH=` is not used. Datasets without a stand-in keep
     today's environment exactly.
   - **Pinned border options (finding 8):** after start, next to `status off`:
     `pane-border-indicators off`, `pane-border-lines single`,
     `pane-border-status off`, and the defaults `pane-border-style default`,
     `pane-active-border-style fg=green` set explicitly, so the stitcher's
     rule depends on nothing implicit. The live test reads them back.
   - `session start --window NAME` (default `shell`) names the first window
     (`new-session -n`); recorded in the recipe as optional `window:`.
   - `Session` gains `panes: dict[role, pane_id]` (first pane is `main`;
     `pane` stays the main pane id, so existing `session.json` files and
     callers work) and a default-empty value for old state files.
   - `write_tasks` writes `tmux:\n  default_session: lumen` into every
     dataset's `project_config.yaml` (finding 4).

2. **`agents` dataset** (`website/screenshots/sample_project.py`). Only what P1
   showed the real TUIs needed; data and the stand-in only:
   - `base` tasks plus: `t14` `Implementing`, `assigned_to:
     alex@example.com`; one more agent task if a scene needs two agents
     (decided by P1/step 6, e.g. `t9`).
   - `.standin/bin/claude`: a self-contained Python script run with
     `$AIT_PYTHON`, no imports from `tests/` or TUI code. From its argv it
     picks a role (`/aitask-pick <n>` → working agent; `/aitask-shadow <pane>`
     → shadow review; `/aitask-sitrep` → sitrep agent) and draws a fixed,
     invented transcript for the sample project plus the Claude-shaped
     composer measured in `tests/lib/fake_composer_agent.py` (full-width `─`
     rule, `❯` + NBSP prompt, rule, status rows), redrawn on SIGWINCH, input
     ignored except `C-c` / `C-d`. No clock, no random text. It also answers
     any probe P1 found the launcher makes. On start it appends one identity
     record (`role|argv|$TMUX_PANE|pid`) to `<project>/.standin/log`, which P1
     and the live test use to prove a pane runs the stand-in.
   - `.gitignore` in the sample repo ignores `.standin/`.
   - Anything else P1 needed (code-agent config pinning `claude`) goes here as
     metadata, or into recipe `setup:` commands under the setup contract.

3. **Panes and windows** (`session.py`, `cli.py`, journaled).
   - `pane split <id> --name ROLE [--target P] [-h|-v] [-l SIZE] [--full] --
     <command>`: `split-window -d -P -F '#{pane_id}' -t <target>
     [-h|-v] [-l SIZE] [-f] -c <project> -e K=V… env -u COLUMNS -u LINES bash
     --noprofile --norc`, then the command is typed in (as `run` does).
     Journal `{kind: pane_split, name, target, direction, size, full,
     command}`. A role name is unique per session.
   - `window new <id> --name N [--role R] -- <command>`: `new-window -d -P -F
     '#{pane_id}' -t <session>: -n N …` with the same pinned env, role
     defaults to `N`. Journal `window_new`.
   - **Addressing (`P`):** a role name created by these verbs (or `main`), or
     a locator `<window_name>.<pane_index>` for panes the TUI itself created
     (minimonitor auto-split, the sitrep window, `ait ide`'s monitor window).
     A locator is resolved at call time from `list-panes -s -F
     '#{window_name}\t#{pane_index}\t#{pane_id}'` and must match exactly one
     pane, else `SessionError` naming the count. Journals and recipes store the
     role or locator, **never a tmux id**.
   - `--pane P` on `screen`, `keys`, `wait`, `find`; `screen --window [NAME]`
     and `find --window [NAME]` read the stitched window text (step 4), so the
     agent gets window-cell coordinates for crops and overlays.
   - **Capture dimensions come from the resolved target, at capture time
     (finding 9).** `pane_geometry(session, P) -> (width, height)` reads
     `#{pane_width} #{pane_height}` for the resolved pane;
     `screen_rows(session, pane=…)` pads / cuts to that height, `screen`
     prints that size, and a pane `export` builds the SVG at that size. A
     window capture uses `#{window_width} #{window_height}`. The size the
     frame was captured at travels with it: crop / overlay rectangles and
     `holds` are checked against **the captured frame's** bounds (a rectangle
     outside them fails the shot / replay with `FAILED:overlay|…`), not
     against `sess.size`. Recipe loading still checks rectangles against the
     recipe `size` (the window, an upper bound); the exact check happens on
     the frame. `sess.size` stays the window size the session was started at.
   - These verbs run after `run` (they are route steps). Every tmux call goes
     through `session.client`; the server is never started here.

4. **`website/screenshots/stitch.py`** (new) and the export path.
   - Pure: `stitch(window_w, window_h, panes) -> list[rich.text.Text]` where a
     pane is `(left, top, width, height, active, ansi)`. Each pane's capture
     goes through **its own** `AnsiDecoder` (SGR carries across lines within a
     pane, never across panes). A decoded row wider than its pane is a
     `StitchError` (capture error); panes overlapping or outside the window
     are a `StitchError`.
   - Border cells are the cells no pane covers. Each gets the box-drawing
     glyph its border neighbours imply (`│ ─ ┼ ├ ┤ ┬ ┴`), and its style follows
     the **pinned** options of step 1 (`pane-border-indicators off`): a border
     cell on the active pane's border gets `pane-active-border-style`, others
     `pane-border-style`. The rule is written for that configuration only, and
     `stitch` refuses (`StitchError`) when the window's options read back as
     anything else (`show-options -gv pane-border-indicators` /
     `pane-border-lines`), so a changed config cannot silently mis-draw.
   - **The rule is checked against real tmux, not against itself.** The live
     test (step 7) renders the same window through a real tmux client: a
     second private server (`ait_shots_<id>_ref`, also started only by
     `start_server`) runs, in a pane of the window's exact size, `env -u TMUX
     tmux -u -L <socket> attach -t <session>` (typed into its shell, like any
     TUI command); `capture-pane -e -N` of that pane is what tmux itself
     drew. The stitched frame's text, border glyphs and border colours must
     equal that render cell for cell, for the two-pane (minimonitor) and the
     three-pane (sitrep) layouts, with each pane active in turn. If they
     differ, the oracle is right and the stitch rule changes.
   - Session side: `window_panes(session, window)` reads geometry with
     `list-panes -t <session>:<window> -F '#{pane_id} #{pane_left} #{pane_top}
     #{pane_width} #{pane_height} #{pane_active}'` and the window size; captures
     each pane with `capture(…, ansi=True)` (`-N`).
   - `svg_export.py`: split `ansi_to_svg` into decode + `rows_to_svg(rows,
     width, height, *, title, scene_id)`; `ansi_to_svg` keeps its signature and
     output. `stitch` output goes through `rows_to_svg`, then
     `svgpost.postprocess` unchanged; pane rectangles are ordinary window-cell
     rectangles for crop / overlays / `holds`.
   - `cli.export` takes a capture source (pane or window). For a window the
     settle check compares two consecutive full window captures (geometry and
     every pane), and `expect` / `holds` are checked on the stitched text of
     the frame that is exported.
   - `shot --window [NAME]` (default: the main pane's window) journals
     `capture: {window: NAME}`.

5. **Recipes** (`website/screenshots/recipe.py`).
   - New optional keys: `window` (first window name) and `capture`
     (`{window: NAME}`; absent = the main pane, as today).
   - New step kinds `pane_split: {name, command, target?, direction?, size?,
     full?}` and `window_new: {name, command, role?}`; `keys` / `wait` /
     `wait_gone` accept an optional `pane:` (long forms `{keys: [...], pane:
     P}` and `{text, pane?, timeout?}`). The short forms load exactly as today,
     so the three shipped recipes load unchanged (tested).
   - Validation: a role used by a step must be created by an earlier step (or
     be `main`, or be a locator); role names unique; `size` like `40` or
     `40%`.
   - `from_session` records the new steps and fields; `replay_one` performs
     them in order. The `recipe save` fresh-replay gate therefore covers them.
   - Module docstring documents the additions.

6. **Scenes, through the discovery workflow** (two passes: explore, then a
   clean walk, `shot --png`, look at the PNG, `recipe save`). Each read from
   its page first; route per scene from P1 (real route preferred):
   - `minimonitor_main_view` (`aitasks_minimonitor_main_view.svg`): the
     `agent-pick-14` window, stand-in left, minimonitor right at 40 columns,
     listing the agent. Page: `tuis/minimonitor/_index.md`.
   - `sitrep_window` (`aitasks_sitrep_tui_main_view.svg`): sitrep agent above,
     sitrep TUI below, full-height minimonitor right. Page:
     `tuis/sitrep/_index.md`.
   - `ait_ide_startup` (`aitasks_ait_ide_startup.svg`): the `monitor` window
     after `./ait ide`, listing the agent windows. Page:
     `installation/terminal-setup.md`.
   - `monitor_layout_annotated` (`aitasks_monitor_layout_annotated.svg`): the
     monitor with an agent focused that has a shadow, so the preview area
     shows preview and shadow columns; `box` overlays with callouts 1-5 =
     the page's numbered list (header, session bar, pane list, preview area
     incl. its shadow column, footer), each with a `holds` text.
   - Every `expect` / `holds` text is stable (task titles, labels), never an
     idle timer or clock.
   - `python3 website/check_screenshots.py`: the four scenes have specs and no
     ownership problem.
   - A scene that cannot be made to look like real use is reported with what
     was found, not faked (task rule).

7. **Tests.**
   - `tests/test_screenshots_stitch.py` (new, no tmux): canned captures for a
     two-pane (vertical split) and the three-pane sitrep layout give the
     expected grid text and the exact border glyph at each border and
     junction cell; border styles under the pinned options (the expected
     cells are taken from the real-tmux oracle run below, recorded as a
     fixture, not derived from the rule under test); a background set in one
     pane does not bleed into its neighbour (per-pane decoder); an over-wide
     row, overlapping panes, a pane outside the window, and options other
     than the pinned ones raise; `rows_to_svg(stitch(...))` reads back with
     `svg_plain_text`; `ansi_to_svg` output is byte-identical before and after
     the split (fixture captured from the current code first).
   - `tests/test_screenshots_recipe.py`: new step kinds and `window` /
     `capture` round-trip through `write` / `load`; pane-addressed `keys` /
     `wait`; a step naming a role no earlier step created, a duplicate role,
     and a bad `size` raise `RecipeError`; the three shipped recipes load and
     equal their pre-change parse; `from_session` records pane / window steps.
   - `tests/test_screenshots_sample_project.py`: `agents` builds, is a git
     repo, `.standin/bin/claude` is executable, ignored by the sample repo,
     and imports nothing from `tests/` or TUI code; no real repo names.
   - `tests/test_screenshots_session_live.py` (already in the serial
     carve-out): a two-pane session captures both panes' text in one image; a
     locator matching two panes is refused; a recipe with a `pane_split` step
     replays in a fresh session; the `agents` dataset with the real
     minimonitor beside the stand-in lists the stand-in's task (the dataset
     build test the task asks for); `stop` leaves no server and no socket file;
     the existing shipped-recipe replays still pass.
   - **Stand-in `PATH`** (live): with the server started from a driver whose
     own `PATH` lacks the stand-in, a pane created by an unattached client
     from inside the session (as a TUI does) and a pane created by
     `split-window` from the driver both run the stand-in — proven by the
     identity log, not by pane creation; control: the same session without
     the argv / global pin resolves `claude` elsewhere (a decoy `claude` on
     the driver's `PATH` that only logs `decoy`), showing the pin is what
     works. `start` fails closed when `claude` does not resolve to the
     stand-in (decoy put ahead of it).
   - **Borders vs real tmux** (live): the oracle comparison of step 4 for the
     two- and three-pane layouts, each pane active in turn; the pinned options
     read back as set.
   - **Pane geometry** (live): after `pane split -h -l 40` of the main pane,
     `screen --pane main` reports the shrunken width and `shot` of the main
     pane gives an SVG of that width and height (no padding: `svg_plain_text`
     rows ≤ the pane width, `viewBox` matches the pane size); an overlay
     inside the window but outside the shrunken pane fails the shot with
     `FAILED:overlay|…`; control: the same rectangle inside the pane passes.
   - Mutants on an isolated copy (never the shared tree): one decoder shared
     across panes; borders not drawn; no over-wide check; locator takes the
     first of several matches; `from_session` drops pane steps; session name
     back to `shots`; `PATH` only through `-e` (no argv / global pin); the
     fail-closed `which` check removed; border style ignoring the active pane;
     pane capture sized from `sess.size`. Each must fail a test.

### Post-phase (risk mitigations)

Q1. **`existing_recipes_regression`** (inline post-phase, see `## Risk`):
    `website/screenshots.sh replay --scene board_child_tasks --scene
    board_layout_annotated --scene board_card_annotated --png` passes after
    the session-name / environment / export changes, and the three new board
    images show the same content as before (compare `svg_plain_text` with a
    replay taken before step 1).

8. **Follow-ups at Step 7 / 8** (after approval):
   - Create the diffviewer task (user decision): hide `diffviewer` from the
     TUI switcher list for docs screenshots, reconciling CLAUDE.md's "keep
     diffviewer in `KNOWN_TUIS`, switchable via `j`" rule (its planning
     decides, with the user, how); context: the two switcher markers and this
     plan's finding 1.
   - `./ait note 2278_5 --from 2278_4`: the two switcher scenes are not
     captured here; they wait for that task, and need this child's pane /
     window verbs and locators.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`; read the last line.
- `website/screenshots.sh replay --scene minimonitor_main_view --scene
  sitrep_window --scene ait_ide_startup --scene monitor_layout_annotated --png`
  passes in fresh sessions; open each PNG and compare with its page section and
  the marker's alt / caption; show them to the user.
- Q1's replay of the three board recipes.
- Afterwards `website/screenshots.sh session list` is empty; `tmux -L ait
  list-sessions` and the default server's `tmux list-sessions` are the same
  before and after.
- `python3 website/check_screenshots.py`.

## Notes for sibling tasks (fill in at the end)

Record: how the stand-ins were made to look real; what the monitor family
needed to recognise them; which routes were real and which hand-built; the
locator grammar; the two switcher scenes left for the diffviewer task and
child 5.

Post-implementation: Step 9 of the task workflow.

## Risk

### Code-health risk: medium
- Renaming the tmux session and adding `PATH` to the pinned environment
  touches the path every shipped board recipe replays through · severity: low
  · → mitigation: inline post-phase existing_recipes_regression
- Extending the step grammar and the export path (`ansi_to_svg` split) could
  change how existing recipes load or export · severity: low · → mitigation:
  none needed; step 7 tests the shipped recipes load unchanged and
  `ansi_to_svg` output is byte-identical
- Pane locators resolved by name could hit the wrong pane when names repeat ·
  severity: low · → mitigation: none needed; exactly one match is required,
  tested with a mutant

- A stand-in `PATH` that does not reach a TUI-spawned pane would launch the
  user's real code agent inside a screenshot session (the binary is a bare
  `claude`) · severity: high · → mitigation: none needed beyond the plan;
  step 1 pins `PATH` on the argv and in the server's global environment,
  fails closed when `claude` does not resolve to the stand-in, and P1 / the
  live test prove stand-in identity per pane from its log (with a decoy
  control); an unidentified agent pane kills the server
- Stitched borders could differ from what tmux draws (indicator mode, active
  style, junctions) · severity: medium · → mitigation: none needed; border
  options are pinned, `stitch` refuses any other configuration, and the live
  test compares cell by cell with a real tmux client's render

### Goal-achievement risk: medium
- The real launch routes (board pick, `ait sitrep`, `ait ide`, shadow `e`)
  depend on agent-command resolution reaching a `PATH` shim, on
  session-environment inheritance, and on behaviour without an attached tmux
  client; any may refuse, which would force hand-built windows · severity:
  medium · → mitigation: inline pre-phase launch_route_probe
- Stand-in agents may not look like real use (monitor status classification,
  composer shape) · severity: medium · → mitigation: none needed; P1's stop
  rule reports before anything is built
- Two of the six scenes (the switcher pair) are not delivered here, by user
  decision · severity: low · → mitigation: none needed; step 8 creates the
  diffviewer task and notes t2278_5
- Volatile on-screen text (idle timers) could make replays flaky · severity:
  low · → mitigation: none needed; `expect` / `holds` use only stable texts

### Planned mitigations
- timing: pre-phase | name: launch_route_probe | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: goal-achievement — real launch routes may refuse in the isolated server | desc: probe board pick, ait sitrep, ait ide and the shadow `e` route with a PATH shim before writing any verb (step P1)
- timing: post-phase | name: existing_recipes_regression | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — session rename / env / export split could break shipped recipes | desc: replay the three board recipes after the change and compare their text with a pre-change replay (step Q1)

Reassessed with both inline phases and the review changes (`PATH` pin, border
pin and oracle, capture geometry) in place: code-health medium (the
real-agent-launch hazard is closed by fail-closed checks, but it is a safety
property the tests must keep proving), goal-achievement medium (P1 bounds the
feasibility risk but cannot remove it before it runs).

## Implementation log

- **P1 done (2026-11-16): all four launch routes work through the real code,
  each agent pane proven to be the stand-in by its identity log.** Board pick
  (agent window + auto-spawned 40-column minimonitor), `./ait sitrep` (the
  three-pane `agent-sitrep` window), `./ait ide` inside the session (the
  `monitor` window, with the monitor's own control-mode client attached) and
  `e` in the monitor (a shadow pane stamped `@aitask_shadow_target`). No
  hand-built windows were needed. What P1 found and fixed before any verb was
  written:
  - **The board's pick opened a terminal on the user's desktop.** With no
    pick screen (missing metadata) the board falls back to `find_terminal()`,
    which used the inherited `DISPLAY` / `WAYLAND_DISPLAY`. Both are now unset
    in every pane, in setup commands and in the server's global environment.
  - **The `.aitask-scripts` symlink leaked the real repository onto the
    screen.** `monitor_app.main` finds its project as
    `Path(__file__).resolve().parents[2]`; through the symlink that is the real
    repo, so the monitor read its config and showed the real sitrep count
    ("sitrep 71 now"). The sample project now gets a COPY of the scripts
    (~0.2 s per build).
  - **The status server wrote into the user's runtime dir.** The minimonitor
    starts `status_server.py`, whose socket / lock / log live under
    `$XDG_RUNTIME_DIR/aitasks`; its `.lock` and `.log` outlived the session.
    `XDG_RUNTIME_DIR` is now a private `<tmp>/run`, removed with the session.
  - **The seed routes `shadow` (and `discuss`) to codex**; the `agents`
    dataset writes its own `codeagent_config.json` with every operation on the
    seed's `pick` agent, so every launch reaches `claude` = the stand-in.
  - **Agent kind resolution** reads `pane_current_command` (argv[0] on Linux):
    the wrapper `exec -a claude`s the interpreter, so the monitor family shows
    `IMPLEMENT`, not `IMPLEMENT (agent unresolved)`.
  - The workflow phase comes from the task's gate ledger: recipes create it
    with real `setup` commands (`aitask_gate.sh materialize-active` +
    `aitask_gate_record.sh`), no hand-written ledger text.
- **Steps 1-7 done.** All four scenes recorded through the discovery workflow
  (explore, clean walk, `recipe save` behind the fresh-replay gate).
- **Q1 done:** the three board recipes replay byte-identical to a replay taken
  before step 1 (`svg_plain_text` equal and the SVG bytes equal).

## Final Implementation Notes
- **Actual work done:**
  - `website/screenshots/session.py`: session named after the sample project
    (`lumen`); stand-in `PATH` pinned on every pane's argv (`env PATH=…`), in
    the server's global environment and for setup commands, with a fail-closed
    `which claude` check before any server exists; desktop variables unset;
    private `XDG_RUNTIME_DIR`; pinned border options (`BORDER_OPTIONS`);
    `--window` names the first window; pane roles and `<window>.<index>`
    locators (`resolve_pane`, exactly one match); `pane_split`, `window_new`;
    `--pane` on screen / keys / wait / find; capture at the pane's current
    size (`pane_geometry`); `window_layout`, `window_options`.
  - `website/screenshots/stitch.py` (new): per-pane decoding, placement,
    border glyphs (tmux's neighbour-bit table) and active-border style for the
    pinned configuration; refuses any other configuration, over-wide rows,
    overlapping or out-of-window panes.
  - `website/screenshots/svg_export.py`: `rows_to_svg` split out of
    `ansi_to_svg` (output byte-identical, tested against a reference file
    exported by the old code).
  - `website/screenshots/cli.py`: `pane split`, `window new`, `--pane` /
    `--window` on screen / find / shot, `--pane` on keys / wait, `session start
    --window`; frames carry their size, and crop / overlay rectangles are
    checked against the captured frame; argv is split at the first `--` so a
    verb's options may follow the session id; replay performs the new steps.
  - `website/screenshots/recipe.py`: steps are `(kind, value, timeout, pane)`;
    new kinds `pane_split` / `window_new`; pane-addressed `keys` / `wait`
    forms; `window` and `capture` keys; role validation; the three shipped
    recipes dump back byte-for-byte.
  - `website/screenshots/sample_project.py`: scripts copied, `tmux.default_session`
    in the project config, the stand-in installed in EVERY dataset, and the
    `agents` dataset (code-agent config, profiles, models, a local bare
    `origin` inside the ignored `.standin/`).
  - `website/screenshots/standin_agent.py` (new): the stand-in agent
    (pick / shadow / sitrep transcripts, word-wrapped to the pane, Claude-shaped
    composer, identity log, `--version`).
  - Scenes: `minimonitor_main_view`, `sitrep_window`, `ait_ide_startup`,
    `monitor_layout_annotated`.
  - Tests: `tests/test_screenshots_stitch.py` (14, fixtures recorded from a
    real tmux client), `test_screenshots_recipe.py` (+7),
    `test_screenshots_sample_project.py` (+11),
    `test_screenshots_session_live.py` (+13: two-pane image, borders vs a real
    tmux client for the two- and three-pane layouts with each pane active,
    pane capture size, locators, pane-step recipe, teardown, stand-in PATH with
    a decoy `claude` and the `-e`-only control, fail-closed refusal, desktop
    variables, the agents dataset under the real minimonitor, the four
    shipped multi-pane recipes). 15 mutants on an isolated copy, all killed.
- **Deviations from plan:**
  - The `agents` dataset keeps every task `Ready` (no `Implementing`): an
    `Implementing` task without a live lock holder is what sitrep's crash
    recovery reports, and the locks a setup command takes record a dead pid.
    The monitor family shows the phase from the gate ledger, not the status.
  - The stand-in ships in every dataset, not only `agents`: in a `base`
    session `p` on the board or `ait sitrep` would otherwise reach the user's
    real `claude`.
  - `pane split` uses `-H` / `-v` (argparse reserves `-h`).
  - `--window` on `session start` has no default: without it tmux names the
    window, as before.
  - The two switcher scenes are not captured (user decision; see Verification
    finding 1).
- **Issues encountered:**
  - **A race in the pick dialog** (`lib/agent_command_screen.py`): right after
    the dialog paints, its tmux-tab session `Select` can still hold no value,
    and `r` is refused with "Please select a session" (measured: 1 drop in 9
    second picks; 0 in 20 once the recipe waits for the Select to show
    `lumen`). Recipes wait for `Pick Task tN`, then `(R)un in tmux`, then
    `lumen`, before pressing `r`. Reported below as an upstream defect.
  - A wait for "Run in tmux" never matched (the button reads "(R)un in tmux")
    and only passed by timing out; found while chasing the race.
  - The stand-in's transcript had hard line breaks, which re-wrapped raggedly
    when the shadow split narrowed the agent pane; it now word-wraps logical
    paragraphs to the pane width, as an agent does.
  - The monitor briefly reports a just-launched agent as `(agent unresolved)`
    (a cached miss from the moment its pane still ran the launcher); the
    monitor recipes wait for it to clear.
- **Key decisions:**
  - No hand-built windows: every agent, minimonitor, sitrep window and shadow
    pane in the four scenes was created by the framework's own launch code.
  - Window size 126x40 (minimonitor), 140x42 (sitrep) and 160x44 (monitor,
    so the agent preview stays readable beside the minimonitor and the shadow).
  - The annotated monitor numbers what the page lists; the page's separate
    "Header" and "Session bar" are ONE row on screen (the session bar carries
    the title), so callouts 1 and 2 sit on that row's title and session parts.
- **Upstream defects identified:**
  - `.aitask-scripts/lib/agent_command_screen.py:1278-1282` — `_build_tmux_config` reads the tmux-tab session `Select.value` before it is populated right after the dialog opens, so an early `r` is refused with "Please select a session" (fast typists and replayed recipes both hit it)
- **Notes for sibling tasks:**
  - **Verbs added:** `session start --window NAME`; `pane split <id> --name
    ROLE [--target P] [-H|-v] [-l N|N%] [--full] -- cmd`; `window new <id>
    --name NAME [--role R] -- cmd`; `--pane P` on screen / keys / wait / find /
    shot; `--window [NAME]` on screen / find / shot. A pane `P` is a role
    (`main` or one the verbs created) or `<window name>.<pane index>` for a
    pane the TUI created; never a tmux id. A `wait` on a locator waits for the
    pane to exist.
  - **Recipe schema additions:** `window:`, `capture: {window: N} | {pane: P}`,
    steps `pane_split: {name, command, target?, direction?, size?, full?}`,
    `window_new: {name, command, role?}`, `keys: {keys, pane}`,
    `wait: {text, pane?, timeout?}`. Steps in code are 4-tuples.
  - **Rectangles** for a window capture are window cells; for a pane capture,
    the pane's own cells at its current size.
  - **Stand-in agents:** every dataset has `.standin/bin/claude`
    (`website/screenshots/standin_agent.py`). It shows pick (t14, t15), shadow
    and sitrep transcripts; add a role there for a new scene. Its identity log
    (`.standin/log`) proves which pane runs it.
  - **What the monitor family needed:** an `agent-<op>-<task>` window (the
    real launchers name it), an agent command named `claude` (argv[0]), a
    gate ledger on the task for the phase, `tmux.default_session` equal to the
    session name, and a copy (not a symlink) of the scripts.
  - **Launch dialogs:** wait for `Pick Task tN`, `(R)un in tmux` AND the
    session name (`lumen`) before `r` (the race above).
  - **sitrep:** needs `./ait lock --init` (the `agents` dataset has a local
    origin) or its refresh reports errors; items come from
    `aitask_sitrep_todo.sh add` setup commands. Its header shows the project's
    real path, i.e. the session's temp dir.
  - **Left for child 5 / the diffviewer task:** `tui_switcher_from_monitor`
    and `tui_switcher_from_minimonitor` (the real switcher lists Diff Viewer).

## Post-Review Changes

### Change Request 1 (2026-11-16 23:05)
- **Requested by user:** five review findings, each reproduced before fixing:
  (1) `DISPLAY` / `WAYLAND_DISPLAY` were unset only in tmux's global
  environment, but `new-session` copies the `update-environment` variables into
  the SESSION environment, so a window the framework creates natively still
  saw the display; (2) `resolve_pane` listed panes with `list-panes -s -t
  =lumen`, which tmux looks up as a window name first, so another session with
  a window called `lumen` answered; (3) `wait` turned every error on a locator
  into an empty screen, so an ambiguous locator made `wait --gone` succeed;
  (4) `window_options` read the global defaults (`show-options -gv`), so a
  border option set on the captured window or one of its panes was not
  refused; (5) a failed command send after a pane was created left no failed
  journal entry, so the recording stayed saveable.
- **Changes made:** (1) the variables are removed from the session environment
  too, and `update-environment` is emptied so no later attach copies them
  back; (2) every new target goes through the gateway helpers
  (`session_scope_target` for `list-panes -s`, `session_target` for
  `list-windows` / `set-environment`, `window_target` for `new-window`);
  (3) a locator matching no pane raises `PaneNotFound`, the only error `wait`
  retries; ambiguity and tmux failures are a failed, journaled step, and
  "gone" is accepted only on a screen that was actually read; (4)
  `window_options(session, panes)` reads each captured pane's effective value
  (`show-options -A -p -v`, pane → window → global) and reports values that
  differ between panes, so `stitch` refuses them; (5) a failed send journals an
  `ok: false` entry and the pane stays registered (it exists).
  Tests, each failing on the pre-fix code on an isolated copy: a native
  `new-window` from a client whose own env has a display;
  a second session with windows `lumen` and `target`; an ambiguous and a
  not-yet-existing locator under `wait --gone` (control: a readable pane);
  `pane-border-indicators colour` on the window and `pane-active-border-style`
  on one pane (control: the pinned window exports); a send-keys failure
  injected into the real `pane split` path, then `recipe save` refused.
- **Files affected:** `website/screenshots/session.py`, `website/screenshots/cli.py`,
  `tests/test_screenshots_session_live.py`.

### Change Request 2 (2026-11-17)
- **Requested by user:** the stand-in ignored C-c: `tty.setraw` turns off the
  terminal's own SIGINT, and the input loop ended only on the C-d byte, though
  the plan names both keys.
- **Changes made:** the loop ends on either byte (`EXIT_BYTES` = 0x03, 0x04)
  and on an empty read (a closed terminal no longer spins the loop); the
  terminal mode is restored on every exit. Tests on a real pty: C-c and C-d
  each end it with status 0 and give back canonical input and echo (waiting
  until the pty is really in raw mode first); control: another key leaves it
  running. The C-c case fails on the pre-fix loop (isolated copy). Checked
  live in tmux as well: after C-c the pane runs bash again.
- **Files affected:** `website/screenshots/standin_agent.py`,
  `tests/test_screenshots_sample_project.py`.
