---
Task: t20_skill_creating_aitask.md
Worktree: none (working in main repository)
Branch: current
---

# Implementation Plan: t20 - AI Task Management Skills

## Overview

Create three Claude Code skills for managing AI tasks:
1. **aitask-create** - Create new task files with auto-numbering
2. **aitask-pick** - Rename from pick-aitask, add direct task selection via argument
3. **aitask-cleanold** - Archive old task/plan files to tar.gz

---

## Phase 1: Create aitask-cleanold Skill

- [x] Create `.claude/skills/aitask-cleanold/SKILL.md`

### Skill Workflow Summary
1. List archived task files (`aitasks/archived/t*_*.md`)
2. List archived plan files (`aiplans/archived/p*_*.md`)
3. Keep the highest-numbered file from each (for aitask-create compatibility)
4. Archive remaining files to `old.tar.gz` (append if exists)
5. Delete original files after successful archiving
6. Commit changes to git

### Key Implementation Details
- Use `tar -rf` to append to existing archives (with gzip workaround: extract, add, recompress)
- Only archive files matching `t*_*.md` and `p*_*.md` patterns (leave other .md files uncompressed)
- Verify archive integrity before deleting originals

---

## Phase 2: Rename pick-aitask to aitask-pick

- [x] Create `.claude/skills/aitask-pick/`
- [x] Copy and modify content from `.claude/skills/pick-aitask/SKILL.md`
- [x] Delete `.claude/skills/pick-aitask/`

### Modifications to SKILL.md
1. Update frontmatter: `name: aitask-pick`
2. Add **Step 0** before Step 1:
   - Check if numeric argument provided (e.g., `/aitask-pick 16`)
   - Find matching task file `aitasks/t<number>_*.md`
   - If found, skip to Step 4 (Determine Execution Environment)
   - If not found, display error and fall back to Step 1
3. Update Step 3 with note that it can be skipped if argument provided

---

## Phase 3: Create aitask-create Skill

- [x] Create `.claude/skills/aitask-create/SKILL.md`

### Skill Workflow Summary
1. **Determine next task number:**
   - Scan `aitasks/t*_*.md` (active tasks)
   - Scan `aitasks/archived/t*_*.md` (archived tasks)
   - Check `aitasks/archived/old.tar.gz` if exists
   - Use max(all numbers) + 1

2. **Gather metadata via AskUserQuestion:**
   - Priority: High / Medium / Low
   - Effort: Low / Medium / High
   - Dependencies: from existing active tasks only

3. **Get task name:**
   - Free text input
   - Sanitize: lowercase, spaces→underscores, remove special chars

4. **Get task definition (iterative):**
   - Ask for content chunk (single line/paragraph)
   - After each Enter, ask "Add more?" → Yes/No
   - Repeat until user selects "No"
   - Concatenate all chunks with newlines

5. **Create task file:**
   ```
   --- effort:<lo/med/hi> pri:<lo/med/hi> dep:<numbers>
   <content>
   ```

6. **Commit to git**

---

## Verification

- [ ] **aitask-cleanold**: Invoke `/aitask-cleanold` and verify correct behavior
- [ ] **aitask-pick**: Test `/aitask-pick` (menu) and `/aitask-pick 10` (direct)
- [ ] **aitask-create**: Invoke `/aitask-create` and verify task creation

---

## Post-Implementation

- [x] Archive task file (add completion timestamp, move to `aitasks/archived/`)
- [x] Archive plan file (add completion timestamp, move to `aiplans/archived/`)

---
COMPLETED: 2026-01-29 22:45
