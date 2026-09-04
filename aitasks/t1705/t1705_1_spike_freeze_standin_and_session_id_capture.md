---
priority: high
effort: medium
depends: []
issue_type: test
status: Ready
labels: [tmux, tmux_destructive, codeagent, claudecode, codexcli, session_persistence, test_infrastructure]
gates: [risk_evaluated]
anchor: 1705
created_at: 2026-09-04 16:01
updated_at: 2026-09-04 16:01
---

## Step 0 — tmux preflight (run BEFORE anything else; blocking)

This task destructively manipulates tmux (`respawn-pane -k`, real `pane-died`
cleanup hooks, `kill-window`/`kill-server` on an isolated server). Its live
tests call `tests/lib/tmux_isolation.sh::require_clean_ait_server`, which
refuses to run from inside tmux or while the dedicated `-L ait` server has any
pane. Check this **first**, before planning or editing a file:

```bash
[ -z "${TMUX:-}" ] && echo "PREFLIGHT_OK: not inside tmux" || { echo "PREFLIGHT_BLOCKED: this session runs inside tmux ($TMUX)"; }
tmux -L ait list-panes -a -F '#{pane_id} #{window_name}' 2>/dev/null && echo "NOTE: the -L ait server has panes — stop 'ait ide' / close them before running the live suites" || echo "PREFLIGHT_OK: -L ait server idle"
```

- `PREFLIGHT_BLOCKED` → **do not implement.** Execute the workflow's **Task
  Abort Procedure** (`task-abort.md`) so the task reverts to `Ready` with its
  plan kept, and tell the user to re-pick from a terminal that is NOT inside
  tmux. Do not set `AIT_LIVE_TMUX_TEST_FORCE=1` — it is for a dedicated CI
  box only.
- `-L ait` server has panes → implementation may proceed, but the live suites
  will refuse until that server is stopped; say so in the Final
  Implementation Notes if verification had to wait.

## Context

First child of t1705 (frozen code agents). It is the **risk-mitigation spike**
`spike_frozen_standin_respawn` from the parent plan
(`aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md`, `## Risk`):
the parent's architecture rests on tmux and code-agent facts that nobody in this
repo has exercised, and every later child pins contracts on them. This child
proves or refutes them on an isolated tmux server **before** any
contract-consuming code exists. Its findings are appended to the parent plan
as a `## Spike findings (t1705_1) — PINNED` block and copied into the plans of
children 2–5; if a fact fails, the parent plan is amended *here*, not
discovered in child 4.

Why it matters: agents are launched with `remain-on-exit on` and a pane-scoped
`pane-died[N]` hook running `aitask_companion_cleanup.sh`, which kills the
companion minimonitor **and the primary pane** when no other real agent remains
in the window (`.aitask-scripts/aitask_companion_cleanup.sh:49-85`). Freezing
replaces the agent process in its own pane with `respawn-pane -k`; whether that
fires `pane-died` — and whether a stamp set *before* it is visible to the hook
— decides if freezing destroys the window. `respawn-pane` has **zero** call
sites in `.aitask-scripts/` today, and `.claude/hooks/guard_live_tmux.py`
denies a bare `tmux respawn-pane` from agent shells.

## What must be proven (each is a numbered test case in the script)

All on an isolated server via `tests/lib/tmux_isolation.sh` (`require_clean_ait_server` FIRST, then
(`require_isolated_tmux`, and `require_clean_ait_server` because the cleanup
hook is raw-tmux by design). Build the window with the real launch helpers
(`agent_launch_utils.launch_in_tmux`, `attach_companion_cleanup_hook`,
`maybe_spawn_minimonitor` with a stub `ait minimonitor` command on `PATH`) so
the hook wiring is the shipped one, not a replica.

1. **Stand-in respawn keeps the window.** Agent pane (a long-running fake
   agent script) + companion pane + the shipped `pane-died` hook. Stamp
   `@aitask_frozen=<id>` on the agent pane, then `respawn-pane -k -t <pane>
   '<stand-in cmd>'`. Assert: window still exists, companion pane alive,
   stand-in command running in the *same* pane id. Record **whether
   `pane-died` fired** (instrument the cleanup script via a wrapper on `PATH`
   or a `run-shell` echo hook at a higher index) and whether the stamp was
   visible when it ran. Negative control: the same sequence **without** the
   stamp-aware abstention must reproduce the window kill, or the test proves
   nothing.
2. **Pane user options survive `respawn-pane -k`**, and `#{pane_pid}`
   changes with it. Assert `@aitask_frozen` still reads back after the
   respawn; assert the new `#{pane_pid}` ≠ the old one.
3. **`env VAR=… <cmd>` prefix keeps `#{pane_pid}` equal to the launched
   process** (the unwrapped-launch contract of
   `agent_launch_utils.launch_in_tmux`, docstring `:1335-1345`) and the
   process sees the variables. Launch `env AITASK_RESTORE_RECORD=x sleep
   1000` via `respawn-pane`; assert `#{pane_pid}` is the `sleep`'s pid and
   `/proc/<pid>/environ` contains the variable.
4. **`run-shell -b` outlives a killed pane.** From pane A run `run-shell -b
   '<script that sleeps 2 then writes a marker file>'`, then `respawn-pane
   -k` pane A immediately. Assert the marker file appears.
5. **SessionStart hook payloads — Claude Code.** In a scratch project with a
   `.claude/settings.json` declaring `hooks.SessionStart` (matcher
   `startup|resume`) pointing at a capture script, launch `claude` inside a
   tmux pane and capture the JSON payload to
   `tests/data/session_hooks/claude_sessionstart.json` (redact the cwd to
   `/REDACTED`). Assert it carries `session_id`, `transcript_path`, `cwd`, and
   that `$TMUX_PANE` and `AITASK_AGENT_STRING` (exported by
   `aitask_codeagent.sh:611`) are visible to the hook process. Then relaunch
   with `claude --resume <session_id>` in a **respawned** pane and assert the
   hook fires again with `source: resume` and the same session id.
6. **SessionStart hook payloads — Codex.** Same with `.codex/config.toml`
   `[hooks]` (or `.codex/hooks.json` — try both; record which the installed
   codex honours and whether the project layer must be trusted). Capture to
   `tests/data/session_hooks/codex_sessionstart.json`. Then `codex resume
   <session_id>` in a respawned pane. **If either the hook or `resume` does
   not work, that is a finding, not a failure**: record it, and the parent
   plan's fallback (codex = re-pick only) becomes the pinned rule.
7. **Live-tmux guard.** Assert that the shipped gateway path
   (`TmuxClient.run(["respawn-pane", ...])` with socket args) is *not* what
   `guard_live_tmux.py` denies — i.e. the guard only blocks a bare `tmux
   respawn-pane` without `-L`/`-S`. Extend
   `tests/test_guard_live_tmux.sh` if a socketed respawn is currently denied.

Cases 5–6 need the real binaries and a logged-in account; guard them with
`command -v claude` / `codex` and an `AITASKS_SPIKE_REAL_AGENTS=1` opt-in so
the script still runs its tmux cases in CI-like environments.

## Key files

- **New** `tests/test_frozen_standin_spike.sh` — the probe, kept permanently
  as the live acceptance control for child 4.
- **New** `tests/data/session_hooks/{claude,codex}_sessionstart.json` — fixture
  payloads consumed by child 3's unit tests.
- **New** `tests/lib/fake_agent.sh` (a long-running "agent" that honours
  `--resume <id>` / `resume <id>` by printing the id and sleeping) — reused by
  children 5 and 8.
- **Edit** `aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md` —
  append `## Spike findings (t1705_1) — PINNED`.
- Possibly `tests/test_guard_live_tmux.sh` (case 7).

## Reference patterns

- `tests/lib/tmux_isolation.sh` — `require_isolated_tmux`, `require_clean_ait_server`.
- `tests/test_kill_agent_pane_smart.sh` — live fixture that builds an
  agent+companion window with the real hook (note t1699 is reordering it;
  read its task file before copying the fixture).
- `tests/test_shadow_capture.sh` — live-tmux test structure, `assert_*` helpers.
- `.aitask-scripts/lib/agent_launch_utils.py:1536-1599`
  (`attach_companion_cleanup_hook`), `:1326-1407` (`launch_in_tmux`).
- `.aitask-scripts/lib/tmux_exec.py` — `TmuxClient.run/spawn`; never call
  `tmux` directly from framework code (tests are not scanned by
  `tests/test_no_raw_tmux.sh`, but use `ait_tmux` from
  `.aitask-scripts/lib/tmux_exec.sh` anyway so socket args are right).
- `aidocs/framework/tui_conventions.md` §"Tmux-stress tasks" and §"Ad-hoc
  probes: TMUX_TMPDIR is not isolation".

## Deliverable: the findings block

Append to the parent plan (and the workflow will copy into children 2–5):

```
## Spike findings (t1705_1) — PINNED
- pane-died on respawn-pane -k: fires | does not fire; stamp visible to hook: yes | no
- pane options survive respawn: yes | no
- env prefix keeps pane_pid = agent pid: yes | no
- run-shell -b survives caller pane kill: yes | no
- claude SessionStart: fields <list>; fires on --resume: yes | no
- codex hooks: config.toml [hooks] | hooks.json | unsupported; codex resume: works | fails (→ codex = re-pick only)
- guard_live_tmux: socketed respawn allowed | denied (fixed in this child)
```

## Verification

```bash
bash tests/test_frozen_standin_spike.sh                       # from a shell OUTSIDE the -L ait server
AITASKS_SPIKE_REAL_AGENTS=1 bash tests/test_frozen_standin_spike.sh   # with real claude/codex
bash tests/test_guard_live_tmux.sh
bash tests/test_no_raw_tmux.sh
grep -n 'Spike findings' aiplans/p1705_frozen_codeagents_session_store_and_viewer_tui.md
```

**Tmux-stress: implement and verify from a shell that is NOT inside the
user's `-L ait` tmux server** (`aidocs/framework/tui_conventions.md` §"Tmux-stress
tasks"). Never `kill-server` from an agent pane — `$TMUX` beats `TMUX_TMPDIR`.
