---
priority: medium
effort: high
depends: []
issue_type: feature
status: Ready
labels: [tmux, aitask_monitor, tui_switcher]
children_to_implement: [t634_2, t634_3, t634_4]
created_at: 2026-04-23 20:19
updated_at: 2026-04-24 10:21
---

## Context

Follow-up to t632 (Force exact-match tmux session targeting). t632 scoped everything to a single tmux session per project — the correct default. This task adds an **opt-in** layer on top: let the user observe and navigate across multiple aitasks projects from a single terminal emulator when they want to, without giving up the single-session-per-project invariant.

Two concrete use cases:

1. **Multi-session monitor (`ait monitor`)** — when working on several aitasks projects in parallel, see every running code agent (across all projects) in one pane list. Clicking/focusing an agent from project B while the monitor lives in project A teleports the tmux client to B's pane.
2. **Two-level TUI switcher** — when multiple aitasks sessions are running, the TUI switcher overlay grows an outer "session" picker so the user can jump to another project's board / codebrowser / brainstorm.

Both features are opt-in via config; defaults keep today's single-session behavior.

## Feasibility (summary)

Checked with claude during t632 review:

- tmux state is globally readable across sessions on one server. `list-panes -a`, `capture-pane -t %<id>`, `send-keys -t %<id>` all work regardless of attach state. Pane IDs are globally unique.
- A tmux *client* attaches to exactly one session at a time. You cannot render two sessions side-by-side in one pane. You can **teleport** the client with `switch-client -t =<sess>`, or **link** a window into two sessions with `link-window`.
- For the monitor, teleport is the right model — one client, jumps to target on focus.
- For the switcher, teleport is also the right model — pick a session in the outer row, pick a window in the inner row, Enter = switch-client + select-window.

## Design invariants to preserve

- **Single tmux session per project** stays the rule for `ait ide` and everything else. Multi-session is an *additive view*, not a multi-attach mode.
- **Shortcut keys (`n`, `b`, `m`, `x` in switcher) stay bound to the current session.** Spawning a window in a browsed session would implicitly teleport the user. List-item Enter = teleport + navigate; shortcut = current-session action.
- **Default off.** `tmux.monitor.multi_session` and `tmux.switcher.multi_session` default `false`. Single-session users see no UI change.

## Known tmux gotchas

1. **Socket scoping** — multi-session only works when all projects use the same tmux server (same socket). If a user launched one project with `-L foo` and another without, they can't see each other. Document; don't try to merge across sockets.
2. **New-empty sessions look non-aitasks** — a fresh tmux session with just a shell has no TUI windows and no aitasks metadata yet. Detection must accept both window-name heuristics AND session-name matches against registered project configs.
3. **`rename-session` prompt in monitor** — today the monitor pops the SessionRenameDialog when the attached session name doesn't match `tmux.default_session`. In multi-session mode this check becomes "does the monitor live in any aitasks session?" — relax or disable.
4. **Focus-request env var plumbing** — the current minimonitor → monitor focus handoff writes `AITASK_MONITOR_FOCUS_WINDOW` on one session's env. Cross-session focus should bypass that dance and call `switch-client`/`select-window`/`select-pane` directly on the target pane id (pane ids are globally unique).
5. **Priority-binding + `App.query_one` gotcha** (see CLAUDE.md) — any new session-row bindings in the switcher must use `self.screen.query_one(...)` guards and raise `SkipAction` on miss, otherwise they consume keys meant for pushed screens.
6. **`link-window`** — tempting for side-by-side views but risky: kill-window on one session removes it from both unless `unlink-window` is called first. Skip it unless a concrete use case demands it.
7. **`TMUX_TMPDIR` in tests** — use an isolated server in integration tests (see the pattern in `tests/test_tmux_exact_session_targeting.sh`) to avoid polluting the developer's real tmux state.

## Children

- **t634_1** (primitives) — shared `discover_aitasks_sessions()` + cross-session focus helpers. Blocks _2 and _3. Small, foundational, testable.
- **t634_2** (monitor) — `TmuxMonitor` + `monitor_app.py` gain a multi-session mode. Depends on _1.
- **t634_3** (switcher) — `lib/tui_switcher.py` gains a two-level session+window UI. Depends on _1; can be implemented in parallel with _2.

An aggregate manual-verification sibling should be created during t634's own planning phase (standard framework flow — `planning.md` Step 6 child-task checkpoint offers it via `aitask_create_manual_verification.sh`). Manual verification is the primary validation for both the monitor UX and the switcher UX; end-to-end TUI behavior is difficult to cover automatically.

## Non-goals

- Showing two sessions visually side-by-side in one pane. Not feasible with stock tmux; would require a compositor or `link-window` acrobatics that break more than they help.
- Implicit cross-socket merging. Out of scope.
- Replacing the current single-session defaults. This is additive.

## References

- Feasibility discussion: see the post-plan Q&A on t632 (plan `aiplans/archived/p632_*.md`).
- Pane ID uniqueness, `switch-client`, target syntax: `tmux(1)` "TARGETS" and "COMMANDS".
- Existing focus handoff pattern: `AITASK_MONITOR_FOCUS_WINDOW` env var in `monitor/monitor_app.py` / `monitor/minimonitor_app.py`.

## Verification

Driven by the manual-verification sibling added during t634's planning phase. End-to-end scenarios include two aitasks projects started side-by-side, multi-session mode toggled on, cross-session focus from the monitor, and two-level selection from the switcher. See each child task's own Verification section for unit-level checks.
