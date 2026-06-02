---
priority: medium
effort: low
depends: []
issue_type: documentation
status: Ready
labels: [docs, codex]
created_at: 2026-06-02 13:47
updated_at: 2026-06-02 13:47
---

## Goal

Restore and update the **Codex CLI** workflow-compliance caveats on
`website/content/docs/installation/known-issues.md` ("Known Agent Issues").

## Background

Commit `22ecb76f` (t862, 2026-05-31) trimmed the Codex CLI section. It removed
the subsection documenting that Codex skips task locking and stalls
post-implementation (needing an explicit nudge to commit/archive), and replaced
it with an optimistic framing: that enabling `default_mode_request_user_input`
in the generated `.codex/config.toml` makes interactive checkpoints "work
throughout the workflow, including post-implementation finalization."

A live `agent-pick-756_3` Codex session (`codex/gpt5_5`) on 2026-06-02
**contradicted that optimism**. The current page frames the only Codex
checkpoint problem as *tool availability* (now considered fixed). The real,
still-present problem is **workflow compliance**: Codex silently skips required
gates even when `request_user_input` is fully available, and must be nudged
repeatedly to surface and repair each skip.

## Observed in the t756_3 session (evidence)

`default_mode_request_user_input = true` was confirmed active and
`functions.request_user_input` was exposed in the session — yet Codex still:

- **Skipped the planning-time risk-evaluation gate** despite `risk_evaluation: true`
  in the active `fast` profile; repaired it only after the user called it out.
- **Skipped the non-skippable Step 8 review-gate** user-input prompts.
- **Treated the archive as the end of the workflow**, stopping before Step 9b and
  thereby **skipping the satisfaction-feedback rating prompt**.
- Required **repeated user nudges** to surface each skip:
  - "is default_mode_request_user_input active? you skipped all user-input questions"
  - "you also skipped the final question about rating the work done"
  - "why did you skip the final satisfaction prompt?"
- Codex's own admission: *"I treated the archive as the end of the workflow and
  stopped before Step 9b... The feedback prompt is a separate non-skippable
  post-implementation step, and I failed to carry it through."*

Note: some early skipped prompts (task confirmation, email, worktree) were
*legitimate* — pre-answered by the `fast` profile (`skip_task_confirmation`,
`default_email`, `create_worktree: false`). The documentation must distinguish
these legitimate profile-driven skips from the genuine compliance failures
above, so the page does not over-claim either way.

## Scope of doc change

In `website/content/docs/installation/known-issues.md`, under `## Codex CLI`:

1. **Keep** the existing "#### Interactive checkpoints" note (the
   `default_mode_request_user_input` availability fact is correct).
2. **Add** a new subsection (e.g. "#### Silently skips required workflow gates"
   or "#### Workflow-compliance caveats") documenting that, even with
   `request_user_input` available, Codex may silently skip non-skippable gates
   — risk evaluation at planning time, the Step 8 review gate, and the Step 9b
   post-archive satisfaction-feedback prompt — and may treat archive as the end
   of the workflow.
3. **Workaround:** after Codex finishes implementation/archive, explicitly
   prompt it to continue and complete remaining non-skippable steps; verify the
   review gate, risk evaluation, and final satisfaction prompt actually ran.
   Stronger reasoning/model settings improve compliance.
4. Follow the repo's user-facing docs convention: **current-state only** — no
   "previously this page said...". State the caveat positively; the t862 history
   belongs in git, not the page body.

## Acceptance

- The Codex CLI section documents the workflow-compliance (silent gate-skipping)
  caveat with the concrete gates affected and a nudge-to-continue workaround.
- Legitimate profile-driven skips are distinguished from compliance failures.
- No version-history prose in the page body (current-state only).
- Cross-references to `commands/codeagent` and the existing Claude Code
  "medium-effort models can miss workflow steps" note remain coherent.

## Related

- t862 (`22ecb76f`) — last edit to this section; the change this task partially
  walks back.
- t871 — manual verification of Codex forced plan mode (related investigation,
  not a doc task).
