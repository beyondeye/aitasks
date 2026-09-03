---
priority: high
effort: low
depends: []
issue_type: chore
status: Ready
labels: [tmux, tmux_destructive, crash_recovery, claudecode, test_infrastructure]
created_at: 2026-09-03 12:12
updated_at: 2026-09-03 12:12
---

## Summary

Adds a `PreToolUse`/`Bash` guard that refuses a tmux command which does not name
the server it talks to, so an ad-hoc agent probe can no longer destroy the live
`tmux -L ait` server. Retroactive wrap — the work is already implemented.

## Why

On 2026-09-03 09:39:52, during t1699, an agent ran this probe from inside a live
`ait` pane to check a `list-panes` parsing hypothesis:

```bash
D=$(mktemp -d) && TMUX_TMPDIR=$D tmux new-session -d -s probe ... \
  && TMUX_TMPDIR=$D tmux kill-server
```

Two seconds later the user's `tmux -L ait` server was gone, taking ~30 panes
across three sessions — every running code agent, TUI and shell, including the
pane that issued the command.

`TMUX_TMPDIR` is not isolation inside a pane. tmux resolves its socket from
`$TMUX` when that is set and ignores `TMUX_TMPDIR` entirely, so both the
`new-session` and the `kill-server` addressed the live server. Verified
read-only:

```
$ TMUX_TMPDIR=/tmp/tmp.X tmux display-message -p '#{socket_path}'
/tmp/tmux-1000/ait                                   # the LIVE server
$ env -u TMUX TMUX_TMPDIR=/tmp/tmp.X tmux display-message -p '#{socket_path}'
error connecting to /tmp/tmp.X/tmux-1000/default     # correctly isolated
```

No framework code was at fault — `kill_agent_pane_smart` was not running. The
existing "Tmux-stress tasks" convention in `aidocs/framework/tui_conventions.md`
covered **test scripts** only; a one-off probe typed into a shell fell straight
through it. This task closes that gap in source rather than in convention.

## What it does

`.claude/hooks/guard_live_tmux.py` denies a Bash command when either holds:

1. A tmux invocation uses a destructive verb (`kill-*`, `respawn-*`,
   `unlink-window`, `source-file`) with no `-L`/`-S`.
2. A tmux invocation carries a `TMUX_TMPDIR=` prefix but no `-L`/`-S` and does
   not strip `$TMUX` — the exact incident shape, denied for any verb including
   read-only ones, because the redirect is silently ignored.

Socketed calls (`tmux -L throwaway kill-server`, `tmux -L ait list-panes`) pass
untouched. Parse failures fail closed. The denial message names the fix and
points at `tests/lib/tmux_isolation.sh`.

## Scope boundary

The hook binds Claude Code Bash calls only. The rule it enforces is written up
in `aidocs/framework/tui_conventions.md` and is what binds Codex CLI, OpenCode
and any other agent — consider porting an equivalent guard if those gain a
comparable pre-execution hook.
