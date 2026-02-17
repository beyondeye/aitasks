# Plan: t143_1 — Create aitask-fold SKILL.md

## Context

Child task 1 of t143. Create `.claude/skills/aitask-fold/SKILL.md` — the complete skill definition for a standalone task-folding workflow. The skill allows users to identify related tasks and merge them into a single task, either interactively or via explicit task IDs.

## File to Create

- **`.claude/skills/aitask-fold/SKILL.md`** — New directory and file

## Implementation

Create the SKILL.md following the same structure as aitask-pick and aitask-explore. The full content is specified in the child task description (t143_1). Key steps:

### SKILL.md Workflow Steps

1. **Step 0a** — Profile selection (copy pattern from aitask-pick)
2. **Step 0b** — Parse explicit task IDs from arguments (comma or space separated). Validate each: file exists, status Ready/Editing, no children, standalone parent. Warn and exclude invalid ones. Abort if <2 valid remain.
3. **Step 0c** — Remote sync (`git pull`, lock cleanup)
4. **Step 1** — Interactive discovery (only if no args). List eligible tasks via `aitask_ls.sh`, filter, identify related groups by labels/content similarity, present with multiSelect AskUserQuestion.
5. **Step 2** — Primary task selection. Ask which task survives (others merge into it).
6. **Step 3** — Merge content. Read descriptions, build merged description with `## Merged from t<N>` headers and `## Folded Tasks` reference section. Update via `aitask_update.sh --desc-file -` and `--folded-tasks`. Handle existing folded_tasks (append). Commit.
7. **Step 4** — Decision point: continue to implementation or save for later (reuse `explore_auto_continue` profile key).
8. **Step 5** — Hand off to task-workflow from Step 3.

### Key Design Decisions

- **Reuse existing task as primary** (unlike aitask-explore which creates a new task)
- **Graceful validation**: warn and skip invalid tasks, don't abort unless <2 remain
- **Append to existing folded_tasks** if primary already has some
- **Reuse `explore_auto_continue`** profile key (same semantics)

## Verification

1. Read created SKILL.md, verify YAML frontmatter matches pattern
2. Verify bash commands use correct script flags
3. Verify handoff context variables match task-workflow Context Requirements table
4. Verify structure consistency with aitask-explore/aitask-pick SKILL.md files

## Step 9 Reference

Post-implementation cleanup already handled by task-workflow Step 9 (folded task deletion, lock release, issue update).

## Final Implementation Notes

- **Actual work done:** Created `.claude/skills/aitask-fold/SKILL.md` with the complete skill workflow (242 lines). All steps from the plan were implemented as specified.
- **Deviations from plan:** None — implementation matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Followed aitask-pick/aitask-explore patterns closely for consistency. Used pagination pattern from aitask-pick for AskUserQuestion when >4 options. Reused `explore_auto_continue` profile key rather than creating a new one.
- **Notes for sibling tasks:** The SKILL.md is now live and auto-detected by Claude Code. The sibling task (t143_2) should read the created SKILL.md to write accurate documentation in `docs/skills.md`.
