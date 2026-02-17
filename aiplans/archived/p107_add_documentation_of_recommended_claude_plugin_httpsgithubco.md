---
Task: t107_add_documentation_of_recommended_claude_plugin_httpsgithubco.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

## Context

The aitasks framework's core philosophy is built around decomposing work into small, connected tasks. A key benefit of this approach is reduced context usage per task — making Claude Code effectively more intelligent. However, the documentation doesn't mention any tools for monitoring context usage in real time, which is critical for understanding when to decompose tasks further or when context is getting bloated.

[claude-hud](https://github.com/jarrodwatts/claude-hud) is a Claude Code plugin that displays real-time context usage. This task adds documentation recommending it.

## Plan

### 1. Add "Context Monitoring" section to `docs/workflows.md`

**File:** `docs/workflows.md`
**Location:** After the "Monitoring While Implementing" section (after line 142, before the `---` separator)

Add a new subsection "Context Monitoring" that:

- Explains why context monitoring matters (ties back to the core philosophy of small tasks)
- Recommends claude-hud with link
- Follows the existing pattern from "Recommended terminal emulators" (bold link + dash + description)

## Files Modified

1. `docs/workflows.md` — Added "Context Monitoring" section

## Verification

1. Check markdown renders correctly with proper link syntax
2. Verify anchor link `#context-monitoring` resolves correctly
3. Ensure claude-hud GitHub URL is valid

## Final Implementation Notes

- **Actual work done:** Added "Context Monitoring" subsection under "Monitoring While Implementing" in `docs/workflows.md`. Follows existing documentation patterns (bold link + description). User chose not to update README.md.
- **Deviations from plan:** Original plan included a README.md change; user requested only workflows.md be modified.
- **Issues encountered:** None.
- **Key decisions:** Placed section as a subsection (h3) under "Monitoring While Implementing" rather than a standalone top-level section, keeping it thematically grouped with the monitoring workflow.

## Step 9 Reference

Post-implementation: archive t107, delete folded task t113, release lock.
