---
Task: t826_1_registry_resolver_projects_cmd_and_create_flag.md
Parent Task: aitasks/t826_brainstorm_cross_repo_project_references.md
Sibling Tasks: aitasks/t826/t826_2_tui_switcher_show_inactive_projects.md, aitasks/t826/t826_3_website_docs_multi_project_workflow.md
Archived Sibling Plans: aiplans/archived/p826/p826_*_*.md
Worktree: (profile 'fast' — works on current branch, no worktree)
Branch: (profile 'fast' — current branch)
Base branch: main
---

# Plan: Cross-repo project registry, resolver, `ait projects` subcommand, `aitask_create.sh --project` flag (t826_1)

## Context

This is the first of three siblings under t826 (cross-repo project
references brainstorm). It introduces the foundational pieces that the
other siblings consume:

- Per-project identity (`project_config.yaml.project = { name, git_remote }`)
- Per-user persistent registry (`~/.config/aitasks/projects.yaml`)
- Internal resolver (`aitask_project_resolve.sh`)
- User-facing `ait projects` subcommand (`list` / `add` / `resolve` / `exec`)
- `aitask_create.sh --project <name>` for cross-repo task spawning
- Authoring-side reference doc (`aidocs/cross_repo_references.md`)

t826_2 will then layer inactive-project visibility on the TUI switcher;
t826_3 will write the user-facing website workflow page.

## Plan

The full step-by-step implementation plan, file paths, reference patterns,
and verification steps are inlined into the task description at
`aitasks/t826/t826_1_registry_resolver_projects_cmd_and_create_flag.md`.

Pick up the task with `/aitask-pick 826_1` and follow the
Implementation Plan section there.

## Decisions inherited from the parent brainstorm

| Decision | Value |
|---|---|
| Registry location | Per-project (`project_config.yaml.project`) + per-user index (`~/.config/aitasks/projects.yaml`) |
| Identity fallback chain | `project.name` → `tmux.default_session` → directory basename |
| Cross-repo task ID notation | Preferred `aitasks#835_3` (no `t`); accepted `aitasks#t835_3` (with `t`). Pattern: `^([a-z0-9_-]+)#t?([0-9]+(?:_[0-9]+)?)$` |
| Resolver fallback order | (1) live tmux scan, (2) per-user index, (3) `AITASKS_PROJECT_<name>` env var |
| Resolver output protocol | `RESOLVED:<root>` / `NOT_FOUND:<name>` / `STALE:<name>:<path>` |
| `ait projects` is user-facing | Yes — wired into `ait` dispatcher |
| `aitask_project_resolve.sh` is internal | Yes — invoked only by other scripts, not directly by users |
| Whitelisting | Neither helper is invoked from any SKILL.md; both skip the 7-touchpoint helper-script whitelist (per memory `feedback_whitelist_only_for_skill_invoked_helpers`) |

## Out of scope (carried forward to future siblings / standalone tasks)

- Adding `project:` block to sister `aitasks_mobile/aitasks/metadata/project_config.yaml`
- Parser/tooling for the `aitasks#835_3` notation
- Cross-project parent linkage (`--project X --parent Y`)
- Auto-clone on `NOT_FOUND`
- `ait projects remove` / pruning

## Step 9 reference

After implementation and review, follow the shared workflow's Step 9. No
worktree to clean (profile `fast` works on the current branch).
