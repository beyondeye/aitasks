---
priority: medium
risk_code_health: low
risk_goal_achievement: medium
effort: high
depends: [t2278_1]
issue_type: feature
status: Implementing
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2278
implemented_with: claudecode/fable5_2
created_at: 2026-11-15 18:12
updated_at: 2026-11-16 08:23
---

## Context

Child 2 of t2278 (docs TUI screenshot generator). The design was revised on
2026-11-15: screenshots are captured by an agent driving the **real TUI in an
isolated tmux session** on sample data, and recipes are recorded from captures
that worked. Read the parent plan
`aiplans/p2278_docs_tui_screenshot_generator.md` first ("Design revision",
"Roles", "Primitives", "Sample state: the setup contract", "Which journal
becomes a recipe", "Recipe lifecycle", "Isolation rules", "Image export").

This task's filename keeps its pre-revision slug
(`scene_specs_and_textual_backend`); there is no Textual backend any more.

Child 1 delivered the marker grammar, `website/screenshots/markers.py` and
`website/check_screenshots.py`, and migrated the 17 markers. This child
delivers the sample project, the session primitives, the SVG export, recipe
recording and replay, the batch manifest, and one documentation example end
to end: `board_child_tasks`.

## Key Files to Modify

- `website/screenshots/sample_project.py` (new): `DATASETS` and
  `build(root, dataset="base")`. Data only; no TUI imports.
- `website/screenshots/session.py` (new): isolated tmux session through
  `TmuxClient`; `start_server`, `start`, `setup`, `run`, `screen`, `keys`,
  `wait`, `find`, `stop`, `list_sessions`; the journal.
- `website/screenshots/svg_export.py` (new): captured ANSI to Rich SVG.
- `website/screenshots/recipe.py` (new): `scenes/<id>.yaml` loader, validator
  and writer. Imports `read_spec_owner` from `screenshots.markers` and rejects
  any spec it reports a problem for.
- `website/screenshots/cli.py`, `website/screenshots.sh` (new): the verbs.
- `website/screenshots/scenes/board_child_tasks.yaml`: recorded by the tool.
- `.gitignore`: `website/screenshots/.staging/`.
- `tests/test_screenshots_recipe.py`, `tests/test_screenshots_svg_export.py`,
  `tests/test_screenshots_sample_project.py`,
  `tests/test_screenshots_session_live.py` (new); the live module joins the
  serial carve-out in `tests/run_all_python_tests.sh` and the list in
  `CLAUDE.md`.

## Capture rules

- Every tmux call goes through
  `TmuxClient(socket_args=["-L", "ait_shots_<id>"])`. The server starts only
  in `start_server()`, with `-f /dev/null`, after asserting the socket has no
  server. Each server has a one-hour time-to-live.
- Pane environment pinned at spawn: `AITASKS_TMUX_SOCKET`, `COLORTERM`,
  scratch `HOME` and `XDG_CONFIG_HOME`, `AIT_PYTHON`; `COLUMNS` / `LINES`
  unset. The pane shell is `bash --noprofile --norc`.
- The sample project is the only data on screen: invented names, project
  `lumen`.
- Waits are bounded polls on screen text. A timeout is a failure and stages
  nothing. Never a sleep.
- Capture with `capture-pane -e -p -N`, decode the whole capture with one
  `AnsiDecoder` (tmux carries SGR state across lines).
- A recipe starts from a named dataset plus recorded `setup` commands, and
  nothing else. `recipe save` accepts only a clean discovery session and
  writes only after a replay in a fresh session passes.
- `shot` / `replay` write to a new batch directory
  `website/screenshots/.staging/<batch-id>/` with `manifest.json`: per scene
  the `output` path, the staged SHA-256, the destination state (`absent` or
  its SHA-256), and each marker's page and exact text. Child 5 builds
  `preview` and `apply` on it.
- The target filename comes from the recipe's `output:` only.

## Reference Files for Patterns

- `tests/test_board_startup_focus_live.py`: a standalone `ait` project (a
  copy of `ait`, a symlink to `.aitask-scripts`) on a private tmux socket,
  with a bounded boot wait.
- `.aitask-scripts/lib/tmux_exec.py` (`TmuxClient`) and
  `aidocs/framework/tmux_gateway.md` (policy 5).
- `website/screenshots/markers.py`: `read_spec_owner`, `path_problem`, `scan`.
- `tests/test_check_screenshots.py::SpecOwnerTests`: ACCEPTED / REJECTED
  tables to reuse.

## Implementation Plan

See `aiplans/p2278/p2278_2_scene_specs_and_textual_backend.md`. Its first
implementation step is the example done by hand before any tooling.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes, with the four
  new modules.
- `website/screenshots.sh list` shows `board_child_tasks`, and
  `website/screenshots.sh replay --scene board_child_tasks` prints a `BATCH:`.
- `website/screenshots.sh session list` is empty afterwards.
- `python3 website/check_screenshots.py` reports the scene as having a spec
  and no ownership violation.
- The user views the staged `aitasks_board_child_tasks.svg`.

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t2278_1** id=2026-11-15T20:16:55Z.3b93d72e75ca0bfe3c915d24 from=t2278_1 from_verified=yes at=2026-11-15T20:16:55Z base=56e9dbdf804ad8ceefb6b30b03f87720fd2b1a2d base_branch=main dirty=yes host=omg16
>
> | Advisory, from t2278_1 (committed in f5588aaea): the scene-spec owner contract your loader's agreement check relies on is now fixed in website/screenshots/markers.py. As of that commit:
> | 
> | - Import SPEC_SCALAR_RE, read_spec_scalar, read_spec_owner and path_problem from screenshots.markers rather than copying the pattern. A loader that rejects any spec for which read_spec_owner(path).problems is non-empty cannot accept a different set than check_screenshots.py does.
> | - Accepted id:/output: lines: a bare token, "double quoted" with no " or \, or 'single quoted' with no '. A trailing # comment needs at least one space before '#'. Separators are spaces only: PyYAML raises on a tab after the colon, before a comment, or as trailing whitespace.
> | - A bare value must start with a letter and must not be a YAML bool/null word (yes/no/true/false/on/off/null/y/n, any case). Otherwise it is the problem "quote it", e.g. id: "123".
> | - output: must also pass path_problem: relative, no empty/./.. segment, and each segment only [A-Za-z0-9._-], because the path becomes the image URL verbatim.
> | - The parent design's own example line, `output: aitasks_board_child_tasks.svg   # required; relative to website/static/imgs/`, reads correctly. tests/test_check_screenshots.py::SpecOwnerTests holds the ACCEPTED/REJECTED tables and the PyYAML agreement check; your fixture can reuse them.
> | - Final scene/file table for the 17 migrated markers: 13 scenes, including a third switcher scene, tui_switcher_from_minimonitor. See "Notes for sibling tasks" in aiplans/p2278/p2278_1_marker_grammar_check_and_migration.md (archived under aiplans/archived/p2278/ after t2278_1 closes).

> **👁 note:read** id=2026-11-15T21:01:23Z.6fa3f62ec63687eb19d35f21 by=t2278_2 at=2026-11-15T21:01:23Z mode=explicit ids=2026-11-15T20:16:55Z.3b93d72e75ca0bfe3c915d24

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-16T06:22:58Z status=pass attempt=1 type=human
