---
Task: t2074_3_setup_layout_repair.md
Parent Task: aitasks/t2074_branch_mode_layout_hardening.md
Sibling Tasks: aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_9_branch_layout_enforcement.md, aitasks/t2074/t2074_12_broken_layout_docs.md, aitasks/t2074/t2074_14_manual_verification_branch_mode_layout_hardening.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_3: Setup layout repair (C4 plus bounded worktree repair)

The binding contract is C4 and the bounded worktree repair in the parent plan.
The full detail is in the task description. Legacy setup paths stay unchanged.

## Steps
1. Replace the `setup_data_branch` :1571 shortcut with classifier dispatch.
   "Configured" means `branch` + `ready`. Dispatch on C1b first, then on C1a.
2. Extract `ait_repair_data_links` from `ait_link_worktree_data`: preflight
   for conflicts, repoint mismatched links, create absent ones. Rewire
   `--link-worktree` to use it and keep its contract.
3. Refusals: `foreign_repo`, `wrong_branch`, `mixed`, unique files in a stale
   dir, and `indeterminate`. Each prints move-aside steps that never delete.
4. Bounded worktree repair, with no `prune`:
   - identify the exact record;
   - case A: ordinary add, using the Step 1/2 fetch and add;
   - case B: preservation preflight (index == tip, no in-progress state,
     normal HEAD), interactive confirmation, a single `--force`;
   - every other case refuses.
5. Write the probe table for `add --force` and `repair` behaviour on the
   installed git, and pin it in a test. If isolation cannot be guaranteed, the
   step refuses.
6. Print the missing-storage messages: branch exists, no branch, row-1 mixed.
7. Tests: same-fixture recovery for every row; the "configured" fix; the
   misdirected-to-existing-dir manifest; the real-dir conflict; case A
   (i)-(iv); case B (a)-(c) preservation with moved copy, staged-change
   checks and the clean-index positive and non-interactive cases; missing
   index or HEAD; the unguarded-`add --force` planted control; two-worktree
   isolation with its prune planted control; legacy setup tests stay green.

## Verification
Run `test_data_branch_setup.sh`, `test_init_data.sh`, the new repair tests,
and `shellcheck`.

## Step 9
Commit with `refactor: … (t2074_3)`, then archive.
