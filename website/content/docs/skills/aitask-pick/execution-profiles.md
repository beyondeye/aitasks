---
title: "Execution Profiles"
linkTitle: "Execution Profiles"
weight: 15
description: "Profile schema, examples, and customization guide for /aitask-pick and related skills"
---

Execution profiles let `/aitask-pick` and related skills pre-answer workflow questions so you can move from task selection to implementation with fewer prompts.

Profiles are YAML files stored in `aitasks/metadata/profiles/`. They are loaded at the start of `/aitask-pick` and can also be reused by related skills that share the task workflow.

## Shipped Profiles

- **default** -- All questions asked normally (empty profile, serves as a template)
- **fast** -- Skip confirmations, use userconfig email, stay on the current branch, and keep feedback questions enabled

## Standard Profile Fields

| Key | Type | Description |
|-----|------|-------------|
| `name` | string (required) | Display name shown during profile selection |
| `description` | string (required) | Description shown below the profile name |
| `skip_task_confirmation` | bool | `true` auto-confirms direct task selection |
| `default_email` | string | `"userconfig"`, `"first"`, or a literal email address |
| `create_worktree` | bool | `true` creates a separate worktree; `false` uses the current branch |
| `base_branch` | string | Branch name used when creating a worktree |
| `plan_preference` | string | `"use_current"`, `"verify"`, or `"create_new"` |
| `plan_preference_child` | string | Same values as `plan_preference`, but only for child tasks |
| `post_plan_action` | string | `"start_implementation"` skips the post-plan checkpoint |
| `post_plan_action_for_child` | string | Same values as `post_plan_action`, but only for child tasks |
| `enableFeedbackQuestions` | bool | `false` disables satisfaction feedback prompts; `true` or omitted keeps them enabled |
| `explore_auto_continue` | bool | Used by `/aitask-explore` to continue automatically after exploration |
| `test_followup_task` | string | `"yes"`, `"no"`, or `"ask"` — create a testing follow-up task before archival |

Omitting a key means that question is asked interactively. `enableFeedbackQuestions` is enabled by default when the key is absent.

## Example

```yaml
name: worktree
description: Like fast but creates a worktree on main for each task
skip_task_confirmation: true
default_email: userconfig
create_worktree: true
base_branch: main
plan_preference: use_current
plan_preference_child: verify
post_plan_action: start_implementation
post_plan_action_for_child: ask
enableFeedbackQuestions: true
test_followup_task: ask
```

## Notes

- Use `enableFeedbackQuestions: false` for unattended or non-interactive profiles
- The shipped `fast` profile keeps feedback enabled; the shipped `remote` profile disables it
- Profiles are preserved during `install.sh --force` upgrades
- Plan approval is always required and cannot be skipped by profiles

For remote/autonomous extensions, see [`/aitask-pickrem`](../aitask-pickrem/).
