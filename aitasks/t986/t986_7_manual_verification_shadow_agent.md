---
priority: medium
effort: medium
depends: [t986_6]
issue_type: manual_verification
status: Ready
labels: [verification, manual]
verifies: [986_1, 986_2, 986_3, 986_4, 986_5, 986_6]
created_at: 2026-06-14 16:07
updated_at: 2026-06-14 16:07
---

## Manual Verification Task

This task is handled by the manual-verification module: run
`/aitask-pick <id>` and the workflow will dispatch to the
interactive checklist runner. Each item below must reach a
terminal state (Pass / Fail / Skip) before the task can be
archived; Defer is allowed but creates a carry-over task.

## Verification Checklist

- [ ] [t986_1] pane_id-keyed task map resolves the correct task per pane (not per window).
- [ ] [t986_1] Two agents in one tmux window: killing one leaves the other alive with correct task-ids.
- [ ] [t986_1] `_find_sibling_pane_id()` returns the intended agent pane, not the first non-companion pane.
- [ ] [t986_1] A `shadow`-classified pane is absent from monitor and minimonitor agent lists.
- [ ] [t986_1] `bash tests/test_no_raw_tmux.sh` stays green; `shellcheck aitask_companion_cleanup.sh` clean.
- [ ] [t986_2] Task-file fixtures at various gate states map to the expected phase (ledger path).
- [ ] [t986_2] Transcript fixtures (review prompt, merge prompt, AskUserQuestion, plain planning) map to the expected phase (text path).
- [ ] [t986_2] A live AskUserQuestion overrides the ledger-derived phase (precedence).
- [ ] [t986_2] The module imports gate-ledger parsing from `lib/gate_ledger.py` (no forked copy).
- [ ] [t986_3] Fixture tasks (parent + child, active + archived) resolve the correct task and plan files.
- [ ] [t986_3] Most-recent-plan selection picks the latest when multiple plans exist.
- [ ] [t986_3] `NOT_FOUND` path is emitted for a missing task/plan.
- [ ] [t986_3] `shellcheck aitask_shadow_context.sh` clean; helper registered in the whitelist.
- [ ] [t986_4] `./.aitask-scripts/aitask_skill_verify.sh` passes (closure + stub-surface checks).
- [ ] [t986_4] Dry-run the flow against transcript fixtures (planning, AskUserQuestion-without-context, plan-to-challenge): the single flow handles all three by instruction.
- [ ] [t986_4] Advisory-only: no path sends input to the source agent pane.
- [ ] [t986_4] Cross-agent: if SKILL.md is agent-agnostic, Codex/OpenCode render from source automatically; create port follow-ups only if agent-specific surfaces are touched.
- [ ] [t986_5] `defaults.shadow` resolves through the agent-string chain (CLI → .local → project → DEFAULT).
- [ ] [t986_5] Placement toggle defaults correctly and is overridable via `.local`/profile.
- [ ] [t986_5] Pressing the key on a followed agent spawns the shadow in the same window, feeding it the captured output, and the shadow pane is NOT listed among agents.
- [ ] [t986_5] `bash tests/test_no_raw_tmux.sh` stays green; `shellcheck` clean.
- [ ] [t986_6] `cd website && hugo build --gc --minify` succeeds with no broken references.
- [ ] [t986_6] Doc prose follows `documentation_conventions.md` (current-state-only, generic agent naming, placeholder project names).
- [ ] [t986_6] Cross-references updated; `workflows/_index.md` bullet added if a workflows page was created.
