---
Task: t290_document_ait_codeagent.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# t290: Document ait codeagent on Website

## Context

Task t268 implemented the multi-agent code agent infrastructure (wrapper script, config files, TUI integration, Settings TUI). Its child t268_8 created initial website documentation including `commands/codeagent.md` and the Settings TUI docs. However, several TUI documentation pages still reference hardcoded "claude" instead of the codeagent wrapper, and cross-references between related pages are incomplete.

## Changes

### 1. Update board how-to: fix hardcoded "claude" reference

**File:** `website/content/docs/tuis/board/how-to.md` (lines ~274-277)

The "How to Pick a Task for Implementation" section currently says:
> The board launches `claude /aitask-pick <task_number>` in a terminal emulator

The board actually uses `ait codeagent invoke task-pick <num>` via the wrapper. Update to:
- Reference the code agent wrapper with a link to `commands/codeagent`
- Mention that the wrapper resolves which agent/model to use based on configuration
- Keep the rest of the section (workflow description, refresh behavior, disabled states) unchanged

### 2. Update codebrowser _index: make explain section agent-neutral

**File:** `website/content/docs/tuis/codebrowser/_index.md` (lines ~69-82)

**Change A:** The "Launching Claude Explain" heading and text hardcodes "Claude Code". Update to:
- Rename heading to "Launching an Explain Session"
- Reference the code agent wrapper for resolving which agent to use for the `explain` operation
- Mention the pre-flight binary check (the codebrowser verifies the agent binary is in PATH before launching)
- Keep the `/aitask-explain` skill reference

**Change B:** Add a codeagent cross-reference to the "See also" section:
- `[ait codeagent](relref to commands/codeagent)` — Configures which agent and model the code browser uses for explain sessions

### 3. Add Related section to codeagent.md

**File:** `website/content/docs/commands/codeagent.md` (after line 244)

Add a `## Related` section at the bottom with links to:
- `/aitask-refresh-code-models` skill
- Settings TUI (visual editor for agent config)
- Board TUI "How to Pick" section (uses `task-pick` operation)
- Code Browser (uses `explain` operation)

## Files Modified

| File | Change |
|------|--------|
| `website/content/docs/tuis/board/how-to.md` | Replace hardcoded `claude /aitask-pick` with codeagent wrapper reference |
| `website/content/docs/tuis/codebrowser/_index.md` | Rename heading, rewrite to agent-neutral, add codeagent to See also |
| `website/content/docs/commands/codeagent.md` | Add `## Related` cross-reference section |

## Verification

1. Build the website: `cd website && hugo build --gc --minify` (catches broken `relref` links)
2. Spot-check rendered pages for the three modified files

## Final Implementation Notes

- **Actual work done:** Updated three website documentation files to replace hardcoded "claude" references with the codeagent wrapper, and added cross-reference links between related pages (codeagent command, board TUI, codebrowser, settings TUI, refresh-models skill).
- **Deviations from plan:** None — all three planned changes implemented as specified.
- **Issues encountered:** None. The existing documentation was well-structured, making the edits straightforward.
- **Key decisions:** Used Hugo `relref` shortcodes for all internal links to ensure build-time validation. Chose `## Related` heading style (matching the skills page pattern) rather than inline `**See also:**` for the command page.
