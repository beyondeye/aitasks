---
priority: low
effort: low
depends: []
issue_type: chore
status: Ready
labels: [task_workflow, documentation]
created_at: 2026-04-21 12:29
updated_at: 2026-04-21 12:29
boardidx: 60
---

Mirror the 5 CLAUDE.md additions from t612 into the equivalent agent-instruction files for Codex CLI, OpenCode, and (if applicable) Gemini CLI, so that implicit behavior rules originally captured in Claude Code auto-memory apply regardless of which code agent is driving the task.

## Context & motivation

t612 consolidated 5 auto-memory entries into CLAUDE.md:
1. *Documentation Writing* — "Delete X, integrate into Y" = redirect cross-refs now
2. *TUI Conventions* — No auto-commit/push of project-level config from runtime TUIs
3. *Skill/Workflow Authoring Conventions* — Execution-profile keys vs. guard variables (reworded existing bullet)
4. *Planning Conventions* (new section) — Refactor duplicates before adding to them
5. *TUI Conventions* — Contextual-footer ordering: keep uppercase sibling adjacent to its lowercase primary

CLAUDE.md is Claude-Code-specific. Equivalent project-instructions files exist for other agents (assembled from seed files in `seed/`):
- `.codex/instructions.md` ← `seed/codex_instructions.seed.md` + `seed/aitasks_agent_instructions.seed.md`
- `.opencode/instructions.md` ← `seed/opencode_instructions.seed.md` + `seed/aitasks_agent_instructions.seed.md`
- `.gemini/` — currently has no instructions.md; check `seed/geminicli_instructions.seed.md` and decide whether to generate one

## Required changes

1. **Decide the source-of-truth layer.** The rules from entries 1-5 apply regardless of code agent, so they most likely belong in `seed/aitasks_agent_instructions.seed.md` (the shared seed) rather than each per-agent seed. Audit the shared seed and promote the 5 rules into it.
2. **Regenerate** `.codex/instructions.md` and `.opencode/instructions.md` from the updated seeds using whatever setup/regen tooling the framework provides (check `ait setup` or equivalent).
3. **Gemini check:** determine whether `.gemini/` needs a generated `instructions.md`. If yes, add it to the setup flow and generate.
4. **Verify** each regenerated file contains the 5 rules and does not contain Claude-specific references (e.g., remove mentions of "CLAUDE.md" in the seed and use a neutral reference).

## Acceptance

- [ ] 5 rules present in `seed/aitasks_agent_instructions.seed.md` (or equivalent shared seed)
- [ ] `.codex/instructions.md` regenerated and contains the 5 rules
- [ ] `.opencode/instructions.md` regenerated and contains the 5 rules
- [ ] Gemini CLI story decided (either instructions.md generated, or explicit non-goal documented)

## Origin

Extracted from the CLAUDE.md additions committed in t612 (see `git log CLAUDE.md`). The original auto-memory files were deleted during t612 archival.
