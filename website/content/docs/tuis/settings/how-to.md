---
title: "How-To Guides"
linkTitle: "How-To"
weight: 20
description: "Step-by-step guides for common Settings TUI tasks"
maturity: [stable]
depth: [intermediate]
---

## Change the Default Model for an Operation

1. Open the Settings TUI: `ait settings`
2. Press **a** to go to the **Agent Defaults** tab
3. Navigate to the operation you want to change (e.g., `task-pick`)
4. Press **Enter** to open the agent/model picker
5. **Step 1:** Select the code agent (claudecode, geminicli, codex, opencode)
6. **Step 2:** Select the model from the list, then choose the target layer:
   - **Project** -- Saves to `codeagent_config.json` (shared, git-tracked)
   - **User** -- Saves to `codeagent_config.local.json` (personal, gitignored)
7. The change takes effect immediately

> **Note:** Choosing **User** layer means this override only applies to your machine. Other team members will continue using the project default.

## Remove a User Override

If you previously set a per-user override and want to revert to the project default:

1. Press **a** to go to the **Agent Defaults** tab
2. Navigate to the entry showing an **[USER]** badge
3. Press **d** or **Delete**
4. The user override is removed and the project default is restored

## View Available Models

1. Press **m** to go to the **Models** tab
2. Browse models organized by agent
3. Check the verification scores to see which models are well-tested for each operation

The Models tab is read-only. To update model definitions, edit the `aitasks/metadata/models_<agent>.json` files directly or use the `/aitask-refresh-code-models` skill to research and update models from the web.

## Configure Board Settings

1. Press **b** to go to the **Board** tab
2. Navigate to the **User Settings** section
3. Use **Enter** or **Space** on a cycle field to toggle values:
   - **Auto-refresh (min)** -- Cycles through 0 (disabled), 1, 2, 5, 10, 15, 30
   - **Sync on refresh** -- Toggles between `yes` and `no`
4. Click **Save Board Settings** to persist

> **Note:** The Columns section at the top is read-only. To customize columns, use the [Board TUI](../board/) directly.

## Edit Project Config Values

1. Press **c** to go to the **Project Config** tab
2. Navigate to the setting you want to change:
   - `codeagent_coauthor_domain`
   - `verify_build`
3. Press **Enter** to open the editor
4. Enter the new value:
   - For `codeagent_coauthor_domain`, enter a domain such as `aitasks.io`
   - For `verify_build`, enter either a single command or YAML in flow style such as `["npm run build", "npm test"]`
5. Click **Save Project Config** to persist the YAML file

> **Note:** Project config values are shared and git-tracked. Changing them affects the whole team.

## Set Default Execution Profiles

Default profiles let you skip the profile selection prompt by pre-assigning a profile to each skill.

### Using the Settings TUI

1. Press **c** to go to the **Project Config** tab
2. Find the **Default Profiles** section (one row per skill)
3. Press **Enter** on a skill to open the profile picker
4. Select a profile name or `<not set>` to clear
5. Click **Save Project Config** to persist

### Using YAML directly

Add `default_profiles` to `project_config.yaml` (team-wide) or `userconfig.yaml` (personal, gitignored):

```yaml
# project_config.yaml (shared with team)
default_profiles:
  pick: fast
  review: default

# userconfig.yaml (personal override)
default_profiles:
  pick: default   # overrides team's "fast"
```

Valid skill names: `pick`, `fold`, `review`, `pr-import`, `revert`, `explore`, `pickrem`, `pickweb`, `qa`.

### Override with `--profile`

Any skill that supports profiles accepts `--profile <name>` to override both team and personal defaults:

```
/aitask-pick --profile fast
/aitask-fold --profile fast 106,108
/aitask-pickrem 42 --profile remote
```

**Resolution order:** `--profile` argument > `userconfig.yaml` > `project_config.yaml` > interactive/auto-select.

## Edit an Execution Profile

1. Press **p** to go to the **Profiles** tab
2. Select a profile from the dropdown (e.g., `fast`, `default`, `remote`)
3. Navigate to the field you want to change
4. Edit the value:
   - **Boolean fields** -- Press **Enter** or **Space** to cycle: `true` / `false` / `(unset)`
   - **Enum fields** -- Press **Enter** or **Space** to cycle through available options + `(unset)`
   - **String fields** -- Press **Enter** to open a text editor dialog
5. Press **?** on any field to toggle between summary and expanded descriptions
6. Click **Save Profile** to persist changes
7. Optionally click **Commit** to commit the profile file to git

Setting a field to `(unset)` removes it from the profile YAML, which means the corresponding question will be asked interactively during the workflow.

## Create a New Execution Profile

1. Press **p** to go to the **Profiles** tab
2. Click **New Profile** at the bottom
3. Fill in the required fields:
   - **Name** -- A short identifier (used as the filename)
   - **Base profile** -- Optionally copy settings from an existing profile
   - **Scope** -- Project (shared) or User (local only)
4. Press **Create**
5. Edit the profile fields as needed
6. Click **Save Profile**

Project-scoped profiles are saved to `aitasks/metadata/profiles/` (git-tracked). User-scoped profiles are saved to `aitasks/metadata/profiles/local/` (gitignored).

## Export Configuration

1. Press **e** from any tab
2. Choose an output path for the `.aitcfg.json` bundle
3. Select which config files to include (or export all)
4. The bundle is created with all selected config files

The export bundle can be shared with team members or used as a backup.

## Import Configuration

1. Press **i** from any tab
2. Select the `.aitcfg.json` file to import
3. Review the files included in the bundle
4. Select which files to import
5. Choose whether to overwrite existing files
6. Imported configs are applied immediately

## tmux integration

When you run `ait settings` inside tmux, you can jump to any other integrated TUI with a single keystroke via the **TUI switcher**:

1. Press **`j`** to open the TUI switcher dialog.
2. Select the target TUI — Monitor, Minimonitor, Board, Code Browser, or Brainstorm — or one of the running code agent windows.
3. The switcher either focuses the existing tmux window running that TUI or creates a new window and launches it.

The settings TUI also hosts the **Tmux** tab, where you can edit the integration defaults (session name, split direction, refresh interval, monitor thresholds) shared by `ait ide`, `ait monitor`, and the TUI switcher itself.

<!-- TODO screenshot: aitasks_tui_switcher_dialog.svg -->

The TUI switcher requires a tmux session. If you are not running inside tmux yet, see [Terminal Setup]({{< relref "/docs/installation/terminal-setup" >}}) for how to launch one with `ait ide`.

---

**Next:** [Reference](../reference/) — keybindings, config files, profile schema.
