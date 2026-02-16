---
Task: t133_restructure_readme_into_docs.md
Worktree: none (working on current branch)
Branch: main
Base branch: main
---

# Plan: Restructure README into docs/ directory (t133)

## Context

The README.md has grown to ~1155 lines — a monolithic document covering everything from installation to architecture. The user wants to restructure it into a concise landing page with detailed documentation split into a `docs/` directory. Each docs file gets its own TOC. The main README.md drops its TOC and instead links to each doc section with a brief summary. A dedicated Windows/WSL installation guide is also requested.

## Implementation Steps

### Step 1: Create docs/ directory structure

Create the following files by extracting content from README.md:

| File | Source (README lines) | Content |
|------|----------------------|---------|
| `docs/commands.md` | Lines 155-643 | Full CLI command reference |
| `docs/skills.md` | Lines 645-849 | Claude Code skill reference + NEW /aitask-explore |
| `docs/workflows.md` | Lines 857-996 | Typical workflow guides |
| `docs/task-format.md` | Lines 998-1035 | Task file format |
| `docs/development.md` | Lines 1037-1143 | Architecture and development |
| `docs/installing-windows.md` | NEW | Windows/WSL installation guide |

### Step 2: Add /aitask-explore to docs/skills.md
### Step 3: Create docs/installing-windows.md
### Step 4: Add internal TOC to each docs/ file
### Step 5: Rewrite README.md as landing page
### Step 6: Add desync prevention note to docs/development.md

## Verification

1. All links from README.md to docs/ files resolve correctly
2. No content from the original README.md is lost
3. Each docs/ file has its own TOC
4. `/aitask-explore` is documented in docs/skills.md
5. `gh auth login` is mentioned in installation docs
6. Windows/WSL guide covers WSL install, Claude Code from WSL, terminal options
7. README.md is significantly shorter (~150-200 lines)

## Final Implementation Notes
- **Actual work done:** Restructured README.md (1155 lines → 142 lines) into a landing page + 6 docs files (1312 lines total). Created docs/commands.md, docs/skills.md, docs/workflows.md, docs/task-format.md, docs/development.md, and docs/installing-windows.md.
- **Deviations from plan:** Added a frontmatter fields table to docs/task-format.md that wasn't in the original README (enhancement). Added `explore_auto_continue` profile key to the profile settings table in docs/skills.md.
- **Key decisions:** Cross-references between docs files use relative paths (e.g., `commands.md#ait-create` from workflows.md). README.md uses `docs/` prefix for all links. Each docs file is self-contained with its own TOC.
- **Content additions:** /aitask-explore fully documented in docs/skills.md. Windows/WSL installation guide created with WSL setup, Claude Code from WSL, gh auth login, and terminal options. "Keeping Documentation in Sync" section added to docs/development.md.
