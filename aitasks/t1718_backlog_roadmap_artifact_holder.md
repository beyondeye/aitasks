---
priority: low
effort: low
depends: []
issue_type: chore
status: Postponed
labels: [artifacts, backlog]
created_at: 2026-09-06 17:03
updated_at: 2026-09-06 17:10
artifacts:
  - handle: art:trail-backlog-roadmap
    kind: implementation_trail
    name: Background-work roadmap
---

**This task is an artifact holder, not work. It is never implemented and never
archived.**

It owns the handle `art:trail-backlog-roadmap` — the background-work roadmap
published by the `aitask-backlog-roadmap` skill (t1569_6).

## Why a standing holder exists

The artifact substrate supports only **task-owned** artifacts, and the owner's
task file carries the `artifacts:` breadcrumb. Every other implementation trail
is owned by the topic-root task it describes (t635, t1118, t1159, t1243), but
this roadmap covers the whole backlog and has no topic root. Owning it from
t1569 — the tree that built it — would move the breadcrumb into
`aitasks/archived/` as soon as that tree completes, while the roadmap itself
goes on being refreshed indefinitely.

`status: Postponed` is the framework's word for deliberately-not-picked work, so
this task never surfaces in `/aitask-pick` and is never a candidate in the
roadmap it owns.

## Do not

- Do not implement, archive or fold this task.
- Do not add work to it. A change to the roadmap belongs on a real task; this
  file only holds the handle.

## Related

- `aidocs/framework/background_work_roadmap.md` — the design record.
- `.claude/skills/aitask-backlog-roadmap/SKILL.md` — the publishing skill.
