---
Task: t280_show_verified_info_in_ait_settings_model_sel.md
Worktree: (current branch)
Branch: main
Base branch: main
---

## Context

Task t280 asks to show verified model information in the `ait settings` TUI. Currently, the Agent Defaults tab shows only the agent/model string (e.g., "claudecode/opus4_6") with no indication of whether that model has been tested for the selected operation. The model picker modal shows `[verified:80]` only when score > 0 but shows nothing when score is 0, leaving users unaware that a model is unverified.

## Plan

All changes in a single file: `aiscripts/settings/settings_app.py`

### 1. Add `raw_value` to `ConfigRow.__init__` (~line 466)

Add a `raw_value` parameter that stores the original value without display decorations. Defaults to `value` if not provided. This prevents Rich markup from corrupting the value when the user edits a row.

### 2. Improve model picker modal display (`AgentModelPickerScreen._show_step2`, ~line 726)

Replace the current single-line score logic with three-tier logic:
- `op_score > 0` → `[score: 80]`
- `op_score == 0` but operation key exists in `verified` → `(not verified)`
- Operation key not in `verified` (e.g., "raw") → show nothing

### 3. Add helper method `_get_verified_label` to `SettingsApp` (~before line 1227)

Looks up verified score for an agent/model/operation combo using `self.config_mgr.models`. Returns Rich markup string.

### 4. Use helper in `_populate_agent_tab` (~lines 1253-1269)

Append verified label to both project and user ConfigRow display values. Pass `raw_value` to ConfigRow so editing still works.

### 5. Fix editing handler (~line 1145)

Use `focused.raw_value` instead of `focused.value` so the model picker receives clean agent/model strings without Rich markup.

## Verification

Run `./ait settings` and:
1. Check Agent Defaults tab — each operation row should show score or "(not verified)" next to the model
2. Press Enter on a row — modal should show score/not-verified for each model option
3. Select a model — confirm editing still works (raw_value parsed correctly)
4. Operations without verified entries (like "raw") should show no label

## Final Implementation Notes
- **Actual work done:** Implemented all 5 planned changes exactly as designed — added `raw_value` to ConfigRow, three-tier verified display in modal, helper method, agent tab integration, and editing handler fix.
- **Deviations from plan:** None — implementation followed the plan exactly.
- **Issues encountered:** None.
- **Key decisions:** Used `raw_value` attribute on ConfigRow rather than regex stripping to cleanly separate display markup from raw data for editing.
