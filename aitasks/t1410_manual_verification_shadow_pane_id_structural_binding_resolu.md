---
priority: medium
effort: medium
depends: [1319]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
active_gates: []
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 4a36c12bb96d.681bafac2cb9.08c6f06389cd
verifies: [1319]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-08-04 13:34
updated_at: 2026-08-04 16:59
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1319

## Verification Checklist

- [x] Spawn a real shadow from minimonitor (`e`) against a live agent; confirm its first argument-free `aitask_shadow_capture.sh` call resolves the bound followed pane with no error (the launch->stamp race at the real agent-CLI layer) — PASS 2026-08-04 16:59 auto: live shadow %210 (Codex, spawned by minimonitor 'e' as $aitask-shadow %204 1409) -- its FIRST capture in a 124-line scrollback is the argument-free form and printed 'resolved followed pane %204 from @aitask_shadow_target', no error; launch->stamp race not hit
- [x] With that shadow running, open the concern picker; confirm concerns still appear — `capture_shadow_text` now passes `--any-pane`, and a regression here surfaces as a silent "no concerns" rather than an error — PASS 2026-08-04 16:59 auto: minimonitor action_pick_concerns data path replicated verbatim over 9 live shadows -- 7 yielded parsed concerns, 0 capture failures, no silent 'no concerns'; monitor's identical picker also driven live to a populated modal
- [x] Run `ait monitor` from a personal tmux session on a different socket than `-L ait`; confirm the shadow preview column and the concern picker still work (the cross-server case the `--any-pane` opt-out exists for) — PASS 2026-08-04 16:59 auto: 'ait monitor' run on socket -L verify1410 (framework on -L ait) listed 13 agents, rendered 'Shadow (%138 <- %116)' with live content + staleness banner, and 'c' opened the picker showing the shadow's concern
- [x] From inside a live shadow pane, run `./.aitask-scripts/aitask_shadow_capture.sh <a-wrong-pane-id>`; confirm it exits 2, names both the requested and the bound pane, and captures nothing — PASS 2026-08-04 16:59 auto: from a pane bound to %1, capture of live pane %0 exited 2 naming BOTH requested and bound pane, stdout 0 bytes; negative control --any-pane %0 returned 11663 bytes, proving the refusal (not an unreadable pane) blocked it
- [x] Invoke `/aitask-shadow %<id>` manually from OUTSIDE the framework's tmux server; confirm the agent follows the split recovery (ask the user to confirm the pane, then re-run with `--any-pane`) and does NOT livelock between the no-arg and explicit forms — PASS 2026-08-04 16:59 auto: real 'claude /aitask-shadow %116' from a pane outside the ait server ran exactly 3 captures -- no-arg (exit 1) -> explicit (exit 2) -> asked the user to confirm the pane -> --any-pane (success). No bounce back to no-arg; ladder terminates
- [x] TODO: verify .aitask-scripts/monitor/monitor_core.py end-to-end in tmux (interactive surface touched by this task) — PASS 2026-08-04 16:59 auto: monitor_core exercised end-to-end in a real tmux TUI -- capture_shadow_text (the sole t1319 change), find_shadow_pane_async, compute_shadow_staleness and the concern picker; spawn_shadow's stamping evidenced by 9 live correctly-bound shadow panes
