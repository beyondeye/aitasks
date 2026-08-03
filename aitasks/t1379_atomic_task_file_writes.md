---
priority: medium
risk_code_health: medium
risk_goal_achievement: low
effort: medium
depends: []
issue_type: bug
status: Implementing
labels: [python, script-performance]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1210
implemented_with: claudecode/opus5
created_at: 2026-08-03 11:10
updated_at: 2026-08-03 17:28
boardidx: 9216
---

## Origin

Spawned from t1371 during Step 8b review.

## Upstream defect

t1371 made `lib/frontmatter_patch.py` write task frontmatter atomically. A
survey done for that task found the same truncate-then-write primitive, and
some related temp-file mistakes, across the rest of the framework:

**Non-atomic task/plan file writers (truncate-then-write):**

- `.aitask-scripts/aitask_update.sh:800` — `write_task_file` rebuilds an existing task file with `} > "$file_path"`; the framework's highest-traffic task-file writer, so the torn-read window t1371 closed for `frontmatter_patch` remains wide open here.
- `.aitask-scripts/board/aitask_board.py:252` — `Task.save` writes with a plain `open(self.filepath, "w")`, reachable from ~10 call sites.
- `.aitask-scripts/board/aitask_merge.py:467` — `filepath.write_text(...)` writes the merged task file during sync conflict resolution.
- `.aitask-scripts/diffviewer/merge_screen.py:113` — `open(path, "w")` writing merged plan content into `aiplans/`.
- `.aitask-scripts/brainstorm/brainstorm_session.py:1537` — `out_path.write_text(...)` rewrites a proposal markdown file in place.

**Cross-device `mv` (degrades to a non-atomic copy+rename):**

- `.aitask-scripts/aitask_plan_verified.sh:187` and `.aitask-scripts/aitask_plan_externalize.sh:544,558` — `mv` a temp created under `$TMPDIR` onto the target.
- `.aitask-scripts/aitask_issue_import.sh:103` — same `$TMPDIR` + `mv` pattern onto a task file.

**Defective existing atomic writers** (also listed in t1281, which owns the
helper consolidation — fix there or here, but not twice):

- `.aitask-scripts/lib/gate_ledger.py:357` — `_atomic_write` builds its temp name from the PID without `O_EXCL`, so two threads in one process collide.
- `.aitask-scripts/lib/skill_template.py:258` — `_atomic_write` has no cleanup path, leaving a `.tmp` sibling behind whenever the write or rename fails.

**Missing write serialization (separate concern from atomicity):**

- No task-file-scoped write lock: `aitask_update.sh`, `Task.save` and `aitask_archive.sh` mutate task files without taking the global attach lock (`lib/attachment_lock.sh`), so they can lost-update a concurrent `ait artifact` / `ait attach` frontmatter write and vice versa. Atomic writes make such a loss clean rather than corrupt; they do not prevent it.

## Diagnostic context

From `aiplans/archived/p1371_atomic_frontmatter_patch_writes.md`.

t1365 moved `ait board`'s By-Trail discovery from the board-startup snapshot to
a live disk read, which exposed the write side: a board scan racing `ait
artifact new` saw the owning task file either cut mid-YAML
(`parse_frontmatter` raises) or truncated to zero bytes (it returns `None`).
`open(path, "w")` truncates *before* any bytes are written, so the empty-file
case is the likelier one.

t1365 hardened the reader; t1371 fixed the one writer named in it. The board's
reader guard is deliberately still in place *because* the writers listed above
were not converted — see the docstring on `_iter_active_task_frontmatter` in
`.aitask-scripts/board/aitask_board.py`, which now cites `write_task_file` and
`Task.save` as the reason both failure shapes remain reachable.

## Suggested fix

Route the Python sites through `.aitask-scripts/lib/atomic_write.py` (created by
t1371: `atomic_write(path, render)` / `atomic_write_text(path, text)`, with
`realpath`, mode preservation via `fchmod`, and cleanup on `BaseException`).
For the shell sites, create the temp in the *destination directory* rather than
`$TMPDIR` — `lib/artifact_cache.sh:103-104` and `aitask_projects.sh:203` already
use that pattern — so the rename cannot cross a filesystem boundary.

Coordinate with **t1281** (unify atomic write helpers) before touching
`gate_ledger.py` or `skill_template.py`: t1281 re-points those onto the shared
helper, which would fix both defects as a side effect.

The write-serialization item is a design question, not a mechanical fix, and may
deserve its own task: decide whether task-file mutation needs a lock scoped to
the task (rather than to the attach/artifact ledgers), and which writers must
take it.

`tests/test_atomic_write.py` (t1371) shows the test pattern — a hardlink probe
is what deterministically discriminates an in-place write from an atomic one.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T13:43:09Z status=pass attempt=1 type=human

> **✅ gate:review_approved** run=2026-08-03T19:29:20Z status=pass attempt=1 type=human
