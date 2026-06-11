---
Task: t973_manual_verification_dedicated_socket.md
Worktree: (current directory — profile 'fast', no worktree)
Branch: main
Base branch: main
---

# Auto-Verification Execution Log: t973 — dedicated tmux socket (t953 mitigation)

Autonomous auto-verification of the t953 risk-mitigation checklist on the live
box (Arch + Hyprland, systemd user session). Strategy: autonomous — each item's
approach was chosen on the fly and executed against real tmux servers, with all
scratch state cleaned up at the end. All 7 items reached **pass**.

## Execution Log

### Item 1 — ait ide lands on `-L ait` under session.slice
- Item text: `ait ide` from a clean shell creates the session on the dedicated socket; `tmux -L ait ls` shows it and the server runs under session.slice (not app.slice).
- Approach: CLI invocation (real `ait ide`, non-TTY so the final interactive `attach` fails after the session is already spawned) + systemd inspection.
- Action run: `./ait ide --session aitverify973`; then `tmux -L ait ls`, `systemctl --user show ait-tmux-aitasks-*.service -p Slice`, `cat /proc/<pid>/cgroup`, `systemd-cgls`.
- Output (trimmed): session `aitasks` created on `-L ait`; unit `ait-tmux-aitasks-4043619-25041.service` `Slice=session.slice`, `ActiveState=active`; `/proc/<pid>/cgroup` → `…/session.slice/ait-tmux-aitasks-…service`; systemd-cgls shows the unit nested under session.slice. (Note: `spawn_session_detached` resolves the project's configured session name internally, so the `--session` override only changes the attach target — a pre-existing quirk unrelated to t953.)
- Verdict: pass

### Item 2 — user's default tmux server untouched
- Item text: the user's personal default tmux server (`tmux ls`) is untouched by ait operations.
- Approach: CLI invocation — compare `tmux ls` before/after ait operations.
- Action run: `tmux ls` before and after the item-1 `ait ide` run.
- Output (trimmed): default server continued to show only the pre-existing `aitasks_go` session; ait spawned its server solely on the `-L ait` socket.
- Verdict: pass

### Item 3 — legacy-session migration prompt (y attaches / n spawns fresh)
- Item text: with a same-name session alive on the default socket and none on the ait socket, `ait ide` shows the legacy-session prompt; `y` attaches to the legacy session, `n` creates a fresh session on the dedicated socket with the hint printed.
- Approach: TUI/TTY interaction — drove `ait ide` through a pseudo-tty via `script(1)`; set up a legacy `aitasks` session on the default server with the ait socket empty.
- Action run: `printf 'y\n' | timeout 4 script -qec './ait ide' /dev/null` and `printf 'n\n' | … script …`; checked `tmux -L ait ls` after each.
- Output (trimmed): prompt fired (`Session 'aitasks' exists on the legacy default tmux server (pre-dedicated-socket). Attach to it instead? [y/N]`). `y` → attached to the legacy default-server session (rendered monitor showed `(attached: aitasks)` with `1:aitasks 2:monitor`); ait socket stayed empty. `n` → printed `Creating a fresh session on the dedicated socket.` + `AITASKS_TMUX_SOCKET=default ait ide` hint, then spawned a fresh session on `-L ait`.
- Verdict: pass

### Item 4 — `AITASKS_TMUX_SOCKET=default` opt-out reaches legacy server
- Item text: `AITASKS_TMUX_SOCKET=default ait ide` reaches the legacy default-socket session (explicit opt-out works end-to-end).
- Approach: CLI invocation with the env override; verify it targets the default server and creates nothing on the ait socket.
- Action run: `AITASKS_TMUX_SOCKET=default ./ait ide` (non-TTY); then `tmux -L ait ls` and `tmux -L default list-windows -t =aitasks`.
- Output (trimmed): reached the legacy `aitasks` session on the default server (added its `monitor` window; only the interactive attach failed, on non-TTY); the ait socket remained empty.
- Verdict: pass

### Item 5 — refuse inside a foreign (non-ait) tmux server
- Item text: inside a personal (non-ait) tmux server, `ait ide` refuses with the socket-identity warning instead of failing cryptically or mutating the wrong server.
- Approach: TUI interaction — ran `ait ide` inside a real foreign server (`-L personal`), synchronized via `tmux wait-for`.
- Action run: `tmux -L personal new-session -d … "./ait ide > out; …"`; read captured output.
- Output (trimmed): `Warning: You are inside a tmux server on socket 'personal', but ait sessions live on the dedicated socket '-L ait'. Detach … or run AITASKS_TMUX_SOCKET=personal ait ide …`; `EXIT=1`; the foreign server was not mutated.
- Verdict: pass

### Item 6 — `j` switcher cross-session teleport on the dedicated server (multi-project)
- Item text: the `j` TUI switcher cross-session teleport works between project sessions on the dedicated server (multi-project case).
- Approach: TUI interaction — stood up two project sessions on `-L ait` (`aitasks`, `aitasks_go`), background-attached a pty client to `aitasks`, drove the live monitor + `j` switcher via `tmux send-keys`, and verified the teleport via `list-clients`. Supporting: `tests/test_tui_switcher_multi_session.sh` 52/52.
- Action run: `send-keys j` → switcher overlay; `send-keys Right` (select aitasks_go); `send-keys Enter`; `tmux -L ait list-clients`.
- Output (trimmed): overlay listed `▶ aitasks  aitasks_go  aitasks_mob`; after Enter the attached client `/dev/pts/11` moved `aitasks → aitasks_go` (gateway-routed `switch-client` on the `-L ait` server).
- Verdict: pass

### Item 7 — monitor rename dialog + codebrowser focus handoff post gateway-routing
- Item text: ait monitor session-rename dialog and codebrowser focus handoff still work post gateway-routing (holdout migration smoke).
- Approach: exercised the exact gateway code paths the two TUIs use, against the live `-L ait` server, via the real `TmuxClient` (env unset → `socket_args=['-L','ait']`). Supporting: `tests/test_monitor_rename_window_target.sh` 3/3.
- Action run: `TmuxClient.run(["rename-session","-t",session_target(cur),new])` on a scratch session; `set/show/unset AITASK_CODEBROWSER_FOCUS` round-trip.
- Output (trimmed): rename rc=0 (session renamed on `-L ait`); focus env set rc=0, read back `AITASK_CODEBROWSER_FOCUS=task:42:line:7`, unset → show rc=1 (cleared).
- Verdict: pass

## Cleanup
- `tmux -L ait kill-server` — removed all scratch sessions on the dedicated socket (`aitasks`, `aitasks_go`, the item-7 scratch session) and terminated the background pty client.
- `tmux kill-session -t '=aitasks'` on the default server — removed the legacy `aitasks` session created for items 3/4 (the user's pre-existing `aitasks_go` left untouched).
- `tmux -L personal kill-server` — removed the foreign server created for item 5.
- No `ait-tmux-*` systemd units left loaded after cleanup.
- Final state: `-L ait` has no server; default server shows only the user's original `aitasks_go`.
