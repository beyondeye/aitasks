"""Canonical code-agent identity for pane-based consumers (t1467).

THE one place a tmux pane is mapped to a code-agent key. Two consumers depend on
it and must not fork it: `lib/workflow_phase.py` (which re-exports
`agent_key_from_command` under its own name, so its existing callers are
unchanged) and `monitor/prompt_patterns.py` (which scopes prompt matching to the
pane's own agent). A second mapper would drift the moment an agent is added to
one per-agent table and not another.

It lives in `lib/` rather than in `monitor/` because the dependency direction is
one-way: `monitor_core.py` puts `lib/` on `sys.path` and imports from it, while
`workflow_phase.py` inserts only its own directory and runs as a standalone CLI.
A mapper under `monitor/` would invert that and break `workflow_phase.py signal`.

Stdlib only, matching `gate_ledger.py`: no PyYAML, no tmux, no Textual.

**`pane_current_command` is not an authoritative agent identifier.** Measured
2026-08-13 on a real session:

    claude     → native ELF binary          → pane reports `claude`    ✓
    opencode   → native npx bin             → pane reports `opencode`  ✓
    codex      → node wrapper, real binary  → pane reports `node`      ✗
                 spawned as a direct child

So resolution is a two-rung ladder (:func:`agent_key_from_pane`), and `""` always
means "could not resolve" — never "not an agent". Callers must degrade on `""`,
never conclude from it.
"""
from __future__ import annotations

import shutil
import subprocess
import time

# The per-agent table key set. `"all"` is a pattern GROUP in
# `prompt_patterns.PROMPT_PATTERNS_BY_AGENT`, never an agent, and is not here.
AGENT_KEYS: tuple[str, ...] = ("claude", "codex", "opencode")

# Short enough that a wedged process table costs a fraction of one refresh tick
# rather than stalling it. Exceeding it is treated as "unresolved", like every
# other failure below.
_LOOKUP_TIMEOUT = 2.0

# (pane_id, pane_pid, current_command) -> resolved key.
#
# All THREE, and the pane_id is the load-bearing one. Keying on pid+command
# alone is not enough: the OS recycles pids, and the recycled process is very
# often the *same command* — `node` is the single most common thing to find at a
# reused pid on a developer box, and it is exactly the command that gets here.
# Such a pane would silently inherit the dead pane's `codex` answer and have its
# prompt matching scoped to the wrong agent, with no child check to correct it,
# until the size flush happened to evict it.
#
# tmux pane ids are monotonic within a server's lifetime, so including it means a
# stale hit now requires a pane_id AND a pid AND a command to coincide across a
# server restart. Residual, accepted: entries for dead panes are not actively
# evicted — the cache is bounded by size, not by pane liveness — because nothing
# in this module observes pane teardown. Eviction on discovery-exit belongs to
# the monitor and is the durable version of this fix.
_PANE_KEY_CACHE: dict[tuple[str, int, str], str] = {}
_CACHE_MAX = 512

# NEGATIVE results are cached separately, with a retry schedule, because
# "unresolved" is frequently a *timing* answer rather than a permanent one: the
# wrapper shape starts asynchronously, so a tick that lands between the pane's
# exec and its child's exec sees no children at all. Caching that "" like a
# positive would pin the pane to ledger-only for its entire lifetime — the exact
# outcome rung 2 exists to prevent.
#
# Shape copied deliberately from `TaskInfoCache._MISS_RETRY_SCHEDULE`: escalating
# backoff, then a sparse terminal interval repeated FOREVER. The terminal step is
# load-bearing for the same reason it is there — a budget that stops would
# permanently poison a pane whose miss outlived it, and nothing else guarantees
# recovery. Steady-state cost for a genuinely agent-less pane (a companion TUI)
# is one `pgrep` per 5 min.
_PANE_MISS_CACHE: dict[tuple[str, int, str], tuple[int, float]] = {}
_MISS_RETRY_SCHEDULE: tuple[float, ...] = (1.0, 5.0, 15.0)
_MISS_RETRY_TERMINAL: float = 300.0

# Injectable clock so tests drive the retry schedule deterministically rather
# than sleeping (aidocs/framework/testing_conventions.md).
_now = time.monotonic


def agent_key_from_command(current_command: str) -> str:
    """Map a pane's running command to an agent key, or ``""``.

    Pure — no I/O, so the CLI and the tests can use it directly. Exact match on
    the basename rather than a substring test: a pane running
    ``claude-something-else`` is not Claude Code.
    """
    cmd = (current_command or "").strip()
    if not cmd:
        return ""
    base = cmd.rsplit("/", 1)[-1].lower()
    return base if base in AGENT_KEYS else ""


def _child_commands(pane_pid: int) -> list[str]:
    """Command names of ``pane_pid``'s DIRECT children; ``[]`` when unknowable.

    ``pgrep -P`` + ``ps -o comm= -p`` is the pair that works on both Linux and
    BSD/macOS — GNU's ``ps --ppid`` does not exist on BSD. Every failure (missing
    binary, non-zero exit, timeout, unparseable output) returns ``[]``, which the
    caller renders as "unresolved", i.e. the pre-t1467 answer.

    Module-level so tests can substitute it and count invocations.
    """
    if not pane_pid or pane_pid <= 0:
        return []
    pgrep = shutil.which("pgrep")
    ps = shutil.which("ps")
    if not pgrep or not ps:
        return []
    try:
        found = subprocess.run([pgrep, "-P", str(pane_pid)],
                               capture_output=True, text=True,
                               timeout=_LOOKUP_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return []
    # pgrep exits 1 when there are simply no children — not an error, just no
    # second rung to climb.
    if found.returncode != 0:
        return []
    kids = [tok for tok in found.stdout.split() if tok.isdigit()]
    if not kids:
        return []
    try:
        named = subprocess.run([ps, "-o", "comm=", "-p", ",".join(kids)],
                               capture_output=True, text=True,
                               timeout=_LOOKUP_TIMEOUT)
    except (OSError, subprocess.SubprocessError):
        return []
    if named.returncode != 0:
        return []
    return [line.strip() for line in named.stdout.splitlines() if line.strip()]


def agent_key_from_pane(current_command: str,
                        pane_pid: int | None = None,
                        pane_id: str = "") -> str:
    """Two-rung resolution: the pane's own command, then ONE level of children.

    Rung 2 exists because a wrapper-style install hides the agent exactly one
    level down (measured: ``node`` → ``codex``). It is bounded at one level on
    purpose — at depth 2 a real Codex is already running
    ``codex-code-mode-host``, so a deeper walk would resolve a pane to whatever
    it happened to spawn rather than to what it *is*.

    Ambiguity suppresses: if the children resolve to more than one DISTINCT
    agent, the answer is ``""``. (Several children resolving to the *same* agent
    is not ambiguous and resolves normally.)

    **Caching is asymmetric, and that asymmetry is load-bearing.** A *positive*
    answer is cached for the pane's life: a process does not become a different
    agent. A *negative* one is only ever provisional — the wrapper spawns its
    child asynchronously, so a tick landing between the pane's exec and the
    child's sees no children at all — and is therefore retried on a backoff
    (:data:`_MISS_RETRY_SCHEDULE`, then :data:`_MISS_RETRY_TERMINAL` forever).
    Caching a miss like a hit would pin such a pane to ledger-only for its whole
    lifetime, which is precisely the outcome rung 2 exists to prevent.
    """
    key = agent_key_from_command(current_command)
    if key:
        return key
    if not pane_pid:
        return ""
    cache_key = ((pane_id or "").strip(), int(pane_pid),
                 (current_command or "").strip())
    cached = _PANE_KEY_CACHE.get(cache_key)
    if cached:
        return cached

    now = _now()
    miss = _PANE_MISS_CACHE.get(cache_key)
    if miss is not None:
        miss_count, last_attempt = miss
        idx = min(miss_count - 1, len(_MISS_RETRY_SCHEDULE) - 1)
        due_after = (_MISS_RETRY_SCHEDULE[idx] if miss_count <= len(_MISS_RETRY_SCHEDULE)
                     else _MISS_RETRY_TERMINAL)
        if now - last_attempt < due_after:
            return ""

    resolved_set = {k for k in (agent_key_from_command(c)
                                for c in _child_commands(int(pane_pid))) if k}
    resolved = resolved_set.pop() if len(resolved_set) == 1 else ""

    if len(_PANE_KEY_CACHE) >= _CACHE_MAX or len(_PANE_MISS_CACHE) >= _CACHE_MAX:
        # Unbounded growth over a long-lived monitor's lifetime is the only
        # failure mode here; dropping the maps just re-runs the lookups.
        _PANE_KEY_CACHE.clear()
        _PANE_MISS_CACHE.clear()
    if resolved:
        _PANE_KEY_CACHE[cache_key] = resolved
        _PANE_MISS_CACHE.pop(cache_key, None)
    else:
        prev_count = miss[0] if miss is not None else 0
        _PANE_MISS_CACHE[cache_key] = (prev_count + 1, now)
    return resolved
