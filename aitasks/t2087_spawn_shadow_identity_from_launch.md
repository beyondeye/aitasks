---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [aitask_monitormini, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2073
followup_kind: upstream_defect
created_at: 2026-10-21 08:43
updated_at: 2026-10-21 08:48
---

## Origin

Spawned from t2073_4 during Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py:spawn_shadow` (~:4040-4070) — `spawn_shadow` resolves its new pane by pid (`resolve_pane_id_by_pid`), whose `None` merges "query failed" with "pane gone". A failure there leaves a live, unstamped shadow that lists as an agent. The same hole was fixed in t2073_4 for the scratchpad with `launch_split_pane` and identity-gated recovery.

## Diagnostic context

t2073_4 (the minimonitor `o` scratchpad spawn) mirrored `spawn_shadow`. Plan review found that `launch_in_tmux` returns only a pid, and that `resolve_pane_id_by_pid` returns `None` both when `list-panes` fails (gateway `(-1, "")` on timeout or transport failure) and when no pane has the pid. On that `None`, `spawn_shadow` only warns ("Shadow launched, but its pane could not be classified") and returns. A live shadow pane is left WITHOUT `@aitask_shadow_target`, so:

- it is discovered as an agent;
- the duplicate guard (`find_shadow_pane_status`) cannot see it, so a second press opens a second shadow;
- the cleanup hook never kills it when its agent dies.

t2073_4 added, and its tests pin:

- `agent_launch_utils.launch_split_pane(command, config) -> (pane_id, pid, err)`: `split-window -P -F '#{pane_id}\t#{pane_pid}'`, each field validated independently, argv shared with `launch_in_tmux` via `_split_window_argv`;
- `monitor_core._recover_pad_pane(monitor, pid)`: bounded (3 tries), identity-gated. It reports "exited" only from a valid pid AND a well-formed rc=0 listing, and "unknown" otherwise;
- `monitor_core._probe_pane` (live/gone/unknown) and `_stamp_or_remove` (ok/exited/removed/stuck). The rules: an empty output proves nothing unless rc == 0, and "removed" is reported only when a second probe proves the pane gone.

## Suggested fix

Move `spawn_shadow`'s same-window split branch onto `launch_split_pane`, and reuse `_recover_pad_pane` / `_stamp_or_remove`, generalized (renamed to helper-neutral names) for its stamp. The separate-window branch (`new_window=True`) needs the same identity: either add a `new-window -P -F '#{pane_id}\t#{pane_pid}'` sibling, or recover by pid with the same unknown ≠ gone rule. Add the matching mocked regressions to `tests/test_monitor_shadow_pick.py` / `tests/test_minimonitor_shadow_pick.py`.
