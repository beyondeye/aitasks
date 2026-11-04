---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: low
depends: []
issue_type: bug
status: Done
labels: [ait_setup, git]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 2179
followup_kind: upstream_defect
implemented_with: claudecode/opus5_5
created_at: 2026-11-03 19:04
updated_at: 2026-11-04 10:07
completed_at: 2026-11-04 10:07
---

## Origin

Spawned from t2184 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_setup.sh:2028` — Step 7's presence guard checks only the `/.aitask-data` line. A `.gitignore` that has it but lacks `/aitasks` or `/aiplans` (for example, after a hand edit) never gets those link rules added back. This predates t2184: the bare-form guard had the same one-line key.

## Diagnostic context

t2184 anchored the task-data block that `setup_data_branch` Step 7 appends (`/.aitask-data`, `/aitasks`, `/aiplans`). It also extended `_ait_rewrite_data_gitignore_lines` so both legacy forms, `name/` and bare `name`, migrate to `/name`. While doing so it noted that the guard deciding whether to append the block, `grep -qxF -e "/$AIT_DATA_DIR_NAME" …` at `aitask_setup.sh:2028`, keys on the **data-dir line only**:

- If the root `.gitignore` carries `/.aitask-data` but someone deleted `/aitasks` or `/aiplans`, Step 7 sees the block as present and appends nothing. The root `aitasks` / `aiplans` symlinks then show as untracked, and a broad `git add -A` could commit them.
- The re-run repair `setup_data_gitignore_symlink_safe` only *rewrites* existing legacy lines; it never adds a missing one. So no setup path restores a missing link rule.
- Step 7 itself only runs on first configuration, since a later `ait setup` hits its "already configured" early return. Any fix must also reach existing installs, through the re-run repair, which `install.sh` / `ait upgrade` call as well.

## Suggested fix

Guard each of `/$AIT_DATA_DIR_NAME` and `/${AIT_DATA_LINKS[@]}` on its own. That is the per-rule guard `_ait_add_gitignore_rules` already gives the other setup groups (t2178's rule table). Consider routing the data block through that table, which already handles CRLF, a non-regular `.gitignore`, and read-back after write. Then have the re-run repair add missing anchored data rules, under the same pre-setup dirty-baseline contract, and add tests for a `.gitignore` missing one link rule on both the Step 7 and the repair routes.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-04T07:22:17Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-04T08:01:47Z status=pass attempt=1 type=human

> **🔄 gate:risk_evaluated** run=2026-11-04T08:07:56Z-risk_evaluated-a1 status=running attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Note: stuckhash:3f3518845d3fdc9f

> **✅ gate:risk_evaluated** run=2026-11-04T08:07:56Z-risk_evaluated-a1 status=pass attempt=1 type=machine
>
> Verifier: `aitask-gate-risk`
> Result: risk evaluated (## Risk section + both levels present)
> Log: `.aitask-gates/2188/risk_evaluated_2026-11-04T08:07:56Z-risk_evaluated-a1.log`
