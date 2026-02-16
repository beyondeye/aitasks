---
priority: medium
effort: high
depends: []
issue_type: documentation
status: Ready
labels: [docs]
created_at: 2026-02-16 12:59
updated_at: 2026-02-16 12:59
---

Restructure the monolithic README.md (~1155 lines) into a concise landing page with detailed documentation split into a `docs/` directory.

## Requirements

### Main README.md changes
- Keep: project intro, quick install, feature highlights, platform support, known issues, license
- Remove the current TOC from README.md
- Replace detailed sections with links to docs/ files, each with a brief 1-2 sentence summary explaining what the section covers and why the reader would want to read it
- The README.md should become a concise landing page (~150-200 lines)

### docs/ directory structure
Create separate doc files (each with its own internal TOC):
- `docs/commands.md` — Full CLI command reference (ait create, ls, update, board, stats, etc.)
- `docs/skills.md` — Claude Code skill reference (/aitask-pick, /aitask-create, /aitask-create2, /aitask-stats, /aitask-cleanold, /aitask-changelog, /aitask-explore)
- `docs/workflows.md` — Typical workflow guides (capturing ideas, task decomposition, GitHub issues, parallel dev, multi-tab, monitoring, follow-up tasks)
- `docs/task-format.md` — Task file format, YAML frontmatter, customizing task types
- `docs/development.md` — Architecture, directory layout, library scripts, modifying/testing, release process
- `docs/installing-windows.md` — Dedicated Windows/WSL installation guide covering: WSL installation, running install from WSL shell, Claude Code installation from WSL, Warp terminal with WSL integration, VS Code WSL extension, `gh auth login` prerequisite

### Each docs/ file should have
- Its own Table of Contents at the top
- Clear section headings
- Self-contained content (no need to read other files for context)

### Content additions (while restructuring)
- Add `/aitask-explore` skill documentation to docs/skills.md
- Add `gh auth login` prerequisite to installation docs
- Add Windows/WSL specific installation details (from existing task t106 content)

### What NOT to do
- Don't change the actual content/meaning of existing documentation — just reorganize
- Don't remove information — ensure everything from the current README ends up in the appropriate docs/ file
- Don't update CHANGELOG.md (that's a separate task)

### Desync prevention
- All links from README.md to docs/ files should use relative paths
- Add a note in the Development section about keeping docs in sync when adding new features

## References
- Current README.md (source of content)
- .claude/skills/aitask-explore/SKILL.md (for explore skill documentation)
- Task t106 (Windows install gaps — can be closed after this task)
- Task t129_5 (document aitask-explore — can be closed after this task)
