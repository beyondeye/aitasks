---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-11 10:42
updated_at: 2026-06-16 17:26
---

Sync the canonical verb inventory from `aidocs/applink/monitor_port_design.md` back into `aidocs/applink/permissions.md` (verb gating table) and align the shipped `applink_profiles/*.yaml` allowed_verbs lists.

## Context

Seventh §"Deferred follow-up tasks" bullet of `aidocs/applink/monitor_port_design.md`. The permissions.md verb gating table is the t822_1 **seed**; t822_3 produced the canonical inventory and recorded the discrepancies explicitly in its §Permission profile cross-check rather than silently fixing them. This task pays that down. Doc + metadata YAML only — no listener code.

## Discrepancies to resolve (from monitor_port_design.md §Permission profile cross-check)

- Add `forward_key` (gate: monitor_control) — and update/remove the seed table's interim note telling clients to send literal escape sequences.
- Add `pick_next_sibling`, `restart_task` (gate: full; flag mobile execution as deferred if still true at pick time). **NOTE (t822_11 landed 2026-06-16):** the modal-handshake task already added both verbs to `applink_profiles/full.yaml` **and** to `profiles.py` `DEFAULT_ALLOWED["full"]` (the no-config fallback). So this task only needs to mirror them into `permissions.md`'s gating table — the YAML/fallback alignment for these two is done. Their execution is still deferred (`NOT_IMPLEMENTED`), so keep the "mobile execution deferred" flag.
- Add `task_detail` (gate: read_only).
- `rename_session` — add a row only if implemented by then; otherwise keep desktop-only note.
- Move `kill_pane`'s call-site citation from raw `kill_pane` to `kill_agent_pane_smart`.
- Refresh the stale line refs in permissions.md's table intro (`tmux_monitor.py:585-720`, `monitor_app.py:1489`) — re-verify against current files at pick time; prefer symbol names over bare line numbers where the doc style allows.

## Key Files to Modify

- `aidocs/applink/permissions.md` — verb gating table + notes.
- `aitasks/metadata/applink_profiles/{read_only,monitor_control,full}.yaml` — if they exist by then (shipped by the listener task t822_7), extend `allowed_verbs` to match; if not yet shipped, record that in the plan and skip.

## Reference Files

- `aidocs/applink/monitor_port_design.md` — §Command verb → applink protocol mapping (source of truth), §Permission profile cross-check
- `aidocs/applink/permissions.md` — target

## Cross-repo contract note (from t822_9, applink delta engine)

t822_9 pinned two `delta` (0x02) wire conventions in `content_transport.md` §delta
that the mobile decoder in `../aitasks_mobile` must match (server is authoritative
per design goal 5): (1) `osc8` sidecar offsets are row-major over the **delta's own
`rows` array** (changed rows only), not the full grid; (2) a row with an **empty
spans array** (`[row_id, []]`) **clears that row to blank**. Surface these in the
mobile decoder contract when syncing — if mobile began parsing `osc8` under a
different assumption, reconcile to the pinned spec.

## Cross-repo contract note (from t822_10, applink append fast path)

t822_10 pinned the `append` (0x03) conventions in `content_transport.md` §append
that the mobile decoder must match: `append` carries **no cursor** (the client
keeps the cursor from the previous frame — the server only appends when the cursor
is unchanged) and **no `osc8` sidecar** (the server emits a `delta` instead when an
appended row has a hyperlink, so `append` rows never set the OSC8 attr bit); the
appended rows carry their **new absolute `row_id`s** (`rows-k … rows-1`) and the
client **adopts the append's `frame_id` as its current frame_id** so a following
`delta`'s `prev_frame_id` chains. Surface these in the mobile decoder contract when
syncing.

## Verification Steps

- Every verb in monitor_port_design.md's table appears in permissions.md's table with the same gate, and vice versa (no orphans either direction).
- Each profile YAML's `allowed_verbs` equals the set of ✓ verbs for its column (when YAMLs exist).
- Cross-reference links between the two docs still resolve.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-16T14:26:28Z status=pass attempt=1 type=human
