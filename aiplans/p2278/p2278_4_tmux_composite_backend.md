---
Task: t2278_4_tmux_composite_backend.md
Parent Task: aitasks/t2278_docs_tui_screenshot_generator.md
Sibling Tasks: aitasks/t2278/t2278_1_*.md, aitasks/t2278/t2278_2_*.md, aitasks/t2278/t2278_3_*.md, aitasks/t2278/t2278_5_*.md, aitasks/t2278/t2278_6_*.md, aitasks/t2278/t2278_7_*.md, aitasks/t2278/t2278_8_*.md
Archived Sibling Plans: aiplans/archived/p2278/p2278_*_*.md
Base branch: main
Output branch: main
---

# Plan: t2278_4 — backend B, tmux composites

Design source: `aiplans/p2278_docs_tui_screenshot_generator.md` ("Backends" B).
Read `aidocs/framework/tmux_gateway.md` (policy 5 in particular) before writing
any code, and the archived plans of children 2 and 3.

## Steps

1. **One composite end to end first: minimonitor beside a stand-in agent.**
   In a scratchpad script:
   - `client = TmuxClient(socket_args=["-L", f"ait_shots_{os.getpid()}"])`;
   - register `client.run(["kill-server"])` as cleanup **before** anything else;
   - assert no server exists on the socket (`client.run(["list-sessions"])`
     returns non-zero);
   - `client.run(["-f", "/dev/null", "new-session", "-d", "-s", S, "-x", "160", "-y", "45", "-c", fixture, agent_cmd])`
     and print `client._argv([...])` once to confirm the argv is
     `tmux -u -L ait_shots_<pid> -f /dev/null new-session ...`;
   - `set-environment -t S AITASKS_TMUX_SOCKET ait_shots_<pid>`;
   - `split-window -h -l 40 -P -F "#{pane_id}" -t <agent pane> "env -u COLUMNS -u LINES ... <minimonitor harness>"`;
   - poll `capture-pane -p` per pane for its settle text;
   - `list-panes -F "#{pane_id} #{pane_left} #{pane_top} #{pane_width} #{pane_height}"`;
   - `capture-pane -e -p -t <pane>` per pane.
   The agent stand-in is `tests/lib/fake_composer_agent.py`; the minimonitor is
   a harness subclass with stubbed data (see `tests/lib/minimonitor_live_harness.py`).
   **Stop rule:** if the panes cannot be given content that looks like the real
   TUI, stop here and report to the user before building the general engine.

2. **Stitching.** Build a cell grid of the window size. Blit each pane's
   captured lines at its `(left, top)`; draw the borders tmux draws between
   panes (the one-cell gaps in the geometry) with box-drawing characters.
   Convert each row to `rich.text.Text` with `Text.from_ansi`, print the rows
   into a recording `Console(width, height, record=True, force_terminal=True,
   color_system="truecolor", legacy_windows=False, safe_box=False)`, then
   `export_svg(title=, theme=, unique_id="terminal-" + scene id)`. A pane line
   shorter than the pane width is padded; a longer one is a capture error.

3. **`backends/tmux_backend.py`.** `start_server()` (the only function that can
   bring a server into existence; asserts none exists first), `build_layout`,
   `wait_ready` (bounded poll, timeout raises), `geometry`, `capture_panes`,
   `stitch`, `teardown`. `capture(scene)` returns `CaptureResult(svg, regions)`
   with `regions` keyed by pane name, so `crop` and `overlays` targets can be
   `{pane: <name>}`. Extend `scene.py` for the `layout` block and the `pane`
   target.

4. **Stand-ins and harnesses in `registry.py`.** Agent stand-in, minimonitor
   harness, monitor harness (replay of deterministic frames), sitrep TUI on a
   fixture store (`tests/test_sitrep_tui_app.py:107` `build_fixture`).

5. **Scenes.**
   - `minimonitor_main_view`: agent pane plus a 40-column right split.
   - `ait_ide_startup`: one `monitor` window as `ait ide` creates it
     (`.aitask-scripts/aitask_ide.sh`), with a few agent windows listed.
   - `sitrep_window`: agent above, sitrep TUI below at 40%, full-height
     minimonitor on the right (`tests/test_sitrep_window_live.sh:113-222`).

6. **Tests, `tests/test_screenshots_tmux_backend.py`.**
   - Skip gate: `shutil.which("tmux")` only. It must not call the backend.
   - Capture: a two-pane layout of `printf` stand-ins yields an SVG containing
     both panes' text; a settle timeout fails; after the run no server answers
     on the private socket.
   - Locale: run the backend in a subprocess with
     `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0`, a pane printing
     `┌─┐ prój`; assert the characters are in the SVG. Control: the same
     capture through a client whose flags exclude `-u` must show `_`. Classify
     the control as the pre-fix expectation, so the assertion is known to fail
     without `-u`.
   - Config: `HOME` and `XDG_CONFIG_HOME` set to a scratch directory containing
     `.tmux.conf` and `tmux/tmux.conf`, each running
     `run-shell 'touch <sentinel>'`; start the server through `start_server()`;
     assert the sentinel does not exist. Control: the same start without
     `-f /dev/null` creates it.
   - Keep the socket directory short (see `tests/lib/tmux_isolation.sh`); do not
     put it under a long `$TMPDIR`.
   - Check whether the module must join the serial carve-out in
     `tests/run_all_python_tests.sh` (a real pane under a wall-clock budget).

## Verification

- `bash tests/run_all_python_tests.sh --test-dir tests`.
- `website/screenshots.sh capture --scene minimonitor_main_view --scene ait_ide_startup --scene sitrep_window`
  twice; `cmp` the images; view them in a browser.
- `tmux -L ait list-sessions` and the user's default server are unchanged
  before and after; no `ait_shots_*` socket has a live server.

## Notes for sibling tasks

Record: how each harness was given realistic content; any pane whose content
could not be made byte-stable; whether the module joined the serial carve-out.

Post-implementation: Step 9 of the task workflow.
