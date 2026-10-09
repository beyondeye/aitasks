---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [codeagent, models, model_selection]
anchor: 1916
followup_kind: upstream_defect
created_at: 2026-10-09 16:09
updated_at: 2026-10-09 16:09
---

## Origin

Spawned from t1927 during Step 8b review.

## Upstream defect

- `.aitask-scripts/aitask_add_model.sh:331-339` — `promote-config` writes the
  project config, then the seed config, then the supersession table, one
  `commit_staged` at a time. If the table write fails after the seed write
  succeeded, the promotion is applied but its supersession edge is not, and
  re-running `promote-config` cannot repair it: it derives predecessors from
  the seed's *current* values, which already name the new model, so it records
  nothing. The lineage is silently lost.

## Diagnostic context

Found while designing t1927's add-model failure handling. The user judged this
a rare condition (the table write is an atomic tempfile + `mv` into
`.aitask-scripts/lib/`, after two successful writes into the same kind of
location) and asked for a **basic fix only**. Recovery stays manual. General
promotion recovery, partial-write detection and concurrency handling are out
of scope.

## Scope: basic fix

1. In `cmd_promote_config`, when the table write (`commit_staged "$tmp_table"
   "$table_file"`, ~L338) fails, print — before `die` — the exact
   `record-supersession` command for every edge the promotion had computed, so
   the user can restore each `old → new` link once the cause is fixed:
   `./.aitask-scripts/aitask_add_model.sh record-supersession --agent <agent> --old <old> --new <new>`
   The edges come from the `RECORDED:<agent>/<old>-><agent>/<new>` lines
   already in `$record_out` (`RECORDED_SIBLING:` lines too, since `_1m`
   siblings are separate edges). Say plainly that the config writes were applied
   and only the table was not.
2. A failure test in `tests/test_add_model.sh`: make the fixture's
   `.aitask-scripts/lib/` unwritable (pattern: Test 9's `chmod 500` on `seed/`).
   Run a promotion that records an edge. Assert exit 1, that the output contains
   the exact retry command, and that running that command after restoring
   permissions records the edge.

A few dozen lines plus the test.

## Verification

- `bash tests/test_add_model.sh`
- `shellcheck .aitask-scripts/aitask_add_model.sh`
