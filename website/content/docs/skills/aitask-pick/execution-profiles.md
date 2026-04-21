---
title: "Execution Profiles"
linkTitle: "Execution Profiles"
weight: 15
description: "Profile schema, examples, and customization guide for /aitask-pick and related skills"
depth: [advanced]
---

Execution profiles let `/aitask-pick` and related skills pre-answer workflow questions so you can move from task selection to implementation with fewer prompts.

Profiles are YAML files stored in `aitasks/metadata/profiles/`. They are loaded at the start of `/aitask-pick` and can also be reused by related skills that share the task workflow.

## Shipped Profiles

- **default** -- All questions asked normally (empty profile, serves as a template)
- **fast** -- Skip confirmations, use userconfig email, stay on the current branch, pause for confirmation after plan approval, and keep feedback questions enabled

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
| `plan_verification_required` | int | Minimum fresh `plan_verified` entries required to skip verification when `plan_preference` is `"verify"` (default `1`) |
| `plan_verification_stale_after_hours` | int | Hours after which a `plan_verified` entry is considered stale (default `24`) |
| `post_plan_action` | string | `"start_implementation"` skips the post-plan checkpoint |
| `post_plan_action_for_child` | string | Same values as `post_plan_action`, but only for child tasks |
| `enableFeedbackQuestions` | bool | `false` disables satisfaction feedback prompts; `true` or omitted keeps them enabled. See [Verified Scores](../../verified-scores/) |
| `explore_auto_continue` | bool | Used by `/aitask-explore` to continue automatically after exploration |
| `qa_mode` | string | `"ask"`, `"create_task"`, `"implement"`, or `"plan_only"` — used by [`/aitask-qa`](../../aitask-qa/) to control what happens with test proposals |
| `qa_run_tests` | bool | `true` runs discovered tests, `false` skips test execution — used by [`/aitask-qa`](../../aitask-qa/) |
| `qa_tier` | string | `"quick"`, `"standard"`, or `"exhaustive"` — pre-selects the QA analysis depth tier |
| `manual_verification_followup_mode` | string | `"ask"` (default) or `"never"` — used by task-workflow Step 8c to control whether the post-implementation manual-verification follow-up prompt fires |

Omitting a key means that question is asked interactively. `enableFeedbackQuestions` is enabled by default when the key is absent.

## Remote-Mode Profile Fields

Remote and web workflows recognize additional profile keys (`force_unlock_stale`, `done_task_action`, `orphan_parent_action`, `complexity_action`, `review_action`, `issue_action`, `abort_plan_action`, `abort_revert_status`). For the full table with types and defaults, see [`/aitask-pickrem` → Remote-Specific Profile Fields](../aitask-pickrem/#remote-specific-profile-fields).

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
qa_mode: ask
```

## Default Profile Configuration

Instead of selecting a profile interactively each time, you can set a default per skill in `project_config.yaml` (team-wide) or `userconfig.yaml` (personal override):

```yaml
# project_config.yaml (shared with team)
default_profiles:
  pick: fast
  review: default

# userconfig.yaml (personal, gitignored)
default_profiles:
  pick: default   # overrides team's "fast"
```

Valid skill names: `pick`, `fold`, `review`, `pr-import`, `revert`, `explore`, `pickrem`, `pickweb`, `qa`. Values are profile names (without `.yaml` extension) matching the `name` field in profile YAML files.

You can also configure defaults via the Settings TUI: `ait settings` → Project Config tab → Default Profiles section.

## Profile Override Argument

All skills that support profiles accept an optional `--profile <name>` argument to override both team and personal defaults:

```
/aitask-pick --profile fast
/aitask-pick 42 --profile fast
/aitask-fold --profile fast 106,108
/aitask-review --profile default
/aitask-pickrem 42 --profile remote
```

The argument is position-independent and can appear anywhere in the argument string.

### Resolution Order

1. `--profile <name>` argument (highest priority)
2. `userconfig.yaml` → `default_profiles.<skill>` (personal)
3. `project_config.yaml` → `default_profiles.<skill>` (team)
4. Interactive selection / auto-select (fallback)

## Notes

- Use `enableFeedbackQuestions: false` for unattended or non-interactive profiles
- The shipped `fast` profile keeps feedback enabled; the shipped `remote` profile disables it
- Profiles are preserved during `install.sh --force` upgrades
- Plan approval is always required and cannot be skipped by profiles

For remote/autonomous extensions, see [`/aitask-pickrem`](../aitask-pickrem/).
