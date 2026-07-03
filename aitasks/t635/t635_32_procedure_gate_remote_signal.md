---
priority: low
effort: high
depends: [635_16]
issue_type: feature
status: Ready
labels: [gates]
anchor: 635
created_at: 2026-07-03 12:41
updated_at: 2026-07-03 12:41
---

## Context

Extracted from **t635_29** (procedure_gate_generalization) at planning time — the
remote/comment-signal integration for procedure gates was split out because it
builds on the remote-projection infrastructure (framework doc Appendix A) delivered
by **t635_16**, which is not yet landed. t635_29 keeps only the ripe core
(async/headless dispatch + agent-aware resolution) with no hard blocker.

Procedure-backed gates (`kind: procedure`) do agent work (inspect the change, update
docs, confirm) and record a terminal `pass`/`skip`/`fail`. This task integrates them
with the **remote projection + comment-signal** surface so a procedure gate can be
triggered and/or observed from the linked issue tracker, uniformly across
GitHub/GitLab/Bitbucket through the dispatcher.

## Scope

- **Status projection:** a procedure gate's terminal state participates in the label
  mirror + singleton status comment (Appendix A.3 / A.4) like other gates.
- **Comment-signal trigger:** define how a procedure gate can be *dispatched* from a
  scoped, authorized comment signal (contrast with human-gate `signal: comment`
  which only *observes* a sign-off) — a procedure gate must actually *run* the
  verifier skill in response, honoring the autonomous-lane non-interactive policy
  from t635_29.
- Reuse the dispatcher backends (`edit_comment`, `list_comments`) and authorization
  allow-lists t635_16 introduces; no hardcoded platform references.

## Depends / Coordination

- **t635_16** (remote projection — Appendix A: label/comment mirror + comment
  signals + dispatcher backend gaps). Hard dependency: this needs that infra.
- Builds on **t635_29** (procedure-gate core: async/headless non-interactive run
  policy) and the framework doc Appendix A.

## Verification (define fully at pick time)

- A procedure gate's terminal state appears in the remote label/comment projection.
- An authorized comment signal dispatches the procedure gate's verifier (runs the
  skill non-interactively per the t635_29 policy), records the terminal block, and
  projects the result — with the autonomy allow-list enforced.
