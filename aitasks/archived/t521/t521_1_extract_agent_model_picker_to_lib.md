---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Done
labels: [codeagent, aitask_board]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_6
created_at: 2026-04-12 09:43
updated_at: 2026-04-12 10:50
completed_at: 2026-04-12 10:50
---

## Context

Pure refactor extracting the 3-step model picker modal (`AgentModelPickerScreen`) and its dependencies out of `.aitask-scripts/settings/settings_app.py` into a new module `.aitask-scripts/lib/agent_model_picker.py`. Required by sibling task t521_2, which wires the picker into the shared `AgentCommandScreen` launch dialog and cannot import from `settings/` without creating a circular dep or pulling the whole settings app into lib/.

**No behavior change.** After this task, `ait settings` must work identically. Only the physical location of the classes changes.

Part of t521 (parent) — see `aiplans/p521/` for the full plan and sibling tasks.

## Key Files to Modify

- `.aitask-scripts/lib/agent_model_picker.py` — **NEW FILE**. Home of the extracted classes.
- `.aitask-scripts/settings/settings_app.py` — remove extracted classes, add imports from the new lib module.

## Reference Files for Patterns

- `.aitask-scripts/lib/agent_command_screen.py` — another Textual `ModalScreen` that lives in `lib/`. Use as reference for imports and module structure.
- `.aitask-scripts/lib/config_utils.py` — provides `_load_json` (already used by `settings_app.py`). The new module should import `_load_json` from here.

## Implementation Plan

1. **Create `.aitask-scripts/lib/agent_model_picker.py`** with:
   - Module docstring.
   - Imports: `json`, `from pathlib import Path`, Textual widgets (`ModalScreen`, `Container`, `Horizontal`, `VerticalScroll`, `Input`, `Label`, `Static`, `Binding`, `Message`, `ComposeResult`), and `from config_utils import _load_json`.
   - `MODEL_FILES` constant (copy from `settings_app.py` line 64). Use `METADATA_DIR = Path("aitasks") / "metadata"` (same as settings_app).
   - `_bucket_avg()` helper (from `settings_app.py` line 472).
   - `_format_op_stats()` helper (from `settings_app.py` line 529).
   - `FuzzyOption` class (from `settings_app.py` line 802–821).
   - `FuzzySelect` class (from `settings_app.py` line 824–937).
   - `AgentModelPickerScreen` class (from `settings_app.py` line 942 through end of class — includes `_build_top_verified`, `compose`, `action_go_back`, `on_fuzzy_select_selected`, `on_fuzzy_select_cancelled`, `_show_step0`, `_show_step1`, `_show_step2`, and any other methods up to the next class definition).
   - **New helper** `load_all_models(project_root: Path | None = None) -> dict[str, dict]` that loads every `models_*.json` from `project_root / "aitasks" / "metadata"` into `{provider: data}`. Implementation:
     ```python
     def load_all_models(project_root: Path | None = None) -> dict[str, dict]:
         root = project_root or Path.cwd()
         result: dict[str, dict] = {}
         for provider, rel in MODEL_FILES.items():
             data = _load_json(root / rel)
             if data:
                 result[provider] = data
         return result
     ```

2. **Update `.aitask-scripts/settings/settings_app.py`:**
   - Remove the extracted `_bucket_avg`, `_format_op_stats`, `FuzzyOption`, `FuzzySelect`, and `AgentModelPickerScreen` class/function definitions.
   - Remove the `MODEL_FILES` constant definition.
   - Add imports after the existing `from agent_launch_utils import detect_git_tuis` line (line 21):
     ```python
     from agent_model_picker import (  # noqa: E402
         AgentModelPickerScreen,
         FuzzyOption,
         FuzzySelect,
         MODEL_FILES,
         _bucket_avg,
         _format_op_stats,
         load_all_models,
     )
     ```
     Only import names that are actually referenced in the remaining `settings_app.py` code. Start with `AgentModelPickerScreen, MODEL_FILES` (definitely needed), then grep-check the rest.
   - Before removing `_bucket_avg` / `_format_op_stats`, grep `settings_app.py` for their usages. If they are used anywhere outside the extracted picker (e.g., in `_aggregate_verifiedstats`, Models tab rendering, or `ConfigManager`), keep those usages working by importing from the new module.
   - Before removing `FuzzyOption` / `FuzzySelect`, grep for usages. If other modal screens in `settings_app.py` use them (e.g., `ProfilePickerScreen`), they must still work — import from the new module.

3. **Fix imports order:** the `sys.path.insert(0, ...lib)` at line 19 in `settings_app.py` adds lib to sys.path, so `from agent_model_picker import ...` will resolve. Place it after the `from tui_switcher` / `from agent_launch_utils` imports for consistency.

4. **Verify no residual references:** grep `settings_app.py` for `FuzzySelect`, `FuzzyOption`, `AgentModelPickerScreen`, `_bucket_avg`, `_format_op_stats`, and `MODEL_FILES`. Each reference must resolve through the new import.

## Verification Steps

1. Syntax check:
   ```bash
   python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py
   python3 -m py_compile .aitask-scripts/settings/settings_app.py
   ```
2. Import smoke test:
   ```bash
   python3 -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); from agent_model_picker import AgentModelPickerScreen, FuzzySelect, load_all_models, MODEL_FILES; print('OK')"
   ```
3. Run `ait settings` → open Agent Defaults tab → Enter on any `pick`/`explain`/`qa` row. The 3-step picker (top verified → agent browse → model browse) must open and behave exactly as before. Pick a model — the row updates and the value is saved to config on exit.
4. Run `ait settings` → Models tab → confirm stats rendering still works (verifies `_format_op_stats` still resolves).
5. Run `shellcheck` on any touched shell scripts (not applicable here — only Python files).
6. `./ait git status` should show 2 modified Python files + 1 new file.

## Dependencies

- **Must be completed before:** t521_2 (wire picker into AgentCommandScreen).
- **Depends on:** nothing.
