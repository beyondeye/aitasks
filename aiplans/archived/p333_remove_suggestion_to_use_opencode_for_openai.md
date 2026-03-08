---
Task: t333_remove_suggestion_to_use_opencode_for_openai.md
Worktree: (none - working on current branch)
Branch: main
Base branch: main
---

## Plan

Update the installation documentation so it no longer recommends OpenCode for OpenAI-model workflows and no longer documents the removed "script-heavy flows can require frequent approvals" Codex caveat.

### Files to Modify
- `website/content/docs/installation/known-issues.md` — remove the OpenCode recommendation subsection, remove the script-heavy approvals subsection, and trim references that only supported the deleted content
- `website/content/docs/installation/_index.md` — reword the Known Issues cross-reference so it no longer mentions OpenCode recommendations

### Verification
- Run `hugo --gc --minify` from `website/`
- Check that the installation docs still render and that the removed sections no longer appear

## Final Implementation Notes
- **Actual work done:** Removed the two obsolete Codex/OpenCode-related subsections from the installation Known Issues page and updated the installation landing page copy to describe the Known Issues link without mentioning OpenCode recommendations.
- **Deviations from plan:** None.
- **Issues encountered:** None.
- **Key decisions:** Kept the Known Issues page and cross-link in place because the page still documents active Claude Code and Codex CLI caveats.
- **Build verification:** `hugo --gc --minify` succeeded in `website/`.
