---
priority: medium
effort: medium
depends: []
issue_type: chore
status: Ready
labels: [framework, remove_support, tests]
gates: [risk_evaluated]
anchor: 2074
created_at: 2026-10-20 12:33
updated_at: 2026-10-20 12:33
---

## Context

This is the closing child of t2074 (remove legacy repository mode). The parent
task requires two things from it: a framework-wide rescan after implementation,
and the reconciliation of active backlog tasks that still carry legacy criteria.
The parent's acceptance is checked against this task's report.

It depends on t2074_1 through t2074_12. Read
`aiplans/p2074_remove_legacy_repository_mode_support.md` in full.

## Work

1. **Backlog reconciliation**, done through the normal task workflow. These are
   the tasks and the criteria that need reconciling:
   - t1619 (MV): the setup decline-branch checklist item.
   - t1625 (MV): the `LEGACY_MODE` link-token branch, and "rather than
     degrading to legacy mode".
   - t1678: the index lock "covers both modes".
   - t1984: the "Concurrency, in legacy mode **and** branch mode" test cell.
   - t1708 (MV): "every automated pin runs in a LEGACY-mode fixture".
   - t1796: the detection-flip reasoning.

   For each task:
   - Confirm the owning child already sent a note. The notes come from
     t2074_3, t2074_4 and t2074_9.
   - Update the obsolete criteria, or create a task for them, with the user's
     confirmation.
   - Record the disposition.

   Archived plans and historical changelog entries stay untouched.
2. **Framework-wide rescan.** Scan `.aitask-scripts/`, `install.sh`, `ait`,
   `goengines/`, `.claude/skills/`, `.agents/`, `.opencode/`, `seed/`,
   `tests/`, `website/content/`, `aidocs/`, `README.md` and `CLAUDE.md` for:
   - explicit terms (`legacy mode`, `LEGACY_MODE`, `LEGACY_MODE_SKIP`,
     `ait_data_mode`, `MODE:legacy`, "passes through to plain git",
     optional/separate data branch);
   - implicit fallbacks:
     - `git -C .aitask-data … || git`
     - `["git"]` used as a task-data command
     - `-d aitasks && ! -L aitasks`
     - a bare `.aitask-data/.git` existence test used as acceptance outside
       the classifier
     - `_AIT_DATA_WORKTREE`
     - `os.path.isdir(".aitask-data")` / `DATA_WORKTREE.exists()` used as a
       mode switch
     - `TASK_DIR` defaults that bypass the layout

   Classify every remaining match into one of five buckets:
   - historical context;
   - a rejection or negative test;
   - setup-only conversion or repair;
   - unrelated use of "legacy";
   - a defect.

   Record the table in this task's plan. For every defect, fix it here if it
   is trivial; otherwise create a follow-up and hand it to its owner.
3. **Post-phase `legacy_branch_tripwire`.** Add
   `tests/test_no_legacy_layout_branches.sh`. It fails if any of the following
   is reintroduced in `.aitask-scripts/` or `install.sh`:
   - `_AIT_DATA_WORKTREE="."`
   - a `LEGACY_MODE` or `LEGACY_MODE_SKIP` token
   - an `ait_data_mode` legacy branch
   - a plain-`git` fallback for task data
   - a bare `.aitask-data/.git` acceptance test outside the classifier

   Give it:
   - a per-line allowlist for the setup-only migration and repair lines in
     `setup_data_branch`;
   - a planted-probe control proving each pattern fires (see the memory
     "Source tripwires: preflight + tool's discovery rule");
   - the file-backed counters, if any case runs in a subshell.
4. **Parent acceptance check.** Walk through every acceptance criterion in the
   t2074 task file and cite the evidence for it: the commit, test or report.

## Verification

- `bash tests/test_no_legacy_layout_branches.sh`, including its planted-probe
  controls.
- The full bash suite, every file run individually.
- `bash tests/run_all_python_tests.sh`.
- `./.aitask-scripts/aitask_skill_verify.sh`.
- The website build and `check_links.py --build`.
