---
priority: medium
effort: low
depends: [t276_1]
issue_type: bug
status: Implementing
labels: []
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-02 19:52
updated_at: 2026-03-02 20:09
---

Update all SKILL.md files, CLAUDE.md, website docs, and peripheral scripts to use the new agent identifiers (claudecode/geminicli instead of claude/gemini).

## Context
Child task 1 (t276_1) renames the core agent identifiers in scripts and configs. This task propagates those changes to all documentation, skill definitions, and any remaining references. Depends on t276_1 being done first so the new names are established.

## Key Files to Modify

### Skill Files
- `.claude/skills/task-workflow/SKILL.md` — Lines 195-201: Agent detection instructions. Change:
  - `claude`, `gemini`, `codex`, `opencode` list → `claudecode`, `geminicli`, `codex`, `opencode`
  - Example `claude/opus4_6` → `claudecode/opus4_6`
  - Example `claude/claude-opus-4-6` → `claudecode/claude-opus-4-6`
- `.claude/skills/aitask-refresh-code-models/SKILL.md` — Multiple references:
  - Line 16: filename extraction examples (`models_claude.json → claude` → `models_claudecode.json → claudecode`)
  - Lines 136, 144-145: git add/commit examples with model filenames
  - Lines 50-53: Research query examples (these refer to the LLM products, NOT the CLI tools — review whether they need changes)

### Documentation
- `CLAUDE.md` — Review for any agent identifier references (mostly uses full product names already, may not need changes)
- Website content files under `website/content/docs/` — search for stale agent identifier references

### Peripheral Scripts (review needed)
- `aiscripts/aitask_review_detect_env.sh` — Lines 295-300: references `.claude/`, `.gemini/` DIRECTORY names — these are NOT being renamed (they are tool config directories, not agent identifiers). KEEP AS-IS.
- Scan all other `aiscripts/*.sh` for any remaining `models_claude` or agent string references

### Other Tool Configs (if applicable)
- `.gemini/skills/` and `.gemini/commands/` — check for agent name references
- `.opencode/skills/` — check for agent name references
- `.agents/skills/` and `.codex/prompts/` — check for agent name references

## Reference Files
- `aiscripts/aitask_codeagent.sh` (after t276_1 changes) — canonical source of new agent names
- Archived plan for t276_1 — see what patterns were established

## Implementation Plan
1. Update `.claude/skills/task-workflow/SKILL.md` agent detection section
2. Update `.claude/skills/aitask-refresh-code-models/SKILL.md` examples and filenames
3. Scan and update any other skill files with agent references
4. Review and update CLAUDE.md if needed
5. Scan website content for stale references
6. Scan `.gemini/`, `.opencode/`, `.codex/` skill/command files
7. Final grep across entire repo for stale `models_claude`, `models_gemini`, `"claude/"`, `"gemini/"` agent identifier patterns

## Verification
- `grep -rn 'models_claude\b\|models_gemini\b' --include='*.md' --include='*.sh' --include='*.py' --include='*.json' .` — should find nothing (or only archived task/plan references)
- Review changed files for consistency
