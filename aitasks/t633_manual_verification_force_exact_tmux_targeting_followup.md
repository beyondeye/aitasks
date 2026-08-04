---
priority: medium
effort: medium
depends: [632]
issue_type: manual_verification
status: Ready
labels: [verification, manual, tmux_destructive]
verifies: [632]
created_at: 2026-04-23 18:08
updated_at: 2026-08-04 17:25
boardcol: manual_verifications
boardidx: 60
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t632

## Socket setup (do this first)

`ait ide` picks its tmux server from `AITASKS_TMUX_SOCKET` via
`ait_tmux_socket_name()` (unset → the dedicated `ait` socket, t953; non-empty →
that socket; set-but-empty → no flag, follows `$TMUX`). Every tmux command in the
checklist must hit the **same** server, so derive it from the same gateway
instead of hard-coding a flag. In the shell you will run the checklist from
(bash — start one with `bash` if your shell is something else):

```bash
cd <project A root>
source .aitask-scripts/lib/tmux_exec.sh
printf 'socket=[%s] flags=[%s] TMUX=[%s]\n' \
  "$(ait_tmux_socket_name)" "$(ait_tmux_socket_args | tr '\n' ' ')" "${TMUX:-not inside tmux}"
```

**Read that line before running anything destructive:**

- `socket=[ait]` (or another name) → good: every `ait_tmux` command is pinned to
  that named server.
- `socket=[]` with `flags=[]` → **STOP.** `AITASKS_TMUX_SOCKET` is set but empty
  (the legacy test-harness escape hatch), so tmux takes no socket flag and
  follows `$TMUX` — inside a pane that is *the server this pane lives on*, which
  may be your personal one. The kill step below would then destroy the session
  you are running the checklist from. Fix it before continuing:
  `unset AITASKS_TMUX_SOCKET` (recommended — restores the dedicated `ait`
  socket) or set it to a socket name, then re-source.
- `TMUX=[…]` non-empty → you are inside a tmux pane. Run the destructive steps
  from a plain terminal instead; if that pane belongs to the target server, the
  kill takes your own shell with it mid-checklist. (`$TMUX`'s first field is the
  socket path — compare it against the socket named above.)

Then use `ait_tmux <verb>` wherever the checklist says so, and re-source in any
new shell. Do **not** swap in a plain `tmux` invocation: without the resolved
socket flags it targets your personal default server, which is neither the
server `ait ide` uses nor the one these steps assert about.

When no server exists on the resolved socket, `ait_tmux` exits 1 with
`error connecting to …` / `no server running on …`. In this checklist that
message means "no ait sessions" — a clean slate, **not** a failure.

## Verification Checklist

- [ ] **Preflight for the destructive step:** complete **Socket setup** above first — its `socket=…` line must name a real socket (never empty) and you must be running from a shell outside the target server. Then run `ait_tmux list-sessions` and read every line: ONE ait server is shared by ALL aitasks projects, so this lists other projects' sessions and any code agents running in them. Pass this item only once you have confirmed that losing every session listed is acceptable; if it reports no server, you are already at a clean slate.
- [ ] `ait_tmux kill-server` to clear all ait sessions — run it ONLY after the preflight above confirmed nothing you still need is running, because it terminates every session on the shared ait server, not just this project's. If the preflight found no server, mark this item Skip; a no-server message here means the same thing and is not a failure.
- [ ] cd to project A and run `ait ide` — confirm it starts session A with a `monitor` window
- [ ] Detach (Ctrl-b d)
- [ ] cd to project B and run `ait ide` — must start a NEW session B, not attach to A
- [ ] `ait_tmux list-sessions` should show both sessions (a plain `tmux` invocation would read your personal default server and show neither)
- [ ] Switch TUIs in each project (board, codebrowser, settings, monitor) and confirm windows stay in each project's own session — no cross-leakage
- [ ] Start a brainstorm in project A; in project B the brainstorm switch must NOT focus A's brainstorm window
- [ ] Verify minimonitor companion panes spawn in the correct project's session (e.g. from board, launch a code agent in project B and check the companion pane is in session B)
