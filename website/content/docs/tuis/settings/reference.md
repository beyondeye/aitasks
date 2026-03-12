---
title: "Reference"
linkTitle: "Reference"
weight: 30
description: "Keyboard shortcuts, configuration files, and profile schema reference"
---

## Keyboard Shortcuts

### Global

| Key | Action |
|-----|--------|
| **a** | Switch to Agent Defaults tab |
| **b** | Switch to Board tab |
| **c** | Switch to Project Config tab |
| **m** | Switch to Models tab |
| **p** | Switch to Profiles tab |
| **e** | Export all configs |
| **i** | Import configs |
| **r** | Reload all configs from disk |
| **q** | Quit |

### Within Tabs

| Key | Action | Context |
|-----|--------|---------|
| **Enter** / **Space** | Edit field or cycle value | Agent Defaults, Board, Profiles |
| **d** / **Delete** | Remove user override | Agent Defaults |
| **?** | Toggle field description (summary/expanded) | Profiles |
| **Escape** | Close dialog or cancel | Modals |

## Tabs

| Tab | Shortcut | Editable | Description |
|-----|----------|----------|-------------|
| Agent Defaults | **a** | Yes | Default agent/model per operation, project and user layers |
| Board | **b** | Partially | Columns (read-only), user settings (editable) |
| Project Config | **c** | Yes | Shared values from `project_config.yaml` such as coauthor domain and build verification |
| Models | **m** | No | Available models per agent with verification scores |
| Profiles | **p** | Yes | Execution profiles that pre-answer workflow questions |

## Agent Defaults Operations

| Operation | Description |
|-----------|-------------|
| `task-pick` | Model used for picking and implementing tasks |
| `explain` | Model used for explaining/documenting code |
| `batch-review` | Model used for batch code review operations |
| `raw` | Model used for direct/ad-hoc code agent invocations (passthrough mode) |

## Configuration Files

| File | Scope | Editable via TUI | Description |
|------|-------|-------------------|-------------|
| `aitasks/metadata/codeagent_config.json` | Project | Yes (Agent Defaults) | Default agent/model per operation |
| `aitasks/metadata/codeagent_config.local.json` | User | Yes (Agent Defaults) | Per-user overrides (gitignored) |
| `aitasks/metadata/board_config.json` | Project | No | Board column definitions |
| `aitasks/metadata/board_config.local.json` | User | Yes (Board) | User board settings (gitignored) |
| `aitasks/metadata/project_config.yaml` | Project | Yes (Project Config) | Shared workflow settings such as coauthor domain and build verification |
| `aitasks/metadata/models_claudecode.json` | Project | No | Claude Code model definitions |
| `aitasks/metadata/models_geminicli.json` | Project | No | Gemini CLI model definitions |
| `aitasks/metadata/models_codex.json` | Project | No | Codex CLI model definitions |
| `aitasks/metadata/models_opencode.json` | Project | No | OpenCode model definitions |
| `aitasks/metadata/profiles/*.yaml` | Project | Yes (Profiles) | Execution profiles (git-tracked) |
| `aitasks/metadata/profiles/local/*.yaml` | User | Yes (Profiles) | User execution profiles (gitignored) |

## Profile Schema

Execution profiles are YAML files with the following keys. All keys are optional -- omitted keys cause the corresponding question to be asked interactively.

### Identity

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `name` | string | -- | Profile display name |
| `description` | string | -- | Brief description of what the profile does |

### Task Selection

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `skip_task_confirmation` | bool | `true`, `false` | Skip the "Is this the correct task?" confirmation |
| `default_email` | enum | `userconfig`, `first` | How to resolve the assignee email without asking |

### Branch & Worktree

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `create_worktree` | bool | `true`, `false` | Whether to create a separate git worktree for the task |
| `base_branch` | string | -- | Branch name to base the task branch on |

### Planning

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `plan_preference` | enum | `use_current`, `verify`, `create_new` | What to do when an existing plan is found |
| `plan_preference_child` | enum | `use_current`, `verify`, `create_new` | Same as above, but specifically for child tasks (takes priority) |
| `post_plan_action` | enum | `start_implementation` | What to do after plan is saved |

### Feedback

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `enableFeedbackQuestions` | bool | `true`, `false` | Whether supported skills ask for satisfaction feedback after completion (`(unset)` behaves like `true`) |

### Exploration

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `explore_auto_continue` | bool | `true`, `false` | Auto-continue to implementation after exploration |

### Lock Management

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `force_unlock_stale` | bool | `true`, `false` | Automatically force-unlock stale locks |

### Remote Workflow

These keys control behavior for the fully autonomous remote workflow (`/aitask-pickrem`):

| Key | Type | Options | Description |
|-----|------|---------|-------------|
| `done_task_action` | enum | `archive`, `skip` | What to do with tasks that have status Done |
| `orphan_parent_action` | enum | `archive`, `skip` | What to do with orphaned parent tasks |
| `complexity_action` | enum | `single_task`, `create_children` | How to handle complex tasks |
| `review_action` | enum | `commit`, `need_changes`, `abort` | What to do after implementation review |
| `issue_action` | enum | `close_with_notes`, `comment_only`, `close_silently`, `skip` | How to handle linked issues during archival |
| `abort_plan_action` | enum | `keep`, `discard` | What to do with plan files on abort |
| `abort_revert_status` | enum | `Ready`, `Editing` | Status to revert to on abort |

## Project Config Keys

| Key | Type | Description |
|-----|------|-------------|
| `codeagent_coauthor_domain` | string | Email domain used for custom code-agent commit coauthors |
| `verify_build` | string or list | Shell command(s) run after implementation to verify the build |

## Model Entry Schema

Each model in `models_<agent>.json`:

```json
{
  "name": "opus4_6",
  "cli_id": "claude-opus-4-6",
  "notes": "Most intelligent model for agents and coding",
  "verified": {
    "pick": 80,
    "explain": 80,
    "batch-review": 0
  },
  "verifiedstats": {
    "pick": {
      "all_time": {"runs": 5, "score_sum": 400},
      "month": {"period": "2026-03", "runs": 2, "score_sum": 180},
      "week": {"period": "2026-W11", "runs": 1, "score_sum": 100}
    }
  }
}
```

| Field | Description |
|-------|-------------|
| `name` | Internal identifier (underscored, no dots) |
| `cli_id` | Exact model ID for the CLI binary's model flag |
| `notes` | Human-readable description |
| `verified` | Per-operation scores (all-time average): 0 = untested, 1-49 = partial, 50-79 = verified, 80-100 = highly verified |
| `verifiedstats` | Per-operation detailed statistics with time-windowed buckets (see below) |

### Verified Stats Buckets

Each skill entry in `verifiedstats` contains three time-windowed buckets:

| Bucket | Period Key | Description |
|--------|-----------|-------------|
| `all_time` | (none) | Cumulative stats across all ratings |
| `month` | `YYYY-MM` | Stats for the current calendar month; resets when the month changes |
| `week` | `YYYY-Www` | Stats for the current ISO 8601 calendar week; resets when the week changes |

Each bucket contains `runs` (number of ratings) and `score_sum` (sum of mapped scores, where raw 1-5 maps to 20-100).

The `verified.<skill>` field is always the rounded average of `all_time` and is maintained automatically for backward compatibility.

Old flat-format stats (`{"runs": N, "score_sum": S}`) are migrated automatically to the bucketed format on the next update.

### All-Providers Aggregation

To compute cross-provider stats for the same underlying LLM model:

1. Extract the model portion from each entry's `cli_id` by stripping the `provider/` prefix (e.g., `openai/gpt-5.4` and `opencode/gpt-5.4` both normalize to `gpt-5.4`)
2. Group entries with identical normalized model IDs across all `models_*.json` files
3. For each skill, sum `runs` and `score_sum` from the matching bucket across the group
4. For `month` and `week` buckets, only aggregate entries with the same `period` value

This aggregation is performed at read time by consumers — no duplicate aggregate values are stored.

`ait settings` implements this aggregation in the Models tab (cross-provider summary lines), the Agent Defaults tab (all-providers hints), and the model picker (Top Verified ranking).

## Export Bundle Format

Config bundles use the `.aitcfg.json` extension and contain:

```json
{
  "_export_meta": {
    "version": 1,
    "timestamp": "2026-03-03T12:00:00",
    "file_count": 5
  },
  "codeagent_config.json": { ... },
  "models_claudecode.json": { ... }
}
```

Bundles include only the files matching the default patterns: `*_config.json`, `*_config.local.json`, `models_*.json`, `models_*.local.json`.
