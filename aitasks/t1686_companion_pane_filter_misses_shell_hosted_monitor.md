---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [aitask_monitor, aitask_monitormini, tmux]
gates: [risk_evaluated]
anchor: 1382
created_at: 2026-09-02 14:16
updated_at: 2026-09-02 14:16
---

## Symptom

`ait minimonitor` (and `ait monitor`) list an agent window **twice**: once as
the real agent card and once as a second AGENT card carrying the *same* window
name. Observed live on `agent-pick-1677` and `agent-pick-1683`.

This is **not** a regression from t1679 (`pane_sort_key` gained a window-name
slot) — that change only reorders cards, it cannot duplicate one.

## Root cause

`_is_companion_process(pid)` (`.aitask-scripts/monitor/monitor_core.py:303`)
decides "is this pane a minimonitor/monitor companion?" by reading
`/proc/<pid>/cmdline` and matching `_COMPANION_KEYWORDS = ("minimonitor",
"monitor_app")`. The `pid` it is handed is tmux's `#{pane_pid}`.

`#{pane_pid}` is the pane's **top-level** process, not its foreground one. When
a companion is launched as the pane's start command (`ait minimonitor`, the
normal path) that happens to be the Python process, and the match works. When a
user restarts the companion **from an interactive shell inside the pane**,
`#{pane_pid}` is `-bash` and `minimonitor_app.py` is a *child* pid. The keyword
match then fails and the pane is not filtered.

Verified live on this machine:

```
%406|agent-pick-1677|python|3972100|START=      -> /proc/3972100/cmdline = "-bash"
                                                   child 1605367 = minimonitor_app.py
%415|agent-pick-1683|python|1611529|START=      -> /proc/1611529/cmdline = "-bash"
                                                   child 1612654 = minimonitor_app.py
```

Every other companion pane in the session had `START=ait minimonitor` and a
Python `pane_pid`. `%406` and `%415` were the **only** two shell-hosted
companions, and `agent-pick-1677` / `agent-pick-1683` were the **only** two
duplicated windows — an exact correlation.

Once the filter misses the pane, `_parse_list_panes`
(`monitor_core.py:2077`) falls through to
`classify_pane(window_name)`, which matches the `agent-` prefix and returns
`PaneCategory.AGENT`. The companion is then rendered as a full agent card, and
because a companion shares its agent's window name the two cards are
indistinguishable in the list.

## The seam that already exists

Every companion stamps the pane-scoped option
`@aitask_monitor_kind = "<kind>:<pid>"` on itself, and the recorded pid is the
**app's own** pid — exactly the one the cmdline heuristic cannot reach:

```
%406: @aitask_monitor_kind minimonitor:1605367
%415: @aitask_monitor_kind minimonitor:1612654
```

`.aitask-scripts/lib/monitor_marker.py` (t1451) is the canonical, single
implementation of the marker's parse + liveness rule
(`parse_monitor_marker` / `monitor_marker_state` / `monitor_marker_alive`),
already consumed by `aitask_companion_cleanup.sh` and
`agent_launch_utils.maybe_spawn_minimonitor`. Monitor **discovery** is the one
place that never consults it, and instead re-derives the same fact with a weaker
heuristic — the classic parallel-reimplementation-of-a-canonical-seam shape.

Reading the marker costs **zero extra tmux round trips**: `_LIST_PANES_FORMAT`
already carries `#{@aitask_shadow_target}` for exactly the analogous
shadow-helper filter, so `#{@aitask_monitor_kind}` is one more field on the same
`list-panes` call.

## Scope — three call sites share the blind spot

| site | consequence today |
|---|---|
| `_parse_list_panes` (`monitor_core.py:2077`) | the duplicate card — the reported symptom |
| `_find_companion_pane_in_window` (`monitor_core.py:3005`) | returns `None`, so callers cannot locate a shell-hosted companion pane in a window |
| kill-pane-or-window helper (`monitor_core.py:3064`) | `is_helper` is False for a shell-hosted companion, so `count_other_real_agents` sees a phantom agent and the kill is downgraded from kill-**window** to kill-**pane**, orphaning the window |

The third is a real behavioural defect beyond cosmetics and should be fixed in
the same change.

## Direction (to be confirmed at planning)

Make the marker the **primary** signal and keep the cmdline heuristic as a
fallback, rather than replacing it outright:

- `@aitask_monitor_kind` present and `monitor_marker_alive()` → companion.
- Marker absent/stale → fall back to `_is_companion_process(pane_pid)`, which
  still catches a companion whose marker was never stamped (a `run_test()`
  mount deliberately passes `mark_pane=False`, and older panes predate t1451).

Do **not** treat a stale marker as a companion: `monitor_marker.py` already
distinguishes `stale` from `present`, and "unverifiable is not absence" is its
documented rule — reuse those verdicts rather than re-deriving them.

## Notes / constraints for the implementer

- Adding a field to `_LIST_PANES_FORMAT` changes the arity of parsed lines. The
  parser currently tolerates `len(parts) in (9, 10)` (10 = current, 9 =
  pre-`history_size` test stubs). That tolerance list, and every test stub that
  builds a `list-panes` line by hand, must be updated together — a stub left at
  the old arity is silently `continue`d, i.e. the test passes vacuously.
- `_is_companion_pane` memoizes only **positive** verdicts, with a TTL, because
  a launcher pane `exec`s into the app under an unchanged pid. Any new signal
  must preserve that asymmetry.
- The marker is only stamped by the production launcher (`mark_pane=True`);
  `App.run_test()` mounts deliberately do not stamp, so the fallback rung must
  survive.

## Acceptance criteria

- [ ] A minimonitor pane hosted under an interactive shell (marker present, app
      as a child pid) is classified as a companion by discovery and does **not**
      appear as an AGENT card in either TUI's list.
- [ ] The same pane is not counted as a real agent by the kill-pane-or-window
      helper: killing the last real agent in such a window kills the **window**.
- [ ] `_find_companion_pane_in_window` resolves a shell-hosted companion pane.
- [ ] A companion pane with **no** marker (unstamped / test mount) is still
      filtered via the existing cmdline fallback — a negative control proving
      the fallback rung is reachable, not dead code.
- [ ] A **stale** marker (recorded pid gone) does not classify a pane as a live
      companion.
- [ ] `monitor_marker.py`'s parse/liveness rule is called, not re-implemented,
      in `monitor_core.py`.
- [ ] Test stubs that construct `list-panes` lines are updated to the new arity;
      a deliberately-wrong-arity line is asserted to be rejected so the arity
      tolerance cannot silently swallow a malformed stub.
- [ ] Existing pane-ordering behaviour (t1659 / t1679) is untouched.

## Reproduction

```bash
tmux split-window -t <agent-window>     # a plain shell pane
# inside it:
ait minimonitor                          # or: python .aitask-scripts/monitor/minimonitor_app.py
```
Then look at any *other* minimonitor in the session: the window now appears
twice in the agent list.

## Related, deliberately NOT folded

- **t1389** — replace prefix-based agent/task classification with stamped pane
  identity. Broader enhancement (effort high) covering a different derivation
  (agent-ness and task binding from the window *name*); this task is the narrow
  companion-filter defect and should not wait on it.
- **t1447** — companion cleanup-hook arming and dead-monitor guards. Same
  subsystem, different failure.
