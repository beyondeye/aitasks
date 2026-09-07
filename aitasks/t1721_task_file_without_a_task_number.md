---
priority: medium
effort: low
depends: []
issue_type: bug
status: Implementing
labels: [backend]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-09-06 17:08
updated_at: 2026-09-07 17:06
---

`aitasks/t_refresh_codeagent_suite_default_model_expectations.md` has **no task
number** in its filename — the `t` prefix is followed directly by the name.

```
aitasks/t_refresh_codeagent_suite_default_model_expectations.md
  status: Ready, anchor: 1162, created_at: 2026-07-29 09:55
```

## Why it matters

`ait ls` lists the file, but nothing can derive an id from it. Every consumer
that maps a listing row back to a task id has to either skip it or produce an
empty id — and an empty id passed onward asks about a task that cannot exist.

Found by the first live run of `aitask_backlog_roadmap.sh` (t1569_6, 2026-09-06),
which now reports it as `UNPARSABLE_TASK_FILE:` and names it in the published
trail's method note rather than silently dropping it. That is a **workaround at
one consumer**, not a fix: any other consumer still meets the same file.

## Scope

1. Decide what the file should be — a real numbered task, or deleted if its
   content is obsolete (it predates several codeagent-model changes).
2. If it is real, give it a claimed id and move it to the conventional path.
3. Consider whether `ait ls` should refuse to emit, or should flag, a task file
   whose name carries no id — a listing row that cannot be addressed is a
   silent trap for every consumer, and this is the only known instance, so the
   guard would currently cost nothing.
