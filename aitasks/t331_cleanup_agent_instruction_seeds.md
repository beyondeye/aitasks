---
priority: medium
effort: low
depends: []
issue_type: chore
status: Ready
labels: [geminicli, codex, opencode]
created_at: 2026-03-08 12:00
updated_at: 2026-03-08 12:00
---

Clean up agent-specific instruction seed files to remove redundant content. Only the Agent Identification section should remain as the agent-specific layer; other sections (shared conventions header, skills location) are either redundant with Layer 1 or unnecessary.

## Changes

### 1. `seed/geminicli_instructions.seed.md`
- Remove the first paragraph referencing `seed/aitasks_agent_instructions.seed.md` (the header/preamble before `## Skills`)
- Remove the `## Skills` section entirely
- Keep only the `## Agent Identification` section

### 2. `seed/codex_instructions.seed.md`
- Keep only the `## Agent Identification` section
- Remove all other sections

### 3. `seed/opencode_instructions.seed.md`
- Keep only the `## Agent Identification` section
- Remove all other sections

## Reference Files

- `seed/geminicli_instructions.seed.md`
- `seed/codex_instructions.seed.md`
- `seed/opencode_instructions.seed.md`
- `seed/aitasks_agent_instructions.seed.md` (Layer 1 shared file — for context)

## Verification

```bash
# Check each file contains only Agent Identification
grep -c "^##" seed/geminicli_instructions.seed.md  # should be 1
grep -c "^##" seed/codex_instructions.seed.md       # should be 1
grep -c "^##" seed/opencode_instructions.seed.md    # should be 1

# Ensure Agent Identification is present in each
grep "Agent Identification" seed/geminicli_instructions.seed.md
grep "Agent Identification" seed/codex_instructions.seed.md
grep "Agent Identification" seed/opencode_instructions.seed.md
```
