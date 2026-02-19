---
priority: high
effort: medium
depends: [t176_1]
issue_type: feature
status: Ready
labels: [web_site]
created_at: 2026-02-19 11:03
updated_at: 2026-02-19 11:03
---

## Context
This is the second child task of t176 (Create Web Site). After the Hugo site scaffold is set up (t176_1), we need to migrate all existing documentation from `docs/` into Hugo content pages with proper Docsy frontmatter.

The project has 7 documentation files in `docs/`:
- `board.md` — TUI Kanban board guide (~555 lines)
- `commands.md` — Full CLI command reference (~511 lines)
- `development.md` — Architecture, internals, release process (~200 lines)
- `installing-windows.md` — Windows/WSL install guide (~100 lines)
- `skills.md` — Claude Code skills reference (~400 lines)
- `task-format.md` — Task file YAML frontmatter schema (~100 lines)
- `workflows.md` — End-to-end workflow guides (~350 lines)

Each needs to be adapted with Docsy frontmatter and placed in `website/content/docs/`.

## Key Files to Create

1. **`website/content/docs/commands.md`** — Adapted from `docs/commands.md` (weight: 10)
2. **`website/content/docs/workflows.md`** — Adapted from `docs/workflows.md` (weight: 20)
3. **`website/content/docs/skills.md`** — Adapted from `docs/skills.md` (weight: 30)
4. **`website/content/docs/task-format.md`** — Adapted from `docs/task-format.md` (weight: 40)
5. **`website/content/docs/board.md`** — Adapted from `docs/board.md` (weight: 50)
6. **`website/content/docs/development.md`** — Adapted from `docs/development.md` (weight: 60)
7. **`website/content/docs/installing-windows.md`** — Adapted from `docs/installing-windows.md` (weight: 70)
8. **`website/content/about/_index.md`** — About page with project info

## Reference Files for Patterns

- `docs/commands.md` — source file with most internal cross-links
- `docs/board.md` — largest source file, has `<!-- SCREENSHOT -->` comments
- `website/content/docs/_index.md` — created in t176_1, shows the Docsy frontmatter pattern
- `website/hugo.toml` — created in t176_1, site configuration

## Implementation Plan

### Step 1: Create adapted docs with frontmatter
For each of the 7 docs files:
1. Read the source file from `docs/`
2. Add Docsy frontmatter at the top:
```yaml
---
title: "Full Title"
linkTitle: "Short Title"
weight: <number>
description: "Brief description for SEO and section listings"
---
```
3. Remove the `# H1 Title` line (Docsy renders the `title` frontmatter as H1)
4. Keep all other content unchanged
5. Write to `website/content/docs/<filename>`

### Frontmatter for each file:

**commands.md** (weight: 10):
```yaml
---
title: "Command Reference"
linkTitle: "Commands"
weight: 10
description: "Complete CLI reference for all ait subcommands"
---
```

**workflows.md** (weight: 20):
```yaml
---
title: "Workflow Guides"
linkTitle: "Workflows"
weight: 20
description: "End-to-end workflow guides for common aitasks operations"
---
```

**skills.md** (weight: 30):
```yaml
---
title: "Claude Code Skills"
linkTitle: "Skills"
weight: 30
description: "Reference for all Claude Code slash-command skills"
---
```

**task-format.md** (weight: 40):
```yaml
---
title: "Task File Format"
linkTitle: "Task Format"
weight: 40
description: "YAML frontmatter schema and conventions for task files"
---
```

**board.md** (weight: 50):
```yaml
---
title: "Kanban Board"
linkTitle: "Board"
weight: 50
description: "TUI Kanban board for visualizing and managing tasks"
---
```

**development.md** (weight: 60):
```yaml
---
title: "Development Guide"
linkTitle: "Development"
weight: 60
description: "Architecture, internals, and release process"
---
```

**installing-windows.md** (weight: 70):
```yaml
---
title: "Windows & WSL Installation"
linkTitle: "Windows/WSL"
weight: 70
description: "Guide for installing and running aitasks on Windows via WSL"
---
```

### Step 2: Update internal cross-links
In the original docs, files link to each other using patterns like `(docs/commands.md#ait-setup)`. In Hugo, these need to be relative to the content directory. Update:
- `docs/commands.md` → `../commands/` or `../commands/#section`
- `docs/workflows.md` → `../workflows/`
- etc.

Search all content files for links matching `docs/*.md` and update to Hugo-relative paths.

### Step 3: Create About page
Create `website/content/about/_index.md`:
```yaml
---
title: "About"
linkTitle: "About"
weight: 30
menu:
  main:
    weight: 30
---
```
Include: project description, author info (GitHub: https://github.com/beyondeye, X/Twitter: DElyasy72333), license summary (MIT + Commons Clause), and link to the GitHub repo.

### Step 4: Verify
```bash
cd website
hugo server
```
Check each page renders correctly and internal links work.

## Verification Steps

1. All 7 doc pages render in the sidebar navigation in correct order
2. Each page shows its title from frontmatter (not a duplicate H1)
3. Internal cross-links between docs work correctly
4. About page accessible from top navigation
5. No broken links or missing content
6. `hugo server` runs without warnings about missing pages
