---
Task: t822_3_monitor_port_design.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_1_applink_protocol_design.md, aitasks/t822/t822_2_applink_tui_qr.md
Archived Sibling Plans: aiplans/archived/p822/p822_*_*.md
Worktree: (current branch — profile fast)
Branch: (current branch — profile fast)
Base branch: main
---

# Plan: t822_3 — `ait monitor` → `applink` port design (aidocs only)

## Context

Third child of parent t822. Doc-only. Depends on t822_1 (uses the JSON envelope from `aidocs/applink/protocol.md` and the permission profile names from `aidocs/applink/permissions.md`). **Parallelizable with t822_2** — does not depend on the TUI skeleton existing; the parent uses `--no-sibling-dep` for this child.

This task explicitly does NOT modify any code under `.aitask-scripts/monitor/`. The actual refactor is a deferred follow-up task this doc enumerates at the end.

## Pre-flight check

1. Confirm `aidocs/applink/protocol.md` and `aidocs/applink/permissions.md` exist (from t822_1). If not, BLOCK and pick t822_1 first.
2. Re-read the load-bearing line:line refs below and verify the lines haven't shifted since the parent's Explore pass. (If they have, update this plan in place before writing the doc.)

## File to create

**`aidocs/applink/monitor_port_design.md`** — sections:

### 1. Overview
- What this doc is, link to parent t822, link to `protocol.md` and `permissions.md`.

### 2. Headless-core extraction
- Table: "Functions moving to `.aitask-scripts/monitor/monitor_core.py` (future)":
  | Symbol | Source | Role |
  | `TmuxMonitor.discover_panes` | `tmux_monitor.py:390-411` | pane discovery |
  | `TmuxMonitor.capture_all` / `capture_all_async` | `tmux_monitor.py:495-584` | snapshot capture |
  | `TmuxMonitor.send_keys` / `send_enter` | `tmux_monitor.py:585-601` | input dispatch |
  | `TmuxMonitor.switch_to_pane` | `tmux_monitor.py:602-629` | focus change |
  | `TmuxMonitor.kill_pane` / `kill_window` | `tmux_monitor.py:656-674` | termination |
  | `TmuxMonitor.spawn_tui` | `tmux_monitor.py:718-723` | new-window spawn |
  | `TmuxControlBackend` / `TmuxControlClient` | `tmux_control.py:69-548` | persistent tmux client |
  | `TaskInfoCache._resolve` | `monitor_shared.py:217-321` | task metadata cache |
  | `PaneSnapshot` / `TmuxPaneInfo` | `tmux_monitor.py:150-171` | wire-shape source |
- Table: "What stays in `monitor_app.py` (UI-bound)":
  Textual widgets, modal screens, refresh timer, key forwarding, scroll-position memory (`monitor_app.py:494-504`).

### 3. Command verb → applink protocol mapping
Rows = verbs (one per `tmux_monitor.py:585-675` function); columns = applink request frame `verb` + payload schema + permission profile (from `permissions.md`) + confirmation-modal-required-Y/N.

Seed table:
| Verb | applink frame | Payload | Profile gate | Modal? |
|------|--------------|---------|--------------|-------|
| `send_keys` | `req {"verb":"send_keys"}` | `{pane_id, keys:[..], literal:bool}` | monitor_control | N |
| `send_enter` | `req {"verb":"send_enter"}` | `{pane_id}` | monitor_control | N |
| `switch_to_pane` | `req {"verb":"focus"}` | `{pane_id}` | monitor_control | N |
| `kill_pane` | `req {"verb":"kill_pane"}` | `{pane_id, confirmed:bool}` | full | Y |
| `kill_window` | `req {"verb":"kill_window"}` | `{window_id, confirmed:bool}` | full | Y |
| `spawn_tui` | `req {"verb":"spawn_tui"}` | `{session_id, tui_name}` | full | N |
| `cycle_compare_mode` | `req {"verb":"cycle_compare"}` | `{}` | monitor_control | N |

(Validate at write time by `grep -nE 'def (send|kill|switch|spawn|cycle)' .aitask-scripts/monitor/tmux_monitor.py` and ensuring every match has a row.)

### 4. Snapshot data model on the wire
- Field-by-field mapping of `PaneSnapshot` / `TmuxPaneInfo` (`tmux_monitor.py:150-171`) to JSON keys.
- Scroll-anchor strategy: substring-anchor (NOT pixel offset). Rationale: snapshot lines reflow on mobile; pixel offsets break across rerenders. Mobile sends `{"focus_anchor":"<last-visible-line-substring>"}` and PC sends back the next snapshot with that anchor marked.
- Two-tier refresh cadence: 3s default, 0.3s when mobile reports `"focused":true` (matches `monitor_app.py:1268-1274`). Mobile sends focused-state changes as push frames.
- Delta vs. full-frame: full snapshots in v1 (simpler), delta as v2 (deferred; note in §8).

### 5. Modal-dialog handshakes
RPC sequences for each modal that today calls `App.push_screen` (`monitor_app.py:1565-1598` etc.):
- `KillConfirmDialog`: PC pushes `{"verb":"confirm","payload":{"action":"kill_pane","target":"<pane_id>"}}` push frame; mobile replies with `{"verb":"confirm_response","payload":{"confirmed":bool}}`. If `false`, PC aborts the kill. Same for `kill_window`.
- `SessionRenameDialog`: PC pushes `{"verb":"prompt","payload":{"field":"session_name","current":"<old>"}}`; mobile replies with `{"verb":"prompt_response","payload":{"value":"<new>"}}`.
- `TaskDetailDialog`: see §6.

### 6. Task-detail RPC
Mobile has no filesystem. Options:
- (A) Server-side: mobile sends `{"verb":"task_detail","payload":{"task_id":"<id>"}}`; PC reads task file via `TaskInfoCache._resolve` and returns the rendered detail.
- (B) Embed in snapshot: every `PaneSnapshot` includes `task_summary` (cached). Cheaper RPC, larger snapshots.
- **Recommend (A) on-demand RPC** for v1 — keeps snapshots small.

### 7. Permission profile cross-check
Confirm every verb in §3 is covered by exactly one profile band in `aidocs/applink/permissions.md`. If `permissions.md` is missing a verb, file it as a discrepancy at the bottom of this doc (don't silently fix — leaves a paper trail).

### 8. Deferred follow-up tasks
Each bullet is phrased to be liftable into an `ait task create` invocation:
- **Refactor: extract `monitor_core.py`** — move the §2 functions into a new module, leaving thin shims in `tmux_monitor.py` / `tmux_control.py` / `monitor_shared.py` for backwards compatibility. Verify `ait monitor` still launches.
- **applink: WebSocket listener** — wire `applink.applink_app` to start a TLS WS server on launch, accept the `pair` verb, and route subsequent frames per the verb table in §3. Integrates with `monitor_core` for snapshot generation.
- **applink: snapshot push loop** — implement the 3s/0.3s cadence and substring-anchor logic from §4. Wire focus-state push frames from the mobile.
- **applink: modal handshake plumbing** — implement §5 request/response correlation by `id` field.
- **applink-mode flag for `aitask_monitor.sh`** — `--headless-for-applink` flag that skips Textual startup and exposes the core only via the applink listener.
- **applink: delta snapshots (v2)** — only after v1 ships, profile snapshot size and decide if deltas are worth the complexity.

## Reference files (read-only)

- `aidocs/applink/protocol.md` (from t822_1) — JSON envelope, pairing flow
- `aidocs/applink/permissions.md` (from t822_1) — profile names + verb gating
- `.aitask-scripts/monitor/monitor_app.py` (1870 lines)
- `.aitask-scripts/monitor/tmux_monitor.py` (774 lines)
- `.aitask-scripts/monitor/tmux_control.py` (547 lines)
- `.aitask-scripts/monitor/monitor_shared.py` (478 lines)
- `.aitask-scripts/monitor/minimonitor_app.py` — confirm headless seam works for both
- `aidocs/gitremoteproviderintegration.md` — style template

## Verification

- `test -f aidocs/applink/monitor_port_design.md`
- Every `def (send|kill|switch|spawn|cycle)` symbol from `grep -nE 'def (send|kill|switch|spawn|cycle)' .aitask-scripts/monitor/tmux_monitor.py` is in the §3 verb table
- Every profile from `aidocs/applink/permissions.md` is used at least once in §3
- 5 random file:line refs in the doc resolve to lines that still match the description
- §8 has at least 3 cleanly-scoped follow-up bullets
- `git diff --stat` shows only `aidocs/applink/monitor_port_design.md` (no code changes)

No runtime tests (doc-only).

## Out of scope

- Any code change under `.aitask-scripts/monitor/` (this is design only)
- The actual `applink` WebSocket listener (the first §8 bullet)
- Mobile-side rendering / scroll-anchor implementation (lives in `../aitasks_mobile`)
