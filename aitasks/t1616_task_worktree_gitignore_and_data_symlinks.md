---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [worktree, git, testing]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1159
followup_kind: upstream_defect
created_at: 2026-08-25 22:17
updated_at: 2026-08-26 08:31
---

## Origin

Spawned from t1606 during Step 8b review. Both defects were hit while working
in a task worktree; neither is in the review-loop code t1606 changed.

## Upstream defect

- `.gitignore:1 — aiwork/ is not ignored, although the framework creates task
  worktrees there (task-workflow Step 7) and the sibling AgentCrew worktree dir
  .aitask-crews/ IS ignored; every task worktree therefore shows as untracked
  and is exposed to a broad 'git add -A'`
- `.aitask-scripts/aitask_init_data.sh:1 — the aitasks/ and aiplans/ data
  symlinks are created only for the primary checkout, so a task worktree
  created by Step 7 has none; four unrelated suite modules then fail there with
  FileNotFoundError on aitasks/metadata/*.json, which reads as a regression
  rather than a missing-fixture problem`

## Diagnostic context

**Defect 1.** `git worktree add -b aitask/<task_name> aiwork/<task_name> main`
(task-workflow Step 7) creates `aiwork/` in the primary checkout. `.gitignore`
ignores `.aitask-crews/` with the comment "AgentCrew worktrees (local, per-crew
branches)" but has no rule for `aiwork/`, so `git status` in the primary
checkout reports `?? aiwork/` for the whole worktree tree. Verified:
`git check-ignore -v aiwork/` matches nothing. The exposure matters most with
several agents active at once, where a broad staging command in one session can
sweep another session's worktree.

**Defect 2.** In the primary checkout `aitasks` and `aiplans` are symlinks into
`.aitask-data/`. A `git worktree add` checkout of the code branch has neither,
because the symlinks are not tracked on that branch — they are created by
`aitask_init_data.sh` / `aitask_setup.sh` for the primary checkout only. Running
`bash tests/run_all_python_tests.sh` inside a task worktree therefore fails with:

    FileNotFoundError: .../aitasks/metadata/codeagent_config.json

in `tests/test_board_movement.py`, `tests/test_profile_editor_shadow_tier.py`
(x2) and `tests/test_settings_brainstorm_descriptions.py`. Confirmed
environmental, not a regression: creating the two symlinks by hand
(`ln -s <primary>/.aitask-data/aitasks aitasks`, same for `aiplans`) makes all
four pass, and the suite then reports
`PYTHON SUITE: PASSED (runner=pytest, exit=0)`.

The failure mode is the expensive part: a 4-minute suite run in a fresh
worktree ends in four red modules that look like the task's own regressions,
and the agent has to disprove that before trusting any verdict.

## Suggested fix

- Add `aiwork/` to `.gitignore` beside the existing `.aitask-crews/` rule, with
  a matching comment.
- Create the two data symlinks as part of task-worktree creation (Step 7's
  `git worktree add`, or a helper it calls), reusing whatever
  `aitask_init_data.sh` already does for the primary checkout rather than
  duplicating the logic. Consider a guard test that a worktree's suite run is
  green, so this cannot regress silently.

Note these are independent; either can land alone.
