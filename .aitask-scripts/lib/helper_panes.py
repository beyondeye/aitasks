#!/usr/bin/env python3
"""The bound-helper pane rule (t2073_3): one definition, every consumer.

A *bound helper* is a pane that exists to serve one agent pane and carries that
agent's ``pane_id`` in a pane-scoped tmux user option. Two kinds exist today:

* the **shadow** agent (``@aitask_shadow_target``, t986);
* the **scratchpad** notes editor (``@aitask_scratchpad_target``, t2073).

Every bound helper obeys the same rule, whatever its kind:

* it is excluded from agent lists and snapshots (discovery);
* it never counts as a real agent when deciding whether a window still holds one
  (``classify_window_panes``, the minimonitor occupancy check, the companion
  cleanup hook, the minimonitor sibling fallback);
* it is killed when its target pane dies (cleanup job 1);
* it is never killed when a *sibling* dies while its target lives.

**Frozen precedence is the caller's job and is never optional.** A pane stamped
``@aitask_frozen`` is a frozen stand-in, never a helper — even when a helper
target retained from whatever ran in the pane before the respawn says otherwise.
Every consumer checks the frozen marker FIRST, exactly as
``monitor_core.classify_window_panes`` does.

Every Python format that classifies helpers carries every option in
:data:`BOUND_HELPER_TARGET_OPTIONS` (positional formats name them field by
field; ``tests/test_helper_panes.py`` pins that each one is present). The one
bash copy
(``aitask_companion_cleanup.sh``, which runs as a tmux ``pane-died`` job) is kept
in step by ``tests/test_cleanup_rule_parity.sh`` plus a tripwire in
``tests/test_helper_panes.py`` asserting that every option in the tuple appears
in both of the script's ``-F`` formats. Add a kind here and that tripwire fails
until the script reads it too.

Lives in ``lib/`` because both ``monitor/monitor_core.py`` and
``lib/agent_launch_utils.py`` consume it, and lib → TUI imports are banned
(``tests/test_no_lib_to_tui_import.sh``). ``monitor_core`` re-exports every name,
so existing ``from monitor.monitor_core import SHADOW_TARGET_OPTION`` sites keep
working. Deliberately stdlib-only.
"""

from __future__ import annotations

#: The shadow's binding to the agent it follows. Set by the shadow spawn path
#: (`monitor_core.spawn_shadow`) to the followed agent's pane id.
SHADOW_TARGET_OPTION = "@aitask_shadow_target"

#: The scratchpad's binding to the agent it was opened beside. Value = that
#: agent's pane id. The helper classifier and the lifecycle binding.
SCRATCHPAD_TARGET_OPTION = "@aitask_scratchpad_target"

#: The canonical absolute store directory of a task scratchpad; empty for an
#: unsaved pad. Used ONLY by the one-per-store duplicate lookup — it is not a
#: helper marker, so it is deliberately absent from the tuple below. A bare task
#: id is not used: one tmux server hosts several projects, and task numbers are
#: repository-local.
SCRATCHPAD_STORE_OPTION = "@aitask_scratchpad_store"

#: Every pane option whose non-empty value marks a pane as a bound helper. The
#: ORDER is the field order of every format built from it; the tuple is closed —
#: add a kind here, never a parallel list elsewhere.
BOUND_HELPER_TARGET_OPTIONS = (SHADOW_TARGET_OPTION, SCRATCHPAD_TARGET_OPTION)


def is_bound_helper(*targets: str) -> bool:
    """True when any already-read helper-target value is non-empty.

    Pure: the tmux read stays at the call site, so this stays unit-testable.
    Empty or whitespace-only values are "not bound"; no arguments is False.
    Does NOT consult the frozen marker — callers apply frozen precedence first.
    """
    return any(t.strip() for t in targets)
