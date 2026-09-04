---
priority: medium
effort: low
depends: []
issue_type: test
status: Implementing
labels: [aitask_monitor, aitask_monitormini, tmux]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1382
followup_kind: upstream_defect
created_at: 2026-09-02 23:13
updated_at: 2026-09-03 11:35
---

## Origin

Spawned from t1686 during Step 8b review.

## Upstream defect

- `tests/test_kill_agent_pane_smart.sh` — the live fixture builds its companion
  as the **LAST** pane, where dropping a helper changes no count, so it could
  never observe the last-record drop that silently killed windows containing a
  live agent. Left as-is by t1686 (it remains a valid fallback-rung control),
  but its ordering is why the defect below survived undetected.

The defect it could not see (found and **already fixed** in t1686, listed here
only as the diagnostic chain):

- `.aitask-scripts/monitor/monitor_core.py:3053` — `kill_agent_pane_smart`
  iterated `stdout.strip().splitlines()` over a `list-panes` format already
  ending in `#{@aitask_shadow_target}`, which is empty on every non-shadow pane.
  `str.strip()` acts on the whole buffer, so it ate the trailing tab of the
  **last** record; that record was then short a field and silently `continue`d.
  When the dropped pane was the only other real agent,
  `count_other_real_agents` returned 0 and the **whole window was killed with a
  live agent still in it.**

## Diagnostic context

From t1686's Final Implementation Notes. The defect was invisible to the live
suite purely because of fixture ordering: `make_window()` creates pane 0 (agent),
splits pane 1 (agent), then splits pane 2 (the companion). tmux lists panes in
index order, so the companion is always last — and a *helper* being dropped from
`records` changes no count, because it was going to be excluded anyway. The one
ordering that discriminates (an unmarked **real agent** listed last) is never
built.

t1686 demonstrated the defect live on an isolated tmux server: with the pre-fix
`strip()`, `kill_agent_pane_smart` on one of two real agent panes returned
`killed_window=True` and destroyed the surviving agent; with the fix it returned
`killed_window=False` and the sibling survived.

## Suggested fix

Add a case to `make_window()` (or a second fixture window) in which an **unmarked
real agent** pane is created last, then assert that killing a sibling collapses to
`kill_pane` and the last pane survives. Keep the existing companion-last case — it
is the fallback-rung control. The synthetic equivalents already exist as
`KillAgentPaneSmartTests::test_counts_an_unmarked_last_real_agent` and its paired
control in `tests/test_monitor_companion_filter.py`; this task carries the same
discrimination into the live-tmux tier.

## Crash postmortem — this task took down the live tmux server (2026-09-03)

**Status when it happened:** `Implementing`, during exploration, before any
fixture edit was written. No repo change was lost; the work simply has to
restart from the Suggested fix above.

**What happened.** At 09:39:52 the session ran this ad-hoc probe to confirm the
`strip()`-eats-the-trailing-tab mechanism against a real tmux:

```bash
D=$(mktemp -d) && TMUX_TMPDIR=$D tmux new-session -d -s probe "tail -f /dev/null" \
  && TMUX_TMPDIR=$D tmux split-window -t probe "tail -f /dev/null" \
  && ... TMUX_TMPDIR=$D tmux kill-server
```

At 09:39:54 the user's `tmux -L ait` server died, taking ~30 panes across three
sessions (`aitasks`, `thinkingapp`, `thinking_back`) — every running code agent,
TUI and shell, including the pane this task was executing in. The session
transcript ends mid-probe.

**Root cause.** `TMUX_TMPDIR` is not isolation inside a pane. tmux resolves its
socket from `$TMUX` when that is set and ignores `TMUX_TMPDIR` entirely, so
both the `new-session` and the `kill-server` addressed `/tmp/tmux-1000/ait`.
Re-verified read-only on 2026-09-03:

```
$ TMUX_TMPDIR=/tmp/tmp.X tmux display-message -p '#{socket_path}'
/tmp/tmux-1000/ait                                   # the LIVE server
$ env -u TMUX TMUX_TMPDIR=/tmp/tmp.X tmux display-message -p '#{socket_path}'
error connecting to /tmp/tmp.X/tmux-1000/default     # correctly isolated
```

The probe was never a product defect — `kill_agent_pane_smart` was not running.
It was an unguarded ad-hoc command. A secondary factor made recovery worse: a
control client leaked on 2026-09-01 by a direct (un-isolated) run of
`tests/test_minimonitor_startup_input_latency.py` held a reader-less stdout
pipe, so the dying server hung in exit limbo and `ait ide` failed with
"spawn_session_detached: tmux new-session failed" until that client was killed.

**Guard now in place** (landed before this task resumes):

- `.claude/hooks/guard_live_tmux.py` — `PreToolUse`/`Bash` hook registered in
  `.claude/settings.json`. Denies (a) any destructive tmux verb (`kill-*`,
  `respawn-*`, `unlink-window`, `source-file`) with no `-L`/`-S`, and (b) any
  `TMUX_TMPDIR=`-prefixed tmux call that does not also strip `$TMUX` — the
  exact shape above. Socketed calls (`tmux -L throwaway kill-server`,
  `tmux -L ait list-panes`) are untouched. Verified live: the hook refused a
  `tmux kill-session` before it reached tmux.
- `tests/test_guard_live_tmux.sh` — 22 assertions, including the verbatim
  probe; both guard rules are independently mutation-checked.
- `aidocs/framework/tui_conventions.md` — new "Ad-hoc probes: `TMUX_TMPDIR` is
  not isolation" subsection under "Tmux-stress tasks".

## Resume preconditions

1. Every tmux call in this task — fixture, probe or one-liner — carries an
   explicit `-L <throwaway-socket>`. The hook denies the unsocketed forms, but
   do not treat the hook as the design: it only covers Claude Code Bash calls.
2. The live-fixture work belongs in `tests/test_kill_agent_pane_smart.sh`,
   which already routes through `tests/lib/tmux_isolation.sh`. Extend
   `make_window()` there rather than writing a standalone probe script.
3. Do not demonstrate the pre-fix defect again. t1686 already demonstrated it
   live and the fix is committed; this task only adds the fixture ordering that
   would have caught it. A "prove the defect first" step would mean killing
   panes on a real server for a result already in the record.
4. Before running the extended suite, confirm the target socket is the fixture
   one, not `ait`: `tmux -L <fixture> display-message -p '#{socket_path}'`.
