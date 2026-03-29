---
priority: medium
effort: medium
depends: [t475_5]
issue_type: documentation
status: Ready
labels: [aitask_monitor, tui, website]
created_at: 2026-03-29 10:58
updated_at: 2026-03-29 10:58
---

## Website Documentation

Create 3-page documentation for the tmux Monitor TUI and document the TUI Switcher widget, following the established TUI docs pattern.

### Context

The aitasks website uses Hugo/Docsy. Each TUI (board, codebrowser, settings) has a 3-page documentation structure: `_index.md` (overview), `how-to.md` (guides), `reference.md` (technical details). This task creates the same for the Monitor TUI and adds TUI Switcher docs.

### Key Files to Create

- `website/content/docs/tuis/monitor/_index.md` (weight: 25)
- `website/content/docs/tuis/monitor/how-to.md` (weight: 10)
- `website/content/docs/tuis/monitor/reference.md` (weight: 20)

### Key Files to Modify

- `website/content/docs/tuis/_index.md` — add monitor entry + TUI switcher section

### Key Files to Reference

- `website/content/docs/tuis/board/_index.md` — example overview page
- `website/content/docs/tuis/board/how-to.md` — example how-to page
- `website/content/docs/tuis/board/reference.md` — example reference page
- `website/content/docs/tuis/_index.md` — TUI index page to update

### Implementation Plan

#### 1. Monitor `_index.md` (Overview)

```yaml
---
title: "tmux Monitor"
linkTitle: "Monitor"
weight: 25
description: "TUI for monitoring tmux panes running Claude Code agents"
---
```

Content:
- Introduction: what the monitor does, when to use it
- Launching: `ait monitor`, CLI options (`--session`, `--interval`, `--lines`)
- Layout walkthrough: Header, Attention section, Code Agents, TUIs panel, Content Preview
- Basic usage: navigating, understanding status indicators

#### 2. Monitor `how-to.md` (Guides)

```yaml
---
title: "How-to Guides"
linkTitle: "How-to"
weight: 10
---
```

Guides:
- How to monitor a specific tmux session
- How to triage idle agents (Confirm / Decide Later / Switch To)
- How to spawn TUI windows from the monitor
- How to configure idle threshold and refresh interval
- How to use the TUI Switcher (`j` key) from any TUI
- How to add custom agent window patterns

#### 3. Monitor `reference.md` (Technical Reference)

```yaml
---
title: "Reference"
linkTitle: "Reference"
weight: 20
---
```

Content:
- Keyboard shortcuts table (all keybindings)
- CLI options table
- Configuration reference (`tmux.monitor` section in project_config.yaml)
- Status indicator colors (green=active, yellow=idle, gray=other)
- Pane categorization rules (agent prefixes, TUI names, other)
- Attention queue behavior

#### 4. Update TUI index page

Add monitor entry to `website/content/docs/tuis/_index.md`:
- Paragraph describing the Monitor TUI between codebrowser and settings sections
- New "TUI Switcher" subsection explaining the `j` shortcut available in all TUIs

### Verification

- Build website: `cd website && hugo build --gc --minify`
- Verify monitor pages appear in sidebar under TUIs
- Verify internal links work (`{{< relref >}}`)
- Check no broken frontmatter
