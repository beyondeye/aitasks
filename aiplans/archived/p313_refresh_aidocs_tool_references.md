---
Task: t313_refresh_aidocs_tool_references.md
Created by: aitask-wrap (retroactive documentation)
---

## Summary

Updated the generated tooling references for Codex CLI and Gemini CLI in `aidocs/` to reflect current session capabilities, tool argument shapes, and version/date metadata.

## Files Modified

- `aidocs/codexcli_tools.md`
  - Reworked the document into clearer tool-group sections.
  - Updated generated timestamp and Codex CLI version metadata.
  - Expanded and normalized argument documentation for `web.run`, `functions.*`, and `multi_tool_use.parallel`.
- `aidocs/geminicli_tools.md`
  - Updated title/date/version metadata.
  - Restructured tool catalog into clearer categories.
  - Normalized argument descriptions and refreshed listed available skills.

## Probable User Intent

Keep `aidocs` tool-reference documentation accurate and current so skill/tool portability work between code agents can rely on up-to-date interface and capability references.

## Final Implementation Notes

- **Actual work done:** Refreshed two markdown tool reference files with updated content and structure for the current CLI sessions.
- **Deviations from plan:** N/A (retroactive wrap - no prior plan existed)
- **Issues encountered:** N/A (changes were already made before wrapping)
- **Key decisions:** Limited wrap scope to the two updated markdown references in `aidocs` and intentionally excluded new extraction scripts.
