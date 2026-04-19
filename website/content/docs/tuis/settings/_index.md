---
title: "Settings"
linkTitle: "Settings"
weight: 30
description: "Centralized TUI for browsing and editing all aitasks configuration"
---

## Launching

```bash
ait settings
```

The Settings TUI requires the shared Python virtual environment (installed by `ait setup`) with the `textual` and `pyyaml` packages.

## Understanding the Layout

The Settings TUI organizes configuration into five tabs, each accessible via a keyboard shortcut displayed in the footer.

### Agent Defaults (a)

{{< static-img src="imgs/aitasks_settings_code_agent_default_models_tab.svg" alt="Agent Defaults tab showing configured models per operation" caption="The Agent Defaults tab shows which code agent and model is configured for each operation" >}}

Shows the default agent/model for each operation (`task-pick`, `explain`, `batch-review`, `raw`). These defaults are used when launching tasks from the [Board]({{< relref "/docs/tuis/board" >}}) TUI and running explain from the [Code Browser]({{< relref "/docs/tuis/codebrowser" >}}) TUI. Each entry displays:

- The current value (e.g., `claudecode/opus4_6`)
- A layer badge: **[PROJECT]** (green) for project-level defaults or **[USER]** (amber) for per-user overrides
- **[Verified score]({{< relref "/docs/skills/verified-scores" >}}) context** -- score, run count, and recency (e.g., `[96 (9 runs, 2 this mo)]`)
- When the same underlying LLM has scores from multiple providers, an **all providers** summary appears below (e.g., `all providers: 96 (12 runs, 3 this mo)`)
- A description of what the operation does

Press **Enter** on any operation to change its agent/model through the model picker.

The picker opens with a **Top Verified** list showing the highest-scoring models for the selected operation across all providers. Select a model directly or choose **Browse all models** to use the full agent/model browser.

{{< static-img src="imgs/aitasks_settings_select_model_step1_codeagent.svg" alt="Step 1: Select code agent" caption="Step 1: Choose which code agent to use (via Browse all models)" >}}

{{< static-img src="imgs/aitasks_settings_select_model_step2_llmmodel.svg" alt="Step 2: Select model and target layer" caption="Step 2: Choose the model and whether to save to project or user config" >}}

Press **d** or **Delete** on an entry to remove a user override and revert to the project default.

### Board (b)

{{< static-img src="imgs/aitasks_settings_board_tab.svg" alt="Board tab showing column configuration and user settings" caption="The Board tab displays column definitions (read-only) and editable user settings" >}}

Displays board configuration in two sections:

- **Columns** (read-only) -- Lists each board column's ID, title, and color
- **User Settings** (editable) -- `Auto-refresh (min)` (cycle through 0, 1, 2, 5, 10, 15, 30 where 0 = disabled) and `Sync on refresh` (toggle whether push/pull runs on each auto-refresh)

Press **Save Board Settings** to persist changes.

### Project Config (c)

Edit shared values from `aitasks/metadata/project_config.yaml` directly in the TUI. The initial editable keys are:

- `codeagent_coauthor_domain` -- Shared email domain used for custom code-agent `Co-authored-by` trailers
- `verify_build` -- Build verification command or YAML list of commands run after implementation

Press **Enter** on a row to edit the value, then use **Save Project Config** to persist it.

### Models (m)

{{< static-img src="imgs/aitasks_settings_llmmodels_tab.svg" alt="Models tab showing available models per agent" caption="The Models tab is a read-only display of all configured models" >}}

Read-only display of all available models organized by agent (claudecode, codex, geminicli, opencode). For each model, shows:

- **Name** -- Internal identifier used in agent strings
- **CLI ID** -- Exact model ID passed to the CLI
- **Notes** -- Description of the model
- **Verified stats** -- Per-operation score with run count and recency (e.g., `pick: 96 (9 runs, 2 this month)`)
- **All providers** -- When the same LLM is available through multiple providers, a cross-provider aggregate line appears below the model row

Model definitions are managed by editing `aitasks/metadata/models_<agent>.json` files directly or using the `/aitask-refresh-code-models` skill.

### Profiles (p)

{{< static-img src="imgs/aitasks_settings_execution_profiles_tab.svg" alt="Profiles tab showing execution profile settings" caption="The Profiles tab lets you browse and edit execution profiles that control workflow behavior" >}}

Browse and edit execution profiles -- YAML files that pre-answer workflow questions to reduce interactive prompts. Each profile contains settings organized into groups:

- **Identity** -- name, description
- **Task Selection** -- skip_task_confirmation, default_email
- **Branch & Worktree** -- create_worktree, base_branch
- **Planning** -- plan_preference, plan_preference_child, post_plan_action
- **Feedback** -- enableFeedbackQuestions
- **Exploration** -- explore_auto_continue
- **QA** -- qa_mode, qa_run_tests
- **Lock Management** -- force_unlock_stale
- **Remote Workflow** -- done_task_action, orphan_parent_action, complexity_action, review_action, issue_action, abort_plan_action, abort_revert_status

Fields use type-appropriate controls: boolean keys toggle between `true`/`false`/`(unset)`, enum keys cycle through their options, and string keys open an edit dialog. Setting a value to `(unset)` removes it from the profile so the question is asked interactively at runtime.

## Navigating

| Key | Action |
|-----|--------|
| **a** | Switch to Agent Defaults tab |
| **b** | Switch to Board tab |
| **c** | Switch to Project Config tab |
| **m** | Switch to Models tab |
| **p** | Switch to Profiles tab |
| **Enter** | Edit selected field |
| **d** / **Delete** | Remove user override (Agent Defaults) |
| **e** | Export all configs to `.aitcfg.json` bundle |
| **i** | Import configs from `.aitcfg.json` bundle |
| **r** | Reload all configs from disk |
| **q** | Quit |

---

**Next:** [How-To Guides](how-to/) — common tasks like editing agents, creating profiles, exporting bundles. Or jump to the [Reference](reference/) for the full tab/field/profile schemas.
