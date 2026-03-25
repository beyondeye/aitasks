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
| `H` | Open history navigated to the task in the detail pane | Global (requires detail pane with task) |
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

1. Press **d** to open the detail pane (if not already visible)
2. Navigate to a line annotated with a task ID
3. The detail pane shows the plan or task content for that annotation
4. Press **H** (capital H) to open the history screen, pre-navigated to that task
5. The history detail pane shows the full task info: commits, affected files, child tasks, etc.
6. Press **h** or **Escape** to return to the code browser

This is the reverse of the existing flow where you press **Enter** on an affected file in history to open it in the browser.
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

## Step 9: Post-Implementation

Follow standard archival workflow.
