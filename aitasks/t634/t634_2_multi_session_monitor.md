---
priority: medium
effort: high
depends: [t634_1]
issue_type: feature
status: Ready
labels: [tmux, aitask_monitor, aitask_monitormini]
created_at: 2026-04-23 20:20
updated_at: 2026-04-23 20:20
---

## Context

Child of t634. Extend `ait monitor` so that a single monitor instance can optionally observe code agents running across **all aitasks sessions** on the current tmux server, not just the session the monitor happens to live in. Depends on t634_1 for `discover_aitasks_sessions()` and `switch_to_pane_anywhere()`.

Primary use case: a user running 3 aitasks projects in parallel opens ONE `ait monitor` (from whichever project they're currently attached to) and sees every active code agent, tagged by project. Clicking a pane from another project teleports the client there.

## Key Files to Modify

- `.aitask-scripts/monitor/tmux_monitor.py` — `TmuxMonitor` grows a `multi_session: bool` constructor arg and, when true, aggregates panes across all discovered aitasks sessions.
- `.aitask-scripts/monitor/monitor_app.py` — read the mode from config, render a session tag column, wire cross-session focus through `switch_to_pane_anywhere`, relax the session-rename prompt for multi-session mode, update the title bar.
- `.aitask-scripts/monitor/monitor_shared.py` — display helpers may need a small formatter for the session tag.
- `aitasks/metadata/project_config.yaml` (runtime) + `seed/project_config.yaml` — document the new config key.
- `website/content/docs/...` — user-facing doc for the feature (current-state only per CLAUDE.md docs rule).
- `tests/test_multi_session_monitor.py` or `.sh` — coverage for the new code paths.

## Reference Files for Patterns

- `.aitask-scripts/monitor/tmux_monitor.py:discover_panes` and `discover_panes_async` — current single-session enumeration. Multi-session version iterates `discover_aitasks_sessions()` and merges results, tagging each pane with its session.
- `.aitask-scripts/monitor/monitor_app.py:_expected_session` / `_rename_session` dialog — the current "wrong session" guardrail. In multi-session mode it should accept any aitasks session (or be skipped entirely).
- `.aitask-scripts/monitor/minimonitor_app.py:action_focus_monitor` — the current env-var focus handoff. **Do NOT extend** that dance cross-session; cross-session focus uses `switch_to_pane_anywhere(pane_id)` directly.

## Implementation Plan

### Step 1 — TmuxMonitor multi-session mode

Add `multi_session: bool = False` to `TmuxMonitor.__init__`. When true:

- `discover_panes` / `discover_panes_async` iterate `discover_aitasks_sessions()` and call the single-session `list-panes -s -t =<sess>` per session, merging results. Each returned `TmuxPaneInfo` gains an optional `session_name` (already on the dataclass today? if not, add it).
- `_pane_cache` key remains `pane_id` (still globally unique).
- `capture_pane`, `kill_pane`, `kill_window`, `send_keys`, `switch_to_pane` all work by pane id — unchanged.
- `switch_to_pane(pane_id, prefer_companion=True)` in multi mode uses `switch_to_pane_anywhere(pane_id)` from t634_1 instead of the current "session-local select-window + select-pane" so cross-session focus teleports correctly.

### Step 2 — Config

Add `tmux.monitor.multi_session: bool` (default false) to `project_config.yaml` schema and `load_monitor_config` parser.

Also consider a companion `tmux.monitor.multi_session_sessions: list[str] | null`:
- `null` (default) → include all discovered aitasks sessions.
- list → restrict to these session names.

Useful if the user runs 5 projects but only wants monitor views of 2.

### Step 3 — monitor_app.py UI changes

- Title bar: `f"tmux Monitor — {N} sessions · {M} panes · multi"` when multi-mode active; unchanged single-session text otherwise.
- Pane list rows: prepend a short session tag (e.g. `[mob]` for `aitasks_mob` — configurable, default `basename(project_root)`) when `multi_session` is true. Single-session view is unchanged.
- Session-rename dialog (`SessionRenameDialog`): skip entirely in multi-session mode.
- Footer: add a `M` binding that toggles multi-session at runtime for quick experimentation; toggle writes only to the in-memory state of the running instance, not to config (matching the TUI auto-commit/push restriction from CLAUDE.md).

### Step 4 — Cross-session focus

Replace current in-session focus with `switch_to_pane_anywhere(pane.pane_id)` in multi mode. When the user hits Enter on a pane from another session:

1. `switch-client -t =<sess>` teleports the attached client.
2. `select-window -t =<sess>:<idx>` focuses the correct window.
3. `select-pane -t <pane_id>` focuses within it.

After the client teleports, the monitor (which lived in the *previous* session) continues running — it remains attached to pane's "home" session's env. That's fine; the next refresh still captures from all sessions by pane id.

### Step 5 — Title-bar session change events

Textual's reactive vars can watch for attached-session changes. On teleport, the monitor's title bar should update to reflect the new attached session. Use `tmux display-message -p '#S'` on each refresh tick; cheap.

## Verification

Automated:

- Unit: `TmuxMonitor(multi_session=True)` with a mocked `discover_aitasks_sessions` returning 2 fake sessions + mocked `subprocess.run` for `list-panes -s` returns a merged pane list with correct session tags.
- Integration (gated on tmux + `TMUX_TMPDIR`): start 2 fake aitasks sessions with dummy panes, construct a real `TmuxMonitor(multi_session=True)`, assert `discover_panes()` returns panes from both.
- Regression: `TmuxMonitor(multi_session=False)` behaves exactly as today — no new code paths triggered.

Manual (aggregate sibling of t634):

- Two projects side-by-side. Enable `multi_session: true` in one. Launch a code agent in each. Monitor shows both with session tags. Enter on the other project's pane teleports client and focuses pane. Monitor refresh after teleport still shows both panes.
- Verify single-session mode (flag off) is bit-identical to today.
- Verify `SessionRenameDialog` does NOT fire when multi_session is on, even if the attached session name doesn't match `default_session`.

## Gotchas to address during implementation

- `display-message -p '#S'` returns the attached client's session, not the monitor process's "home" session. In multi-session mode this is exactly what we want for the title bar. Single-session mode still uses `self._session` (immutable per monitor instance).
- If the user kills the *attached* session from inside the monitor (e.g. via `kill-window` on the only window of that session), the client detaches. Handle the detach event — don't crash. Textual should survive a detach; verify.
- Pane ID stability: a pane id (`%42`) is stable until the pane dies; cross-session teleports don't invalidate it. The existing `_pane_cache` keyed on pane id remains correct.
- Order-dependence of monitor enumeration: in multi-session mode, sort sessions (e.g. by name) so the display is stable across refreshes. Otherwise `list-sessions` order is server-internal and can jitter.
- Don't forget `minimonitor_app.py` companion panes — they're per-session and should NOT appear in the multi-session monitor's pane list (companion filter already exists; keep it active in both modes).
