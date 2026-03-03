---
Task: t268_8_documentation.md
Parent Task: aitasks/t268/t268_code_agent_wrapper.md
Archived Sibling Plans: aiplans/archived/p268/p268_*_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan: t268_8 — Code Agent & Settings Documentation

## Context

The code agent wrapper system (t268) and settings TUI have been fully implemented across 7 sibling tasks but lack website documentation. This task creates website docs for both `ait codeagent` (command reference) and `ait settings` (TUI docs modeled on the board TUI structure). Folds t289 (document ait settings TUI) into this task.

## Implementation Steps

### 1. Fold t289 into t268_8
- [x] Update t289 status to Folded
- [x] Add `folded_tasks: [289]` to t268_8 frontmatter

### 2. Create `website/content/docs/commands/codeagent.md`
- [x] Command reference page (weight: 45) covering:
  - Agent string format and naming rules
  - Supported agents table (agent, binary, model flag)
  - Operations table with defaults
  - All 5 subcommands with usage and example output
  - Configuration: 4-level resolution chain, project + user config with JSON examples
  - Model configuration: JSON schema, verification scores
  - `implemented_with` metadata tracking
  - TUI integration (board picks via wrapper, codebrowser explains via wrapper)

### 3. Create `website/content/docs/tuis/settings/` (3 files)
- [x] `_index.md` — Tutorial introduction with screenshots (6 SVGs), 4-tab overview, navigation table
- [x] `how-to.md` — 8 step-by-step guides: change model, remove override, view models, configure board, edit profile, create profile, export, import
- [x] `reference.md` — Keyboard shortcuts, tabs table, operations table, config files table, full profile schema, model entry schema, export bundle format

### 4. Update existing index pages
- [x] `website/content/docs/tuis/_index.md` — Add Settings entry
- [x] `website/content/docs/commands/_index.md` — Add `ait codeagent` under Tools, `ait settings` under TUI, usage examples

### 5. Copy settings SVG images to website static
- [x] Copy 6 SVGs from `imgs/` to `website/static/imgs/` (where Hugo serves static files from)

### 6. Post-review changes
- [x] Update TUIs intro from "two" to "several"

### 7. Verify
- [x] Hugo build passes (`hugo build --gc --minify`) — 92 pages, 46 static files

## Final Implementation Notes
- **Actual work done:** Created 4 new documentation files (1 command reference + 3 settings TUI pages), updated 2 existing index pages, copied 6 SVG images to website static directory. Folded t289 into this task.
- **Deviations from plan:** Original task proposed `aidocs/codeagent.md` — user redirected to website docs instead. t289 was folded in to consolidate documentation work.
- **Issues encountered:** Settings SVG images were in `imgs/` (project root) but the `static-img` Hugo shortcode serves from `website/static/imgs/`. Needed to copy them.
- **Key decisions:** Used board TUI docs as the structural model (index + how-to + reference). Command reference page placed at weight 45 in docs/commands. Settings TUI docs placed at weight 30 in docs/tuis.
- **Notes for sibling tasks:** No remaining sibling tasks — this was the last child of t268.
