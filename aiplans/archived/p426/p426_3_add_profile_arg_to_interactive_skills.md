---
Task: t426_3_add_profile_arg_to_interactive_skills.md
Parent Task: aitasks/t426_default_execution_profiles.md
Sibling Tasks: aitasks/t426/t426_1_*.md, aitasks/t426/t426_2_*.md, aitasks/t426/t426_4_*.md, aitasks/t426/t426_5_*.md, aitasks/t426/t426_6_*.md
Archived Sibling Plans: aiplans/archived/p426/p426_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t426_3 — Add `--profile` to Interactive Skills

## Context

6 interactive skills use the Execution Profile Selection Procedure (interactive variant). Each needs to:
1. Parse `--profile <name>` from its arguments
2. Pass `skill_name` and `profile_override` to the procedure call in Step 0a

Additionally, Codex (`.agents/skills/`) and OpenCode (`.opencode/skills/`) wrappers need their Arguments sections updated.

## Steps

### 1. Update Core Skills (Claude Code)

For each of the 6 skills, apply two changes:

**A. Add `--profile` argument parsing**

Each skill that accepts arguments has a Step 0b (or equivalent) for argument parsing. Add a `--profile` parsing block. The exact insertion point varies per skill:

**Pattern for skills WITH existing arguments (pick, fold, revert):**

Add before the existing argument parsing in Step 0b:

```markdown
### Step 0 (pre-parse): Extract `--profile` argument

If the skill arguments contain `--profile <name>`:
- Extract the `<name>` value (the word following `--profile`)
- Store it as `profile_override`
- Remove `--profile <name>` from the argument string before passing to Step 0b
- If `--profile` appears but no name follows, warn: "Missing profile name after --profile" and set `profile_override` to null

If no `--profile` in arguments, set `profile_override` to null.
```

**Pattern for skills WITHOUT existing arguments (review, pr-import, explore):**

Add a new argument section:

```markdown
## Arguments (Optional)

This skill accepts an optional `--profile <name>` argument to override execution profile selection.

Example: `/aitask-review --profile fast`

If provided, parse the profile name and store as `profile_override`. If not provided, set `profile_override` to null.
```

**B. Pass parameters to procedure call**

In Step 0a (or Step 3b for explore), update the procedure call to pass the new parameters:

Change from:
```
Execute the **Execution Profile Selection Procedure** (see `execution-profile-selection.md`).
```

To:
```
Execute the **Execution Profile Selection Procedure** (see `execution-profile-selection.md`) with:
- `skill_name`: `"pick"` (or `"fold"`, `"review"`, etc.)
- `profile_override`: the value parsed from `--profile` argument (or null)
```

#### Per-skill details:

1. **aitask-pick** (`.claude/skills/aitask-pick/SKILL.md`)
   - Has Step 0b with numeric argument (task ID)
   - Add pre-parse step before Step 0b to extract `--profile`
   - Example: `/aitask-pick --profile fast 42` or `/aitask-pick 42 --profile fast`
   - `skill_name`: `"pick"`

2. **aitask-fold** (`.claude/skills/aitask-fold/SKILL.md`)
   - Has Step 0b with comma/space-separated task IDs
   - Add pre-parse step before Step 0b
   - Example: `/aitask-fold --profile fast 106,108` or `/aitask-fold 106,108 --profile fast`
   - `skill_name`: `"fold"`

3. **aitask-review** (`.claude/skills/aitask-review/SKILL.md`)
   - No existing arguments
   - Add Arguments section
   - Example: `/aitask-review --profile fast`
   - `skill_name`: `"review"`

4. **aitask-pr-import** (`.claude/skills/aitask-pr-import/SKILL.md`)
   - No existing arguments (or has PR URL argument — check)
   - Add/update Arguments section
   - Example: `/aitask-pr-import --profile fast`
   - `skill_name`: `"pr-import"`

5. **aitask-revert** (`.claude/skills/aitask-revert/SKILL.md`)
   - Has optional numeric argument (task ID)
   - Add pre-parse step
   - Example: `/aitask-revert --profile fast 42`
   - `skill_name`: `"revert"`

6. **aitask-explore** (`.claude/skills/aitask-explore/SKILL.md`)
   - Profile selection is deferred to Step 3b
   - No existing arguments
   - Add Arguments section, pass to Step 3b procedure call
   - Example: `/aitask-explore --profile fast`
   - `skill_name`: `"explore"`

### 2. Update Codex Wrappers (`.agents/skills/`)

For each of the 6 skills, update the Arguments section in `.agents/skills/aitask-<name>/SKILL.md`.

Current pattern:
```markdown
## Arguments
Accepts an optional task ID: `16` (parent) or `16_2` (child). Without argument, follows interactive selection.
```

Add `--profile` to the Arguments section:
```markdown
## Arguments
Accepts an optional task ID: `16` (parent) or `16_2` (child). Without argument, follows interactive selection.
Optional `--profile <name>` to override execution profile selection. Example: `/aitask-pick --profile fast 16`.
```

For skills without existing arguments (review, pr-import, explore), add:
```markdown
## Arguments
Optional `--profile <name>` to override execution profile selection. Example: `/aitask-review --profile fast`.
```

### 3. Update OpenCode Wrappers (`.opencode/skills/`)

Same changes as Codex wrappers, in `.opencode/skills/aitask-<name>/SKILL.md`.

### 4. Verify

- Read each updated core skill to verify `--profile` parsing and procedure call are consistent
- Read each wrapper to verify Arguments section mentions `--profile`
- Test manually: invoke `/aitask-pick --profile fast` to verify override works

## Files to Modify

**Core (6 files):**
- `.claude/skills/aitask-pick/SKILL.md`
- `.claude/skills/aitask-fold/SKILL.md`
- `.claude/skills/aitask-review/SKILL.md`
- `.claude/skills/aitask-pr-import/SKILL.md`
- `.claude/skills/aitask-revert/SKILL.md`
- `.claude/skills/aitask-explore/SKILL.md`

**Codex wrappers (6 files):**
- `.agents/skills/aitask-pick/SKILL.md`
- `.agents/skills/aitask-fold/SKILL.md`
- `.agents/skills/aitask-review/SKILL.md`
- `.agents/skills/aitask-pr-import/SKILL.md`
- `.agents/skills/aitask-revert/SKILL.md`
- `.agents/skills/aitask-explore/SKILL.md`

**OpenCode wrappers (6 files):**
- `.opencode/skills/aitask-pick/SKILL.md`
- `.opencode/skills/aitask-fold/SKILL.md`
- `.opencode/skills/aitask-review/SKILL.md`
- `.opencode/skills/aitask-pr-import/SKILL.md`
- `.opencode/skills/aitask-revert/SKILL.md`
- `.opencode/skills/aitask-explore/SKILL.md`

## Reference Files

- `.claude/skills/task-workflow/execution-profile-selection.md` — updated procedure with Input params (from t426_2)
- Existing skill SKILL.md files for argument parsing patterns

## Final Implementation Notes
- **Actual work done:** Added `--profile <name>` argument parsing to all 6 interactive skills (pick, fold, review, pr-import, revert, explore) and updated their procedure calls to pass `skill_name` and `profile_override`. Updated all 12 wrapper files (6 Codex + 6 OpenCode) to document `--profile` in their Arguments sections. Exactly as planned.
- **Deviations from plan:** aitask-revert originally used "Step 0" for profile selection — renamed to "Step 0a" to be consistent with other skills, and added "Step 0 (pre-parse)" before it. Also updated a downstream reference ("Step 0" → "Step 0a") in the context variables section. Added `--profile` to revert's formal Arguments section (not just the pre-parse step). For pr-import, the core skill had no formal Arguments section — added a new `## Arguments (Optional)` section (the wrappers already documented PR URL args).
- **Issues encountered:** None. All 18 files edited cleanly.
- **Key decisions:** Used two patterns consistently: Pattern A (pre-parse step) for skills with existing arguments (pick, fold, revert), Pattern B (new Arguments section) for skills without (review, pr-import, explore). For explore, the `--profile` is parsed at the top but passed through to Step 3b (deferred profile selection), not Step 0a.
- **Notes for sibling tasks:** t426_4 (auto-select skills: pickrem, pickweb) should follow a similar pattern but targeting the auto-select procedure. The `--profile` argument is position-independent — it can appear anywhere in the argument string. All wrapper files follow the same pattern: append a line documenting `--profile` to the existing Arguments section.
