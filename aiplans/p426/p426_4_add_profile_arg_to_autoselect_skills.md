---
Task: t426_4_add_profile_arg_to_autoselect_skills.md
Parent Task: aitasks/t426_default_execution_profiles.md
Sibling Tasks: aitasks/t426/t426_1_*.md, aitasks/t426/t426_2_*.md, aitasks/t426/t426_3_*.md, aitasks/t426/t426_5_*.md, aitasks/t426/t426_6_*.md
Archived Sibling Plans: aiplans/archived/p426/p426_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t426_4 — Add `--profile` to Auto-Select Skills

## Context

2 non-interactive skills (pickrem, pickweb) use the auto-select profile procedure. Each needs to parse `--profile <name>` from arguments and pass it to the auto-select procedure.

## Steps

### 1. Update `aitask-pickrem` (`.claude/skills/aitask-pickrem/SKILL.md`)

This skill already has a required positional argument (task ID). Add `--profile <name>` as an optional named flag.

**Add pre-parse step** before existing argument parsing:

```markdown
### Step 0 (pre-parse): Extract `--profile` argument

If the skill arguments contain `--profile <name>`:
- Extract the `<name>` value
- Store it as `profile_override`
- Remove `--profile <name>` from the argument string
- If `--profile` appears but no name follows, warn and set `profile_override` to null

If no `--profile` in arguments, set `profile_override` to null.
```

**Update Step 1** (profile auto-select) to pass parameters:

```markdown
Execute the **Execution Profile Selection Procedure — Auto-Select** (see `execution-profile-selection-auto.md`) with:
- `mode_label`: `"Remote"`
- `skill_name`: `"pickrem"`
- `profile_override`: the value parsed from `--profile` argument (or null)
```

Example usage: `/aitask-pickrem 42 --profile remote`

### 2. Update `aitask-pickweb` (`.claude/skills/aitask-pickweb/SKILL.md`)

Same pattern as pickrem. Add pre-parse for `--profile`, update Step 1:

```markdown
Execute the **Execution Profile Selection Procedure — Auto-Select** (see `execution-profile-selection-auto.md`) with:
- `mode_label`: `"Web"`
- `skill_name`: `"pickweb"`
- `profile_override`: the value parsed from `--profile` argument (or null)
```

Example usage: `/aitask-pickweb 42 --profile remote`

### 3. Update Codex Wrappers

**`.agents/skills/aitask-pickrem/SKILL.md`** and **`.agents/skills/aitask-pickweb/SKILL.md`:**

Update Arguments section to add:
```markdown
Optional `--profile <name>` to override execution profile auto-selection.
```

### 4. Update OpenCode Wrappers

**`.opencode/skills/aitask-pickrem/SKILL.md`** and **`.opencode/skills/aitask-pickweb/SKILL.md`:**

Same change as Codex wrappers.

### 5. Verify

- Read each updated skill to verify argument parsing consistency
- Verify wrappers mention `--profile`

## Files to Modify

**Core (2 files):**
- `.claude/skills/aitask-pickrem/SKILL.md`
- `.claude/skills/aitask-pickweb/SKILL.md`

**Codex wrappers (2 files):**
- `.agents/skills/aitask-pickrem/SKILL.md`
- `.agents/skills/aitask-pickweb/SKILL.md`

**OpenCode wrappers (2 files):**
- `.opencode/skills/aitask-pickrem/SKILL.md`
- `.opencode/skills/aitask-pickweb/SKILL.md`

## Reference Files

- `.claude/skills/task-workflow/execution-profile-selection-auto.md` — updated procedure with Input params (from t426_2)
