---
priority: medium
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [task_workflow, git-integration, child_tasks]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
children_to_implement: [t1166_1, t1166_2, t1166_3]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-07-19 23:02
updated_at: 2026-07-20 12:06
---

## Goal

Extend the framework's per-task git-worktree support so that a task family — a parent task split into child tasks (and potentially anchor-grouped work) — can share one code worktree across all children, with per-child selective sync decisions and a deferred final merge when the family completes. Today each task gets its own ephemeral worktree/branch that is created, merged to main, and torn down within a single workflow run; children of the same parent get no continuity.

## Current state (exploration findings)

- **Two distinct worktree systems** exist and must not be conflated:
  - The per-task ephemeral *code* worktree: `aiwork/<task_name>` on branch `aitask/<task_name>`, gated by the `create_worktree` execution-profile key (`.aitask-scripts/lib/profile_editor.py`, `profiles.md`). This is the system this task redesigns.
  - The long-lived shared *data* worktree `.aitask-data/` on the `aitask-data` branch (task/plan files, `./ait git` routing). Out of scope — but naming and the code/data commit split (never mix code and `aitasks/`/`aiplans/` files in one commit) must be preserved.
- **Lifecycle is hardcoded one-task-one-branch-one-merge** in `.claude/skills/task-workflow/SKILL.md`: Step 5 creates the worktree (reuse guard keyed on `<task_name>` via `git worktree list --porcelain`), Step 9 runs a NON-SKIPPABLE merge-approval AskUserQuestion, then `git checkout main && git merge aitask/<task_name>`, then worktree + branch teardown. Abort/crash paths: `task-abort.md`, `crash-recovery.md`.
- **Children run as independent fresh workflow invocations** (`/aitask-pick <parent>_<n>`), each re-entering the full workflow; no shared session state. Cross-child knowledge flows through archived sibling plan files only. A shared worktree must therefore be discoverable/reusable across process restarts, keyed on the family (parent id / anchor), not the child name.
- **`anchor:` frontmatter already provides a family group key** (children inherit the parent's anchor; root has none) but nothing execution-related reads it today. It is the natural key for a group-level worktree/branch (e.g. `aiwork/t<root>` on `aitask/t<root>_family`).
- **Gates and archival are per-task**: archival hard-blocks until a task's declared gates pass (`GATE_PENDING`), the child's completion removes it from `children_to_implement`, and the parent auto-archives when the last child completes (`aitask_archive.sh`). A deferred final merge at family completion is a new lifecycle stage the archival flow does not model.
- **Existing precedent for deferred merges**: Claude-Web mode (`aitask-pickweb` + `aitask_web_merge.sh`) decouples "work on a branch" from "merge/archive later" via per-branch completion markers and a later merge scan. Study as a model.
- No pending tasks overlap this scope (worktree mentions in active tasks are incidental).

## Acceptance criteria

- **Per-child selective sync-back is a required workflow stage, not an optional
  optimization.** At each child's completion the workflow must evaluate the
  family branch's accumulated changes and sync the eligible subset back to main
  (with user approval). A design that only merges once at family completion is
  an incomplete implementation of this task.
- **Rationale — divergence control:** each partial sync shrinks the diff the
  family branch carries against main, keeping the final merge small and
  low-conflict. This works hand-in-hand with the sync-forward policy of design
  question 6: regularly syncing eligible changes *to* main and rebasing/merging
  main *into* the family branch are the two halves of keeping a long-lived
  family worktree from diverging.
- A targeted-sync sub-skill/procedure (hunk/path-level selection) exists as a
  reusable unit, not inlined ad hoc into task-workflow steps.

## Design questions to resolve in planning

1. **Sharing policy**: always share one worktree for all children vs. per-family opt-in (frontmatter field or profile key) vs. per-child decision at pick time.
2. **Selective sync semantics**: at each child's completion, evaluate which changes make sense to sync to main immediately (e.g. independent, low-risk pieces) vs. which stay on the family branch for the final merge. This likely needs a supporting sub-skill/procedure for targeted code sync (hunk/path-level selection) and clear rules for what the NON-SKIPPABLE merge approval covers at each stage.
3. **Merge-approval placement**: today's per-task approval gate would fire per child; decide whether it moves to the final family merge, applies to each partial sync, or both.
4. **Lifecycle ownership**: who tears the family worktree down — the last child's Step 9, the parent auto-archival, or an explicit family-completion step? Must handle aborted/postponed children and crash recovery (worktree survey in `crash-recovery.md`).
5. **Gate/archival interaction**: children whose code is not yet merged to main still need their gates satisfiable and their archival meaningful; decide whether archival semantics change ("done = on family branch") or a new "merged" stage is added.
6. **Base-branch drift**: long-lived family branches diverge from main while other tasks merge; define rebase/merge-from-main policy between children.

## Blast radius

Large: `task-workflow` SKILL.md Steps 5/8/9, `task-abort.md`, `crash-recovery.md`, profile schema (`profile_editor.py`, `profiles.md`, profile YAMLs), possibly `aitask_archive.sh`, plus a new targeted-sync sub-skill/helper script. All skill changes land in the Claude Code tree first, with follow-up port tasks for Codex CLI / OpenCode per CLAUDE.md.
