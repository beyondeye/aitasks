# Monitor → AppLink Port Design

How the existing `ait monitor` TUI is ported to drive a mobile client over the `applink` protocol: the headless-core extraction seam, the canonical command-verb inventory, the snapshot-to-wire mapping, and the modal-dialog handshakes.

## Overview

`ait monitor` (`.aitask-scripts/monitor/monitor_app.py`) is a Textual TUI that polls tmux panes, classifies them (agent / TUI / other), renders snapshots, and dispatches user commands back to tmux. To serve a mobile client, the non-Textual half of that pipeline must become a reusable headless core that both the local TUI and the `ait applink` WebSocket listener can drive.

This document is design-only — it produces no code changes. It defines:

- The **extraction seam**: which symbols move to a future `monitor_core.py` and which stay UI-bound (§Headless-core extraction).
- The **canonical verb inventory**: every monitor command verb, its applink request frame, payload schema, permission gate, and confirmation-modal requirement (§Command verb → applink protocol mapping). This table supersedes the seed table in [permissions.md](permissions.md) per t822_1's forward-pointer notes.
- The **snapshot wiring**: how `PaneSnapshot` and the monitor refresh loop map onto the fixed wire format of [content_transport.md](content_transport.md) (§Wiring PaneSnapshot to the content transport).
- The **modal handshakes**: RPC request/response shapes replacing the Textual modal screens (§Modal-dialog handshakes).
- The **follow-up task list** that implements all of the above (§Deferred follow-up tasks).

Parent task: [t822](../../aitasks/t822_new_ait_bridge_tui.md). Envelope, pairing, and lifecycle live in [protocol.md](protocol.md); profile vocabulary in [permissions.md](permissions.md); the pane-content wire format in [content_transport.md](content_transport.md).

## Headless-core extraction

The natural seam runs between `TmuxMonitor.capture_all()` output (a `dict[str, PaneSnapshot]`) and the Textual render loop: everything below the seam is pure data/control logic with no Textual imports, everything above is widget- and screen-bound.

### Functions moving to `.aitask-scripts/monitor/monitor_core.py` (future)

| Symbol | Source | Role |
|--------|--------|------|
| `TmuxPaneInfo` / `PaneSnapshot` dataclasses | `tmux_monitor.py:105,119` | wire-shape source |
| `TmuxMonitor.start_control_client` / `close_control_client` / `has_control_client` / `control_state` | `tmux_monitor.py:171-205` | control-mode lifecycle |
| `TmuxMonitor.discover_panes` / `discover_panes_async` | `tmux_monitor.py:345,356` | pane discovery |
| `TmuxMonitor.cycle_compare_mode` | `tmux_monitor.py:435` | idle-detection compare-mode state |
| `TmuxMonitor.capture_pane` / `capture_pane_async` / `capture_all` / `capture_all_async` | `tmux_monitor.py:498,507,526,537` | snapshot capture |
| `TmuxMonitor.send_enter` / `send_keys` | `tmux_monitor.py:552,556` | input dispatch |
| `TmuxMonitor.switch_to_pane` / `find_companion_pane_id` | `tmux_monitor.py:569,598` | focus change (`prefer_companion` param) |
| `TmuxMonitor.kill_pane` / `kill_window` / `kill_agent_pane_smart` | `tmux_monitor.py:623,633,643` | termination (smart kill collapses the window when the last agent dies) |
| `TmuxMonitor.spawn_tui` | `tmux_monitor.py:685` | new-window spawn |
| `TmuxControlClient` / `TmuxControlBackend` | `tmux_control.py:76,313` | persistent `tmux -C` control-mode client |
| `TaskInfoCache` (incl. `_resolve`) | `monitor_shared.py:103,311` | task metadata cache (serves §Task-detail RPC) |

### tmux gateway delegation (t952_3 — landed)

The tmux **exec-strategy dispatcher** (control-client-when-alive, subprocess-fallback-on-`-1`) and the socket-flag ownership live in `lib/tmux_exec.py` (`TmuxClient.run_via_control` / `run_async_via_control`, `tmux_exec.py:230`). Two hard rules for the extraction:

- `monitor_core` **delegates to** `lib/tmux_exec.py` as its tmux-exec substrate — it does **not** re-own the dispatcher. The delegation seam already exists: `TmuxMonitor.tmux_run` / `_tmux_async` are thin wrappers over `TmuxClient.run_via_control` (`tmux_monitor.py:207-231`) and move to `monitor_core` as-is.
- The physical relocation of `TmuxControlClient` / `TmuxControlBackend` out of `monitor/tmux_control.py` was deliberately deferred from t952_3 to ride with this extraction — `monitor_core` is their natural home. The extraction follow-up task (§Deferred follow-up tasks) inherits this.

### What stays in `monitor_app.py` (UI-bound)

| Concern | Location | Why it stays |
|---------|----------|--------------|
| Widgets: `PaneCard`, `MiniPaneCard`, `PreviewPanel` | `monitor_app.py` (also `minimonitor_app.py`) | Textual render surface |
| Modal screens (see §Modal-dialog handshakes for the full list) | `monitor_app.py:198,265`; `monitor_shared.py:418-695` | replaced by RPC handshakes on mobile; Textual remains the desktop UX |
| Refresh timer loop | `monitor_app.py:617-619` | cadence policy is per-client (see §Refresh cadence wiring) |
| Key forwarding (`on_key` → `_forward_key_to_tmux`) | `monitor_app.py:1296,1342` | Textual event plumbing; the *mapping* (`_TEXTUAL_TO_TMUX`, `monitor_app.py:100`) moves server-side behind the `forward_key` verb |
| Scroll-position memory (`was_at_bottom`/`anchor_text` + `_locate_anchor`) | `monitor_app.py:450-458,629-642` | render-side only — see §Scroll anchor |
| Pane-launch orchestration (`AgentCommandScreen`, `launch_in_tmux`, `maybe_spawn_minimonitor`) | `monitor_app.py:1704-1726` | multi-screen launch config; mobile v1 defers it (see verb table notes) |

The `monitor_shared.py` dialogs are shared with `minimonitor_app.py` — the extraction must keep both TUIs working from the same core.

## Command verb → applink protocol mapping

Canonical v1 inventory. Audited 2026-06-11 against `tmux_monitor.py` methods and every `action_*` handler in `monitor_app.py:1262-1823` — this supersedes the seed table in [permissions.md §Verb gating table](permissions.md#verb-gating-table) (which predates `forward_key`, `pick_next_sibling`, and `restart_task`).

Request frames use the JSON envelope from [protocol.md §Message envelope](protocol.md#message-envelope); only `verb` and `payload` are shown. Profile names are from [permissions.md](permissions.md).

| Verb | Existing call site | Payload | Profile gate | Modal? |
|------|--------------------|---------|--------------|:------:|
| `snapshot` (server push, data plane) | `tmux_monitor.py:526` (`capture_all`) | n/a — pushed per [content_transport.md](content_transport.md) | read_only | N |
| `send_enter` | `tmux_monitor.py:552` | `{pane_id}` | monitor_control | N |
| `send_keys` | `tmux_monitor.py:556` | `{pane_id, keys, literal:bool}` | monitor_control | N |
| `forward_key` | `monitor_app.py:100,1342` (`_TEXTUAL_TO_TMUX`, `_forward_key_to_tmux`) | `{pane_id, key:"<abstract-key-name>"}` | monitor_control | N |
| `focus` (= `switch_to_pane`) | `tmux_monitor.py:569` | `{pane_id, prefer_companion?:bool}` | monitor_control | N |
| `cycle_compare_mode` | `tmux_monitor.py:435` (handler `monitor_app.py:1489`) | `{pane_id}` | monitor_control | N |
| `kill_pane` | `tmux_monitor.py:643` (`kill_agent_pane_smart`; raw `kill_pane` at `:623`) | `{pane_id, confirmed:bool}` | full | Y |
| `kill_window` | `tmux_monitor.py:633` | `{window_id, confirmed:bool}` | full | Y |
| `spawn_tui` | `tmux_monitor.py:685` | `{tui_name}` | full | N |
| `pick_next_sibling` | `monitor_app.py:1602` | `{pane_id, sibling_id?}` | full | Y (suggest → optional chooser) |
| `restart_task` | `monitor_app.py:1728` | `{pane_id, confirmed:bool}` | full | Y |
| `task_detail` | `monitor_shared.py:311` (`TaskInfoCache._resolve`) | `{task_id}` | read_only | N |
| `subscribe` / `request_keyframe` (data-plane control) | [content_transport.md §Refresh control](content_transport.md#refresh-control-focus-back-pressure) | per content_transport.md | read_only | N |

Notes:

- **`forward_key` folds `_TEXTUAL_TO_TMUX` into one verb.** The map (`monitor_app.py:100`) translates abstract key names (`up`, `escape`, `f5`, …) to tmux `send-keys` arguments; `ctrl+<c>` translates to `C-<c>`, plain characters go literal (`monitor_app.py:1342-1363`). All of that translation runs server-side: mobile sends the abstract key name, the server resolves it. This closes the forward-pointer note in permissions.md (which told clients to send literal escape sequences in the interim).
- **`kill_pane` maps to `kill_agent_pane_smart`.** The desktop confirm path kills via the smart variant (`monitor_app.py:1594`), which collapses the window when the last agent pane dies (cleaning up its companion minimonitor). The applink verb keeps that semantics; raw `kill_pane` stays an internal primitive.
- **`focus` is the wire name for `switch_to_pane`** — it both moves desktop tmux focus and raises the pane's data-plane cadence (the single `focus` verb from [content_transport.md](content_transport.md) covers both; no separate verb needed). `prefer_companion` is an optional intra-session affordance and defaults to false.
- **`pick_next_sibling` / `restart_task` are workflow-level verbs** discovered in the post-Explore audit. They drive `ait` task flows (resolve the pick command, kill the old pane, launch a new agent window via `AgentCommandScreen` + `launch_in_tmux`, `monitor_app.py:1669-1726,1760-1823`), not just tmux primitives. They are **inventoried here for completeness but their mobile implementation is deferred** past the v1 listener — the launch-config screen has no mobile equivalent yet, and a server-side default-launch policy needs its own design. Gate: `full`, with the multi-step handshakes from §Modal-dialog handshakes. `restart_task` additionally requires the pane to be idle (`snap.is_idle`, enforced server-side as on desktop, `monitor_app.py:1739`).
- **Pure-UI actions have no verb.** `action_switch_zone`, `action_send_enter` (footer no-op), `action_refresh`, `action_cycle_preview_size`, `action_scroll_preview_tail`, `action_toggle_auto_switch`, `action_toggle_multi_session`, `action_open_log`, and `action_dismiss_dialog` are desktop render/navigation concerns (zone focus, preview sizing, local timers, spawning a desktop log-viewer window). Mobile gets the same data from the snapshot stream and renders its own navigation. `action_show_task_info` is covered by the `task_detail` verb.
- A `req` for a verb above the session's tier returns `err` with `code:"PERMISSION_DENIED"` per [permissions.md](permissions.md).

## Wiring PaneSnapshot to the content transport

The wire format is **fixed** by [content_transport.md](content_transport.md) (per-line styled spans, five frame types `keyframe`/`delta`/`append`/`cursor`/`dim`, MessagePack over WebSocket binary frames). This section maps the existing monitor data model onto that format — it does not redefine the wire format.

### Snapshot → row encoding

`PaneSnapshot.content` (`tmux_monitor.py:119-126`) carries the last N lines of `tmux capture-pane -p -e` output (`_capture_args`, `tmux_monitor.py:492`) — raw text with ANSI/SGR escapes. The snapshot push loop parses that once into rows of styled spans per [content_transport.md §Row encoding](content_transport.md#row-encoding-the-core-decision).

**Parser approach — decision:** an **ad-hoc SGR state machine tuned for `capture-pane -e` output**, not `pyte`. Rationale: `capture-pane -e` emits already-rendered lines (no cursor movement, no scroll regions, no alt-screen sequences — tmux resolved all of that); the only escapes present are SGR color/attribute runs and OSC8 hyperlinks. A full terminal emulator like `pyte` would re-implement grid state the input cannot contain, and adds a dependency. The state machine tracks the current `(fg, bg, attrs)` tuple across `ESC[...m` runs, splits each line into spans on attribute change, and computes span `width` with the same width tables tmux uses (per content_transport.md design goal 5). This parser lives next to the deltifier in `monitor_core` (see below).

The non-content `PaneSnapshot` fields (`idle_seconds`, `is_idle`, `awaiting_input`, `awaiting_input_kind`) plus `TmuxPaneInfo` identity fields (`window_name`, `category`, `session_name`) do **not** ride the binary data plane — they are pane *status*, not pane *content*. They travel as a JSON `push` frame (`verb:"pane_status"`) at the idle cadence, so the mobile pane list can show the same idle/awaiting-input badges as `PaneCard` without decoding binary frames.

### Refresh cadence wiring

| Desktop today | Wire knob ([content_transport.md §subscribe](content_transport.md#refresh-control-focus-back-pressure)) | Default mapping |
|---------------|------------------------------------------------|-----------------|
| Main refresh timer: `refresh_seconds` (default 3, from `--interval` / `tmux.monitor.refresh_seconds` — `monitor_app.py:617-619,1883`) | `cadence_idle_ms` | 3 s → `3000` |
| Fast preview timer: 0.3 s while the preview zone is focused (`monitor_app.py:1271`) | `cadence_focused_ms` | 0.3 s → `300` |

The applink listener reuses the same `capture_all_async` tick but drives per-pane cadence from the mobile `subscribe` payload instead of the Textual zone state. The server clamps requested cadences to its own policy floor (the existing control-client throughput is the binding constraint, not the wire).

### Focus-state forwarding

Mobile's `focus` control verb maps onto the per-pane focused-state the desktop tracks as `_focused_pane_id`: the focused pane gets `cadence_focused_ms`, all others drop to `cadence_idle_ms` (single focused pane, matching the desktop model). The same verb also performs the desktop `switch_to_pane`. `focus` is gated `monitor_control` or higher (it is both a control action and a cadence change); a `read_only` client cannot call it, and instead raises a pane's cadence by **subscribing to just that pane with a fast `cadence_idle_ms`** (server-clamped to the policy floor). So cadence is purely a `subscribe`-payload concern and `focus` stays purely a control verb — no tier-conditional dispatch, no wire change needed.

### Scroll anchor — no wire impact

The desktop preview keeps per-pane scroll memory as `(was_at_bottom, anchor_text)` and re-finds the anchor line after refresh (`monitor_app.py:450-458`, `_locate_anchor` at `monitor_app.py:629-642`) because the rolling capture buffer shifts line indices between polls. This is a **render-side concern only**. On the wire, content_transport.md's frame-independent keyframes and linear `frame_id` chain ([§Frame integrity and recovery](content_transport.md#frame-integrity-and-recovery)) give the mobile client stable continuity: it rebuilds scroll position from `frame_id` succession (and `append` row flow) rather than substring matching. Mobile must not duplicate the anchor mechanism, and the server must not put anchor state on the wire.

### Deltification responsibility

content_transport.md assigns delta computation to the server (row hashing + changed-row collection, Stage 2). It lives in **`applink/content.py`** (the pure `deltify` / `row_signature` / `build_osc8` helpers), and the per-row hash state is kept **per-connection** on `Subscription.PaneState.row_sigs`, driven by the applink push scheduler (`applink/pusher.py`) — not in `monitor_core` and not in `monitor_app.py`'s render loop. The capture pipeline that *does* need to be shared is already shared (`monitor_core.capture_all_async`, t822_8); a per-row hash *cache* does not, because a delta is computed against the specific frame a given client last received, and two clients on the same pane generally sit at different `frame_id`s — so the diff baseline is irreducibly per-client. A cross-client shared cache could only memoize the current-capture row hashes (computed once per tick anyway) and would couple the shared TUI core to applink's subscription lifecycle for no real benefit at the realistic client count. The existing per-pane change tracking (`_last_content` / `_last_change_time`, `tmux_monitor.py:459-465`) stays separate: it feeds idle detection at whole-pane granularity, while the deltifier hashes per-row; merging them is a non-goal.

### Append fast-path detection

The Stage 3 `append` fast path ([content_transport.md §append](content_transport.md#append)) is implemented by `detect_append` in `applink/content.py`, next to `deltify` and keyed off the same per-connection `Subscription.PaneState.row_sigs` baseline: it already has the previous and current row signatures in hand, so the bottom-growth test is a cheap prefix comparison — the new grid is the baseline scrolled up by *k* rows (`new[i] == prev[i+k]`). The emit slots into `pusher._push_pane` *before* the delta path. Beyond the shift match, the cursor gate requires the **full cursor tuple unchanged and at the bottom row** (a new `PaneState.last_cursor`), because `append` carries no cursor — emitting one while the cursor moved would strand the client with a stale cursor.

Alt-screen is **not** detected explicitly — `PaneSnapshot` exposes no alt-screen flag. Exact-shift detection is the deliberate conservative substitute: a vim/htop redraw is not a clean full-viewport shift and falls back to `delta`, and a coincidental alt-screen shift is still convergence-correct (the client reaches the same grid a keyframe would produce). So the implemented condition is "exact shift + unchanged cursor", not a literal "no scroll-region/alt-screen" check.

## Modal-dialog handshakes

Desktop modals become control-plane RPC round-trips. The server pushes a request, the mobile client renders a native dialog and replies; correlation uses the envelope `id`. Gating applies to the underlying verb (per [permissions.md](permissions.md)), not the handshake frames.

| Dialog | Location | Handshake |
|--------|----------|-----------|
| `KillConfirmDialog` | `monitor_shared.py:489` | Mobile sends `kill_pane` with `confirmed:false` → server replies `res` with `{confirm_required:true, target:{pane_id, window_name, task?}}` → mobile re-sends with `confirmed:true` to execute. (Pull model: mobile initiates, so no unsolicited push is needed.) Same for `kill_window` and `restart_task`. |
| `RestartConfirmDialog` | `monitor_app.py:265` | As above; the `res` detail includes `{task_id, title, status, idle_seconds}` and the server rejects non-idle panes with `err` `code:"BAD_PAYLOAD"`, `detail:{reason:"not_idle"}`. |
| `SessionRenameDialog` | `monitor_app.py:198` | Mobile sends `rename_session` with `{session_id, name?}`; with `name` absent the `res` returns `{current:"<old>"}` for the edit field; with `name` present the rename executes. (Desktop-only in v1 — inventoried for parity, not gated in the v1 table; add to permissions.md when implemented.) |
| `NextSiblingDialog` / `ChooseSiblingModal` | `monitor_shared.py:571,695` | Two-step: `pick_next_sibling` with no `sibling_id` → `res` `{suggested:{id,title}, current:{id,title,status}, parent_id, ready_siblings:[{id,title},…]}` → mobile either re-sends with the chosen `sibling_id` to execute, or drops it. The desktop suggest-then-choose flow (`monitor_app.py:1602-1667`) collapses into one round-trip plus the confirmed call. |
| `TaskDetailDialog` | `monitor_shared.py:418` | Read-only — see §Task-detail RPC. |

The pull-model convention (mobile re-sends with `confirmed:true` / a chosen ID) keeps every destructive action client-initiated and idempotent on the server; the server never blocks a thread waiting for a dialog reply, matching the desktop's callback style (`monitor_app.py:1585-1600`).

## Task-detail RPC

Mobile has no filesystem, so `TaskInfoCache` (`monitor_shared.py:103`, resolver `_resolve` at `monitor_shared.py:311`) must be served over the wire. Two options were considered:

- **(A) On-demand RPC (chosen):** mobile sends `{"verb":"task_detail","payload":{"task_id":"<id>"}}`; the server resolves via `TaskInfoCache` and returns the `TaskInfo` fields (`monitor_shared.py:89-100`): `{task_id, task_file, title, priority, effort, issue_type, status, body, plan_content}`. The server invalidates the cache entry first, matching the desktop force-refresh (`monitor_app.py:1517`).
- (B) Embed in snapshot: every pane status push includes the rendered task detail. Rejected — task bodies and plan content are large and change rarely; embedding them multiplies idle-cadence traffic for data the user views occasionally.

The lightweight identity fields the pane list *does* need continuously (task id, title, status) ride the `pane_status` push from §Snapshot → row encoding, resolved through the same cache.

## Permission profile cross-check

Every verb in the §Command verb table maps to exactly one profile band from [permissions.md](permissions.md), and all three profiles (`read_only`, `monitor_control`, `full`) are used. Discrepancies with permissions.md's seed table, to be resolved by the sync follow-up (§Deferred follow-up tasks) — not silently fixed here:

- `forward_key` — absent from the seed table (its note anticipated this doc); gate at `monitor_control`.
- `pick_next_sibling`, `restart_task` — new verbs, not in the seed table; gate at `full`.
- `task_detail` — not in the seed table; gate at `read_only` (read-only data, same band as `snapshot`).
- `rename_session` — desktop-only in v1; add a row only when implemented.
- `kill_pane`'s call-site citation should move from raw `kill_pane` to `kill_agent_pane_smart` (`tmux_monitor.py:643`), which is what the confirmed desktop path actually invokes.

## Deferred follow-up tasks

Each bullet is scoped to be lifted into its own `ait task create` call:

- **Refactor: extract `monitor_core.py`** — move the §Headless-core extraction symbols into a new module, leaving thin import shims in `tmux_monitor.py` / `tmux_control.py` / `monitor_shared.py` for backwards compatibility. Includes the deferred physical relocation of `TmuxControlClient` / `TmuxControlBackend` out of `monitor/tmux_control.py` (deferred from t952_3 — monitor_core is their natural home). monitor_core **delegates** tmux exec to `lib/tmux_exec.py` (`TmuxClient.run_via_control`); it does not re-own the dispatcher. Verify `ait monitor` and `ait minimonitor` both still launch.
- **applink: WebSocket listener** — start a TLS WS server from the applink TUI, accept the `pair` verb per [protocol.md](protocol.md), and route subsequent control frames per the §Command verb table, enforcing profile gates. Integrates with `monitor_core` for verb execution.
- **applink: snapshot push loop (Stage 1 of content_transport.md)** — drive `capture_all_async` on the subscribe cadences, parse `capture-pane -e` output into the row/span schema with the ad-hoc SGR state machine (§Snapshot → row encoding), emit `keyframe`/`cursor`/`dim` frames plus the `pane_status` JSON push. Wire `subscribe` and `focus`.
- **applink: delta engine (Stage 2 of content_transport.md)** — per-row hashing + changed-row collection in `monitor_core`; emit `delta` frames against `prev_frame_id`; implement the `request_keyframe` recovery path.
- **applink: append fast-path (Stage 3 of content_transport.md)** — bottom-cursor + no-upper-changes detection next to the deltifier; emit `append` frames for log-streaming panes.
- **applink: modal handshake plumbing** — implement the §Modal-dialog handshakes pull-model round-trips (`confirm_required` responses, re-send-with-`confirmed` execution, `pick_next_sibling` suggest/choose), correlated by envelope `id`.
- **applink: update `permissions.md` verb gating table** — sync the canonical §Command verb inventory (incl. `forward_key`, `pick_next_sibling`, `restart_task`, `task_detail`) back into [permissions.md](permissions.md) and ship matching `applink_profiles/*.yaml` updates.
- **applink-mode flag for `aitask_monitor.sh`** — a `--headless-for-applink` mode that skips Textual startup and exposes `monitor_core` only via the applink listener (for running the bridge on a box nobody is watching).

## Out of scope (this document)

- Any code change under `.aitask-scripts/monitor/` — this is design only; the refactor is the first follow-up bullet above.
- The applink WebSocket listener implementation (second bullet).
- Mobile-side rendering, dialog UX, and scroll handling — lives in `../aitasks_mobile`.
- Editing `aidocs/applink/permissions.md` — the sync is its own follow-up bullet so the seed table and the YAML profiles move together.
