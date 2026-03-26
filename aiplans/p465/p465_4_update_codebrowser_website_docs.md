---
Task: t465_4_update_codebrowser_website_docs.md
Parent Task: aitasks/t465_launch_qa_from_codebrowser.md
Sibling Tasks: aitasks/t465/t465_1_*.md, aitasks/t465/t465_2_*.md, aitasks/t465/t465_3_*.md
Archived Sibling Plans: aiplans/archived/p465/p465_*_*.md
Worktree: (current branch)
Branch: (current branch)
Base branch: main
---

# Plan: Update codebrowser website documentation

## Step 1: Update reference.md — Application shortcuts

File: `website/content/docs/tuis/codebrowser/reference.md`, line ~22 (after `h` row)

Add row:
```
| `H` | Open history screen navigated to the task at cursor | Global (requires annotated line) |
```

## Step 2: Update reference.md — History Screen shortcuts

File: `website/content/docs/tuis/codebrowser/reference.md`, line ~36 (after `s` row)

Add row:
```
| `a` | Launch QA agent for the selected task | History detail |
```

## Step 3: Update reference.md — Environment Variables

File: `website/content/docs/tuis/codebrowser/reference.md`, line ~119

Update TERMINAL description:
```
| `TERMINAL` | Auto-detected | Terminal emulator for launching code agents (when pressing `e` or `a`) |
```

## Step 4: Add how-to section — Navigate from Code to Task History

File: `website/content/docs/tuis/codebrowser/how-to.md`, after "How to Launch Explain from the Browser" section

```markdown
### How to Navigate from Code to Task History

When viewing annotated code, you can jump directly to a specific task in the history screen:

1. Navigate to a line annotated with a task ID
2. Press **H** (capital H) to open the history screen, pre-navigated to that task
3. The history detail pane shows the full task info: commits, affected files, child tasks, etc.
4. Press **h** or **Escape** to return to the code browser

If the detail pane is open, **H** uses its current task. Otherwise, it resolves the task from the annotation at the cursor line. This is the reverse of the existing flow where you press **Enter** on an affected file in history to open it in the browser.
```

## Step 5: Add how-to section — Launch QA from History

File: `website/content/docs/tuis/codebrowser/how-to.md`, after "How to Browse Completed Tasks" section

```markdown
### How to Launch QA from the History Screen

You can run QA analysis on any completed task directly from the history screen:

1. Press **h** to open the history screen
2. Select a completed task from the list
3. Press **a** to launch the configured QA agent for that task
4. A terminal opens with the `/aitask-qa` skill pre-loaded for the selected task
5. If no terminal is detected, the codebrowser suspends and runs QA in the current terminal

The QA agent uses the model configured for the `qa` operation in `ait settings` (Agent Defaults tab). By default, this is `claudecode/sonnet4_6`.
```

## Verification

- `cd website && hugo build --gc --minify` builds without errors
- New sections render correctly in generated output
- Links resolve (no broken relref)

## Final Implementation Notes
- **Actual work done:** All 5 steps implemented as planned. Added `H` and `a` shortcut rows to reference.md, updated TERMINAL env var description, added two new how-to sections (Navigate from Code to Task History, Launch QA from History).
- **Deviations from plan:** Corrected the `H` shortcut description during plan verification — original plan (from task file) said "requires detail pane with task" but per p465_2's actual implementation, `H` resolves from annotation at cursor when detail pane is not open. Updated to "requires annotated line".
- **Issues encountered:** None.
- **Key decisions:** Kept how-to sections concise and consistent with existing section style.
- **Notes for sibling tasks:** This is the final child task (t465_4). All t465 children are now complete.
