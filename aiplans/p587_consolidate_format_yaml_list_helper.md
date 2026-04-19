---
Task: t587_consolidate_format_yaml_list_helper.md
Base branch: main
plan_verified: []
---

# Plan: Consolidate `format_yaml_list` helper (t587)

## Context

`format_yaml_list()` is defined twice (byte-identical) in
`.aitask-scripts/aitask_create.sh` and `.aitask-scripts/aitask_update.sh`.
In addition, `aitask_create.sh` defines `format_labels_yaml()` and
`format_file_references_yaml()` — both are byte-identical synonyms that
wrap the exact same body (comment text differs, body does not).

This task is a pure refactor: move the single canonical implementation
into `.aitask-scripts/lib/task_utils.sh` (alongside its inverse
`parse_yaml_list`, around line 106), delete all four local copies, and
rewrite the call sites of the two synonyms to use `format_yaml_list`
directly. Both scripts already source `lib/task_utils.sh`
(`aitask_create.sh:11`, `aitask_update.sh:11`), so no new sourcing is
required. Discovered while implementing t583_2 and deliberately deferred
to keep that diff focused.

**No behavior change.** Output is identical for every input.

## Files to Modify

### 1. `.aitask-scripts/lib/task_utils.sh` — Add the helper

Immediately after `parse_yaml_list()` (ends at line 109) and before the
`# --- Helper: read a YAML field from frontmatter ---` section (line
111), insert:

```bash
# Format a comma-separated string as a YAML inline list.
# "1,3,5" -> "[1, 3, 5]"; empty input -> "[]".
# Inverse of parse_yaml_list.
format_yaml_list() {
    local input="$1"
    if [[ -z "$input" ]]; then
        echo "[]"
    else
        echo "[$(echo "$input" | sed 's/,/, /g')]"
    fi
}
```

Use a short section header comment `# --- YAML List Formatting ---`
above the function, mirroring the existing `# --- YAML List Parsing ---`
header at line 102.

### 2. `.aitask-scripts/aitask_create.sh` — Delete all three local copies and rewrite synonym calls

- **Delete lines 1200–1228**: `format_yaml_list()`, `format_labels_yaml()`,
  `format_file_references_yaml()` — all three functions plus their
  blank separators. (The `# --- Step 6: Create Task File ---` comment at
  line 1194 and `get_timestamp()` at 1196–1198 stay; `dedup_file_refs()`
  at line 1232+ stays.)
- **Rewrite 4 synonym call sites** (labels) — replace
  `format_labels_yaml` with `format_yaml_list`:
  - Line 388: `labels_yaml=$(format_yaml_list "$labels")`
  - Line 476: `labels_yaml=$(format_yaml_list "$labels")`
  - Line 1410: `labels_yaml=$(format_yaml_list "$labels")`
- **Rewrite 3 synonym call sites** (file references) — replace
  `format_file_references_yaml` with `format_yaml_list`:
  - Line 408: `file_refs_yaml=$(format_yaml_list "$file_references")`
  - Line 494: `file_refs_yaml=$(format_yaml_list "$file_references")`
  - Line 1430: `file_refs_yaml=$(format_yaml_list "$file_references")`

Existing `format_yaml_list` call sites (331, 385, 402, 473, 489, 1407,
1424) need no change.

### 3. `.aitask-scripts/aitask_update.sh` — Delete local copy

- **Delete lines 410–418**: the `format_yaml_list()` function body.
- Keep the `# --- YAML Formatting ---` section header at line 404 and
  `get_timestamp()` at 406–408 — `get_timestamp` is still defined
  locally in both scripts and is out of scope for this task.

All 6 existing call sites (450, 453, 467, 473, 479, 485) continue to
work because `task_utils.sh` is sourced at line 11.

### 4. `tests/test_format_yaml_list.sh` — New test file

Create a new self-contained bash test that sources `task_utils.sh`
directly and exercises the function. No git/tempdir setup needed
(unlike `test_fold_file_refs_union.sh`) because `format_yaml_list` is a
pure string function.

Reuse the `assert_eq` / PASS/FAIL/TOTAL counter pattern from
`tests/test_fold_file_refs_union.sh:14–30,281–285` (the minimal bash
test style). Structure:

```bash
#!/usr/bin/env bash
# test_format_yaml_list.sh - Tests for format_yaml_list() in lib/task_utils.sh

set -e
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"

PASS=0; FAIL=0; TOTAL=0

assert_eq() { ... }  # identical to test_fold_file_refs_union.sh

# Cases:
assert_eq "empty -> []"                 "[]"          "$(format_yaml_list "")"
assert_eq "single entry -> [a]"         "[a]"         "$(format_yaml_list "a")"
assert_eq "single numeric -> [42]"      "[42]"        "$(format_yaml_list "42")"
assert_eq "two entries"                 "[1, 2]"      "$(format_yaml_list "1,2")"
assert_eq "three entries"               "[1, 3, 5]"   "$(format_yaml_list "1,3,5")"
assert_eq "labels multi"                "[ui, backend]" "$(format_yaml_list "ui,backend")"
assert_eq "file refs with colon/range"  "[foo.py, bar.py:10-20]" "$(format_yaml_list "foo.py,bar.py:10-20")"
# Summary: print Results line, exit non-zero on any FAIL
```

The cases (empty, single-entry, multi-entry, labels-shape,
file-references-shape) cover both inverses — confirming the single
helper replaces all three deleted functions.

## Reference Files

- `tests/test_fold_file_refs_union.sh` — bash test style template
  (assert_eq, PASS/FAIL counters, exit code).
- `.aitask-scripts/lib/task_utils.sh:106–109` — `parse_yaml_list`, the
  existing inverse next to which `format_yaml_list` will live.

## Verification

1. **Syntax check all touched scripts:**
   ```bash
   bash -n .aitask-scripts/lib/task_utils.sh
   bash -n .aitask-scripts/aitask_create.sh
   bash -n .aitask-scripts/aitask_update.sh
   bash -n tests/test_format_yaml_list.sh
   ```

2. **Run the new test:**
   ```bash
   bash tests/test_format_yaml_list.sh
   ```
   All cases should PASS; exit code 0.

3. **Run the related existing test** (exercises the same
   `task_utils.sh` via `aitask_fold_mark.sh`):
   ```bash
   bash tests/test_fold_file_refs_union.sh
   ```
   Should continue to PASS — no regression.

4. **Confirm no stale references** to the deleted synonyms:
   ```bash
   grep -rn "format_labels_yaml\|format_file_references_yaml" .aitask-scripts/ tests/
   ```
   Expect no output.

5. **Shellcheck clean** (per CLAUDE.md):
   ```bash
   shellcheck .aitask-scripts/aitask_create.sh \
              .aitask-scripts/aitask_update.sh \
              .aitask-scripts/lib/task_utils.sh
   ```
   No new warnings introduced.

6. **Smoke test via CLI** — create a throwaway task with labels and
   file refs to confirm the emitted YAML is unchanged (`labels: [a, b]`
   and `file_references: [x.py, y.py:1-10]`), then delete it. This
   exercises both rewritten call paths end-to-end.

## Step 9: Post-Implementation

Standard task-workflow Step 9 applies — no separate branch
(`create_worktree: false` from profile `fast`), commit with
`refactor: Consolidate format_yaml_list helper (t587)`, then
`/aitask-qa 587`, then archive.

## Final Implementation Notes

- **Actual work done:** Added `format_yaml_list()` to
  `.aitask-scripts/lib/task_utils.sh` under a new `# --- YAML List Formatting ---`
  section directly after `parse_yaml_list()` (its inverse). Deleted all
  four local copies: three from `aitask_create.sh` (`format_yaml_list`,
  `format_labels_yaml`, `format_file_references_yaml`, lines 1200–1228
  of the pre-change file) and one from `aitask_update.sh` (lines
  410–418). Rewrote the six synonym call sites in `aitask_create.sh`
  (three `format_labels_yaml` → `format_yaml_list` at 388/476/1410;
  three `format_file_references_yaml` → `format_yaml_list` at
  408/494/1430). Created `tests/test_format_yaml_list.sh` (10 asserts:
  empty, single-alpha, single-numeric, single-child-id, two/three
  numeric, labels, file-refs-with-colon-range, parse/format
  round-trip, syntax check).
- **Deviations from plan:** One minor cleanup beyond the plan: after
  deleting `format_yaml_list` from `aitask_update.sh`, the
  `# --- YAML Formatting ---` section header only covered the unrelated
  `get_timestamp()`, so the now-misleading header was removed too.
- **Issues encountered:** Initial test run failed with "lib/terminal_compat.sh: No such file or directory" because
  the test script set its own `SCRIPT_DIR` and `task_utils.sh`'s
  sourcing prologue reuses the variable via `${SCRIPT_DIR:-...}`. Fixed
  by renaming the test's variable to `TEST_DIR` to avoid the collision.
- **Key decisions:** Kept `get_timestamp()` in both scripts
  (out-of-scope, appears in each as a local helper). Put the new helper
  under its own `# --- YAML List Formatting ---` header mirroring the
  existing `# --- YAML List Parsing ---` header for parse_yaml_list.
  Test sources `task_utils.sh` directly (pure function, no tempdir/git
  scaffolding needed).
- **Verification:** `bash tests/test_format_yaml_list.sh` — 10/10
  passed. `bash tests/test_fold_file_refs_union.sh` — 13/13 passed (no
  regression). `bash -n` clean on all four touched files. Smoke test
  via `aitask_create.sh --batch` with `--labels "ui,backend"` and two
  `--file-ref` flags produced exactly `labels: [ui, backend]` and
  `file_references: [foo.py, bar.py:10-20]`, confirming byte-identical
  output.
