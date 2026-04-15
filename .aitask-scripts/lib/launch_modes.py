"""Single source of truth for agent launch modes.

All call sites that validate, default, or enumerate launch modes must
import from this module. The shell bridge (``launch_modes_sh.sh``)
shells out here at runtime so shell consumers stay in sync
automatically.

Modes:
    headless              - subprocess, no UI, output piped to log file.
    interactive           - tmux window or terminal fallback, full Claude
                            Code UI. Integrates with ait monitor.
    openshell_headless    - (not yet implemented) sandboxed shell subprocess
                            running the agent non-interactively. Stubbed
                            in the runner with LaunchError; picker modals
                            and validators accept it.
    openshell_interactive - (not yet implemented) sandboxed shell subprocess
                            attached to a terminal for user inspection.
                            Stubbed; same acceptance as above.

The two openshell variants are placeholders that exercise the
single-source-of-truth migration and surface missed call sites at
runtime. Real launch semantics are tracked in a follow-up task.
"""
from __future__ import annotations

VALID_LAUNCH_MODES: frozenset[str] = frozenset(
    {"headless", "interactive", "openshell_headless", "openshell_interactive"}
)
DEFAULT_LAUNCH_MODE: str = "headless"


def validate_launch_mode(val: str) -> bool:
    return val in VALID_LAUNCH_MODES


def normalize_launch_mode(
    val: str | None, fallback: str = DEFAULT_LAUNCH_MODE
) -> str:
    if val is None or val not in VALID_LAUNCH_MODES:
        return fallback
    return val


def launch_modes_pipe() -> str:
    """Sorted pipe-separated alternation for shell regex consumers."""
    return "|".join(sorted(VALID_LAUNCH_MODES))
