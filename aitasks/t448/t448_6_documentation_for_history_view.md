---
priority: low
effort: low
depends: [t448_5]
issue_type: documentation
status: Implementing
labels: [aitask_board, task-archive, website]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-24 09:00
updated_at: 2026-03-25 12:11
---

## Context

This is child task 6 of t448 (Completed Tasks History View in Codebrowser). It updates the website documentation to cover the new Completed Tasks History feature in the codebrowser.

Depends on t448_5 (all code implementation complete).

## Key Files to Modify
- `website/content/docs/tuis/codebrowser/_index.md` — add new section
- `website/content/docs/tuis/codebrowser/reference.md` — update keybinding table
- `website/content/docs/tuis/codebrowser/how-to.md` — add how-to section

## Reference Files
- `website/content/docs/tuis/codebrowser/_index.md` — existing codebrowser docs structure
- `website/content/docs/tuis/codebrowser/reference.md` — existing keyboard shortcuts reference
- `website/content/docs/tuis/codebrowser/how-to.md` — existing how-to sections

## Implementation

### _index.md Updates

Add a new section "Viewing Completed Task History" after the "Understanding Annotations" section:

- Describe the feature: press `h` to open the history screen
- Explain the two-pane layout: task list (left) + task details (right)
- Cover key features:
  - Reverse-chronological task list ordered by commit history
  - Chunked loading with "Load more" button
  - Recently opened tasks (persistent across sessions)
  - Task details: metadata, commit links, affected files
  - Sibling task browsing via modal dialog
  - Task/plan content toggle with `v`
  - File navigation: select affected file to open in codebrowser
  - State preservation when switching between views

### reference.md Updates

Add to the keyboard shortcuts table:
- `h` — Toggle completed tasks history view
- Within history screen:
  - `h` / `Escape` — Return to code browser
  - `v` — Toggle task/plan view
  - `s` — Open sibling task picker (on child tasks)
  - `Tab` — Cycle focus between panes

### how-to.md Updates

Add a "How to Browse Completed Tasks" section with step-by-step:
1. Open history: Press `h` in the codebrowser
2. Browse tasks: Scroll through the list, use "Load more" for older tasks
3. View task details: Select a task to see metadata, commit links, affected files
4. Open commit in browser: Focus a commit link and press Enter
5. Navigate to affected file: Focus a file and press Enter
6. Browse sibling tasks: Press `s` on a child task to open the sibling picker
7. Return to code browser: Press `h` or `Escape`

## Verification

1. Run `cd website && hugo build --gc --minify` — verify build succeeds with no errors
2. Review rendered pages for accuracy and completeness
3. Verify all internal `relref` links resolve correctly
4. Check that keybinding documentation matches actual implementation
