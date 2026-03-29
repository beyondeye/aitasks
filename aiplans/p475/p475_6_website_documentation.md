---
Task: t475_6_website_documentation.md
Parent Task: aitasks/t475_monitor_tui.md
Sibling Tasks: aitasks/t475/t475_3_*.md, aitasks/t475/t475_4_*.md, aitasks/t475/t475_5_*.md
Archived Sibling Plans: aiplans/archived/p475/p475_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: Website Documentation

## Step 1: Create monitor/_index.md

File: `website/content/docs/tuis/monitor/_index.md`

Frontmatter: title "tmux Monitor", linkTitle "Monitor", weight 25.

Content: Introduction, launching (`ait monitor`), CLI options, layout walkthrough (header, attention section, code agents, TUI panel, content preview), basic navigation.

Follow pattern from `website/content/docs/tuis/board/_index.md`.

## Step 2: Create monitor/how-to.md

File: `website/content/docs/tuis/monitor/how-to.md`

Frontmatter: title "How-to Guides", weight 10.

Guides:
- Monitor a specific tmux session
- Triage idle agents (Confirm / Decide Later / Switch To)
- Spawn TUI windows from the monitor
- Configure idle threshold and refresh interval
- Use the TUI Switcher (`j`) from any TUI
- Add custom agent window patterns to config

Follow pattern from `website/content/docs/tuis/board/how-to.md`.

## Step 3: Create monitor/reference.md

File: `website/content/docs/tuis/monitor/reference.md`

Frontmatter: title "Reference", weight 20.

Content:
- Keyboard shortcuts table
- CLI options table (--session, --interval, --lines)
- Configuration reference (tmux.monitor section)
- Status indicators (colors and meanings)
- Pane categorization rules
- Attention queue behavior

Follow pattern from `website/content/docs/tuis/board/reference.md`.

## Step 4: Update TUI index page

File: `website/content/docs/tuis/_index.md`

- Add Monitor paragraph between existing TUI descriptions
- Add "TUI Switcher" subsection explaining the `j` shortcut

## Verification

- `cd website && hugo build --gc --minify` — no errors
- Pages appear in sidebar under TUIs
- Internal links resolve correctly

## Step 9 Reference

Commit, archive, push per task-workflow Step 9.
