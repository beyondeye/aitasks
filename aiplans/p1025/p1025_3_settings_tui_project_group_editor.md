---
Task: t1025_3_settings_tui_project_group_editor.md
Parent Task: aitasks/t1025_design_project_group_grouping_and_tui_navigation.md
Sibling Tasks: aitasks/t1025/t1025_1_*.md, aitasks/t1025/t1025_2_*.md, aitasks/t1025/t1025_4_*.md
Archived Sibling Plans: aiplans/archived/p1025/p1025_1_*.md, aiplans/archived/p1025/p1025_2_*.md
Worktree: (none — profile 'fast', current branch)
Branch: main
Base branch: main
---

# Plan: settings-TUI project-group editor (t1025_3)

Depends on t1025_1 (registry writer + slug validator + membership model methods).
See parent plan `aiplans/p1025_*.md`.

## Steps

1. Add a `project-groups` `TabPane` and/or `ModalScreen` editor in
   `.aitask-scripts/settings/settings_app.py`, following `EditVerifyBuildScreen`
   (`:772`) / `ProfilePickerScreen` (`:922`) / `NewProfileScreen` (`:960`). List
   registered repos with their current group; offer assign/create/rename/clear.
   Reuse the keybinding-registry/tab-switch map (`:156`).
2. **Membership-edit model methods** (in t1025_1's model layer; the screen calls
   one method per op — "encapsulate cleanup in model"). All names pass the
   t1025_1 slug validator; illegal input rejected/normalized with a visible
   message BEFORE any write:
   - **Assign:** set one repo's `project_group` to an existing/new slug.
   - **Create:** implicit once ≥1 repo references the slug; duplicate = no-op merge.
   - **Clear:** blank → unset (repo → "(ungrouped)").
   - **Rename:** ONE atomic full-file read-modify-write (reuse
     `build_registry_yaml`) rewriting every member old→new; rename into existing
     slug merges groups.
3. No direct YAML writes from the TUI — go through the t1025_1 writer.

## Verification

- Model-level tests vs a temp registry: assign; create (duplicate-merge);
  clear→ungrouped; rename (all members rewritten atomically); rename-into-existing
  (merge); slug rejection of `:`/`#`/`|`/space/uppercase.
- Smoke test: the project-groups tab/screen mounts without error.
- Manual: edit a group in the settings TUI; confirm the registry file updates and
  the switcher/stats re-render reflects it (live coverage in t1025_5).

## Step 9
Standard child archival.
