---
priority: high
effort: medium
depends: [t1912_2]
issue_type: enhancement
status: Ready
labels: [git, concurrency, robustness]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-11-12 19:42
updated_at: 2026-11-12 19:42
---

## Context

Child 3 of t1912. Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. This child must
land **before** t1912_4 (writer cutover).

Today `.aitask-scripts/lib/verified_update_lib.sh` calls
`converge_current_repo_with_remote` (= `task_data_converge`,
`lib/task_utils.sh` ~L2416-2545) before and after every stats write.
That converge **pushes** unpushed local task-data commits as a side effect.
Satisfaction Feedback Step 0 (the usage bump) runs on every completion, so
several workflow paths currently publish their task-data commits **only**
through that side effect.

t1912_4 removes the converge. t1912 design item 7 and the user decision say
to move that publication to an explicit `./ait git push` **at each step that
relies on it**, not to the stats writer and not to a single push inside
satisfaction-feedback.

Pushers today:
- `./ait git push` = `task_push`, with pull-rebase retries;
- `aitask_pick_own.sh`, `aitask_gate_record.sh`, `aitask_note.sh` and
  `aitask_lock.sh` push.
- `aitask_archive.sh`, `aitask_task_commit.sh` and `aitask_create.sh` do
  **not** push.

## Inventory of dependent paths (explorer findings, 2026-11-12; re-verify each)

| Path | Unpushed commits it carries |
|---|---|
| `task-workflow/SKILL.md` Step 9 gate guard "Defer — keep in-flight" (~L1137-1144): skips the L1211 push and goes to 9b | Step 8 plan commit; verification-state commit (`manual-verification.md` ~L290) |
| `task-workflow/planning.md` child-split "Stop here" (~L317), commits at ~L271 / L332 | child task files and child plans |
| `task-workflow/cross-repo-child-assignment.md` "Stop here" (~L163) | local children (repo B pushes itself at ~L136) |
| `aitask-explore` "save for later": `.aitask-scripts/skill_templates/_auto_continue_block.j2` ~L64-65, used at `aitask-explore/SKILL.md.j2` ~L323 | the created task |
| `aitask-qa` Step 7 (`SKILL.md.j2` ~L81), after follow-up creation | the follow-up task |
| `aitask-docs-gap` Step 6 → 7 (~L167, ~L209) | the doc task (`aitask_create.sh --commit`) |
| `aitask-add-model` Step 6 → 7 (~L289, ~L334) | `models_<agent>.json` (and `codeagent_config.json` in promote mode) |
| `aitask-refresh-code-models` Step 8 → 9 (~L154, ~L182) | `models_*.json` |

The converge also gives a second publish attempt when the Step 9 L1211 push
fails (`pushed: no`). Decide whether that path needs anything; at minimum,
the end banner already reports `pushed: no`.

Paths that already push and need no change:
- `aitask-wrap`, `aitask-web-merge` and normal Step 9 archival.
- `aitask-pickrem` (pushes at ~L541).
- `aitask-pickweb` (no `./ait git`).

## Approach

- Before editing, grep afresh for every caller of satisfaction-feedback and
  every "stop / end" exit that follows a task-data commit, across
  `.claude/skills/**`. Extend the inventory if something was missed; this
  table came from grep, not proof.
- At each site, add a best-effort `./ait git push` step right after the last
  task-data commit and before the session ends. Its result is reported, and
  a failure never fails the workflow. Where the step shows the end banner
  (`workflow-end.md`), feed the push result into the banner's `pushed:`
  field, as Step 9 does.
- Edit the **source of truth**:
  - `.md.j2` templates and `.claude/skills/<skill>/` sources (see
    `aidocs/framework/skill_authoring_conventions.md` and
    `aidocs/framework/stub-skill-pattern.md`);
  - shared templates under `.aitask-scripts/skill_templates/`.
- Then rerender, regenerate the goldens in the same commit, and run
  `./.aitask-scripts/aitask_skill_verify.sh`.
- `.agents/` and `.opencode/` trees: where they are not rendered from the
  same sources, suggest separate port tasks (per CLAUDE.md).

## Verification

- `./.aitask-scripts/aitask_skill_verify.sh` is clean.
- The golden tests for every touched procedure pass, including
  `tests/test_skill_render_task_workflow.sh`.
- For each site, reading the rendered fast/default/remote variants shows the
  push step in place.
- The 'after' risk mitigation task `pin_rehomed_push_sites` (a standalone
  task that depends on this child) adds the pinned-inventory guard test. It
  does not belong here.

Step 9 (Post-Implementation) applies.
