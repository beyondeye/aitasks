---
Task: t276_2_skills_docs_peripheral.md
Parent Task: aitasks/t276_ambiguous_codeagent_names.md
Sibling Tasks: aitasks/t276/t276_1_core_scripts_configs_tests.md
Archived Sibling Plans: aiplans/archived/p276/p276_1_core_scripts_configs_tests.md
Worktree: (none — working on current branch)
Branch: (current branch)
Base branch: main
---

# Plan: t276_2 — Skills, documentation, and peripheral scripts rename

## Goal
Propagate the `claude` → `claudecode` and `gemini` → `geminicli` agent identifier renames to all skill definitions, documentation, and any remaining references across the repo. Depends on t276_1 being complete.

## Steps

### 1. Update `.claude/skills/task-workflow/SKILL.md`
- Lines 195-201: Agent detection section — update the agent list and examples:
  - `claude`, `gemini`, `codex`, `opencode` → `claudecode`, `geminicli`, `codex`, `opencode`
  - Example `claude/opus4_6` → `claudecode/opus4_6`
  - Example `claude/claude-opus-4-6` → `claudecode/claude-opus-4-6`
  - `models_<agent>.json` pattern reference (filename convention stays same, just the agent value changes)

### 2. Update `.claude/skills/aitask-refresh-code-models/SKILL.md`
- Line 16: filename extraction examples
- Lines 136, 144-145: git add/commit example paths (`models_claude.json` → `models_claudecode.json`)
- Lines 50-53: Research query examples — these refer to LLM products (Anthropic Claude, Google Gemini), NOT CLI tools. Keep the research queries but update any references to CLI agent names.

### 3. Scan and update other skill files
- Check all `.claude/skills/*/SKILL.md` for agent string references
- Focus on skills that reference `models_claude`, `claude/opus4_6`, or similar patterns

### 4. Update CLAUDE.md
- Review for any agent identifier references that need updating
- Note: CLAUDE.md mostly uses full product names ("Claude Code", "Gemini CLI") not short identifiers

### 5. Scan `.gemini/`, `.opencode/`, `.codex/` configs
- Check if any of these tool config directories contain agent name references that need updating
- These are secondary tool integrations — changes should mirror the Claude Code skill updates

### 6. Scan website content
- Search `website/content/` for stale agent identifier references
- Update any occurrences found

### 7. Final repo-wide grep
- `grep -rn 'models_claude\b\|models_gemini\b'` — should find nothing active
- `grep -rn '"claude/' --include='*.md' --include='*.sh' --include='*.py' --include='*.json'` — review hits

## Verification
- Read updated skill files to confirm consistency
- Grep for stale references across the entire repo
- Verify no false positives (LLM model references like "Claude" in prose should be kept)

## Step 9 (Post-Implementation)
After implementation: review, commit, archive, push per task-workflow.
