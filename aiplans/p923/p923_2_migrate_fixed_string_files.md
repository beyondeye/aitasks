---
Task: t923_2_migrate_fixed_string_files.md
Parent Task: aitasks/t923_consolidate_test_assert_helpers_shared_lib.md
Sibling Tasks: aitasks/t923/t923_1_*.md, aitasks/t923/t923_3_*.md, aitasks/t923/t923_4_*.md, aitasks/t923/t923_5_*.md
Archived Sibling Plans: aiplans/archived/p923/p923_1_*.md
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-03 12:51
---

# Plan: Migrate fixed-string (`grep -qF`) files (t923_2)

Depends on 923_1 (landed). **Read `aiplans/archived/p923/p923_1_*.md` first** for
the `asserts.sh` API, the `assert_migration_verify.sh` invocation, and the exact
block-removal/source-insertion recipe — this plan reuses that recipe verbatim.

The simplest bucket: these files' inline `assert_contains` / `assert_not_contains`
already use fixed-string matching, so their call sites map directly to the shared
**default** `assert_contains` / `assert_not_contains` — no `_ci`/`_re` remap.

## Context

t920 added a `--` end-of-options guard to `assert_contains`/`assert_not_contains`
across the suite and had to touch ~70 inline copies because there is no shared
assert library. 923_1 built that library (`tests/lib/asserts.sh`), a before/after
verification harness (`tests/lib/assert_migration_verify.sh`), and migrated a
10-file pilot. This child migrates the largest, cleanest bucket — files whose
inline `assert_contains` uses fixed-string `grep -qF`.

## Verify-pass findings (2026-06-03 — re-checked against the current codebase)

- **Foundation present and working.** `tests/lib/asserts.sh` exists with the full
  documented API (14 functions: `assert_eq`, `assert_eq_trim`, `assert_contains`
  /`_ci`/`_re` + `_not_` variants, `assert_exit_zero`/`_nonzero`, the four
  `assert_{file,dir}_{exists,not_exists}`). `tests/lib/assert_migration_verify.sh`
  exists; a snapshot→check smoke test on two fixed files returned `VERIFY OK`,
  exit 0.
- **FIXED bucket = 62 files (not "~66").** Reconciles exactly: 923_1 measured 136
  files defining `assert_contains` inline (66 fixed / 33 ci / 26 regex / 4 other);
  the 10-file pilot removed 10 inline defs (4 of them fixed), leaving 126 inline
  and **62 fixed**. The file list is regenerated mechanically in Step 1 below — do
  not trust a hardcoded list.
- **No `assert_not_contains` flavor mismatch.** Across all 126 inline-defining
  files, zero have an `assert_not_contains` whose grep flavor differs from their
  `assert_contains`. The per-call-site "watch for" case from the original plan
  does not occur in the current suite, but the harness still backstops it.
- **FINDING A — `assert_eq_trim` remap applies to this bucket (original plan
  omitted it).** 923_1's FINDING 4: files whose inline `assert_eq` trims via
  `xargs`/`tr` must remap to `assert_eq_trim` (the trim absorbs BSD `wc -l`
  leading-space padding on macOS; the default `assert_eq` does not trim). Four
  FIXED-bucket files trim and **must** use `assert_eq_trim`:
  `tests/test_auto_merge_file_ref.sh`, `tests/test_file_references.sh`,
  `tests/test_issue_import_contributor.sh`, `tests/test_merge_issues.sh`. All
  four trim with `echo "$x" | xargs`. The other 58 files keep the default
  `assert_eq`. (Regenerate this trim list in Step 1 — see command.)
- **FINDING B — anchor source insertion on `PROJECT_DIR`, not the scaffold line.**
  The original plan said "insert the `asserts.sh` source after the
  `test_scaffold.sh` source", but **42 of the 62 fixed files never source
  `test_scaffold.sh`** — they compute `PROJECT_DIR` inline. All 62 define
  `PROJECT_DIR`. Per 923_1's proven recipe, anchor the `. "$PROJECT_DIR/tests/lib/asserts.sh"`
  insertion on the line that defines/sources `PROJECT_DIR` (right after the
  scaffold source when present, otherwise right after the inline `PROJECT_DIR=…`
  computation).

## Step 1 — Regenerate the file lists

Bucketing (scope the grep-flavor probe to each function body, catch all flag
orderings — `-qF`, `-Fq`, `-F -q`):

```bash
classify_body() {  # $1=file $2=func
  awk -v fn="$2" '
    $0 ~ "^"fn"\\(\\)" {inf=1; next}
    inf && /^}/ {exit}
    inf && /^assert_/ {exit}
    inf && /grep[[:space:]]+-/ {print; exit}
  ' "$1"
}
for f in tests/test_*.sh; do
  grep -qE '^assert_contains\(\)' "$f" || continue
  l=$(classify_body "$f" assert_contains)
  if   echo "$l" | grep -qE 'grep[^|]*-[a-zA-Z]*i'; then continue          # ci
  elif echo "$l" | grep -qE 'grep[^|]*-[a-zA-Z]*F'; then echo "$f"         # FIXED
  fi
done
```

Trim-`assert_eq` sublist (these remap to `assert_eq_trim`):

```bash
while read -r f; do
  awk '/^assert_eq\(\)/{i=1} i{print} i&&/^}/{exit}' "$f" \
    | grep -qE 'xargs|tr -d|tr -s' && echo "TRIM: $f"
done < <fixed_list>
```

Exclude any fixed file already migrated in 923_1's pilot (`test_aitask_merge.sh`,
`test_agent_instructions.sh`, `test_aitask_projects_doctor.sh`,
`test_aitask_projects_remove.sh`) — they no longer define the helpers inline, so
the bucketing command already skips them.

## Step 2 — Migrate in verified batches (~15–20 files)

For each batch:

1. `tests/lib/assert_migration_verify.sh snapshot <baseline> <files...>`.
2. Per file (block-removal/insertion done with the editor, **never `sed -i`** —
   stay off BSD sed):
   - Insert `. "$PROJECT_DIR/tests/lib/asserts.sh"` anchored on the `PROJECT_DIR`
     line (FINDING B): immediately after `. "$PROJECT_DIR/tests/lib/test_scaffold.sh"`
     when present, otherwise immediately after the inline `PROJECT_DIR=…` line.
   - Delete the inline definitions the lib now provides (`assert_eq`,
     `assert_contains`, `assert_not_contains`, and any of `assert_exit_zero/nonzero`,
     `assert_file_exists/not_exists`, `assert_dir_exists/not_exists` the file
     defines). **Keep** file-local `PASS=0/FAIL=0/TOTAL=0` (the lib references
     these globals; it does not declare them), single-use/domain helpers, and any
     synonym-named exit helpers (synonyms are 923_5's job).
   - **Call-site remaps:** fixed `assert_contains`/`assert_not_contains` → default
     (no rename). **Trim files (FINDING A): remap `assert_eq` → `assert_eq_trim`**
     for the 4 files listed above; non-trim files keep the default `assert_eq`.
   - **Per-call-site flavor guard:** if any individual `assert_not_contains` (or
     `assert_contains`) call in a fixed file is actually a different flavor,
     remap that call to the matching `_ci`/`_re` variant. Per-call-site, not
     per-file. (None expected — verify finding shows no per-file mismatch — but
     keep the guard.)
3. `tests/lib/assert_migration_verify.sh check <baseline> <files...>` — FAIL count
   + exit status MUST be identical for every file. Investigate ANY delta before
   committing.
4. `shellcheck` a sample of the batch clean (modulo pre-existing info notes).
5. Commit the batch with plain `git` (code files, not `./ait git`):
   `refactor: Consolidate fixed-string assert helpers, batch N (t923_2)`.

## Step 3 — Verify

- Standalone FAIL-count + exit identical before vs after for every migrated file
  (the harness is the gate).
- Migrated files no longer define the consolidated helpers inline:
  `grep -rlE '^assert_contains\(\)' tests/` should not list any migrated file.
- The 4 trim files use `assert_eq_trim` at their `assert_eq` call sites.
- `shellcheck` clean on a sample.

## Risk

### Code-health risk: low
- Wide blast radius (62 files), but each change is a pure, mechanical
  consolidation individually gated by the before/after harness (FAIL-count + exit
  must match) — a regression cannot reach a commit undetected. · severity: low ·
  → mitigation: in-task verify harness (923_1 deliverable), run per batch.
- macOS-only `assert_eq` trim drift: the 4 trim files must use `assert_eq_trim`,
  and this Linux machine cannot exercise the BSD `wc -l` padding path that makes
  the distinction matter. · severity: low · → mitigation: the trim files are
  enumerated up front (FINDING A) and mapped to `assert_eq_trim`; the harness
  catches any local count divergence.

### Goal-achievement risk: low
- Goal is narrow and well-scoped (migrate the fixed bucket count-neutrally) and
  the recipe is already proven on 923_1's 10-file pilot. No material concern.
  · severity: low · → mitigation: none needed (harness-verified).

_No before/after mitigation tasks: the principal risk (semantic drift across a
wide blast radius) is mitigated in-task by 923_1's verification harness, re-run
on every migrated file. This mirrors 923_1's own risk framing._

## Final Implementation Notes

- **Actual work done:** Migrated **61 of the 62** fixed-string files to source
  `tests/lib/asserts.sh`, in 4 harness-verified batches (commits
  `26834e81`, `db9a8f1b`, `4adbd718`, `85aba234`). Removed the inline
  `assert_eq` / `assert_contains` / `assert_not_contains` (and any inline
  `assert_exit_*` / `assert_file_*` / `assert_dir_*`) definitions; kept
  file-local `PASS/FAIL/TOTAL` and all domain helpers
  (`assert_exit_code`, `setup_*`, etc.). Net **−1,825 lines** (207 ins /
  2032 del). Every batch passed `assert_migration_verify.sh check` (FAIL-count
  + exit identical before vs after); `shellcheck` introduced no new
  warnings/errors (each pre-existing note confirmed via HEAD~1 comparison).
- **assert_eq_trim remap (923_1 FINDING 4 — applied):** the 4 trimming-`assert_eq`
  files had **all** their `assert_eq` call sites remapped to `assert_eq_trim`
  (verified: 0 bare `assert_eq` calls remain):
  `test_auto_merge_file_ref.sh` (19), `test_file_references.sh` (9),
  `test_issue_import_contributor.sh` (51), `test_merge_issues.sh` (6).
  The other 57 files kept the default `assert_eq`. This was the key gap in the
  original plan, surfaced during plan verification.
- **Insertion anchor (FINDING B — applied):** followed 923_1's pilot convention —
  replaced the inline helper block in-place with a comment +
  `. "$PROJECT_DIR/tests/lib/asserts.sh"`, rather than anchoring on the
  scaffold source line (42/62 files don't source `test_scaffold.sh`). This
  works because the source lands after `PROJECT_DIR` is defined in all
  clean files.
- **Deviations from plan — 1 file deferred to 923_5:**
  **`test_opencode_setup.sh`** is a straggler, NOT migrated here. It (a) defines
  its helpers *before* `PROJECT_DIR` is computed and (b) runs `set -euo pipefail`
  with **no `TOTAL` counter init** and echoes `PASS:` on success — a different
  helper shape. Naively migrating it broke it (`PROJECT_DIR: unbound variable`,
  caught by the harness on batch 2). Cleanly migrating it needs two special
  fixes (source after the dir def + add `TOTAL=0`), which is outside 923_2's
  clean-default scope. **923_5 (synonyms/stragglers/final gates) should handle
  it.**
- **Issues encountered:** only the straggler above; the harness caught it
  immediately. All other 61 files migrated mechanically with no count drift.
- **Key decisions:** used a portable Python migration helper (not committed;
  avoids BSD `sed -i` per 923_1) that removes the consolidated-helper blocks by
  column-0 `}` boundary and, for trim files, remaps `\bassert_eq\b` →
  `assert_eq_trim` (the `\b` won't touch `assert_eq_trim` — trailing `_` is a
  word char). The before/after harness was the correctness gate per batch.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:** 57/61 migrated cleanly with the default helpers;
  4 needed the `assert_eq_trim` remap (above). The **non-standard helper shape**
  (no `TOTAL`, echoes `PASS:`, `set -u`) is the thing to watch for in 923_3/923_4
  too — before migrating a file, confirm `PROJECT_DIR` (or its dir var) is
  defined *before* the insertion point and that a `set -u` file initializes
  `TOTAL`. 923_3/923_4 reuse this exact recipe with `_ci`/`_re` call-site
  remapping (this bucket needed none — no per-file flavor mismatch exists in the
  current suite). The session's `/tmp/migrate_asserts.py` can be adapted (add a
  flavor-rename mode). One straggler (`test_opencode_setup.sh`) is left for
  923_5.

## Step 9 (Post-Implementation)

Standard cleanup/archival/merge per `task-workflow` Step 9.
