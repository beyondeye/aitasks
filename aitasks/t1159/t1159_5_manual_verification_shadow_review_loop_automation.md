---
priority: medium
effort: medium
depends: [t1159_4]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1159_1, 1159_2, 1159_3, 1159_4]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-11 15:56
updated_at: 2026-08-11 15:56
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t1159_1] With a live shadow running a review, confirm the emitted concern block's first in-fence line is `Round: <N> @ <ISO-8601 seconds>Z` and that the timestamp was shell-sourced (matches wall clock to the minute)
- [ ] [t1159_1] Trigger a repeat review with identical concerns (round 2): minimonitor's auto-offer toast fires again and names the round (dedup lifted)
- [ ] [t1159_1] Ask the shadow for a review that finds zero concerns: it emits a metadata-only block (fences + round header only) and NO auto-offer toast appears
- [ ] [t1159_1] Open the picker on a round-carrying block: the context line shows the round and time
- [ ] [t1159_2] Arm the loop with `L` during a live `/aitask-pick` plan review (Claude followed + Claude shadow): banner shows ARMED; when the followed agent settles at the plan checkpoint after addressing concerns, exactly ONE recheck lands in the shadow pane, naming the expected round
- [ ] [t1159_2] While the shadow is mid-analysis (streaming), confirm the loop holds (banner "waiting for shadow to settle") and fires only after the shadow returns to an empty composer
- [ ] [t1159_2] Answer the recheck round; confirm no second fire occurs until the followed pane changes again and settles (edge contract + cooldown)
- [ ] [t1159_2] Kill the shadow pane while armed: loop auto-disarms with a visible notification
- [ ] [t1159_2] Attempt to arm with a Codex/OpenCode shadow (or a followed agent without prompt detection): visible refusal message, loop stays disarmed
- [ ] [t1159_2] Confirm at no point does ANY injected text land in the followed agent's pane
- [ ] [t1159_3] In the picker, mark a concern with `t` (») and confirm: a draft file appears in `aitasks/new/` with `followup_kind: review_finding` and the anchor of the reviewed task, and the notify reports the draft path
- [ ] [t1159_3] Spin off two concerns with the same region in one confirmation: two distinct draft files, no overwrite
- [ ] [t1159_3] After spin-off, run the next review round: the spun-off concern is suppressed (store entry with producer `spinoff` visible via `aitask_shadow_rejected.sh list`)
- [ ] [t1159_3] Finalize one spun-off draft with `ait create` and confirm it claims a real id
- [ ] [t1159_4] Website minimonitor page documents `L`, `t`, banner states, and refusal messages; `hugo build` passes
- [ ] [t1159_4] `aidocs/framework/shadow_agent.md` review-loop section matches landed behavior (spot-check the 8-point safety contract against the code)
