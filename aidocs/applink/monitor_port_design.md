# Monitor → AppLink Port Design

How the existing `ait monitor` TUI is ported to drive a mobile client over the `applink` protocol: the headless-core extraction seam, the canonical command-verb inventory, the snapshot-to-wire mapping, and the modal-dialog handshakes.

## Overview

`ait monitor` (`.aitask-scripts/monitor/monitor_app.py`) is a Textual TUI that polls tmux panes, classifies them (agent / TUI / other), renders snapshots, and dispatches user commands back to tmux. To serve a mobile client, the non-Textual half of that pipeline must become a reusable headless core that both the local TUI and the `ait applink` WebSocket listener can drive.

This document is design-first, but the design it specifies has since been **fully implemented**: the `monitor_core` headless-core extraction (t822_6/t822_7), the permissions-table sync (t822_12), and the applink control plane, data plane, headless bridge, and modal handshakes (t822_7–t822_14) have all landed (§Deferred follow-up tasks). The lone remainder is the workflow-verb launch policy for `pick_next_sibling`/`restart_task` execution, noted there. It defines:

- The **extraction seam**: which symbols were extracted to `monitor_core.py` and which stay UI-bound (§Headless-core extraction).
- The **canonical verb inventory**: every monitor command verb, its applink request frame, payload schema, permission gate, and confirmation-modal requirement (§Command verb → applink protocol mapping). This table supersedes the seed table in [permissions.md](permissions.md) per t822_1's forward-pointer notes.
- The **snapshot wiring**: how `PaneSnapshot` and the monitor refresh loop map onto the fixed wire format of [content_transport.md](content_transport.md) (§Wiring PaneSnapshot to the content transport).
- The **modal handshakes**: RPC request/response shapes replacing the Textual modal screens (§Modal-dialog handshakes).
- The **follow-up task list** that implements all of the above (§Deferred follow-up tasks).

Parent task: [t822](../../aitasks/t822_new_ait_bridge_tui.md). Envelope, pairing, and lifecycle live in [protocol.md](protocol.md); profile vocabulary in [permissions.md](permissions.md); the pane-content wire format in [content_transport.md](content_transport.md).

## Headless-core extraction

The natural seam runs between `TmuxMonitor.capture_all()` output (a `dict[str, PaneSnapshot]`) and the Textual render loop: everything below the seam is pure data/control logic with no Textual imports, everything above is widget- and screen-bound.

### Functions extracted to `.aitask-scripts/monitor/monitor_core.py` (t822_6, landed)

These symbols now live in `monitor_core.py`; `tmux_monitor.py`, `tmux_control.py`, and (for `TaskInfoCache`) `monitor_shared.py` retain re-export shims for existing import sites.

| Symbol | Location | Role |
|--------|----------|------|
| `TmuxPaneInfo` / `PaneSnapshot` dataclasses | `monitor_core.py` | wire-shape source |
| `TmuxMonitor.start_control_client` / `close_control_client` / `has_control_client` / `control_state` | `monitor_core.py` | control-mode lifecycle |
| `TmuxMonitor.discover_panes` / `discover_panes_async` | `monitor_core.py` | pane discovery |
| `TmuxMonitor.cycle_compare_mode` | `monitor_core.py` | idle-detection compare-mode state |
| `TmuxMonitor.capture_pane` / `capture_pane_async` / `capture_all` / `capture_all_async` | `monitor_core.py` | snapshot capture |
| `TmuxMonitor.send_enter` / `send_keys` | `monitor_core.py` | input dispatch |
| `TmuxMonitor.switch_to_pane` / `find_companion_pane_id` | `monitor_core.py` | focus change (`prefer_companion` param) |
| `TmuxMonitor.kill_pane` / `kill_window` / `kill_agent_pane_smart` | `monitor_core.py` | termination (smart kill collapses the window when the last agent dies) |
| `TmuxMonitor.spawn_tui` | `monitor_core.py` | new-window spawn |
| `TmuxControlClient` / `TmuxControlBackend` | `monitor_core.py` | persistent `tmux -C` control-mode client (relocated from `tmux_control.py`) |
| `TaskInfoCache` (incl. `_resolve`) | `monitor_core.py` | task metadata cache (serves §Task-detail RPC) |

### tmux gateway delegation (t952_3 — landed)

The tmux **exec-strategy dispatcher** (control-client-when-alive, subprocess-fallback-on-`-1`) and the socket-flag ownership live in `lib/tmux_exec.py` (`TmuxClient.run_via_control` / `run_async_via_control`). Two hard rules held for the extraction:

- `monitor_core` **delegates to** `lib/tmux_exec.py` as its tmux-exec substrate — it does **not** re-own the dispatcher. The delegation seam: `TmuxMonitor.tmux_run` / `_tmux_async` are thin wrappers over `TmuxClient.run_via_control` and now live in `monitor_core` (`monitor_core.py`).
- The physical relocation of `TmuxControlClient` / `TmuxControlBackend` out of `monitor/tmux_control.py`, deferred from t952_3, landed with the t822_6 extraction — `monitor_core` is now their home, and `tmux_control.py` is a re-export shim.

### What stays in `monitor_app.py` (UI-bound)

| Concern | Location | Why it stays |
|---------|----------|--------------|
| Widgets: `PaneCard`, `MiniPaneCard`, `PreviewPanel` | `monitor_app.py` (`MiniPaneCard` in `minimonitor_app.py`) | Textual render surface |
| Modal screens (see §Modal-dialog handshakes for the class list) | `monitor_app.py` / `monitor_shared.py` | replaced by RPC handshakes on mobile; Textual remains the desktop UX |
| Refresh timer loop | `monitor_app.py` (`_refresh_data`) | cadence policy is per-client (see §Refresh cadence wiring) |
| Key forwarding (`on_key` → `_forward_key_to_tmux`) | `monitor_app.py` (`on_key` / `_forward_key_to_tmux`) | Textual event plumbing; the *mapping* (`_TEXTUAL_TO_TMUX`, now in `monitor_core.py`) is resolved server-side behind the `forward_key` verb |
| Scroll-position memory (`was_at_bottom`/`anchor_text` + `_locate_anchor`) | `monitor_app.py` (`_record_preview_scroll` / `_locate_anchor`) | render-side only — see §Scroll anchor |
| Pane-launch orchestration (`AgentCommandScreen`, `launch_in_tmux`, `maybe_spawn_minimonitor`) | `agent_command_screen.py` + `lib/agent_launch_utils.py` (invoked from `monitor_app.py`) | multi-screen launch config; mobile v1 defers it (see verb table notes) |

The `monitor_shared.py` dialogs are shared with `minimonitor_app.py` — the extraction must keep both TUIs working from the same core.

## Command verb → applink protocol mapping

Canonical v1 inventory. Audited 2026-06-11 against `monitor_core.py` methods and every `action_*` handler in `monitor_app.py`. This is the canonical source; [permissions.md §Verb gating table](permissions.md#verb-gating-table) is the in-sync profile-band view of the same verbs (synced from this inventory in t822_12, including `forward_key`, `pick_next_sibling`, `restart_task`, and `task_detail`).

Request frames use the JSON envelope from [protocol.md §Message envelope](protocol.md#message-envelope); only `verb` and `payload` are shown. Profile names are from [permissions.md](permissions.md).

| Verb | Existing call site | Payload | Profile gate | Modal? |
|------|--------------------|---------|--------------|:------:|
| `snapshot` (server push, data plane) | `monitor_core.py` (`capture_all`) | n/a — pushed per [content_transport.md](content_transport.md) | read_only | N |
| `send_enter` | `monitor_core.py` (`send_enter`) | `{pane_id}` | monitor_control | N |
| `send_keys` | `monitor_core.py` (`send_keys`) | `{pane_id, keys, literal:bool}` | monitor_control | N |
| `forward_key` | `monitor_app.py` (`_forward_key_to_tmux`; map `_TEXTUAL_TO_TMUX` in `monitor_core.py`) | `{pane_id, key:"<abstract-key-name>"}` | monitor_control | N |
| `focus` (= `switch_to_pane`) | `monitor_core.py` (`switch_to_pane`) | `{pane_id, prefer_companion?:bool}` | monitor_control | N |
| `cycle_compare_mode` | `monitor_core.py` (`cycle_compare_mode`; handler `monitor_app.py` `action_cycle_compare_mode`) | `{pane_id}` | monitor_control | N |
| `kill_pane` | `monitor_core.py` (`kill_agent_pane_smart`; raw `kill_pane`) | `{pane_id, confirmed:bool}` | full | Y |
| `kill_window` | `monitor_core.py` (`kill_window`) | `{window_id, confirmed:bool}` | full | Y |
| `spawn_tui` | `monitor_core.py` (`spawn_tui`) | `{tui_name}` | full | N |
| `pick_next_sibling` | `monitor_app.py` (`action_pick_next_sibling`) | `{pane_id, sibling_id?}` | full | Y (suggest → optional chooser) |
| `restart_task` | `monitor_app.py` (`action_restart_task`) | `{pane_id, confirmed:bool}` | full | Y |
| `task_detail` | `monitor_core.py` (`TaskInfoCache._resolve`) | `{task_id}` | read_only | N |
| `subscribe` / `request_keyframe` (data-plane control) | [content_transport.md §Refresh control](content_transport.md#refresh-control-focus-back-pressure) | per content_transport.md | read_only | N |
| `history` (scrollback pull, data-plane) | `applink/router.py` (queues on `Subscription`); served by `applink/pusher.py` (`_drain_history`) as a negative-row-id `keyframe` | `{pane_id, before_line, count}` ([content_transport.md §Scrollback](content_transport.md#scrollback)) | read_only | N |
| `pause` (data-plane self-throttle) | `applink/router.py` (`ConnState.paused`); halts `applink/pusher.py` (`PushScheduler`) until `resume` | `{}` (empty — [content_transport.md §Back-pressure](content_transport.md#back-pressure)) | read_only | N |

Notes:

- **`forward_key` folds `_TEXTUAL_TO_TMUX` into one verb.** The map (`_TEXTUAL_TO_TMUX`, `monitor_core.py`) translates abstract key names (`up`, `escape`, `f5`, …) to tmux `send-keys` arguments; `ctrl+<c>` translates to `C-<c>`, plain characters go literal (`translate_key` in `monitor_core.py`, applied via `_forward_key_to_tmux`). All of that translation runs server-side: mobile sends the abstract key name, the server resolves it. This closes the forward-pointer note in permissions.md (which told clients to send literal escape sequences in the interim).
- **`kill_pane` maps to `kill_agent_pane_smart`.** The desktop confirm path kills via the smart variant (`action_kill_pane` in `monitor_app.py`), which collapses the window when the last agent pane dies (cleaning up its companion minimonitor). The applink verb keeps that semantics; raw `kill_pane` stays an internal primitive.
- **`focus` is the wire name for `switch_to_pane`** — it both moves desktop tmux focus and raises the pane's data-plane cadence (the single `focus` verb from [content_transport.md](content_transport.md) covers both; no separate verb needed). `prefer_companion` is an optional intra-session affordance and defaults to false.
- **`pick_next_sibling` / `restart_task` are workflow-level verbs** discovered in the post-Explore audit. They drive `ait` task flows (resolve the pick command, kill the old pane, launch a new agent window via `AgentCommandScreen` + `launch_in_tmux` — `agent_command_screen.py` / `lib/agent_launch_utils.py`, driven from `action_pick_next_sibling` / `action_restart_task` in `monitor_app.py`), not just tmux primitives. They are **inventoried here for completeness but their mobile implementation is deferred** past the v1 listener — the launch-config screen has no mobile equivalent yet, and a server-side default-launch policy needs its own design. Gate: `full`, with the multi-step handshakes from §Modal-dialog handshakes. `restart_task` additionally requires the pane to be idle (`snap.is_idle`, enforced server-side as on desktop in `action_restart_task`).
- **Pure-UI actions have no verb.** `action_switch_zone`, `action_send_enter` (footer no-op), `action_refresh`, `action_cycle_preview_size`, `action_scroll_preview_tail`, `action_toggle_auto_switch`, `action_toggle_multi_session`, `action_open_log`, and `action_dismiss_dialog` are desktop render/navigation concerns (zone focus, preview sizing, local timers, spawning a desktop log-viewer window). Mobile gets the same data from the snapshot stream and renders its own navigation. `action_show_task_info` is covered by the `task_detail` verb.
- A `req` for a verb above the session's tier returns `err` with `code:"PERMISSION_DENIED"` per [permissions.md](permissions.md).

## Wiring PaneSnapshot to the content transport

The wire format is **fixed** by [content_transport.md](content_transport.md) (per-line styled spans, five frame types `keyframe`/`delta`/`append`/`cursor`/`dim`, MessagePack over WebSocket binary frames). This section maps the existing monitor data model onto that format — it does not redefine the wire format.

### Snapshot → row encoding

`PaneSnapshot.content` (`monitor_core.py`) carries the last N lines of `tmux capture-pane -p -e` output (`_capture_args`, `monitor_core.py`) — raw text with ANSI/SGR escapes. The snapshot push loop parses that once into rows of styled spans per [content_transport.md §Row encoding](content_transport.md#row-encoding-the-core-decision).

**Parser approach — decision:** an **ad-hoc SGR state machine tuned for `capture-pane -e` output**, not `pyte`. Rationale: `capture-pane -e` emits already-rendered lines (no cursor movement, no scroll regions, no alt-screen sequences — tmux resolved all of that); the only escapes present are SGR color/attribute runs and OSC8 hyperlinks. A full terminal emulator like `pyte` would re-implement grid state the input cannot contain, and adds a dependency. The state machine tracks the current `(fg, bg, attrs)` tuple across `ESC[...m` runs, splits each line into spans on attribute change, and computes span `width` with the same width tables tmux uses (per content_transport.md design goal 5). This parser lives next to the deltifier in `monitor_core` (see below).

The non-content `PaneSnapshot` fields (`idle_seconds`, `is_idle`, `awaiting_input`, `awaiting_input_kind`) plus `TmuxPaneInfo` identity fields (`window_name`, `category`, `session_name`) do **not** ride the binary data plane — they are pane *status*, not pane *content*. They travel as a JSON `push` frame (`verb:"pane_status"`) at the idle cadence, so the mobile pane list can show the same idle/awaiting-input badges as `PaneCard` without decoding binary frames.

### Refresh cadence wiring

| Desktop today | Wire knob ([content_transport.md §subscribe](content_transport.md#refresh-control-focus-back-pressure)) | Default mapping |
|---------------|------------------------------------------------|-----------------|
| Main refresh timer: `refresh_seconds` (default 3, from `--interval` / `tmux.monitor.refresh_seconds` — `_refresh_data` in `monitor_app.py`) | `cadence_idle_ms` | 3 s → `3000` |
| Fast preview timer: 0.3 s while the preview zone is focused (`monitor_app.py`) | `cadence_focused_ms` | 0.3 s → `300` |

The applink listener reuses the same `capture_all_async` tick but drives per-pane cadence from the mobile `subscribe` payload instead of the Textual zone state. The server clamps requested cadences to its own policy floor (the existing control-client throughput is the binding constraint, not the wire).

### Focus-state forwarding

Mobile's `focus` control verb maps onto the per-pane focused-state the desktop tracks as `_focused_pane_id`: the focused pane gets `cadence_focused_ms`, all others drop to `cadence_idle_ms` (single focused pane, matching the desktop model). The same verb also performs the desktop `switch_to_pane`. `focus` is gated `monitor_control` or higher (it is both a control action and a cadence change); a `read_only` client cannot call it, and instead raises a pane's cadence by **subscribing to just that pane with a fast `cadence_idle_ms`** (server-clamped to the policy floor). So cadence is purely a `subscribe`-payload concern and `focus` stays purely a control verb — no tier-conditional dispatch, no wire change needed.

### Scroll anchor — no wire impact

The desktop preview keeps per-pane scroll memory as `(was_at_bottom, anchor_text)` and re-finds the anchor line after refresh (`_record_preview_scroll` / `_locate_anchor` in `monitor_app.py`) because the rolling capture buffer shifts line indices between polls. This is a **render-side concern only**. On the wire, content_transport.md's frame-independent keyframes and linear `frame_id` chain ([§Frame integrity and recovery](content_transport.md#frame-integrity-and-recovery)) give the mobile client stable continuity: it rebuilds scroll position from `frame_id` succession (and `append` row flow) rather than substring matching. Mobile must not duplicate the anchor mechanism, and the server must not put anchor state on the wire.

### Deltification responsibility

content_transport.md assigns delta computation to the server (row hashing + changed-row collection, Stage 2). It lives in **`applink/content.py`** (the pure `deltify` / `row_signature` / `build_osc8` helpers), and the per-row hash state is kept **per-connection** on `Subscription.PaneState.row_sigs`, driven by the applink push scheduler (`applink/pusher.py`) — not in `monitor_core` and not in `monitor_app.py`'s render loop. The capture pipeline that *does* need to be shared is already shared (`monitor_core.capture_all_async`, t822_8); a per-row hash *cache* does not, because a delta is computed against the specific frame a given client last received, and two clients on the same pane generally sit at different `frame_id`s — so the diff baseline is irreducibly per-client. A cross-client shared cache could only memoize the current-capture row hashes (computed once per tick anyway) and would couple the shared TUI core to applink's subscription lifecycle for no real benefit at the realistic client count. The existing per-pane change tracking (`_last_content` / `_last_change_time`, `monitor_core.py`) stays separate: it feeds idle detection at whole-pane granularity, while the deltifier hashes per-row; merging them is a non-goal.

### Append fast-path detection

The Stage 3 `append` fast path ([content_transport.md §append](content_transport.md#append)) is implemented by `detect_append` in `applink/content.py`, next to `deltify` and keyed off the same per-connection `Subscription.PaneState.row_sigs` baseline: it already has the previous and current row signatures in hand, so the bottom-growth test is a cheap prefix comparison — the new grid is the baseline scrolled up by *k* rows (`new[i] == prev[i+k]`). The emit slots into `pusher._push_pane` *before* the delta path. Beyond the shift match, the cursor gate requires the **full cursor tuple unchanged and at the bottom row** (a new `PaneState.last_cursor`), because `append` carries no cursor — emitting one while the cursor moved would strand the client with a stale cursor.

Alt-screen is **not** detected explicitly — `PaneSnapshot` exposes no alt-screen flag. Exact-shift detection is the deliberate conservative substitute: a vim/htop redraw is not a clean full-viewport shift and falls back to `delta`, and a coincidental alt-screen shift is still convergence-correct (the client reaches the same grid a keyframe would produce). So the implemented condition is "exact shift + unchanged cursor", not a literal "no scroll-region/alt-screen" check.

## Modal-dialog handshakes

Desktop modals become control-plane RPC round-trips. The server pushes a request, the mobile client renders a native dialog and replies; correlation uses the envelope `id`. Gating applies to the underlying verb (per [permissions.md](permissions.md)), not the handshake frames.

| Dialog | Location | Handshake |
|--------|----------|-----------|
| `KillConfirmDialog` | `monitor_shared.py` | Mobile sends `kill_pane` with `confirmed:false` → server replies `res` with `{confirm_required:true, target:{pane_id, window_name, task?}}` → mobile re-sends with `confirmed:true` to execute. (Pull model: mobile initiates, so no unsolicited push is needed.) Same for `kill_window` and `restart_task`. |
| `RestartConfirmDialog` | `monitor_app.py` | As above; the `res` detail includes `{task_id, title, status, idle_seconds}` and the server rejects non-idle panes with `err` `code:"BAD_PAYLOAD"`, `detail:{reason:"not_idle"}`. |
| `SessionRenameDialog` | `monitor_app.py` | Mobile sends `rename_session` with `{session_id, name?}`; with `name` absent the `res` returns `{current:"<old>"}` for the edit field; with `name` present the rename executes. (Desktop-only in v1 — inventoried for parity, not gated in the v1 table; add to permissions.md when implemented.) |
| `NextSiblingDialog` / `ChooseSiblingModal` | `monitor_shared.py` | Two-step: `pick_next_sibling` with no `sibling_id` → `res` `{suggested:{id,title}, current:{id,title,status}, parent_id, ready_siblings:[{id,title},…]}` → mobile either re-sends with the chosen `sibling_id` to execute, or drops it. The desktop suggest-then-choose flow (`action_pick_next_sibling` in `monitor_app.py`) collapses into one round-trip plus the confirmed call. |
| `TaskDetailDialog` | `monitor_shared.py` | Read-only — see §Task-detail RPC. |

The pull-model convention (mobile re-sends with `confirmed:true` / a chosen ID) keeps every destructive action client-initiated and idempotent on the server; the server never blocks a thread waiting for a dialog reply, matching the desktop's callback style in `monitor_app.py`.

## Task-detail RPC

Mobile has no filesystem, so `TaskInfoCache` (`monitor_core.py`, resolver `_resolve`) must be served over the wire. Two options were considered:

- **(A) On-demand RPC (chosen):** mobile sends `{"verb":"task_detail","payload":{"task_id":"<id>"}}`; the server resolves via `TaskInfoCache` and returns the `TaskInfo` fields (`TaskInfo` in `monitor_core.py`): `{task_id, task_file, title, priority, effort, issue_type, status, body, plan_content}`. The server invalidates the cache entry first, matching the desktop force-refresh (`action_show_task_info` in `monitor_app.py`).
- (B) Embed in snapshot: every pane status push includes the rendered task detail. Rejected — task bodies and plan content are large and change rarely; embedding them multiplies idle-cadence traffic for data the user views occasionally.

The lightweight identity fields the pane list *does* need continuously (task id, title, status) ride the `pane_status` push from §Snapshot → row encoding, resolved through the same cache.

## Permission profile cross-check

Every verb in the §Command verb table maps to exactly one profile band from [permissions.md](permissions.md), and all three profiles (`read_only`, `monitor_control`, `full`) are used. The discrepancies with permissions.md's original seed table below were resolved by the sync follow-up in t822_12 (permissions.md now matches this inventory):

- `forward_key` — was absent from the seed table (its note anticipated this doc); now gated at `monitor_control`.
- `pick_next_sibling`, `restart_task` — were new verbs, absent from the seed table; now gated at `full`.
- `task_detail` — was absent from the seed table; now gated at `read_only` (read-only data, same band as `snapshot`).
- `rename_session` — desktop-only in v1; add a row only when implemented.
- `kill_pane`'s call-site citation references `kill_agent_pane_smart` (`monitor_core.py`), which is what the confirmed desktop path actually invokes (not the raw `kill_pane` primitive).

## Deferred follow-up tasks

Every bullet below has since **landed** (the `monitor_core` extraction plus the applink control plane, data plane, headless bridge, and modal handshakes shipped across t822_6–t822_14). The one genuine remainder is noted inline: the workflow-verb *execution* for `pick_next_sibling`/`restart_task` (kill-old-pane + relaunch-agent) is deferred pending an applink launch policy — the handshake round-trips themselves are wired and return `NOT_IMPLEMENTED` on the final execute.

- **✅ Landed (t822_6 / t822_7) — Refactor: extract `monitor_core.py`** — moved the §Headless-core extraction symbols into the new module, leaving thin import shims in `tmux_monitor.py` / `tmux_control.py` / `monitor_shared.py` for backwards compatibility. Included the physical relocation of `TmuxControlClient` / `TmuxControlBackend` out of `monitor/tmux_control.py` (deferred from t952_3 — monitor_core is their home), and the move of `_TEXTUAL_TO_TMUX` / `translate_key` server-side (t822_7). monitor_core **delegates** tmux exec to `lib/tmux_exec.py` (`TmuxClient.run_via_control`); it does not re-own the dispatcher. `ait monitor` and `ait minimonitor` both still launch from the shared core.
- **✅ Landed (t822_7) — applink: WebSocket listener** — `AppLinkServer` (`applink/server.py`) wraps the pure `FrameRouter` (`applink/router.py`) in a `wss://` server (TLS, refuses plaintext fallback), accepts the `pair` verb per [protocol.md](protocol.md), and routes control frames per the §Command verb table, enforcing profile gates. Executes verbs through `monitor_core`.
- **✅ Landed (t822_8; hardened t822_14) — applink: snapshot push loop (Stage 1 of content_transport.md)** — `PushScheduler` (`applink/pusher.py`) drives `capture_all_async` on the subscribe cadences; the ad-hoc SGR state machine (`parse_sgr_line` / `parse_snapshot` in `applink/content.py`, §Snapshot → row encoding) parses `capture-pane -e` output into the row/span schema; emits `keyframe`/`cursor`/`dim` frames plus the `pane_status` JSON push. `subscribe` and `focus` are wired.
- **✅ Landed (t822_9) — applink: delta engine (Stage 2 of content_transport.md)** — per-row hashing + changed-row collection (`deltify` / `row_signature` in `applink/content.py`) against the per-connection `PaneState.row_sigs` baseline; emits `delta` frames against `prev_frame_id`; `request_keyframe` recovery path implemented.
- **✅ Landed (t822_10) — applink: append fast-path (Stage 3 of content_transport.md)** — bottom-cursor + no-upper-changes detection (`detect_append` in `applink/content.py`) next to the deltifier; emits `append` frames for log-streaming panes.
- **✅ Landed (t822_11) — applink: modal handshake plumbing** — the §Modal-dialog handshakes pull-model round-trips (`confirm_required` responses, re-send-with-`confirmed` execution, `pick_next_sibling` suggest/choose), correlated by envelope `id`. **Remainder:** the final kill+relaunch *execution* of `pick_next_sibling`/`restart_task` returns `NOT_IMPLEMENTED`, deferred until the applink workflow launch policy lands.
- **✅ Landed (t822_12) — applink: update `permissions.md` verb gating table** — synced the canonical §Command verb inventory (incl. `forward_key`, `pick_next_sibling`, `restart_task`, `task_detail`) back into [permissions.md](permissions.md) with matching `applink_profiles/*.yaml` updates.
- **✅ Landed (t822_13) — applink-mode flag for `aitask_monitor.sh`** — `--headless-for-applink` skips Textual startup and runs the applink listener TUI-less via `applink/headless.py` (for running the bridge on a box nobody is watching).

## Out of scope (this document)

- Any code change under `.aitask-scripts/monitor/` — this document is design only; the `monitor_core` refactor was delivered by the now-landed follow-up task above (t822_6).
- The applink WebSocket listener implementation — delivered by the now-landed follow-up above (t822_7).
- Mobile-side rendering, dialog UX, and scroll handling — lives in `../aitasks_mobile`.
- Editing `aidocs/applink/permissions.md` — the sync is its own follow-up bullet so the seed table and the YAML profiles move together.
