---
Task: t374_better_verify_build_settings.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

The `verify_build` setting in the ait settings TUI (`ait settings`, Project Config tab) has several UX issues: the display doesn't update after editing (shows "not set"), editing is single-line only (awkward for YAML lists), there's no way to pick from common project presets, and no link to documentation. Task t374 addresses all of these.

## Plan

### Files to modify
- `.aitask-scripts/settings/settings_app.py` — All UI changes (bug fix, new modals, CSS, preset matching, doc link)
- `.aitask-scripts/settings/verify_build_presets.yaml` — **New file** with preset definitions (41 presets)

### Step 1: Bug fix — display not updating after edit
- Fix `_handle_project_config_edit` to use `_format_yaml_value()` for display value
- Store actual widget ID when opening modal (fixes `_repop_counter` mismatch)

### Step 2: Create preset YAML file
- 41 presets covering Rust, Node.js, Go, Python, Android, C/C++, Java, Kotlin, Scala, Swift, Ruby, PHP, Elixir, Dart/Flutter, Hugo, Jekyll, Docker, Make, Shell, Zig, .NET, Haskell
- `_load_verify_build_presets()` and `_match_preset_name()` helpers

### Step 3: Multi-line edit modal (EditVerifyBuildScreen)
- TextArea widget with YAML language support
- Block/compact YAML conversion for editing
- "Load Preset" button

### Step 4: Preset picker modal (VerifyBuildPresetScreen)
- FuzzySelect with live preview via new `Highlighted` message
- Preview shows preset content as user navigates

### Step 5: Show preset name when value matches
- Semantic matching via `yaml.safe_load` comparison
- Shown in both initial display and after editing

### Step 6: Documentation link
- Build Verification docs URL shown below verify_build description

### Step 7: CSS additions
- TextArea height, preset preview panel styling

## Implementation Status
- [x] All steps implemented and tested
- [x] Bug fix for "could not update" error (row ID sync issue)
- [ ] Not yet committed — code changes in working directory

## Post-implementation: Step 9 cleanup and archival per task-workflow
