---
priority: medium
effort: low
depends: []
issue_type: feature
status: Implementing
labels: [tui, brainstorming]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-03-18 12:22
updated_at: 2026-03-18 12:36
---

## Context

The diff viewer TUI (t417) needs a project scaffold and realistic test data before any diff logic or widgets can be built. This is the foundation task that creates the directory structure, launcher script, and 5 dummy plan files that all subsequent child tasks will use for development and testing.

The diff viewer will live in `.aitask-scripts/diffviewer/` alongside the existing board, codebrowser, and settings TUIs.

## Key Files to Create

- `.aitask-scripts/diffviewer/__init__.py` — Empty package marker
- `.aitask-scripts/diffviewer/test_plans/plan_alpha.md` — Numbered steps structure, 3 sections
- `.aitask-scripts/diffviewer/test_plans/plan_beta.md` — Section-by-file structure, shares content with alpha but reordered
- `.aitask-scripts/diffviewer/test_plans/plan_gamma.md` — Architecture overview + implementation steps, shares some paragraphs with alpha/beta
- `.aitask-scripts/diffviewer/test_plans/plan_delta.md` — Minimal plan, content subset of gamma
- `.aitask-scripts/diffviewer/test_plans/plan_epsilon.md` — Longest plan, superset content, different heading structure
- `.aitask-scripts/aitask_diffviewer.sh` — Launcher script (follow `aitask_codebrowser.sh` pattern)

## Reference Files for Patterns

- `.aitask-scripts/aitask_codebrowser.sh` — Launcher script to copy/adapt (venv detection, dependency check, Python exec)
- `aiplans/archived/` — Real plan file examples for understanding structure variation
- `.aitask-scripts/board/task_yaml.py` — Frontmatter format reference

## Implementation Plan

1. Create `.aitask-scripts/diffviewer/` directory and `__init__.py`
2. Create `test_plans/` subdirectory
3. Write 5 dummy plan files with YAML frontmatter (Task, Worktree, Branch, Base branch fields) and varied markdown body:
   - **plan_alpha**: Uses `## Step 1`, `## Step 2` etc. numbered section headings. Has a "Context" section, 3 implementation steps with code snippets, and a "Verification" section.
   - **plan_beta**: Uses `## File: src/main.py`, `## File: src/utils.py` section-by-file headings. Shares 2 paragraphs verbatim with alpha (at different positions). Has a code snippet identical to alpha's.
   - **plan_gamma**: Uses `## Architecture Overview`, `## Component Design`, `## Implementation` headings. Shares the "Verification" section with alpha. Has bullet lists instead of numbered lists.
   - **plan_delta**: Minimal — only "Context" and "Implementation" sections. Content is a strict subset of gamma (2 paragraphs copied verbatim).
   - **plan_epsilon**: Longest plan. All sections from alpha + gamma combined, plus unique "Risk Assessment" and "Performance Considerations" sections. Different heading depth (`###` subsections). Rephrased versions of shared content.
4. Create `.aitask-scripts/aitask_diffviewer.sh` launcher following `aitask_codebrowser.sh` pattern:
   - `#!/usr/bin/env bash`, `set -euo pipefail`
   - cd to repo root
   - Detect/activate Python venv
   - Check textual dependency
   - `exec python3 .aitask-scripts/diffviewer/diffviewer_app.py "$@"`

## Verification

- All 5 `.md` files exist and have valid YAML frontmatter parseable by `task_yaml.parse_frontmatter()`
- Plans share overlapping content at different positions (needed for structural diff testing)
- Plans have enough unique content to produce non-trivial diffs
- `bash .aitask-scripts/aitask_diffviewer.sh` runs without error (even if the Python app is just a placeholder stub)
- `shellcheck .aitask-scripts/aitask_diffviewer.sh` passes
