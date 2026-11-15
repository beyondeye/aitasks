---
priority: medium
effort: high
depends: [t2278_1]
issue_type: feature
status: Ready
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 2 of t2278 (docs TUI screenshot generator). The full design is in the
parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`; read its "Scene
spec", "Backends" (A) and "CLI and skill" sections first. Child 1 delivered the
marker grammar, `website/screenshots/markers.py` and
`website/check_screenshots.py`, and migrated the 17 markers.

This child adds the declarative scene spec, the registry of app adapters and
fixtures, capture backend A (headless Textual to SVG), and the `list` and
`capture` commands. It delivers six scenes.

## Key Files to Modify

- `website/screenshots/scene.py` (new): YAML loader and validator (PyYAML).
  Required fields `id`, `output`, `backend`, `size`. `id` must equal the file
  stem. `id` and `output` must be plain single-line scalars, because the
  stdlib checker reads them with a line pattern.
- `website/screenshots/registry.py` (new): fixed tables in source (not YAML):
  `APPS` (adapter per TUI), `FIXTURES` (fixture builders), and the pinned look
  (one Textual theme, one Rich terminal theme, default sizes, window title
  policy, the invented project name shown on screen).
- `website/screenshots/backends/textual_backend.py` (new).
- `website/screenshots/cli.py` (new): `list`, `capture [--scene ID | --pending | --all]`.
- `website/screenshots.sh` (new): launcher that sources
  `.aitask-scripts/lib/python_resolve.sh` and uses `require_ait_python`. The
  tool needs Textual, Rich and PyYAML, which only the framework venv has.
- `website/screenshots/scenes/*.yaml` (new): `tui_switcher_dialog`,
  `tui_switcher_from_monitor`, `board_child_tasks`, `board_task_detail_lock`,
  `trails_main_view`, `brainstorm_browse_tab`. Use the scene ids and `output`
  filenames child 1 put in the markers.
- `website/.gitignore` (or the repo `.gitignore`): `website/screenshots/.staging/`.
- `tests/test_screenshots_scene.py`, `tests/test_screenshots_textual_backend.py` (new).

## Capture rules (backend A)

- Boot with `app.run_test(size=(cols, rows))`, run the steps with Pilot, then
  wait on the settle condition (text present on screen, or a CSS selector
  matching) with a bounded poll. A timeout is a failure: no image is written.
  Never settle with a sleep.
- Drain workers (`await app.workers.wait_for_complete()`) before leaving the
  `run_test` block; a `@work` worker still running at block exit fails the run.
- Do not call `App.export_screenshot()`: it passes no `unique_id`, theme or
  chrome control. Copy its lines (`textual/app.py`, `export_screenshot`): build
  a recording `rich.console.Console(width, height, file=io.StringIO(),
  force_terminal=True, color_system="truecolor", record=True,
  legacy_windows=False, safe_box=False)`, print
  `app.screen._compositor.render_update(full=True, screen_stack=app._background_screens, simplify=False)`,
  then `console.export_svg(title=..., theme=..., unique_id="terminal-" + <scene id>)`.
- Output must be byte-identical across runs: no clock, date or temp path may
  reach the screen. Adapters pin dates (`today=` where the app accepts one) and
  use a fixed fixture path name shown on screen.
- `capture` writes a new batch directory every run:
  `website/screenshots/.staging/<batch-id>/`, never into an existing one, and
  prints `BATCH:<batch-id>`. It writes `manifest.json` with, per scene: the
  `output` path, the staged image's SHA-256, the destination file's state at
  capture time (`absent` or its SHA-256), and for each marker of that scene
  the page path and the exact marker text. Child 5 builds `preview` and
  `apply` on this manifest.
- The target filename comes from the spec's `output:` only, never from a
  marker.

## Reference Files for Patterns

- `tests/lib/board_fixture.py`: `build_fixture_tree`, `load_board_module`,
  `enter_fixture_tree`, `make_trails_app`, `RICH_TOPOLOGY`,
  `block_app_worker_starts`. Invariant: `TASK_DIR` must be the literal relative
  `"aitasks"` and the cwd must be the tree root; restore the cwd before the
  tree is deleted. `build_fixture_tree` takes `project_name=`: pass an invented
  name (doc guide rule: never the real repo names on screen).
- `tests/test_tui_group_nav.py:121-150`: pushing `TuiSwitcherOverlay` on a host
  app under patches of `ts.discover_aitasks_sessions`, `ts._session_windows`
  and `TuiSwitcherOverlay._compute_desync_summary`. `diffviewer` must not
  appear in a docs screenshot of the switcher.
- `tests/test_trails_app.py:168-175`: `bf.make_trails_app()` with
  `discover_trails` and `run_trail_drift` patched.
- `tests/test_brainstorm_compare_overlay.py:205` (`_make_session`) and
  `tests/test_brainstorm_node_action_integration.py:44-54`: a brainstorm session
  on a temp `AGENTCREW_DIR`.
- `tests/test_agent_model_picker_narrow.py:41-62`: host app pushing a screen,
  fixed `today`.
- Settle idioms: `pilot.pause()`, `pilot.wait_for_scheduled_animations()`.
  `pilot.pause()` does not advance real timers.
- Rich geometry: `rich/console.py` `export_svg`; Textual `textual/app.py`
  `export_screenshot`. Installed: Textual 8.2.7, Rich 15.0.0.

## Implementation Plan

See `aiplans/p2278/p2278_2_scene_specs_and_textual_backend.md`. The first step
is one scene end to end (`board_child_tasks`) before the format is generalised.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes, including: spec
  validation, a per-adapter capture test, a double capture that is
  byte-identical, and a settle timeout that fails without writing an image.
- `website/screenshots.sh list` shows the six scenes.
- `website/screenshots.sh capture --all` twice gives two batches with
  byte-identical images.
- `python3 website/check_screenshots.py` now reports the six scenes as having a
  spec and no ownership violation.
- Open each staged SVG in a browser and check it shows the described state.

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
