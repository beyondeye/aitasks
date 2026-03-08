---
Task: t337_assign_proper_label_and_description_to_aitasks_repo.md
Worktree: (none - current branch)
Branch: main
Base branch: main
---

# Plan: Assign Proper Labels and Description to aitasks Repo

## Context

The aitasks GitHub repo (beyondeye/aitasks) currently has no description, no topics, and only the 9 default issue labels. This task sets up proper GitHub metadata based on what similar projects use.

## Research Summary

Analyzed 10 related repos. Key patterns:
- **Descriptions** are 1-2 sentences, lead with the project name, state what it does and for whom
- **Topics** typically include: `ai-agents`, `claude-code`, `cli`, `developer-tools`, `automation`, `orchestration`, `tui`
- **Issue labels** commonly add: `area:*` for components, `priority:*` for triage, and domain-specific types beyond defaults

## 1. Repository Description

**Set to:**
> File-based task management framework for AI coding agents — markdown tasks with YAML frontmatter, git-native, zero infrastructure. Works with Claude Code, Gemini CLI, OpenCode, and Codex CLI.

## 2. Repository Topics (18)

- `task-management` — core purpose
- `ai-agents`, `coding-agents` — target users
- `claude-code`, `gemini-cli`, `opencode`, `codex-cli` — supported agents
- `cli`, `bash` — tech stack
- `git` — file-based, git-native approach
- `tui` — board interface
- `developer-tools`, `automation` — category
- `orchestration` — workflow management
- `skills` — distinctive feature
- `kanban` — board-based task visualization
- `code-review`, `code-quality` — automated review guides and quality checks

## 3. Issue Labels Added (13 new)

**Issue type labels** (matching task_types.txt):
| Label | Color | Description |
|-------|-------|-------------|
| `feature` | `#1d76db` | New feature or capability |
| `chore` | `#ededed` | Maintenance or housekeeping |
| `performance` | `#d4c5f9` | Performance improvement |
| `refactor` | `#c2e0c6` | Code restructuring without behavior change |
| `test` | `#bfd4f2` | Test improvements or additions |

**Area labels** (key components):
| Label | Color | Description |
|-------|-------|-------------|
| `area: cli` | `#f9d0c4` | CLI dispatcher and scripts |
| `area: board` | `#f9d0c4` | TUI board (Python/Textual) |
| `area: skills` | `#f9d0c4` | Claude Code skills and agent commands |
| `area: workflow` | `#f9d0c4` | Task workflow and lifecycle |
| `area: website` | `#f9d0c4` | Documentation website (Hugo/Docsy) |

**Priority labels:**
| Label | Color | Description |
|-------|-------|-------------|
| `priority: high` | `#b60205` | Urgent — address soon |
| `priority: medium` | `#fbca04` | Normal priority |
| `priority: low` | `#0e8a16` | Nice to have |

## Final Implementation Notes
- **Actual work done:** Set repo description, 18 topics, and 13 new issue labels via `gh` CLI API calls. No code changes — all GitHub API operations.
- **Deviations from plan:** None. Plan was updated during review to add `opencode`, `codex-cli`, `kanban`, `code-review`, `code-quality` topics per user feedback.
- **Issues encountered:** None.
- **Key decisions:** Used `area: ` prefix (with space) for area labels to match conventions from MiniCodeMonkey/chief and gemini-cli-extensions/conductor. Colors chosen to visually group: areas (salmon), priorities (red/yellow/green), types (varied pastel).
