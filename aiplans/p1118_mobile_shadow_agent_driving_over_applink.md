---
Task: t1118_mobile_shadow_agent_driving_over_applink.md
Base branch: main
plan_verified: []
---

# t1118 — Mobile shadow-agent driving over applink (paired cross-repo plan)

## Context

Shadow-agent driving — spawning an advisory shadow companion beside a followed code
agent, viewing/typing into it, picking and forwarding its concerns, and seeing
feedback-staleness warnings — today lives only in `ait minimonitor` (`e` spawn key,
`c` concern picker). The applink server and the mobile companion app
(`aitasks_mobile`, Kotlin Multiplatform) have zero shadow awareness: shadow panes are
dropped at discovery (`monitor_core._parse_list_panes` ~line 1032,
`is_shadow_target(parts[8])`), so they never reach the roster, `pane_status` pushes,
or the binary data plane.

This is a **paired cross-repo plan** (`xdeprepo: aitasks_mobile`, confirmed by user).
The decomposition below spans this repo (applink server + protocol docs) and
`aitasks_mobile` (wire + mediator + UI). Tasks are created only after plan approval
via the Cross-Repo Child Assignment Procedure (local parent = t1118; a counterpart
parent is created in `aitasks_mobile`).

**Design decisions — ⚠ visibility/band choices below are best-judgment defaults
(AskUserQuestion timed out twice); they follow the user's stated concern ("read-only
would see AND STREAM shadow panes, not just harmless metadata") but need explicit
confirmation at approval:**

- **Visibility model: metadata for all, content gated.** Shadow panes appear in the
  roster and `pane_status` (binding/stale metadata) for ALL profiles, but shadow-pane
  **content streaming** requires `monitor_control`: for a `read_only` session, the
  `subscribe` verb excludes shadow panes from the effective `content_panes` set (and
  `request_keyframe`/`history` reject them via the existing `streams_content` /
  `not_content_pane` path). Status-only pushes for shadows remain (t1045
  roster-vs-content split does exactly this shape already).
- **Permission bands:** `spawn_shadow` → `full` (launches an agent; `spawn_tui`
  precedent); `shadow_concerns` → `monitor_control` (concern text is content-derived
  advisory analysis — coherent with the content gate above; NOT `read_only` as
  originally sketched); concern forwarding = client-composed `send_keys` into the
  FOLLOWED pane (`monitor_control`), no new verb — user-initiated, preserving the
  advisory-only model (the shadow itself never inputs into the followed pane).
- **No protocol `v` bump** — all changes additive per `protocol.md` §Versioning
  (mobile `pairJson` has `ignoreUnknownKeys=true`).
- **NOT coupled to t1011** (applink launch policy): shadow spawns with pure defaults;
  no launch-config screen exists even on desktop.

## Server-side architecture (this repo)

### D1 — Roster exposure: opt-in flag, desktop drop intact

The drop lives in `_parse_list_panes` (`monitor/monitor_core.py`), shared by all
consumers. Change:

- Add field `shadow_target: str = ""` to `TmuxPaneInfo` (monitor_core.py:234).
- Add `PaneCategory.SHADOW` enum member.
- Add constructor flag `include_shadow_panes: bool = False` to `TmuxMonitor`.
  In `_parse_list_panes`: flag False (desktop default) → current drop unchanged;
  True → keep the pane with `shadow_target=parts[8]`, `category=SHADOW`.
- Only the applink server's monitor instance passes `include_shadow_panes=True`
  (construction sites: `applink/applink_app.py`, `applink/headless.py`).
- Desktop TUIs behaviorally unchanged (default False). Negative-control test: with
  the flag off, a stamped shadow pane is still dropped.
- Audit downstream applink consumers for SHADOW-category safety: `_discover_pane_ids`
  (subscribe-all now includes shadows — intended for roster/status; content gated per
  profile, see D2b), `kill_agent_pane_smart` real-agent count (keys off the marker —
  verify unchanged), snapshot capture.

### D2 — New verbs (`applink/router.py` `_dispatch` + `IMPLEMENTED_COMMAND_VERBS`)

1. **`spawn_shadow`** — payload `{pane_id}` (the FOLLOWED agent pane). Gate `full`.
   - Validate `pane_id`: `_req_pane_id` (`^%\d+$`) + roster membership
     (`get_pane` / `_pane_cache`) — reject unknown panes (`BAD_PAYLOAD`).
   - One-shadow-per-agent guard: reverse-lookup existing shadow. **Extract the spawn
     body from `minimonitor_app.action_launch_shadow` (minimonitor_app.py:1046-1147)
     into a shared headless helper** (e.g. `spawn_shadow_for_pane` in `monitor_core.py`
     or `lib/agent_launch_utils.py`), covering: guard (`match_shadow_pane` pattern),
     task-id resolution, `resolve_dry_run_command(root, "shadow", ...)`,
     `TmuxLaunchConfig` placement policy (`tmux.shadow_same_window` /
     `shadow_pane_width`), `launch_in_tmux`, `@aitask_shadow_target` stamping,
     `attach_shadow_cleanup_hook`. Minimonitor's action becomes a thin caller —
     one canonical seam, two consumers.
   - Existing shadow → `err BAD_PAYLOAD detail:{reason:"shadow_exists", shadow_pane}`.
   - Response `{ok, shadow_pane}`. No shell interpolation of client input (pane_id is
     `%N`-validated; task_id resolved server-side). Not a two-phase confirm verb
     (non-destructive; `spawn_tui` precedent). Audit-log spawn attempts.
2. **`shadow_concerns`** — payload `{pane_id}` (the SHADOW pane). Gate
   `monitor_control`.
   - Validate: pane-id format + roster membership + `shadow_target` non-empty, else
     `BAD_PAYLOAD detail:{reason:"not_shadow_pane"}`.
   - Server-side **wrap-joined capture** (`capture-pane -J` — the concern parser's
     capture-join contract from `aidocs/framework/shadow_concern_format.md`; the data
     plane streams visually-wrapped rows, so client-side parsing would corrupt long
     concerns) + `monitor/concern_parser.parse_concerns` reuse (forgiving variant —
     explicit user action).
   - Response `{concerns:[{priority, region, body}], followed_pane,
     analyzed_at: epoch|null, stale: bool}` — staleness computed server-side, same
     compare as minimonitor `_update_shadow_freshness`
     (`get_pane_option(shadow, SHADOW_ANALYZED_AT_OPTION)` vs
     `get_last_change_wall(followed)` + refresh-tick epsilon).

**D2-inv — Non-stamping invariant (NON-NEGOTIABLE, both verbs + D3):** passive
server-side inspection must NEVER write `@aitask_shadow_analyzed_at`. Only the
shadow's own read of the followed pane (via `aitask_shadow_capture.sh` running
inside the shadow pane) stamps. Therefore all applink capture paths (D2.2 RPC and
D3 status detection) use raw gateway `capture-pane -J` directly — they must NOT
shell out to `aitask_shadow_capture.sh`. Otherwise status polling would mark advice
fresh merely because the server inspected the shadow, suppressing stale warnings in
the exact scenario the feature exists to expose. Negative-control test: run a
status tick + a `shadow_concerns` call against a stamped shadow pane; assert the
`@aitask_shadow_analyzed_at` value is byte-identical before/after.

### D2b — Content gating for shadow panes (profile-aware)

For `read_only` sessions, shadow panes are status-only: `subscribe` filters shadow
panes out of the effective `content_panes` set (router has `conn.session.profile`);
`request_keyframe`/`history` already reject non-content panes
(`not_content_pane` / `not_subscribed`) so they need no new logic once the filter is
in place. `monitor_control`+ streams shadow content like any pane. Roster + status
pushes unaffected by profile (except the D3 field-level split).

**Capability flags (server-owned truth for client gating):** the `pair` / `resume`
response payload gains two additive fields the client gates UI off — never
profile-name ordering:
- `allowed_verbs: [...]` — the session profile's verb list (the server already
  holds it in the gate; `applink/profiles.py`).
- `caps: {shadow_content: bool}` — mirrors the D2b content-gating decision (true
  for `monitor_control`+).
Old clients ignore the new fields; new clients degrade gracefully when absent
(fields nullable → fall back to hiding shadow affordances).

### D3 — `pane_status` additive fields (`applink/pusher.py` `_send_pane_status`)

- On SHADOW panes: `shadow_target: "%N"` (their binding; also lets the client
  distinguish shadow panes in the roster without string heuristics).
- On FOLLOWED panes with a bound shadow: `shadow_pane: "%N"`, `shadow_stale: bool`,
  `shadow_analyzed_at: epoch|null`, `shadow_has_concerns: bool` (strict
  `has_concern_block` — parity with minimonitor's auto-offer trigger; client de-dups).
- Absent on panes without shadows — old clients ignore unknown keys.
- **Field-level profile split (metadata-only coherence):** binding and staleness
  fields (`shadow_target`, `shadow_pane`, `shadow_stale`, `shadow_analyzed_at`)
  derive from pane options + change timestamps — content-free metadata, pushed to
  ALL profiles. `shadow_has_concerns` is **content-derived** (parsed from shadow
  pane content) and is **suppressed for `read_only` sessions**: `PushScheduler` is
  per-connection and knows the session profile, so the field is added only when the
  connection's profile grants `shadow_concerns` (`monitor_control`+). Test: a
  read_only connection's `pane_status` lacks the field while a monitor_control
  connection's includes it, same tick.

**D3-cost — Concern-detection cost contract (explicit, testable):**
- **Change-gated:** re-capture + re-parse a shadow pane only when its content changed
  since the last verdict — gate on monitor_core's existing per-pane change tracking
  (`_last_change_time` / `get_last_change_wall`), which the tick already maintains.
  Unchanged content ⇒ serve the cached verdict, zero capture, zero parse.
- **Depth-capped:** detection capture is `capture-pane -J` limited to the last 200
  lines (the `aitask_shadow_capture.sh` default depth) — never full scrollback. The
  concern block is emitted at the end of a review; 200 tail lines is the same budget
  the desktop auto-offer effectively scans.
- **Shared per-pane, not per-connection:** `PushScheduler` is per-connection; the
  verdict cache must live on a shared layer keyed by `pane_id` (e.g. a small
  `ShadowStatusCache` on/next to the shared `TmuxMonitor` instance holding
  `(last_change_marker, has_concerns, analyzed_at, payload_hash)`), so N subscribers
  cost one capture+parse per content change, not N.
- **Stamp reads are cheap** (`show-options -pqv`) and ride the same change gate.
- **Tests:** parse-call spy — two status ticks over unchanged shadow content parse
  exactly once; content change triggers exactly one re-parse; two concurrent
  connections share one parse; capture call asserts the depth cap argument.

### D4 — send_keys `paste` mode (forwarding support)

Multi-line forwarding via `send_keys -l` would submit each embedded newline as
Enter in most agent CLIs — unlike desktop clipboard paste (bracketed). Add an
**additive optional `paste: bool` field to the existing `send_keys` verb** (default
false → behavior unchanged): when true, the server delivers the text via tmux
`load-buffer` (stdin, no shell interpolation) + `paste-buffer -p -d -t <pane>`
(bracketed paste, buffer deleted). Same `monitor_control` gate, same `_MAX_STR`
bound. This makes mobile forwarding **stage-only**: text lands in the agent's input
unsubmitted; the user reviews and presses Enter explicitly (KeyForwarderBar).
Implemented in monitor_core (new `paste_text(pane_id, text)` beside `send_keys`,
gateway-routed) + router flag + docs. Tests: router flag routing; paste_text unit
test (gateway spy: load-buffer stdin + `-p` flag); multi-line payload arrives
without submitting; **regression: `send_keys` with `paste` absent or `false`
dispatches byte-for-byte identically to today (StubMonitor records unchanged
`send_keys(pane_id, keys, literal)` call, no buffer commands)** — the shared-verb
blast radius is guarded, not assumed.

### D5 — Docs + profiles (t822_12 sync pattern — all agreeing surfaces together)

- New `aidocs/applink/shadow_driving.md`: roster-exposure + content-gating decision,
  verb payload schemas, permission gating, `pane_status` extensions **incl. the
  field-level profile split** (`shadow_has_concerns` = content-derived, suppressed
  below monitor_control), the capability flags (`allowed_verbs` /
  `caps.shadow_content` on pair/resume), the non-stamping invariant (D2-inv), the
  cost contract (D3-cost), `paste` mode, advisory-only invariant, staleness
  semantics. Cross-refs from `monitor_port_design.md` + `protocol.md`.
- `monitor_port_design.md`: add canonical verb-table rows (+ `send_keys` payload
  gains `paste?:bool`).
- `permissions.md`: gating rows (`spawn_shadow`→full,
  `shadow_concerns`→monitor_control).
- `aitasks/metadata/applink_profiles/*.yaml`: `shadow_concerns` in
  `monitor_control.yaml` + `full.yaml`; `spawn_shadow` in `full.yaml` — **and** the
  in-code fallback `applink/profiles.py:DEFAULT_ALLOWED` in the same commit
  (parallel surfaces).

## Mobile-side architecture (aitasks_mobile)

Established extension seam per feature (greenfield for shadow):

- **Wire** (`domain/.../applink/wire/ControlFrames.kt`): `SpawnShadowPayload{pane_id}`,
  `ShadowConcernsReq{pane_id}`, `ShadowConcernsRes{concerns:[ConcernWire{priority,
  region, body}], followed_pane, analyzed_at?, stale}`; `SendKeysPayload` gains
  `paste: Boolean = false`; `PaneStatusPush` gains nullable-with-default
  `shadow_target`, `shadow_pane`, `shadow_stale`, `shadow_analyzed_at`,
  `shadow_has_concerns`.
- **Mediator** (`MonitorSessionMediator.kt`): `spawnShadow(paneId)` (sendKeys-shaped),
  `shadowConcerns(paneId): Result<ShadowConcerns>` (taskDetail-shaped typed decode);
  `sendKeys` gains the paste flag. `PaneStatus` domain + `toDomain` extended.
- **Persistence contract (pinned here — B1 and B2 implement against it, no local
  re-decision):**
  - **Persisted (stable binding):** `shadow_target` (on shadow panes) and
    `shadow_pane` (on followed panes) go into `PaneStatusDBO` as nullable columns +
    mapper + Room `AutoMigration` (title v4→v5 precedent). Bindings survive
    reconnect so the pane list can render shadow structure immediately.
  - **Transient (volatile):** `shadow_stale`, `shadow_analyzed_at`,
    `shadow_has_concerns` never touch Room. They ride the existing `paneStatuses`
    flow into an in-memory ScreenModel map keyed by `pane_id`; on
    reconnect/screen-recreate they reset to unknown and stale/concern badges stay
    hidden until the first fresh push. (Stable-handle vs mutable-state split; avoids
    DB churn at status cadence and stale-badge lies from cached state.)
- **Capability gating (pinned — no profile-name ordering):** the session stores the
  `pair`/`resume` response's additive `allowed_verbs` + `caps.shadow_content`
  (nullable; absent ⇒ shadow affordances hidden). UI gates: spawn button ⇔
  `"spawn_shadow" ∈ allowed_verbs`; concern picker ⇔ `"shadow_concerns" ∈
  allowed_verbs`; shadow content viewing ⇔ `caps.shadow_content`. The existing
  `canControl` string check stays for legacy surfaces but no NEW shadow gate may
  compare profile names — the server is the single owner of the permission
  decision.
- **UI** (`shared/.../monitor/`): spawn-shadow action on a followed agent pane
  (pane-row menu / app-bar action, gated per capability flags above); shadow pane
  rows in `PaneListPanel` with a shadow badge (AssistChip pattern,
  PaneListPanel.kt:210) + stale badge on the followed row; shadow pane viewable via
  existing `PaneContentViewer` + `KeyForwarderBar` when `caps.shadow_content`
  (otherwise the row shows status-only, no content stream — matches server gate);
  `ConcernPickerSheet` modeled on `TaskDetailSheet` (sealed Loading/Loaded/Error,
  ModalBottomSheet) with multi-select rows, priority/region chips, stale red banner,
  de-dup on `shadow_has_concerns` transitions.
- **Forwarding semantics (pinned):** "Forward" composes the selected concerns using
  the desktop `build_clipboard_payload` text format **verbatim** and sends it via
  `sendKeys(followedPane, text, literal=true, paste=true)` — **stage-only, never
  auto-submits**; the user reviews the staged text in the followed pane's viewer and
  presses Enter via `KeyForwarderBar`. Tests: fake-client test asserts the exact
  staged payload, `paste=true`, and no trailing Enter/`forward_key` call.
- **DI**: extend the `MonitorScreenModel` factory in `AppKoinModule.kt:115`.

## Paired decomposition (authoritative for both repos)

Local parent: **t1118** (this repo). Cross-repo parent (to create in
`aitasks_mobile`): **"Shadow-agent driving over applink (mobile side)"** — labels
`[applink, shadow]`.

| Label | Side | Nominal parent | In-repo deps | Cross-repo deps | issue_type | Title / description |
|-------|------|----------------|--------------|-----------------|------------|---------------------|
| A1 | local | t1118 | — | — | documentation | **Shadow-driving protocol design doc** — author `aidocs/applink/shadow_driving.md` (D5 content list incl. D2-inv non-stamping invariant, D3-cost contract, D2b content gating, `paste` mode); verb rows in `monitor_port_design.md` + `permissions.md` (marked "implementation pending"); cross-ref from `protocol.md`. Defines the wire contract both repos build against. |
| A2 | local | t1118 | A1 | — | feature | **Shadow-aware roster + content gating + capability flags** — `TmuxPaneInfo.shadow_target`, `PaneCategory.SHADOW`, `TmuxMonitor(include_shadow_panes=False)` opt-in consumed in `_parse_list_panes`; applink constructs with `True`; `pusher._send_pane_status` emits `shadow_target` on shadow panes; D2b profile-aware `content_panes` filter for read_only; `pair`/`resume` response gains additive `allowed_verbs` + `caps.shadow_content`. Desktop drop semantics intact (negative-control test); downstream-consumer audit. Tests: parse flag on/off, pusher field, subscribe-all includes shadows, read_only content filter + keyframe rejection, pair-response caps per profile. |
| A3 | local | t1118 | A2 | — | feature | **`spawn_shadow` verb + shared spawn helper** — extract minimonitor `action_launch_shadow` body into a shared headless helper (guard, task resolution, dry-run command, placement config, launch, stamp, cleanup hook); minimonitor becomes thin caller; router verb (full-gated, roster-validated, audit-logged, `shadow_exists` error); `full.yaml` + `DEFAULT_ALLOWED` + permissions.md row live. Tests: router validation/gating/guard via StubMonitor; helper unit test with construction spies; minimonitor regression. |
| A4 | local | t1118 | A2 | — | feature | **`shadow_concerns` RPC + shadow status fields + `paste` mode** — monitor_control-gated verb: raw gateway wrap-joined capture (NOT via `aitask_shadow_capture.sh` — D2-inv) + `parse_concerns` reuse + server-side staleness verdict; `pane_status` gains `shadow_pane`/`shadow_stale`/`shadow_analyzed_at`/`shadow_has_concerns` per the D3-cost contract (change-gated, depth-capped 200, shared per-pane cache; `shadow_has_concerns` suppressed for read_only per D3 field split); `send_keys` `paste:bool` via `load-buffer`+`paste-buffer -p` (`paste_text` in monitor_core); profile yamls + `DEFAULT_ALLOWED`. Tests: verb happy/not-shadow paths, staleness cases, **non-stamping negative control**, parse-call-count/cost spies, paste routing + gateway spy, **no-paste byte-for-byte send_keys regression**, read_only-vs-monitor_control field-split test. |
| B1 | cross-repo | mobile parent | — | A1 | feature | **Shadow wire + mediator layer** — `ControlFrames.kt` payloads (`SpawnShadowPayload`, `ShadowConcernsReq/Res`, `ConcernWire`), `SendKeysPayload.paste`, `PaneStatusPush` additive nullable fields; pair/resume response parsing for `allowed_verbs` + `caps.shadow_content` (nullable, stored on session); error mapping for `shadow_exists`/`not_shadow_pane`; mediator `spawnShadow`/`shadowConcerns` + paste-aware `sendKeys`; **persistence contract as pinned in parent plan**: `shadow_target`/`shadow_pane` → DBO+mapper+AutoMigration; stale/analyzed_at/has_concerns transient-only. Tests: serialization round-trips (incl. absent caps → null), mediator verb + push routing via `FakeMonitorStreamClient`, mapper/migration. |
| B2 | cross-repo | mobile parent | B1 | A3, A4 | feature | **Shadow UI: spawn, viewer, concern picker, staleness** — spawn action + concern picker + shadow content viewing gated **off the explicit capability flags** (`allowed_verbs`, `caps.shadow_content`) per pinned contract — never profile-name ordering; shadow + stale badges; shadow viewing via `PaneContentViewer`/`KeyForwarderBar`; `ConcernPickerSheet` (TaskDetailSheet template; multi-select, chips, stale red banner, has_concerns de-dup); **forwarding = stage-only** `sendKeys(followed, build_clipboard_payload-format, literal=true, paste=true)`, user submits via Enter. Transient shadow-state map in ScreenModel per pinned contract. Tests: extracted decision fns incl. capability-gate cases (absent caps hides affordances); fake-client forwarding assertions (payload verbatim, paste=true, no auto-Enter). |
| A5 | local | t1118 | A3, A4 | B2 | manual_verification | **End-to-end manual verification** — pair a real device: shadow visible; metadata-for-all/content-gated model verified per profile (read_only: binding/stale badges yes, `shadow_has_concerns` and content stream no); spawn from app (full) incl. `shadow_exists` rejection; concern picker with real parsed concerns; **stale banner appears when followed agent moves on AND passive status polling does not clear it** (D2-inv live check); multi-line concern forwarded via paste mode arrives staged, unsubmitted; desktop minimonitor `e`/`c` unregressed; shadow auto-cleanup reflected in roster. |

Sequencing: A1 → A2 → {A3, A4} in this repo; B1 (after A1) → B2 (after A3/A4) in
`aitasks_mobile`; A5 last. Cross-repo deps recorded symbolically; real IDs wired at
creation (Cross-Repo Child Assignment Procedure, Step 7).

## Reused existing code (do not reinvent)

- `monitor/concern_parser.py` — `parse_concerns`, `has_concern_block` (pure, tested).
- `lib/agent_launch_utils.py` — `resolve_dry_run_command`, `launch_in_tmux`,
  `TmuxLaunchConfig`, `attach_shadow_cleanup_hook`.
- `minimonitor_app.py` — `match_shadow_pane`, `_update_shadow_freshness` logic
  (ported/extracted, not duplicated).
- `monitor_core.py` — `get_pane_option`, `get_last_change_wall`,
  `SHADOW_TARGET_OPTION`, `SHADOW_ANALYZED_AT_OPTION`, `_pane_cache` roster checks,
  per-pane change tracking (`_last_change_time`) for the D3 change gate.
- Router `_req_pane_id` / `_bad_field` / audit patterns; `spawn_tui` allowlist
  precedent; t1045 roster-vs-content split (`streams_content`) for D2b;
  `tests/test_applink_router.sh` StubMonitor harness.
- Mobile: `TaskDetailSheet` sheet template, `sendKeys`/`taskDetail` mediator shapes,
  `FakeMonitorStreamClient` test harness, AssistChip badge pattern, Room
  AutoMigration precedent (title v4→v5).

## Verification

- Per-child tests as listed in the table (bash StubMonitor router tests, pusher
  emission/cost tests, Python parse tests; Kotlin `:domain:test` / `:shared` host
  tests, `./gradlew check`).
- Negative controls: desktop flag-off shadow drop; non-stamping invariant
  (analyzed_at unchanged by status tick + RPC).
- Cost: parse-call-count spies per D3-cost.
- `shellcheck` on any touched `.sh`.
- A5 manual-verification child covers the live end-to-end (device + real tmux).
- Step 9 (Post-Implementation) per task-workflow: gates run, archival, `./ait git push`.

## Risk

### Code-health risk: medium
- `_parse_list_panes` opt-in flag touches the single shared discovery path used by
  every TUI; a regression would surface shadows in desktop kill/sibling logic ·
  severity: medium · → mitigation: A2's negative-control test (flag off ⇒ drop
  unchanged) + downstream-consumer audit within A2.
- Extracting `action_launch_shadow` into a shared helper could regress the desktop
  spawn flow (placement config, cleanup hook ordering) · severity: medium ·
  → mitigation: A3 keeps minimonitor as thin caller with regression test +
  construction-spy unit test; A5 re-verifies desktop `e` flow live.
- Periodic concern detection could make the push loop sluggish with several bound
  shadows / subscribers even without extra tmux round-trips (parse cost) ·
  severity: medium · → mitigation: D3-cost contract (change-gated, depth-capped,
  shared per-pane cache) + parse-call-count tests in A4.

### Goal-achievement risk: medium
- Passive server inspection stamping `@aitask_shadow_analyzed_at` would suppress
  stale warnings — defeating the feature's core purpose · severity: high ·
  → mitigation: D2-inv structural rule (raw gateway capture only, never
  `aitask_shadow_capture.sh`) + negative-control test in A4 + A5 live check.
- Concern parsing correctness depends on the wrap-join (`-J`) capture contract; a
  non-joined capture silently corrupts long concerns · severity: medium ·
  → mitigation: A4 unit test feeds wrapped fixture text through the server capture
  path; A5 verifies with a real long concern.
- Forwarding via literal `send_keys` would auto-submit each newline in most agent
  CLIs — desktop clipboard flow has no such hazard · severity: medium ·
  → mitigation: D4 `paste` mode (bracketed paste, stage-only) + fake-client
  no-auto-Enter test in B2 + A5 live multi-line check.
- Cross-repo contract drift (server payloads vs Kotlin wire types) · severity: low ·
  → mitigation: A1 doc is the single contract; B1 serialization tests mirror the
  documented schemas.

(No separate before/after mitigation tasks — every mitigation above is embedded in
the decomposition's own children, incl. the A5 manual-verification child. Confirmed
"No mitigations" default after AskUserQuestion timeout.)

## Post-approval workflow references

- Step 7: Cross-Repo Child Assignment Procedure creates the `aitasks_mobile`
  counterpart parent + all children (A1–A5, B1–B2) with plans, wires symbolic deps
  to real IDs, demotes t1118 to parent-of-children.
- Step 9 (Post-Implementation) applies per child on pick-up.
