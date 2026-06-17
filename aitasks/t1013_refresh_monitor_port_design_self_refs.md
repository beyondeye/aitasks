---
priority: low
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [ait_bridge]
created_at: 2026-06-16 17:35
updated_at: 2026-06-16 17:35
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
