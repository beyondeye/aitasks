---
priority: medium
effort: high
depends: [t2278_3]
issue_type: feature
status: Ready
labels: [website, documentation, tui, screenshots]
gates: [risk_evaluated]
anchor: 2278
created_at: 2026-11-15 18:12
updated_at: 2026-11-15 18:12
---

## Context

Child 4 of t2278 (docs TUI screenshot generator). The full design is in the
parent plan `aiplans/p2278_docs_tui_screenshot_generator.md`; read "Backends"
(B) first. Children 2 and 3 delivered the scene spec, backend A, `capture` and
`svgpost` (crop and overlays on cell rectangles).

This child adds capture backend B: a multi-pane tmux window stitched into one
SVG. It delivers the three composite scenes.

## Hard rules

- **Every tmux call goes through the gateway**:
  `TmuxClient(socket_args=["-L", "ait_shots_<pid>"])` from
  `.aitask-scripts/lib/tmux_exec.py`. Never build a `["tmux", ...]` argv by
  hand. `tests/test_no_raw_tmux.sh` does not scan `website/`, but the client is
  what adds the mandatory `-u` flag and decodes output as UTF-8 with
  `surrogateescape` (`aidocs/framework/tmux_gateway.md`, policy 5). Without
  them a client with no UTF-8 locale receives `_` for every box-drawing
  character.
- **The user's tmux config is never loaded.** The server is started by
  `client.run(["-f", "/dev/null", "new-session", "-d", ...])`. `TmuxClient._argv`
  prepends `tmux -u -L <socket>` to the caller's arguments, so this yields
  `tmux -u -L ait_shots_<pid> -f /dev/null new-session ...` with no gateway
  change. There is no post-start fallback (a loaded config may already have run
  `run-shell`, installed hooks or started plugins). One `start_server()`
  function is the only place a server can come into existence, and it asserts
  the socket has no server before it runs.
- Teardown is `kill-server` on the private socket only, registered before the
  first spawn. Never address the default socket or `-L ait`.
- Pin `AITASKS_TMUX_SOCKET` in the session environment (panes run in the
  server's environment). Launch panes with `env -u COLUMNS -u LINES` (Rich
  prefers those over the real pty size). Take pane ids from `-P -F`.
- Readiness is a settle text per pane, polled with `capture-pane -p`; a timeout
  is a failure, not a skip. Never settle with a sleep.

## Key Files to Modify

- `website/screenshots/backends/tmux_backend.py` (new): start the server,
  build the layout, wait for each pane, read geometry from `list-panes -F`,
  capture each pane with `capture-pane -e -p`, stitch the panes with drawn
  borders into a recording Rich `Console` via `Text.from_ansi`, export with
  `export_svg` using the same pinned `unique_id`, title and theme as backend A.
  Pane rectangles are passed to `svgpost` the way widget regions are.
- `website/screenshots/scene.py`: validate the `layout` block (window size,
  panes: command or stand-in, split direction and size, settle text).
- `website/screenshots/registry.py`: stand-in commands and harness apps.
- `website/screenshots/scenes/`: `ait_ide_startup`, `minimonitor_main_view`,
  `sitrep_window`.
- `tests/test_screenshots_tmux_backend.py` (new).

## Reference Files for Patterns

- `tests/test_minimonitor_width_pin_live.py` and
  `tests/lib/minimonitor_width_pin_harness.py`: a harness subclass of
  `MiniMonitorApp` running in a real pane on a private socket, `-f /dev/null`,
  `split-window -h -l 40 -P -F`, `env -u COLUMNS -u LINES`, a `ready` signal.
- `tests/lib/minimonitor_live_harness.py`: real `MiniMonitorApp` with stubbed
  data in a pane.
- `tests/test_sitrep_window_live.sh:113-222`: the full sitrep layout (agent
  above, sitrep TUI below at 40%, full-height minimonitor on the right) built
  through `monitor_core.spawn_sitrep` with stand-ins, and its geometry check.
- `tests/lib/fake_composer_agent.py`: a scripted pane drawn like an agent's
  composer; use it as the agent stand-in.
- `tests/lib/monitor_status_scenarios.py` and
  `monitor/status_recording.py replay`: deterministic monitor content.
- `.aitask-scripts/aitask_ide.sh`: `ait ide` is one `monitor` window.
- `.aitask-scripts/lib/agent_launch_utils.py` `maybe_spawn_minimonitor`:
  the 40-column right split.
- `tests/lib/tmux_isolation.sh`: why the socket directory must stay short.

## Implementation Plan

See `aiplans/p2278/p2278_4_tmux_composite_backend.md`. The first step is one
composite end to end (minimonitor beside a stand-in agent pane). If the panes
cannot be given realistic content through harness apps, stop and report before
building the general layout engine.

## Verification Steps

- `bash tests/run_all_python_tests.sh --test-dir tests` passes, with:
  - a capture test, skipped when `tmux` is absent by a probe that does not run
    the backend;
  - a locale test: the backend in a subprocess under
    `LC_ALL=C PYTHONUTF8=0 PYTHONCOERCECLOCALE=0` against a pane printing
    box-drawing characters and a non-ASCII word, asserting they appear
    unchanged in the SVG; its control (the same capture with `-u` removed from
    the argv) must show the `_` substitution;
  - a config test: `HOME` and `XDG_CONFIG_HOME` point at a scratch directory
    whose `tmux.conf` runs `run-shell 'touch <sentinel>'`; after the backend
    starts its server the sentinel file must not exist.
- After a capture, no `ait_shots_*` server is left running, and the user's own
  tmux server is untouched.
- A double capture of each composite scene is byte-identical.
- Open the three staged SVGs and compare each with its page description.
