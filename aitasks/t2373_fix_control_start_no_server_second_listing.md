---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [monitor]
followup_kind: upstream_defect
created_at: 2026-11-27 01:43
updated_at: 2026-11-27 01:43
---

## Origin

Spawned from aitasks_go#t134 (the Go port of the `_ait_control` helper-session
attach into `goengines/tmux`) during its Step 8b review.

## Upstream defect

- `.aitask-scripts/monitor/monitor_core.py` `TmuxControlClient._start_pass` /
  `_server_is_gone`: after a failed start listing, "no server" is established
  by a SECOND `list-sessions` (`_server_is_gone` runs `run_checked` again). A
  tmux server that comes back between the two calls erases the first call's
  no-server observation, so `lost_project` stays empty after a real outage and
  the supervisor raises no `exit_seen`.

## Diagnostic context

The Go port first mirrored this two-call shape. The t134 reviewer showed it
with a seam: the first subprocess answered "no server", the second returned a
session listing, and the start reported an empty loss reason despite the
observed outage. The Go port now classifies the ONE listing that failed
(`RunChecked`: `Outcome == no_server`) and asks nothing a second time. The
Python side was not reproduced directly; this is the same structure, by
inspection, as of aitasks main 46b34ee2f.

## Suggested fix

Make `_inspect` use `run_checked` and return the no-server outcome alongside
the rows, then drop the second probe in `_server_is_gone` (keep the
"transport is not absence" rule: only tmux's own no-server answer counts).
Add a test with a gateway stub whose first listing says no server and whose
second would succeed.
