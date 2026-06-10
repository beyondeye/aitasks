---
Task: t952_3_absorb_controlmode_repoint_monitor.md
Parent Task: aitasks/t952_centralize_tmux_invocations_shared_gateway.md
Sibling Tasks: aitasks/t952/t952_1_*.md, aitasks/t952/t952_2_*.md, aitasks/t952/t952_4_*.md, aitasks/t952/t952_5_*.md
Worktree: aiwork/t952_3_absorb_controlmode_repoint_monitor
Branch: aitask/t952_3_absorb_controlmode_repoint_monitor
Base branch: main
---

# t952_3 — Absorb control-mode + re-point monitor (perf-sensitive)

Stage 3 — see parent plan `aiplans/p952_centralize_tmux_invocations_shared_gateway.md`.
Depends on **t952_1**. **Behavior-preserving.**

## ⚠️ t822_3 COORDINATION (re-verify at pick time)
This child edits `monitor/tmux_monitor.py` and `monitor/tmux_control.py` —
inside t822_3's `monitor_core` extraction blast radius. **Rebase after t822_3
lands, or coordinate the edits.** Check t822_3's status before starting; if it
has landed, re-anchor the line references below against the post-extraction
layout. Siblings t952_1 / t952_2 / t952_4 do not touch `monitor/`.

## Implementation steps

1. Add a session-bound control-mode dispatcher to `lib/tmux_exec.py` that owns
   "control-client when alive, subprocess fallback on `rc == -1`" — porting the
   logic from `monitor/tmux_monitor.py:255-285` **verbatim** (the fallback-on-`-1`
   branch is load-bearing).
2. Move `TmuxControlBackend` / `TmuxControlClient` ownership under the gateway so
   control-mode is reusable beyond monitor. Keep the backend **session-bound**
   (`TmuxControlBackend(session=...)`) — do NOT generalize to server-wide.
3. Re-point `TmuxMonitor.tmux_run` (~266) and `_tmux_async` (~255) to thin
   delegations onto the gateway dispatcher — signatures unchanged so all ~14
   monitor call sites are untouched.
4. Thread the gateway socket args (cached at construction, NOT per-call) into the
   `tmux -C attach` argv (`monitor/tmux_control.py:~98-99`), between `"tmux"`
   and `"-C"`.
5. The raw helpers `_run_tmux_subprocess` / `_run_tmux_async` either move into
   the gateway as its internal fallback primitives or remain as documented
   exceptions — whichever, ensure t952_5's allowlist covers the survivor.

## Risks
- Perf hot path — no per-call config reads.
- Preserve `(rc, stdout)` with `-1`-on-transport-failure exactly.

## Verification
- **Keystone:** `tests/test_tmux_run_parity.sh` (backend-on vs backend-off
  identical) — the behavior-preservation oracle.
- `tests/test_tmux_control.sh`, `tests/test_tmux_control_resilience.sh`.
- Assert the attach argv carries the socket flag when `AITASKS_TMUX_SOCKET` set.
- Run under `require_isolated_tmux`.

See **Step 9 (Post-Implementation)** for archival.
