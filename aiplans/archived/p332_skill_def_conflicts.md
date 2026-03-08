---
Task: t332_skill_def_conflicts.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: Consolidate Gemini CLI and Codex CLI Skill Wrappers (t332)

## Context

Gemini CLI reads skills from both `.gemini/skills/` and `.agents/skills/`, causing conflict warnings. Fixed by consolidating into `.agents/skills/` only with conditional agent-specific sections.

## Implementation

1. Updated all 17 `.agents/skills/aitask-*/SKILL.md` to unified wrappers with conditional prereqs/tool mapping:
   - Category A (both prereqs, 8 skills): pick, pickrem, pickweb, wrap, review, fold, explore, pr-import
   - Category B (codex prereqs only, 8 skills): changelog, create, explain, refresh-code-models, reviewguide-classify, reviewguide-import, reviewguide-merge, web-merge
   - Category C (no prereqs, 1 skill): stats

2. Copied `geminicli_tool_mapping.md` and `geminicli_planmode_prereqs.md` to `.agents/skills/`

3. Deleted all 17 `.gemini/skills/aitask-*/` directories (kept helper docs at `.gemini/skills/` for commands)

4. Updated `.github/workflows/release.yml`: codex_skills step packages all helper docs; gemini_skills step only copies helper docs + commands

5. Updated `install.sh`: codex staging includes all helper docs; gemini staging only stages helper docs (no skill wrappers)

6. Updated `.aitask-scripts/aitask_setup.sh`: codex setup installs all helper docs; gemini setup only installs helper docs + commands

7. Updated `tests/test_gemini_setup.sh`: tests now verify 0 skill wrappers in gemini_skills, fixed pre-existing assertion bug

## Final Implementation Notes
- **Actual work done:** Consolidated 17 Gemini CLI + 17 Codex CLI skill wrappers into 17 unified wrappers in `.agents/skills/`. Updated release pipeline, install script, and setup script. Fixed test assertions.
- **Deviations from plan:** None significant. The pre-existing test bug (checking for "Skills" instead of "Agent Identification" in geminicli seed) was also fixed.
- **Issues encountered:** geminicli_instructions.seed.md doesn't have a "## Skills" section, so test assertion was wrong.
- **Key decisions:** Kept `.gemini/skills/geminicli_*.md` originals alongside copies in `.agents/skills/` to avoid breaking `.gemini/commands/` which reference them via `@` syntax. Gemini commands remain completely unchanged per task requirement.
