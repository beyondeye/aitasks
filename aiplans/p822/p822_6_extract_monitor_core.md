---
Task: t822_6_extract_monitor_core.md
Parent Task: aitasks/t822_new_ait_bridge_tui.md
Sibling Tasks: aitasks/t822/t822_10_applink_append_fastpath.md, aitasks/t822/t822_11_applink_modal_handshakes.md, aitasks/t822/t822_12_applink_permissions_doc_sync.md, aitasks/t822/t822_13_applink_headless_monitor_flag.md, aitasks/t822/t822_4_manual_verification_new_ait_bridge_tui.md, aitasks/t822/t822_5_applink_qr_add_hostname_field.md, aitasks/t822/t822_7_applink_websocket_listener.md, aitasks/t822/t822_8_applink_snapshot_push_loop.md, aitasks/t822/t822_9_applink_delta_engine.md
Archived Sibling Plans: aiplans/archived/p822/p822_1_applink_protocol_design.md, aiplans/archived/p822/p822_2_applink_tui_qr.md, aiplans/archived/p822/p822_3_monitor_port_design.md
Base branch: main
plan_verified: []
---

# Plan: t822_6 — Extract the headless monitor core into `monitor_core.py`

## Context

`ait monitor` / `ait minimonitor` and the future `ait applink` WebSocket
listener (sibling t822_7+) all need the **non-Textual** half of the monitor
pipeline — pane discovery, capture, idle detection, tmux control-mode client,
and the task-metadata cache. Today that logic is spread across three modules
in `.aitask-scripts/monitor/`:

- `tmux_monitor.py` (754 lines) — already a non-UI module: `TmuxMonitor`,
  `TmuxPaneInfo`/`PaneSnapshot`, `PaneCategory`, compare-mode constants,
  `load_monitor_config`, the `tmux_run`/`_tmux_async` gateway-delegation seam.
- `tmux_control.py` (593 lines) — already non-UI: `TmuxControlClient`,
  `TmuxControlState`, `TmuxControlBackend` (the persistent `tmux -C` client).
- `monitor_shared.py` (760 lines) — **mixed**: the headless `TaskInfo` /
  `TaskInfoCache` (+ `_TASK_ID_RE`) live here alongside Textual dialogs and
  rich-rendering helpers.

This task is the first §"Deferred follow-up tasks" bullet of the design doc
`aidocs/applink/monitor_port_design.md` (authored by t822_3). It creates a
single cohesive `monitor_core.py` holding exactly the headless symbols the
design's §Headless-core extraction table names, leaving **thin re-export
shims** in the three original files so every existing import site keeps
working. It is a behavior-preserving **code-motion refactor** — no new
behavior, no applink wiring (that's t822_7+).

Two hard rules inherited from t822_3 / the t952 tmux-gateway track:
1. `monitor_core` **delegates** tmux exec to `lib/tmux_exec.py`
   (`TmuxClient.run_via_control` / `run_async_via_control`). The delegation
   seam already exists (`TmuxMonitor.tmux_run` / `_tmux_async`,
   `tmux_monitor.py:207-231`) and moves as-is — `monitor_core` must NOT
   re-own the control-client-vs-subprocess dispatcher.
2. **No Textual imports in `monitor_core`.**

The physical relocation of `TmuxControlClient` / `TmuxControlBackend` out of
`tmux_control.py` was deliberately deferred from t952_3 to ride with this
extraction — `monitor_core` is their natural home.

### Verification of the design doc's symbol table (re-checked on-disk 2026-06-14)

The doc warned line refs may have drifted under t952 churn. Re-verified —
symbol names are stable; current locations:

| Symbol(s) | Current location |
|-----------|------------------|
| `PaneCategory`, `DEFAULT_AGENT_PREFIXES`, `DEFAULT_TUI_NAMES`, `COMPARE_MODE_STRIPPED/RAW`, `COMPARE_MODES`, `DEFAULT_COMPARE_MODE`, `_ANSI_CSI_RE`, `_strip_ansi`, `_COMPANION_KEYWORDS`, `_is_companion_process` | `tmux_monitor.py:49-103` |
| `TmuxPaneInfo`, `PaneSnapshot` | `tmux_monitor.py:104,118` |
| `TmuxMonitor` (incl. `start/close/has_control_client`, `control_state`, `tmux_run`/`_tmux_async`, `discover_panes(_async)`, `cycle_compare_mode`, `capture_*`, `send_*`, `switch_to_pane`, `find_companion_pane_id`, `kill_*`, `kill_agent_pane_smart`, `spawn_tui`, …) | `tmux_monitor.py:129-715` |
| `load_monitor_config` | `tmux_monitor.py:716` |
| `_quote_arg`, `TmuxControlClient`, `TmuxControlState`, `TmuxControlBackend` (+ module regexes/limits `_HEAD_RE`, `_EXIT_RE`, `_DEFAULT_STREAM_LIMIT`, `_DEFAULT_CLOSE_TIMEOUT`) | `tmux_control.py:63-593` |
| `_TASK_ID_RE`, `TaskInfo`, `TaskInfoCache` (incl. `_resolve`, `find_next_sibling`, `find_ready_siblings`, `get_task_id/info`, …) | `monitor_shared.py:86,89,103-415` |

Confirmed `TaskInfo`/`TaskInfoCache` are fully Textual/rich-free (deps: `re`,
`Path`, `parse_frontmatter`, `_TASK_ID_RE`). Confirmed `tmux_control.py` has
no reverse dependency on `tmux_monitor` (imports only `tmux_exec`), so the
merge is acyclic.

### Import surface (every consumer, grep-verified — drives the shim contract)

All consumers put `.aitask-scripts/` on `sys.path` and import `monitor` as a
**package** (`from monitor.X import …`); the launchers run `monitor_app.py` /
`minimonitor_app.py` which do the same. So shims use the package-absolute
form `from monitor.monitor_core import …`.

- `monitor_app.py:27-38` → from `tmux_monitor`: `PaneCategory, PaneSnapshot,
  TmuxMonitor, load_monitor_config`; from `tmux_control`: `TmuxControlState`;
  from `monitor_shared`: `_ansi_to_rich_text, _TASK_ID_RE, TaskInfo,
  TaskInfoCache, TaskDetailDialog, KillConfirmDialog, NextSiblingDialog,
  ChooseSiblingModal, format_compare_mode_glyph, format_pane_status`.
- `minimonitor_app.py:26-37` → same `tmux_monitor`/`tmux_control` sets; from
  `monitor_shared`: `_TASK_ID_RE, TaskInfoCache, TaskDetailDialog,
  KillConfirmDialog, NextSiblingDialog, ChooseSiblingModal,
  format_compare_mode_glyph, format_pane_status`.
- `monitor_shared.py:20` → `from monitor.tmux_monitor import PaneSnapshot`.
- Tests: `test_idle_compare_modes.py` (`TmuxMonitor, TmuxPaneInfo,
  PaneCategory, COMPARE_MODE_RAW, COMPARE_MODE_STRIPPED`),
  `test_prompt_detection.py` (`TmuxMonitor, TmuxPaneInfo, PaneCategory`),
  `test_git_tui_config.py` (`DEFAULT_TUI_NAMES, load_monitor_config`),
  `test_tmux_exec.py` (`TmuxControlClient` from `monitor.tmux_control`),
  `test_task_info_cache_archived.py` (`TaskInfoCache` from
  `monitor.monitor_shared`).

## Approach (recommended)

Create `monitor_core.py` as the single home for the headless symbols; convert
the three source files to re-export shims. Because `tmux_monitor.py` and
`tmux_control.py` are *already* entirely non-UI, their whole bodies move; only
`monitor_shared.py` is split (task-context out, dialogs/render-helpers stay).

### Step 1 — Create `.aitask-scripts/monitor/monitor_core.py`

Assemble in this order (with `from __future__ import annotations`, so
definition order is runtime-safe and the existing forward-ref annotations keep
working):

1. **Module docstring** — "Headless monitor core: pane discovery/capture, idle
   detection, tmux control-mode client, and task-metadata cache. No Textual
   imports — shared by `ait monitor`, `ait minimonitor`, and `ait applink`."
2. **Imports** (deduped union of the three files): stdlib (`asyncio`,
   `collections`, `contextlib`, `enum`, `os`, `re`, `subprocess`, `sys`,
   `threading`, `time`, `dataclass`, `Enum`, `Path`, `Optional`,
   `TYPE_CHECKING`); the `lib/` `sys.path` insert; `from tmux_exec import
   TmuxClient, tmux_socket_args`; `from tui_registry import BRAINSTORM_PREFIX,
   TUI_NAMES`; `from agent_launch_utils import (AitasksSession,
   discover_aitasks_sessions, switch_to_pane_anywhere, tmux_session_target,
   tmux_window_target)`; `from task_yaml import parse_frontmatter`; and the
   `prompt_patterns` try/except dual-import carried over verbatim from
   `tmux_monitor.py:44-46`. Drop the `TYPE_CHECKING: from .tmux_control import
   TmuxControlBackend` block — same-module now.
3. **Constants/helpers** from `tmux_monitor.py`: `PaneCategory`,
   `DEFAULT_AGENT_PREFIXES`, `DEFAULT_TUI_NAMES`, the compare-mode block,
   `_ANSI_CSI_RE`, `_strip_ansi`, `_COMPANION_KEYWORDS`, `_is_companion_process`.
4. **Dataclasses**: `TmuxPaneInfo`, `PaneSnapshot`.
5. **Control-mode classes** from `tmux_control.py`: `_quote_arg`, its module
   regexes/limits, `TmuxControlClient`, `TmuxControlState`, `TmuxControlBackend`.
6. **`TmuxMonitor`** from `tmux_monitor.py`, with the two runtime defer-imports
   replaced by same-module references:
   - `start_control_client` (`:178`): delete `from .tmux_control import
     TmuxControlBackend`; reference `TmuxControlBackend` directly.
   - `control_state` (`:202`): delete `from .tmux_control import
     TmuxControlState`; reference `TmuxControlState` directly.
7. **`load_monitor_config`**.
8. **Task context** from `monitor_shared.py`: `_TASK_ID_RE`, `TaskInfo`,
   `TaskInfoCache` (all methods, unchanged).

### Step 2 — Convert `tmux_monitor.py` to a re-export shim

Replace the body with a docstring ("Backwards-compatibility shim — the
implementation moved to `monitor_core.py` (t822_6). Add new code there, not
here.") and an explicit re-export:

```python
from monitor.monitor_core import (  # noqa: F401
    PaneCategory, TmuxPaneInfo, PaneSnapshot, TmuxMonitor, load_monitor_config,
    DEFAULT_AGENT_PREFIXES, DEFAULT_TUI_NAMES,
    COMPARE_MODE_STRIPPED, COMPARE_MODE_RAW, COMPARE_MODES, DEFAULT_COMPARE_MODE,
    _strip_ansi,
)
```

(Names chosen to cover every grep'd import + the public constants; `_strip_ansi`
kept defensively as it was module-public.)

### Step 3 — Convert `tmux_control.py` to a re-export shim

```python
from monitor.monitor_core import (  # noqa: F401
    TmuxControlClient, TmuxControlState, TmuxControlBackend,
)
```

Plus the shim docstring.

### Step 4 — Split `monitor_shared.py`

- Replace the moved definitions (`_TASK_ID_RE` `:86`, `TaskInfo` `:89-100`,
  `TaskInfoCache` `:103-415`) with a single import from the new home, and
  repoint the existing `PaneSnapshot` import (`:20`) to `monitor_core`:
  ```python
  from monitor.monitor_core import (  # noqa: E402,F401
      PaneSnapshot, _TASK_ID_RE, TaskInfo, TaskInfoCache,
  )
  ```
  (Re-exporting `_TASK_ID_RE`/`TaskInfo`/`TaskInfoCache` keeps
  `monitor_app`/`minimonitor_app`/`test_task_info_cache_archived` imports from
  `monitor.monitor_shared` working.)
- **Keep** in `monitor_shared.py`: the Textual dialogs (`TaskDetailDialog`,
  `KillConfirmDialog`, `NextSiblingDialog`, `ChooseSiblingModal`,
  `_SiblingRow`), and the render helpers (`_ansi_to_rich_text`,
  `format_pane_status`, `format_compare_mode_glyph`, `COMPARE_MODE_ICONS`,
  `_DARK_BG_ANSI` & friends). These are UI-bound and stay.

### Step 5 — Update the raw-tmux test allowlist

`tests/test_no_raw_tmux.sh:51` allowlists `monitor/tmux_control.py` (the
`tmux -C attach` client). That raw spawn moves into `monitor_core.py`, so add
`.aitask-scripts/monitor/monitor_core.py` to `ALLOWLIST` with the same reason,
and drop the now-shim `tmux_control.py` entry (the shim issues no raw tmux).
Re-run the test to confirm.

## Files modified

- **New:** `.aitask-scripts/monitor/monitor_core.py`
- `.aitask-scripts/monitor/tmux_monitor.py` → shim
- `.aitask-scripts/monitor/tmux_control.py` → shim
- `.aitask-scripts/monitor/monitor_shared.py` → task-context import moved out
- `tests/test_no_raw_tmux.sh` → allowlist entry

No consumer (`monitor_app.py`, `minimonitor_app.py`, any test) is edited — the
shims preserve their import paths. That is the explicit backwards-compat goal.

## Verification

1. `grep -n 'import.*textual\|from textual\|from rich' .aitask-scripts/monitor/monitor_core.py` → no matches (hard rule).
2. `grep -n 'run_via_control\|run_async_via_control' .aitask-scripts/monitor/monitor_core.py` → present (delegation seam intact); confirm no re-implemented dispatcher.
3. Import checks (from a context with `.aitask-scripts` on path):
   `python -c "from monitor.monitor_core import TmuxMonitor, TmuxControlBackend, TaskInfoCache, PaneSnapshot"` and the same via the shims
   `python -c "from monitor.tmux_monitor import TmuxMonitor, load_monitor_config, DEFAULT_TUI_NAMES; from monitor.tmux_control import TmuxControlClient, TmuxControlState; from monitor.monitor_shared import TaskInfo, TaskInfoCache, _TASK_ID_RE, KillConfirmDialog"`.
4. Test files:
   `bash tests/test_no_raw_tmux.sh`,
   `python -m pytest tests/test_tmux_exec.py tests/test_idle_compare_modes.py tests/test_prompt_detection.py tests/test_task_info_cache_archived.py tests/test_git_tui_config.py` (or run each directly per repo convention).
5. `shellcheck tests/test_no_raw_tmux.sh` (touched shell).
6. Launch both TUIs against a live tmux session: `ait monitor` and
   `ait minimonitor` render panes, preview, and task-detail without import
   errors. (Aggregate manual verification for the t822 children is owned by
   sibling t822_4.)

## Out of scope

- Any applink wiring (WebSocket listener, snapshot/delta loop) — siblings
  t822_7+.
- Editing `monitor_app.py` / `minimonitor_app.py` imports — the shims exist
  precisely so these stay untouched.
- The `permissions.md` verb-table sync — separate §follow-up bullet.

## Risk

### Code-health risk: medium
- Behavior-preserving code motion across a central, load-bearing subsystem
  (two live TUIs + the persistent `tmux -C` control client). The real failure
  modes are mechanical: a symbol missed in a shim's re-export list, a circular
  import, or a stale raw-tmux allowlist entry. · severity: medium · →
  mitigation: inline — the re-export lists are derived from a grep of every
  consumer import site, and the five existing import-site tests + both TUI
  launches + the textual/delegation greps in Verification exercise the entire
  surface. No separate before/after task de-risks this further.

### Goal-achievement risk: low
- The extraction set, seam, and shim contract are fully specified by
  `aidocs/applink/monitor_port_design.md`; the modules are already non-UI, so
  the seam is clean and the deliverable is pure code motion with a
  grep-verified symbol table. None identified.

## Post-implementation

Follow shared workflow Step 8 (review) → Step 9 (child-task archival to
`aitasks/archived/t822/`, plan to `aiplans/archived/p822/`; parent t822 stays
open with remaining children). Pre-existing defect to note at Step 8b:
`aidocs/benchmarks/bench_monitor_refresh.py:94` monkeypatches
`_tm._run_tmux_async`, a symbol already deleted in t952_3 — the benchmark is
already broken independent of this task; this refactor neither fixes nor
worsens it.
