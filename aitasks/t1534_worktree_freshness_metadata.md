---
priority: medium
effort: medium
depends: []
issue_type: enhancement
status: Ready
labels: []
anchor: 635
followup_kind: risk_mitigation
created_at: 2026-08-16 18:54
updated_at: 2026-08-16 18:54
---

## Origin

Risk-mitigation ("after") follow-up for t1263, created at Step 8d after implementation landed.

## Risk addressed

Worktree isolation — the one signal that could prove ownership structurally — is **not** used, because freshness cannot be proven after the fact. · severity: low

t1263 added `aitask_change_surface.sh`, which attributes a dirty tree to a task
from three signals: the `(t<id>)` commit tag (proven), the task's plan naming a
path by exact file (declared), and a claim-time dirty-set baseline (proven
negative). Anything else is `UNKNOWN:` and escalates to the user.

An earlier draft added a fourth signal: if the tree is a linked worktree on an
`aitask/*` branch, treat everything dirty as the task's. That was **rejected in
review** — it is an *inference* about how the worktree was created, not a proof.
A reused or hand-made linked worktree can hold foreign dirt, and trusting the
inference would bypass the `UNKNOWN:` escalation entirely, which is the exact
false-attribution failure t1263 exists to close.

## Goal

Make worktree freshness **provable** rather than inferred, so a framework-created
task worktree can serve as a genuine ownership signal instead of escalating all
of its unnamed dirt.

Sketch:

- Have task-workflow Step 5 record framework-created-worktree metadata at the
  moment it runs `git worktree add -b aitask/<task_name> aiwork/<task_name> <base>` —
  the only point at which "this tree was created clean, for this task" is a fact
  rather than a guess. Recording the task id, the base commit, and a timestamp is
  enough.
- Teach `aitask_change_surface.sh` to read that metadata and, when it is present
  **and** matches the current tree and task, treat the tree as isolated: dirty
  paths are this task's by construction.
- Absence of the metadata must keep today's behaviour exactly (escalate via
  `UNKNOWN:`) — the signal may only ever *add* attribution, never remove the
  fail-safe.

## Why this was spawned rather than inlined

It edits the shared `task-workflow` authoring template (`.claude/skills/task-workflow/SKILL.md`
Step 5), which requires regenerating the rendered goldens across every profile
and every agent tree — a blast radius well beyond t1263's own change. Estimated
at design time as `inline_risk: high`, `added_complexity: high`.

## Verification

- A worktree created by the framework's own Step 5 flow yields the metadata, and
  `aitask_change_surface.sh list <id>` in that tree attributes its dirty paths.
- A hand-made `git worktree add` on an `aitask/*` branch does **not** yield the
  metadata, and its unnamed dirt still comes back `UNKNOWN:` (negative control —
  this is the case that made the inference unsafe).
- Metadata for a *different* task or a different toplevel is rejected, not
  trusted.
- With the metadata absent, output is byte-identical to today's.
