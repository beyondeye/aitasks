---
Task: t1716_probe_respawn_pane_e_env_passing.md
Created by: aitask-wrap (retroactive documentation)
Base branch: main
Output branch: main
---

# t1716 — Case 3b: `respawn-pane -e` env passing

## Summary

Adds **Case 3b** to `tests/test_frozen_standin_spike.sh` (the permanent t1705
freeze-spike probe, kept as child t1705_4's live acceptance control). The case
proves that tmux's native `respawn-pane -e VAR=value`:

1. delivers the variable to the respawned process, and
2. keeps `#{pane_pid}` equal to that process — i.e. introduces no wrapper.

61 added lines, one file, no product code.

## Files Modified

- **`tests/test_frozen_standin_spike.sh`** — new `Case 3b` block inserted
  directly after Case 3, plus one line added to the header case list so the
  file's own index stays accurate.

## Probable User Intent

This did not come from a pre-existing plan. It arose from a question about
whether the spike's findings would survive a tmux upgrade (3.6a → 3.7c). While
checking the upstream CHANGES, the installed man page showed that
`respawn-pane` already accepts `-e environment` on 3.6a:

```
respawn-pane [-k] [-c start-directory] [-e environment] [-t target-pane]
             [shell-command [argument ...]]
```

The t1705_1 spike's Case 3 had validated only the `env VAR=… cmd` prefix, so
t1705_5 (restore / re-pick flows) would have had to choose its env-passing
mechanism on assumption. The user asked for the alternative to be pinned by
evidence before that child commits to one.

## Design notes

**A one-variable parallel, deliberately.** Case 3b uses the same fixture and the
same two assertions as Case 3; only the delivery mechanism differs. Running both
is what makes the comparison meaningful — a single passing mechanism proves
nothing about the alternative, and a shared fixture is what rules out the
difference being an artefact of how each case was built.

**Why `#{pane_pid}` is the load-bearing assertion.** `launch_in_tmux`'s contract
is that the pane's pid *is* the agent process, because a wrapper that **outlives**
the agent would make a dead agent's lock keep reading as alive (t1465) — a
quieter failure than the false-crash bug that contract replaced. A mechanism
that broke it would be unusable for the restore path no matter how cleanly it
delivered the variable.

**Why the process self-reports.** Inherited verbatim from Case 3's reasoning:
this host is macOS, which has no `/proc`, and `ps eww` / `ps -E` return no
environment at all under SIP — there is no portable way to read a *foreign*
process's environment. A `pgrep -f` pattern was also rejected: it can match a
concurrent case in this same suite or an unrelated user process, so the
assertion could pass while inspecting the wrong process, which is worse than
failing. `fake_agent.sh --report-env <file>` writes to a path only this run
knows, tying the pid and the environment to one self-report by the process
itself.

**The absent-report path is a finding, not a skip.** A tmux build without `-e`
fails the respawn outright, so the case records `UNKNOWN` plus `tmux -V` rather
than passing silently — the same principle as the spike's other verdicts, where
"we could not observe it" must never be recorded as "it does not work".

## Result

Measured on tmux 3.6a / macOS 15.7.3 (Darwin 24.6.0): **both mechanisms work.**

| mechanism | pane_pid == agent pid | variable delivered |
|---|---|---|
| `env VAR=… <cmd>` prefix (Case 3) | yes | yes |
| `respawn-pane -e VAR=value` (Case 3b) | yes | yes |

`-e` is the recommendation for t1705_5: tmux sets the variable in the spawned
process's environment itself, so the command string carries no wrapper at all
and nothing execs through `env`. The prefix stays proven and usable as a
fallback on a build without `-e`.

Suite: **31/31** (was 29/29 — this adds two assertions). shellcheck clean
(SC1091 sourcing / SC2329 trap-invoked notices only).

## Final Implementation Notes

- **Actual work done:** Added Case 3b to `tests/test_frozen_standin_spike.sh`
  (+61 lines) and updated the header case index. Recorded the result in the
  `## Spike findings (t1705_1) — PINNED` block of
  `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` — item 2 now
  carries a two-mechanism table and the `-e` recommendation — and cross-
  referenced this task from `t1705_5`, the child that consumes the finding.
- **Deviations from plan:** N/A (retroactive wrap — no prior plan existed).
- **Issues encountered:** None. The case passed on first run.
- **Key decisions:** (a) implemented as a one-variable parallel to Case 3 rather
  than as a replacement, so both mechanisms stay measured; (b) the no-report
  path records `UNKNOWN` + `tmux -V` instead of skipping, so an unsupported tmux
  build is visible; (c) the archived `p1705_1` plan was deliberately left
  untouched — the active parent plan is the live cross-child contract, and
  rewriting an archived record to describe later work would misrepresent what
  that task did.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** t1705_5's restore path should prefer
  `respawn-pane -e` over an `env` prefix when passing `AITASK_RESTORE_*`. Both
  preserve the `pid_anchor` lock-liveness contract; `-e` avoids the extra exec.
  This needs no tmux version bump — `-e` is present on 3.6a.
