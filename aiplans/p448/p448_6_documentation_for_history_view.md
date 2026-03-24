---
Task: t448_6_documentation_for_history_view.md
Parent Task: aitasks/t448_archived_tasks_in_board.md
Sibling Tasks: aitasks/t448/t448_5_*.md
Archived Sibling Plans: aiplans/archived/p448/p448_*_*.md
Worktree: (none)
Branch: main
Base branch: main
---

# Plan: Documentation for history view

## Step 1: Update `_index.md`

File: `website/content/docs/tuis/codebrowser/_index.md`

Add new section after "Understanding Annotations":

### Viewing Completed Task History

Cover:
- Press `h` to open the history screen
- Two-pane layout: task list (left) + task details (right)
- Left pane: recently opened tasks (persistent) + all completed tasks (reverse chronological by commit date)
- Chunked loading with "Load more" button
- Right pane: metadata, commit links, affected files, task/plan body
- Sibling task browsing via `s` key
- File navigation: select affected file to return to codebrowser
- State preserved when switching between views

## Step 2: Update `reference.md`

File: `website/content/docs/tuis/codebrowser/reference.md`

Add to keyboard shortcuts table:
| Key | Action |
|-----|--------|
| `h` | Toggle completed tasks history view |
| `v` | Toggle task/plan view (in history detail) |
| `s` | Open sibling task picker (in history, child tasks) |

## Step 3: Update `how-to.md`

File: `website/content/docs/tuis/codebrowser/how-to.md`

Add "How to Browse Completed Tasks" section with steps:
1. Press `h` to open history
2. Browse tasks in the list, use "Load more" for older ones
3. Select a task to see details
4. Press Enter on a commit link to open in browser
5. Press Enter on an affected file to view in codebrowser
6. Press `s` on a child task to browse siblings
7. Use back button or `h`/Escape to return

## Verification

1. `cd website && hugo build --gc --minify` — no errors
2. Review rendered pages for accuracy
3. All relref links resolve

## Step 9: Post-Implementation

Archive child task and parent task, update plan, push.
