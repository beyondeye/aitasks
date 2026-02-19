---
title: "/aitask-review"
linkTitle: "/aitask-review"
weight: 70
description: "Review code using configurable review guides, then create tasks from findings"
---

Review code using configurable review guides, then create tasks from findings. This skill separates code quality review from implementation — first build something that works, then systematically review it for quality improvements.

**Usage:**
```
/aitask-review          # Interactive: choose scope and review guides
```

## Workflow Overview

1. **Define review scope** — Choose what to review: specific file paths, directories, or glob patterns; or select from recent commits (non-administrative commits are listed with pagination)
2. **Select review guides** — The skill auto-detects relevant guides from `aireviewguides/` by analyzing target files (language, framework, project markers) and ranking guides by relevance. Guides are presented for multi-select with environment-specific matches first, then universal guides
3. **Systematic review** — For each selected guide, Claude reads the guide's review instructions and examines the target code, recording findings with severity (high/medium/low), location, description, and suggested fix
4. **Present findings** — Results are grouped by review guide and severity. Select which findings to act on (individual selection or "select all")
5. **Create tasks** — Three modes: a single task combining all findings, one task per review guide, or one task per finding. For multiple tasks, a parent + children structure is created automatically
6. **Handoff** — Choose to continue directly to implementation (via the standard `/aitask-pick` workflow) or save the task(s) for later

## Key Capabilities

- **Auto-detection of relevant guides** — The environment detection system scores review guides against your target files using project markers, file extensions, shebang lines, and directory patterns. You see the most relevant guides first, with an option to include non-matching guides
- **Severity classification** — Findings are categorized as high (security vulnerabilities, correctness bugs, data loss), medium (code quality, missing error handling, performance), or low (style, naming, cosmetics). Task priority is derived from the highest severity among selected findings
- **Flexible task creation** — Create a single task for quick fixes, group by guide for organized review rounds, or separate tasks for independent parallel work
- **Execution profiles** — Pre-configure which guides to auto-select via the `review_default_modes` profile key (comma-separated list of guide names). Set `review_auto_continue` to `true` to auto-proceed to implementation after task creation

## Review Guides

Review guides are markdown files in `aireviewguides/` organized by environment (e.g., `general/`, `python/`, `shell/`). Each guide has YAML frontmatter with metadata (`name`, `description`, `reviewtype`, `reviewlabels`, `environment`) and a body containing actionable review instructions.

To exclude specific guides from auto-detection, add patterns to `aireviewguides/.reviewguidesignore`. This file uses gitignore syntax:

```
general/performance.md    # Exclude a specific guide
android/                  # Exclude an entire environment
*.draft.md                # Exclude all draft guides
!general/security.md      # Re-include after a broader exclusion
```

To manage review guides, see the companion skills:
- [`/aitask-reviewguide-import`](../aitask-reviewguide-import/) — Import external coding standards and best practices as review guides
- [`/aitask-reviewguide-classify`](../aitask-reviewguide-classify/) — Assign metadata to guides for better auto-detection and similarity matching
- [`/aitask-reviewguide-merge`](../aitask-reviewguide-merge/) — Consolidate overlapping guides to avoid duplicate review checks
