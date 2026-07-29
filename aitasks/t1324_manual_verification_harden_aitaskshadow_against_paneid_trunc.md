---
priority: medium
effort: medium
depends: [1307]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [1307]
created_at: 2026-07-29 11:16
updated_at: 2026-07-29 11:16
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

**Related to:** t1307

## Verification Checklist

- [ ] Launch a real shadow from minimonitor (`e`) against an agent whose pane id is multi-digit (e.g. %237) and confirm the shadow's first capture command carries the id verbatim — no dropped digits.
- [ ] Repeat the launch with a Codex CLI shadow (the agent that exhibited the original %237 -> %7 truncation) and confirm the same.
- [ ] Deliberately run `./.aitask-scripts/aitask_shadow_capture.sh %7` from inside a live shadow pane and confirm the documented recovery works: `tmux show-options -pqv -t "$TMUX_PANE" @aitask_shadow_target` returns the real followed pane id.
- [ ] From a shell with TMUX_PANE unset, confirm the recovery's step-1 guard does not run `tmux show-options -t ""` (no tmux error is emitted).
- [ ] Confirm the shadow asks the user rather than fuzzy-matching when given a pane id that matches no live pane and no binding is available.
- [ ] Verify `./.aitask-scripts/aitask_shadow_capture.sh --help` and `python3 .aitask-scripts/aitask_shadow_spawn_learner.py --help` render `%237` (not `%5`, and not a literal `%%237`).
- [ ] Launch `/aitask-learn-skill %<multi-digit>` from a shadow via the spawn-learn-skill path and confirm the learner receives the pane id unmangled.
