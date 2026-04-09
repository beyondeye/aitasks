---
Task: t507_3_git_tui_setting_in_settings_tui_tmux_tab.md
Parent Task: aitasks/t507_lazygit_integration_in_ait_monitorcommon_switch_tui.md
Sibling Tasks: aitasks/t507/t507_1_*.md, aitasks/t507/t507_2_*.md, aitasks/t507/t507_4_*.md
Archived Sibling Plans: aiplans/archived/p507/p507_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Implementation Plan: t507_3 — Git TUI Setting in Settings TUI Tmux Tab

## Steps

### 1. Fix `save_tmux_settings()` data-loss bug

File: `.aitask-scripts/settings/settings_app.py` lines 2739-2741

**Bug:** `data["tmux"] = tmux_data` replaces entire tmux dict with only schema-tracked keys, wiping `tmux.monitor` (refresh_seconds, idle_threshold_seconds, capture_lines, agent_window_prefixes, tui_window_names).

**Fix:** Merge schema fields into existing tmux dict:

Change:
```python
data = dict(self.config_mgr.project_config)
if tmux_data:
    data["tmux"] = tmux_data
else:
    data.pop("tmux", None)
```

To:
```python
data = dict(self.config_mgr.project_config)
if tmux_data:
    existing_tmux = dict(data.get("tmux") or {})
    existing_tmux.update(tmux_data)
    data["tmux"] = existing_tmux
else:
    # Only remove schema-tracked keys, preserve other tmux sub-sections
    existing_tmux = dict(data.get("tmux") or {})
    for key in TMUX_CONFIG_SCHEMA:
        existing_tmux.pop(key, None)
    if existing_tmux:
        data["tmux"] = existing_tmux
    else:
        data.pop("tmux", None)
```

### 2. Add `git_tui` to `TMUX_CONFIG_SCHEMA`

File: `.aitask-scripts/settings/settings_app.py` after `prefer_tmux` entry in `TMUX_CONFIG_SCHEMA` (around line 398)

Add:
```python
"git_tui": {
    "summary": "Git management TUI",
    "detail": (
        "External git TUI to integrate in the TUI switcher (j/g shortcut). "
        "Only one instance runs per tmux session. "
        "Set to 'none' to disable."
    ),
    "type": "enum",
    "options": "lazygit,gitui,tig,none",
    "default": "none",
},
```

This is sufficient because `_populate_tmux_tab()` auto-renders all `TMUX_CONFIG_SCHEMA` entries. The `save_tmux_settings()` method auto-saves all schema keys.

### 3. (Optional) Dynamic option detection

For better UX, modify `_populate_tmux_tab()` to dynamically detect installed tools and adjust the options list. Add import at top of file:

```python
from agent_launch_utils import detect_git_tuis
```

In `_populate_tmux_tab()`, when building the CycleField for `git_tui`, override options with detected tools + "none":

```python
if key == "git_tui":
    installed = detect_git_tuis()
    if installed:
        options_str = ",".join(installed) + ",none"
    # else keep default options from schema
```

This makes only installed tools cycleable, which is cleaner UX.

## Post-Implementation

Proceed to Step 9 (Post-Implementation) for archival.

## Verification

1. Open `ait settings` → Tmux tab → verify `git_tui` field appears with cycle options
2. Save settings → verify `tmux.monitor` section is preserved (the bug fix)
3. Change git_tui → save → check `project_config.yaml` has the value under `tmux.git_tui`

## Final Implementation Notes
- **Actual work done:** Implemented all 3 steps exactly as planned. Fixed the save_tmux_settings() data-loss bug (merge instead of overwrite), added git_tui enum field to TMUX_CONFIG_SCHEMA, and added dynamic option detection via detect_git_tuis() import. All automated verifications passed: detect_git_tuis() returns installed tools, schema loads correctly, and the save logic preserves tmux.monitor sub-dict.
- **Deviations from plan:** None — all file paths, line numbers, and code patterns matched the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Dynamic detection filters options to only installed tools + "none", falling back to the full static list if no tools are detected. This means the CycleField will only show relevant options.
- **Notes for sibling tasks:** The `detect_git_tuis` import is now available in settings_app.py. t507_4 (TUI switcher) should use `load_tmux_defaults()` to read the configured git_tui value, not the schema. The save bug fix means tmux.monitor and any future sub-dicts under tmux will be preserved when saving schema-tracked fields.
