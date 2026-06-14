"""tmux_control - Backwards-compatibility shim.

The persistent `tmux -C` (control mode) client moved to `monitor_core.py`
(t822_6, completing the relocation deferred from t952_3); this module now only
re-exports it so existing import sites (`from monitor.tmux_control import …`)
keep working. **Add new code to `monitor_core.py`, not here.**

See `monitor_core.py` for the design rationale and the control-mode
lifecycle (`TmuxControlClient` / `TmuxControlBackend` / `TmuxControlState`).
"""
from monitor.monitor_core import (  # noqa: F401  (re-export shim)
    TmuxControlClient,
    TmuxControlState,
    TmuxControlBackend,
)
