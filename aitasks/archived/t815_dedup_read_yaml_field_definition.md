---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [aitask_pick]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7
created_at: 2026-05-20 10:19
updated_at: 2026-05-20 11:19
completed_at: 2026-05-20 11:19
---

## Origin

Spawned from t813 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/agentcrew_utils.sh:89 — read_yaml_field is a second,
  independent definition that collides with
  .aitask-scripts/lib/task_utils.sh:282; whichever lib is sourced last
  silently wins, a latent footgun beyond t813's scope.`

## Diagnostic context

`aitask_archive.sh` sources `task_utils.sh` first and `agentcrew_utils.sh`
second, so the `agentcrew_utils.sh` copy of `read_yaml_field` shadows the
`task_utils.sh` copy at archive time. While implementing t813 (fixing
multi-line YAML flow-list parsing), the `task_utils.sh::read_yaml_field` fix
alone left a test failing — the archive path was still calling the unfixed
`agentcrew_utils.sh` copy. Both copies were fixed in t813, but the underlying
duplication remains: two functions with the same name, identical intent, and
no guard — any future edit to one silently diverges from the other depending
on source order.

The same risk likely applies to other helpers — `read_yaml_list` currently
lives only in `agentcrew_utils.sh`, but the two libs should be audited for
other name collisions.

## Suggested fix

Keep a single canonical `read_yaml_field` (and any other duplicated YAML
helpers) in one lib — `task_utils.sh` is the natural home — and have
`agentcrew_utils.sh` either source it or drop its copy. If `agentcrew_utils.sh`
must stay standalone (it is sourced without `task_utils.sh` by crew scripts),
extract the shared YAML readers into a small dedicated lib both can source.
Add a double-source guard / collision check. Verify `aitask_archive.sh` and
the crew scripts still resolve the function after the change.
