---
Task: t314_missing_agent_attrib_for_wrap.md
Branch: main
---

## Summary

Extract the agent attribution logic (recording `implemented_with` in task frontmatter) from inline code in task-workflow into a shared procedure, and add references to all skills that were missing it: aitask-wrap, aitask-pickrem, aitask-pickweb, and aitask-web-merge.

## Implementation Plan

1. Add "Agent Attribution Procedure" to `procedures.md` with full detection logic
2. Move attribution in task-workflow from Step 4 (too early for Codex plan mode) to Step 7 (start of implementation)
3. Add procedure references to aitask-wrap, aitask-pickrem, aitask-pickweb
4. Update aitask-pickweb completion marker JSON to include `implemented_with` field
5. Update aitask-web-merge to apply `implemented_with` from marker before archival

## Final Implementation Notes

- **Actual work done:** Created shared Agent Attribution Procedure in procedures.md. Moved attribution from task-workflow Step 4 to Step 7. Added references in 4 skills: aitask-wrap (Step 4a), aitask-pickrem (Step 8), aitask-pickweb (Step 6 + completion marker JSON), aitask-web-merge (Step 5).
- **Deviations from plan:** Originally planned to keep attribution in Step 4, but user feedback clarified it must happen after plan mode exit (Codex CLI constraint). Moved to implementation step in all skills.
- **Issues encountered:** None.
- **Key decisions:** For pickweb (no cross-branch ops), agent string is stored in completion marker JSON and applied by web-merge during archival. For wrap (no plan mode phase), attribution happens right after task creation.
