---
priority: medium
effort: medium
depends: [1520]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1520]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-16 13:02
updated_at: 2026-08-16 13:02
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1520

## Verification Checklist

- [ ] Arm: in a real `ait minimonitor`, follow a Claude agent, `E`-launch an OpenCode shadow, press `L` — the loop must ARM, not refuse with "has no readiness detection yet".
- [ ] Fire: let the followed agent settle with unread output — exactly one `refetch and recheck round N` line must be injected into the SHADOW pane, and nothing into the followed pane.
- [ ] Hold (working): while the OpenCode shadow is mid-output (⬝⬝⬝⬝ esc interrupt footer visible), the loop must NOT inject.
- [ ] Hold (permission dialog): park the OpenCode shadow on its "Allow once / Allow always / Reject" dialog — the loop must NOT inject while it is up.
- [ ] Hold (command palette): open the OpenCode shadow's `ctrl+p` command palette and leave it open — the loop must NOT inject (Enter there would run the selected command).
- [ ] Hold (typed text): type text into the OpenCode shadow's composer without submitting — the loop must NOT inject and concatenate onto it.
- [ ] Short pane: shrink the OpenCode shadow pane so no line remains below the composer box border, and start a turn — the loop must NOT inject even though the box looks idle (this is the fail-dangerous case the window guard covers).
- [ ] Availability: at a normal narrow split (e.g. 40 cols), an idle OpenCode shadow must still be eligible — confirm the loop does eventually fire rather than never firing.
- [ ] Mid-loop swap: with the loop armed, swap the shadow to an OpenCode agent — the loop must stay armed (not auto-disarm).
- [ ] Regression: repeat the arm+fire check with a Claude shadow and a Codex shadow — both must behave exactly as before this change.
- [ ] Monitor unchanged: confirm `ait monitor` still reads a followed OpenCode agent with an open command palette as idle — the new pattern deliberately does NOT extend followed-pane awaiting_input (it renders outside the 6-line window).
