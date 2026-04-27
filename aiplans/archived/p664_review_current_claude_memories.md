---
Task: t664_review_current_claude_memories.md
Base branch: main
plan_verified: []
---

# Plan: t664 — Review Claude memories, transform to framework-update tasks, then delete memories

## Context

Task t664 is meta-work: review the 12 stored Claude auto-memories at
`/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/`, identify ones that
encode user corrections of unexpected agent behavior (or load-bearing design
invariants), spawn standalone aitasks that hardwire those rules into the
framework so the next session's agent doesn't repeat the mistakes, then delete
all stored memories.

User answers (from planning):
- **Granularity:** Bundled by target file — 4 standalone tasks.
- **Scope:** 9 actionable feedback memories + 2 design-invariant project memories
  (skip the packaging-shim historical memory).
- **Hierarchy:** Standalone (sibling) tasks, not children of t664.

## Memory triage (12 memories)

Source dir: `/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/`
plus the `MEMORY.md` index.

| # | File | Type | Outcome |
|---|------|------|---------|
| 1 | `feedback_ait_setup_vs_upgrade_in_hints.md` | feedback | → CLAUDE.md addition |
| 2 | `feedback_check_sibling_tasks_before_planning_overlap.md` | feedback | → planning.md addition |
| 3 | `feedback_cli_verb_rename_clean_removal.md` | feedback | → CLAUDE.md addition |
| 4 | `feedback_companion_pane_autodespawn.md` | feedback | → CLAUDE.md addition |
| 5 | `feedback_context_variable_pattern_over_substitution.md` | feedback | → CLAUDE.md addition |
| 6 | `feedback_offer_upstream_followup_proactively.md` | feedback | → task-workflow Step 8 addition |
| 7 | `feedback_step8_user_review_is_must.md` | feedback | → task-workflow Step 8 strengthening |
| 8 | `feedback_test_full_install_flow.md` | feedback | → CLAUDE.md addition |
| 9 | `feedback_tui_pane_navigation_keys.md` | feedback | → CLAUDE.md addition |
| 10 | `project_packaging_model_shim_only.md` | project | **SKIP** — historical decision, no future PM work pending |
| 11 | `project_single_session_per_project.md` | project | → CLAUDE.md addition (design invariant) |
| 12 | `project_tui_switcher_shortcuts_on_selected.md` | project | → CLAUDE.md addition (design invariant) |

## New tasks to create (4 standalone)

All created via `./.aitask-scripts/aitask_create.sh --batch --commit` (no
`--parent`). Each task description includes the "From: memory <name>" line so
the origin is traceable, plus a copy of the original memory rule and a
proposed implementation sketch.

### Task A — CLAUDE.md augmentations (8 small additions)

- **Name:** `claudemd_encode_feedback_rules`
- **Priority:** medium · **Effort:** medium · **Type:** documentation
- **Labels:** `claudeskills,documentation,task_workflow`
- **Covers memories:** 1, 3, 4, 5, 8, 9, 11, 12

Body covers (each as one bullet/section in CLAUDE.md):
- **TUI Conventions section:**
  - Pane-internal cycling uses ←/→, not `[`/`]` (memory 9).
  - Single tmux session per project — cross-session lookup or prefix-match
    `-t <session>` is a bug; use exact match `-t =<session>` (memory 11).
  - TUI switcher shortcut keys act on the **selected** session (the one
    browsed via Left/Right), not the attached session (memory 12).
  - Companion pane auto-despawn pattern (canonical helper at
    `.aitask-scripts/aitask_companion_cleanup.sh`): primary + companion
    pane IDs captured at spawn, pane-died hook scoped to the primary,
    companion only despawned when no other primary-like sibling pane
    remains; never `kill-window` (memory 4).
- **Skill / Workflow Authoring Conventions section:**
  - Context-variable pattern over template-substitution engines: declare
    per-instance values in a context file the agent reads, reference as
    `${VAR}` placeholders, do not introduce a write-time substitution
    pipeline (memory 5).
- **Adding a New Helper Script section:**
  - Test the full `install.sh → ait setup` flow end-to-end into a scratch
    dir for any helper that touches `aitasks/metadata/*.yaml` — unit-level
    tests on a hand-crafted seed pass while the integration breaks because
    `install.sh` deletes `seed/` after install (memory 8).
- **CLI Conventions section (new sub-section under "Shell Conventions" or
  its own H2):**
  - Verb semantics: `ait setup` for repair / restore / populate-missing;
    `ait upgrade` only for genuine version-change. `ait upgrade latest`
    short-circuits when on the latest version, so it cannot repair
    (memory 1).
  - When renaming an `ait` subcommand, default to clean removal of the
    old verb from the dispatcher (no deprecated alias). Only add a
    forwarding alias when the user explicitly requests backward compat
    (memory 3).

### Task B — planning.md: pre-plan sibling-task overlap check

- **Name:** `planning_check_sibling_task_overlap`
- **Priority:** medium · **Effort:** low · **Type:** feature
- **Labels:** `task_workflow,aitask_pick,claudeskills`
- **Covers memory:** 2

Body: Add a step to `.claude/skills/task-workflow/planning.md` Step 6.1 (after
the complexity assessment, before child-task creation) that requires the agent
to grep `aitasks/` for in-flight work on overlapping labels/components before
adding child tasks that may compete with sibling/parent tasks already covering
the same layer. Description includes the rule from memory 2 verbatim plus a
concrete example (t650 vs t653). Must mention the suggested follow-up to
mirror the change in `.opencode/skills/`, `.gemini/skills/`, `.agents/skills/`
per CLAUDE.md "WORKING ON SKILLS" rule.

### Task C — task-workflow Step 8: prompt for upstream root-cause follow-up

- **Name:** `task_workflow_step8_upstream_followup_offer`
- **Priority:** medium · **Effort:** low · **Type:** feature
- **Labels:** `task_workflow,aitask_pick,claudeskills`
- **Covers memory:** 6

Body: Update `.claude/skills/task-workflow/SKILL.md` Step 8 so that when the
implementation revealed an upstream defect during diagnosis, the agent must
add a discrete follow-up question to the AskUserQuestion review prompt: "Want
me to also file the upstream <X> bug as a new aitask?" (separate from the
main commit/abort options). Include the t660 origin example and proposed
implementation sketch. Must mention follow-up parity tasks for the other
three code agents.

### Task D — task-workflow Step 8: strengthen non-skippable user-review language

- **Name:** `task_workflow_step8_review_nonskippable_guard`
- **Priority:** medium · **Effort:** low · **Type:** feature
- **Labels:** `task_workflow,aitask_pick,claudeskills`
- **Covers memory:** 7

Body: Update `.claude/skills/task-workflow/SKILL.md` Step 8 to add explicit
language stating that the AskUserQuestion review prompt is non-skippable —
no execution-profile key (`skip_task_confirmation`, `post_plan_action`, etc.)
and no auto-mode behavior may elide it. Memory text quoted (t645 origin).
Include the rule that future profile-keys named `commit_review: skip` would
be the only valid override path. Must mention follow-up parity tasks for the
other three code agents.

## Files modified by this task (t664)

- `aitasks/t664_review_current_claude_memories.md` — status update via
  `aitask_pick_own.sh` (already done) and final archival via `aitask_archive.sh`.
- `aiplans/p664_review_current_claude_memories.md` — externalized plan.
- `aitasks/t<A>…t<D>_*.md` — 4 new task files created via
  `aitask_create.sh --batch --commit`.
- **Deleted at end of implementation:** all 12 memory files plus `MEMORY.md`
  in `/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/`. The memory
  directory is **outside the git tree**, so deletion is `rm`, not `git rm`,
  and is not part of any commit.

## Implementation steps

1. **Pre-flight:** Re-verify memory dir contents
   (`ls /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/`) to catch
   any new memory written between planning and implementation.

2. **Create Task A (CLAUDE.md bundle):**
   - Compose the description heredoc with the 8 covered memories listed
     verbatim (each as a "From memory: …" block) plus the proposed
     CLAUDE.md additions.
   - Run `./.aitask-scripts/aitask_create.sh --batch --commit --name claudemd_encode_feedback_rules --priority medium --effort medium --type documentation --labels "claudeskills,documentation,task_workflow" --desc-file - <<'TASK_DESC' … TASK_DESC`
   - Capture the task ID from the `Created:` line.

3. **Create Task B (planning.md):** same shape, name
   `planning_check_sibling_task_overlap`, type `feature`, effort `low`,
   labels `task_workflow,aitask_pick,claudeskills`. Body includes the
   memory rule, the t650 example, and the per-agent parity-follow-up note.

4. **Create Task C (Step 8 upstream follow-up):** same shape, name
   `task_workflow_step8_upstream_followup_offer`.

5. **Create Task D (Step 8 non-skippable guard):** same shape, name
   `task_workflow_step8_review_nonskippable_guard`.

6. **Verify:** `./ait git log -5 --oneline` shows 4 ait-create commits.

7. **Step 8 user review** (mandatory per task-workflow SKILL.md): show
   `git status` + `git diff --stat`, then run `AskUserQuestion`
   "Commit changes / Need more changes / Abort task". This is the
   non-skippable review checkpoint — do not skip it under any profile.

8. **Memory deletion** (only after the user approves "Commit changes" and
   the new tasks are confirmed):
   ```bash
   rm /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/feedback_*.md
   rm /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/project_*.md
   rm /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/MEMORY.md
   ```
   No git operation — the memory dir is outside the repo.

9. **Commit / archive flow:** No source-code files were edited by t664
   itself (the new task files were committed by `aitask_create.sh
   --commit` already). The plan-file commit will happen at archive time
   per the standard task-workflow Step 8 / Step 9 path.

## Verification

- `ls /home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/` returns
  empty (or just `..`).
- `./.aitask-scripts/aitask_ls.sh -v 20 | grep -E "claudemd_encode_feedback_rules|planning_check_sibling_task_overlap|task_workflow_step8_upstream|task_workflow_step8_review_nonskippable"`
  returns 4 task lines.
- `./ait git log --oneline -10` shows 4 `feature: Add task` / `documentation: Add task` commits attributed to the create flow plus the t664 archival commit.

## Step 9 reference

Standard post-implementation flow per `.claude/skills/task-workflow/SKILL.md`
Step 9: archive t664 via `./.aitask-scripts/aitask_archive.sh 664`, push via
`./ait git push`. No worktree to clean (profile `fast` set
`create_worktree: false`).

## Final Implementation Notes

- **Actual work done:** Created 4 standalone aitasks encoding 11 of the 12
  reviewed memories into framework-update tasks:
  - **t665** (`claudemd_encode_feedback_rules`, documentation, medium effort)
    — bundles 8 small CLAUDE.md additions covering memories 1, 3, 4, 5, 8,
    9, 11, 12. Targets the TUI Conventions, Skill / Workflow Authoring
    Conventions, Adding a New Helper Script, and (new) CLI Conventions
    sections.
  - **t666** (`planning_check_sibling_task_overlap`, feature, low effort)
    — adds a sibling-task overlap check to `planning.md` §6.1 before
    child-task creation, with the t650 vs t653 worked example.
  - **t667** (`task_workflow_step8_upstream_followup_offer`, feature, low
    effort) — adds an upstream-defect reflection sub-step + conditional
    AskUserQuestion to task-workflow `SKILL.md` Step 8, with the t660
    worked example.
  - **t668** (`task_workflow_step8_review_nonskippable_guard`, feature, low
    effort) — adds a prominent NON-SKIPPABLE callout at the top of
    task-workflow `SKILL.md` Step 8, with the t645 origin.
  Memory 10 (`project_packaging_model_shim_only.md`) was deliberately
  skipped as historical-decision-only with no future PM packaging work
  pending.
- **Deviations from plan:** None. The plan's Implementation Steps 1–6 ran
  exactly as scoped; Step 7 user-review was approved; Step 8 deletion
  proceeds next.
- **Issues encountered:** Pre-existing uncommitted changes to
  `.aitask-scripts/brainstorm/brainstorm_crew.py` and
  `tests/test_brainstorm_crew.py` were present in the working tree at
  task start. They are unrelated to t664 and were left untouched.
- **Key decisions:**
  - Bundling 8 CLAUDE.md additions into a single task (t665) rather than
    8 separate tasks: aligns with CLAUDE.md "Don't add abstractions
    beyond what the task requires" and keeps each addition reviewable in
    one PR.
  - Each of t666/t667/t668 explicitly mentions the cross-agent parity
    follow-up requirement (`.opencode/`, `.gemini/`, `.agents/`) per
    CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" — so future
    implementers don't have to rediscover the multi-agent rule.
  - Memory deletion uses `rm` (no git op) because
    `/home/ddt/.claude/projects/-home-ddt-Work-aitasks/memory/` is
    outside the project tree.
