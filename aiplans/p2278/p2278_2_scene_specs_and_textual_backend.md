---
Task: t2278_2_scene_specs_and_textual_backend.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_4_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_2 — scene specs, backend A and the capture path

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` ("Scene spec",
"Backends" A, "CLI and skill"). Read child 1's archived plan
(`aiplans/archived/p2278/p2278_1_*.md`) for the final scene/file table.

## Steps

1. **One scene end to end first: `board_child_tasks`.** Write a throwaway
   script in the scratchpad that:
   - builds a board fixture with `tests/lib/board_fixture.py`
     (`build_fixture_tree(root, RICH_TOPOLOGY, project_name=<invented name>)`),
     `chdir`s to the tree, loads the module with `load_board_module("aitasks", tag=...)`;
   - runs `KanbanApp()` under `run_test(size=(160, 48))`, expands a parent,
     waits for a child card to be on screen;
   - exports with the copied export lines (recording `Console`,
     `render_update(full=True, ...)`, `export_svg(title=, theme=, unique_id=)`).
   Run it twice and `cmp` the two files. Do not generalise until they are
   byte-identical and the image looks right in a browser. Anything on screen
   that varies between runs (dates, the temp path, lock state) is found here.

2. **`scene.py`.** `load_scene(path) -> Scene`, `load_all(dir) -> dict`.
   Validate: required `id`, `output`, `backend`, `size`; `id` equals the file
   stem; `id` / `output` are plain single-line scalars (re-read the raw lines
   with the same pattern `markers.read_spec_owner` uses and fail if the two
   readers disagree); `output` is relative with no `..`; `backend` is one of
   `textual`, `tmux`, `pixels`; `app` and `fixture.name` exist in the registry;
   each step is exactly one of `press`, `click`, `wait_for`; `settle` is
   `{text}` or `{selector}`; unknown keys are errors. `crop` and `overlays`
   are accepted and passed through; child 3 validates and implements them.
   Duplicate `output` across specs is an error in `load_all`.

3. **`registry.py`.** In source, not YAML:
   - `LOOK`: Textual theme name, Rich `TerminalTheme`, default size, the
     invented project name. Pick the theme from the result of step 1 and record
     why in the notes.
   - `FIXTURES`: `board_rich`, `trails_basic`, `brainstorm_basic`.
   - `APPS`: one adapter per TUI, each a context manager that yields a mounted
     app and restores cwd and patched module attributes on exit:
     `board`, `trails`, `brainstorm`, `switcher` (host app pushing
     `TuiSwitcherOverlay`, with a `variant` parameter for the from-monitor
     case; `diffviewer` filtered out of the listed windows).
   Adapters import from `tests/lib` and `.aitask-scripts/{lib,board,...}` with
   `sys.path` inserts computed from the repo root.

4. **`backends/textual_backend.py`.** `capture(scene) -> CaptureResult(svg, regions)`:
   run the adapter, execute steps, wait on settle with a bounded poll (default
   10 s, a timeout raises `SettleTimeout`), `await app.workers.wait_for_complete()`,
   export. `regions` stays empty in this child.

5. **`cli.py` and `screenshots.sh`.**
   - `list`: scene id, backend, output, and whether a marker or an existing
     image refers to it.
   - `capture [--scene ID]... | --pending | --all`: `--pending` means scenes
     with at least one unresolved marker. Creates
     `website/screenshots/.staging/<batch-id>/` (id = UTC timestamp plus a
     short random suffix; refuse if the directory exists), writes the images
     under their `output` path and `manifest.json` (per scene: `output`,
     staged SHA-256, destination state `absent` or SHA-256, and each marker's
     page path and exact text from `markers.scan`). Prints `BATCH:<id>` last.
     A scene that fails to capture is reported and left out of the manifest;
     the exit status is non-zero.
   - Add `website/screenshots/.staging/` to `.gitignore`.

6. **Scenes.** Write the six specs. Decide the open minimonitor-switcher point:
   capture the switcher as opened from minimonitor; if its hint row matches the
   generic one, the marker keeps `tui_switcher_dialog`, otherwise add a third
   scene and update that marker's `scene=` / `file=`.

7. **Tests.**
   - `tests/test_screenshots_scene.py`: each validation rule; the two readers
     agree on `id` / `output`.
   - `tests/test_screenshots_textual_backend.py`: per adapter, a capture
     produces an SVG containing an expected text; a double capture is
     byte-identical; a settle that can never match raises and writes no file;
     no live worker remains. If the test runs test bodies in subshells or
     boots a TUI with `@work` workers, follow `aidocs/framework/testing_conventions.md`.

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`.
- `website/screenshots.sh list`; `website/screenshots.sh capture --all` twice,
  then compare the two batches' images with `cmp`.
- `python3 website/check_screenshots.py`: six scenes have specs, no ownership
  violation.
- View each staged SVG in a browser.

## Notes for sibling tasks

Record: the pinned look and why; the manifest schema as implemented (child 5
consumes it); the adapter interface (children 3, 4 and 6 add adapters); every
source of run-to-run variation found in step 1 and how it was pinned.

Post-implementation: Step 9 of the task workflow.
