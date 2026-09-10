---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation, web_site]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1657
followup_kind: upstream_defect
implemented_with: claudecode/opus5
created_at: 2026-09-10 12:45
updated_at: 2026-09-10 15:39
---

## Origin

Spawned from t1657_6 during Step 8b review.

## Upstream defect

- `docs/README.md:30 — links skills/aitask-pick.md, which is now the directory skills/aitask-pick/_index.md`
- `docs/README.md:26 — links workflows/terminal-setup.md, which now lives under installation/terminal-setup`
- `docs/README.md:43-47 — the commands block omits most command pages (lock, gates, sync, explain, codeagent, crew, pr-import, note)`

## Diagnostic context

t1657_6 added an `/aitask-note` row to `docs/README.md`'s single index table
(`Guide | Source File | Description`). Locating the insertion point showed the
table is stale in three ways. `docs/README.md` is not part of the Hugo build, so
`website/check_links.py` never sees it — which is how these links went dead
without anything failing.

The two broken rows point at paths that moved: `skills/aitask-pick.md` became
the directory `skills/aitask-pick/_index.md`, and the terminal-setup page moved
under `installation/` (the site links it as `installation/terminal-setup/`).
The commands block lists only `_index`, `setup-install`, `task-management`,
`board-stats` and `issue-integration`, omitting every other page under
`website/content/docs/commands/`.

Line numbers are as of commit 0e5b965fa (after t1657_6's one-row insertion).

## Suggested fix

Repoint the two moved rows and add rows for the missing command pages — or
decide the table should list sections rather than individual pages. Consider a
small guard that resolves every relative link in `docs/README.md` against the
tree, since the site's link checker cannot reach this file.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-09-10T12:39:32Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-09-10T12:59:33Z status=pass attempt=1 type=human
