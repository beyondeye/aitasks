---
Task: t777_3_stub_skill_design_and_gitignore.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_3 — Stub design + slash-dispatch validation + .gitignore

## Scope

Designs the canonical stub SKILL.md pattern that all per-skill conversions (t777_6, t777_8..15) follow. Critical step: validate that each of the 4 agents can programmatically slash-dispatch from inside a skill. If any agent cannot, document the fallback.

## Step Order

1. **Validate slash-dispatch per agent** — Author throwaway `_dispatch_test/SKILL.md` files for each of the 4 agents. Test that the agent runs bash AND invokes the second slash command. Record pass/fail matrix.
2. **Author canonical stub document** at `.claude/skills/task-workflow/stub-skill-pattern.md` — sections covering bash body, slash-dispatch syntax per agent, fallback for non-supporting agents.
3. **Decide on .gitignore strategy** for per-profile dirs. Recommended: rename `task-workflow/` → `task_workflow/` across all 4 agent trees (eliminates the hyphen-glob ambiguity). Document the trade-off in this plan file.
4. **Add `.gitignore` entries** for per-profile dirs:
   ```
   .claude/skills/*-*/
   .agents/skills/*-*/
   .gemini/skills/*-*/
   .opencode/skills/*-*/
   ```

## Critical Files

- `.claude/skills/task-workflow/stub-skill-pattern.md` (new)
- `.gitignore` (modify)
- Potentially: `task-workflow/` → `task_workflow/` rename across 4 agent trees + all internal references

## Pitfalls

- **Slash-dispatch unsupported in an agent** — fallback is the stub prints "Run `ait skillrun <skill> --profile <name>` from a shell" and exits. Degraded UX in that agent but not a blocker.
- **gitignore glob ambiguity** — `task-workflow/` has a hyphen. Rename to `task_workflow/` if needed; surface the rename as a documented decision.

## Verification

- 4-agent slash-dispatch matrix is documented.
- `.gitignore` matches `aitask-pick-fast/` but NOT `aitask-pick/` (test via `git check-ignore`).
- If rename executed: all references updated; no broken cross-references in stubs/templates.
