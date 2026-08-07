---
Task: t1451_shadow_staleness_reads_tmux_failure_as_no_warning.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1451 — Shadow staleness reads a tmux failure as "no warning"

## Context

t1446 fixed one instance of a class of bug: *an unverifiable tmux observation
read as a negative verdict*. `discover_window_panes` collapsed any `rc != 0`
into `[]`, and the minimonitor read `[]` as "no other panes remain" and quit —
so a machine-wide stall on 2026-08-06 made every companion pane abandon the
agent it was watching. The fix made the observation explicit:
`(observed, panes)`, where `observed` is `True` only when tmux answered *and*
every record parsed.

Auditing the neighbours turned up three defects that t1446 deliberately left
out of scope. This task fixes all three.

1. **Same class, different function.** `TmuxMonitor.get_pane_option`
   (`monitor_core.py:1410-1425`) returns `""` on `rc != 0`, and
   `compute_shadow_staleness` (`:538-540`) reads that empty string as "the
   shadow has not analyzed anything yet: nothing to warn about". A tmux failure
   therefore *clears* a standing staleness banner in the minimonitor. The
   function is already carefully tri-state for the exception path — only the
   failed-read-as-empty-string path falls through to a positive verdict.
2. **Two dead single-instance guards.** `aitask_minimonitor.sh:37` and
   `agent_launch_utils.py:1569` test `pane_current_command` for
   `minimonitor` / `monitor_app`, but a live minimonitor pane reports `python`
   (confirmed live during t1446: `%423 4041322 python`). Neither guard can ever
   fire — dead code pretending to be a guard.
3. **A companion with no cleanup hook, and an overwrite hazard.**
   `maybe_spawn_minimonitor` computes exactly the `(agent_pane,
   companion_pane)` pair the cleanup hook needs and never arms it, so every
   board- / codebrowser- / crew-launched window carries a companion with no
   `pane-died` hook. `tui_switcher.py:1386` arms it by hand with a **bare**
   `set-hook -p … pane-died` — index `[0]`, the exact overwrite hazard
   `attach_shadow_cleanup_hook` was written to avoid.

Intended outcome: an unverifiable tmux read never produces a positive verdict
in this area; the guards actually guard; and every companion pane is cleaned up
from one code path, independently of which companion armed the hook first.

## Decisions taken

Confirmed with the user up front:

- **Guards match a pane user-option marker**, not a command line. tmux's only
  command-line format is `#{pane_start_command}`, which is set only for panes
  launched *with* a command — a minimonitor typed into an existing shell pane
  would stay invisible. The repo's established idiom for identifying helper
  panes is a marker (`@aitask_shadow_target`, read by
  `aitask_companion_cleanup.sh` and `agent_launch_utils`), so this follows it.
- **Both halves of the hook fix**, including arming inside
  `maybe_spawn_minimonitor`.
- **`attach_shadow_cleanup_hook` → `attach_companion_cleanup_hook`.**

Revised after the user's plan review (each replaces an earlier design; the
reasoning is recorded because the discarded versions look reasonable):

- **Cleanup discovers companions by marker; the hook payload is no longer
  treated as universal.** One `pane-died` hook carries exactly one
  `companion_pane`, and `attach_companion_cleanup_hook` deliberately never
  overwrites — so whichever companion armed the hook *first* is the only one the
  payload names. `spawn_shadow` passes `companion_pane or shadow_pane`, and from
  the full monitor `companion_pane` is `None`, so a shadow-first ordering leaves
  the hook naming the *shadow* pane. Job 2 of `aitask_companion_cleanup.sh` then
  counts the minimonitor as a **real agent sibling** (it has no
  `@aitask_shadow_target`), which both spares the companion and, worse, keeps
  *any* other companion alive on a bogus sibling count. That miscount is a
  pre-existing bug; the new marker is exactly what is needed to fix it. See
  Step 3.
- **The spawner does NOT stamp the marker; only the app stamps its own pane.**
  An earlier draft had `maybe_spawn_minimonitor` stamp the companion pane right
  after `split-window` to close a boot-time race. That stamp is what created the
  need for a self-skip in the child's guard — and therefore a self-deadlock
  whenever the child could not identify its own pane, plus a fail-open branch
  that would silently permit duplicate monitors. Dropping the stamp removes both
  by construction: our own pane can never carry a marker before our app starts,
  so there is nothing to skip and no ambient `$TMUX_PANE` dependency. The
  residual boot-window race is documented in `## Risk` and is strictly smaller
  than today's, where the guard never fires at all.
- **Marker liveness is validated by the guards now, not deferred.** The marker
  carries the marking process's pid; a marker whose pid is provably dead is
  ignored and cleared. This was originally proposed as a spawned follow-up task;
  it is protection this change needs immediately, so it is inline.
- **One liveness implementation, called from both languages — not two that
  agree by inspection.** An earlier draft specified the rule prosaically and let
  the shell guard reimplement it with `${marker##*:}` + `kill -0`. That diverges
  in at least two ways: `garbage:123` parses as a dead numeric pid in shell (so
  the shell clears a marker Python calls unverifiable and blocks on), and
  `kill -0` reports **failure** for a live process owned by another user where
  `os.kill(pid, 0)` raises `PermissionError`, which the contract counts as
  alive. Both are silent, and neither is the kind of thing a reader catches. So
  the predicate lives in one small module with a CLI entry point and the shell
  guard *calls* it (Step 2a). Parity then holds by construction and is pinned by
  a table-driven test that drives both entry points over the same inputs.

---

### Pre-phase (risk mitigations)

Runs before the Step 1–5 body; its substance is designed into Step 2 rather
than bolted on, and these are the checkable obligations that phase carries.

1. `[monitor_marker_liveness]` The marker value MUST be `<kind>:<pid>` with
   `kind` drawn from `MONITOR_KINDS` (Step 2a) — a bare `<kind>` is not
   acceptable, because a guard cannot then tell a live monitor from a marker
   left by a hard-killed one.
2. `[monitor_marker_liveness]` There MUST be exactly **one** implementation of
   the liveness rule: `monitor_marker_state` in `lib/monitor_marker.py`. The
   shell guard MUST invoke it (Step 2c) rather than re-derive it; the Python
   guard MUST import it (Step 2d). Verified by grepping the tree for a second
   `kill -0` / `##*:` on a marker value, and pinned by the parity test in
   Step 4.
3. `[monitor_marker_liveness]` A non-empty value that does not parse — unknown
   kind, missing pid, non-numeric pid, extra fields — MUST classify as
   **present** and MUST NOT be cleared. This is the same "unverifiable is not a
   negative verdict" rule this whole task is about, and it is where a
   hand-rolled shell parse diverges first (`garbage:123`).
4. `[monitor_marker_liveness]` The CLI's verdict codes MUST sit outside the
   range a failing interpreter can produce (Step 2a: `0 / 10 / 11`), the CLI
   MUST return `EXIT_PRESENT` on any internal or usage error, and the shell
   guard MUST treat **only** the two verified codes as non-blocking — every
   other status blocks, with a distinct message naming the exit code. A verdict
   sharing an error code is the worst case in the whole design: exit 1 (uncaught
   exception) mapped to "stale" would make the guard clear a *live* marker.
5. `[monitor_marker_liveness]` A stale-marked pane MUST NOT count toward
   `maybe_spawn_minimonitor`'s `real_panes >= 3` overcrowding limit (Step 2d,
   case (c) of `test_minimonitor_instance_guard.py`) — it is a helper pane
   either way.
6. `[verify_marker_wiring]` `mark_monitor_pane` MUST emit only values its own
   readers classify as parseable (Step 2a's `kind in MONITOR_KINDS` assertion),
   asserted by feeding the captured argv value back through
   `monitor_marker_state`.
7. `[verify_marker_wiring]` The production path MUST be proven, not assumed:
   both `main()`s pass `mark_pane=True`, both `on_mount`s stamp, both
   `on_unmount`s clear, and a default (test-style) construction does neither.
   Every other guard test in Step 4 starts from an already-marked pane, so
   without this the whole feature could be inert in production with a green
   suite. See `tests/test_monitor_pane_marker_wiring.py` (Step 4).

---

## Step 1 — `get_pane_option` returns `(ok, value)`

**`.aitask-scripts/monitor/monitor_core.py:1410-1425`**

Change the signature to `-> tuple[bool, str]` and return `(False, "")` on
`rc != 0`, `(True, out.strip())` otherwise. This is the shape
`find_shadow_pane_status` (`:376-403`) already uses in this module, and the
2-tuple is deliberate for the same reason t1446 chose one: a caller cannot
consume it without binding the flag, whereas `""` is silently falsy.

Update the docstring: `-q` still makes an *unset* option yield `(True, "")` —
a verified absence, distinct from `(False, "")` = tmux could not answer.

**`compute_shadow_staleness` (`:498-550`)**

```python
    try:
        ok, stamp = await monitor.get_pane_option(
            shadow_pane, SHADOW_ANALYZED_AT_OPTION
        )
    except Exception:
        return None, None  # option read failed — preserve prior state
    if not ok:
        return None, None  # tmux could not answer — preserve prior state
```

Keep the unpack **inside** the `try`. A stub still returning a bare string
raises (`ValueError`/`TypeError`) and lands on the existing preserve branch —
fail-safe in the only direction that matters here, since `None` never clears a
standing warning. Add the new row to the contract table at `:511-521`:

| Condition | Result |
|---|---|
| ``get_pane_option`` reports failure (`ok is False`) | ``(None, None)`` |

placed directly under the "raised" row, and extend the closing paragraph to say
that a *failed* read is unverifiable, never "never analyzed".

**No consumer changes needed.** `minimonitor_app._update_shadow_freshness`
(`:1941-1955`) already returns early on `stale is None` — that early return is
the fix taking effect. Both `monitor_app.py` consumers (`:1118`, `:2926`)
discard `analyzed_at` and coerce with `bool(stale)`, so `False → None` is a
no-op there (`bool(None) == bool(False)`); the one-shot toast has no prior
state to preserve.

## Step 2 — a real single-instance marker

### 2a. The marker, and ONE liveness implementation

**New `.aitask-scripts/lib/monitor_marker.py`** — deliberately tiny and
**stdlib-only** (no `tmux_exec`, no yaml), so the shell guard can exec it as a
script without paying for `agent_launch_utils`' import graph.

```python
MONITOR_KIND_OPTION = "@aitask_monitor_kind"
MONITOR_KINDS = ("minimonitor", "monitor")
_MARKER_RE = re.compile(r"^(minimonitor|monitor):([0-9]+)$")


def parse_monitor_marker(value: str) -> tuple[str, int] | None:
    """`<kind>:<pid>` with a KNOWN kind -> (kind, pid); anything else -> None."""


def monitor_marker_state(value: str) -> str:
    """Classify a @aitask_monitor_kind value: "absent" | "present" | "stale".

    Unverifiable is NOT absent (t1451 — the same principle as the staleness fix
    this task is built around):
      * ``""``                                   -> "absent"
      * parseable, process exists                -> "present"
      * parseable, process gone                  -> "stale"  (caller clears it)
      * non-empty but NOT parseable              -> "present" (cannot verify)

    "Not parseable" covers an unknown kind (`garbage:123`), a missing pid
    (`minimonitor`), a non-numeric pid, and extra fields (`minimonitor:1:2`).
    Every one of those blocks and is never cleared — clearing a marker we do not
    understand would silently delete another tool's state.
    """


def monitor_marker_alive(value: str) -> bool:
    """`monitor_marker_state(value) == "present"` — the guards' predicate."""
```

Process existence is `os.kill(pid, 0)`: `ProcessLookupError` → gone;
**`PermissionError` → exists** (a live process owned by another user). Pid reuse
is possible in principle; its consequence is a guard that declines to launch a
second monitor, which is the safe direction.

**CLI entry point** in the same file, so there is exactly one implementation of
the rule in the repo:

```python
# Verdict codes. Chosen ABOVE the range a failing interpreter can produce:
# an uncaught exception exits 1, a missing file or usage error exits 2, a
# non-executable/not-found exec exits 126/127, a signal exits 128+n. If a
# verdict shared any of those, an interpreter failure would be indistinguishable
# from a decision — and mapping it to "stale" would make the guard CLEAR A LIVE
# MARKER on a crash (t1451).
EXIT_PRESENT, EXIT_STALE, EXIT_ABSENT = 0, 10, 11


def main(argv: list[str]) -> int:      # usage: monitor_marker.py state <value>
    try:
        if len(argv) != 3 or argv[1] != "state":
            return EXIT_PRESENT        # usage error -> unverifiable -> block
        return {"present": EXIT_PRESENT, "stale": EXIT_STALE,
                "absent": EXIT_ABSENT}[monitor_marker_state(argv[2])]
    except Exception:
        return EXIT_PRESENT            # internal failure -> unverifiable -> block


if __name__ == "__main__":
    sys.exit(main(sys.argv))
```

Three properties are load-bearing:

- **Only `EXIT_ABSENT` and `EXIT_STALE` are verified verdicts.** Every other
  status — including ones this program never returns — means the classification
  did not happen, and the caller must treat it as *present*. That is the same
  "unverifiable is not a negative verdict" rule the whole task is about, applied
  to the transport rather than to tmux.
- **The CLI itself fails safe**, so the contract does not rest on the caller's
  mapping alone: any internal exception or usage error returns `EXIT_PRESENT`.
- **No `argparse`.** The value is read as a bare positional, so a marker
  beginning with `-` can never be interpreted as an option — an argparse usage
  error would exit 2 and, worse, is a parse of untrusted pane state.

Nothing is printed, so no caller can mistake detection output for a decision.

**`.aitask-scripts/lib/agent_launch_utils.py`** re-exports
`MONITOR_KIND_OPTION`, `monitor_marker_alive` and `monitor_marker_state` from
`monitor_marker` (both live under `lib/`, already on `sys.path` for every
consumer) and adds the two writers, placed next to `CLEANUP_SCRIPT_NAME`
(`:1368`) — here rather than in `monitor_core`, because `monitor_core` already
imports from this module (`:42-45`) and the reverse edge would be circular:

```python
def mark_monitor_pane(kind: str) -> bool:
    """Stamp this process's own pane: `<kind>:<os.getpid()>`."""


def unmark_monitor_pane() -> bool:
    """Clear the marker (`set-option -pu`) on this process's own pane."""
```

Both read `os.environ.get("TMUX_PANE")` themselves and no-op (returning `False`)
when it is unset; both route through the module's `_TMUX` gateway.
`mark_monitor_pane` MUST build its value with `f"{kind}:{os.getpid()}"` and
assert `kind in MONITOR_KINDS`, so a writer can never emit a value its own
readers classify as unparseable.

`unmark_monitor_pane` is the normal-exit path; the `stale` classification is
what covers an abnormal one (a hard-killed minimonitor in a pane that survives
it — the user's own shell pane, since nothing in the tree sets a global
`remain-on-exit`, so a *spawned* companion pane always dies with its process and
takes its pane options with it).

### 2b. The app stamps its own pane — and nothing else does

**Only the app writes the marker.** The spawner deliberately does not (see
"Decisions taken"): if `maybe_spawn_minimonitor` stamped the pane it just
created, the minimonitor booting *inside* that pane would find its own marker
and refuse to start unless it could identify its own pane from ambient state.
Not stamping removes that failure mode entirely — no self-skip, no fail-open,
no `$TMUX_PANE` dependency in either guard.

Each app stamps at mount and clears at unmount, gated on a new constructor flag
so a test mount never writes to a live pane — the same precaution
`monitor_app`'s `rename_window` flag exists for (t1240):

- `.aitask-scripts/monitor/minimonitor_app.py` — add `mark_pane: bool = False`
  to `__init__` (`:227-238`); in `on_mount` (`:326`), after the `not
  os.environ.get("TMUX")` early return, call `mark_monitor_pane("minimonitor")`
  when the flag is set; call `unmark_monitor_pane()` in `on_unmount` (`:378`)
  under the same flag. Pass `mark_pane=True` from `main()` (`:2354`).
  `mark_monitor_pane` is imported from `agent_launch_utils`, which this module
  already imports (`:64`).
- `.aitask-scripts/monitor/monitor_app.py` — identical, next to the existing
  `if self._rename_window:` block (`:688`), with kind `"monitor"`; `main()` at
  `:3378` already passes `rename_window=True`, add `mark_pane=True` there.

### 2c. Guard A — `.aitask-scripts/aitask_minimonitor.sh:33-42`

```bash
# Single-instance guard: skip if another minimonitor/monitor runs in the same
# window. Matches the @aitask_monitor_kind pane marker each app stamps on
# itself at mount — `pane_current_command` reports `python` for a live monitor
# and so could never fire (t1451). Only a booted app ever writes the marker, so
# this pane cannot be carrying one yet and needs no self-exclusion.
#
# Liveness is decided by lib/monitor_marker.py, NOT reimplemented here: a shell
# rewrite of the rule diverges silently (`${marker##*:}` reads `garbage:123` as
# a dead pid; `kill -0` reports failure for another user's live process where
# os.kill counts it alive).
#
# BLOCKING IS THE DEFAULT ARM. Only the two verified verdicts — 11 absent, 10
# stale — let the loop continue. Every other status (a crashed interpreter =>
# 1, a missing file/usage error => 2, 126/127, a signal) means the marker was
# never classified, and an unclassified marker is "present" (t1451).
MARKER_TOOL="$SCRIPT_DIR/lib/monitor_marker.py"
if [[ -n "${TMUX:-}" ]]; then
    while IFS='|' read -r pane_id marker; do
        [[ -z "$marker" ]] && continue
        marker_rc=0
        "$PYTHON" "$MARKER_TOOL" state "$marker" || marker_rc=$?
        case "$marker_rc" in
            11) continue ;;                       # verified absent
            10) # verified stale — the marking process is gone; self-heal
                ait_tmux set-option -pu -t "$pane_id" \
                    @aitask_monitor_kind 2>/dev/null || true
                continue ;;
            0)  echo "A monitor is already running in this window. Exiting." ;;
            *)  # NOT a verdict: the check itself failed. Say so distinctly —
                # a silent block here is indistinguishable from a real monitor.
                echo "Could not classify the monitor marker on $pane_id" \
                     "(check exited $marker_rc) — assuming a monitor is" \
                     "running. Exiting." >&2 ;;
        esac
        exit 0
    done < <(ait_tmux list-panes \
        -F "#{pane_id}|#{@aitask_monitor_kind}" 2>/dev/null || true)
fi
```

The `exit 0` sits **after** the `case`, not inside its arms, so adding a future
status cannot accidentally create a new non-blocking path: a new arm has to
`continue` explicitly to avoid exiting.

`MARKER_TOOL` is assigned unconditionally — deliberately **not**
`${MARKER_TOOL:-…}`. A production override would be a test-only backdoor that
also lets any caller point the guard at an arbitrary script it then executes.
Fault injection goes through `$AIT_PYTHON` instead, which `python_resolve.sh`
already documents as the explicit interpreter override and places first in its
resolution order — see Step 4.

`$PYTHON` is already resolved at `:14` (`require_ait_python`) and the script
already pays two interpreter startups at `:18-19` for the dependency check, so
this adds cost only on the rare pane that actually carries a marker.

`|` (not `:` and not a space) is the field separator throughout: the marker
value itself contains `:`, and `IFS=' '` collapses runs, which silently shifts
fields when a middle column is empty. With `IFS='|'` empty fields are preserved.

### 2d. Guard B — `agent_launch_utils.py:1561-1575`

```python
    rc, out = _TMUX.run(
        ["list-panes", "-t", tmux_window_target(session, win_index),
         "-F", f"#{{pane_id}}|#{{{MONITOR_KIND_OPTION}}}|#{{@aitask_shadow_target}}"]
    )
    if rc == 0:
        real_panes = 0
        for line in out.strip().splitlines():
            pane_id, _, rest = line.partition("|")
            marker, _, shadow_target = rest.partition("|")
            if marker:
                if monitor_marker_alive(marker):
                    return None
                _TMUX.spawn(["set-option", "-pu", "-t", pane_id,
                             MONITOR_KIND_OPTION], ...)   # stale — self-heal
                continue          # a helper pane either way: never counted
            if not shadow_target.strip():
                real_panes += 1
        if real_panes >= 3:
            return None
```

Rename the misleading local `cmd_line` to `marker`. Note the `continue`: a
monitor pane is a *helper*, so even a stale-marked one must not inflate the
overcrowding count.

## Step 3 — one slot-safe hook path, and marker-driven cleanup

### 3a. Rename

`attach_shadow_cleanup_hook` → `attach_companion_cleanup_hook`
(`agent_launch_utils.py:1390`), updating every reference:

- `.aitask-scripts/monitor/monitor_core.py:45` (import), `:2789` (call in
  `spawn_shadow`)
- `aidocs/framework/shadow_agent.md:246`
- tests: `test_monitor_shadow_pick.py` (`:186`, `:587-636`),
  `test_minimonitor_shadow_pick.py` (`:193`, `:235`),
  `test_monitor_shadow_spawn_live.sh` (`:7`, `:37`, `:282`, `:468`, `:566`),
  `tests/lib/tmux_socket_containment.py:4`, `tests/lib/tmux_isolation.sh:92`

Update the docstring's "Mirrors the git-TUI companion wiring in `tui_switcher`"
line — after this change `tui_switcher` *calls* it instead. Add a note that the
`companion_pane` argument is a **legacy/best-effort hint**, not the authority on
what gets cleaned up (see 3b).

### 3b. Make `aitask_companion_cleanup.sh` discover companions by marker

**This is the fix for the ordering defect.** One hook carries one
`companion_pane`, and `attach_companion_cleanup_hook` never overwrites — so the
payload names whichever companion armed the hook first. Today job 2
(`:45-59`) counts any pane that is neither the primary, nor `$companion`, nor a
shadow as a *real agent sibling*; a minimonitor that is not `$companion`
therefore reads as a live agent and keeps the whole window's cleanup from
firing. Job 1 already solved this shape for shadows by discovering them from a
marker rather than the argument; do the same for monitor companions.

Rewrite job 2 (`:45-59`) to read three fields and treat *any* marked pane as a
helper, killing all of them when no real agent remains:

```bash
# 2. Count real-agent siblings in the window. A pane keeps companions alive
#    only if it is neither the dying primary, nor a companion pane, nor a
#    shadow helper. Companion panes are discovered from @aitask_monitor_kind
#    (t1451) rather than trusted from "$companion": one pane-died hook carries
#    one companion id, and the hook is append-only, so whichever companion
#    armed it first is the only one the argument can name. "$companion" is
#    still honoured as a hint for a pane that predates the marker.
others=0
companions=()
while IFS='|' read -r pane target kind; do
    [ -n "$pane" ] || continue
    [ "$pane" = "$primary" ] && continue
    if [ -n "$kind" ] || [ "$pane" = "$companion" ]; then
        companions+=("$pane")
        continue
    fi
    [ -n "$target" ] && continue        # shadow helper
    others=$((others + 1))
done < <(tmux list-panes -t "$window" \
    -F '#{pane_id}|#{@aitask_shadow_target}|#{@aitask_monitor_kind}' 2>/dev/null)

if [ "$others" -eq 0 ]; then
    for pane in "${companions[@]}"; do
        tmux kill-pane -t "$pane" 2>/dev/null || true
    done
fi
tmux kill-pane -t "$primary" 2>/dev/null || true
```

Job 1 (`:33-43`) keeps its behavior but switches to the same `|` separator for
consistency and empty-field safety.

Liveness is deliberately **not** consulted here: this runs at pane death and is
killing panes, not deciding whether to launch. A stale-marked pane in a window
whose last real agent just died should be closed regardless.

Note `"${companions[@]}"` under `set -u` with an empty array — use
`${companions[@]+"${companions[@]}"}` or seed the array, and confirm with
`shellcheck`.

### 3c. Arm the hook in `maybe_spawn_minimonitor`

`agent_launch_utils.py:1596-1603`, after the companion pane id is captured and
before the refocus:

```python
    if agent_pane and companion_pane:
        attach_companion_cleanup_hook(agent_pane, companion_pane)
```

`agent_pane` is already computed at `:1580-1584` and is `""` when the
`display-message` probe failed — guard on it rather than arming a hook against
an unknown pane. The return value is deliberately ignored: unlike
`spawn_shadow`, this path has no notification surface, and the minimonitor's own
auto-close (t1446) remains the backstop when the hook is not installed.

### 3d. Replace the bare `set-hook` in `tui_switcher.py:1373-1390`

```python
        if companion_pane:
            from agent_launch_utils import attach_companion_cleanup_hook
            attach_companion_cleanup_hook(primary_pane, companion_pane)
```

This deletes the duplicated `remain-on-exit` / `script_path` / `hook_cmd`
construction. It is not redundant with 3c: that call derives its agent pane from
`display-message` on the window, whereas here `primary_pane` is the git pane id
captured directly from the spawn. When both fire with the same pair the second
returns `"existing"` and installs nothing. Update the method docstring
(`:1350-1356`) to name the helper.

## Step 4 — tests

**Contract updates (must land with the source — the stubs are the contract).**

- `tests/test_shadow_seam.py:326` — `_StaleMon.get_pane_option` returns
  `(True, self._stamp)`; add an `ok=False` constructor knob returning
  `(False, "")`.
- `tests/test_minimonitor_concern_action.py:728` —
  `_async_return((True, stamp))`.
- `tests/test_minimonitor_concern_smoke.py:106` — unchanged (it deliberately
  omits `get_pane_option` to exercise the `hasattr` branch).

**Staleness (Step 1).**

- `tests/test_shadow_seam.py` — one test per new contract row: `ok is False`
  → `(None, None)`, and it must be `is not` the `False` returned by the
  empty-stamp row (the tri-state assertion the existing
  `test_none_is_distinguishable_from_false` makes for the exception path).
- `tests/test_shadow_seam.py` — pin the real method: drive
  `TmuxMonitor.get_pane_option` with a fake `tmux_run_async` returning
  `(0, "1000.0\n")` → `(True, "1000.0")`, `(-1, "")` → `(False, "")`,
  `(1, "")` → `(False, "")`.
- `tests/test_minimonitor_concern_action.py` `ShadowFreshnessTests` —
  **behavioral**: set `app._shadow_feedback_stale = True` and a non-empty
  banner, make `get_pane_option` return `(False, "")`, run
  `_update_shadow_freshness`, assert the flag and banner text are **unchanged**.
  This is the bug on the user-visible surface; it fails against today's code.

**Marker + guards (Step 2).**

- New `tests/test_monitor_marker_liveness.py` — the **shared table** and both
  entry points, so shell/Python parity is asserted rather than reviewed.

  Define one module-level table of `(value, expected_state)` pairs covering:
  `""` → `absent`; `minimonitor:<os.getpid()>` and `monitor:<os.getpid()>` →
  `present`; `minimonitor:<reaped child pid>` → `stale`; and the
  **malformed-but-numeric** family that a hand-rolled shell parse gets wrong —
  `garbage:123`, `minimonitor:1:2`, `mini monitor:123`, `MINIMONITOR:123`,
  `:123` — plus `minimonitor` (no pid), `minimonitor:abc`, `garbage`, all →
  `present`. Obtain a reliably-dead pid by spawning and reaping a trivial child
  rather than guessing a number; obtain a live-but-not-ours pid only if one can
  be found safely, otherwise document `PermissionError → present` as covered by
  a direct `os.kill` monkeypatch instead.

  Then run the table twice:
  1. against `monitor_marker_state()` in-process;
  2. against `subprocess.run([sys.executable, "lib/monitor_marker.py", "state",
     value])`, mapping exit `0/10/11` → `present/stale/absent` and **failing on
     any other status** rather than bucketing it.

  Assert both agree with the table **and with each other**. Note the second lane
  is what the shell guard actually executes, so it is a real end-to-end pin on
  the shell path's verdict, not a replica of it.

  Then pin the *transport* contract, which is where a verdict/error collision
  hides:
  - `EXIT_PRESENT, EXIT_STALE, EXIT_ABSENT` are `0, 10, 11` — assert the two
    non-zero codes are `> 2` and `< 126`, i.e. disjoint from an uncaught
    exception (1), a usage/missing-file error (2), and exec/signal statuses.
  - Usage errors return `EXIT_PRESENT`: `["monitor_marker.py"]`,
    `[..., "state"]`, `[..., "bogus", "x"]`, `[..., "state", "a", "b"]`.
  - A marker value beginning with `-` (e.g. `--help`, `-minimonitor:1`) is
    classified, never parsed as an option — it must return `EXIT_PRESENT`, and
    the process must not print usage text.
  - An internal failure returns `EXIT_PRESENT`: call `main()` in-process with
    `monitor_marker_state` monkeypatched to raise.
- New `tests/test_minimonitor_instance_guard.py` — fake-`_TMUX`
  `maybe_spawn_minimonitor` tests: (a) a window with a **live**-marked pane
  returns `None` and issues no `split-window`; (b) a window with a
  **stale**-marked pane proceeds *and* issues the `set-option -pu` self-heal;
  (c) a stale-marked pane is not counted toward the 3-pane overcrowding limit;
  (d) `attach_companion_cleanup_hook` is called with
  `(agent_pane, companion_pane)` after a successful split; (e) when the
  `display-message` probe fails (`agent_pane == ""`) no hook is armed; (f) the
  spawner issues **no** `set-option` writing `@aitask_monitor_kind` — the
  no-self-stamp invariant that removes the self-deadlock. Follow
  `tests/test_monitor_shadow_pick.py:580-637`'s `_HookTmux` pattern.
- New `tests/test_minimonitor_single_instance_guard.sh` — live-tmux, via
  `tests/lib/tmux_isolation.sh`.

  **Harness first: one delegating interpreter shim, selected by `$AIT_PYTHON`.**
  `resolve_python` (`lib/python_resolve.sh:52-78`) tries `$AIT_PYTHON`, then
  `~/.aitask/venv/bin/python`, then `~/.aitask/bin/python3`, and only then
  `PATH` — so a `PATH` shim is unreachable, and a bare `true` would fail
  `require_ait_python`'s version probe at `aitask_minimonitor.sh:14` before the
  guard runs. The shim must therefore **delegate to the real interpreter by
  default** and misbehave only for the one call under test, driven by env vars
  the shim itself reads (nothing in production reads them):

  - unset → pure passthrough;
  - `AIT_TEST_MARKER_FAULT=exit:<n>` → exit `<n>` when the argv contains
    `monitor_marker.py`, else delegate;
  - `AIT_TEST_MARKER_FAULT=missing` → rewrite that argument to a nonexistent
    path and delegate, so the **real** "can't open file" status is observed
    rather than assumed;
  - `AIT_TEST_NO_LAUNCH=1` → exit 0 when the argv contains
    `minimonitor_app.py`, so the negative states never start a TUI.

  Then run `aitask_minimonitor.sh` against an isolated window in five states:
  (i) a sibling pane marked
  with a **live** pid → prints "A monitor is already running", rc 0;
  (ii) a sibling marked with a **dead** pid → message absent, and
  `show-options -p` on that pane confirms the marker was cleared;
  (iii) a sibling marked `garbage:123` (malformed but numeric) → message
  **present** and the marker **still set** — the shell-side parity case;
  (iv) no marked sibling → message absent;
  (v) a sibling marked with a **live** pid, with the marker check faulted three
  ways via the shim — `exit:1` (an uncaught exception), `exit:2` and `missing`
  (a real unopenable file), and `exit:127`. In every case the guard must
  **block**, emit the distinct "could not classify" message naming the exit
  code, and leave the marker **unchanged**. This is the fail-safe arm, and the
  `exit:1` variant is precisely the one that would previously have cleared a
  live marker.

  States (ii)–(iv) carry `AIT_TEST_NO_LAUNCH=1` so the script's final `exec` is
  inert while everything before it runs for real. If the shim proves unworkable,
  drive the run through `tmux send-keys` into a disposable pane and read it back
  with `capture-pane` — do not weaken the negative controls to positive-only
  assertions.

**Production wiring (Step 2b) — the concern-2 coverage.**

Every test above works on panes that are *already* marked, so a missed import,
an unset flag, or a dropped lifecycle call would leave all of them green while
production never writes a marker at all. Pin the wiring itself:

- New `tests/test_monitor_pane_marker_wiring.py` — mount-level, following
  `tests/test_monitor_rename_gate.py:45-94` exactly (fake `TMUX`/`TMUX_PANE`
  env via `mock.patch.dict(..., clear=True)`, `_start_monitoring` neutralized,
  the gateway recorded). For **both** `MiniMonitorApp` and `MonitorApp`:
  1. `mark_pane=True` + fake tmux env → mount issues
     `set-option -p -t %99 @aitask_monitor_kind <kind>:<os.getpid()>`, with the
     kind matching the app (`minimonitor` / `monitor`) and the pid being the
     **real** running pid, not a placeholder.
  2. The value written must satisfy `monitor_marker_state(...) == "present"` —
     asserted by feeding the captured argv's value straight into the predicate,
     which is what closes the writer/reader loop.
  3. Unmount issues `set-option -pu -t %99 @aitask_monitor_kind`.
  4. Default construction (no `mark_pane`) issues **neither**, even with
     `$TMUX`/`$TMUX_PANE` pointing at a live pane — the t1240 isolation
     invariant that keeps the rest of the suite from writing to the agent's own
     pane.
  5. `mark_pane=True` **without** `$TMUX_PANE` issues neither (fail-safe, same
     shape as `test_production_flag_without_pane_is_failsafe`).
- Same file — the `main()` link, which `test_monitor_rename_gate.py` notably
  does *not* cover for `rename_window` and which is exactly where the flag can
  be dropped: replace the app class in the module namespace with a recorder
  whose `run()` is a no-op, patch `sys.argv` to a minimal `--session demo` and
  patch the tmux session probe (`_detect_tmux_session`), call `main()`, and
  assert the recorded kwargs contain `mark_pane=True`. If config/env resolution
  inside `main()` proves too entangled to drive, narrow the patching (explicit
  `--session`, stubbed config loader) rather than dropping the assertion — a
  source-text grep for `mark_pane=True` is **not** an acceptable substitute,
  since it cannot tell a live call from a comment or a dead branch.

**Cleanup ordering (Step 3b) — the concern-4 coverage.**

- New `tests/test_companion_cleanup_ordering.sh` — live-tmux, isolated socket.
  It invokes `aitask_companion_cleanup.sh <primary> <companion>` **directly**
  (driving real `pane-died` events is unnecessary and flaky; the script is the
  unit that decides). Cases, each asserting the exact surviving pane set:
  1. **Companion-first ordering** — window = primary + minimonitor (marked) +
     shadow (`@aitask_shadow_target=<primary>`); invoke with
     `companion=<minimonitor>`. Expect: all three gone.
  2. **Shadow-first ordering** — same window, but invoke with
     `companion=<shadow pane>`, reproducing a hook armed by `spawn_shadow` from
     the full monitor. Expect: all three gone. **This case fails against
     today's script** — it is the negative control for 3b.
  3. **Sibling preservation** — same window plus a plain extra pane. Expect:
     primary killed, shadow killed (job 1 is unconditional), minimonitor and
     the extra pane **alive**.
  4. **Unmarked legacy companion** — a companion pane with no marker, named
     only by the argument. Expect: killed, i.e. the `"$companion"` hint still
     works for panes predating the marker.
- `tests/test_tui_switcher_agent_launch.py` — assert
  `_launch_git_with_companion` routes through
  `attach_companion_cleanup_hook(primary_pane, companion_pane)` and issues no
  bare `set-hook`.

## Step 5 — docs

- `aidocs/framework/tui_conventions.md` §"Companion pane auto-despawn"
  (`:333-362`) — record that `maybe_spawn_minimonitor` arms the hook via
  `attach_companion_cleanup_hook` so every companion path is covered from one
  place; that a bare `set-hook -p … pane-died` is never used; and that **cleanup
  discovers companions by marker, not from the hook payload**, because the
  append-only hook can only ever name the first companion.
- `aidocs/framework/tui_conventions.md` §"The shadow agent is a second
  companion-pane case" (`:364-385`) — document `@aitask_monitor_kind` alongside
  `@aitask_shadow_target`: the `<kind>:<pid>` format, who stamps it (only the
  app, at mount — never the spawner, and why), who clears it, the liveness rule
  including "unverifiable is not dead", and that the guards read it because
  `pane_current_command` reports `python`.
- `aidocs/framework/shadow_agent.md:246` — rename, plus a line that the hook's
  `companion_pane` argument is a hint rather than the cleanup authority.

No website doc changes: none of this is user-facing behavior.

---

### Post-phase (risk mitigations)

1. `[verify_companion_lifecycle_live]` Before the Step 8 review, verify the
   `remain-on-exit` behavior change against a **real tmux server** — unit tests
   cannot reach it. In a live `ait` session:
   - Launch an agent from `ait board` so a companion spawns.
   - `tmux show-hooks -p -t <agent-pane>` lists a `pane-died` entry invoking
     `aitask_companion_cleanup.sh`, and `tmux show-options -p -t <agent-pane>
     remain-on-exit` reads `on`.
   - `tmux show-options -p -t <companion> @aitask_monitor_kind` reads
     `minimonitor:<pid>` with that pid alive.
   - Exit the agent. Confirm the companion despawns, the window closes, and
     `tmux list-panes` shows **no lingering dead pane** (`#{pane_dead}` = 1)
     anywhere in the session.
   - Repeat with a plain shell added to the window: the agent's exit must kill
     the agent pane and **leave the companion alive**.

   Record the observed outcome in the plan's Final Implementation Notes. If a
   dead pane lingers, the fix is to stop arming the hook in
   `maybe_spawn_minimonitor` (Step 3c) — not to ship it.

---

## Verification

```bash
# Unit / contract
bash tests/run_all_python_tests.sh --test-dir tests 2>&1 | tail -5   # check $PIPESTATUS[0]
# Focused, faster loop:
~/.aitask/venv/bin/python -m pytest tests/test_shadow_seam.py \
    tests/test_minimonitor_concern_action.py \
    tests/test_minimonitor_concern_smoke.py \
    tests/test_minimonitor_instance_guard.py \
    tests/test_monitor_marker_liveness.py \
    tests/test_monitor_pane_marker_wiring.py \
    tests/test_monitor_rename_gate.py \
    tests/test_monitor_shadow_pick.py tests/test_minimonitor_shadow_pick.py \
    tests/test_tui_switcher_agent_launch.py -q

# Shell
shellcheck .aitask-scripts/aitask_minimonitor.sh .aitask-scripts/aitask_companion_cleanup.sh
bash tests/test_no_raw_tmux.sh
bash tests/test_minimonitor_single_instance_guard.sh
bash tests/test_companion_cleanup_ordering.sh
bash tests/test_monitor_shadow_spawn_live.sh      # live tmux; exercises the rename
```

**Negative controls** — each must fail *before* the corresponding fix, verified
by running the new test against unmodified source (or by reverting the one
line), not by assertion:

| Mutation | Failing test |
|---|---|
| Drop `if not ok:` from `compute_shadow_staleness` | banner-preservation test in `test_minimonitor_concern_action.py` |
| Keep job 2's `"$companion"`-only companion detection | case 2 (shadow-first ordering) in `test_companion_cleanup_ordering.sh` |
| Revert guard B to `pane_current_command` | case (a) in `test_minimonitor_instance_guard.py` |
| Make `monitor_marker_state` return `absent` for unparseable values | the unverifiable rows in `test_monitor_marker_liveness.py` (both lanes) |
| Re-add a spawner-side `set-option @aitask_monitor_kind` | case (f) in `test_minimonitor_instance_guard.py` |
| Reimplement the shell guard's liveness inline as `${marker##*:}` + `kill -0` | state (iii) `garbage:123` in `test_minimonitor_single_instance_guard.sh` |
| Renumber the verdict codes to `0/1/2` | the disjointness assertion in `test_monitor_marker_liveness.py`, and state (v)'s `exit:1` shim (which would clear a live marker) |
| Change the shell guard's default arm from block to `: ;` | all four faults in state (v) of `test_minimonitor_single_instance_guard.sh` |
| Add a `${MARKER_TOOL:-…}` override to the guard | none — this is why fault injection goes through `$AIT_PYTHON`; guard it in review instead |
| Drop the CLI's `except Exception -> EXIT_PRESENT` | the monkeypatched-raise case in `test_monitor_marker_liveness.py` |
| Drop `mark_pane=True` from either `main()` | the `main()`-link test in `test_monitor_pane_marker_wiring.py` |
| Drop the `unmark_monitor_pane()` call from either `on_unmount` | case 3 in `test_monitor_pane_marker_wiring.py` |

Post-implementation cleanup, archival, and the merge into the output branch are
handled by **Step 9 (Post-Implementation)** of the task workflow.

---

## Risk

### Code-health risk: medium
- Arming the hook inside `maybe_spawn_minimonitor` sets `remain-on-exit on` on
  the agent pane at **all 21 call sites** (board, codebrowser, crew, syncer,
  monitor/minimonitor pick, tui_switcher). Today those panes close silently on
  agent exit; afterwards they fire `pane-died`. If `aitask_companion_cleanup.sh`
  cannot run — or `attach_companion_cleanup_hook` returns `"unverified"` and
  installs nothing while `remain-on-exit` is set regardless — dead panes linger
  instead of closing. · severity: medium
  · → mitigation: inline post-phase verify_companion_lifecycle_live
- Rewriting job 2 of `aitask_companion_cleanup.sh` widens what pane death
  destroys: it now kills *every* marker-carrying pane in the window, not only
  the one the hook named. A wrongly-marked pane would be killed on any primary's
  death. The blast radius is bounded by who writes the marker (only the two
  apps, on their own pane), but the script runs in a minimal hook environment
  where a failure is invisible. · severity: medium
  · → mitigation: test_companion_cleanup_ordering.sh cases 1–4 (Step 4), whose
  case 2 is a true negative control against today's script
- A stale `@aitask_monitor_kind` marker outlives its process on a pane that
  survives it (a minimonitor hard-killed inside the user's own shell pane, so
  `unmark_monitor_pane()` never ran). · severity: low
  · → mitigation: inline pre-phase — folded into Step 2 itself
  (`monitor_marker_alive` + the self-healing `set-option -pu` in both guards)
- Blast radius is wide but mechanical: 8 source files (one of them new), 8
  modified + 5 new test files, 2 aidocs pages — of which the
  `attach_shadow_cleanup_hook` rename is a pure symbol substitution.
  · severity: low · → mitigation: none (the renamed call sites are all exercised
  by the existing suite)
- The guard's liveness check now execs a Python interpreter per marked pane in
  `aitask_minimonitor.sh`. That is the price of having one implementation of the
  rule instead of two that drift; it is paid only on panes that carry a marker,
  and the script already pays two interpreter startups for its dependency check.
  · severity: low · → mitigation: none (accepted cost, recorded here so a later
  reader does not "optimize" it back into a divergent shell reimplementation)

### Goal-achievement risk: low
- **Residual boot-window race.** With the spawner no longer stamping, a second
  `maybe_spawn_minimonitor` call targeting the same window during the ~1 s
  between `split-window` and the app's `on_mount` stamp sees no marker and can
  spawn a duplicate companion. Accepted deliberately: the alternative (spawner
  stamping) reintroduces a self-deadlock in the *primary* path, and the residual
  hole is strictly smaller than today's, where the guard never fires at all.
  · severity: low · → mitigation: none (documented limitation; the overcrowding
  check at `real_panes >= 3` still bounds the outcome)
- The new live shell tests assume `ait_tmux` honors an injected socket and that
  the guard script's final `exec` can be suppressed for the negative controls.
  · severity: low · → mitigation: none (Step 4 states the `send-keys` +
  `capture-pane` fallback, which preserves the controls)

**Reassessment after the review revision.** Goal-achievement drops from `medium`
to **low**: the one high-severity item was a self-deadlock created by the
spawner-side stamp, and removing that stamp eliminates it by construction rather
than guarding against it. Code-health stays **medium** and gains a bullet: the
cleanup rewrite is the correct fix for the ordering defect but genuinely widens
what pane death destroys, which is why it carries a four-case live test rather
than a unit assertion.

### Planned mitigations
- timing: pre-phase | name: monitor_marker_liveness | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — a stale @aitask_monitor_kind marker silently blocks companion spawns | desc: stamp the marker as <kind>:<pid>, decide liveness in one shared module both guards call, clear a provably-dead marker, and treat an unverifiable value as present
- timing: pre-phase | name: verify_marker_wiring | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — guard tests all assume an already-marked pane, so broken production wiring would leave them green | desc: mount-level and main()-level tests proving both apps receive mark_pane=True, stamp a parseable marker at mount, and clear it at unmount
- timing: post-phase | name: verify_companion_lifecycle_live | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — remain-on-exit now set on every companion-bearing agent pane | desc: live-tmux acceptance that pane-died fires, the companion despawns, and no dead pane lingers

---

## Final Implementation Notes

- **Actual work done:** All three defects landed as planned, plus the two fixes
  the plan review added (marker-driven cleanup discovery, and no spawner-side
  stamp). Files: `monitor_core.py` (`get_pane_option` -> `(ok, value)`, the new
  contract-table row, `compute_shadow_staleness`'s `if not ok:` branch);
  **new** `lib/monitor_marker.py` (marker constants, `parse_monitor_marker`,
  `monitor_marker_state` / `_alive`, and the fail-safe CLI);
  `lib/agent_launch_utils.py` (re-exports, `mark_monitor_pane` /
  `unmark_monitor_pane`, marker-based guard B with stale self-heal, hook arming
  in `maybe_spawn_minimonitor`, rename to `attach_companion_cleanup_hook`);
  `aitask_minimonitor.sh` (marker guard calling the CLI, block-by-default);
  `aitask_companion_cleanup.sh` (marker-driven job 2, `|` field separator);
  `lib/tui_switcher.py` (bare `set-hook` replaced by the helper); both apps
  (`mark_pane` flag, stamp at mount, clear at unmount, `main()` wiring).
  Tests: 5 new files (`test_monitor_marker_liveness.py`,
  `test_minimonitor_instance_guard.py`, `test_monitor_pane_marker_wiring.py`,
  `test_minimonitor_single_instance_guard.sh`,
  `test_companion_cleanup_ordering.sh`) plus stub/rename updates in 8 existing
  files. Docs: `tui_conventions.md` (both companion sections + a new
  `@aitask_monitor_kind` subsection), `shadow_agent.md`.

- **Deviations from plan:**
  - `test_monitor_pane_marker_wiring.py` was first written as a test-defining
    base class with two subclasses, which trips
    `tests/test_collection_structure.py`'s "no class inherits tests from a
    same-module base" rule (both subclasses silently re-collect all 6 tests).
    Restructured to a single class parameterizing over `APP_SPECS` with
    `subTest`. Both arms were then re-proven live by mutating the *monitor* app
    (not the minimonitor) and confirming the failure.
  - `aitask_companion_cleanup.sh` uses a space-joined string rather than a bash
    array for the companion list, sidestepping the `set -u` empty-array quirk
    the plan flagged. Pane ids are `%N`, so neither word-splitting nor globbing
    is a hazard.
  - The plan's fallback for the shell test's negative control (`send-keys` +
    `capture-pane`) was not needed: the `$AIT_PYTHON` delegating shim worked, so
    every negative control is a direct assertion.
  - A `AIT_TEST_LAUNCH_WITNESS` positive control was added beyond the plan.
    States (ii)/(iv) assert the *absence* of a block message, which would also
    pass if the script died before reaching the guard; the witness proves the
    run actually reached its final `exec`.

- **Issues encountered:**
  - The plan's original test-harness design ("shim `PATH` so the resolved
    interpreter is a no-op `true`") was wrong and was corrected during the plan
    review: `resolve_python` reaches `$PATH` only after `$AIT_PYTHON`, the venv
    and `~/.aitask/bin/python3`, and a bare `true` fails `require_ait_python`'s
    version probe at `aitask_minimonitor.sh:14` before the guard runs. The shim
    must delegate to the real interpreter and misbehave only for the call under
    test.
  - `tests/test_monitor_shadow_spawn_live.sh` **could not be run** in this
    session: `require_clean_ait_server` refuses inside tmux by design, because
    it arms real `pane-died` hooks and `aitask_companion_cleanup.sh` reaches
    tmux with raw, un-flagged calls that no env override can sandbox. It was not
    forced. Its assertions on the renamed helper are mirrored at unit level by
    `tests/test_monitor_shadow_pick.py::HookIdempotenceTests`, which passes.
    **Worth running from a non-tmux terminal before release.**

- **Key decisions:**
  - **One liveness implementation, called from both languages.** A shell rewrite
    diverges silently in two ways (`${marker##*:}` reads `garbage:123` as a dead
    pid; `kill -0` fails for another user's live process where `os.kill`'s
    `PermissionError` means alive), so `monitor_marker.py` owns the rule and the
    shell guard execs its CLI.
  - **Verdict codes `0/10/11`, outside the interpreter-failure range.** With
    `0/1/2`, an uncaught Python exception (exit 1) would have mapped to "stale"
    and made the guard **clear a live marker** on a crash; a missing file (exit
    2) would have mapped to "absent". Blocking is the shell guard's default arm,
    and the shared `exit 0` sits after the `case` so a future arm must
    `continue` explicitly to become non-blocking.
  - **The spawner never stamps the marker.** A spawner-side stamp lands before
    the child's own guard runs, so the child would see its own marker; removing
    it eliminates the self-deadlock by construction instead of guarding against
    it, at the cost of a documented ~1 s boot-window race.
  - **Cleanup discovers companions by marker.** The `pane-died` hook is
    append-only and carries one `companion_pane`, so the argument only ever
    names the first companion to arm it; the argument is now a fallback hint.

- **Live verification (post-phase mitigation `verify_companion_lifecycle_live`):**
  Run against an isolated tmux server rather than the user's live `-L ait`
  server, which gives the same evidence without risking real agents. Observed:
  hook installed at `pane-died[0]` invoking `aitask_companion_cleanup.sh`;
  `remain-on-exit on`; companion marker `minimonitor:<pid>` with that pid alive.
  Killing the agent process closed the agent pane, despawned the companion and
  closed the window, with **zero lingering dead panes** (`#{pane_dead}` = 1
  anywhere in the session). With an extra plain pane present, the agent's exit
  killed only the agent pane and left both the companion and the extra pane
  alive. No rollback of Step 3c was needed.

- **Negative controls (each mutation run, named test confirmed failing, source
  restored):** staleness `if not ok:` removed -> 3 tests; guard B liveness
  removed -> 3; hook arming removed -> 1; `mark_pane=True` dropped from `main()`
  -> 1; `on_unmount` clear dropped -> 1; monitor-app stamp dropped (subTest arm
  2) -> 2; cleanup marker discovery removed -> the shadow-first ordering case;
  shell guard reimplementing liveness inline -> 11, including `garbage:123`
  being *cleared* rather than blocking; shell guard default arm made
  non-blocking -> 8; open-coded `set-hook` left beside the helper -> 1.

- **Upstream defects identified:**
  - `.aitask-scripts/aitask_minimonitor.sh:36` (pre-change) — the guard's
    self-exclusion compared `#{pane_pid}` against `$$`. Those are different
    processes whenever the script is not the pane's direct child, so the
    self-skip never worked either. Moot now (the new guard needs no
    self-exclusion, since only a booted app writes the marker), recorded because
    the same `$$`-vs-`pane_pid` confusion could recur elsewhere.
  - `.aitask-scripts/monitor/monitor_app.py:2926` — the `c`-hotkey picker passes
    `stale=bool(stale)` to `ConcernPickerModal`, collapsing
    `compute_shadow_staleness`'s tri-state so an *indeterminate* staleness
    renders as "not stale". Behaviour is unchanged by this task (`False` and
    `None` both coerce to `False`), and a one-shot modal has no prior state to
    preserve — but it is the same conflation class this task is about, on a
    surface that could later want to say "unknown".
  - `.aitask-scripts/monitor/monitor_core.py:1779` — `discover_window_panes` is
    still a **sync** `tmux_run` (5 s default timeout) reached from the async
    `_refresh_data` via `_check_auto_close`, so a stalled tmux can freeze the
    minimonitor UI for up to 5 s per tick. Already tracked as t1446's
    `async_window_pane_discovery` follow-up; re-confirmed still present.
