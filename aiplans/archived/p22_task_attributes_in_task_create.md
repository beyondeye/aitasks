---
Task: t22_task_attributes_in_task_create.md
Worktree: none (working in main repository)
Branch: current
---

# Implementation Plan: YAML Front Matter for AITask System

## Task Reference
- Task: `aitasks/t22_task_attributes_in_task_create.md`

## Summary
Convert the aitask system from single-line metadata (`--- effort:med pri:hi dep:1,3,5`) to proper multi-line YAML front matter with new attributes: `created_at`, `updated_at`, `labels`, `issue_type`, and `status`.

## Target Format
```yaml
---
priority: high
effort: medium
depends: [1, 3, 5]
issue_type: feature
status: Ready
labels: [ui, backend]
created_at: 2026-02-01 14:30
updated_at: 2026-02-01 14:30
---

Task description here...
```

## User Requirements
- Multi-line YAML front matter (not single-line)
- Timestamps: human-readable format (2026-02-01 14:30)
- Labels: free-form, comma-separated input, sanitized (no duplicates, valid filename chars)
- Status: `Editing`/`Postponed`/`Ready`/`Done`, coexists with COMPLETED timestamp at file end
- Note: `Done` is set by aitask-pick when completing a task; initial values are `Editing`/`Postponed`/`Ready`
- Issue type: `bug`/`feature`

---

## Implementation Steps

### Step 1: Update `aitasks_ls.sh` - Add YAML Parsing and Status Filtering
- [x] Update help text to document new YAML format
- [x] Add `-s` / `--status` flag to filter by status (default: `Ready`)
- [x] Add `parse_task_metadata()` function
- [x] Add `parse_yaml_frontmatter()` function
- [x] Extract legacy parsing logic into `parse_legacy_format()` function
- [x] Add `calculate_blocked_status()` function
- [x] Simplify main processing loop
- [x] Filter tasks by status
- [x] Add issue_type to verbose output
- [x] Legacy format tasks default to status=Ready

### Step 2: Update `aitasks_create.sh` - New Attribute Collection
- [x] Add helper functions (select_issue_type, select_status, get_labels, etc.)
- [x] Modify main() function for new prompts
- [x] Rewrite create_task_file() function for YAML output
- [x] Update summary display
- [x] Remove map_priority() and map_effort() functions

### Step 3: Update `aitask-pick` Skill
- [x] Update Step 9 to set status: Done when completing task

### Step 4: Testing
- [x] Create a new task with ./aitasks_create.sh (manual testing required)
- [x] List tasks with ./aitasks_ls.sh -v 10 - verified working
- [x] Test backward compatibility with existing tasks - legacy format parses correctly
- [x] Test YAML format parsing - verified working
- [x] Test status filtering - verified working (Ready default, Editing filter, all filter)

### Step 5: Post-Implementation
- [ ] Archive task file
- [ ] Archive plan file

---

## Critical Files
- `/home/ddt/Work/tubetime/aitasks_ls.sh`
- `/home/ddt/Work/tubetime/aitasks_create.sh`
- `/home/ddt/Work/tubetime/.claude/skills/aitask-pick/SKILL.md`

---
COMPLETED: 2026-02-01 14:33
