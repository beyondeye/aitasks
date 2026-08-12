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

## Startup focus: `AUTO_FOCUS` can hand the keyboard to a text `Input`

`Screen._update_auto_focus` runs inside `Screen._compose` — **before** the
app's `on_mount` — and focuses the first *focusable* widget in DOM order that
matches the resolved selector:

```python
auto_focus = self.app.AUTO_FOCUS if self.AUTO_FOCUS is None else self.AUTO_FOCUS
```

Two consequences that have each cost a bug:

- **`App.AUTO_FOCUS` defaults to `"*"`.** A TUI that sets nothing is opted *in*.
- **`Screen.AUTO_FOCUS = None` means "inherit the app's"** — it disables
  nothing. Only a falsy selector (`""`) actually skips the loop.

When the winner is a text `Input`, every **non-`priority`** binding is swallowed
as text. Only `priority=True` bindings (typically arrows/tab/escape) keep
working, so the TUI still feels alive — which is why t1491 was first filed as a
*relaunch* bug rather than "`q` does not quit".

### The two-layer fix

Both layers are needed; neither alone is sufficient:

1. A `Screen` subclass with `AUTO_FOCUS = ""`, returned from
   `App.get_default_screen()`. Scope it to the **default screen** so pushed
   modals keep the app-level `"*"` and still focus their first control.
2. A `_claim_startup_focus()` deferred from `on_mount` via `call_after_refresh`,
   anchoring focus on a real widget. Layer 1 alone leaves the screen unfocused —
   safe (keys route to the App bindings) but with no navigation anchor; layer 2
   alone leaves a ~100–250ms window in which the `Input` owns the keyboard.

Reference implementations: `board/aitask_board.py` (`BoardScreen`,
`KanbanApp._claim_startup_focus`) and `codebrowser/codebrowser_app.py`
(`CodeBrowserScreen`, `CodeBrowserApp._claim_startup_focus`). Reuse the app's
existing focus-cycle helper for the anchor rather than restating its preference
order — the codebrowser's claim calls `_focus_recent_or_tree`, which
`action_toggle_focus` already owns.

### Verify in a real pty — a headless pin may not fail

`Screen._update_auto_focus` can pick a **different widget under `App.run_test`
than under a real terminal**, because the two drivers differ in what is mounted
and visible at compose time. Measured on the board at Textual 8.2.7, same
fixture and size: a real terminal picked `Input#search_box`, `run_test` picked
`HorizontalScroll#board_container` — where `q` quit fine. So a passing headless
test is **not** evidence.

The divergence is not universal: it depends on how many focusable widgets the
branch has. The codebrowser's non-git branch has so few that `run_test` picks
the `Input` too, and its headless pin does fail pre-fix. Determine it per app;
do not assume either way.

To diagnose, trace rather than read the screen: wrap
`textual.screen.Screen._update_auto_focus` to log the resolved selector and the
widget it left focused, inject it via a `sitecustomize.py` on `PYTHONPATH` (which
preserves the real entry point), and run the TUI in a tmux pane. Pass the env
with an `env` prefix on the command — `tmux set-environment` only reaches panes
tmux spawns itself, not a command typed into an already-running shell. Always
run the probe against a TUI whose behaviour is already known first: an empty
trace means the probe never fired, and that reads exactly like "nothing was
picked".

### Audit status (t1495)

Verified live in a tmux pane at Textual 8.2.7. "Picked" is the widget
auto-focus left focused at compose.

| App | picked at compose | bare `q` | status |
|---|---|---|---|
| `board/aitask_board.py` | auto-focus disabled → claim anchors `TaskCard` | quits | fixed (t1491) |
| `codebrowser` (git repo) | `RecentFilesList#recent_files` | quits | not affected |
| `codebrowser` (non-git) | **`Input#file_search_input`** | **swallowed** | **fixed (t1495)** |
| `monitor/monitor_app.py` | `VerticalScroll#pane-list` | quits | not affected |
| `brainstorm/brainstorm_app.py` | `ContentTabs` | quits | not affected |
| `settings/settings_app.py` | `ContentTabs` | quits | not affected |
| `logview/logview_app.py` | — | — | immune via an `on_mount` focus (t1486) |

The three "not affected" apps land on a scroll container or a tab bar, which
bind arrows and not letters. They still have **no startup focus anchor**, so no
row/card is selected until the user presses Tab or clicks — a UX gap, not this
defect.

**Unaudited — treat as unknown, not clear.** These set no `AUTO_FOCUS` either
and have not been driven in a pty: `monitor/minimonitor_app.py`,
`syncer/syncer_app.py`, `chatlink/chatlink_app.py`, `applink/applink_app.py`,
`diffviewer/diffviewer_app.py`, `agentcrew/agentcrew_dashboard.py`. Static
reading suggests none mounts a text `Input` on its default screen, but that is
exactly the claim t1495 existed to stop taking on trust.

The only other place that disables auto-focus today is
`lib/agent_command_screen.py` (`AgentCommandScreen.AUTO_FOCUS = ""`), a modal
shared by several apps.

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

## Terminal-width tiers vs component minimum widths

Two different questions get asked about width, and conflating them is how the
repo accumulated four unrelated "narrow" numbers before t1251:

- **"How wide is this terminal?"** — a *layout tier* decision. Shared. Branch on
  `lib/tui_layout.py`: `terminal_tier(width)` → `NARROW` / `NORMAL` / `WIDE`, or
  `is_narrow_terminal(width)` for the two-way case.
- **"How many cells does this widget need?"** — a *component minimum width*. It
  belongs to that widget and stays in its class.

**Rules.**

1. Never write a bare terminal-width comparison (`if width >= 120:`,
   `if app_width < 80:`). Call `terminal_tier` / `is_narrow_terminal` instead.
   The tier constants live in exactly one place so a UX retune is one edit.
2. Keep the *per-tier dimensions* local. `lib/tui_layout.py` owns the tier
   boundary; the TUI owns what it does at each tier — e.g.
   `CodeBrowserApp.SIDEBAR_WIDTH_BY_TIER = {WIDE: 35, NORMAL: 28, NARROW: 22}`.
3. Never reuse a tier constant as a component floor because the numbers match
   today. `CODE_MIN_WIDTH` is 80 and `NARROW_TERMINAL_WIDTH` is 80, but they are
   independent decisions; coupling them means a tier retune silently resizes the
   code pane.
4. **Prefer deriving the threshold from live geometry** over any constant.
   `KanbanApp._apply_filter_reflow` computes its breakpoint as
   `selector.content_width() + 2 + FILTER_SEARCH_MIN_WIDTH` — it cannot drift
   when the selector grows a filter. Reach for a tier constant only when there
   is nothing to measure.

**Constants that deliberately did NOT move into `lib/tui_layout.py`** (t1251
inventoried these; do not "finish the job" by centralizing them):

| Constant | File | Why it stays |
|---|---|---|
| `CODE_MIN_WIDTH = 80` | `codebrowser/codebrowser_app.py` | Code-pane floor; equals the narrow tier by coincidence. |
| `DETAIL_DEFAULT_WIDTH = 30` | `codebrowser/codebrowser_app.py` | Detail-pane default width, not a threshold. |
| `FILTER_SEARCH_MIN_WIDTH = 30` | `board/aitask_board.py` | Search-box floor. t1247 made it the sole source of truth — deliberately not mirrored into CSS. |
| `_SENTINEL_SAFE_COLS = 24` | `monitor/concern_parser.py` | Derived from the sentinel strings' own lengths (21/18 chars). A *correctness* threshold, not a UX one. |
| `_NARROW_PREFIX_COLS = 8` | `monitor/monitor_shared.py` | Fixed prefix cost of a concern row. |
| `target_width = 40` | `monitor/minimonitor_app.py` | A tmux **pane** width the app pins itself to (from `tmux.minimonitor.width`), not a test against the terminal. |

**The `narrow: bool` dialog kwarg is not a width test.** The `narrow` parameter
threaded through `monitor_shared.py`, `lib/agent_command_screen.py`,
`lib/agent_model_picker.py`, and `lib/tui_switcher.py` is a **host-role flag**:
`TuiSwitcherMixin._switcher_narrow()` returns a static `False` and minimonitor
overrides it to `True` because it always lives in a ~40-column split pane.
Nothing measures the terminal, so there is no tier to consult. Do not "fix" it
to call `is_narrow_terminal`.

## Clipboard copies route through `lib/tui_clipboard.copy_to_system_clipboard`

Never call Textual's `app.copy_to_clipboard` directly from TUI code
(`tests/test_tui_clipboard_seam.sh` enforces this). Textual's method emits a
bare OSC 52 escape, and tmux only forwards a pane's OSC 52 to the outer
terminal when that pane is in the client's **visible** window — from a
background window (or a session no terminal client is attached to, e.g. a
second project session) the text lands in a tmux paste buffer and the system
clipboard is silently left untouched, while the TUI still shows its "copied"
notification. `copy_to_system_clipboard(app, text)` keeps the OSC 52 copy
(the working path outside tmux) and, when `$TMUX` is set, additionally pushes
the text through the tmux gateway (`TmuxClient.set_clipboard`, i.e.
`load-buffer -w`), which forwards to attached clients regardless of pane
visibility.

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
2. Arm the hook through `agent_launch_utils.attach_companion_cleanup_hook`,
   which sets `remain-on-exit on` and appends the pane-scoped `pane-died` hook
   at the first free index. **Never open-code `tmux set-hook -p -t <primary>
   pane-died …`**: a bare `set-hook` writes index `[0]` and silently destroys
   whatever hook already sits there.
3. The hook calls a cleanup script that lists panes in the window and decides
   whether any *real agent* sibling remains. If none → kill the primary and
   every companion. If ≥1 → kill only the primary and leave companions alive.
4. Do NOT use `tmux kill-window`.
5. Do NOT use a global "kill companion on any pane-exit" approach.

Every companion spawn path now arms the hook from that one helper:
`maybe_spawn_minimonitor` (board / codebrowser / crew / syncer / monitor picks),
`spawn_shadow`, and `tui_switcher`'s git-TUI branch. Before t1451 the first of
those armed nothing at all, so board- and codebrowser-launched windows carried a
companion with no hook.

**Cleanup discovers companions by MARKER, not from the hook payload.** One
`pane-died` hook carries exactly one `companion_pane`, and the helper never
overwrites — so the argument can only ever name whichever companion armed the
hook *first*. With a shadow-first ordering that argument is the *shadow's* pane,
and a minimonitor sharing the window then reads as a real agent sibling, sparing
both. So the `companion_pane` argument is a best-effort hint for panes predating
the markers, and the authority is the pane options: `@aitask_monitor_kind`
(monitor/minimonitor companions) and `@aitask_shadow_target` (shadows). Both
orderings are pinned by `tests/test_companion_cleanup_ordering.sh`.

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

### `@aitask_monitor_kind` — the monitor's own pane marker

A running `ait monitor` / `ait minimonitor` stamps **its own** pane with
`@aitask_monitor_kind`, the counterpart to the shadow's `@aitask_shadow_target`.
Two consumers read it: the single-instance guards
(`aitask_minimonitor.sh` and `agent_launch_utils.maybe_spawn_minimonitor`) and
`aitask_companion_cleanup.sh`'s companion discovery.

It exists because **`#{pane_current_command}` cannot identify a monitor** — a
live minimonitor pane reports `python`, so the guards' old substring match
against `minimonitor` / `monitor_app` could never fire. `#{pane_start_command}`
is not a substitute either: it is only set for panes launched *with* a command,
so a minimonitor typed into an existing shell pane would stay invisible.

- **Format: `<kind>:<pid>`** (`minimonitor:41322` / `monitor:41890`), where the
  pid is the marking process's. Without it a guard cannot tell a live monitor
  from a marker left by a hard-killed one.
- **Only the app writes it, on itself**, at mount, gated on a `mark_pane`
  constructor flag that only `main()` sets (the same test-isolation precaution
  as `MonitorApp`'s `rename_window`, t1240). The **spawner deliberately does
  not** stamp the pane it creates: a minimonitor booting inside a pre-stamped
  pane would find its own marker and refuse to start unless it could identify
  its own pane from ambient state. Not stamping removes that self-deadlock by
  construction, at the cost of a ~1 s boot-window race in which a second
  `maybe_spawn_minimonitor` for the same window sees no marker.
- **Cleared at unmount**; an abnormal exit is covered by the liveness rule.
- **Liveness lives in exactly one place: `lib/monitor_marker.py`.** Python
  imports it; `aitask_minimonitor.sh` execs its CLI (`state <value>`, verdict in
  the exit status). Do not reimplement it in shell — `${marker##*:}` reads
  `garbage:123` as a dead pid, and `kill -0` reports failure for another user's
  live process where `os.kill`'s `PermissionError` means it exists.
- **Unverifiable is not absence.** A non-empty value that does not parse
  (unknown kind, missing/non-numeric pid, extra fields) classifies as *present*
  and is never cleared; only a parseable marker whose pid is provably gone is
  `stale`, and only that licenses a caller to clear it. The CLI's verdict codes
  (`0` present, `10` stale, `11` absent) sit outside the range a failing
  interpreter produces, and every other status must be treated as *present* —
  mapping one to `stale` would make a crash clear a live marker.

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

**"There is no room in the footer" is no longer a reason to hide a binding.**
Stock Textual's `Footer` is one row high and pushes the overflow into a
horizontal *mouse-wheel* scroll region, so a hidden-by-necessity key is
invisible to a keyboard user. `.aitask-scripts/lib/multirow_footer.py` provides
`MultiRowFooter`, a drop-in `Footer` subclass that reflows the same `FooterKey`
widgets onto as many rows as the width needs — so `check_action` gating,
click-to-fire and the `bindings_updated` recompose all keep working. Use it when
a screen declares more keys than one row holds:

```python
yield MultiRowFooter(hint_action="open_shortcuts_editor")
```

- Row count is emergent: content that fits stays on one row, so a wide terminal
  looks exactly as it does today and the footer only grows when it must.
- The row cap is the global `footer_max_rows` userconfig key (default 3; `1`
  restores single-row behavior). Past the cap the footer drops the tail and
  renders a `+N more (<key>)` affordance — it never hides keys silently.
- `hint_action` takes an **action**, not a key: the affordance's key display is
  resolved from the composed binding, so it follows a user remap. Do not resolve
  it through `resolve_key(<app scope>, …)` for actions registered under the
  `shared` scope (e.g. `open_shortcuts_editor`) — `register_app_bindings`
  deliberately does not shadow those into the app scope, so the lookup returns
  `None` and any literal fallback goes stale for exactly the users who rebound it.
- Adopted on the board (t1418). The other TUIs still mount the stock `Footer`;
  `agentcrew_dashboard`, `codebrowser`, `monitor`, `stats` and
  `codebrowser/history_screen` all overflow a 120-column terminal today.

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

**Import semantics of the sweep — do not "optimize" either half.** Each sweep
*re-executes* the manifest module's body, and does so under a **private probe
name** (`_shortcut_scopes_probe_<module_name>`) rather than the module's
canonical name. Both properties are load-bearing:

- *Re-exec rather than reuse an already-imported module.* Module-level and
  class-body registrations (`shared.tui_switcher`, `brainstorm.dag`) only fire
  during an import, and `keybinding_registry` can be reset between sweeps — a
  reuse implementation silently loses those scopes.
- *Probe name rather than the canonical one.* Executing under the canonical name
  would rebind `sys.modules[<name>]` to a fresh module object, giving its classes
  a **second identity**, so anything still holding the pre-sweep class (a mounted
  TUI screen, a test module's top-level import) fails `isinstance` against the
  post-sweep one. The `?` editor sweeps inside running TUIs, so this bites live
  processes, not just tests.

`ModuleIdentityTests` in `tests/test_shortcut_scopes.py` pins the canonical-entry
invariant (including across repeated sweeps, with a negative control proving the
check is falsifiable); the drift guard above pins the re-exec half.

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
- Most tmux tests only need `require_isolated_tmux` (isolate, never refuse). A
  test that runs framework code reaching tmux **outside** the gateway — the
  shadow cleanup hook is the case in point, since
  `aitask_companion_cleanup.sh` is raw-`tmux`-by-design — should additionally
  call `require_clean_ait_server`, which turns this preflight into an exit-2
  refusal instead of a human checklist item. Both live in
  `tests/lib/tmux_isolation.sh`; the refusal guard must be called **first**,
  because `require_isolated_tmux` unsets `$TMUX` and repoints `$TMUX_TMPDIR`.
  `tests/test_monitor_shadow_spawn_live.sh` is the reference caller.
