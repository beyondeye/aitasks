---
priority: high
effort: medium
depends: []
issue_type: documentation
status: Ready
labels: [ait_bridge]
created_at: 2026-05-24 09:32
updated_at: 2026-05-24 09:32
---

Design doc only: spec how the existing `ait monitor` TUI will be ported to drive a mobile client over the `applink` protocol. Identifies the headless-core extraction seam, maps every existing command verb to a protocol message + permission profile, defines the snapshot data model and refresh cadence, and enumerates the modal-dialog handshakes. Produces no code changes under `.aitask-scripts/monitor/`.

## Context

Parent task **t822** introduces `ait applink`. Once t822_1 has locked the protocol and t822_2 has shipped the bare TUI skeleton, this design doc unblocks the next wave of follow-up tasks (extract `monitor_core.py`, wire it through applink, etc.) that the user will create after this PR lands.

The Explore pass for t822 already mapped the architecture seam: `tmux_monitor.py` and `tmux_control.py` are pure-data/control modules; `monitor_app.py` is the Textual-bound layer. Natural wire boundary is between `TmuxMonitor.capture_all()` output (dict of `PaneSnapshot`) and the Textual render loop.

This task explicitly does NOT modify any code under `.aitask-scripts/monitor/`.

## Depends on

- t822_1 only (uses the JSON envelope from `aidocs/applink/protocol.md` and the permission profile list from `aidocs/applink/permissions.md`)
- NOT t822_2 (this is parallelizable with the TUI skeleton — `--no-sibling-dep` set at creation)

## Key Files to Create

- `aidocs/applink/monitor_port_design.md` — covers:
  1. **Headless-core extraction.** Public API surface of a future `.aitask-scripts/monitor/monitor_core.py`:
     - `TmuxMonitor.discover_panes()` / `capture_all()` / `capture_all_async()` (`tmux_monitor.py:390-584`)
     - `TmuxMonitor.send_keys()`, `send_enter()`, `kill_pane()`, `switch_to_pane()` (`tmux_monitor.py:585-675`)
     - `TmuxControlBackend` / `TmuxControlClient` (`tmux_control.py:69-548`)
     - `TaskInfoCache._resolve()` (`monitor_shared.py:217-321`)
     - `PaneSnapshot` / `TmuxPaneInfo` dataclasses (`tmux_monitor.py:150-171`)
  2. **What stays in `monitor_app.py`:** Textual widgets (`PaneCard`, `MiniPaneCard`, `PreviewPanel`), modal screens (`TaskDetailDialog`, `KillConfirmDialog`, `SessionRenameDialog`), refresh timer loop, key forwarding logic, scroll-position memory (`monitor_app.py:494-504`).
  3. **Command verb → applink protocol mapping table.** For each of the 7 verbs (`send_enter`, `forward_key`, `switch_to_pane`, `kill_pane`, `kill_window`, `spawn_tui`, `cycle_compare_mode`), document:
     - Existing `tmux_monitor.py:585-675` function signature
     - Proposed `applink` request frame (verb name, payload schema)
     - Permission profile that gates it (matches t822_1's `permissions.md`)
     - Whether a confirmation modal is required
  4. **Snapshot data model on the wire.** JSON shape for `PaneSnapshot`:
     - Field-by-field mapping from the dataclass
     - Scroll-anchor strategy (substring-anchor, NOT pixel offset — see `monitor_app.py:494-504` for rationale)
     - Two-tier refresh cadence (3s default, 0.3s when focused — `monitor_app.py:1268-1274`); how the mobile client signals "focused" state
     - Delta vs. full-frame strategy (recommend full snapshots for v1; defer deltas)
  5. **Modal-dialog handshakes.** RPC request/response design for `KillConfirmDialog`, `SessionRenameDialog`, `TaskDetailDialog`.
  6. **Task-detail RPC.** How `TaskInfoCache` (`monitor_shared.py:217-321`) is served to the mobile client (which has no filesystem access) — either as a side RPC or embedded in the snapshot.
  7. **Out of scope / deferred follow-up tasks.** Bullet list of clearly-scoped successor tasks:
     - Extract `monitor_core.py` (refactor)
     - Wire `applink` WebSocket listener using `monitor_core.py`
     - Add an `applink`-mode flag to `aitask_monitor.sh`
     - Each bullet phrased to be lifted into a future `ait task create` call.

## Key Files to Reference (read-only)

- `aidocs/applink/protocol.md` (from t822_1) — JSON envelope to use
- `aidocs/applink/permissions.md` (from t822_1) — permission profile names
- `.aitask-scripts/monitor/monitor_app.py` — full code (1870 lines; consult specific line refs above)
- `.aitask-scripts/monitor/tmux_monitor.py` (774 lines)
- `.aitask-scripts/monitor/tmux_control.py` (547 lines)
- `.aitask-scripts/monitor/monitor_shared.py` (478 lines)
- `.aitask-scripts/monitor/minimonitor_app.py` — sister TUI, useful to confirm the headless seam works for both
- `aidocs/gitremoteproviderintegration.md` — style template (architecture overview + extension checklist + tables)

## Implementation Plan

1. Read `aidocs/applink/protocol.md` and `aidocs/applink/permissions.md` (produced by t822_1).
2. Re-read the load-bearing file:line refs listed above and verify line numbers haven't shifted (use the line numbers from the parent plan as a starting hint).
3. Write `aidocs/applink/monitor_port_design.md` following the 7-section outline above.
4. Build the verb table by inspecting `tmux_monitor.py:585-675` and `monitor_app.py:1262-1799` for any verbs missed in the parent's Explore pass.
5. Build the snapshot field-mapping table by inspecting `PaneSnapshot` / `TmuxPaneInfo` (`tmux_monitor.py:150-171`).
6. Style match: ## section headers, embed tables, code blocks under 20 lines, no ToC.

## Verification Steps

- `aidocs/applink/monitor_port_design.md` exists and renders cleanly
- Every verb in `tmux_monitor.py:585-675` appears in the verb-mapping table (cross-check with `grep -nE 'def (send|kill|switch|spawn|cycle)' .aitask-scripts/monitor/tmux_monitor.py`)
- Every permission profile named in t822_1's `permissions.md` is used at least once in the verb gating table
- All file:line references resolve to existing lines (manual spot-check on 5 of them)
- The "deferred follow-up tasks" section contains at least 3 clearly-scoped bullets that could each become a standalone `ait task create` call

No runtime tests (doc-only task).

## Out of Scope

- ANY code change under `.aitask-scripts/monitor/` (this is design only)
- The actual `applink` WebSocket listener (deferred to a follow-up task this doc enumerates)
- Mobile-side rendering / scroll-anchor implementation (lives in `../aitasks_mobile`)
