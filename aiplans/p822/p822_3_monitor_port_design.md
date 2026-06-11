---
Task: t822_3_monitor_port_design.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_4_manual_verification_new_ait_bridge_tui.md, aitasks/t822/t822_5_applink_qr_add_hostname_field.md
Archived Sibling Plans: aiplans/archived/p822/p822_*_*.md
Worktree: (current branch — profile fast)
Branch: (current branch — profile fast)
Base branch: main
plan_verified:
  - claudecode/fable5 @ 2026-06-11 10:20
---

# Plan: t822_3 — `ait monitor` → `applink` port design (aidocs only)

## Context

Third child of parent t822. Doc-only. Depends on t822_1 (uses the JSON envelope from `aidocs/applink/protocol.md` and the permission profile names from `aidocs/applink/permissions.md`). This task explicitly does NOT modify any code under `.aitask-scripts/monitor/`. The actual refactor is a deferred follow-up task this doc enumerates at the end.

## Verification status

Re-verified 2026-06-11 under profile `fast` (`plan_preference_child: verify`, `DECISION:VERIFY`). Findings:

- **t952_3 landed** (commit 509f395c7): the tmux exec-strategy dispatcher now lives in `lib/tmux_exec.py` (`TmuxClient.run_via_control` / `run_async_via_control`); `tmux_monitor.py` delegates to it (`tmux_monitor.py:34,169,231`); `_run_tmux_subprocess` / `_run_tmux_async` are deleted. The task's "Coordination — tmux gateway (t952_3)" section is now folded into §2 below.
- **All file:line citations refreshed** (see tables below — every number in the original plan had shifted).
- **Dialogs migrated**: `TaskDetailDialog`, `KillConfirmDialog`, `NextSiblingDialog`, `ChooseSiblingModal` now live in `monitor_shared.py` (which grew 478 → 760 lines); `SessionRenameDialog` and the new `RestartConfirmDialog` remain in `monitor_app.py`.
- **Two new verbs missed by the parent's Explore pass**: `action_pick_next_sibling` (`monitor_app.py:1602`) and `action_restart_task` (`monitor_app.py:1728`). Both added to the §3 verb table. `switch_to_pane` gained a `prefer_companion: bool` param (`tmux_monitor.py:569`).
- `cycle_compare_mode` is now a `TmuxMonitor` method (`tmux_monitor.py:435`); the `monitor_app.py:1489` action handler remains the UI entry point.

## Pre-flight check

1. Confirm `aidocs/applink/protocol.md`, `permissions.md`, and `content_transport.md` exist (verified 2026-06-11: all present).
2. Line refs in this plan were re-verified 2026-06-11 post-t952_3; spot-check during writing only if further commits touch `.aitask-scripts/monitor/` or `lib/tmux_exec.py`.

## File to create

**`aidocs/applink/monitor_port_design.md`** — sections:

### 1. Overview
- What this doc is, link to parent t822, link to `protocol.md`, `permissions.md`, `content_transport.md`.

### 2. Headless-core extraction

- Table: "Functions moving to `.aitask-scripts/monitor/monitor_core.py` (future)":
  | Symbol | Source | Role |
  | `TmuxMonitor.discover_panes` / `discover_panes_async` | `tmux_monitor.py:345,356` | pane discovery |
  | `TmuxMonitor.cycle_compare_mode` | `tmux_monitor.py:435` | compare-mode state |
  | `TmuxMonitor.capture_all` / `capture_all_async` | `tmux_monitor.py:526,537` | snapshot capture |
  | `TmuxMonitor.send_enter` / `send_keys` | `tmux_monitor.py:552,556` | input dispatch |
  | `TmuxMonitor.switch_to_pane` | `tmux_monitor.py:569` | focus change (note `prefer_companion` param) |
  | `TmuxMonitor.kill_pane` / `kill_window` | `tmux_monitor.py:623,633` | termination |
  | `TmuxMonitor.spawn_tui` | `tmux_monitor.py:685` | new-window spawn |
  | `TmuxControlClient` / `TmuxControlBackend` | `tmux_control.py:76,313` | persistent tmux control-mode client |
  | `TaskInfoCache._resolve` | `monitor_shared.py:311` | task metadata cache |
  | `PaneSnapshot` / `TmuxPaneInfo` | `tmux_monitor.py:119,105` | wire-shape source |
- **tmux gateway delegation (t952_3 — landed).** Document explicitly:
  - `monitor_core` **delegates to** `lib/tmux_exec.py` (`TmuxClient.run_via_control` / `run_async_via_control`) as its tmux-exec substrate — it does **NOT** re-own the control-client-when-alive / subprocess-fallback dispatcher. The delegation seam already exists at `tmux_monitor.py:229-231`.
  - The physical relocation of `TmuxControlClient` / `TmuxControlBackend` out of `monitor/tmux_control.py` was deliberately deferred from t952_3 to ride with the monitor_core extraction — monitor_core is their natural home. The extraction follow-up task (§8) inherits this.
- Table: "What stays in `monitor_app.py` (UI-bound)":
  Textual widgets (`PaneCard`, `MiniPaneCard`, `PreviewPanel`), modal screens (see §5 for current locations), refresh timer (`monitor_app.py:617-619`), key forwarding (`_forward_key_to_tmux`, `monitor_app.py:1342`), scroll-position memory (`monitor_app.py:450-458` + `_locate_anchor` at `monitor_app.py:629-642`).

### 3. Command verb → applink protocol mapping

Rows = verbs from `tmux_monitor.py` methods + `monitor_app.py` action handlers (`monitor_app.py:1262-1823`); columns = applink request frame `verb` + payload schema + permission profile (from `permissions.md`) + confirmation-modal-required-Y/N.

Seed table (canonical inventory — supersedes the seed table in `permissions.md` per t822_1's Final Implementation Notes):

| Verb | applink frame | Payload | Profile gate | Modal? |
|------|--------------|---------|--------------|-------|
| `send_keys` | `req {"verb":"send_keys"}` | `{pane_id, keys:[..], literal:bool}` | monitor_control | N |
| `send_enter` | `req {"verb":"send_enter"}` | `{pane_id}` | monitor_control | N |
| `forward_key` | `req {"verb":"forward_key"}` | `{pane_id, key:"<textual-key-name>"}` | monitor_control | N |
| `switch_to_pane` | `req {"verb":"focus"}` | `{pane_id, prefer_companion:bool}` | monitor_control | N |
| `cycle_compare_mode` | `req {"verb":"cycle_compare"}` | `{pane_id}` | monitor_control | N |
| `kill_pane` | `req {"verb":"kill_pane"}` | `{pane_id, confirmed:bool}` | full | Y |
| `kill_window` | `req {"verb":"kill_window"}` | `{window_id, confirmed:bool}` | full | Y |
| `spawn_tui` | `req {"verb":"spawn_tui"}` | `{session_id, tui_name}` | full | N |
| `pick_next_sibling` | `req {"verb":"pick_next_sibling"}` | `{pane_id, sibling_id?}` | full | Y (sibling chooser) |
| `restart_task` | `req {"verb":"restart_task"}` | `{pane_id, confirmed:bool}` | full | Y |

Notes for the doc:
- `forward_key` folds the `_TEXTUAL_TO_TMUX` map (`monitor_app.py:100`) into a single verb, per t822_1's forward-pointer note in `permissions.md`. Key-name translation happens server-side.
- `pick_next_sibling` / `restart_task` are new since the parent Explore pass (`monitor_app.py:1602,1728`). Both are workflow-level verbs (they drive `ait` task flows, not just tmux); gate at `full` and mark their multi-step handshakes in §5. If their v1 mobile implementation is deferred, the table still lists them with a "deferred to follow-up" flag — the inventory must be complete.
- `cycle_compare_mode` cites `tmux_monitor.py:435` (now a TmuxMonitor method); the `monitor_app.py:1489` handler is the UI entry point being replaced.

(Validate at write time: `grep -nE 'def (send|kill|switch|spawn|cycle)' .aitask-scripts/monitor/tmux_monitor.py` and `grep -n 'def action_' .aitask-scripts/monitor/monitor_app.py` — every tmux-affecting match must have a row or an explicit out-of-scope note for pure-UI actions like `action_cycle_preview_size`, `action_refresh`, `action_toggle_*`, `action_scroll_preview_tail`, `action_switch_zone`, `action_open_log`, `action_show_task_info` → §6.)

### 4. Wiring `PaneSnapshot` to the content-transport spec

The wire format is **fixed** by `aidocs/applink/content_transport.md` (per-line styled spans, 5 frame types `keyframe`/`delta`/`append`/`cursor`/`dim`, MessagePack over WebSocket binary frames). This section maps the existing monitor data model onto that format — it does **not** redefine the wire format.

- **`PaneSnapshot.text` → row encoding.** `tmux_monitor.py:119`'s `PaneSnapshot.text` field carries `tmux capture-pane -e` output. The wiring code (see §8 follow-up "applink: snapshot push loop") parses ANSI/SGR sequences into rows of styled spans per content_transport.md §Row encoding. Decide and document the parser approach (candidates: `pyte`, an ad-hoc SGR parser tuned for `capture-pane -e` output, or `ansicon`-style state machine).
- **Refresh cadence wiring.** Tie `monitor_app.py:617-619`'s timer (`refresh_seconds`, default 3, configurable via `--interval` / tmux_config — `monitor_app.py:1883`) and the 0.3 s fast-preview interval (`monitor_app.py:1271`) into content_transport.md's `subscribe.cadence_idle_ms` / `cadence_focused_ms`. Default mapping: 3 s → `3000`, 0.3 s focused → `300`.
- **Focus-state forwarding.** Map mobile's `focus` control verb onto the monitor's per-pane focused-state flag; no protocol change needed on the wire.
- **Scroll anchor — no wire impact.** With content_transport.md's frame-independent keyframes + `frame_id` chain (§Frame integrity and recovery), the anchor mechanism in `monitor_app.py:450-458` / `_locate_anchor` (`monitor_app.py:629-642`) is **a render-side concern only**; mobile rebuilds scroll position from `frame_id` continuity rather than from substring matching. Document this explicitly to head off duplicate state.
- **Deltification responsibility.** content_transport.md assigns delta computation to the server (row hashing + changed-row collection, Stage 2). Specify where this runs in the monitor pipeline — a `monitor_core` helper invoked by the applink listener, **not** by `monitor_app.py`'s render loop (so the Textual UI and the applink listener can share a single hash cache).
- **Append fast-path detection.** content_transport.md §`append` requires bottom-cursor + no-upper-changes detection. Document where this check lives (next to the deltifier).

### 5. Modal-dialog handshakes

RPC sequences for each modal that today calls `push_screen`. Current locations (post-t952-era refactor — dialogs partially migrated to `monitor_shared.py`):

| Dialog | Location | Handshake |
|--------|----------|-----------|
| `KillConfirmDialog` | `monitor_shared.py:489` | PC pushes `{"verb":"confirm","payload":{"action":"kill_pane","target":"<pane_id>"}}`; mobile replies `{"verb":"confirm_response","payload":{"confirmed":bool}}`. If `false`, abort. Same for `kill_window`. |
| `SessionRenameDialog` | `monitor_app.py:198` | PC pushes `{"verb":"prompt","payload":{"field":"session_name","current":"<old>"}}`; mobile replies `{"verb":"prompt_response","payload":{"value":"<new>"}}`. |
| `RestartConfirmDialog` | `monitor_app.py:265` | Same `confirm`/`confirm_response` shape as kill, `action:"restart_task"`. |
| `NextSiblingDialog` / `ChooseSiblingModal` | `monitor_shared.py:571,695` | Two-step: PC pushes `{"verb":"choose","payload":{"field":"sibling","options":[...]}}`; mobile replies `{"verb":"choose_response","payload":{"selected":"<id>"}}` (or cancel). |
| `TaskDetailDialog` | `monitor_shared.py:418` | Read-only — see §6. |

### 6. Task-detail RPC

Mobile has no filesystem. Options:
- (A) Server-side: mobile sends `{"verb":"task_detail","payload":{"task_id":"<id>"}}`; PC reads task file via `TaskInfoCache._resolve` (`monitor_shared.py:311`) and returns the rendered detail.
- (B) Embed in snapshot: every `PaneSnapshot` includes `task_summary` (cached). Cheaper RPC, larger snapshots.
- **Recommend (A) on-demand RPC** for v1 — keeps snapshots small.

### 7. Permission profile cross-check

Confirm every verb in §3 is covered by exactly one profile band in `aidocs/applink/permissions.md` (`read_only` / `monitor_control` / `full`). The new `forward_key`, `pick_next_sibling`, and `restart_task` verbs are NOT yet in `permissions.md`'s seed table — list them in a "Discrepancies with permissions.md" note at the bottom of the doc (don't silently fix `permissions.md`; t822_1's notes already designate this doc as the canonical inventory, but the `permissions.md` update is a separate follow-up — add it to §8).

### 8. Deferred follow-up tasks

Each bullet is phrased to be liftable into an `ait task create` invocation:
- **Refactor: extract `monitor_core.py`** — move the §2 functions into a new module, leaving thin shims in `tmux_monitor.py` / `tmux_control.py` / `monitor_shared.py` for backwards compatibility. Includes the deferred physical relocation of `TmuxControlClient` / `TmuxControlBackend` out of `monitor/tmux_control.py` (deferred from t952_3 — monitor_core is their natural home). monitor_core **delegates** tmux exec to `lib/tmux_exec.py` (`TmuxClient.run_via_control`); it does not re-own the dispatcher. Verify `ait monitor` and `ait minimonitor` still launch.
- **applink: WebSocket listener** — wire `applink.applink_app` to start a TLS WS server on launch, accept the `pair` verb, and route subsequent frames per the verb table in §3. Integrates with `monitor_core` for snapshot generation.
- **applink: snapshot push loop (Stage 1 of content_transport.md)** — implement the 3 s / 0.3 s cadence, parse `tmux capture-pane -e` into the row/span schema, emit `keyframe`, `cursor`, and `dim` frames. Wire `focus` and `subscribe` control verbs.
- **applink: delta engine (Stage 2 of content_transport.md)** — row hashing + changed-row collection on the server; emit `delta` frames against `prev_frame_id`. Add the recovery path (`request_keyframe`).
- **applink: append fast-path (Stage 3 of content_transport.md)** — bottom-cursor detection + `append` frame emission for log-streaming panes.
- **applink: modal handshake plumbing** — implement §5 request/response correlation by `id` field, covering confirm/prompt/choose shapes.
- **applink: update `permissions.md` verb gating table** — sync the canonical §3 inventory (incl. `forward_key`, `pick_next_sibling`, `restart_task`) back into `aidocs/applink/permissions.md`.
- **applink-mode flag for `aitask_monitor.sh`** — `--headless-for-applink` flag that skips Textual startup and exposes the core only via the applink listener.

## Reference files (read-only)

- `aidocs/applink/protocol.md` (from t822_1) — JSON envelope, pairing flow
- `aidocs/applink/permissions.md` (from t822_1) — profile names + seed verb gating
- `aidocs/applink/content_transport.md` (from t822_1 follow-up) — **canonical wire format for pane content (row/span schema, 5 frame types, refresh control). Consume; do not redefine.**
- `.aitask-scripts/monitor/monitor_app.py` (1901 lines)
- `.aitask-scripts/monitor/tmux_monitor.py` (741 lines)
- `.aitask-scripts/monitor/tmux_control.py` (592 lines)
- `.aitask-scripts/monitor/monitor_shared.py` (760 lines)
- `.aitask-scripts/lib/tmux_exec.py` — tmux gateway (t952_3); `TmuxClient.run_via_control` at `tmux_exec.py:211`
- `.aitask-scripts/monitor/minimonitor_app.py` — sister TUI, confirm headless seam works for both
- `aidocs/gitremoteproviderintegration.md` — style template

## Verification

- `test -f aidocs/applink/monitor_port_design.md`
- Every `def (send|kill|switch|spawn|cycle)` match from `grep -nE 'def (send|kill|switch|spawn|cycle)' .aitask-scripts/monitor/tmux_monitor.py` is in the §3 verb table
- Every `def action_` in `monitor_app.py` is either in the §3 verb table or explicitly listed as pure-UI/out-of-scope in the doc
- Every profile from `aidocs/applink/permissions.md` (`read_only`, `monitor_control`, `full`) is used at least once in §3
- 5 random file:line refs in the doc resolve to lines that still match the description
- §8 has at least 3 cleanly-scoped follow-up bullets
- §4 does **not** redefine the wire format — it cites `content_transport.md` for row/span schema and frame types; the doc's contribution is the *wiring* of `PaneSnapshot` and the monitor refresh loop onto that format
- §2 states the tmux_exec delegation rule (monitor_core delegates to `lib/tmux_exec.py`; does not re-own the dispatcher) and the deferred `TmuxControlClient`/`Backend` relocation
- `git diff --stat` shows only `aidocs/applink/monitor_port_design.md` (no code changes)

No runtime tests (doc-only).

## Out of scope

- Any code change under `.aitask-scripts/monitor/` (this is design only)
- The actual `applink` WebSocket listener (a §8 bullet)
- Mobile-side rendering / scroll-anchor implementation (lives in `../aitasks_mobile`)
- Editing `aidocs/applink/permissions.md` (sync is a §8 follow-up bullet)

## Risk

### Code-health risk: low
None identified. (Doc-only change: one new file under `aidocs/applink/`; no code touched; `git diff --stat` gate in Verification enforces it.)

### Goal-achievement risk: low
None identified. (Verb-inventory completeness — the main delivery risk — is enforced by the two grep cross-checks in Verification; line-citation freshness was re-verified post-t952_3 on 2026-06-11; follow-up tasks lifted from §8 re-verify anchors at pick time per standard workflow.)

## Final Implementation Notes

- **Actual work done:** Created `aidocs/applink/monitor_port_design.md` (178 lines) following the planned outline: Overview; Headless-core extraction (symbol table with 11 rows incl. control-client lifecycle + `kill_agent_pane_smart` + `find_companion_pane_id` added beyond the plan's seed table; t952_3 tmux-gateway delegation rules; UI-stays table); canonical 13-verb protocol mapping (the plan's 10 verbs plus `snapshot`, `task_detail`, and `subscribe`/`request_keyframe` data-plane control rows); PaneSnapshot→content_transport wiring (parser decision made: ad-hoc SGR state machine over `pyte`, with rationale — `capture-pane -e` output has no cursor/grid sequences; added a `pane_status` JSON push for non-content snapshot fields); modal-dialog handshakes (pull-model: client re-sends with `confirmed:true` instead of server-pushed confirm — chosen so the server never blocks on a dialog reply and destructive actions stay client-initiated); task-detail RPC (option A on-demand, with `TaskInfo` field list); permission cross-check (5 discrepancies vs permissions.md seed table listed, not silently fixed); 8 deferred follow-up bullets (plan had 7; split the permissions.md sync into its own bullet).
- **Deviations from plan:**
  - `PaneSnapshot.content` is the actual field name (plan said `PaneSnapshot.text`) — corrected in the doc.
  - Modal handshakes use a **pull model** (mobile re-sends the gated verb with `confirmed:true` after a `confirm_required` response) instead of the plan's server-push `confirm`/`confirm_response` frames — simpler correlation, no server-side dialog state.
  - `kill_pane` documented as mapping to `kill_agent_pane_smart` (`tmux_monitor.py:643`), the path the desktop confirm flow actually invokes; raw `kill_pane` stays internal.
  - `rename_session` inventoried in the handshake table but flagged desktop-only in v1 (not in the verb gating table).
- **Issues encountered:** A concurrent session was editing this repo mid-task (uncommitted modifications to `monitor_app.py`, `tmux_control.py`, `lib/tmux_exec.py`, etc.). Line citations in the doc were verified against the **current on-disk state** (e.g. `_TEXTUAL_TO_TMUX` at `monitor_app.py:100`, `run_via_control` at `tmux_exec.py:230`); if that session's work is reverted instead of committed, a handful of `monitor_app.py`/`tmux_exec.py` line refs will drift by ~12 lines. Symbol names in every citation make re-anchoring trivial.
- **Key decisions:** ad-hoc SGR parser over `pyte` (input is pre-rendered, no grid state to emulate, no new dependency); pull-model modal RPC; `focus` as the single wire verb for both desktop `switch_to_pane` and data-plane cadence raise; `pick_next_sibling`/`restart_task` inventoried at `full` but mobile implementation explicitly deferred (launch-config screen has no mobile equivalent yet); non-content snapshot fields ride a JSON `pane_status` push, not the binary data plane.
- **Upstream defects identified:** None
- **Notes for sibling tasks:** t822_4 (manual verification) — this task is doc-only, nothing to verify at runtime. t822_5 (QR hostname field) — unrelated surface. For the **follow-up tasks** the user will create from §8 of the doc: the extraction bullet must carry the t952_3 delegation rules (delegate to `lib/tmux_exec.py`, do NOT re-own the dispatcher; `TmuxControlClient`/`Backend` relocation rides with it) and should re-verify all line refs at pick time — the monitor files are under active churn from the t952 track.
