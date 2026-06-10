---
priority: low
effort: high
depends: [t635_15]
issue_type: feature
status: Ready
labels: [gates, gitremote]
created_at: 2026-06-10 18:56
updated_at: 2026-06-10 18:56
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

## References

- `aidocs/gates/aitask-gate-framework.md` Appendix A (complete spec)
- `aidocs/gates/integration-roadmap.md` (Phase 5)
