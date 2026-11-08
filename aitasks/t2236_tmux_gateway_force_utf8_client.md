---
priority: medium
risk_code_health: medium
risk_goal_achievement: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [tmux, robustness]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus5_5
created_at: 2026-11-08 10:20
updated_at: 2026-11-08 12:38
---

## Origin

Found in aitasks_go t103 (`aitasks_go#t103`, the Go port of the tmux gateway).
The Go gateway now passes `tmux -u` on every invocation. This task brings the
Python and shell gateways (the source of truth that the Go port follows) in
step with it.

## Defect

tmux rewrites every non-printable or non-ASCII byte in command output to `_`
when the **client** process has no UTF-8 locale (LC_ALL / LC_CTYPE / LANG not
naming UTF-8). The affected bytes include:
- the TAB in `_SESSION_LIST_FORMAT = "#{session_name}\t#{@aitask_project_root}"`
  (`.aitask-scripts/lib/agent_launch_utils.py`). Every session name gains a
  trailing `_`, `list-panes -t =<name>_:` fails, and
  `discover_aitasks_sessions()` returns nothing;
- non-ASCII bytes in `#{pane_current_path}`, in the `@aitask_project_root`
  stamp, in `AITASKS_PROJECT_<s>` values and in window names
  (`/…/prój` comes back as `/…/pr_j`). So a printable-separator fix alone would
  not be enough.

Evidence was measured on tmux 3.8 against private sockets (tmux 3.4 and 3.6a
behave the same, per aitasks_go t100):

| client env | tab | `ó` | `\x1f` |
|---|---|---|---|
| none / `LANG=C` / `LC_ALL=C` | `_` | `_` | `_` |
| `LANG=C.UTF-8` / `LC_CTYPE=C.UTF-8` | kept | kept | kept |
| no locale + `tmux -u` | kept | kept | kept |
| control mode (`-C attach`), no locale | `_` | `_` | — |
| control mode with `-u`, no locale | kept | kept | — |

The client's locale decides this, not the server's.

## Python exposure (executed, not inferred)

`discover_aitasks_sessions()` was run against a private server with a session
in this repository:
- `LANG=C.UTF-8` gives the session;
- `LC_ALL=C` gives `[]`, so it is **affected**;
- with no locale vars at all it gives the session, but only because of PEP 538
  C-locale coercion: Python sets `LC_CTYPE=C.UTF-8` in its own environment and
  the tmux child inherits it.

So Python is affected under `LC_ALL=C` / `LC_ALL=POSIX` or a non-UTF-8 named
locale. Shell callers of `lib/tmux_exec.sh` get no coercion and are exposed
whenever the locale is unset.

## Suggested fix

- `lib/tmux_exec.py` `TmuxRunner._argv`: return `["tmux", "-u", *socket_args, *args]`.
  Check that every spawn path goes through it, including the control-mode
  attach and `new_session_argv` / the persistent new-session ladder.
- `lib/tmux_exec.sh`: add `-u` to the gateway's argv in the same way.
- Prefer `-u` over forcing `LC_CTYPE`. It is a client flag, so it never leaks
  into the environment of panes that `new-session` / `new-window` create, and
  it does not depend on a `C.UTF-8` locale being installed (macOS has none).
- Update `aidocs/framework/tmux_gateway.md` with the rule.
- Audit tests that substitute the tmux binary or assert the exact argv; they
  will now see `-u` first.
- Add a regression test: discovery on a private server with
  `LC_ALL=C` in the runner env, including a session whose pane cwd and stamp
  hold a non-ASCII path.

## Reference

The Go change is `goengines/tmux/exec.go` (`utf8Flag`) and `goengines/tmux/doc.go` in aitasks_go,
commit tagged `(t103)`.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-11-08T10:38:42Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-11-08T12:54:50Z status=pass attempt=1 type=human
