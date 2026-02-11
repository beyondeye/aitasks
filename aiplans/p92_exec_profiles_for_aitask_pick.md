---
Task: t92_exec_profiles_for_aitask_pick.md
Worktree: (none - worked on current branch)
Branch: main
Base branch: main
---

# Plan: Execution Profiles for aitask-pick (t92)

## Context

The aitask-pick workflow asks many interactive questions (email, local/remote, worktree, plan handling, etc.) before reaching implementation. Execution profiles store pre-configured answers in YAML files so users can go from task selection to implementation with minimal input.

## Implementation

### Files Created
- `seed/profiles/default.yaml` — Empty profile (template, all questions asked normally)
- `seed/profiles/fast.yaml` — Fast-track profile (skip confirmations, use first email, local, no worktree, reuse plans)
- `aitasks/metadata/profiles/default.yaml` — Live copy of default profile
- `aitasks/metadata/profiles/fast.yaml` — Live copy of fast profile

### Files Modified
- `.claude/skills/aitask-pick/SKILL.md` — Added Step 0a (profile selection before task selection), 8 profile checks across 7 steps, profile schema and customization documentation
- `skills/aitask-pick/SKILL.md` — Synced staging copy
- `install.sh` — Added `install_seed_profiles()` function, profiles directory creation
- `.github/workflows/release.yml` — Added `seed/` to release tarball

### Profile Schema
| Key | Type | Values |
|-----|------|--------|
| `name` | string (required) | Display name |
| `description` | string (required) | Shown during selection |
| `skip_task_confirmation` | bool | Auto-confirm task |
| `default_email` | string | `"first"` = first from emails.txt; or literal email |
| `run_location` | string | `"locally"` / `"remotely"` |
| `create_worktree` | bool | Create worktree or not |
| `base_branch` | string | Branch name |
| `plan_preference` | string | `"use_current"` / `"verify"` / `"create_new"` |
| `post_plan_action` | string | `"start_implementation"` |

## Final Implementation Notes
- **Actual work done:** Created YAML-based execution profile system with default and fast profiles, integrated profile checks into 7 workflow steps, added customization documentation, updated install pipeline and release workflow
- **Deviations from plan:** Step 0.5 was renamed to Step 0a and moved before Step 0 (renamed to Step 0b) per user feedback, since the profile needs to be loaded before task confirmation. Also removed `"skip"` as a `default_email` value — omitting the field entirely activates the question
- **Issues encountered:** None
- **Key decisions:** YAML format chosen over JSON per user preference; profiles stored in `aitasks/metadata/profiles/` matching existing metadata pattern; seed profiles shipped via `seed/` directory in tarball with install.sh handling copy (preserves user customizations on --force reinstall)
