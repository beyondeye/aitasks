---
priority: high
effort: high
depends: [t1157_4]
issue_type: feature
status: Ready
labels: [workflows, remote, codeagent, aitask_explore, claudecode]
gates: [risk_evaluated]
anchor: 1157
created_at: 2026-07-17 12:18
updated_at: 2026-07-17 12:18
---

## Context

Fifth child of t1157. Add a distinct message-triggered open-ended explore workflow on the generic host. It should feel like native `aitask-explore` over Discord: choose intent, inspect the committed repository, iteratively steer/redirect, review task metadata, and explicitly approve task creation. It must not implement code or gain repository write credentials.

## Key files to modify

- New static chat-native remote-explore skill in `.claude/skills/` using the relay checkpoint/proposal contracts.
- `.aitask-scripts/aitask_codeagent.sh`: a headless operation/dispatch for the new skill, preserving explicit billing and tool-timeout controls.
- New explore workflow handler under `.aitask-scripts/chatlink/` and registration with the t1157_3 router.
- `.aitask-scripts/chatlink/render.py`: intent, findings checkpoint, redirect, pause, proposal, and metadata interactions.
- Flow/daemon tests plus a headless skill dispatch/conformance test.

## Reference files

- `.claude/skills/aitask-explore/SKILL.md.j2` for intent and iterative exploration semantics.
- `.claude/skills/aitask-explorechat/SKILL.md` and `tests/test_codeagent_explore_relay.sh` for the machine-spawned relay pattern.
- t1157_1 through t1157_4 contracts.

## Implementation plan

1. A message in a configured explore channel opens an `explore:` thread and becomes the initial description. Ask the user to choose Investigate problem, Explore codebase area, Scope idea, or Explore documentation; allow free-text refinement.
2. Explore read-only committed HEAD according to the chosen strategy. Persist a checkpoint after each meaningful round.
3. Render every findings checkpoint inside the interaction with Continue, Redirect, Propose task, Pause, and Abort. Redirect accepts free text and updates the durable transcript.
4. Use the default 60-minute attempt budget: 45 active minutes plus a 15-minute synthesis reserve, with the same visible/clamped semantics as bug intake.
5. Synthesize and validate an unapproved task proposal, then exit the sandbox. Let the initiator review/modify metadata and use Approve, Request changes, Resume, Restart, or Abort.
6. Explicit approval creates one parent aitask through the routed project's gateway. There is no Continue to implementation option and the sandbox never writes source/task/git state.
7. Support seven-day resumability and a 15-minute revision attempt as defined by the shared session model.
8. Keep the skill static and Claude-first; do not absorb t1136/t1137/t1140 multi-agent runtime scope.

## Verification

- Each intent selects the correct exploration strategy and generates evidence-backed findings.
- Continue and Redirect perform additional meaningful rounds; Pause/Abort semantics and findings visibility are pinned.
- Budget expiry, no-response defaults, proposal lifecycle, explicit approval, revision, resume/restart, and latest-HEAD revalidation are covered.
- Headless dispatch dry-run and live opt-in smoke prove relay questions/checkpoints/proposal landing.
- The sandbox has no repo mutation/git credential path, and no task is created without approval.
