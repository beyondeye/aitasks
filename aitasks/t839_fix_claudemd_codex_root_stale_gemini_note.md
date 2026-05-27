---
priority: low
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [documentation]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-27 11:00
updated_at: 2026-05-27 12:43
---

## Origin

Spawned from t777_18 during Step 8b review.

## Upstream defect

- `CLAUDE.md:203 — "Codex CLI: \`.agents/skills/\` (shared with Gemini CLI)"`. The parenthetical "(shared with Gemini CLI)" is stale. Gemini's skills root is `.gemini/skills/` (see `.aitask-scripts/lib/agent_skills_paths.sh::agent_skill_root`); `.agents/skills/` is shared between codex and the future `agy` agent (t814 / t834), not gemini.

## Diagnostic context

Verified during t777_18 sibling-and-cross-task scan. The current `agent_skill_root` mapping in `.aitask-scripts/lib/agent_skills_paths.sh` is:
- claude → `.claude/skills`
- codex → `.agents/skills`
- gemini → `.gemini/skills`
- opencode → `.opencode/skills`

And `agent_shared_skills_root` declares only codex shares its root today (with the future `agy` agent per t814 / t834). The CLAUDE.md parenthetical predates t777 (last touched circa t691) and never picked up the actual shared-root semantics.

## Suggested fix

Change `CLAUDE.md:203` from:

```
- **Codex CLI:** `.agents/skills/` (shared with Gemini CLI); `.codex/` holds
```

to:

```
- **Codex CLI:** `.agents/skills/` (shared root: rendered variants carry an
  extra `-codex-` segment — see t834); `.codex/` holds
```

or simply drop the parenthetical entirely if the shared-root nuance is already covered by the new "Skill templating and per-profile dispatch" subsection added in t777_18.
