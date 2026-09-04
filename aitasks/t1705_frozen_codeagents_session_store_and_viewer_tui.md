---
priority: medium
risk_code_health: medium
risk_goal_achievement: high
effort: high
depends: []
issue_type: feature
status: Ready
labels: [minimonitor, tmux, codeagent, tui, session_persistence]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1705_1, t1705_2, t1705_3, t1705_4, t1705_5, t1705_6, t1705_7, t1705_8, t1705_9, t1705_10]
created_at: 2026-09-04 10:50
updated_at: 2026-09-04 16:15
---

## Goal

Add a third lifecycle state for a code agent beyond live and `parked`: **frozen**.
A frozen agent's process is gone, but its terminal output is persisted and shown
in-place by a new viewer TUI that occupies the agent's own pane in its own tmux
window (viewer left, minimonitor companion right — exactly the live-agent
layout). Minimonitor lists the frozen agent as an agent-like row (glyph +
`frozen`, no live state dot, no capture). From the viewer or minimonitor the
user can **restore** the agent to live via `claude --resume <session-id>` /
`codex resume <session-id>`, or — when the record carries a task id — **re-pick**
the task (`/aitask-pick <id>`), which is often cheaper than resuming.

Motivation: with 10–20 parallel agents most sessions are kept only for
reference (task-workflow summaries, spawned task lists, analysis results, the
task number for the next sibling). `parked` still keeps the process alive;
frozen frees it while keeping the reference content and a way back.

**This is a large feature and MUST be decomposed into child tasks at planning
time.** A suggested decomposition is at the end.

## Framework "session" concept (new)

Introduce an explicit, persisted notion of the current aitasks *framework
session*: the set of all agents across every aitasks tmux session / project on
this machine, with freeze data for the frozen ones. Store under
`~/.config/aitasks/` (same tier as `agent_marks.json` / `projects.yaml`; 0600;
write via `os.replace`; writers serialize on the `registry_lock.sh` mutex;
readers lock-free — mirror `lib/agent_marks.py` + `aitask_agent_marks.sh`).

Per-agent record (both live and frozen) should carry at least:
- `root` (realpath of project root), tmux `session`, `window` name, `pane_id`
  (not durable across tmux restarts — identity stays `(root, window)` as in
  agent_marks)
- `operation` (pick/qa/resume/explore/raw/…) and `task_id` when the window name
  is `agent-(pick|qa|resume)-<id>` (reuse `task_id_from_window_name`)
- `agent_string` (e.g. `claudecode/opus5`), resolved `agent_kind`
- codeagent `session_id` + `transcript_path` (see hook below), `started_at`
- freeze fields when frozen: `frozen_at`, capture file path(s), capture line
  count, last known phase text

Freeze-All: iterate `discover_aitasks_sessions()` × agent panes and freeze
every live agent (use case: shutting down the machine). Restore-All / per-agent
restore re-creates the window with the same name so the task-id ↔ window
mapping keeps working.

## Capturing the codeagent session id

Verified (2026-09): `claude --resume <session-id|name>` (`--fork-session`,
`--session-id <uuid>` exist; claude 2.1.259) and `codex resume [SESSION_ID]
[PROMPT]` (`--last`, `--all`; codex 0.153.0). Both hook systems deliver
`session_id`, `transcript_path`, `cwd` on stdin for `SessionStart` /
`SessionEnd`. Claude Code also exports `CLAUDE_CODE_SESSION_ID` to Bash tool
commands and stores transcripts at `~/.claude/projects/<escaped-cwd>/<id>.jsonl`;
Codex has **no** `CODEX_SESSION_ID` (upstream feature request only) and stores
sessions under `~/.codex/sessions/<yyyy>/<mm>/…`.

⇒ The one mechanism that works for both agents is a **`SessionStart` hook**
(Claude: `.claude/settings.json` `hooks.SessionStart`, matcher `startup|resume`;
Codex: `<repo>/.codex/hooks.json` or `[hooks]` in `.codex/config.toml`, project
layer must be trusted) that records `session_id` / `transcript_path` for the
pane it runs in (`$TMUX_PANE`), e.g. as a pane user-option
(`@aitask_agent_session`) and/or into the session store. The hook must be
shipped via `seed/` and installed by `ait setup` for every supported agent
(see `aidocs/framework/aitasks_extension_points.md`). Fallback when the hook
did not fire: newest transcript file for the cwd (Claude), or "restore via
re-pick only".

## Freeze flow (per agent)

1. Resolve the agent record; capture the pane with raw ANSI and wrap-join:
   `capture-pane -p -e -J -t <pane> -S -` (full scrollback; consider a
   configurable cap) through the tmux gateway (`lib/tmux_exec.py`), and store it
   (ANSI file + optionally an ANSI-stripped `.txt` for search/markdown).
2. **Stand-in hazard:** agents are launched with `remain-on-exit on` and a
   pane-scoped `pane-died` hook running `aitask_companion_cleanup.sh`, which
   kills the companion AND the primary pane when no other real agent sibling
   remains — i.e. killing the agent would close the whole window. The freeze
   flow must first stamp the pane (e.g. `@aitask_frozen=<record-id>`), make the
   cleanup script abstain for stamped panes, then `respawn-pane -k -t <pane>
   'ait <viewer> --frozen <record-id>'` so the viewer takes the agent's slot and
   the companion minimonitor survives. Window name is kept unchanged so
   `classify_pane` (`agent-` prefix) and `task_id_from_window_name` keep
   working.
3. Write the frozen record; update the marks store if the agent was
   parked/prioritized (decide: frozen clears the mark, or coexists).

## Viewer TUI (new; name TBD at planning — e.g. `ait frozen` / `ait icebox`)

- Faithful rendering of the raw ANSI capture (default) with a toggle to
  plain/ANSI-stripped and an optional markdown rendering of all or a selected
  part of the text. Precedent: `.aitask-scripts/logview/logview_app.py`
  (RichLog + `Text.from_ansi`, `r` raw toggle) and `monitor_shared` ANSI→Rich.
- **Text search** (`/`, `n`, `esc`) over the ANSI-stripped text (logview
  precedent).
- **Select + copy**: Textual 8.2.7 native mouse selection (`ALLOW_SELECT`,
  `get_selection` — `Log`/`RichLog` implement it) plus a keyboard line-range
  select (codebrowser `code_viewer.py` shift+up/down model); copy MUST go
  through `lib/tui_clipboard.copy_to_system_clipboard` (OSC52 + tmux
  `load-buffer -w`; enforced by `tests/test_tui_clipboard_seam.sh`).
- **Restore** action: build `claude --resume <id>` / `codex resume <id>` from
  the record's agent string (via `aitask_codeagent.sh` so model/binary
  resolution stays single-sourced) and relaunch it **in this same pane**
  (respawn-pane), clearing the frozen record; **Re-pick** action when
  `task_id` is present (reuse the existing pick launch path).
- Header shows identity: project, window, task id/title, agent, frozen_at.
- Register as a switcher-visible TUI: 4-part atomic change in
  `lib/tui_registry.py` + `tui_switcher.py` (`_TUI_SHORTCUTS`, `Binding`,
  `action_shortcut_<name>`), add the module to `KNOWN_BINDING_SOURCES`, follow
  `aidocs/framework/tui_conventions.md` and `tmux_gateway.md`; website page
  under `website/content/docs/tuis/`.

## Minimonitor / monitor integration

- Discovery must recognise a frozen stand-in pane (via the `@aitask_frozen`
  pane option or record lookup) and produce a `PaneSnapshot` flagged `frozen`
  — listed in the agents section like a `parked` row (`_agent_card_text`
  branch: glyph + name + `frozen`), excluded from the idle/awaiting/done state
  partition and from capture (`monitor_core` classification must not run
  prompt detection on it); session-bar counter `Nf` alongside `Np`.
- Keys: freeze the followed agent (from the companion), freeze from the list,
  Freeze-All, restore / re-pick a frozen row; a filter toggle analogous to `P`.
  Keep `k`/`n`/`space` semantics sane on a frozen row (e.g. `k` removes the
  stand-in + record; `space` mark cycle disabled or defined).
- `kill_agent_pane_smart` / `aitask_companion_cleanup.sh` sibling counting must
  treat the stand-in consistently (a frozen stand-in is not a "real agent" for
  keeping the companion alive when another agent dies? — decide and test).
- Same treatment in `ait monitor` (`monitor_app.py`) rows.

## Key code touchpoints (from exploration)

- `.aitask-scripts/lib/agent_marks.py`, `aitask_agent_marks.sh` — store/lock
  template (v2 schema, `registry_lock.sh`, liveness purge with `--observed`)
- `.aitask-scripts/monitor/monitor_core.py` — `PaneCategory`, `TmuxPaneInfo`,
  `PaneSnapshot.parked`, `classify_pane`, `_capture_args`,
  `kill_agent_pane_smart`, `task_id_from_window_name`, `TaskInfoCache`
- `.aitask-scripts/monitor/minimonitor_app.py` — `_agent_card_text`,
  `_rebuild_pane_list` (`P` filter), `action_toggle_mark`, BINDINGS /
  `#mini-key-hints` parity test; `monitor_app.py` counterpart
- `.aitask-scripts/lib/agent_launch_utils.py` — `launch_in_tmux`,
  `maybe_spawn_minimonitor`, `attach_companion_cleanup_hook`,
  `discover_aitasks_sessions`, `resolve_dry_run_command`
- `.aitask-scripts/aitask_companion_cleanup.sh` — pane-died kill logic
- `.aitask-scripts/aitask_codeagent.sh`, `lib/agent_string.sh`,
  `lib/agent_command_screen.py` — launch command construction / agent string
- `.aitask-scripts/logview/logview_app.py`, `codebrowser/code_viewer.py`,
  `lib/tui_clipboard.py` — viewer building blocks
- `.aitask-scripts/lib/tui_registry.py`, `lib/tui_switcher.py`,
  `lib/keybinding_registry.py` (`KNOWN_BINDING_SOURCES`)
- `.claude/settings.json` (existing PreToolUse hook), `.codex/config.toml`,
  `seed/`, `aitask_setup.sh` — hook installation
- `aidocs/framework/tui_conventions.md`, `tmux_gateway.md`,
  `aitasks_extension_points.md`; `website/content/docs/tuis/`

## Suggested child decomposition (refine at planning)

1. Session-id capture: SessionStart hooks for claude/codex (+ seed/setup
   install), pane option + fallback resolution, tests with fixture payloads.
2. Framework session store: schema, locked writer script, lock-free reader,
   liveness/expiry policy, CLI verbs (list / freeze-record / restore-record /
   purge), unit tests.
3. Freeze engine: capture + stamp + cleanup-script abstention + respawn-pane
   stand-in; live tmux tests (outside the user's main tmux server — see
   `tui_conventions.md` "Tmux-stress tasks").
4. Viewer TUI: ANSI rendering + plain/markdown toggle, search, select/copy,
   restore / re-pick actions, header; switcher + shortcut-manifest
   registration.
5. Minimonitor + monitor integration: frozen snapshot flag, rows, counters,
   filter, keys (freeze followed / freeze-all / restore), sibling-count rules.
6. Restore flows: `--resume` command construction via `aitask_codeagent.sh`,
   re-pick path, Restore-All; edge cases (transcript missing, agent CLI
   missing).
7. Website docs + `aidocs/framework` notes (new TUI page, minimonitor page
   updates, session concept in concepts/).
