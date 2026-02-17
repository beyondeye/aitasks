---
Task: t151_remove_or_update_aitaskzipold_skill.md
Worktree: N/A (working on current branch)
Branch: main
Base branch: main
---

## Context

The `aitask-zipold` skill is a thin wrapper that only documents and dispatches to `aiscripts/aitask_zip_old.sh`. Unlike complex skills like `/aitask-pick` that provide multi-step workflows, this skill adds no orchestration or Claude Code-specific functionality. The bash script is already accessible via `./ait zip-old` and has its own `--help`. No other skills depend on it.

**Decision: Delete the skill.**

## Implementation Plan

### Step 1: Delete the aitask-zipold skill directory

- Remove `.claude/skills/aitask-zipold/` (contains only `SKILL.md`)

### Step 2: Update `docs/development.md`

- **File:** `docs/development.md`
- **Line ~136:** Change `/aitask-zipold` reference in the Release Process section to `./ait zip-old`

### Step 3: Update `docs/skills.md`

- **File:** `docs/skills.md`
- **Line ~15:** Remove `/aitask-zipold` from the skills list table
- **Line ~30:** Remove any quick-reference entry
- **Lines ~264-282:** Remove the detailed `/aitask-zipold` section

## Verification

1. Confirm `.claude/skills/aitask-zipold/` no longer exists
2. Confirm `docs/development.md` references `./ait zip-old` instead of `/aitask-zipold`
3. Confirm `docs/skills.md` has no references to `aitask-zipold`
4. Grep the codebase for any remaining references to `aitask-zipold`
5. Run `./ait zip-old --help` to confirm the CLI path still works

## Final Implementation Notes
- **Actual work done:** Deleted the aitask-zipold skill directory, updated docs/development.md to reference `./ait zip-old` instead of `/aitask-zipold`, and removed all references from docs/skills.md (TOC entry, overview table row, and detailed section).
- **Deviations from plan:** None — implemented exactly as planned.
- **Issues encountered:** None.
- **Key decisions:** Confirmed the skill adds no value beyond wrapping the bash script. The `./ait zip-old` CLI command is the correct replacement.

## Step 9 (Post-Implementation)

Archive task and plan files per the standard workflow.
