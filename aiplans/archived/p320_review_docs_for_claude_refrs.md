---
Task: t320_review_docs_for_claude_refrs.md
Worktree: (none — working on current branch)
Branch: (none — working on current branch)
Base branch: main
---

# Plan: Review docs for multi-agent references (t320)

## Summary

- Review `website/content/docs/` for legacy Claude-first wording now that the project supports multiple code agents.
- Genericize agent-agnostic docs while preserving intentionally Claude-specific content such as Claude Code Web, permissions, install steps, and configuration file names.
- Verify the Hugo docs build after the wording updates.

## Implementation Changes

- Updated onboarding and overview docs to describe aitasks as a multi-agent workflow rather than a Claude-only workflow.
- Rewrote generic workflow and skill pages to refer to `the agent`, `the skill`, or `your code agent` where the behavior is shared across Claude Code, Gemini CLI, Codex CLI, and OpenCode.
- Updated TUI docs for board and codebrowser to reflect that agent launches now go through the configured code agent rather than assuming Claude Code.
- Kept intentional Claude-specific pages and sections unchanged, including Claude Code Web workflow docs, Claude permission setup, known Claude-specific caveats, and Claude-specific model/config references.

## Test Plan

- Search `website/content/docs` for `claude|claude code|anthropic` and confirm remaining matches are intentional product-specific references.
- Run `hugo` from `website/` to verify the documentation site still builds cleanly.
- Spot-check the most edited pages for wording quality and command accuracy.

## Final Implementation Notes

- **Actual work done:** Updated 26 documentation pages under `website/content/docs/` to remove Claude-only narration from generic docs and align them with the current multi-agent architecture.
- **Deviations from plan:** Kept a few generic index/overview references that explicitly list supported agents, because those references are factual product descriptions rather than legacy Claude-only narration.
- **Issues encountered:** The task-data branch already had an unrelated user modification in `aitasks/t321/t321_2_issue_import_contributor_support.md`, so task archival needs to use path-specific git operations instead of the bulk archive helper that stages all task-data changes.
- **Key decisions:** Used neutral phrases like `code agent`, `agent session`, and `the skill` in shared docs; preserved Claude-specific wording only where it documents real product boundaries or file names.
- **Build verification:** `hugo` completed successfully in `website/` on 2026-03-08.
