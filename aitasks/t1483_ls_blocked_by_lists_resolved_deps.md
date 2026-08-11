---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [aitask_ls, dependencies, display]
created_at: 2026-08-11 16:30
updated_at: 2026-08-11 16:30
---

## Symptom

`aitask_ls.sh` renders a task with a mixed dependency list such as
`depends: [t45_9, 75]` as `Blocked (by t45_9,75)` — including the bare
numeric entry `75` even though task 75 is archived (completed). The task
is genuinely blocked (by the still-active `t45_9`), so blocking is
correct; only the *displayed reason string* is wrong: it names a
resolved/archived dependency as if it were still a blocker. This misleads
the reader and will misrepresent the blocker set once the real blocker
(`t45_9`) lands.

## Root cause

The defect is a display bug, **not** a dependency-resolution bug. In
`calculate_blocked_status()`:

```bash
for dep_id in "${ADDR[@]}"; do
    if is_task_uncompleted "$dep_id"; then
        blocked=1
        blocking_info="$d_text"   # <-- dumps the ENTIRE depends list
        break
    fi
done
```

As soon as *any* dependency is unresolved, `blocking_info` is set to the
whole `d_text` and the loop breaks. So every dependency in the list —
including ones that `is_task_uncompleted` would correctly report as
completed/archived (bare `75` normalizes to `75`, is absent from the
active-ids set, and returns "completed") — is reprinted in the
`Blocked (by ...)` line.

The bare-numeric entry `75` resolves *correctly*; the display just never
filters `d_text` down to the actually-unresolved subset.

The cross-repo `xdeps` loop immediately below already does this correctly:
it appends only the actual blocker to `blocking_info` incrementally
(`blocking_info="${blocking_info:+$blocking_info,}..."`).

## Fix

Accumulate only the unresolved `dep_id`s into `blocking_info` and drop the
early `break`, mirroring the xdeps loop:

```bash
for dep_id in "${ADDR[@]}"; do
    if is_task_uncompleted "$dep_id"; then
        blocked=1
        blocking_info="${blocking_info:+$blocking_info,}${dep_id}"
    fi
done
```

This lists every genuine blocker and omits resolved/archived deps, so
`t45_3` would render as `Blocked (by t45_9)`.

## Location

- `.aitask-scripts/aitask_ls.sh`, function `calculate_blocked_status()`
  (the `blocking_info="$d_text"` line inside the explicit-dependency loop).

## Reproduction

- A task with `depends: [t<active_child>, <archived_bare_id>]` where the
  bare id is archived and the child is still active.
- Confirmed against `t45_3` (`depends: [t45_9, 75]`): `t75` is archived,
  `t45_9` is `Ready`; the list renders `Blocked (by t45_9,75)`.

## Notes

- Filed from a downstream consumer repo (thinking_backend) whose synced
  `.aitask-scripts/aitask_ls.sh` copy carries the identical code; the
  source of truth is this (aitasks) repo.
- Behavior change is display-only. Consider a regression check that a
  mixed list with one resolved and one active dep renders only the active
  dep in the blocked-by reason.
