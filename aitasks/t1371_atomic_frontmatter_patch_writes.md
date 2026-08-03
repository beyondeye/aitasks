---
priority: medium
risk_code_health: low
risk_goal_achievement: low
effort: low
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
created_at: 2026-08-02 22:55
updated_at: 2026-08-03 10:40
---

## Origin

Spawned from t1365 during Step 8b review.

## Upstream defect

`.aitask-scripts/lib/frontmatter_patch.py:214,238` — `cmd_add` / `cmd_remove`
rewrite the task file with a plain `open(path, "w")` (truncate-then-write)
instead of a temp-file + atomic rename, so any concurrent reader can observe an
empty or partially written task file.

## Diagnostic context

t1365 fixed `ait board`'s By-Trail trail discovery, which had been reading
active task frontmatter from a board-startup snapshot. Moving discovery to a
live disk read exposed the write side: `ait artifact new` patches the owning
task's `artifacts:` frontmatter through `frontmatter_patch.py`, and a board scan
racing that write can see the file in one of two broken states:

- cut mid-YAML — `parse_frontmatter` raises `yaml.parser.ParserError`;
- truncated to zero bytes or cut before the closing `---` — `parse_frontmatter`
  returns `None`.

The truncate-to-empty case is the likelier of the two, because `open(path, "w")`
truncates *before* any bytes are written.

t1365 hardened the **reader**: the board's discovery scan now guards every file,
reports the ones it could not read, and refuses to report an empty-but-errored
scan as "no trails" (see `_iter_active_task_frontmatter` in
`.aitask-scripts/board/aitask_board.py`). That is a per-consumer mitigation. The
write site is still non-atomic, and every *other* frontmatter reader in the
framework remains exposed to the same window with no such guard.

## Suggested fix

Write to a temp file in the same directory and `os.replace()` it over the
target, so readers observe either the old file or the new one and never a
partial state. Both `cmd_add` and `cmd_remove` need it. Worth checking whether
other in-place frontmatter writers share the pattern, and whether a single
shared `atomic_write_text()` helper is the right home for it.

## Gate Runs
<!-- Appended by the gate framework. Do not edit by hand; use `./.aitask-scripts/aitask_gate.sh append` for corrections. -->

> **✅ gate:plan_approved** run=2026-08-03T07:40:27Z status=pass attempt=1 type=human
