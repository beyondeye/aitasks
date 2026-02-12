---
Task: t99_2_doc_utility_commands_and_skills.md
Parent Task: aitasks/t99_update_scripts_and_skills_docs.md
---

# Plan: t99_2 — Document Utility Commands and Skills

## Scope
Document `ait setup`, `ait board`, `ait stats`, `ait clear-old` commands and `/aitask-stats`, `/aitask-cleanold` skills.

## Steps
- [x] Read `aiscripts/aitask_board.sh` (37 lines)
- [x] Read `aiscripts/aitask_stats.sh` (732 lines)
- [x] Read `aiscripts/aitask_clear_old.sh` (427 lines)
- [x] Read `aiscripts/aitask_setup.sh` (389 lines)
- [x] Read `.claude/skills/aitask-stats/SKILL.md`
- [x] Read `.claude/skills/aitask-cleanold/SKILL.md`
- [x] Write snippet file with all 6 documentation sections

## Final Implementation Notes
- **Actual work done:** Wrote 148-line documentation snippet covering 4 commands and 2 skills. `ait setup` placed first as it's the first command users run. `ait stats` documented with all 7 statistic types and CSV export format.
- **Deviations from plan:** Reordered sections to put `ait setup` first per user feedback. Removed reference to `ait setup` from `ait board` section since setup is a general post-install step.
- **Issues encountered:** None.
- **Key decisions:** `ait setup` documented as a guided flow (numbered steps describing what happens at each stage) since it's an interactive installer. `ait board` kept brief since it's a launcher for the Python TUI.
- **Notes for sibling tasks:** Consistent format with t99_1: numbered lists for interactive/guided flows, options tables for CLI flags, feature bullet lists for skills. The `ait setup` section should appear early in the Command Reference when consolidated.
