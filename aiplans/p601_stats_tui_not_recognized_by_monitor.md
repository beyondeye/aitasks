---
Task: t601_stats_tui_not_recognized_by_monitor.md
Base branch: main
plan_verified: []
---

# Plan: Register `stats` TUI with ait monitor — centralize registry + merge config (t601)

## Context

The new `stats` TUI (launch: `ait stats-tui`) runs as a tmux window named `stats`, but `ait monitor` classifies it as `OTHER`. The user confirmed this visually in the current `aitasks` tmux session.

Two problems feed the bug:

1. **Duplication.** The "what counts as a TUI" set is declared in four places with slightly different contents, and `stats` is missing from the three non-switcher copies:

   | Location | Current contents | Role |
   |---|---|---|
   | `.aitask-scripts/monitor/tmux_monitor.py:32` `DEFAULT_TUI_NAMES` | board, codebrowser, settings, brainstorm, monitor, minimonitor, diffviewer, git | monitor pane classification |
   | `.aitask-scripts/lib/agent_launch_utils.py:233-234` `_DEFAULT_TUI_NAMES` | same | minimonitor auto-spawn exclusion |
   | `.aitask-scripts/lib/tui_switcher.py:59-66` `KNOWN_TUIS` (+ `_TUI_NAMES`) | board, monitor, codebrowser, settings, **stats**, diffviewer (+ dynamic `git`) | TUI switcher modal |
   | `aitasks/metadata/project_config.yaml` `tmux.monitor.tui_window_names` | board, codebrowser, settings, brainstorm, monitor, minimonitor, diffviewer, git | replaces the code default at load time |

2. **Replace semantics.** The config loader (both `tmux_monitor.load_monitor_config` and `agent_launch_utils.maybe_spawn_minimonitor`) currently treats `tui_window_names` as a full **replacement** of the code default. That means this repo's stale config masks any new TUI added to the code — which is exactly how `stats` ended up invisible.

Fix both: introduce a single registry and change the config semantics to **merge/union** — config names are additive to the framework default rather than a replacement.

## Approach

### 1. New module: `.aitask-scripts/lib/tui_registry.py`

Non-UI, stdlib-only. Single source of truth.

```python
"""tui_registry - Single source of truth for aitask TUI window registration.

Used by:
  - monitor/tmux_monitor.py            (pane classification)
  - lib/agent_launch_utils.py          (minimonitor auto-spawn exclusion)
  - lib/tui_switcher.py                (TUI switcher modal)

Adding a new TUI only requires adding one entry here.
"""
from __future__ import annotations

# (window_name, display_label, launch_command, in_switcher)
#   - window_name: exact tmux window name
#   - display_label / launch_command: only meaningful when in_switcher is True
#   - in_switcher=False still classifies the name as a TUI but hides it from
#     the switcher modal (per-task windows and companion panes)
TUI_REGISTRY: list[tuple[str, str | None, str | None, bool]] = [
    ("board",       "Task Board",    "ait board",       True),
    ("monitor",     "tmux Monitor",  "ait monitor",     True),
    ("codebrowser", "Code Browser",  "ait codebrowser", True),
    ("settings",    "Settings",      "ait settings",    True),
    ("stats",       "Statistics",    "ait stats-tui",   True),
    ("diffviewer",  "Diff Viewer",   "ait diffviewer",  True),
    ("brainstorm",  None,            None,              False),
    ("minimonitor", None,            None,              False),
]

# Prefix match also classified as TUI (per-task brainstorm windows).
BRAINSTORM_PREFIX = "brainstorm-"

# Full classification set. "git" is always included because the git TUI is
# surfaced dynamically from `tmux.git_tui` config and should classify as a TUI.
TUI_NAMES: frozenset[str] = frozenset({name for name, *_ in TUI_REGISTRY} | {"git"})


def switcher_tuis() -> list[tuple[str, str, str]]:
    """Return (name, label, command) tuples for TUIs shown in the switcher modal."""
    return [(n, l, c) for n, l, c, in_sw in TUI_REGISTRY if in_sw and l and c]
```

### 2. Change config loader semantics: replace → merge

Both consumers treat `tmux.monitor.tui_window_names` as **additive** over the registry default.

**`.aitask-scripts/monitor/tmux_monitor.py`** (`load_monitor_config`, around lines 536-537):

```python
# Before
if "tui_window_names" in monitor:
    defaults["tui_names"] = set(monitor["tui_window_names"])

# After
if "tui_window_names" in monitor:
    # Merge with defaults so new framework TUIs are never masked by stale config.
    defaults["tui_names"] = set(TUI_NAMES) | set(monitor["tui_window_names"])
```

Also replace `DEFAULT_TUI_NAMES` at line 32 with a re-export from the registry (keeps external test imports working):

```python
import sys
from pathlib import Path as _Path
_LIB_DIR = str(_Path(__file__).resolve().parent.parent / "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from tui_registry import TUI_NAMES as DEFAULT_TUI_NAMES, BRAINSTORM_PREFIX  # noqa: E402
```

In `classify_pane` (line ~135), replace the literal `"brainstorm-"` with `BRAINSTORM_PREFIX`.

**`.aitask-scripts/lib/agent_launch_utils.py`** (`maybe_spawn_minimonitor`, around lines 280-281):

```python
# Before
if "tui_window_names" in monitor:
    tui_names = set(monitor["tui_window_names"])

# After
if "tui_window_names" in monitor:
    tui_names = set(_DEFAULT_TUI_NAMES) | set(monitor["tui_window_names"])
```

Replace the local `_DEFAULT_TUI_NAMES` (lines 233-234) with a registry import:

```python
from tui_registry import TUI_NAMES as _DEFAULT_TUI_NAMES
```

### 3. `.aitask-scripts/lib/tui_switcher.py`

Replace `KNOWN_TUIS`, `_TUI_NAMES`, and `_BRAINSTORM_PREFIX` with registry imports (lines 59-84):

```python
from tui_registry import switcher_tuis, TUI_NAMES as _TUI_NAMES, BRAINSTORM_PREFIX as _BRAINSTORM_PREFIX

KNOWN_TUIS = switcher_tuis()
```

`_build_tui_list()` stays the same — it still injects the git entry dynamically from the `tmux.git_tui` config key.

### 4. `aitasks/metadata/project_config.yaml`

Remove the entire `tui_window_names` block under `tmux.monitor` (lines 14-22). With merge semantics in place, the block's only effect now would be to add entries on top of the registry — and there's nothing to add. The other `tmux.monitor` keys (`refresh_seconds`, `idle_threshold_seconds`, `capture_lines`, `agent_window_prefixes`) stay.

### 4b. `aitasks/metadata/userconfig.yaml` (dead-config cleanup)

The loaders in `tmux_monitor.py` and `agent_launch_utils.py` only read `project_config.yaml` — a `tmux.monitor.tui_window_names` block in `userconfig.yaml` has never had any effect. Remove the `tui_window_names` sublist from the user's `userconfig.yaml` (currently lines 20-29 of that local file). The file is gitignored on the data branch, so this is a local edit only — no commit needed for it.

Note (out of scope): the same userconfig file has other entries that are also never read from userconfig (full `tmux:` subtree, `codeagent_coauthor_domain`, `test_command`, `lint_command`). Leaving those alone for now; flag to user in the summary.

### 5. `tests/test_git_tui_config.py`

Add new assertions alongside the existing `git` tests:

- `test_stats_in_default_tui_names` — imports `tmux_monitor.DEFAULT_TUI_NAMES`, asserts `"stats"` present.
- `test_stats_in_tui_switcher_names` — imports `tui_switcher._TUI_NAMES`, asserts `"stats"` present.
- `test_registry_contains_all_framework_tuis` — imports `tui_registry.TUI_NAMES`, asserts presence of `stats`, `brainstorm`, `minimonitor`, `diffviewer`, `git`.
- `test_config_tui_names_merges_with_defaults` — writes a temp `project_config.yaml` with a custom `tui_window_names: [mytui]`, calls `load_monitor_config`, asserts the result contains both `"mytui"` (from config) and `"stats"` (from registry default).

### 6. `website/content/docs/tuis/monitor/reference.md`

Describe current state only (no history / no "this used to replace" language):

- Table row for `tmux.monitor.tui_window_names` (line 121): rewrite description to
  _"Additional window names classified as TUIs beyond the framework defaults. Framework-built TUIs (board, codebrowser, settings, brainstorm, monitor, minimonitor, stats) are always classified regardless of this setting. `brainstorm-*` prefix matches are also always included."_
  Remove the explicit "Default: board, codebrowser, …" list — it's no longer an override, it's an addendum, so the default is empty.
- Example YAML block (lines 96-108): reshape `tui_window_names` to show how a project would add a custom window name, e.g. `- my_custom_tui`, with a short comment `# optional: extra window names to classify as TUIs`. Keep the framework list out of the example to avoid it becoming a stale duplicate again.

No changes to `minimonitor/how-to.md` are needed — it already just references the key name.

## Out of Scope

- `aitasks/metadata/userconfig.yaml` — gitignored, and its `tui_window_names` block is never read by monitor/minimonitor (loaders only read `project_config.yaml`). Worth mentioning to the user as a cleanup note; not a code change.
- Ports to `.gemini/`, `.agents/`, `.opencode/` — no skill/command content changes.
- Promoting git into `TUI_REGISTRY` — git is deliberately config-driven via `tmux.git_tui`; the registry just ensures the `"git"` window name classifies as TUI when present.

## Verification

1. Registry sanity: from `.aitask-scripts/lib/` run `python3 -c "from tui_registry import TUI_NAMES, switcher_tuis; print(sorted(TUI_NAMES)); print([t[0] for t in switcher_tuis()])"`. Expect `stats` in both outputs.
2. Merge-semantics unit test: `python3 -m unittest tests.test_git_tui_config` (runs the new merge test plus the stats + git assertions).
3. Live check: restart `ait monitor` in the current `aitasks` tmux session (`stats` already lives at window index 7) and confirm it renders alongside `board`, `codebrowser`, etc., rather than in the `OTHER` bucket.
4. Switcher check: press `j` in any TUI — `stats` still appears with the `t` shortcut, and `brainstorm` / `minimonitor` still do **not** appear (they're `in_switcher=False`).
5. `shellcheck` not needed — no shell changes.

## Step 9 (Post-Implementation)

Follow the shared workflow: review → commit (`refactor: Centralize TUI registry and merge tui_window_names config (t601)`) → archive via `./.aitask-scripts/aitask_archive.sh 601` → `./ait git push`.
