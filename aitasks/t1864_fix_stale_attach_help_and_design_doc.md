---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [documentation]
gates: [risk_evaluated]
anchor: 1687
followup_kind: upstream_defect
created_at: 2026-09-22 17:45
updated_at: 2026-09-22 17:45
---

## Origin

Spawned from t1687_2 during Step 8b review.

## Upstream defect

- `ait:51` — the dispatcher help line reads "Manage task file attachments (ls; add/get/rm/move/gc pending)", but add/get/rm/gc are shipped; only `move` is pending.
- `aidocs/task_attachments_design.md:396-397` — the §11 decomposition still lists "decref on archive" for the archive-integration child, contradicting §8's resolved "archiving never decrefs" (t1030_3). Internal design doc is stale.

## Diagnostic context

While writing the `ait attach` website reference (t1687_2), every claim was
checked against `.aitask-scripts/aitask_attach.sh`. The script's own
`show_help` is correct (`move` is marked "not yet implemented"; the verb
dies via `cmd_stub`), but the top-level `ait` help still describes all verbs
but `ls` as pending. Separately, `aidocs/task_attachments_design.md` §8
records that archiving never decrefs, while §11's decomposition list still
says "decref on archive" — an agent reading §11 alone would document the
wrong lifecycle (the website page now states the shipped behaviour).

## Suggested fix

- `ait:51`: change the parenthetical to "(ls/add/get/rm/gc; move pending)".
- `aidocs/task_attachments_design.md` §11 item 3: replace "decref on archive"
  with the shipped behaviour (archive keeps refs; orphan-only `gc` with the
  grace knob), or mark the list as the historical decomposition.
