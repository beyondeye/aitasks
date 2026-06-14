"""tmux_monitor - Backwards-compatibility shim.

The implementation moved to `monitor_core.py` (t822_6); this module now only
re-exports the headless monitor symbols so existing import sites
(`from monitor.tmux_monitor import …`) keep working. **Add new code to
`monitor_core.py`, not here.**

Non-UI surface (no Textual dependency): pane discovery, content capture, idle
detection, and pane categorization for tmux sessions.

Usage:
    from monitor.tmux_monitor import TmuxMonitor, load_monitor_config

    config = load_monitor_config(project_root)
    monitor = TmuxMonitor(session="aitasks", **config)
    snapshots = monitor.capture_all()
"""
from monitor.monitor_core import (  # noqa: F401  (re-export shim)
    PaneCategory,
    TmuxPaneInfo,
    PaneSnapshot,
    TmuxMonitor,
    load_monitor_config,
    DEFAULT_AGENT_PREFIXES,
    DEFAULT_TUI_NAMES,
    COMPARE_MODE_STRIPPED,
    COMPARE_MODE_RAW,
    COMPARE_MODES,
    DEFAULT_COMPARE_MODE,
    _strip_ansi,
    _TEXTUAL_TO_TMUX,
    translate_key,
    task_id_from_window_name,
    count_other_real_agents,
    is_shadow_target,
    SHADOW_TARGET_OPTION,
)
