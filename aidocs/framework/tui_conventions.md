# TUI (Textual) Conventions

Specialist guidance for authoring or modifying Textual-based TUIs under
`.aitask-scripts/` (board, monitor, minimonitor, codebrowser, brainstorm,
settings, syncer, stats-tui, diffviewer, the TUI switcher, etc.).

## Long-running Textual TUI launchers may call `require_ait_python_fast` (current scope: `ait board` only)

`require_ait_python_fast` resolves to PyPy when the user has run
`ait setup --with-pypy`, and falls through to CPython otherwise. At present
the only launcher that uses it is `aitask_board.sh`:

```bash
PYTHON="$(require_ait_python_fast)"
```

All other launchers — including `aitask_settings.sh`, `aitask_brainstorm_tui.sh`,
`aitask_syncer.sh` — stay on `require_ait_python`. These three were previously
routed to the fast path "by analogy with board" but were never empirically
measured; that routing-by-analogy is what t785 cited when retiring the entire
fast path. t831 brought the fast path back scoped to board only.

**Rule for new fast-path adoption.** Do not add `require_ait_python_fast` to
a launcher without a per-TUI benchmark following the t718_6 protocol
(`aidocs/framework/python_tui_performance.md`, "t718_6 Empirical Verification"). Routing
by analogy is no longer acceptable.

**Permanent exceptions** (empirically verified — keep on CPython regardless of
benchmark interest):
- `codebrowser` (PyPy ~17% slower steady-state, ~2× slower cold-start)
- `monitor` / `minimonitor` (PyPy 76–90% slower at typical pane counts)
- `stats-tui` (depends on `plotext`, installed only in the CPython venv)
- `diffviewer` (until its brainstorm integration lands)

Short-lived CLIs (one-shot helpers, `ait create`, status reporters) keep
`require_ait_python` to avoid the ~150-300 ms PyPy warmup penalty. Full
evidence and tables: `aidocs/framework/python_tui_performance.md`.

## `AIT_USE_PYPY` precedence (runtime override)

When PyPy has been installed via `ait setup --with-pypy`, `aitask_board.sh`
auto-routes through `~/.aitask/pypy_venv`. The `AIT_USE_PYPY` env var
overrides per invocation, but **only on launchers that call
`require_ait_python_fast`** (currently just `aitask_board.sh`):

| `AIT_USE_PYPY` | PyPy installed? | Result for `ait board` |
|----------------|-----------------|------------------------|
| `1`            | Yes             | PyPy (forced) |
| `1`            | No              | error: install with `ait setup --with-pypy` |
| `0`            | (any)           | CPython (override) |
| unset          | Yes             | PyPy (default once installed) |
| unset          | No              | CPython (current behavior preserved) |

`ait settings`, `ait brainstorm`, `ait syncer`, and other launchers that
use `require_ait_python` ignore `AIT_USE_PYPY` — the env var precedence
lives inside `require_ait_python_fast`. To A/B-test one of those TUIs
under PyPy, point `AIT_PYTHON` at the PyPy venv binary for that invocation
(`AIT_PYTHON=~/.aitask/pypy_venv/bin/python ait settings`); this is a
manual hook intended for measurement, not a supported runtime mode.

Codebrowser / monitor / minimonitor / stats-tui stay on CPython regardless of
`AIT_USE_PYPY` (see the exceptions list above). Full analysis:
`aidocs/framework/python_tui_performance.md`.

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

The same App-priority-first ordering bites **arrow-key navigation** in a pushed
modal: in Textual 8.x an App's `priority=True` binding fires before a modal's own
`priority=True` binding, so a modal that wants ←/→/↑/↓ gets nothing when the App
already binds those keys (e.g. `KanbanApp` binds `left`/`right` for column nav).
Two remedies:

- **Blanket (preferred when the modal just needs default widget navigation):**
  gate the App's nav actions in `check_action` — `if action in ("nav_up",
  "nav_down","nav_left","nav_right") and len(self.screen_stack) > 1: return
  False`. Returning `False` for a priority binding makes Textual treat it as
  inactive, so the key falls through to the focused modal widget. Covers any
  current or future pushed modal without per-class enumeration.
- **Targeted (when the App action must delegate to the modal's widget):** make
  the App action modal-aware and **duck-type across class boundaries** — a modal
  under `lib/` has its own widget classes, so `isinstance(focused, CycleField)`
  against the App's own `CycleField` won't match; test
  `hasattr(focused, "cycle_prev")` / `getattr` for the method instead. See
  `aitask_board.action_nav_left`.

## Modals pushed by multiple Apps must carry their own DEFAULT_CSS

A `lib/` `ModalScreen` that can be pushed by more than one App must define its
own `DEFAULT_CSS` for everything its descendant widgets need — it does NOT
inherit the pushing App's CSS. A modal that borrows the launching App's styles
(focus highlight, `.section-header` / `.section-hint`, per-widget heights) looks
correct from its "home" App but loses all of it when pushed from another: e.g.
`lib/profile_editor.ProfileEditScreen` relied on `SettingsApp.CSS`, so pushed
from `ait board` the focus highlight vanished and rows were unstyled, making the
arrow-key UI feel broken. Give the modal a `DEFAULT_CSS` class attribute
covering dialog size, focus-highlight rules for any `.focused`-class widget,
header/hint styling, and widget heights/paddings; mirror the rules from any App
that already styles those widgets so behavior is identical across launch
surfaces. Always include a help/instructions line so keyboard discoverability
never depends on focus styling alone. (See the priority-bindings note above for
the matching arrow-key fix.)

## Filters over a multi-select list keep selected rows visible

A search/fuzzy filter over a **multi-select** list (e.g. the `FuzzyCheckList`
widget) must keep already-checked rows **on screen** even when they don't match
the current query — "view-only filter" / "selection survives filtering" means
visible-on-screen, not merely state-preserved-in-memory. The visibility rule is
`display = matched OR checked`; only unselected non-matching rows are hidden.
Implementing it as `display = matched` (hide checked-but-unmatched rows, preserve
state) reads as broken — the user loses sight of their current selection. When a
requirement says "view-only filter", confirm it means visible-on-screen rather
than assuming hidden-but-state-preserved.

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

## Two-axis project-group navigation (switcher + stats)

The multi-session switcher and the stats TUI navigate sessions along **two
independent axes**:

- **Left / Right** cycles the **ring** — the *derived* session list for the
  currently selected project-group: that group's members plus any **live**
  session outside the group (so a live repo is always reachable). Stale
  out-of-group sessions are dropped from the ring.
- **`[` / `]`** cycles the **selected project-group**, re-deriving the ring.

Both axes consume `group_sessions(sessions, selected_group) -> GroupedSessions`
in `agent_launch_utils.py` — the TUIs never re-derive grouping. The selected
group defaults to the **selected (operating) session's** resolved
`project_group` (via `default_selected_group`), NOT the attached session's, so a
switcher opened with a cross-group preselected session (monitor / minimonitor)
lands on that session's group. `[` / `]` advance the group via
`advance_selected_group`; a session that falls out of the new ring is re-pointed
to a ring member.

Two TUI-specific rules:

- **Stats `[` / `]` are pane-guarded and dual-meaning.** On the agents ranking
  panes (`agents.verified` / `agents.usage`) they cycle the ranking *time
  window*; on every other pane they cycle the *project-group*. This mirrors how
  Left/Right routes to session cycling only off those panes. The footer label
  reads `win/grp` to reflect both meanings.
- **The stats "All sessions" aggregate is a fixed final ring member.** It is
  layered onto the ring by the TUI's ring builder (`_session_ring`), *not* by the
  pure `group_sessions()`. Left/Right reaches it; `[` / `]` group cycling never
  selects it (it is group-agnostic).

## Registering a switcher-visible TUI is a four-part atomic change

Adding a TUI to `TUI_REGISTRY` in `.aitask-scripts/lib/tui_registry.py` is not
complete on its own. A switcher-visible TUI needs all four of these, changed
together:

1. **Registry position** in `TUI_REGISTRY` — order by user-perceived,
   related-functionality grouping, NOT alphabetically by name (e.g. App Linker
   sits after `stats` and before `diffviewer`).
2. **A single-letter shortcut** in `_TUI_SHORTCUTS` in `tui_switcher.py` — pick a
   free, mnemonic letter (the taken set is whatever `_TUI_SHORTCUTS` currently
   holds; read it, don't hardcode the list).
3. **A matching `Binding(...)` row** in the switcher's `BINDINGS`.
4. **An `action_shortcut_<name>(self)` method** that calls
   `self._shortcut_switch("<name>")`.

Without 2–4 the TUI appears in the modal but can't be teleported to with a
keystroke, while every other switcher-visible TUI can. Treat the four as one
atomic change. (`applink` is the worked example: registry row + shortcut `a` +
`Binding("a", "shortcut_applink")` + `action_shortcut_applink`.)

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
  boundaries. This section owns the *why*; the mandatory exact-match helpers
  (`session_target` / `ait_tmux_session_target`) and the gateway they live in
  are documented in `aidocs/framework/tmux_gateway.md`.
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

### The shadow agent is a second companion-pane case

minimonitor is no longer the only companion pane. The **shadow** agent
(`aidocs/framework/shadow_agent.md`) is a second kind of companion: an advisory
coding agent spawned, by default, as a split in the **same window** as the agent
it follows (configurable to a separate window). Code that reasons about the panes
in an agent window must account for it on two fronts:

- **It must never be counted as a real agent.** The shadow pane carries the
  pane-scoped tmux user option `@aitask_shadow_target` (set to the followed
  agent's `pane_id`). monitor / minimonitor exclude any pane carrying that option
  from agent snapshots, and `kill_agent_pane_smart`'s window-vs-pane decision
  excludes it from the real-agent sibling count — exactly as the
  minimonitor / monitor panes are excluded. Per-agent state is keyed by
  `pane_id` (see `tmux_gateway.md`), so several real agents can share one window
  without a shadow being mistaken for one.
- **It is bound to one followed agent.** When the followed agent's pane dies, its
  bound shadow is killed automatically (`aitask_companion_cleanup.sh` matches
  `@aitask_shadow_target` against the dying pane) even if other agents remain in
  the window; killing a *different* agent leaves an unrelated shadow alive. A
  shadow pane never keeps the minimonitor companion alive once the last real
  agent in the window is gone.

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

## brainstorm TUI information architecture

The `ait brainstorm` TUI is organized as **three peer tabs** plus an always-on
runtime strip:

- **Browse** (`b`) — the node DAG with a graph⇄list toggle (`v`, persisted per
  session) and one shared `NodeDetailPanel`. `space` marks nodes; `Enter` opens
  the Node Hub; `A` opens the contextual Operations dialog; `c` opens the
  compare-matrix overlay on the marked set. `d`/`g` are view-specific
  muscle-memory shortcuts into Browse.
- **Session** (`s`) — session-lifecycle operations (pause / resume / finalize /
  archive / delete) with inline confirms.
- **Running** (`r`) — the runtime monitor: runner state, running processes,
  operation groups, and agent logs. Per-row agent actions operate on the
  focused row: `p` pause/resume, `k`/`K` kill, `w` reset, `R` retry (reset +
  ensure the runner relaunches), `x` clean up a finished/failed entry (confirm
  modal), `e` edit launch mode, `L` open log.

Above the tabs, an **always-on runtime strip** mirrors the runner state and the
running-op count (`[●] <runner state>   ▶ N running`) so it is visible from
every tab. Its derivation (`derive_runner_state` / `format_status_strip` in
`brainstorm_app.py`) is a pure function, unit-tested independently of the App.

## New TUIs / dialogs must register in the global shortcut manifest

Every Textual App or modal/sub-screen that owns customizable shortcuts sets
`_shortcuts_scope` and registers its bindings via `ShortcutsMixin.__init__`
(or, for module-level widgets, a class-body `register_app_bindings("<scope>",
…)`). That registration is **lazy** — it only happens when the class is
instantiated/imported. The **Settings → Shortcuts** tab, however, must list
*every* TUI's bindings in a process where only `SettingsApp` runs, so it relies
on the global sweep `register_all_known_bindings()` in
`.aitask-scripts/lib/shortcut_scopes.py`.

How to apply when you add a new scope:
- A new dialog/sub-screen **inside an existing TUI module** (one already listed
  in `KNOWN_BINDING_SOURCES`) is picked up automatically — the sweep imports the
  module and introspects its classes for `_shortcuts_scope`. No manifest edit
  needed.
- A **brand-new TUI module file** MUST be added to `KNOWN_BINDING_SOURCES` in
  `lib/shortcut_scopes.py` (entry: `(module_name, path_relative_to_.aitask-scripts,
  scopes_tuple)`, where `scopes_tuple` lists every scope the module contributes).
- `tests/test_shortcut_scopes.py` is a drift guard: it scans the source tree for
  every `_shortcuts_scope`/`register_*bindings` declaration and fails if the
  sweep does not register it — so a forgotten manifest entry surfaces as a test
  failure naming the missing scope, not a silently-empty Settings tab.
- Keep `KNOWN_BINDING_SOURCES` module-only (no per-class entries); the sweep
  reads class attributes without instantiating, so do not add heavy
  instantiation there.

The in-TUI `?` editor uses the same manifest, *filtered*: it calls
`shortcut_scopes.register_scope_bindings(scope)` (from
`ShortcutsMixin.action_open_shortcuts_editor`) so the active TUI's modal
sub-scopes (e.g. `board.detail`) and the shared cross-TUI dialogs (`shared.*`,
e.g. `shared.agent_cmd`) are listed up front without opening each modal
first — and without importing every other TUI. The `scopes`
column in `KNOWN_BINDING_SOURCES` is what drives that filtering. The `?` editor
binding itself (`open_shortcuts_editor`) is a **`shared`-scope** shortcut,
registered at import by `shortcuts_mixin.register_shared_bindings()` (mirroring
the `j` TUI switcher); the shared-action de-dup in `register_app_bindings` then
lists it once under `shared` and applies a rebind in every TUI.

## Tmux-stress tasks: implement outside the user's main aitasks tmux

For tasks whose tests/verification destructively manipulate tmux (`kill -KILL`
of `tmux -C attach` children, `tmux kill-session`, `tmux kill-server`, `tmux
pause-pane`, etc. — typical surface: `.aitask-scripts/monitor/`,
`tmux_control.py`, `agent_launch_utils.py`, resilience test suites), the
implementation must NOT run from inside the user's active aitasks tmux
session. Even with per-case `TMUX_TMPDIR` sockets, a wrong test or an embedded
helper bug can blast the user's real session and take all running code agents
down. Note that since t953 ait sessions live on the dedicated `-L ait` socket,
so "the user's main aitasks tmux" means the dedicated server, not the personal
default one; the test isolation helper (`tests/lib/tmux_isolation.sh`) pins
`AITASKS_TMUX_SOCKET=""` in addition to redirecting `TMUX_TMPDIR`, so isolated
tests can reach neither the personal default server nor the dedicated `ait`
server.

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
