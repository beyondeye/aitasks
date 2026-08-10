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
    strip_ansi,
    # `strip_ansi` was `_strip_ansi` until t1216_1, when it moved to
    # `monitor/ansi_utils.py` and lost the underscore. No in-tree caller used the
    # private name, but keeping the old alias costs one line and this module's
    # whole job is to keep existing import sites working — including ones we
    # cannot see.
    strip_ansi as _strip_ansi,
    _TEXTUAL_TO_TMUX,
    translate_key,
    task_id_from_window_name,
    count_other_real_agents,
    is_shadow_target,
    SHADOW_TARGET_OPTION,
    SHADOW_ANALYZED_AT_OPTION,
    # Shared shadow seam (t1216_1) — lifted out of minimonitor_app so both apps
    # import one implementation. All take a duck-typed `monitor` (the gateway
    # surface only), or none at all, rather than a concrete TmuxMonitor.
    match_shadow_pane,
    shadow_query_args,
    find_shadow_pane,
    find_shadow_pane_async,
    capture_shadow_text,
    compute_shadow_staleness,
    refresh_shadow_phase_stamp,
    # Shadow spawn seam (t1216_4) — the monitor is a second spawn surface, so
    # placement, the stamp and the cleanup-hook wiring live in one body.
    find_shadow_pane_status,
    spawn_shadow,
    load_project_tmux_config,
    _SHADOW_CAPTURE_TIMEOUT,
    _SHADOW_DEEP_RETRY_LINES,
    _SHADOW_TRUNCATED_MSG,
)
