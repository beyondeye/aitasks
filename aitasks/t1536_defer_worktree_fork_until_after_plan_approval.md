---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Implementing
labels: [task_workflow, git, worktree, claudeskills, execution_profiles]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-17 08:31
updated_at: 2026-08-17 12:07
---

## Problem

In `task-workflow`, **Step 5 (Environment and Branch Setup)** does two different
things in one place:

1. **Resolves** the branch context — `base_branch` (profile key, else an
   `AskUserQuestion`: "Which branch should the new task branch be based on?") and
   `output_branch` (profile key, else defaults to the resolved base).
2. **Immediately forks** — `mkdir -p aiwork` followed by
   `git worktree add -b aitask/<task_name> aiwork/<task_name> <base-branch>`
   (`.claude/skills/task-workflow/SKILL.md:340-349`).

Planning is **Step 6**. So on any `create_worktree: true` profile the fork point
is pinned to the *local* base-branch HEAD **before a single line of planning has
happened** — before the plan is written, before the user approves it, and before
the Remote Drift Check runs.

Consequences:

- The plan is designed against a tree that may already differ from the fork
  point, and nothing re-cuts the branch afterwards.
- `remote-drift-check.md` (run from `planning.md`'s Checkpoint, i.e. *after* the
  fork) compares `<branch>..origin/<branch>` only. Its own notes are explicit
  that "the worktree directory is irrelevant for the drift comparison because
  the helper compares `<branch>..origin/<branch>`, not the worktree's
  `aitask/<task_name>` branch" (`remote-drift-check.md:88`). So the check can
  report drift on a fork that was already cut from the pre-drift HEAD, and its
  only remedy is to throw the whole session away ("Stop and re-verify plan"),
  leaving a stale worktree behind.
- Every "stop, don't abort" exit strands a worktree that was created for work
  that never started.
- The fork is a **write** attempted before plan mode is entered/exited, which is
  the "plan mode deferral" edge case alluded to in passing at `SKILL.md:374`
  ("this guard catches edge cases like plan mode deferral") and described
  nowhere else.

## Goal

Split resolution from forking. The **decision** about the base branch stays at
Step 5; the **fork itself** happens only once the plan is approved *and* the
Remote Drift Check has cleared — i.e. at the top of Step 7, immediately before
implementation begins.

## Acceptance criteria

1. **Step 5 keeps only the resolution.** `base_branch` / `output_branch` are
   still resolved there (profile key or `AskUserQuestion`), and the
   `create_worktree` yes/no decision is still made there. No `git worktree add`
   and no `mkdir -p aiwork` run in Step 5.

2. **Step 5's base-branch question tells the user when the fork happens.** When
   the base branch is asked interactively (no `base_branch` profile key), the
   question text must state explicitly that the worktree will be created *after*
   the plan is approved and the remote drift check has passed — not now. The
   same must hold for the display line on the profile-driven path
   ("Profile '<name>': using base branch <branch>"), so a user reading either
   surface is not left believing the fork already happened. Per project
   convention the explanation belongs **inside the widget's question text**, not
   in same-turn prose (see the visibility rule in `aitask-explore` Step 2 —
   t1150).

3. **The fork runs at the top of Step 7**, after `planning.md`'s Checkpoint has
   approved the plan and after the **Remote Drift Check Procedure** has returned
   "Continue anyway". It must run before the Step 7 ownership guard's
   implementation work and before any file is written for the task.

4. **Reuse check on the deferred fork.** The deferred `git worktree add` must
   first apply the same reuse rule Re-entry Routing already states
   (`SKILL.md:276`): if `git worktree list --porcelain` shows a
   `branch refs/heads/aitask/<task_name>` record, reuse that directory and do
   NOT recreate the branch/worktree. See the "Relationship to t1392" section.

5. **`Worktree:` plan-header field no longer depends on a directory probe.**
   `.aitask-scripts/aitask_plan_externalize.sh:515` currently emits the header
   line via `[[ -d "aiwork/${task_name}" ]] && echo "Worktree: aiwork/..."`.
   Externalization happens in Step 6, i.e. **before** the deferred fork, so that
   probe would silently drop the field from every worktree-mode plan. Add an
   explicit `--worktree <path>` flag (mirroring the existing `--no-worktree`,
   and validated the same way) and thread the Step-5 resolved intent through
   both externalize call-sites via the existing `<branch-flags>` contract
   documented in `plan-externalization.md:22-41`. The probe must not remain as a
   silent fallback that re-introduces the drop.

6. **`crash-recovery.md` still gets a `Worktree:` value.** That procedure prints
   `- Worktree: <path or "(current branch)">` (`crash-recovery.md:75`) from the
   plan header; verify it renders correctly for a task that crashed *between*
   plan approval and the fork (header declares a worktree, none exists on disk),
   and that its wording does not assert the directory exists.

7. **Stop-path prose corrected.** `plan-approved-stop.md:20` ("the plan is kept,
   the task returns to `Ready`, and the worktree/branch are left in place") and
   its Notes bullet at `:90` ("The worktree and `aitask/<task_name>` branch are
   intentionally left in place") both become conditional: reached from
   "Approve and stop here" or "Stop and re-verify plan", **no worktree exists
   yet**, and that is the improvement — the drift stop no longer strands a fork
   cut from the pre-drift HEAD. Reached from Step 7's risk-mitigation "before"
   stop, the worktree *does* exist and is still left in place.

8. **Abort path verified, not assumed.** `task-abort.md:57-63` is already phrased
   conditionally ("If a worktree was created in Step 5"). Update the step
   reference and confirm the `2>/dev/null || true` guards make the no-worktree
   case a clean no-op rather than a silent lie.

9. **Re-entry routing reconciled.** `SKILL.md:276` says "If a worktree for
   `<task_name>` already exists … reuse it … Otherwise run Step 5 as normal."
   With the fork moved, "run Step 5 as normal" no longer creates anything —
   re-point it at the Step 7 fork site so a resumed task still gets a worktree.

10. **Docs updated.** `website/content/docs/skills/aitask-pick/_index.md:30`
    numbers "Environment setup" as phase 6 *before* "Planning" as phase 7 —
    correct the ordering description. Check
    `website/content/docs/workflows/parallel-development.md:20` and
    `website/content/docs/workflows/crash-recovery.md` for the same assumption.

11. **Goldens regenerated.** All `.md.j2` edits under
    `.claude/skills/task-workflow/` must be accompanied by regenerated
    per-profile variants in the same commit, and
    `./.aitask-scripts/aitask_skill_verify.sh` must pass. Per CLAUDE.md, port
    the change to `.agents/skills/` (Codex) and `.opencode/skills/` afterwards —
    suggest separate aitasks for those.

## Relationship to t1392

**t1392_step5_worktree_reuse_on_repick** reports that Step 5's
`git worktree add -b` has no reuse check, so a stop-then-repick fails on a
worktree profile. It names three reaching paths:

- `planning.md` Checkpoint → "Approve and stop here"
- `remote-drift-check.md` → "Stop and re-verify plan"
- Step 7's risk-mitigation "before" stop

**This task dissolves the first two** — neither stop path would have created a
worktree yet, so there is nothing to collide with on re-pick. The third still
reaches a real worktree (the fork happens at the top of Step 7, the mitigation
stop later within it), so the reuse check is still required — which is why it is
acceptance criterion 4 here. t1392 was deliberately **not folded**; it should be
re-scoped or closed once this lands.

## Relationship to t1277

**t1277_plan_header_resolved_base_branch** (Ready) makes the plan header's
`Base branch:` field carry the Step-5 *resolved* base branch instead of
`detect_primary_branch()`. It touches the same helper
(`aitask_plan_externalize.sh`) and the same `<branch-flags>` threading contract
this task must extend for `--worktree`. Coordinate: doing t1277 first makes this
task's flag work a small addition to an already-threaded channel; doing them in
the other order means threading the channel twice. Consider adding
`depends: [1277]` at planning time.

## Non-goals

- Re-cutting or rebasing the fork point after the drift check. This task moves
  *when* the fork happens; it does not add a "your base moved locally while you
  planned" detector. That gap (the drift check compares local-vs-remote, never
  fork-point-vs-current-base) is real but separate — spin it off if the plan
  confirms it is still reachable after this change.
- Changing `aitask_crew_init.sh:118`, which does its own `git worktree add` for
  the agent-crew flow and is out of scope.
- Porting to Codex / OpenCode skill trees (separate tasks per CLAUDE.md).

## Provenance

Surfaced via `/aitask-explore` — the question was whether the base-branch prompt
at Step 5 is followed by an immediate fork or a deferred one. It is immediate;
the user's direction is that "the fork point should be after plan approval and
after plan drift check", and that if the decision is split from the fork, the
Step 5 prompt must say so.
