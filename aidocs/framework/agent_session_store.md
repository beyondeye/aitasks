# The agent session store (framework session) — contributor notes

Contributor-only detail behind the framework session store. The public
architecture (file locations and modes, the single-writer guarantee, record
identity, the five states, operation leases, the session hook's recording
rules, verified / unverified restores, cleanup reasons and the override
variables) is on the website at
`website/content/docs/development/framework-session.md`; the user-facing idea
is `website/content/docs/concepts/framework-session.md`. Keep public facts
there and only implementation detail here.

## How the single-writer guarantee is implemented

`aitask_agent_sessions.sh` is the only writer. It holds a lock
(`registry_lock.sh`) around each read-modify-write of
`~/.config/aitasks/agent_sessions.json` and replaces the file atomically
(`os.replace` of a freshly written temp file). That atomic replace is why the
readers (the viewer, `ait monitor`, `ait minimonitor`) take no lock: every
write lands whole. `lib/agent_sessions.py` is the lock-free primitive the
wrapper drives; see its module docstring.

## Pane options and the order they are stamped

`@aitask_record` is stamped on the pane only after the record has been written,
so a pane never points at a record that does not exist yet. Two more pane
options, `@aitask_frozen` and `@aitask_standin_ready`, mark a frozen pane and a
frozen-agent viewer that has finished starting up in it. Together they let the
framework tell "the agent is still here" from "the viewer has taken over"
without trusting a process name. The public page names only `@aitask_record`.

## What an operation lease holds

A lease is a one-time nonce, the coordinator's own process id and the time it
was taken (`op_nonce`, `op_owner_pid`, `op_started_at`). Every command that
changes a leased record must present the matching nonce; that is how a
coordinator that lost a race is made to write nothing. `reconcile` takes a lease
over only when 60 seconds have passed since it was taken and that process id is
no longer alive (`_lease_stale`).

## How the session hook decides it is in the agent's own pane

The hook records only when the pane's process is one of its ancestors and
every process between them can be identified and none is the Codex app-server
daemon. The daemon case is the one this
check exists for: a hand-started Codex agent routed through the shared
app-server daemon would otherwise report the pane that started the daemon.

## How the session hook reads the CLI from a transcript path

For an agent started by hand, the hook infers the CLI from the shape of the
transcript path the agent reports: a Claude Code transcript lives under
`projects/`, a Codex one is a `rollout-…` file. The path counts only when it
names the very session being reported.

## Codex hook timing (measured)

Codex's interactive TUI fires the SessionStart hook only at a session's first
turn, not at launch. That is the measured behaviour of Codex 0.163.0; Codex
0.153.4 fired it only under `codex exec`. It is why a resumed Codex agent is
verified from the transcript its process holds open rather than by waiting for
the hook, and why a late hook report can upgrade an unverified restore.

The public pages state only the rule (the hook fires at the first turn). Keep
version numbers here, and re-measure when a Codex release changes the timing.

## How the open transcript is read

The coordinator learns which session's transcript a resumed Codex process
holds open from `/proc` on Linux and from `lsof` on macOS (the macOS probes,
`ps` / `lsof` / `sysctl(KERN_PROCARGS2)`, are described in the comment block
above `_ps_probe` in `lib/agent_sessions.py`). On any other platform the read
finds nothing, so the restore falls back to liveness and reports unverified.
The same read captures an older Codex agent's session at freeze time.

## Overrides and the test suite

`AITASKS_AGENT_SESSIONS_FILE` and `AITASKS_FROZEN_DIR` are what the test suite
uses to keep every test off the real `~/.config/aitasks/` state. The
end-to-end fixtures for frozen agents are `tests/lib/frozen_fixtures.sh` (see
`testing_conventions.md`).

## Related contributor docs

- Pane option names and who stamps or clears each one (`@aitask_record`,
  `@aitask_frozen`, `@aitask_standin_ready`): `tmux_gateway.md`, the pane
  option table.
- Frozen stand-in panes as a companion-pane case, and where the state machine,
  lease and reconcile table are specified: `tui_conventions.md`, "Frozen
  stand-in panes are a third companion-pane case".
- Adding or changing a session hook: `aitasks_extension_points.md`, "Adding a
  code-agent session hook".
