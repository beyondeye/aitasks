---
priority: medium
effort: medium
depends: [1685]
issue_type: manual_verification
status: Implementing
labels: [verification, manual]
verifies: [1685]
assigned_to: dario-e@beyond-eye.com
anchor: 1685
followup_kind: manual_verification
created_at: 2026-09-02 18:34
updated_at: 2026-09-02 19:15
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1685

## Verification Checklist

- [x] In `ait monitor`, press Space three times on one agent and confirm the mark cycles unmarked (dim ☆) → ★ → P → unmarked, with the glyph legible in your terminal font — PASS 2026-09-02 19:02 auto: live tmux fixture -- space cycled agent-t101 dim ☆ → ★ → P → ☆; P is ASCII U+0050, rendered bold white in capture-pane -pe
- [x] With an agent parked, confirm its row shows only `P`, the window name and a dim `parked` — no state dot, no status, no gate summary — PASS 2026-09-02 19:02 auto: parked row rendered 'P 1:agent-t101-claudecode (1)  parked' -- no state dot, no ≈, no status, no gate summary; 'parked' in #999999 vs #e0e0e0 body (dim)
- [x] Confirm the monitor session bar shows an `N parked` term alongside the live counters, and that the live counters no longer include the parked agent — PASS 2026-09-02 19:02 auto: session bar read '2 idle  1 parked'; parking the awaiting-input agent dropped '1 awaiting' from the live counters
- [fail] Press `P` in `ait monitor` to hide parked agents, then `P` again to show them; confirm the list shrinks and grows — FAIL 2026-09-02 19:02 follow-up t1697
- [x] Park the FOCUSED card while the filter is on and confirm focus lands on a visible card — not on the preview column and not nowhere — PASS 2026-09-02 19:02 auto: with filter ON, parked the focused visible card -- row vanished, exactly one focus highlight remained on a visible card, ? modal still opened
- [x] Park the ONLY visible agent while the filter is on and confirm the pane list empties cleanly, the preview shows its empty state, and `P` still works to reveal the agent again — PASS 2026-09-02 19:02 auto: parked the last visible agent with filter ON -- list emptied, preview showed 'Focus an agent or pane to see its output', P revealed all 3 parked rows
- [x] With the filter OFF, focus a parked card and confirm the preview reads "This agent is parked — press Space to unpark it." rather than an empty pane — PASS 2026-09-02 19:02 auto: filter OFF, focused a parked card -- preview read 'This agent is parked -- press Space to unpark it.'
- [x] Park an agent while the filter is on and read the toast: it must name the `P` then `Space` route back — PASS 2026-09-02 19:02 auto: toast read 'Parked agent-t103-claudecode -- hidden. Press P to show parked agents, then Space to unpark.'
- [x] Confirm auto-switch (`A`) never moves focus onto a parked agent, with both an idle and an awaiting-input parked agent present — PASS 2026-09-02 19:02 auto: control (nothing parked) auto-switch moved focus active→awaiting on rebuild; with the idle and awaiting agents parked it stayed on the active agent
- [x] In `ait minimonitor`, press Space on the followed agent until it is parked, and confirm the docked `── this agent ──` panel shows `P` and KEEPS updating its phase line — parking must not stop this pane watching its own agent — PASS 2026-09-02 19:15 auto: docked panel showed 'P agent-pick-101' and its phase line kept tracking live capture while parked -- IMPLEMENT ⏸? ↔ IMPLEMENT? flipped both ways as the followed pane's prompt appeared/disappeared
- [x] With the followed agent parked, confirm `L` (auto-recheck loop), `c` (concerns) and `e` (shadow launch) still work on it — PASS 2026-09-02 19:15 auto: with the followed agent parked, L reported the agent-capability refusal (not 'no followed agent pane'), c reported 'No shadow agent running -- press e', and e spawned a pane stamped @aitask_shadow_target
- [x] Press `P` in `ait minimonitor` and confirm parked agents leave and rejoin the scrollable list, and that the key hints row shows `P:parked` — PASS 2026-09-02 19:15 auto: P removed then restored the three parked rows in the scrollable list; key hints row shows 'P:parked'
- [x] Park an agent from `ait monitor` in one project and confirm it appears parked in another project's monitor within a refresh cycle (~3s) — PASS 2026-09-02 19:15 auto: parked projB's agent from projA's monitor -- projB's own monitor showed it parked on the first poll; unparking propagated back in ~3s
- [x] Verify a parked agent's tmux pane genuinely stops being captured — e.g. produce output in it and confirm no monitor re-renders its content while parked — PASS 2026-09-02 19:15 auto: a monitor booted with two agents already parked issued capture-pane only for the unparked panes (control boot captured all five); output written into a parked pane never appeared in the monitor, and appeared immediately after unparking
- [x] Rename the tmux window a minimonitor follows while its agent is parked, and confirm the docked panel keeps updating (the identity-confirmation fail-safe) — PASS 2026-09-02 19:15 auto: renamed the followed window while parked -- docked panel kept updating its phase line in both directions (identity text stays frozen by the one-shot contract)
- [x] Confirm an existing pre-t1685 marks store (~/.config/aitasks/agent_marks.json at version 1) still shows every star after upgrading — PASS 2026-09-02 19:15 auto: v1 store (no kind key) read as four ★ priority marks in the monitor and as |priority from the CLI list; on-disk file left at version 1 by the read
