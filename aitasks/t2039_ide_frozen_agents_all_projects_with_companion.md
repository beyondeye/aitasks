---
priority: high
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [frozen, minimonitor, tmux, ait_ide]
gates: [risk_evaluated]
created_at: 2026-10-16 11:06
updated_at: 2026-10-16 11:06
---

## User report

1. `ait ide` offers to bring back frozen agents **only for the project it is run
   in**. To bring back frozen agents from several projects (here `aitasks` and
   `thinking_backend`), the user has to run `ait ide` separately in each project
   root. That is poor UX.
2. Frozen agents brought back by `ait ide` (viewers recreated with V, or restored
   with R/P) come back **without a minimonitor** in their window. Every agent
   window should always have its minimonitor companion beside it.

Both findings below were observed live on 2026-10-16 (tmux 3.8, `-L ait` server),
after the user picked V in the `aitasks` and `thinking_back` sessions.

## Part A — the companion minimonitor kills itself right after it is spawned (root cause, reproduced)

**Evidence**
- Each recreated viewer window (`agent-pick-*`) holds only its stand-in pane:
  `%1 %3 %5 %7 %9` in `aitasks`, `%12 %14` in `thinking_back`.
- The `pane-died` hook on `%1` is
  `aitask_companion_cleanup.sh %1 %2`. So `agent_reopen._fresh` →
  `agent_restore._spawn_companion` → `maybe_spawn_minimonitor` *did* split a
  companion (`%2`, and likewise `%4 %6 %8 %10 %13 %15`), and every one is gone.
- Spawning `ait minimonitor` again beside `%1` (window 2), while the session's
  active window was 7, exits in about 140 ms with rc 0 and prints
  `A monitor is already running in this window. Exiting.`
- A probe run from a pane in window 2: an untargeted
  `tmux -L ait list-panes -F '#{window_index}|#{pane_id}|#{@aitask_monitor_kind}'`
  listed **window 7's** panes (`%16`, plus `%17` carrying `minimonitor:21899`).
  `display-message -p '#{window_index}'` printed `7`. On this server (with
  control-mode clients attached), an untargeted command run inside a pane
  resolves to the session's *current* window, not to the pane's own window.

**Root cause.** The single-instance guard in `.aitask-scripts/aitask_minimonitor.sh`
(`ait_tmux list-panes -F "#{pane_id}|#{@aitask_monitor_kind}"`, with no `-t`) looks
at the session's **active** window. t1451 made this guard live by switching it to
the marker check; before that it could never fire. Now any companion spawned into
a window that is *not* the active one exits whenever the active window holds a live
monitor or minimonitor. After `ait ide`, the active window is `monitor`, so every
companion that `reopen` spawns dies at once.

**Exposed spawn paths** (check each one during planning):
- `agent_reopen._fresh` uses `new-window -d`; `_adopt` acts on a window that is
  not selected.
- `launch_in_tmux` with `select_window=False` (`-d`) — background launches from
  board, codebrowser and trails.
- Splits into an existing window that is not the active one.
- Cross-session spawns from `tui_switcher`, which hit the target session's
  current window.
- `agent_restore._launch_into_new_window` selects its window, so it is exposed
  only if the active window changes before the guard runs (a race).

**Fix direction.** Point the guard at the pane's own window: `list-panes -t
"$TMUX_PANE"` (a pane target lists that pane's window). Decide the behaviour when
`$TMUX_PANE` is unset. Also grep shell and Python code for other untargeted tmux
reads that run *inside* a pane (`list-panes` / `display-message -p` with no `-t`).
They belong to the same defect class. `aidocs/framework/tmux_gateway.md` applies.

**Tests.** `tests/test_minimonitor_single_instance_guard.sh` builds a single
window, which is also the active one, so it cannot see this bug. Add a live case on
a scratch socket: the guard's window is **not** the active window, and the active
window carries a live monitor marker. The companion must stay up. Keep the existing
positive case: a live monitor in the *same* window still blocks. The new case must
fail on the pre-fix guard.

## Part B — a restored agent gets no companion when its viewer window has none

The same-pane branch of `agent_restore.restore()` respawns the agent inside the
viewer pane. On purpose, it never spawns a companion: "the companion its surviving
window already has is never doubled" (docstring of `_launch_into_new_window`). That
assumption breaks whenever the viewer window has lost its companion:
- Part A;
- the user closed the companion;
- viewers reopened before t1851.

The restored agent then has no minimonitor for the rest of its life.

Direction: after a successful same-pane restore, call the best-effort
`_spawn_companion`. `maybe_spawn_minimonitor` already refuses when a live monitor
marker sits in the window, so it cannot double one. During planning, also decide
whether `ait ide` should top up companions for viewers that are *tracked* but have
no companion. `gone` does not list those, so today nothing would ever repair them.
For example, the viewers in the live sessions above stay companionless until they
are restored, even after the Part A fix.

## Part C — one `ait ide` run offers frozen agents of every project

**Today.** `aitask_ide.sh` → `ide_offer_frozen_agents <root> <session> <frozen_sh>`
(`.aitask-scripts/lib/ide_frozen_offer.sh`) → `aitask_frozen.sh gone --root <cwd>`.
Only this project's records are listed, and V/R/P act with
`--session <this session>`.

**The store is global** (`~/.config/aitasks/agent_sessions.json`). On 2026-10-16 it
held frozen records for:

| project | records | notes |
|---|---|---|
| `aitasks` | 5 | |
| `thinking_backend` | 2 | session `thinking_back` |
| `thinking_app` | 4 | from 2026-09-20; their session `thinkingapp` no longer exists; no `agent_kind` and no session id, so view-only |

**Wanted.** Running `ait ide` in any project lists frozen agents with no viewer
**across all projects**, grouped by project. V/R/P act on all of them (decide in
planning whether a per-project choice is also needed). Each agent lands in **its
own project's tmux session**, never in the session being opened: a project's
agents live in that project's session, and `ait monitor` maps sessions back to
roots.

**Building blocks that already exist**
- `agent_reopen.reopen_all(root, session=None)` / `reopen_one` →
  `agent_restore._resolve_target_session(root, None)`. It uses the first session
  that discovery attributes to the root; if none exists, it creates one through
  `tmux_bootstrap.sh --create-only` (t1784), under that function's ownership rule.
- `restore <id>` without `--session` uses the same resolution.
- Each project's session name comes from that project's `tmux.default_session`
  (for example, `thinking_backend` → `thinking_back`).

**Design points for planning**
- Grammar: add a cross-root `gone` (for example `gone --all-roots`) whose lines
  carry the record's root. Update the parser in `ide_frozen_offer.sh` to match,
  and keep `gone --root` as it is.
- The current project stays pinned to `--session <this session>`. Every other
  project resolves its own session. A refused or colliding bootstrap for one
  project (name taken, `session_not_for_root`, `default_session_unreadable`) is
  reported for that project and must not abort the others.
- Stale roots (directory gone, or no longer a registered project): list them, but
  never bootstrap a session for a missing root. Report them so the user can drop
  them with `ait frozenagent`. Decide whether the offer is limited to projects in
  the registry (`ait projects list`).
- The re-classification in R/P (`_ide_frozen_restore` re-runs `gone` and reads
  the caller's `ids` / `windows` arrays) must re-classify across every root it
  acts on.
- Prompt UX: show one group per project with counts, and V stays the default.
  In non-interactive mode, the one-line hint also mentions how many records other
  projects have. `--no-frozen-check` stays as it is.
- After acting, tell the user how to reach the other projects' sessions (TUI
  switcher `j`, or `ait ide` in that project).
- Docs: the `ait ide --help` text ("Frozen agents: when this project has…") and
  `website/content/docs/workflows/freeze-and-restore-agents.md`. Run
  `website/check_links.py --build` after any website edit.
- Tests: extend `tests/test_ide_frozen_offer.sh` (it uses a stub `frozen_sh`) and
  `tests/test_agent_reopen.py` / `tests/test_frozen_reopen_live.sh` for the
  cross-root listing and per-project session targeting. That includes one
  project whose session bootstrap is refused while the others still succeed.

## Acceptance criteria

- [ ] A minimonitor companion spawned into a window that is not the active one
      stays up when the active window holds a live monitor. A live test covers
      this and fails on the pre-fix guard.
- [ ] A live monitor in the *same* window still blocks a second minimonitor
      (existing positive case kept).
- [ ] After `ait ide` → V, every recreated viewer window has a live minimonitor.
      After R/P, or a later restore, every restored agent window has one.
- [ ] A single `ait ide` run lists frozen agents with no viewer for every project,
      grouped by project. Its actions put each agent into that project's own
      session. A failure in one project never blocks the others.
- [ ] `ait ide --help` and the freeze-and-restore workflow page describe the
      cross-project behaviour.
