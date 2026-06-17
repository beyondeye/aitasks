---
priority: low
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: documentation
status: Implementing
labels: [ait_bridge]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-06-16 17:35
updated_at: 2026-06-17 12:02
boardidx: 80
---

## Origin

Spawned from t822_12 during Step 8b review. t822_12 synced
`aidocs/applink/permissions.md` (the profile-gating table) into agreement with
the canonical verb inventory in `aidocs/applink/monitor_port_design.md`. While
doing so it surfaced two now-stale self-references inside the **canonical** doc
itself — out of scope for the seed→canonical sync, recorded here as a small
documentation follow-up.

## Upstream defect

- `aidocs/applink/monitor_port_design.md:61 — §Command verb intro still calls permissions.md the "seed table … which predates forward_key, pick_next_sibling, restart_task"; after t822_12's sync permissions.md no longer lacks those verbs, so the parenthetical is historically-stale. Reword to reflect that permissions.md is now the in-sync profile-band view.`
- `aidocs/applink/monitor_port_design.md:67-78 — the canonical §Command verb table's own call-site line numbers are stale post-t822_6 (monitor_core extraction): tmux_monitor.py:526 (capture_all), monitor_shared.py:311 (TaskInfoCache._resolve), tmux_monitor.py:552/556/569/643, etc. Those symbols now live in .aitask-scripts/monitor/monitor_core.py. Refresh to monitor_core.py / monitor_app.py with symbol names (prefer symbols over bare line numbers, as t822_12 did for permissions.md).`

## Diagnostic context

During t822_12, exploration found the t822_6 monitor_core extraction had moved
the entire monitor command surface (capture_all, send_*, switch_to_pane, kill_*,
spawn_tui, cycle_compare_mode, TaskInfoCache, _TEXTUAL_TO_TMUX) from
`tmux_monitor.py`/`monitor_shared.py` into `monitor_core.py`. permissions.md was
updated to cite the new symbols; monitor_port_design.md was left untouched to
keep t822_12 scoped, but its own citations have the same staleness.

## Suggested fix

Reword the §Command verb intro parenthetical (no longer "predates"), and rewrite
the table's "Existing call site" column to `monitor_core.py`/`monitor_app.py`
symbol references. Mirror the citation style t822_12 established in permissions.md.
Verify: `grep -n 'tmux_monitor.py:\|monitor_shared.py:' aidocs/applink/monitor_port_design.md` → empty.

## Scope (expanded 2026-06-17 — accepted by user during planning)

The two-bullet "Upstream defect" list above was the original framing. During
planning it became clear the staleness is **doc-wide**, not confined to those
two spots, and the verify (`grep → empty`) is only achievable by refreshing the
whole doc. With user approval the scope was expanded to a **full
post-extraction refresh** of `monitor_port_design.md` (no longer low effort):

- Convert every fragile `path:line` citation to drift-proof **symbol-form**
  (mirroring t822_12 / permissions.md), repointing the moved symbols to
  `monitor_core.py` (and launch orchestration to its real homes
  `agent_command_screen.py` / `lib/agent_launch_utils.py`).
- Flip the "(future)/deferred" framing for the now-landed `monitor_core`
  extraction: §Headless-core header + Source table, the tmux-gateway
  delegation prose, and the §Deferred follow-up bullets that landed
  (extraction t822_6/t822_7; permissions sync t822_12).
- Original defects 1 & 2 (intro parenthetical, verb table) are included.

Broadened verify (both → empty):
`grep -nE '[a-z_]+\.py:[0-9]' aidocs/applink/monitor_port_design.md` and
`grep -n 'tmux_monitor.py:\|monitor_shared.py:' aidocs/applink/monitor_port_design.md`.

Out of scope: landed-status of the remaining applink follow-ups (WS listener,
delta engine, append, handshakes, applink-mode flag) — not verified; left
deferred. No code changes; permissions.md/profiles untouched (that was t822_12).

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-06-17T09:02:13Z status=pass attempt=1 type=human

> **✅ gate:risk_evaluated** run=2026-06-17T09:02:14Z status=pass attempt=1 type=machine
