"""Single source of truth for agent launch modes.

All call sites that validate, default, or enumerate launch modes must
import from this module. The shell bridge (``launch_modes_sh.sh``)
shells out here at runtime so shell consumers stay in sync
automatically.

Note: ``openshell`` is present in the vocabulary as a canary/placeholder.
Real launch semantics for it are not implemented yet — the runner
dispatch in ``agentcrew_runner.py`` will warn and skip on encounter.
The placeholder exists to exercise the single-source-of-truth refactor
and make missed call sites visible at runtime. Actual ``openshell``
support is a follow-up task (see t461_9).
"""
from __future__ import annotations

VALID_LAUNCH_MODES: frozenset[str] = frozenset(
    {"headless", "interactive", "openshell"}
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
