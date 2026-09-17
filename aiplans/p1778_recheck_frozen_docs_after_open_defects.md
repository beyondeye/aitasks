---
Task: t1778_recheck_frozen_docs_after_open_defects.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1778 — Re-check frozen-agent docs after t1773 / t1766 landed

## Context

Risk-mitigation follow-up for t1705_9: the frozen-agent pages were written while
t1773 (closed-window restore) and t1766 (viewer's hardcoded 40 s restore
deadline) were open. Both are now archived as Done (734609846, 016dd7b3a), so
the task is actionable.

Current state, verified against the tree:

- **t1773 half — already documented.** t1784 (68158b17f) added a
  "**Where the agent comes back.**" paragraph to
  `website/content/docs/tuis/frozenagent/how-to.md` § "Bring an agent back"
  (lines ~83-97): the gone-pane → new window route, session creation via the
  bootstrap, and the `session_name_taken` refusal. The one shipped behaviour
  still undocumented is the fail-closed preflight in
  `.aitask-scripts/lib/agent_restore.py` (~499-506): when the recorded pane
  cannot be probed because tmux is unreachable, the restore returns
  `preflight:tmux unreachable` **before any store write**, so the viewer's
  verdict (`agent_sessions.restore_verdict`) is
  `restore did not start — run 'ait frozenagent' or reconcile`, not
  `restore failed: …`.
- **t1766 half — sharpen only.** Viewer (`frozenagent_app._settle_timeout_for`)
  and monitor/minimonitor (`monitor_shared.py` ~1019-1041) both call
  `agent_frozen_ops.restore_settle_timeout(record root, dispatch_grace=10)` =
  10 s dispatch + `restore_ack_grace` + 10 s slack (40 s at default). The
  `reference.md` § Configuration is neutrally worded and not wrong; it can now
  state that every surface derives its wait from the same grace.
- Monitor / minimonitor pages carry no stale restore-deadline or closed-window
  claims (grep for `40 s`, `pane_gone`, `grace`, `closed window`).
- t1705_10 (Ready, not started) owns a future workflow page with "When
  something goes wrong"; the closed-window route now lives in how-to.md, so it
  should link there rather than restate it.

Working on the current branch (profile `fast`).

## Steps

1. **`website/content/docs/tuis/frozenagent/reference.md` § Configuration** —
   after the "read from the record's own project" paragraph, add a short
   paragraph:

   > The same grace sets how long the viewer, `ait monitor` and
   > `ait minimonitor` watch a restore before reporting
   > `restore still <state> after the grace — run reconcile; capture kept`:
   > 10 seconds for the dispatch, plus `restore_ack_grace`, plus 10 seconds of
   > slack — 40 seconds at the default. All three read it from the record's
   > project, so raising the grace never turns a slow but successful restore
   > into a stall report.

2. **`website/content/docs/tuis/frozenagent/how-to.md` § "Bring an agent back"**
   — append one sentence to the "Where the agent comes back" paragraph (before
   the "A restore never borrows…" paragraph):

   > If tmux cannot be queried to tell whether the old pane is still there, the
   > restore does not guess: it stops before touching the record, and the viewer
   > reports `restore did not start — run 'ait frozenagent' or reconcile`.

3. **Coordination note to t1705_10** (post-implementation, via `./ait note`):
   the closed-window / no-session restore route is documented in
   `tuis/frozenagent/how-to.md` § "Bring an agent back" → "Where the agent comes
   back" and the grace/watch-deadline in `reference.md` § Configuration — link to
   those from "When something goes wrong" instead of restating them.

## Verification

```bash
cd website && hugo build --gc --minify && python3 check_links.py --build
```

Plus a re-read of the two edited sections against `restore_settle_timeout` and
the `agent_restore` preflight.

Step 9 (Post-Implementation): commit `documentation: … (t1778)`, archive task
and plan.

## Risk

### Code-health risk: low
None identified.

### Goal-achievement risk: low
- The "Where the agent comes back" text was written by t1784, not this task; if
  t1784's prose has a subtle inaccuracy it rides along unchecked · severity: low
  · → mitigation: none (re-read against `agent_restore.py` during step 2)

## Final Implementation Notes
- **Actual work done:** Steps 1 and 2 as planned — `reference.md` § Configuration now states the viewer/monitor/minimonitor watch deadline (10 s dispatch + `restore_ack_grace` + 10 s slack, read from the record's project); `how-to.md` § "Where the agent comes back" gains the tmux-unreachable fail-closed sentence. Step 3 (note to t1705_10) is sent at Step 8e.
- **Deviations from plan:** None.
- **Issues encountered:** The t1773 half of this task had already been covered by t1784 (68158b17f), which added the "Where the agent comes back" paragraph; re-read it against `agent_restore.py` and found it accurate.
- **Key decisions:** Verified the tmux-unreachable message against `agent_sessions.restore_verdict`: the preflight fails before `restore-begin`, so `restore_attempts` never bumps and the verdict is `restore did not start — …` (not `restore failed: preflight:…`).
- **Upstream defects identified:** None
