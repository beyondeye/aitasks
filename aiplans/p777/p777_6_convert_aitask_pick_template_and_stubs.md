---
Task: t777_6_convert_aitask_pick_template_and_stubs.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_6 — Convert `aitask-pick` (PILOT) across all 4 agents

## Scope

The PILOT conversion. Largest single-skill conversion (most profile-check blocks). Proves the cross-agent template + stub-dispatch model end-to-end. Subsequent per-skill children (t777_8..15) repeat the pattern.

## Step Order

1. **First implementation step — verify skill-loader auto-discovery** for all 4 agents. Confirm `.j2` files are NOT auto-discovered as skills. If they are, switch to `SKILL.md.tmpl` or `_template/SKILL.md.j2`.
2. **Author `.claude/skills/aitask-pick/SKILL.md.j2`** — copy current content; convert "Profile check:" blocks → `{% if profile.<key> %}…{% else %}…{% endif %}`; add `{% if agent == "..." %}` branches; scan + `{% raw %}` literal braces; frontmatter `name: aitask-pick-{{ profile.name }}`.
3. **Write per-agent stubs** at `.claude/skills/aitask-pick/SKILL.md`, `.agents/skills/aitask-pick/SKILL.md`, `.gemini/skills/aitask-pick/SKILL.md`, `.opencode/skills/aitask-pick/SKILL.md` — follow `task-workflow/stub-skill-pattern.md` (t777_3).
4. **Render + test** — `ait skill render pick --profile fast --agent claude` produces expected output; repeat for codex/gemini/opencode; manual stub-dispatch test inside live agent session.

## Critical Files

- `.claude/skills/aitask-pick/SKILL.md.j2` (new)
- `.claude/skills/aitask-pick/SKILL.md` (replace with stub)
- `.agents/skills/aitask-pick/SKILL.md` (replace with stub)
- `.gemini/skills/aitask-pick/SKILL.md` (replace with stub)
- `.opencode/skills/aitask-pick/SKILL.md` (replace with stub)

## Pitfalls

- **CLAUDE.md "Claude-first" rule** — `.j2` template lives ONLY in `.claude/skills/aitask-pick/`. Other agents only get stubs.
- **Profile-check block discovery** — grep `Profile check:` in the current SKILL.md to find all sites. Don't miss any.
- **Frontmatter name** — must equal the directory name `aitask-pick-<profile>` for the slash command to resolve.

## Verification

See task description (full Verification Steps). Manual stub-dispatch on all 4 agents is the critical end-to-end test.

## Notes for sibling tasks (t777_8..15)

After completing this pilot, document any quirks discovered (e.g. minijinja syntax limitations, agent-specific stub adjustments) in `task-workflow/stub-skill-pattern.md` for siblings to leverage.
