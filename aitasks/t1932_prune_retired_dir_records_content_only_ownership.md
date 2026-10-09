---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [install, install_scripts, framework]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1926
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-10-09 15:31
updated_at: 2026-10-09 16:02
---

## Origin
Spawned from t1926 during Step 8b review.

## Upstream defect
- `.aitask-scripts/aitask_prune_retired_skills.sh:160-194 — DIR records decide ownership by content only against the flat SHA set, so a user-authored file copied byte-for-byte from any shipped blob inside a retired directory counts as "known" and the whole directory is deleted (reproduced in review; the scripts manifest avoids DIR records, the skills manifest still uses them)`

## Diagnostic context
t1926 reused this pruner for retired `.aitask-scripts/` files. Its plan first
proposed `DIR .aitask-scripts/lib/attachment_backends`, claiming a user-added
backend would keep the directory. Plan review reproduced the opposite: a
temporary fixture with pristine `local.sh` plus a user `my_backend.sh` copied
from it exited 0 and deleted the whole directory. The DIR loop checks only that
every file's `git hash-object` is in the manifest's flat SHA set; it never
checks that the file's relative path was ever shipped. t1926 sidestepped it by
using FILE records only (and pins "no DIR record" in
`tests/test_retired_scripts_manifest.sh`). `retired_skills_manifest.txt` still
uses six DIR records (`aitask-pickn` / `task-workflown` surfaces), so the hole
is live there, though only for a user file that is byte-identical to a shipped
blob.

## Suggested fix
Make DIR ownership path-aware: a file inside a retired DIR counts as known only
when its path relative to the DIR was shipped there (record per-DIR relative
paths, or path-keyed SHAs, in the manifest) — keeping the flat set's coverage of
the `aitasks/metadata/{codex,opencode}_skills/` staging copies. Add a
`tests/test_prune_retired_skills.sh` case with a copied-blob user file under a
retired DIR, plus a negative control.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-10-09T13:02:49Z status=pass attempt=1 type=human
