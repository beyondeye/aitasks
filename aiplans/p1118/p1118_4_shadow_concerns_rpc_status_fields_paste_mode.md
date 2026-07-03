---
Task: t1118_4_shadow_concerns_rpc_status_fields_paste_mode.md
Parent Task: aitasks/t1118_mobile_shadow_agent_driving_over_applink.md
Sibling Tasks: aitasks/t1118/t1118_1_*.md, aitasks/t1118/t1118_2_*.md, aitasks/t1118/t1118_3_*.md, aitasks/t1118/t1118_5_*.md
Archived Sibling Plans: aiplans/archived/p1118/p1118_*_*.md
Worktree: aiwork/t1118_4_shadow_concerns_rpc_status_fields_paste_mode
Branch: aitask/t1118_4_shadow_concerns_rpc_status_fields_paste_mode
Base branch: main
---

# Plan: `shadow_concerns` RPC + shadow status fields + paste mode (t1118_4)

Implements parent-plan D2.2 + D2-inv + D3 + D3-cost + D4. Contract:
`aidocs/applink/shadow_driving.md`. Parallel to t1118_3 (depends only on
t1118_2).

## NON-NEGOTIABLE invariants

- **D2-inv:** passive inspection NEVER writes `@aitask_shadow_analyzed_at`.
  All captures here use the raw gateway (`capture-pane -J`) — never shell out
  to `aitask_shadow_capture.sh` (it stamps when run inside a shadow pane).
- **D3-cost:** change-gated re-parse; 200-line depth cap; one capture+parse per
  content change shared across all connections.

## Wire contract (normative — from `aidocs/applink/shadow_driving.md` / t1118_1)

```json
{"verb":"shadow_concerns","payload":{"pane_id":"%15"}}          // SHADOW pane
// res:
{"payload":{"concerns":[{"priority":"high","region":"...","body":"..."}],
            "followed_pane":"%12","analyzed_at":1783158000,"stale":false}}
// analyzed_at: epoch seconds (float ok) or null when the shadow has not
// analyzed yet; stale=false when analyzed_at is null.
// err: BAD_PAYLOAD detail {"reason":"not_shadow_pane"} when the pane has an
// empty shadow_target.
{"verb":"send_keys","payload":{"pane_id":"%12","keys":"...","literal":true,
                                "paste":true}}   // paste optional, default false
```

## Steps

1. **monitor_core capture + verdict:**
   - `capture_pane_joined(pane_id, lines=200)` — gateway `capture-pane -p -J`
     with a `-S -200` style tail cap.
   - `shadow_staleness(shadow_pane, followed_pane)` — port the compare from
     minimonitor `_update_shadow_freshness` (~:1228): `analyzed_at =
     float(get_pane_option(shadow, SHADOW_ANALYZED_AT_OPTION))`,
     `last_change = get_last_change_wall(followed)`,
     `stale = last_change > analyzed_at + eps` (eps = max(2.0, refresh
     seconds)); absent stamp → `analyzed_at=None, stale=False`; malformed →
     treat as absent (failure-safe).
   - `paste_text(pane_id, text)` — `load-buffer -` (text via stdin, no shell
     interpolation) + `paste-buffer -p -d -t <pane>`; gateway-routed.
2. **`ShadowStatusCache`** (module in `applink/` or on the shared monitor):
   keyed by shadow `pane_id`, holds `(change_marker, has_concerns, analyzed_at,
   payload_hash)`. Recompute only when `get_last_change_wall(shadow_pane)`
   (or the pane's `_last_change_time` marker) moved; else serve cached.
   Strict `has_concern_block` for the flag (auto-offer parity).
3. **Router `shadow_concerns`** (`monitor_control` band): validate pane-id
   format + roster membership + non-empty `shadow_target` (else `BAD_PAYLOAD`
   `{"reason":"not_shadow_pane"}`); capture via step 1 helper (depth-capped),
   `concern_parser.parse_concerns` (forgiving); response `{concerns:[...],
   followed_pane, analyzed_at, stale}`.
4. **Router `send_keys` paste flag:** optional `paste: bool` (default false).
   False/absent → existing `monitor.send_keys(...)` call **unchanged
   byte-for-byte**; true → `monitor.paste_text(pane_id, keys)`. Same
   `monitor_control` gate and `_MAX_STR` bound.
5. **Pusher `_send_pane_status`:** on FOLLOWED panes with a bound shadow
   (binding map derived once per tick from the roster scan), add
   `shadow_pane`, `shadow_stale`, `shadow_analyzed_at`; add
   `shadow_has_concerns` **only when the connection's profile grants
   `shadow_concerns`** (field-level split — use the profile helper from
   t1118_2, one decision point). Values come from `ShadowStatusCache`.
6. **Profiles (same commit):** `shadow_concerns` in `monitor_control.yaml` +
   `full.yaml` + `DEFAULT_ALLOWED`; flip the `permissions.md` row; document
   `paste` in `monitor_port_design.md` row if t1118_1 marked it pending.

## Verification

- Router (StubMonitor): happy path; `not_shadow_pane`; `monitor_control`
  gating; paste routing; **no-paste regression** — StubMonitor records the
  identical `send_keys(pane_id, keys, literal)` call and no buffer commands.
- Staleness unit cases: fresh / stale / absent stamp / malformed stamp.
- **Non-stamping negative control:** stamped shadow pane; run a status tick +
  a `shadow_concerns` call; assert the stamp value is byte-identical.
- Cost spies: two ticks unchanged content ⇒ one parse; content change ⇒ one
  re-parse; two connections ⇒ one shared parse; capture carries the depth cap.
- Field split: read_only conn lacks `shadow_has_concerns`; monitor_control conn
  has it (same tick).
- `paste_text` gateway spy: load-buffer stdin + `-p` + `-d`; wrapped-fixture
  text through the capture path parses without corruption.
- Suites: `bash tests/test_applink_router.sh`, `bash tests/test_applink_pusher.sh`,
  `tests/test_concern_parser.py`, `tests/test_no_raw_tmux.sh`.

## Post-implementation

Step 9 (task-workflow): archive via `aitask_archive.sh 1118_4`, push.
