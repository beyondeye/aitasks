"""Canonical task level enum (high/medium/low), shared by priority, effort,
and the two risk fields (risk_code_health, risk_goal_achievement). Single
Python source of truth — mirror of TASK_LEVELS in
.aitask-scripts/lib/task_utils.sh."""

LEVELS = ("high", "medium", "low")            # canonical, severity-descending
LEVELS_ASCENDING = ("low", "medium", "high")  # ascending, for UI pickers


def is_valid_level(value: str) -> bool:
    """Return True if ``value`` is a valid task level."""
    return value in LEVELS
