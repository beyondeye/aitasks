---
Task: t826_3_website_docs_multi_project_workflow.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_1_registry_resolver_projects_cmd_and_create_flag.md, aitasks/t826/t826_2_tui_switcher_show_inactive_projects.md
Archived Sibling Plans: aiplans/archived/p826/p826_1_*.md, aiplans/archived/p826/p826_2_*.md (both required reading — the website page documents the actually-shipped surface from both)
Worktree: (profile 'fast' — works on current branch, no worktree)
Branch: (profile 'fast' — current branch)
Base branch: main
---

# Plan: Website docs — multi-project workflow page (t826_3)

## Context

Third (currently-final) sibling under t826. After t826_1 ships the registry
+ `ait projects` + `aitask_create.sh --project` and t826_2 ships TUI
switcher inactive-project visibility, the user-facing Hugo/Docsy website
needs a workflow page covering multi-project work end-to-end.

Depends on t826_1 and t826_2 archived — documentation should reflect the
shipped surface, not a forecasted design.

## Plan

The full audit, content outline, and verification steps are inlined into the
task description at
`aitasks/t826/t826_3_website_docs_multi_project_workflow.md`.

Before drafting, read both archived sibling plans
(`aiplans/archived/p826/p826_1_*.md` and `aiplans/archived/p826/p826_2_*.md`)
plus the implementation commits — the page must match the actually shipped
behavior including any deviations recorded in those plans' Final
Implementation Notes.

## Key writing constraints

| Constraint | Value |
|---|---|
| Page location | `website/content/docs/workflows/multi_project.md` (create if absent; update if a multi-project page already exists) |
| Sidebar wiring | Verify the new page appears in the workflows section nav |
| Cross-link from authoring docs | Append a link to the new website page in `aidocs/cross_repo_references.md` |
| Cross-repo notation default | Preferred `aitasks#835_3` (no `t`); accepted `aitasks#t835_3` (with `t`). State the no-`t` form as the recommended default |
| `ait monitor` mention | Explicitly note that monitor is **unchanged** — its multi-project view stays scoped to live tmux sessions |
| Doc-writing rule | Per CLAUDE.md "Documentation Writing": current state only — no "previously we…" prose, no migration notes, no version history |
| Build verification | `cd website && hugo build --gc --minify` clean; `./serve.sh` visually inspect |

## Required sections (in order)

1. Why — cross-repo coordination pain, persistent registry
2. Per-project identity (`project:` block in `project_config.yaml`)
3. `ait projects` subcommand reference (`list` / `add` / `resolve` / `exec`)
4. Cross-repo task creation walkthrough (`aitask_create.sh --project`)
5. Cross-repo notation in plans / commits (`aitasks#835_3` preferred)
6. TUI switcher inactive-project behavior (with explicit "monitor unchanged" note)
7. Recipe: "How to register a sister project and spawn a task there"

## Out of scope

- Documentation of future-sibling features (cross-project parent linkage, notation parser, `ait projects remove`, auto-clone)
- Non-English locale translations
- Website design / nav structural changes

## Step 9 reference

After implementation and review, follow the shared workflow's Step 9. No
worktree to clean (profile `fast` works on the current branch).
