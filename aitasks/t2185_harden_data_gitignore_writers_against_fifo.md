---
priority: medium
effort: low
depends: [2184]
issue_type: bug
status: Ready
labels: [install, ait_setup]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
plan_approved_at: 2026-11-03 18:55
anchor: 2173
followup_kind: upstream_defect
created_at: 2026-11-03 17:34
updated_at: 2026-11-03 18:55
---

## Origin

Spawned from t2178 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2900 — _ait_rewrite_data_gitignore_lines checks only -e/-L before grep, so a FIFO .gitignore hangs setup_data_gitignore_symlink_safe, which runs on every ait setup and on upgrade (install.sh); needs the same [[ -f ]] gate as _ait_add_gitignore_rules plus a bounded FIFO test`
- `.aitask-scripts/aitask_setup.sh:2022-2031,2045-2066 — setup_data_branch Step 7 appends the data-dir and rendered-skill blocks to the main .gitignore with unchecked >> after [[ ! -f ]] tests: a FIFO hangs it, and a read-only or non-regular .gitignore aborts setup under errexit (first branch-mode setup only)`

## Diagnostic context

t2178 moved every `setup_*` `.gitignore` helper onto `_ait_add_gitignore_rules` and, after review, gated that writer on `[[ -f "$gitignore" ]]` before it reads anything: a FIFO in place of `.gitignore` blocks grep's `open(O_RDONLY)` until a writer appears (and `{ … } >> fifo` blocks on open for write), so the old helpers — and the shared writer itself — hung instead of warning (27f red proof: exit 124 for all 11 helpers). The grep for remaining `>> "$gitignore"` writers then found the two `setup_data_branch` Step 7 blocks, which write the **main** `.gitignore`, and `_ait_rewrite_data_gitignore_lines` has the same `-e || -L` then `grep` shape as the writer had. Neither was in t2178's named scope.

Measured on git 2.56: git itself does not block on a FIFO `.gitignore` (`ls-files --others --exclude-standard`, `status --porcelain`, `diff --name-only` all rc 0), so these framework reads are the hang.

t2178 also made the shared writer's failure warning honest about partial appends (`_ait_gitignore_partial`, "the write stopped part-way"); the Step 7 blocks append the same way and would need the same treatment if they move onto the writer.

## Suggested fix

- `_ait_rewrite_data_gitignore_lines`: add `[[ -f "$gitignore" ]] || return 2` right after its existence check (rc 2 is already reported non-fatally by `setup_data_gitignore_symlink_safe`); add a bounded FIFO case (`run_bounded` from `tests/lib/proc_fixtures.sh`, like t2178's 27f in `tests/test_setup_git.sh`) for `setup_data_gitignore_symlink_safe`.
- `setup_data_branch` Step 7: check both appends (or route them through `_ait_add_gitignore_rules`-style checked writes), never fatal, honest warning; note the data block's guard is CRLF-tolerant and the rendered-skill block's guard is a single `grep -F` of one pattern, so they may not fit the per-rule writer as-is.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-03T16:55:20Z status=pass attempt=1 type=human
>
> Note: deferred
