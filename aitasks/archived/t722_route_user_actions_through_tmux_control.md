---
priority: medium
effort: medium
depends: [t719_2]
issue_type: refactor
status: Done
labels: [performance, monitor, tui, refactor]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-04-30 10:48
updated_at: 2026-05-03 12:07
completed_at: 2026-05-03 12:07
boardcol: now
boardidx: 10
---

## Context

Follow-up to **t719** (`tmux -C` control-mode refactor for monitor/minimonitor).

t719's Phase 1 (`t719_1` + `t719_2`) routes only the *async hot-path* tmux invocations (`list-panes`, `capture-pane`) through the persistent `tmux -C` control client. **User-action subprocess calls remain on plain `subprocess.run`** — the rationale being that fork+exec overhead is invisible at user reaction times. That rationale was good enough for the performance goal, but it leaves the monitor's tmux interaction split across two surfaces.

**Why this becomes load-bearing:** the user is planning to add support for connecting to the monitor from a mobile device. A single contact surface for all tmux operations is desirable for that future feature — the mobile bridge can speak the control-client protocol once, instead of having to translate two different code paths (control client + ad-hoc subprocess). Consolidating now (after t719's perf work has settled) avoids retrofitting under deadline pressure.

## Scope — calls to migrate

Source: `grep -n 'subprocess\.\(run\|Popen\)' .aitask-scripts/monitor/*.py` after `t719_2` lands. Per the t719 parent plan's "Out of scope" section, these are the user-action call sites:

### `tmux_monitor.py` (sync paths)

- `discover_panes` (single-session sync) — `list-panes` (line ~302)
- `capture_pane` (sync) — `capture-pane` (line ~455)
- `discover_window_panes` — `list-panes` for a specific window (line ~337)
- `send_enter` — `send-keys Enter` (line ~512)
- `send_keys` — `send-keys` arbitrary (line ~531)
- `switch_to_pane` — `select-window` + `select-pane` (line ~552, ~564)
- `find_companion_pane_id` — `list-panes` (line ~579)
- `kill_pane` — `kill-pane` (line ~604)
- `kill_window` — `kill-window` (line ~620)
- `kill_agent_pane_smart` — `list-panes` (line ~652)
- `spawn_tui` — `new-window` (line ~681)

### `monitor_app.py`

- `rename-window` (line ~530)
- `has-session` (line ~547)
- `show-environment` (line ~767)
- `set-environment` unset (line ~788)
- `display-message #S` (line ~887)

### `minimonitor_app.py`

- `display-message` own pane info (line ~168, ~256)
- `list-panes` (line ~459)
- `select-pane` (line ~485)
- `set-environment` (line ~616)
- `list-windows` (line ~632)
- `select-window` (line ~647)
- `new-window` (line ~656)

## Approach

1. **Add sync convenience wrapper** to `TmuxControlClient` (e.g., `request_sync(args, timeout)`) that runs the async `request()` on the existing event loop via `loop.create_task` + a brief `loop.run_until_complete` — or, more cleanly, expose the bridge through `TmuxMonitor.tmux_run(args)` that picks the right path depending on whether an event loop is already running. The exact mechanism depends on whether the calling site is sync (most user-actions) or async (rare).
2. **Audit every site listed above** — for each, replace the inline `subprocess.run(["tmux", ...], ...)` with `self._monitor.tmux_run([...])` (or equivalent). Preserve return semantics: `subprocess.CompletedProcess` callers want `returncode + stdout + stderr`; the control-client wrapper returns `(rc, str)`. Where `stderr` was being inspected (none of the user-action paths actually inspect stderr per the t719_1 audit), confirm and adjust.
3. **Subprocess fallback unchanged.** When the control client is not started or has died, the wrapper falls back to subprocess just like the async hot-path does. This keeps the apps usable in degraded mode.
4. **Tests:**
   - Extend `tests/test_tmux_control.sh` with a sync-wrapper case (issue a kill-pane via the control client, verify the pane is gone).
   - Add a regression test that exercises `kill_agent_pane_smart` end-to-end against a fixture session, ensuring control-client and subprocess paths produce identical state changes (pane gone, companion preserved).
5. **Manual verification:** all the user-action UI flows (kill, switch, send-keys, multi-session toggle) still work identically. Add a paragraph to the eventual mobile-bridge design doc that points here.

## Verification

- `bash tests/test_tmux_control.sh` — passes (with new sync-wrapper case).
- `grep -n 'subprocess\.\(run\|Popen\).*tmux' .aitask-scripts/monitor/*.py` — returns **only** the fallback path inside the wrapper. All other tmux invocations route through the control client.
- Manual smoke: launch `ait monitor` and `ait minimonitor`; exercise kill-pane (`x`), switch-to-pane (`s`), send-Enter (`enter`), multi-session toggle (`M`); confirm behavior unchanged.
- `tmux list-clients` does not show extra control clients (confirm the same single client is reused for sync calls).

## Out of bounds

- The mobile-device bridge itself — that's a separate, larger task that depends on this consolidation landing first.
- Touching tmux invocations *outside* `.aitask-scripts/monitor/` (e.g., in agent_launch_utils, terminal_compat, or any of the bash helpers). Those are not part of the monitor's contact surface.

## Dependencies

Depends on **t719_2** (hot-path integration) — needs `TmuxControlClient` lifecycle to be wired into both apps before this consolidation makes sense.
