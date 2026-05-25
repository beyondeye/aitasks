# TUI (Textual) Conventions

Specialist guidance for authoring or modifying Textual-based TUIs under
`.aitask-scripts/` (board, monitor, minimonitor, codebrowser, brainstorm,
settings, syncer, stats-tui, diffviewer, the TUI switcher, etc.).

## TUI launchers resolve Python via `require_ait_python`

When introducing a new launcher `.sh` under `.aitask-scripts/` for a Textual
TUI — long-running or short-lived — use:

```bash
PYTHON="$(require_ait_python)"
```

at the top of the script. All TUIs share a single CPython 3.14+ venv at
`~/.aitask/venv/`, resolved through `lib/python_resolve.sh`. The framework
has one Python runtime; no per-TUI interpreter selection.

For historical context on the retired PyPy fast path and the conditions
under which a future re-evaluation would be warranted, see
`aidocs/python_tui_performance.md`.

## `n` is the create-task key across every aitasks TUI

`n` binds to create-task in board, codebrowser, minimonitor, monitor,
brainstorm, and the TUI switcher modal. Do not default to `c` or other
alternatives when adding a create-task binding to a new TUI. Related TUIs may
bind `n` to "next" (monitor, logview, diffviewer) — those are read-oriented
TUIs without a create-task action, so the conflict is only notional.

## Priority bindings + `App.query_one` gotcha

When an `App` and a pushed `Screen` define a binding with the same action name
and `priority=True`, the App-level action runs first. If its "am I in the right
screen?" guard uses `self.query_one(...)`, the query walks the entire screen
stack and will match widgets from underlying screens — so the guard succeeds
for the wrong screen, consumes the key, and the active screen's own binding
never fires.

Scope guards to `self.screen.query_one(...)`. On guard-miss, raise
`textual.actions.SkipAction` so the next priority binding (the active screen's
own action) gets a chance. Alternative: use distinct action names per screen.

## No auto-commit/push of project-level config from runtime TUIs

Runtime `save()` paths in config modules must write only the user-level
(`*.local.json`, gitignored) layer. Project-level (`*.json`, tracked) files
are read-only at runtime unless there is an explicit user-initiated "export /
publish" action.

Never call `git commit` or `./ait git push` from inside a TUI event handler
for a config change. First-time ship of a project-level file is a one-time
implementation commit; runtime saves after that must not touch it.

## Contextual-footer ordering: keep uppercase sibling adjacent to its lowercase primary

When a pane's footer includes both a lowercase primary action (e.g., `d` =
toggle detail) and its uppercase sibling (e.g., `D` = expand detail), keep them
adjacent in the footer — `d D …`, not `d c D …`.

The uppercase-to-tail demotion rule applies only to uppercase keys whose
primary is NOT itself in the pane's suffix. Example: in `detail_pane` the
suffix should be `["d", "D", "c", "H"]` — `D` adjacent to `d`; `H` (whose `h`
primary lives in `PRIMARY_ORDER`) at the tail.

## Pane-internal cycling uses `←` / `→` arrow keys

For pane-level item cycling inside a Textual TUI (e.g., cycling operations in
the stats verified-rankings pane), use ←/→ arrow keys — not `[` / `]` brackets.
Arrows are more discoverable and ergonomic for left/right motion.

When designing a pane that needs prev/next cycling within a shared right-hand
content area:
- Use App-level bindings for `"left"` / `"right"` so the sidebar `ListView`
  (which only consumes ↑/↓) doesn't interfere.
- Ensure inner widgets don't consume left/right — e.g., set
  `DataTable(cursor_type="row")` so the table's default cell-cursor bindings
  are inactive.
- Guard the action handler on the currently-visible pane id so arrows are a
  no-op when viewing other panes.
- Keep `show=False` on the bindings to avoid cluttering the footer; surface the
  hint in the pane's own header text instead.

## TUI switcher shortcuts act on the *selected* session, not the attached one

In the multi-session TUI switcher, shortcut keys (`b` board, `m` monitor, `c`
codebrowser, `s` settings, `t` stats, `r` brainstorm, `g` git, `x` explore,
`n` new task) act on the selected (Left/Right-browsed) session — identical to
pressing Enter on that TUI's row in that session. Cross-session teleport
(`switch-client`) fires automatically when the selected session differs from
the attached one.

Future work on `.aitask-scripts/lib/tui_switcher.py` and related keybinding
docs must preserve shortcut-on-selected semantics. `self._session` in a
shortcut handler is the *selected/operating* session (mutated by Left/Right) —
that read is correct. The separate `self._attached_session` attribute exists
only to decide whether to issue `switch-client`. Do not "fix" the asymmetry by
routing shortcuts through the attached session or by adding a current-running-
names set.

## Single tmux session per project

The aitasks framework is designed to use exactly ONE tmux session per project.
All TUIs, agents, monitor, minimonitor, brainstorm, and codebrowser of a given
project live inside that one session (configured by `tmux.default_session` in
`aitasks/metadata/project_config.yaml`).

Users routinely run multiple aitasks projects side-by-side (e.g., `aitasks`
and `aitasks_mob`) in different terminals. Each project must stay fully
isolated in its own tmux session so TUIs and singletons (lazygit, brainstorm,
monitor) do not cross-contaminate between projects.

How to apply:
- Any tmux lookup that scans across sessions (e.g., `find_window_by_name`
  iterating `get_tmux_sessions()`) is architecturally incorrect and must be
  scoped to the current project's session.
- Any `tmux -t <session>` target must use exact match (`-t =<session>`) —
  tmux's default prefix match means a session named `aitasks` silently
  resolves to `aitasks_mob` if that's the only running match, crossing project
  boundaries.
- When reviewing multi-project behavior, assume the user may have several
  session names that share prefixes.

## Companion pane auto-despawn — kill the companion only, never the window

When spawning a companion pane (e.g., `minimonitor`) alongside a primary
command in a new tmux window (git TUI / `ait create` / explore agents /
similar), the companion must auto-despawn when the primary exits — but only
the companion pane, and only if no other sibling pane is still using the
window.

Two failure modes to avoid:
1. Blanket-killing the window (`tmux kill-window`) tears down user-created
   panes (shells, notes).
2. A global "kill companion on any pane-exit" approach despawns prematurely
   when one of several primary-like siblings exits.

The companion should persist until *every* primary-like pane is gone.

How to apply:
1. Capture the primary pane id (`tmux new-window -P -F "#{pane_id}"`) and
   companion pane id (same flags on `split-window`) at spawn time.
2. Attach a pane-scoped `pane-died` hook to the primary (`tmux set-hook -p -t
   <primary> pane-died …`) with `remain-on-exit on` so the hook fires.
3. The hook calls a cleanup script that lists panes in the window, excluding
   primary + companion. If zero other panes → kill both. If ≥1 → kill only
   the primary and leave the companion alive.
4. Do NOT use `tmux kill-window`.
5. Do NOT use a global "kill companion on any pane-exit" approach.

Canonical helper lives at `.aitask-scripts/aitask_companion_cleanup.sh` (shell
script, called via `tmux run-shell`, not from a code-agent skill — no
whitelisting touchpoints).

## TUI footer must surface every operation on the affected tab/screen

When a plan adds keybindings to a Textual TUI tab/screen, the same plan must
also flip pre-existing `show=False` bindings and `on_key`-only handlers (no
`Binding` declared) on that tab/screen to footer-visible `Binding`
declarations. Partial coverage is worse than none because it misleads users
into thinking the visible set is complete.

How to apply:
- Audit every existing binding on the affected widget/screen. Convert
  `on_key`-only handlers to proper `Binding` declarations with `action_*`
  methods.
- Default new bindings to `show=True` with a short, user-friendly label.
- For pre-existing `show=False` bindings, propose flipping them to `show=True`
  (or justify keeping them hidden — e.g., internal navigation that would
  clutter the footer) in the same plan.
- Arrow-key bindings can be footer-visible if they are part of the primary
  interaction model (e.g., 2D graph navigation); don't reflexively hide them
  just because Textual examples often do.
- Surface this as an explicit deliverable in the child task that introduces
  the new operations.

## Tmux-stress tasks: implement outside the user's main aitasks tmux

For tasks whose tests/verification destructively manipulate tmux (`kill -KILL`
of `tmux -C attach` children, `tmux kill-session`, `tmux kill-server`, `tmux
pause-pane`, etc. — typical surface: `.aitask-scripts/monitor/`,
`tmux_control.py`, `agent_launch_utils.py`, resilience test suites), the
implementation must NOT run from inside the user's active aitasks tmux
session. Even with per-case `TMUX_TMPDIR` sockets, a wrong test or an embedded
helper bug can blast the user's real session and take all running code agents
down.

How to apply:
- Flag the risk before drafting the verification section. Recommend the user
  pick the task from a shell that is **not** inside their main aitasks tmux.
  The plan can still be written from inside; only implement + verify need the
  outside-tmux precaution.
- If the user is mid-pick when the risk surfaces, offer "abort + revert to
  Ready, keep the plan" as the default action — do not push through
  implementation.
- If only a subset of test cases need a sandboxed tmux, split them into a
  separate runner script the user invokes from a clean shell.
