---
Task: t521_1_extract_agent_model_picker_to_lib.md
Parent Task: aitasks/t521_change_default_codeagent_at_run_time.md
Sibling Tasks: aitasks/t521/t521_2_wire_agent_picker_into_launch_dialog.md, aitasks/t521/t521_3_update_agent_command_screen_callers.md
Archived Sibling Plans: (none — all siblings pending)
Worktree: (none — working on current branch per fast profile)
Branch: main
Base branch: main
---

# p521_1 — Extract AgentModelPickerScreen to lib/agent_model_picker.py

## Context

Pure refactor. `AgentModelPickerScreen` is a 3-step fuzzy-search picker
(top verified → browse agents → browse models) currently defined inside
`.aitask-scripts/settings/settings_app.py`. Sibling task t521_2 needs to
import it from the shared launch dialog (`lib/agent_command_screen.py`),
but importing `settings/settings_app.py` from `lib/` would pull the entire
settings app into every TUI and risk circular imports. The clean fix is
to move the picker and its dependencies into a new `lib/` module.

**No behavior change.** `ait settings` must work identically after this task.

## Source line references in `settings/settings_app.py`

| Symbol | Line (approx) | Notes |
|--------|-------|-------|
| `MODEL_FILES` | 64 | Constant. Also used by `ConfigManager.load_all` for the Models tab. |
| `_bucket_avg` | 472 | Helper. Used by `_format_op_stats` and `_build_top_verified`. |
| `_format_op_stats` | 529 | Helper. Also used by Models tab rendering — verify before removing. |
| `FuzzyOption` | 802 | Used only by `FuzzySelect`. |
| `FuzzySelect` | 824 | Used by `AgentModelPickerScreen` and possibly `ProfilePickerScreen` — grep to confirm. |
| `AgentModelPickerScreen` | 942 | The main picker class. |

## Target

Create `.aitask-scripts/lib/agent_model_picker.py` containing:
- Module docstring
- `MODEL_FILES` constant
- `_bucket_avg`, `_format_op_stats`
- `FuzzyOption`, `FuzzySelect`
- `AgentModelPickerScreen`
- New `load_all_models(project_root=None) -> dict[str, dict]` helper

And update `.aitask-scripts/settings/settings_app.py` to import these from
`agent_model_picker` instead of defining them locally.

## Implementation Steps

### 1. Create `.aitask-scripts/lib/agent_model_picker.py`

Skeleton:

```python
"""agent_model_picker — Shared 3-step picker for code agent + LLM model selection.

Used by the settings TUI (to edit global defaults in codeagent_config.json)
and by the launch dialog (to override the agent/model for a single run).
The module is Textual-dependent but has no settings_app dependency.

Public API:
- AgentModelPickerScreen — ModalScreen presenting 3 steps:
    0: top-verified models for an operation
    1: browse all code agents
    2: browse models within a selected agent
- FuzzySelect / FuzzyOption — reusable fuzzy-search list widget
- MODEL_FILES — {provider: Path} map of models_*.json files
- load_all_models(project_root) — load every models_*.json into a dict
"""
from __future__ import annotations

import sys
from pathlib import Path

from textual import on
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Container, VerticalScroll
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import Input, Label, Static

# Resolve sibling lib import for _load_json
_LIB_DIR = str(Path(__file__).resolve().parent)
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from config_utils import _load_json  # noqa: E402


METADATA_DIR = Path("aitasks") / "metadata"
MODEL_FILES: dict[str, Path] = {
    "claudecode": METADATA_DIR / "models_claudecode.json",
    "codex": METADATA_DIR / "models_codex.json",
    "geminicli": METADATA_DIR / "models_geminicli.json",
    "opencode": METADATA_DIR / "models_opencode.json",
}


def load_all_models(project_root: Path | None = None) -> dict[str, dict]:
    """Load all models_*.json files into {provider: data}.

    Callers can use this instead of instantiating ConfigManager to get
    the all_models dict required by AgentModelPickerScreen.
    """
    root = project_root or Path.cwd()
    result: dict[str, dict] = {}
    for provider, rel in MODEL_FILES.items():
        data = _load_json(root / rel)
        if data:
            result[provider] = data
    return result


def _bucket_avg(bucket: dict) -> int:
    ...  # copy from settings_app.py:472

def _format_op_stats(buckets: dict, compact: bool = False) -> str:
    ...  # copy from settings_app.py:529


class FuzzyOption(Static):
    ...  # copy from settings_app.py:802-821

class FuzzySelect(Container):
    ...  # copy from settings_app.py:824-937

class AgentModelPickerScreen(ModalScreen):
    ...  # copy from settings_app.py:942 through end of class
```

**Key points:**
- Copy the class/function bodies *verbatim* — this is a pure move, not a
  rewrite.
- The `AgentModelPickerScreen.compose` method references `MODEL_FILES` for
  the step-1 agent list — this already reads from the module-level
  constant, so no change needed.
- `_show_step2` calls `_load_json(model_path)` where `model_path` comes
  from `MODEL_FILES.get(agent, ...)`. This will continue to work.

### 2. Update `.aitask-scripts/settings/settings_app.py`

**Discovery first:**
```bash
grep -n "FuzzySelect\|FuzzyOption\|AgentModelPickerScreen\|_bucket_avg\|_format_op_stats\|MODEL_FILES" .aitask-scripts/settings/settings_app.py
```

For each hit, confirm whether it's a definition (to delete) or a usage (to
update to the new import). Pay attention to `ProfilePickerScreen` and the
Models tab code — they may use `FuzzySelect` or `_format_op_stats`.

**Removals** (after confirming no other usages need them as locally defined):
- Delete the `MODEL_FILES = {...}` block around line 64.
- Delete `_bucket_avg` at line 472.
- Delete `_format_op_stats` at line 529.
- Delete `FuzzyOption` at line 802.
- Delete `FuzzySelect` at line 824.
- Delete the full `AgentModelPickerScreen` class at line 942.

**Additions** near the top of `settings_app.py`, after line 21
(`from agent_launch_utils import detect_git_tuis`):

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

Only include the names actually referenced by the remaining `settings_app.py`
code — the discovery step above tells you which ones. `AgentModelPickerScreen`
and `MODEL_FILES` are definitely needed; the rest depends on the grep.

### 3. Verify `_aggregate_verifiedstats` still works

`_aggregate_verifiedstats` (around line 480 in settings_app.py) uses
`_normalize_model_id`. It does NOT currently use `_bucket_avg` or
`_format_op_stats`, but double-check — if it does, add those imports.

## Verification

### Syntax
```bash
python3 -m py_compile .aitask-scripts/lib/agent_model_picker.py
python3 -m py_compile .aitask-scripts/settings/settings_app.py
```

### Import smoke test
```bash
python3 -c "import sys; sys.path.insert(0, '.aitask-scripts/lib'); \
  from agent_model_picker import (AgentModelPickerScreen, FuzzySelect, \
  FuzzyOption, MODEL_FILES, _bucket_avg, _format_op_stats, load_all_models); \
  print('OK')"
```

### Interactive test — `ait settings`
1. Run `ait settings`.
2. Open the "Agent Defaults" tab.
3. Press Enter on the `pick` row (project layer). The 3-step picker opens:
   - Step 0: Top verified models for `pick` (e.g. Claudecode Opus 4.6).
   - Select "Browse all models..." → Step 1: agent browser.
   - Pick an agent → Step 2: model browser.
4. Pick a model → confirm the row updates.
5. Press `s` to save → confirm `codeagent_config.json` diff.
6. Revert the save so the repo is clean (or remember to revert at commit time).

### Interactive test — other settings tabs
- "Models" tab renders with model stats visible.
- "Profiles" tab still edits profiles correctly.
- Profile picker still works (if it uses `FuzzySelect`).

### Git sanity
```bash
./ait git status
```
Expected: 1 new file (`lib/agent_model_picker.py`), 1 modified file (`settings/settings_app.py`). Nothing else.

## Step 9 reference

Per task-workflow Step 9: after implementation + review, run
`./.aitask-scripts/aitask_archive.sh 521_1`. No worktree cleanup (fast profile).
