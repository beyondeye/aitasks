---
priority: high
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [codex, tmux, codeagent, opencode, monitor]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/fable5_2
created_at: 2026-10-18 12:33
updated_at: 2026-11-20 08:46
---

## Problem

Inside the ait tmux server, Codex and OpenCode draw part of their UI in colours that cannot be read:

- **Codex:** the "Working" shimmer is drawn as `38;2;0;0;0` (pure black) on a dark `48;2;30;30;30` background. The composer and prompt backgrounds are also the fallback `30;30;30` instead of a blend of the terminal's colours.
- **OpenCode** (with `"theme": "system"`): normal text is drawn as `38;2;0;0;0` and panels as `48;2;0;0;0`, on whatever the real terminal background is. On a dark terminal the text is invisible.

Both agents ask the terminal for its default foreground and background (OSC 10 / OSC 11) and build colours from the answer. Inside tmux, tmux answers. In the affected sessions it answers black for both.

## Root cause (re-verified 2026-11-18, tmux 3.8)

It is not specific to either agent. tmux takes a pane's default colours from the **first client attached to the pane's session**. A control-mode client (`tmux -C attach -t =<session> -f no-output,ignore-size`, which is what monitor and minimonitor run) reports colour 0, i.e. black. When it attached before the real terminal, every pane in that session gets black/black.

In the tmux source (`window.c`, `window_pane_get_fg` / `window_pane_get_bg`) the loop over clients skips only unattached clients and clients whose `tty.fg` is `-1`. It does not skip control clients. tmux `master` has the same code today, so an upgrade does not fix it.

Measured on a private server (`-L t2051r`, `-f /dev/null`) with a pty-driven fake terminal that answers OSC 10/11 with `#ccddee` / `#223344`:

| clients attached to the pane's session | OSC 10 / 11 reply |
|---|---|
| none | no reply |
| control client only | `rgb:0000/0000/0000` for both |
| control client first, then the real client | black for both — **the bug** |
| same, after the control client leaves | real colours |
| real client first, then the control client | real colours |
| real client in the session, control client (attached first) in **another** session | real colours |
| real client whose terminal never answers OSC 10/11 | no reply |
| same, plus a control client attached later | black for both |
| real client attached, then detached | no reply |

OSC 4 palette queries get no reply from tmux in any of these cases.

Real agents, same private server with the live server's options (`allow-passthrough on`, `*:RGB`), start screen only, no turn spent:

| agent | control client first | real client first |
|---|---|---|
| OpenCode 1.18.34, `theme: system` | text `0;0;0`, panels `0;0;0` / `25;25;25` | text `204;221;238`, panels `48;73;97` / `69;82;95` |
| Codex 0.170.0 | text `117;117;117`, backgrounds `30;30;30` | text `204;221;238`, backgrounds `60;75;90` |

OpenCode gets its 16-colour palette from the outer terminal through tmux passthrough (17 queries reached the fake terminal), so its accent colours are right. Only the default fg/bg come from tmux, and those are the black ones. Without `allow-passthrough` OpenCode gets no palette and silently uses its built-in `opencode` theme, which hides the bug.

Live server at the time of the check: session `aitasks` had a control client created before the real client, and its Codex pane showed `48;2;30;30;30`. A Codex pane in a session with no control client showed `48;2;53;54;64`, a blend of the real colours.

## Constraint

The solution must NOT be tied to a specific outer terminal (no Alacritty/Ghostty/kitty-specific logic), and it must not be specific to one agent.

## Approach

Fix the cause once, for every agent: **attach the monitor/minimonitor control clients to a dedicated helper session (`_ait_control`) instead of the project session.** tmux then answers from the real terminal client. No probing of the outer terminal, no fallback colours and no light/dark handling are needed.

The detailed design is the unapproved draft in `aiplans/p2051_codex_pane_tmux_default_colors.md` (helper ownership marker, foreign-collision fallback, detection of project deletion while connected, explicit targets for control-routed commands, live tests). The user chose this option during the first planning round. Re-verify the draft before approving it:

- The mechanism still works: two control clients joined one `_ait_control` helper, a pane in the project session answered with the real colours, and the helper was destroyed when the last control client left.
- The draft's line numbers are stale. The two implicit-target calls are now at `monitor_app.py:1901` (`_read_attached_session`) and `monitor_shared.py:1368` (`_run_frozen_detached`). The attach argv is still built in `monitor_core.py::_attach_argv`.
- The control client now ends itself when tmux moves it to another session (t2245). Check how that interacts with a client that lives in the helper session.
- The draft names only Codex. Extend its verification and acceptance to OpenCode.
- t2161 (control client quoting) is Ready and touches the same client. t2038 (Go monitor status server) is Postponed and also attaches a control client per session. Whichever lands later must keep the helper-session attach.

### Alternatives measured

- **Per-pane style** (`select-pane -P 'fg=…,bg=…'` on the agent pane): works in every client order, and also with no real client attached. It needs colours from somewhere (our own probe of the outer terminal plus a fallback), it paints the pane background, and it must be applied per agent pane. Setting only `fg` leaves `bg` black. `window-style` behaves the same but only for panes in that window.
- **Control client reports the colours** (`refresh-client -r`): tmux has a per-pane report path, but one attempt on 3.8 did not change the reply. Not pursued. Treat as untested rather than ruled out.

## `ait ide` integration (measured 2026-11-18)

`ait ide` creates the `monitor` window and only then runs `exec tmux attach`, so the control client always attaches before the real terminal. `ait ide` is therefore the normal way to hit the bug. With the helper session it needs no change for colours: in that same order a pane in the project session answered with the real colours.

**Gap the draft plan does not cover: `detach-on-destroy off`.** With that option (set in the user's `tmux.conf`; tmux's default is `on`), destroying the project session while a real terminal is attached moves that terminal **into `_ait_control`**, even when another project session exists. The user is left on the helper's `sleep` pane, and the helper never goes away because it now has an attached client. With `detach-on-destroy on` the terminal detaches and the helper is destroyed with its last control client, as designed.

The design must handle this, and a live test must pin it for both settings. Candidates to measure: set `detach-on-destroy` on the project session so its clients never fall into the helper, or have the helper move a non-control client that lands in it to another session (or detach it) through a session hook.

Also for planning: the helper shows up in tmux's own session surfaces (`prefix s`, `prefix (` / `)`), which cannot be filtered.

## Scope decisions (user, 2026-11-19)

- **This is a transport-layer fix with no UI.** The control connections belong to the shared control-client code in `monitor/monitor_core.py`, which every TUI that opens one goes through. The fix lives there, so current and future TUIs get it without knowing about it.
- **It is not integrated into sitrep.** The sitrep window is a window inside the project session, and the bug is about which client attached to that session first. From inside the project session sitrep could only use the per-pane style alternative. Keeping the two apart also keeps one responsibility each.
- **The helper pane stays a plain `sleep`**, not a Textual "lobby" TUI. Normally nobody sees that pane, so a TUI there would sit idle and add a Python process per tmux server.
- **The `detach-on-destroy off` gap is handled with a plain bounce** (session option or hook, to be measured), not a TUI.
- **Out of scope, noted on t2211:** once sitrep is the always-open backbone window of each project session, the bounce could land the terminal on another live project's sitrep window. That depends on t2211 and is not part of this task.

## Open questions for planning

- **No real client attached when the agent starts** (unattended launch, or a session nobody is viewing): tmux sends no reply at all. The helper session does not change that. Codex then appears to use its own fallback (`30;30;30` backgrounds). Measure what both agents draw in that case and whether either re-queries after a client attaches. If the result is unreadable, the per-pane style is the candidate for that case only.
- **Agents already running** keep the black colours they read at startup unless they re-query. Decide whether the fix needs to say "restart the agent" or can refresh them.

## Acceptance

- With a monitor or minimonitor running and attached before the real terminal, an OSC 10/11 probe in a pane of the project session returns the real terminal's colours, not black.
- Codex launched by the framework in that session: the "Working" shimmer is legible. Capture with `tmux capture-pane -e -p` during a turn and confirm the RGB is not `0;0;0`.
- OpenCode launched by the framework in that session with `theme: system`: normal text is not `38;2;0;0;0` and panels are not `48;2;0;0;0`.
- Negative control in the same fixture: the old attach (control client in the project session, attached first) gives black.
- Monitor and minimonitor still work: their commands still act on the project session, and they still notice when the project session is destroyed.
- The no-real-client case is measured for both agents and either shown readable or handed to a follow-up task.

## Notes

- Probe: write `ESC ] 10 ; ? ESC \` and `ESC ] 11 ; ? ESC \` to the pane tty in raw mode and read the replies, with `ESC [ c` as an end marker (tmux always answers it). It needs a real tty, so run it in a tmux window, not through a tool shell.
- Fake terminal: `pty.fork()` running `tmux -L <sock> attach -t =<session>` with `TERM=xterm-256color`, and a reader that answers OSC 10/11 (and OSC 4 for OpenCode) queries. The draft plan moves this into `tests/lib/`.
- Use a private socket and drop `TMUX` / `TMUX_PANE` from the environment. A bare `tmux` in an agent pane follows `$TMUX` to the live server.
- For OpenCode the fixture must set `allow-passthrough on`, or the `system` theme is never used and the test proves nothing.
- Real-agent colour check: launch the agent in a window of the fixture session, wait about 8 s, then count `38;2;R;G;B` and `48;2;R;G;B` in `capture-pane -e -p`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-20T06:46:12Z status=pass attempt=1 type=human
