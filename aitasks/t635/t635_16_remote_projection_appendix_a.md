---
priority: low
effort: high
depends: [t635_15]
issue_type: feature
status: Ready
labels: [gates, gitremote]
created_at: 2026-06-10 18:56
updated_at: 2026-07-26 00:00
---

## Context

Phase 5 of `aidocs/gates/integration-roadmap.md` — the full Appendix A of
the framework doc: projecting gate state to the linked remote issue for
reviewers who never clone the repo, and accepting scoped human-gate
signals from issue comments.

## Scope

Per `aidocs/gates/aitask-gate-framework.md` Appendix A:
- Label mirror (A.3): debounced terminal-only `ait-gate:<name>:<state>`
  labels via the dispatcher; sidecar `_mirror-state.json` convergence.
- Comment mirror (A.4): singleton edited-in-place status comment +
  append-only notable-event comments (all-pass, exhausted, human-wait,
  help-needed) with the suppression rules.
- Comment signal (A.5): `signal: comment` human gates with
  `match_keyword`/`reject_keyword` + authorization allow-lists
  (`reviewers:` frontmatter, `gate_authorized_users`); the narrowly-scoped
  read-back carve-out and its verbatim autonomy rule.
- Dispatcher backend gaps must close first or within this task:
  `edit_comment`, `list_comments` (A.7) — graceful degradation per A.8
  where a platform lags.
- All flags per A.9; uniform across GitHub/GitLab/Bitbucket through the
  dispatcher — no hardcoded platform references.

Consider splitting at planning time (label mirror needs no new backends
and can ship first; comment mirror + comment signal follow).

## Premise refresh (2026-07-26 — t635_33 active-gates model) — CONFIRM AT PLAN TIME

Flagged as an open question, **not** an asserted defect: Appendix A was not
re-read when this note was written, so treat it as something to check rather
than a finding.

**t635_33 landed 2026-07-19** (this task was last updated 2026-06-10) and split
what "a task's gates" means: raw `gates:` is *declared intent*, while the
enforced set is the derived `active_gates` tuple (declared ∩ profile ceiling)
materialized at claim, with `active_gates_filtered` recording what the ceiling
removed. The scope above speaks of projecting "gate state" without
distinguishing the two.

**Decide at plan time which set the projection carries.** Mirroring
declared-but-filtered gates would show reviewers gates that will never run under
the active profile — misleading in exactly the audience this feature exists for
(reviewers who never clone the repo). Candidate rule: project the **enforced**
set, and either omit filtered gates entirely or render them distinctly as
"skipped: execution profile", consistent with t635_33's invariant that a
filtered gate is invisible or at most reported as skipped — never an error.
Whichever is chosen, apply it uniformly to the label mirror (A.3), the status
comment (A.4) and comment-signal authorization (A.5).

## Downstream

- **t635_32** (procedure_gate_remote_signal, split out of t635_29) `depends:` on
  this task — it integrates procedure-backed gates with this remote projection +
  comment-signal surface (status projection + comment-triggered dispatch).

## References

- `aidocs/gates/aitask-gate-framework.md` Appendix A (complete spec)
- `aidocs/gates/integration-roadmap.md` (Phase 5)
