---
priority: low
effort: low
depends: [t465_2, t465_3]
issue_type: documentation
status: Ready
labels: [codebrowser, website]
created_at: 2026-03-25 12:58
updated_at: 2026-03-25 12:58
---

## Context

After implementing the two new codebrowser features (t465_2: navigate to history for current task via `H`, and t465_3: launch QA from history via `a`), the website documentation must be updated to reflect these additions.

Depends on t465_2 and t465_3 being complete.

## Key Files to Modify

- `website/content/docs/tuis/codebrowser/reference.md` — Add keyboard shortcuts to tables
- `website/content/docs/tuis/codebrowser/how-to.md` — Add how-to guide sections

## Reference Files for Patterns

- `reference.md` lines 10-22: Application keyboard shortcuts table — add `H` row
- `reference.md` lines 24-37: History Screen keyboard shortcuts table — add `a` row
- `reference.md` lines 115-122: Environment Variables table — update TERMINAL description
- `how-to.md` lines 94-105: "How to Launch Explain from the Browser" — pattern for the new how-to sections

## Implementation Plan

1. In `reference.md` Application table (after `h` row):
   - Add: `| \`H\` | Open history screen navigated to the task shown in the detail pane | Global (requires detail pane with task) |`
2. In `reference.md` History Screen table (after `s` row):
   - Add: `| \`a\` | Launch QA agent for the selected task | History detail |`
3. In `reference.md` Environment Variables table:
   - Update TERMINAL description to: `Terminal emulator for launching code agents (when pressing \`e\` or \`a\`)`
4. In `how-to.md`, after "How to Launch Explain from the Browser" section (~line 105):
   - Add "How to Navigate from Code to Task History" section
5. In `how-to.md`, after "How to Browse Completed Tasks" section:
   - Add "How to Launch QA from the History Screen" section

## Verification Steps

- `cd website && hugo build --gc --minify` should build without errors
- Verify new sections render correctly
- Check internal links resolve (especially relref links to /aitask-qa)
