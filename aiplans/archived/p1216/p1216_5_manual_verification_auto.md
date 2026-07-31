---
Task: t1216_5_manual_verification_monitor_shadow_pane_view_and_concern_pic.md
Parent Task: aitasks/t1216_monitor_shadow_pane_view_and_concern_picker.md
Archived Sibling Plans: aiplans/archived/p1216/p1216_1_shared_shadow_seam.md, aiplans/archived/p1216/p1216_2_monitor_shadow_zone.md, aiplans/archived/p1216/p1216_3_monitor_concern_picker.md, aiplans/archived/p1216/p1216_4_monitor_shadow_spawn.md
Base branch: main
Output branch: main
---

# p1216_5 — Manual-verification auto-execution record

Autonomous auto-verification (strategy: autonomous) of the 22-item checklist
for the monitor shadow pane view + concern picker feature (t1216_1..t1216_4).
All 22 items reached **pass**. This file is the retroactive record of what was
actually run.

## Safety envelope

The task's pick-time guard was honored before any execution:

- The picking shell was **outside tmux** (`TMUX` and `AITASKS_TMUX_SOCKET`
  unset) and `tmux -L ait list-panes -a` reported **no server** — no live code
  agents were at risk.
- All live checks ran on a **throwaway isolated tmux server**
  (`TMUX_TMPDIR=/tmp/aitsv_1000`, private socket dir,
  `AITASKS_TMUX_SOCKET=""` pinning the gateway to the no-flag path), created
  and killed by the harness. The `-L ait` socket was re-checked empty after
  teardown.
- The two tmux-destructive spawn/death items were delegated to
  `tests/test_monitor_shadow_spawn_live.sh` (t1353), which carries its own
  `require_clean_ait_server` + `require_isolated_tmux` guards.

## Live fixture

Scratchpad harness (`shadowver/setup.sh` + `env.sh`, session-scratchpad only,
not committed):

- Fake project root with `aitasks/metadata/project_config.yaml` (plus, for the
  `E` dialog leg, the repo's `codeagent_config.json` / `models_*.json` and a
  symlink to the real `.aitask-scripts/`) so session discovery and dry-run
  command resolution worked.
- Session `aitwork`, 220x52: windows `home`, `agent-t9941/2/3` (fake agents =
  `tail -f <feed>`; agent classification is window-prefix based), `monitor`
  running the real `aitask_monitor.sh --session aitwork --interval 1`.
- Fake shadows = 60-col splits in the agent windows tailing feed files, with
  `@aitask_shadow_target` stamped to the followed pane; concern blocks and
  agent output injected by appending to the feed files (no command echo).
- Keys driven with `tmux send-keys` (including SGR mouse sequences for card
  clicks and wheel scroll); assertions via `tmux capture-pane -p` (and `-e`
  for the border-styling comparison).

## Execution Log

- **Item 1 (run outside main tmux):** pass — environment verified as above.
- **Item 2 (minimonitor unchanged after lift):** pass — real minimonitor
  spawned as a companion split beside `agent-t9941`; resolved "this agent"
  correctly; `c` opened the narrow two-line-row picker; with a past
  `@aitask_shadow_analyzed_at` and fresh followed-agent output, the picker
  showed the stale banner. Discriminating A/B: a git worktree at the pre-lift
  commit (`466d6d9c0~1`) ran a second minimonitor against the same fixture —
  behavior identical pre/post lift (including the standing top banner not
  rendering in this synthetic fixture in either version, so that is a fixture
  condition, not a lift regression; banner logic is pinned by
  `ShadowFreshnessTests`). The `e`-spawn leg is pinned by
  `test_minimonitor_shadow_pick.py` (OK).
- **Item 3 (analyzed_at only written from shadow pane):** pass — a stamp of
  `1000.0` survived many monitor tick captures and zone interaction unchanged;
  a second shadow's stamp stayed **empty** across tick captures and an
  explicit `c` capture.
- **Item 4 (Tab cycling):** pass — with shadow: list → PREVIEW(LIVE) →
  SHADOW(LIVE) → list; without shadow: list ↔ preview only, no Shadow header.
- **Item 5 (unwrapped at real width):** pass — a 100-char line wrapped at
  exactly the real 60-col shadow pane boundary in both the real pane and the
  monitor column (continuation row identical), proving no re-wrap at monitor
  column width.
- **Item 6 (active column unambiguous):** pass — LIVE badge tracked the
  focused column in every capture; full-screen ANSI capture diff shows the
  accent border styling shift with zone state (accent-run counts 48 vs 26).
- **Item 7 (key routing):** pass — text typed in SHADOW zone appeared only in
  the shadow pane; in PREVIEW zone only in the agent pane.
- **Item 8 (narrow fallback):** pass — at 90 cols the shadow column
  disappeared and the agent preview went full-width (LIVE retained); restored
  at 220 cols.
- **Item 9 (per-column tail resume):** pass — `t` from the pane list resumed
  tail only on the last-focused column in both directions; the other column's
  scroll was byte-identical across the `t` press. Observation (informational):
  entering a preview zone can shift a paused column ~5 lines via the
  text-anchor restore; pre-existing anchor-by-text behavior, not the `t`
  contract.
- **Item 10 (kill shadow while focused):** pass — killed the shadow with
  SHADOW focused while typing; zero keystrokes reached the agent pane; zone
  fell back to PREVIEW with the "Shadow gone — back to the agent preview"
  toast.
- **Item 11 (badge, no toast on non-selected):** pass — new block on the
  non-selected agent's shadow lit `◆!` on that card; no toast.
- **Item 12 (toast once):** pass — selecting the agent fired the toast once;
  no re-toast across 15s of 1s ticks.
- **Item 13 (picker → clipboard → paste):** pass — picker showed the latest
  block only (last-block-wins); ticked 1 of 2 rows; confirm wrote
  `DEFAULT_PREAMBLE` + only the selected concern to the tmux buffer
  (`load-buffer -w` path); `paste-buffer` into the followed agent rendered it
  correctly.
- **Item 14 (Esc cancels):** pass — no tmux buffer written; badge stayed
  cleared.
- **Item 15 (stale marker):** pass — past stamp + fresh agent output → toast
  carried "⚠ STALE — agent moved on" and the picker showed the red stale
  banner.
- **Item 16 (no per-tick subprocess churn):** pass — 30s /proc child-PID
  sampling (4ms period) in two configs (3 shadowed agents, badges absent vs
  standing concern blocks): identical child sets — one persistent
  `tmux -C attach` control client plus one unrelated `desync_state.py`
  snapshot; CPU 32 vs 34 ticks (~1% core, flat); no
  `aitask_shadow_capture.sh` processes; shadowed agents ran ~40 min total in
  the fixture.
- **Item 17 (e splits beside the agent):** pass —
  `tests/test_monitor_shadow_spawn_live.sh` case A drives the real
  `action_launch_shadow` on live tmux: shadow lands in the followed agent's
  window, monitor pane never named in hooks; `e` binding pinned by the mocked
  suite.
- **Item 18 (duplicate refused):** pass — live monitor `e` on a shadowed
  agent showed "A shadow is already running for this agent";
  `DuplicateGuardTests` additionally pin the guard as live-query-based.
- **Item 19 (E picker dialog):** pass — live `E` opened the
  "Shadow (pick agent)" dialog with the agent/model selector (cancelled;
  nothing launched); chosen-agent launch args pinned by the mocked suite.
- **Item 20 (agent death):** pass — live smoke cases E/F: the cleanup hook
  fired on agent death, the shadow died, the monitor stand-in survived; the
  wrong-companion bypass control proved the kill path is real.
- **Item 21 (shadow_same_window false):** pass — live smoke case B: shadow in
  its own `agent-shadow-<task>` window, active window unmoved, cleanup hook
  armed with `[agent, shadow]`; hook lethality proven in cases E/F.
- **Item 22 (shadows never agents):** pass — CODE AGENTS count stayed at the
  real-agent count with shadows bound and shadow panes never appeared as
  cards; cache-boundary and kill/sibling exclusion pinned by
  `test_monitor_shadow_status.py`; `tests/test_no_raw_tmux.sh` PASS.

Suites run this session (all green): `test_monitor_shadow_pick`,
`test_monitor_shadow_zone`, `test_monitor_shadow_status`,
`test_monitor_concern_action`, `test_minimonitor_concern_action`,
`test_minimonitor_shadow_pick` (unittest, venv python),
`tests/test_monitor_shadow_spawn_live.sh`, `tests/test_no_raw_tmux.sh`.

## Cleanup

- Isolated tmux server killed; `/tmp/aitsv_1000` removed; `-L ait` socket
  re-verified empty.
- Pre-lift git worktree `/tmp/aitsv_prelift` removed.
- Harness scripts and ANSI captures remain only in the session scratchpad.
