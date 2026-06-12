# Auto-Verification Execution Log — t979

**Task:** `aitasks/t979_manual_verification_pin_minimonitor_pane_width_on_resize_fol.md`
**Verifies:** t978 (Pin minimonitor companion pane width on resize)
**Strategy:** autonomous (whole-checklist), 2026-06-12
**Mode:** real PTY-attached tmux client on an isolated socket (`-L auto979`),
driving genuine terminal SIGWINCH → Textual `on_resize`. No user-owned tmux
sessions or repo files (other than this checklist) were touched.

## Summary

| Item | Verdict | Notes |
|------|---------|-------|
| 1 — spawn companion pane at ~40 cols | **PASS** | pane spawns at 40 cols; minimonitor mounts and renders |
| 2 — detach → resize wider → reattach snaps to 40 | **FAIL → t981** | growth re-pin lost (the reported bug recurs) |
| 3 — live resize stays pinned to 40 | FAIL on growth (same root cause as t981) | shrink re-pins fine; widening does not |
| 4 — `width: 50` config pins to 50 | config plumbing correct; pin-on-growth inherits t981 | not independently passable |
| 5 — verify `minimonitor_app.py` e2e in tmux | covered by items 1–4 | e2e performed; results above |

## Execution Log

### Item 1 — spawn at ~40 cols  (PASS)
- Approach: TUI interaction. Isolated tmux server; `split-window -h -l 40`
  running `ait minimonitor` (mimics `agent_launch_utils.maybe_spawn_minimonitor`).
- Output: companion pane reports `40x50`, `pane_current_command=python`,
  minimonitor UI rendered ("── this agent ── / agent-foo").
- Verdict: pass.

### Item 2 — detach → resize much wider → reattach  (FAIL)
- Approach: PTY-attached real client; widen window 200→400 (pane drifts 40→140);
  reattach at 500 (pane 160). Re-pin issued but **not applied** on growth.
- Verdict: fail. Follow-up bug **t981** created.

### Items 3–5 — shared root cause
Instrumented the app (non-invasive monkeypatch wrapping `on_resize` /
`_maybe_pin_width`, logic unchanged): `on_resize` fires with the correct drifted
`self.size.width` and **does** issue `resize-pane -x 40` (`action=RESIZE->40`),
yet the pane stays wide on a window *growth*. Transport isolation:

| `resize-pane -x 40` issued via … (window just grown, client @400) | result |
|---|---|
| control client (`tmux -C attach`), immediately in `on_resize` | **stays 140 (FAIL)** |
| subprocess `tmux resize-pane`, immediately | → 40 (works) |
| control client, after ~1.5 s settle | → 40 (works) |
| control client on a *shrink* (400→300) | → 40 (works) |

Root cause: an immediate `resize-pane` sent through a tmux **control-mode client**
during the window-growth reflow loses the race to tmux's proportional layout.
`TmuxMonitor.resize_pane` → `run_via_control` uses the control client whenever it
is alive (the normal runtime state). Full analysis and suggested fixes are in
`aitasks/t981_fix_failed_verification_t979_item2.md`.

Unit tests `tests/test_tmux_exec.py::TestResizePane` pass — they cover only argv
construction, not the live control-client-vs-reflow race.

## Cleanup
- Isolated tmux server `-L auto979` killed.
- Scratch repro scripts under `/tmp/auto_verify_979/` (not in repo):
  `harness.sh`, `pty_harness.py`, `pty_probe.py`, `pty_diag.py`, `diag_launch.py`,
  `pty_isolate.py`, `pty_timing.py`, `pty_ctrl.py`, `pty_ctrl2.py`.
  `pty_ctrl2.py` reproduces the failure with no minimonitor involved.
