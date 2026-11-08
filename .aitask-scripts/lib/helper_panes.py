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
* it is killed when its target pane dies (cleanup job 1) **or is killed
  directly** (:func:`kill_bound_helpers`, t2088) — a plain `kill-pane` /
  `kill-window` fires no `pane-died`, so job 1 never runs on the two framework
  paths that kill an agent that way: `monitor_core.TmuxMonitor.
  kill_agent_pane_smart` and `lib/agent_freeze.drop_record`;
* it is never killed when a *sibling* dies while its target lives.

**Frozen precedence is the caller's job and is never optional.** A pane stamped
``@aitask_frozen`` is a frozen stand-in, never a helper — even when a helper
target retained from whatever ran in the pane before the respawn says otherwise.
Every consumer checks the frozen marker FIRST, exactly as
``monitor_core.classify_window_panes`` does — and so does the direct-kill
sweep below, both when it lists candidates and again in the server at dispatch
time.

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

import re
from collections.abc import Callable
from typing import NamedTuple

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

#: The canonical absolute project root a sitrep agent pane serves (t2175_4).
#: Set by `monitor_core.spawn_sitrep` on the agent pane of the repository's one
#: `agent-sitrep` window; read ONLY by its one-per-root duplicate lookup. It is
#: NOT a helper marker: the sitrep pane is a code agent and must stay in agent
#: lists, so it is deliberately absent from the tuple below.
SITREP_ROOT_OPTION = "@aitask_sitrep_root"

#: The canonical absolute project root the sitrep TUI pane serves (t2211_2).
#: Set by `monitor_core.spawn_sitrep` on the `ait sitrep tui` pane beside the
#: sitrep agent; the one-TUI-per-root lookup reads it. The pane sits between the
#: two classes above, so it has its own predicate (:func:`is_sitrep_tui_pane`):
#:
#: * it is NOT an agent for anything that LISTS agents — discovery, the sitrep
#:   agent matcher's name+cwd fallback, the minimonitor's sibling to follow, the
#:   `h` harvest target — although its window is `agent-sitrep` and its cwd is
#:   the root;
#: * it IS a real occupant for anything that decides whether a window still
#:   holds one — the companion cleanup hook, smart kill / collapse, the freeze
#:   coordinator, the companion occupancy scan, the minimonitor's auto-close.
#:
#: So it is deliberately NOT in `BOUND_HELPER_TARGET_OPTIONS`: joining it would
#: make the retention rule collapse the window under a live TUI.
SITREP_TUI_ROOT_OPTION = "@aitask_sitrep_tui_root"

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


def is_sitrep_tui_pane(frozen: str, tui_root: str) -> bool:
    """True when already-read values mark a pane as the sitrep TUI (t2211_2).

    Frozen FIRST, like every helper rule: a `@aitask_frozen` stand-in is a
    frozen agent, whatever `@aitask_sitrep_tui_root` its pane retained. The
    listing consumers skip such a pane; the retention rule never consults this
    (see :data:`SITREP_TUI_ROOT_OPTION`).
    """
    return not frozen.strip() and bool(tui_root.strip())


# --- the direct-kill sweep (t2088) -------------------------------------------
#
# `kill-pane` / `kill-window` fire no `pane-died`, so a caller that kills an
# agent directly must retire that agent's helpers itself. The sweep LISTS
# candidates and then kills each one in a SEPARATE dispatch, and anything can
# happen in between: a tmux restart recycles a candidate's `%N` into an
# unrelated pane, a freeze stamps it, it is rebound. So no kill is ever a bare
# `kill-pane` of a listed id — each is one `if-shell -F` whose condition the
# server evaluates at dispatch time (the `agent_frozen_ops.kill_if_stamped`
# shape, t1773/t1783), followed by a read-back.

#: A tmux pane id, and a pid. Every value spliced into a guard condition must
#: match one of these first: they contain none of `#{},` and so cannot change
#: the condition's structure.
_PANE_ID_RE = re.compile(r"%[0-9]+")
_PID_RE = re.compile(r"[0-9]+")

#: Positional fields of :func:`bound_helper_sweep_format` before the targets.
_SWEEP_FIXED_FIELDS = 4

#: `display-message` on a helper after its dispatch. A gone pane answers rc 0
#: with an EMPTY `#{pane_id}` while the server-scoped `#{pid}` still expands
#: (measured on tmux 3.8, and 3.6a in `agent_frozen_ops._pre_read`).
_READBACK_FORMAT = "#{pane_id}\t#{pid}"


class HelperCandidate(NamedTuple):
    """One listed pane that, at listing time, was a helper bound to the target."""

    pane_id: str
    pane_pid: str
    #: The tmux SERVER pid (`#{pid}`) the listing came from.
    server_pid: str
    #: The binding option whose value named the target (the first, if several).
    option: str


def bound_helper_sweep_format(frozen_option: str) -> str:
    """The `list-panes -a -F` format :func:`helpers_bound_to` parses.

    `pane_id, pane_pid, pid, <frozen>, <each BOUND_HELPER_TARGET_OPTIONS>`,
    tab-joined. The frozen option is a parameter (`monitor_core.FROZEN_OPTION`)
    so this module holds no copy of it.
    """
    return "\t".join(
        ["#{pane_id}", "#{pane_pid}", "#{pid}", f"#{{{frozen_option}}}"]
        + [f"#{{{opt}}}" for opt in BOUND_HELPER_TARGET_OPTIONS]
    )


def helpers_bound_to(stdout: str, target_pane_id: str) -> list[HelperCandidate]:
    """Candidates for the sweep: panes bound to ``target_pane_id``.

    Pure. Parses a :func:`bound_helper_sweep_format` listing:

    * per line, never a whole-buffer ``strip()`` — the trailing target fields
      are empty on most panes, and a strip would drop the last record (t1686);
      a row of the wrong arity, or whose ids / pids are not well-formed, is
      skipped, so nothing malformed reaches a guard condition;
    * **frozen first** — a `@aitask_frozen` stand-in is never a helper, whatever
      target it retained from before its respawn;
    * **target alive => nothing.** If the target itself is in the listing, the
      kill did not take (or a restart recycled its `%N`), and the helpers serve
      a live pane.

    These are candidates only. :func:`kill_bound_helpers` re-checks each one in
    the server at dispatch time.
    """
    if not _PANE_ID_RE.fullmatch(target_pane_id or ""):
        return []
    arity = _SWEEP_FIXED_FIELDS + len(BOUND_HELPER_TARGET_OPTIONS)
    found: list[HelperCandidate] = []
    for line in stdout.splitlines():
        parts = line.split("\t")
        if len(parts) != arity:
            continue
        pane_id, pane_pid, server_pid, frozen = (
            p.strip() for p in parts[:_SWEEP_FIXED_FIELDS])
        if pane_id == target_pane_id:
            return []
        if frozen:
            continue
        if not (_PANE_ID_RE.fullmatch(pane_id) and _PID_RE.fullmatch(pane_pid)
                and _PID_RE.fullmatch(server_pid)):
            continue
        targets = parts[_SWEEP_FIXED_FIELDS:]
        option = next((opt for opt, value
                       in zip(BOUND_HELPER_TARGET_OPTIONS, targets)
                       if value.strip() == target_pane_id), "")
        if option:
            found.append(HelperCandidate(pane_id, pane_pid, server_pid, option))
    return found


def all_of(halves: "list[str]") -> str:
    """Join ``if-shell -F`` conditions with nested binary ``&&``.

    tmux's ``#{&&:a,b}`` takes exactly two operands (measured on tmux 3.8), so
    N conditions nest right: ``#{&&:a,#{&&:b,c}}``. The one grammar every
    guarded dispatch here shares — the helper sweep and the harvest-and-close
    run kill (t2175_5).
    """
    if not halves:
        raise ValueError("all_of needs at least one condition")
    cond = halves[-1]
    for half in reversed(halves[:-1]):
        cond = f"#{{&&:{half},{cond}}}"
    return cond


def _guard_condition(cand: HelperCandidate, target_pane_id: str,
                     frozen_option: str) -> str:
    """The `if-shell -F` condition that must hold, AT DISPATCH TIME, to kill.

    Still unfrozen, still bound to the target by the same option, still running
    the listed process, and still on the same server generation. A restart that
    recycles the `%N` fails the server-pid half even when the new pane happens
    to carry the same binding; the server-pid half is also what makes the
    "target is gone" reading the listing gave apply to the server the kill runs
    in, since pane ids are never reused within one generation.
    """
    return all_of([
        f"#{{==:#{{{frozen_option}}},}}",
        f"#{{==:#{{{cand.option}}},{target_pane_id}}}",
        f"#{{==:#{{pane_pid}},{cand.pane_pid}}}",
        f"#{{==:#{{pid}},{cand.server_pid}}}",
    ])


def run_identity_condition(pane_pid: str, server_pid: str,
                           frozen_option: str) -> str:
    """The condition that must hold to kill ONE agent run (t2175_5).

    Unfrozen, still running process ``pane_pid``, on server generation
    ``server_pid``. A freeze or restore respawns a different process into the
    same pane id, which fails the ``pane_pid`` half; a server restart that
    recycles the ``%N`` fails the server half. Both values must be bare pids —
    they are spliced into the condition, so anything else is refused here.
    It guards the target pane only: tmux evaluates it in that pane's context,
    which is why the run kill never extends to the pane's window.
    """
    if not (_PID_RE.fullmatch(pane_pid or "")
            and _PID_RE.fullmatch(server_pid or "")):
        raise ValueError("pane_pid and server_pid must be bare pids")
    return all_of([
        f"#{{==:#{{{frozen_option}}},}}",
        f"#{{==:#{{pane_pid}},{pane_pid}}}",
        f"#{{==:#{{pid}},{server_pid}}}",
    ])


#: Public name of the post-dispatch read-back format (see `_READBACK_FORMAT`).
READBACK_FORMAT = _READBACK_FORMAT


def readback_state(rc: int, out: str, pane_id: str, server_pid: str) -> str:
    """Classify a :data:`READBACK_FORMAT` read of ``pane_id`` after a kill.

    ``"gone"`` only from a successful read on the SAME server generation that
    shows an empty ``#{pane_id}``; ``"present"`` when the pane answers with its
    own id on that server; anything else — a failed read, a short read, a
    different server, a different pane — is ``"unknown"``, never "gone".
    """
    if rc != 0:
        return "unknown"
    fields = (out.splitlines() or [""])[0].split("\t")
    if len(fields) != 2 or fields[1].strip() != server_pid:
        return "unknown"
    found = fields[0].strip()
    if not found:
        return "gone"
    return "present" if found == pane_id else "unknown"


def kill_bound_helpers(
    run: Callable[[list[str]], tuple[int, str]],
    target_pane_id: str,
    *,
    frozen_option: str,
) -> list[str]:
    """Kill every helper bound to ``target_pane_id``, which was just killed.

    ``run`` is the caller's gateway (`TmuxMonitor.tmux_run`,
    `agent_frozen_ops.run`), so this module issues no tmux of its own.

    Whole-server (`list-panes -a`), where cleanup job 1 is session-scoped: pane
    ids are server-unique, so the same helpers match, plus any in another
    session, and no session has to be resolved before the kill.

    Each kill is ONE guarded dispatch (:func:`_guard_condition`), never a bare
    `kill-pane`, and is then read back, because `if-shell` answers 0 whether or
    not its branch fired. Returns only the ids read back as gone on the same
    server. Best-effort, like job 1's `|| true`: a failure leaves a helper
    behind and never changes the caller's verdict.
    """
    rc, out = run(["list-panes", "-a", "-F",
                   bound_helper_sweep_format(frozen_option)])
    if rc != 0:
        return []
    killed: list[str] = []
    for cand in helpers_bound_to(out, target_pane_id):
        run(["if-shell", "-F", "-t", cand.pane_id,
             _guard_condition(cand, target_pane_id, frozen_option),
             f"kill-pane -t {cand.pane_id}"])
        rc, back = run(["display-message", "-p", "-t", cand.pane_id,
                        _READBACK_FORMAT])
        if readback_state(rc, back, cand.pane_id, cand.server_pid) == "gone":
            killed.append(cand.pane_id)
    return killed
