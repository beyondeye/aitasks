---
priority: medium
effort: medium
depends: [t1159_4, t1159_7, t1518]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [t1159_1, t1159_2, t1159_3, t1159_4, t1518]
anchor: 1159
followup_kind: manual_verification
created_at: 2026-08-11 15:56
updated_at: 2026-08-17 10:19
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Arming-gate baseline (re-read before running the loop items)

This checklist was written against t1159_2's original Claude-only loop and
re-baselined on 2026-08-17. Arming checks **two independent gates** in
`action_toggle_review_loop` (`.aitask-scripts/monitor/minimonitor_app.py`), and
they refuse for different reasons with different wording:

| gate | source of truth | refusal |
|---|---|---|
| followed pane | `review_loop.REVIEW_LOOP_AGENTS` | names the agent; wording is t1518's to change |
| shadow pane | `review_loop.SHADOW_READY_DETECTORS` | "…has no readiness detection yet" |

Two shifts invalidated the original single "Codex/OpenCode shadow refuses" item:

- **t1509 (Done)** populated `SHADOW_READY_DETECTORS` with `codex` and
  `opencode`, so a Codex/OpenCode *shadow* no longer refuses on the shadow-side
  gate. Any refusal you now see with one comes from the *followed* gate — a
  different cause, so the old item would have passed for the wrong reason.
- **t1518** widens `REVIEW_LOOP_AGENTS` past `("claude",)` per agent, behind
  live evidence, and explicitly may leave an agent out. **Read the tuple in the
  source before running the two refusal items** — do not assume which agents
  refuse. Whatever t1518 shipped is the expected outcome.

`REVIEW_LOOP_AGENTS` was `("claude",)` at the time of this edit, with t1518
still `Implementing`; treat that as stale and re-read.

## Verification Checklist

- [ ] [t1159_1] With a live shadow running a review, confirm the emitted concern block's first in-fence line is `Round: <N> @ <ISO-8601 seconds>Z` and that the timestamp was shell-sourced (matches wall clock to the minute)
- [ ] [t1159_1] Trigger a repeat review with identical concerns (round 2): minimonitor's auto-offer toast fires again and names the round (dedup lifted)
- [ ] [t1159_1] Ask the shadow for a review that finds zero concerns: it emits a metadata-only block (fences + round header only) and NO auto-offer toast appears
- [ ] [t1159_1] Open the picker on a round-carrying block: the context line shows the round and time
- [ ] [t1159_2] Arm the loop with `L` during a live `/aitask-pick` plan review (Claude followed + Claude shadow): banner shows ARMED; when the followed agent settles at the plan checkpoint after addressing concerns, exactly ONE recheck lands in the shadow pane, naming the expected round
- [ ] [t1159_2] While the shadow is mid-analysis (streaming), confirm the loop holds (banner "waiting for shadow to settle") and fires only after the shadow returns to an empty composer
- [ ] [t1159_2] Answer the recheck round; confirm no second fire occurs until the followed pane changes again and settles (edge contract + cooldown)
- [ ] [t1159_2] Kill the shadow pane while armed: loop auto-disarms with a visible notification
- [ ] [t1159_2] Followed-side arm refusal: with a followed agent that is NOT in `REVIEW_LOOP_AGENTS` at the time you run this, press `L` and confirm a visible refusal that **names that agent**, and the loop stays disarmed. Read the tuple first (`.aitask-scripts/monitor/review_loop.py`, `REVIEW_LOOP_AGENTS`) and pick your pane accordingly — see "Arming-gate baseline" below; if the tuple covers every agent you can run, mark this **Skip** with the tuple contents as the reason rather than Pass
- [ ] [t1159_2] Shadow-side arm refusal is **not** live-reachable and must not be verified live: since t1509 every installed agent (claude, codex, opencode) has a `SHADOW_READY_DETECTORS` entry, so no real shadow trips it. Confirm by reading the dict, then confirm the guard is covered by `tests/test_minimonitor_concern_action.py` (`_UNDETECTED_KEY = "futureagent"`, asserts `no readiness detection`) — Pass on those two reads
- [ ] [t1159_2] Distinguish the two shadow-side messages: an unresolved shadow agent must say "could not resolve the shadow's agent yet — try again", never "has no readiness detection yet". Arm immediately after pressing `e` (before the shadow settles) to try to hit the retry path; **Skip** if it resolves too fast to observe
- [ ] [t1518] Cross-agent pairing, per t1518's coordination note (it defers the pairings here rather than duplicating live runs): for each agent t1518 actually added to `REVIEW_LOOP_AGENTS`, arm with that agent as the **followed** pane and confirm exactly one automatic recheck round lands in the shadow pane
- [ ] [t1518] Same pairings, negative direction: pure option-cursor movement inside that agent's question widget and inside its native dialog fires **nothing** (`SELECTION_ONLY`)
- [ ] [t1159_2] Confirm at no point does ANY injected text land in the followed agent's pane
- [ ] [t1159_3] In the picker, mark a concern with `t` (») and confirm: a draft file appears in `aitasks/new/` with `followup_kind: review_finding` and the anchor of the reviewed task, and the notify reports the draft path
- [ ] [t1159_3] Spin off two concerns with the same region in one confirmation: two distinct draft files, no overwrite
- [ ] [t1159_3] After spin-off, run the next review round: the spun-off concern is suppressed (store entry with producer `spinoff` visible via `aitask_shadow_rejected.sh list`)
- [ ] [t1159_3] Finalize one spun-off draft with `ait create` and confirm it claims a real id
- [ ] [t1159_4] Website minimonitor page documents `L`, `t`, banner states, and refusal messages; `hugo build` passes
- [ ] [t1159_4] `aidocs/framework/shadow_agent.md` review-loop section matches landed behavior (spot-check the 8-point safety contract against the code)
