---
Task: t515_changing_tmux_settings_bug.md
Worktree: (current branch)
Branch: main
Base branch: main
---

# Fix: Tmux settings save resets git_tui on first save (t515)

## Context

When the Settings TUI starts, `on_mount()` calls all six `_populate_*_tab()` methods sequentially. Each one increments the shared `_repop_counter` to generate unique widget IDs. The tmux tab gets counter value 4, but by the time all tabs finish populating, the counter is at 5 (profiles tab). When the user saves tmux settings, `save_tmux_settings()` reads the current `_repop_counter` (5) and queries for widgets with `_5` suffix — but the tmux widgets have `_4` suffix. All queries fail silently (`except Exception: pass`), `tmux_data` ends up empty, and the `else` branch at line 2760 strips all schema keys from the config, resetting `git_tui` to its default `"none"`.

This only happens once because `save_tmux_settings()` calls `_populate_tmux_tab()` at the end (line 2770), which re-increments the counter and creates fresh widgets matching the new counter value. Subsequent saves work correctly.

The same bug pattern exists in `_save_profile()` (line 3145) which also uses `self._repop_counter` directly.

## Fix

Store per-tab counter values so each save function uses the counter that was active when its tab was last populated.

### File: `.aitask-scripts/settings/settings_app.py`

**1. Add per-tab counter variables in `__init__`** (after line 1894):
```python
self._tmux_tab_rc: int = 0
self._profiles_tab_rc: int = 0
```

**2. Store counter in `_populate_tmux_tab()`** (after line 2663 `rc = self._repop_counter`):
```python
self._tmux_tab_rc = rc
```

**3. Use stored counter in `save_tmux_settings()`** (line 2732):
Change `rc = self._repop_counter` → `rc = self._tmux_tab_rc`

**4. Store counter in `_populate_profiles_tab()`** (after line 2907 `rc = self._repop_counter`):
```python
self._profiles_tab_rc = rc
```

**5. Use stored counter in `_save_profile()`** (line 3145):
Change `rc = self._repop_counter` → `rc = self._profiles_tab_rc`

## Verification

1. Run the Settings TUI: `python .aitask-scripts/settings/settings_app.py`
2. Go to Tmux tab — verify git_tui shows "lazygit" (matching project_config.yaml)
3. Toggle prefer_tmux and click Save
4. Verify git_tui is still "lazygit" after save
5. Check `aitasks/metadata/project_config.yaml` — git_tui should be preserved
6. Refer to Step 9 (Post-Implementation) for archival

## Final Implementation Notes
- **Actual work done:** Added per-tab counter snapshots (`_tmux_tab_rc`, `_profiles_tab_rc`) stored when each tab is populated, used by save/edit handlers instead of the shared `_repop_counter`. Fixed 5 locations total: `save_tmux_settings`, `_handle_tmux_config_edit`, `_save_profile`, and `_handle_profile_string_edit`.
- **Deviations from plan:** Also fixed `_handle_tmux_config_edit` (line 2789) and `_handle_profile_string_edit` (line 3286) which had the same bug pattern — these were not in the original plan but discovered during implementation.
- **Issues encountered:** None.
- **Key decisions:** Used per-tab counter snapshots rather than refactoring to per-tab counters, keeping the shared counter for its original purpose (ensuring globally unique IDs) while giving each tab a stable reference for widget queries.
