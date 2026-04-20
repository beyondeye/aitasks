---
priority: medium
effort: medium
depends: [t597_3]
issue_type: feature
status: Implementing
labels: [statistics, aitask_monitor]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-04-19 17:52
updated_at: 2026-04-20 09:09
---

## Context

Fourth child of t597. Adds the pane-config modal (preset picker + custom layout builder) and layered persistence (project-level presets in `aitasks/metadata/stats_config.json`, user-level active layout + custom combos in `stats_config.local.json`).

User-confirmed shape: open with `c`. Modal shows preset list (Overview, Labels & Issue Types, Agents & Models, Velocity) + saved custom layouts + a "+ New custom" entry that opens a multi-select pane chooser plus a name input.

## Key Files to Modify

- `.aitask-scripts/stats/stats_config.py` (NEW) — schema, defaults, `load()`, `save()`.
- `.aitask-scripts/stats/modals/__init__.py` (NEW).
- `.aitask-scripts/stats/modals/config_modal.py` (NEW) — `ModalScreen`.
- `.aitask-scripts/stats/modals/name_input.py` (NEW) — small `Input` modal for naming a new custom layout.
- `.aitask-scripts/stats/stats_app.py` — replace `c` stub with `push_screen(ConfigModal(...))`; on close, reload sidebar from new active layout.
- `aitasks/metadata/stats_config.json` (NEW, committed via `./ait git`) — ships the four preset definitions.
- `.gitignore` — ensure `stats_config.local.json` is gitignored (verify existing `*.local.json` rule covers it; add explicit entry if not).

## Reference Files for Patterns

- `.aitask-scripts/board/aitask_board.py` lines 235–251 — `load_layered_config` / `split_config` / `save_project_config` / `save_local_config` usage. Same helpers (likely from `lib/config_utils.py`) — find and reuse.
- `.aitask-scripts/board/aitask_board.py` METADATA_FILE / `_PROJECT_KEYS` / `_USER_KEYS` split.
- `.aitask-scripts/settings/settings_app.py` `ProfilePickerScreen`, `NewProfileScreen`, `SaveProfileConfirmScreen` (lines ~1221–1452) — modal patterns for preset/custom combo + name input.
- Sibling `aiplans/p597/p597_3_*.md` for `PANE_DEFS` (the pool the custom builder picks from).

## Implementation Plan

1. **`stats_config.py`**:
   - Default presets dict (Overview / Labels / Agents / Velocity → list of pane ids).
   - `_PROJECT_KEYS = ["presets"]`, `_USER_KEYS = ["active", "active_pane_id", "days", "week_start", "custom"]`.
   - `load() -> dict`: layered load, return merged config.
   - `save(config)`: split via `split_config`, save project + local halves.
   - `resolve_active_layout(config) -> list[str]`: returns the list of pane ids for the active preset OR custom layout name. Falls back to `presets["overview"]` if active is missing.
2. **`config_modal.py`** (`ModalScreen[Optional[str]]`):
   - Two-pane layout: left list (presets + customs + "+ New custom"), right detail (preview of which panes are in the selected layout, with edit affordance for custom).
   - On select preset → "Apply" updates `config["active"]`, saves, returns the new active name.
   - On "+ New custom" → push `NameInputModal`; on name returned, switch right pane to a `SelectionList` of all `PANE_DEFS` keys grouped by category. "Save" stores `config["custom"][name] = [...]` and sets active.
   - Edit existing custom: pre-check the corresponding entries in `SelectionList`.
   - Delete custom: a `d` binding on a custom row removes it after a confirm; cannot delete presets.
3. **`name_input.py`**: `ModalScreen[str]` with one `Input` and OK/Cancel — returns the name string or `None`.
4. **`stats_app.py` integration**:
   - On startup, load config; populate sidebar from `resolve_active_layout(config)`.
   - `action_config()` → `push_screen(ConfigModal(config), self._on_config_done)`.
   - Callback: if a new layout name returned, refresh sidebar and content.
5. **Ship presets**: write `aitasks/metadata/stats_config.json` with the 4 presets; commit via `./ait git`.
6. **Gitignore check**: grep `.gitignore` for `*.local.json`. If absent, append `aitasks/metadata/stats_config.local.json`.
7. **Priority binding caveat** (memory `feedback_textual_priority_bindings`): `c` and `up`/`down` bindings must respect the modal screen — scope guards in app-level handlers to `self.screen.query_one(...)` and raise `SkipAction` so modal-level bindings can fire.

## Verification Steps

```bash
ait stats-tui
# Press c → modal opens. Pick "Labels" preset → Apply → sidebar reflects labels panes.
# c again → "+ New custom" → name "myview" → check 2-3 panes → Save → sidebar reflects.
# Quit, relaunch → "myview" is the active layout (persistence works).
# cat aitasks/metadata/stats_config.json        # presets present, no user state
# cat aitasks/metadata/stats_config.local.json  # active + custom present
git status                                       # .local.json must NOT be tracked
```

## Out of Scope

- Removing `--plot` (t597_5).
- Manual end-to-end verification (t597_6 — automated checks here are partial).
