---
priority: medium
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_fold, bash_scripts, gates]
gates: [risk_evaluated]
anchor: 1962
followup_kind: upstream_defect
created_at: 2026-10-13 11:22
updated_at: 2026-10-13 11:22
---

## Origin

Spawned from t1962 during Step 8 review. The reviewer confirmed it as pre-existing debt with disposition "follow-up": carry the repair into this task rather than expanding t1962.

## Upstream defect

- `.aitask-scripts/aitask_fold_content.sh` (`split_fw`) and `.aitask-scripts/lib/plan_paths.py` (`cut_task_framework_sections`) both treat everything after the FIRST framework heading (`## Inbox` / `## Gate Runs` / `## Folded History`) as ledger. A task body produced by the **pre-t1962** fold script can carry genuine `## Merged from t<N>` requirements sections *below* its own `## Inbox` / `## Gate Runs`: the old script appended merged sections after the primary's ledgers. Those requirements are:
  - excluded from task-declared text, because `task_body_text` cuts at the first framework header. This affects trail_gather, shadow_scope and parallel_admission_collect;
  - when such a task is folded again, routed by t1962's `split_fw` into the inert `## Folded History` of the new primary, and so still excluded.

## Diagnostic context

- The reviewer reproduced it: a folded source whose `## Inbox` is followed by `## Merged from t3` containing `src/older.py`. After the fold, `src/older.py` is still in the output but absent from `plan_paths.extract(plan_paths.task_body_text(...))`.
- The baseline reader (HEAD before t1962) already excluded that requirement, so this is not a t1962 regression. t1962 made the merged body's own layout correct (declared → merged → Folded Tasks → Folded History → primary ledgers) but did not repair existing legacy layouts.
- Ledger records must stay historical and inert (`ledger_block.neutralize_markers`); only genuine declared sections should return to declared text.

## Suggested fix

- Option A (repair at fold time): in `aitask_fold_content.sh`, scan the framework tail of the primary and of each folded body for sections that are not framework sections (`## Merged from …`, `## Folded Tasks`, other non-ledger `## ` headings), and hoist them back into the declared part, keeping the ledger sections terminal.
- Option B (one-shot migration): a helper that rewrites existing active task files into the canonical layout.
- In either case, add a fixture with `## Inbox` followed by `## Merged from t3: …` naming `src/older.py`. Assert the path is declared after the repair and that the ledgers stay inert (real `gate_ledger` / `note_inbox` / `plan_paths` parsers, as in `tests/test_fold_content.sh`).
