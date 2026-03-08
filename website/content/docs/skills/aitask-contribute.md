---
title: "/aitask-contribute"
linkTitle: "/aitask-contribute"
weight: 23
description: "Contribute local framework changes back to the upstream aitasks repository"
---

Contribute your local modifications and enhancements back to the upstream aitasks repository without creating a fork, branch, or pull request. The skill analyzes your changes against upstream, lets you select and group what to contribute, and automatically creates structured GitHub issues with full diffs, motivation, and scope — ready for the maintainer to import as an aitask.

**Usage:**
```
/aitask-contribute
```

> **Note:** Must be run from the project root directory. Requires the `gh` CLI installed and authenticated (`gh auth login`). See [Skills overview](..) for details.

## Step-by-Step

1. **Prerequisites check** — Verifies `gh` CLI is installed and authenticated. Detects contribution mode (clone/fork vs downstream project) and lists available contribution areas
2. **Area selection** — Choose which areas of the framework you modified: scripts, Claude skills, Gemini CLI, Codex CLI, OpenCode, website, or a custom path
3. **File discovery** — Scans selected areas for files that differ from upstream and presents them for selection
4. **Upstream diff + AI analysis** — Generates diffs for selected files and AI analyzes the changes: what changed semantically, whether changes are logically related or distinct, appropriate scope classification, and merge complexity
5. **Contribution grouping** — If multiple distinct change groups are identified, choose to split into separate contributions (one issue per group), keep as a single contribution, or create custom groupings
6. **Motivation and scope** — For each contribution group: confirm or edit the AI-proposed title, provide motivation for the change, select scope (bug fix, enhancement, new feature, documentation), and choose a merge approach
7. **Review, confirm, and create issue(s)** — Preview the full issue body, then create it on the upstream repository. Each issue includes embedded diffs, motivation, scope, and merge approach

## Key Capabilities

- **Two contribution modes** — Automatically detected from the repository structure:
  - *Clone/fork mode* — You're working directly in a clone or fork of the aitasks repository
  - *Downstream project mode* — You're working in a project that uses aitasks as a framework (installed via `ait setup`)

- **Contribution areas** — Pre-defined areas that map to framework directories: shell scripts (`.aitask-scripts/`), Claude Code skills (`.claude/skills/`), Gemini CLI (`.gemini/`), Codex CLI (`.agents/`, `.codex/`), OpenCode (`.opencode/`), and website (`website/`). Custom paths are also supported.

- **AI-powered change analysis** — Diffs are analyzed semantically to identify logical change groups, propose titles, assess merge complexity, and suggest appropriate scope classifications

- **Multi-contribution support** — When changes span multiple unrelated improvements, they can be split into separate GitHub issues — one per logical group — for cleaner upstream tracking

- **Contributor attribution** — When the created issue is later imported upstream via [`ait issue-import`](../../commands/issue-integration/#ait-issue-import), the contributor's identity is preserved. Implementation commits include `Co-authored-by` trailers crediting the original contributor

- **No fork required** — Unlike the traditional fork → branch → PR workflow, contributors simply make their modifications locally and let the skill handle the rest. This significantly lowers the barrier to contribution

## Workflows

For a full workflow guide covering the contribution lifecycle end-to-end (including issue import and PR import), see [Contribute and Manage Contributions](../../workflows/contribute-and-manage/).
