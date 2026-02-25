# Execution Profiles

Reference documentation for execution profiles used by the task-workflow skill
and calling skills (aitask-pick, aitask-explore, etc.).

## Table of Contents

- [Profile Schema Reference](#profile-schema-reference)
- [Customizing Execution Profiles](#customizing-execution-profiles)

---

Profiles are YAML files stored in `aitasks/metadata/profiles/`. They pre-answer workflow questions to reduce interactive prompts. Two profiles ship by default:
- **default** — All questions asked normally (empty profile, serves as template)
- **fast** — Skip confirmations, use userconfig email, work locally on current branch, reuse existing plans

## Profile Schema Reference

| Key | Type | Required | Values | Step |
|-----|------|----------|--------|------|
| `name` | string | yes | Display name shown during profile selection | Step 0a |
| `description` | string | yes | Description shown below profile name during selection | Step 0a |
| `skip_task_confirmation` | bool | no | `true` = auto-confirm task; omit or `false` = ask | Step 0b |
| `default_email` | string | no | `"userconfig"` = from userconfig.yaml (falls back to first from emails.txt); `"first"` = first from emails.txt; or a literal email address; omit = ask. Note: `assigned_to` from task metadata always takes priority regardless of this setting (see Step 4 email resolution). | Step 4 |
| `create_worktree` | bool | no | `true` = create worktree; `false` = current branch | Step 5 |
| `base_branch` | string | no | Branch name (e.g., `"main"`) | Step 5 |
| `plan_preference` | string | no | `"use_current"`, `"verify"`, or `"create_new"` | Step 6.0 |
| `plan_preference_child` | string | no | Same values as `plan_preference`; overrides `plan_preference` for child tasks. Defaults to `plan_preference` if omitted | Step 6.0 |
| `post_plan_action` | string | no | `"start_implementation"` = skip to impl; omit = ask | Step 6 checkpoint |

Only `name` and `description` are required. Omitting any other key means the corresponding question is asked interactively.

> **Remote-specific profile fields** (e.g., `done_task_action`, `review_action`, `issue_action`) are documented in the `aitask-pickrem` skill. They are only recognized by that skill and ignored by this workflow.

## Customizing Execution Profiles

**To create a custom profile:**
1. Copy an existing profile: `cp aitasks/metadata/profiles/fast.yaml aitasks/metadata/profiles/my-profile.yaml`
2. Edit `name` and `description` (both required — `description` is shown during profile selection)
3. Add, remove, or change setting keys as needed
4. Any key you omit will cause that question to be asked interactively

**Example — worktree-based workflow:**
```yaml
name: worktree
description: Like fast but creates a worktree on main for each task
skip_task_confirmation: true
default_email: first
create_worktree: true
base_branch: main
plan_preference: use_current
post_plan_action: start_implementation
```

**Notes:**
- Profiles are partial — only include keys you want to pre-configure
- The `description` field is shown next to the profile name when selecting a profile
- Profiles are preserved during `install.sh --force` upgrades (existing files are not overwritten)
- Plan approval (ExitPlanMode) is always mandatory and cannot be skipped by profiles
