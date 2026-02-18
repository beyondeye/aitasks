---
Task: t172_4_update_claude_skills.md
Parent Task: aitasks/t172_rename_reviewmode_to_reviewguide.md
Sibling Tasks: aitasks/t172/t172_5_*.md
Archived Sibling Plans: aiplans/archived/p172/p172_1_*.md, aiplans/archived/p172/p172_2_*.md, aiplans/archived/p172/p172_3_*.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Context

Child task 4 of t172 (rename reviewmode to reviewguide). t172_1 physically moved/renamed all directories and files. t172_2 updated install.sh and aitask_setup.sh. t172_3 updated bash scripts and tests. This task updates the three Claude Code skill files to use the new naming and paths.

Critical notes from t172_3: The `REVIEW_MODES` output section header was renamed to `REVIEW_GUIDES` in detect_env.sh, and `--reviewmodes-dir` flag was renamed to `--reviewguides-dir`.

## Plan

### 1. Update `.claude/skills/aitask-reviewguide-classify/SKILL.md` (223 lines)

All changes are text replacements — no structural changes.

**Frontmatter:** name and description updated.
**All paths:** `aitasks/metadata/reviewmodes/` → `aireviewguides/`
**Script refs:** `aitask_reviewmode_scan.sh` → `aitask_reviewguide_scan.sh`
**Skill refs:** `/aitask-reviewmode-classify` → `/aitask-reviewguide-classify`, merge too
**Ignore file:** `.reviewmodesignore` → `.reviewguidesignore`
**Terminology:** reviewmode→reviewguide, review mode→review guide throughout

### 2. Update `.claude/skills/aitask-reviewguide-merge/SKILL.md` (280 lines)

Same pattern as classify skill.

### 3. Update `.claude/skills/aitask-review/SKILL.md` (306 lines)

**Paths:** `aitasks/metadata/reviewmodes` → `aireviewguides`
**Flags:** `--reviewmodes-dir` → `--reviewguides-dir`
**Output parsing:** `REVIEW_MODES` → `REVIEW_GUIDES`
**Skill refs:** classify and merge invocations updated
**Terminology:** review modes→review guides, reviewmode→reviewguide

## Verification

1. `grep -ri "reviewmode" .claude/skills/aitask-reviewguide-classify/SKILL.md` — 0 results
2. `grep -ri "reviewmode" .claude/skills/aitask-reviewguide-merge/SKILL.md` — 0 results
3. `grep -ri "reviewmode" .claude/skills/aitask-review/SKILL.md` — 0 results
4. `grep -r "aitasks/metadata/reviewmodes" .claude/skills/` — 0 results
5. `grep -r "aireviewguides" .claude/skills/` — should show new paths

## Final Implementation Notes

- **Actual work done:** All planned changes executed across 3 files. Updated frontmatter names/descriptions, all path references from `aitasks/metadata/reviewmodes/` to `aireviewguides/`, script references, skill invocation references, ignore file references, output section headers (`REVIEW_MODES` → `REVIEW_GUIDES`), flag names (`--reviewmodes-dir` → `--reviewguides-dir`), and all terminology (reviewmode→reviewguide, review mode→review guide).
- **Deviations from plan:** None. All changes were straightforward text replacements as planned.
- **Issues encountered:** None.
- **Key decisions:** Kept `review_default_modes` profile key name unchanged (renaming it would break existing profiles). Also updated `aitasks/metadata/` references in Notes sections to `aireviewguides/` where they referred to vocabulary file storage.
- **Notes for sibling tasks:**
  - t172_5 should check if any active task files or archived task/plan files reference "reviewmode" terminology in skill invocations or path references
  - The `review_default_modes` profile key was intentionally NOT renamed — it refers to mode names (the `name` frontmatter field), not the concept of "review modes"

## Post-Implementation

Step 9 from task-workflow: archive task and plan via `aitask_archive.sh 172_4`.
