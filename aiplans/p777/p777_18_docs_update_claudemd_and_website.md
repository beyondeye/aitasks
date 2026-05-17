---
Task: t777_18_docs_update_claudemd_and_website.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Parent Plan: aiplans/p777_modular_pick_skill.md
Base branch: main
---

# Plan: t777_18 — Documentation update

## Scope

Add "Skill Template Authoring Conventions" to CLAUDE.md and user-facing docs to website. Per project rule: describe current state only, no "previously" framing.

## Step Order

1. **CLAUDE.md** — new subsection under "WORKING ON SKILLS / CUSTOM COMMANDS" covering: `.j2` source vs stub `SKILL.md`, per-profile dir naming, `{% if agent == … %}` pattern, `{% raw %}` for literal braces, `ait skill verify` contract, per-agent skill-path table, reference to `task-workflow/stub-skill-pattern.md`.
2. **website/content/docs/workflows/skill-templating.md** (new) — user-facing intro; examples of `ait skillrun pick --profile fast 42` and direct `/aitask-pick`; how profile dispatch works; how to use AgentCommandScreen per-run editor.
3. **README.md** — brief `ait skillrun` mention.
4. **Verify all references** — `ait skill verify` clean; all file paths match what t777_1..15 created.

## Critical Files

- `CLAUDE.md` (modify)
- `website/content/docs/workflows/skill-templating.md` (new)
- `README.md` (modify if appropriate)

## Pitfalls

- **"Previously…" wording forbidden** — describe positive current state only.
- **Internal cross-references** — verify every link resolves.

## Verification

`cd website && ./serve.sh` renders cleanly; fresh-context reader can understand the templating mechanism from CLAUDE.md alone.
