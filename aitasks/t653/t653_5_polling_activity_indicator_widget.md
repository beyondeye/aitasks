---
priority: medium
effort: medium
depends: [t653_1]
issue_type: feature
status: Ready
labels: [agentcrew, ait_brainstorm]
created_at: 2026-04-26 16:40
updated_at: 2026-04-26 16:40
---

## Context

Sibling of t653_1 (brainstorm TUI self-heal). t653_1 introduces a 30-second slow watcher (`set_interval(30, _poll_initializer)`) for the post-Error initializer recovery path. There is no visual indication that this watcher is alive — the user sees a banner with an error and no sign that the TUI is still working in the background. Same gap exists for any other `set_interval` / `set_timer` in the brainstorm TUI: timers fire silently and the user has no way to tell whether polling is active.

This task adds a reusable `PollingIndicator` widget and wires it up next to **every** polling site in the brainstorm TUI. The widget is mounted **contextually** — adjacent to the operation/widget the polling refers to — not in a single global location. Per user direction (2026-04-26 conversation): "the idea is to have it contextual to the operation that it refers too" and "All polling sites in brainstorm TUI".

## Visual specification

The widget is a single-character indicator (a circle: `●` recommended; alternatives `◉`, `⬤`, `○`, `◎` to consider during implementation) with three states:

- **Off** (no active polling): hidden, or rendered as dim/blank space — does not consume layout when off.
- **Active dim-cycle** (polling is installed but no tick recently): cycles continuously through three dim brightness levels at a slow rate (~0.6–1.0 s per step). Cycling makes it clear the watcher is alive.
- **Flash** (a poll just fired): briefly switches to a bright color (~150–250 ms), then returns to the dim-cycle state.

The "flash on poll-fire" is the key signal — it tells the user "yes, the timer just ticked, we are checking right now". The dim-cycle is reassurance that the watcher is still installed between ticks.

## Key Files to Modify

- `.aitask-scripts/brainstorm/brainstorm_app.py` — wire indicator next to each polling site (`_start_initializer_wait`, `_poll_initializer`, and any other `set_interval`/`set_timer` site discovered during a grep audit).
- New file: `.aitask-scripts/brainstorm/polling_indicator.py` — the reusable widget. Or, if `brainstorm_app.py` is the only consumer for now, consider colocating as a class inside `brainstorm_app.py` and extracting later if other TUIs adopt it.

## Reference Files for Patterns

- `.aitask-scripts/brainstorm/brainstorm_app.py` — examine existing animated widgets (search for `set_interval` calls with short intervals; the spinner-like elements for agent-running indicators if any).
- t653_1 plan (`aiplans/p653/p653_1_brainstorm_tui_self_heal_apply.md`) — the slow-watcher poll site this widget's first consumer; see the S4 step.
- Textual docs: `Static`, `set_interval`, `add_class`/`remove_class` for state transitions; reactive attributes for state-driven re-render.

## Implementation Plan

1. **Create the widget class** `PollingIndicator(Static)`:
   - Reactive state attribute: `state: Literal["off", "dim", "flash"] = "off"`.
   - Private dim-cycle interval handle and a flash-timeout handle.
   - Methods:
     - `start()` → set `state = "dim"`, start the cycle interval.
     - `stop()` → cancel both intervals; set `state = "off"`.
     - `flash()` → set `state = "flash"`; cancel any in-flight flash-timeout; install a one-shot `set_timer(0.2, self._end_flash)`.
   - `watch_state(state)` → update `Static`'s text + class to render the right brightness.
   - CSS classes: `.polling-off`, `.polling-dim-1`, `.polling-dim-2`, `.polling-dim-3`, `.polling-flash` — colors via Textual color theme tokens (e.g., `$accent-darken-3` / `$accent-darken-2` / `$accent-darken-1` / `$accent`).

2. **Audit polling sites in `brainstorm_app.py`:**
   ```bash
   grep -n "set_interval\|set_timer" .aitask-scripts/brainstorm/brainstorm_app.py
   ```
   For each site, identify the operation it refers to (initializer poll, heartbeat refresh, agent-state poll, etc.).

3. **Mount one indicator per operation, next to its associated widget.** Examples:
   - For the initializer poll: mount alongside the initializer banner introduced by t653_1 (right edge of the same row).
   - For node/agent state polls: mount next to the agent-state label / DAG node widget the timer refreshes.
   - Mounting strategy: prefer adding to the `compose()` for that operation's containing widget; if no obvious container exists, add a horizontal sub-row.

4. **Wire each polling site:**
   - On `set_interval(...)` install: call `indicator.start()`.
   - At the top of each poll callback (e.g., `_poll_initializer`): call `indicator.flash()`.
   - On timer cancellation / poll completion: call `indicator.stop()`.

5. **Theme integration.** Use Textual color tokens that adapt to dark/light themes. Avoid hard-coded RGB.

## Verification Steps

1. **Unit-ish:** Open any session with the initializer in error state (use t653_1's synthetic test fixture). Observe a dim-cycling indicator next to the initializer banner. Wait 30 s and observe a brief bright flash, then return to dim cycle.

2. **Audit grep:** After wiring, every `set_interval` / `set_timer` site in `brainstorm_app.py` should have an associated `.flash()` and matching `.start()` / `.stop()` calls. No silent timers.

3. **Theme:** Switch Textual theme (dark/light). Indicator brightness levels remain readable in both.

4. **No-regression:** Normal happy-path session with no polling active — no indicators visible anywhere in the dashboard.

## Out of scope

- Wiring polling indicators in OTHER ait TUIs (board, monitor, codebrowser, etc.). This task is brainstorm-only. If the widget proves useful, a follow-up task can lift it to a shared location and wire those TUIs.
- Heartbeat fixes (Layer A — owned by parent t650).
- Tolerant initializer apply (Layer C — owned by t653_2).
- Agent-crew status changes (Layer D — owned by t653_3).

## Notes

- Depends on t653_1 landing first (the slow 30 s watcher is the headline consumer). Implementable in parallel — wiring becomes a no-op until t653_1's timer is installed.
- t653_4 (manual verification aggregate) can be optionally extended to verify the new visual behavior, but doing so is not blocking for this task.
