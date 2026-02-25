---
Task: t244_refactor_task_workflow.md
Branch: main
Base branch: main
---

# Plan: Refactor task-workflow SKILL.md into multi-file skill (t244)

## Context

The task-workflow skill (`SKILL.md`) is 772 lines / 43KB — the largest skill in the project and well over the recommended 500-line limit for Claude Code skills. Per best practices, large skills should use **progressive disclosure**: keep the main SKILL.md concise and move detailed reference content into separate files loaded on demand.

This is the first multi-file skill in the project, establishing a pattern for future splits.

## Approach

Extract 3 self-contained sections into separate files, replacing them with short reference blocks in SKILL.md. The main workflow flow (Steps 3→4→5→7→8→9) stays in SKILL.md — Claude reads it linearly when following the workflow. Extracted files are read only when their specific content is needed.

### New file structure

```
.claude/skills/task-workflow/
├── SKILL.md          (~465 lines, down from 772)  — Core workflow Steps 3-5, 7-9, Notes
├── procedures.md     (~115 lines)  — Task Abort, Issue Update, Lock Release
├── planning.md       (~190 lines)  — Step 6: full planning procedure
└── profiles.md       (~60 lines)   — Execution profile schema + customization
```

## Implementation Steps

### 1. Create `procedures.md`

Extract lines 599-701 (Task Abort Procedure, Issue Update Procedure, Lock Release Procedure).

Structure:
- Preamble explaining what the file contains and when to read it
- Table of contents (required for files >100 lines)
- All three procedures with exact existing content
- Internal cross-refs within the file ("see below" for Lock Release from Abort) stay as-is

### 2. Create `planning.md`

Extract lines 231-406 (Step 6: Create Implementation Plan — including 6.0, 6.1, Child Task Documentation Requirements, Save Plan to External File, Checkpoint).

Structure:
- Preamble explaining this is Step 6 and when to read it
- Table of contents
- All subsections with exact existing content
- Update internal reference: "Task Abort Procedure (see below)" → "Task Abort Procedure (see `procedures.md`)"

### 3. Create `profiles.md`

Extract lines 724-772 (Execution Profiles section: schema reference table + customization guide).

Structure:
- Preamble
- Brief TOC
- Schema reference table and customization guide with exact existing content

### 4. Update SKILL.md — replace extracted sections with reference blocks

**Step 6 replacement (~9 lines replacing 176):**
```markdown
### Step 6: Create Implementation Plan

> **Full planning workflow:** Read `planning.md` for the complete Step 6 procedure including:
> - 6.0: Check for Existing Plan (profile-aware)
> - 6.1: Planning (EnterPlanMode, child tasks, complexity assessment)
> - Child Task Documentation Requirements
> - Save Plan to External File (naming conventions, metadata headers)
> - Checkpoint (post-plan action)
>
> After the checkpoint in `planning.md`, proceed to Step 7.
```

**Procedures replacement (~7 lines replacing 103):**
```markdown
### Procedures

The following procedures are in `procedures.md` — read on demand when referenced:

- **Task Abort Procedure** — Lock release, status revert, worktree cleanup. Referenced from Step 6 checkpoint and Step 8.
- **Issue Update Procedure** — Update/close linked issues during archival. Referenced from Step 9.
- **Lock Release Procedure** — Release task locks. Referenced from Task Abort Procedure.
```

**Execution Profiles replacement (~4 lines replacing 49):**
```markdown
### Execution Profiles

> **Full reference:** See `profiles.md` for the complete profile schema, available keys, and customization guide.

Profiles are YAML files in `aitasks/metadata/profiles/` that pre-answer workflow questions. Default profiles: **default** (all questions asked) and **fast** (skip confirmations).
```

**Update cross-references within remaining SKILL.md:**
- Step 8 (~line 490): "Execute the **Task Abort Procedure** (see below)" → "...Procedure** (see `procedures.md`)"
- Step 9 (~lines 564-566): "Execute the **Issue Update Procedure** (see below)" → "...(see `procedures.md`)"

### 5. Update references in other skills

**No cross-skill reference changes needed.** The official Claude Code docs don't address cross-skill file references — all best practice examples are intra-skill. Since SKILL.md remains the single entry point and already contains summary + pointers to the extracted files, other skills that reference `.claude/skills/task-workflow/SKILL.md` will naturally follow pointers when needed.

The only exception: `aitask-wrap/SKILL.md` (line 283) references the "Issue Update Procedure" by name. Add a relative path for clarity:

| File | Line | Change |
|------|------|--------|
| `aitask-wrap/SKILL.md` | 283 | `handle per task-workflow Issue Update Procedure` → `handle per task-workflow Issue Update Procedure (see ../task-workflow/procedures.md)` |

**Unchanged references** (all still point to SKILL.md, which is correct):
- `aitask-pick/SKILL.md` line 210, 229
- `aitask-explore/SKILL.md` line 249, 268, 269
- `aitask-review/SKILL.md` line 270, 296, 297
- `aitask-fold/SKILL.md` line 218

### 6. Verify

- `wc -l` on SKILL.md confirms under 500 lines
- Read each extracted file to confirm it's self-contained
- Verify all cross-references between files are correct
- Verify Step 3 entry points from calling skills still work

## Final Implementation Notes

- **Actual work done:** Split task-workflow/SKILL.md (772→470 lines) into 4 files: SKILL.md + procedures.md (113 lines) + planning.md (190 lines) + profiles.md (59 lines). Updated cross-references in SKILL.md and aitask-wrap/SKILL.md.
- **Deviations from plan:** Added an override clause in planning.md's checkpoint: when a child task plan is verified, the checkpoint is always interactive (ignores `post_plan_action` profile setting). This ensures users always see and confirm verified child task plans even with fast profiles.
- **Issues encountered:** During testing, the verify-plan flow for child tasks auto-skipped the confirmation checkpoint due to the fast profile's `post_plan_action: start_implementation`. Added the override clause to fix this.
- **Key decisions:** Kept all cross-skill references pointing to SKILL.md (not directly to sub-files), following the principle that SKILL.md is the single entry point. Only exception: aitask-wrap references procedures.md directly via relative path since it only needs one specific procedure.
