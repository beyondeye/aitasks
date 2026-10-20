---
priority: medium
effort: high
depends: []
issue_type: refactor
status: Ready
labels: [framework, remove_support, git, setup, test_infrastructure, website, docs]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t2074_1, t2074_3, t2074_9, t2074_12, t2074_14]
created_at: 2026-10-20 10:15
updated_at: 2026-10-20 17:00
---

## Objective

Harden the **branch-mode** task-data layout (the `aitask-data` branch plus the
`.aitask-data` worktree) so that a damaged or misconfigured layout is detected,
refused before any task-data write, stage, commit, pull or push, and repaired
safely by `ait setup`. **Legacy repository mode stays fully supported and
unchanged.** In legacy mode, task data lives on the code branch and `task_git`
uses plain git.

## History

This task was created as "remove legacy repository mode support" during the
t2070 shadow review, then planned and split into 14 children. On 2026-10-20 the
user **reversed** that decision and asked to keep legacy mode. The task was then
rescoped to the branch-mode defects the audit found, which exist regardless of
legacy mode. The original removal description and plan survive in git history
only. They are not active requirements.

## Defects addressed

- **Detection rungs 1–3 accept any `.aitask-data/.git`**
  (`.aitask-scripts/lib/task_utils.sh:81-121`). That includes a stale
  `gitdir`, an unrelated repo or clone, and a worktree on the wrong branch.
  When `.aitask-data` is deleted but the data links remain, rung 4 silently
  falls back to plain git on the code branch.
- **The writer guard is bypassed before any layout check.**
  `assert_task_data_writable` and `assert_data_worktree_clean` return on
  `AIT_GIT_SKIP_STATE_CHECK=1` first, and `aitask_update.sh --batch` without
  `--commit` writes without ever reaching git.
- **Setup does not detect or repair a damaged layout.** It reports "already
  configured" on bare marker existence (`aitask_setup.sh:1571`).
  `ait_ensure_data_symlinks` keeps misdirected links.
- **The board's `_task_git_cmd` (`board/board_task_manager.py:66`) resolves
  cwd-relatively** and falls back to `["git"]`. It never re-validates during the
  board's long life.
- **Mixed or misdirected primary checkouts go unnoticed.** Examples: a real
  `aitasks/` dir beside a valid data worktree, or a link to another dir.

## Children

- **t2074_1** `data_layout_classifier`: C1a/C1b classifiers, the CLI and
  `lib/data_layout.py`. Additive only.
- **t2074_3** `setup_layout_repair`: setup's "configured" fix, link repair, and
  the bounded worktree repair (never `git worktree prune`).
- **t2074_9** `branch_layout_enforcement`: fixture preparation, shell
  enforcement, and Python/board enforcement. It absorbs t2074_2 and t2074_10.
- **t2074_12** `broken_layout_docs`: website troubleshooting for damaged
  branch layouts.
- **t2074_14**: manual verification of t2074_3 and t2074_9.

The binding contract is `aiplans/p2074_branch_mode_layout_hardening.md`: states,
enforcement table, wiring, the C4 recovery matrix, and the bounded-repair rules.

## Acceptance criteria

- **Classification.** Every broken branch-mode state is distinguished from
  `legacy` and `uninitialized`. That covers stale marker, foreign repo, wrong
  branch (rebase and bisect are wedged, not broken), missing storage, and
  indeterminate topology. Genuine legacy projects, including ones with a
  leftover `aitask-data` ref or stale registration, still classify as `legacy`.
- **Git routing.** It refuses broken C1a states before running any git
  command, and still works for `unlinked`, `misdirected`, `dangling` and
  `mixed` C1b states. Writers, plus the named readers (`aitask_ls.sh`,
  `aitask_query_files.sh`, board startup), refuse every non-ready branch state.
  Legacy behaviour is unchanged.
- **No-mutation tests** prove refusals leave task data, both repos and the
  remote unchanged. They use content manifests and git snapshots with planted
  controls, and include the `AIT_GIT_SKIP_STATE_CHECK` and no-`--commit` paths.
- **Setup repair.**
  - `ait setup` repairs what it can losslessly and refuses the rest with
    manual steps.
  - It never runs `git worktree prune`.
  - It never replaces a registration whose index or operation state cannot be
    reproduced.
  - It leaves unrelated worktree metadata byte-identical.
- **Board.** It re-validates fresh before every git operation and mutation, and
  splits inspection (C1a) from mutation (C1a+C1b).
- **Docs.** They describe each damaged state, its refusal and its recovery, and
  the narrowed reader contract. The website build and `check_links.py --build`
  pass.
- **Test suites.** All bash and Python suites pass. Legacy-mode tests stay
  green without modification of their legacy fixtures.
