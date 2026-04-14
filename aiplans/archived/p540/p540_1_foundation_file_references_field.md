---
Task: t540_1_foundation_file_references_field.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_2_*.md, aitasks/t540/t540_3_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_1: `file_references` foundation (verified)

## Context

Today `aitask_create.sh` only accepts file attachments by dumping raw paths into the description body — no structured field, no line ranges, no way for other tooling to find "tasks that reference file X". t540 introduces a YAML list `file_references` on the task frontmatter (1-indexed inclusive line numbers). This is the foundation every other t540 child (except t540_2 and t540_6) depends on. It must land before t540_3, t540_4, t540_5, t540_7.

This plan has been verified against the current codebase. It corrects two location drifts from the initial plan and pins implementation to existing helpers. It also encodes the compact-no-union format decision (see Design).

## Design

- **Format:** YAML list of strings, mirroring `labels` / `depends` / `children_to_implement`.
- **Entry syntax:** `path` | `path:RANGE_SPEC` where `RANGE_SPEC` is `N(-M)?(^N(-M)?)*` — i.e., a single line number or `N-M` range, optionally followed by more ranges joined by `^`. Example: `foo.py:10-20^30-40^89-100`. Line numbers are 1-indexed, inclusive.
- **Append semantics:** `--file-ref` always appends; no "replace-all" flag in the first pass.
- **Dedup:** exact-string match only. `foo.py:10-20^30-40` and `foo.py:10-20^30-40` dedup; `foo.py:10-20^30-40` and `foo.py:30-40^10-20` do NOT (order-sensitive). Adding `foo.py:15-25` when `foo.py:10-20^30-40` exists just creates a second entry — no range-union merging in this task (deferred; may never be needed).
- **Line-range-agnostic search:** `aitask_find_by_file.sh` matches by stripping everything from the first `:` onward — two entries for the same path with different range specs both count as the same file reference.
- **Validation:** CLI rejects malformed entries at parse time. Regex: `^[^:]+(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)?$`.

## Corrections vs. the initial plan

The initial plan was 95% correct. Two anchors drifted and one helper reference was wrong:

1. **Child task writer location.** Initial plan said "child-task creation path at ~1300-1356". Actual: `create_child_task_file()` at `aitask_create.sh:338-400`, frontmatter block at lines 371-397. Insert `file_references:` after line 378 (`labels:`).
2. **`write_task_file` lives in `aitask_update.sh`, not `lib/task_utils.sh`.** Defined at `aitask_update.sh:390-479` with 20 positional params. Add `file_references` as a 21st optional param and emit it right after `labels:` at line 429 (behind an `if [[ -n ... ]]` guard, matching existing optional-field convention).
3. **Model for `get_file_references()` is `extract_related_issues()`, not `get_user_email()`.** The initial plan referenced `get_user_email()` at `lib/task_utils.sh:164-169`, but that's a scalar extractor. `extract_related_issues()` at `lib/task_utils.sh:445-468` already parses a YAML list field with exactly the style we need (strip brackets, split on comma, trim quotes). Mirror that.

## Key files to modify

### 1. `.aitask-scripts/lib/task_utils.sh` — new helpers

Add two helpers:

- **`get_file_references()`** — modeled on `extract_related_issues()` (lines 445-468 in the same file). Output: one entry per line, verbatim — the caller is responsible for splitting path / range-spec / individual ranges. Empty output when the field is absent.
- **`validate_file_ref()`** — takes a single candidate entry and `die`s with a clear error if it does not match `^[^:]+(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)?$`. Used by both `aitask_create.sh` and `aitask_update.sh` at CLI parse time.

The existing `_AIT_TASK_UTILS_LOADED` guard at lines 4-6 already protects against double-sourcing — no new guard variable needed.

### 2. `.aitask-scripts/aitask_update.sh` — parse + process + write

- **`parse_yaml_frontmatter()` (lines 263-362):** Add `CURRENT_FILE_REFERENCES=""` to the reset block (around line 283), and add a `file_references) CURRENT_FILE_REFERENCES=$(parse_yaml_list "$value") ;;` case to the switch (around line 348, next to `folded_tasks`).
- **New `process_file_references_operations()`:** Add right after `process_children_operations()` at line 635. Mirror `process_children_operations` exactly, but accept an append-only `add_ref` list and a `remove_ref` list (the rule is "append always, no replace-all flag"). Dedup by exact-string on append. Returns a comma-separated string.
- **`write_task_file()` (lines 390-479):** Add `local file_references="${21:-}"` after line 410, and emit after `labels:` at line 429:
  ```bash
  # Only write file_references if present
  if [[ -n "$file_references" ]]; then
      local file_references_yaml
      file_references_yaml=$(format_yaml_list "$file_references")
      echo "file_references: $file_references_yaml"
  fi
  ```
- **`parse_args()` (lines 177-223):** Add two flags next to `--add-child` / `--remove-child` (lines 192-193):
  ```bash
  --file-ref) validate_file_ref "$2"; BATCH_ADD_FILE_REFS+=("$2"); shift 2 ;;
  --remove-file-ref) validate_file_ref "$2"; BATCH_REMOVE_FILE_REFS+=("$2"); shift 2 ;;
  ```
  Declare the two arrays at the top of the script where `BATCH_ADD_LABELS` / `BATCH_REMOVE_LABELS` are declared.
- **Update all 3 `write_task_file` call sites** to pass `CURRENT_FILE_REFERENCES` (or the processed result) as the 21st arg: lines 688, 1140, 1364.
- **At the main update flow** (around line 1278 where label/children ops run), call `process_file_references_operations` and assign its output to a local that's passed to `write_task_file` at line 1364.

### 3. `.aitask-scripts/aitask_create.sh` — emit on create

- **Usage / help (`show_help()` at lines 52-112):** Document `--file-ref PATH[:RANGE_SPEC]` (repeatable), mentioning the `^` multi-range syntax.
- **`parse_args()` (lines 115-142):** Add `--file-ref) validate_file_ref "$2"; BATCH_FILE_REFS+=("$2"); shift 2 ;;` — model after `--labels` at line 126. Declare `BATCH_FILE_REFS=()` at the top with the other `BATCH_*` arrays (check around line 44 for placement).
- **Interactive file-attach flow (lines 1036-1082):** At line 1079 where `current_round_refs+=("$selected_file")` runs, also append to `BATCH_FILE_REFS`:
  ```bash
  BATCH_FILE_REFS+=("$selected_file")
  ```
- **`format_file_references_yaml()`:** Add next to `format_labels_yaml()` at lines 1112-1120. Same body as `format_labels_yaml`, just the name differs.
- **`create_task_file()` (lines 1122-1184):** Convert `BATCH_FILE_REFS[@]` to a comma-separated string (dedup by exact-string using a bash assoc-array), format with `format_file_references_yaml`, and emit after `labels: $labels_yaml` at line 1158 — guard with `if [[ -n "$file_refs" ]]` so empty lists are omitted (matches the existing `assigned_to` pattern).
- **`create_child_task_file()` (lines 338-400):** Same pattern. Add `file_references` as a new trailing positional param, and emit right after `labels: $labels_yaml` at line 378 (same guard).
- **Both emit sites MUST dedup before serializing** — `foo.py:10-20` appearing twice in `BATCH_FILE_REFS` should produce a single entry. The codebase already requires bash 5.x via `#!/usr/bin/env bash` so `declare -A` is safe.

### 4. `.aitask-scripts/aitask_find_by_file.sh` — new script

Model structured output on `aitask_query_files.sh` / `aitask_fold_validate.sh`:

- Usage: `aitask_find_by_file.sh <path>`
- Source `lib/task_utils.sh` for `get_file_references()`.
- Scan `aitasks/*.md` and `aitasks/t*/t*_*.md` — **NOT** `aitasks/archived/`.
- For each task file: read `status` via the same parse approach `aitask_fold_validate.sh` uses; skip unless status is `Ready` or `Editing`. Skip `Implementing`, `Postponed`, `Done`, `Folded`.
- Read `file_references` via `get_file_references`; if any entry's path-only portion (strip from the first `:` onward) matches `<path>`, emit `TASK:<task_id>:<task_file>` on its own line.
- Exit 0 on no matches (silent). Exit non-zero only on argument errors.

### 5. `tests/test_file_references.sh` — new test

Model on `tests/test_verified_update.sh` (closest structural match for batch flag testing on list fields). Cases:

1. Batch create with single `--file-ref foo.py` → frontmatter has `file_references: [foo.py]`.
2. Batch create with multiple mixed refs `--file-ref a.py --file-ref b.py:10-20` → list in order, brackets, no quoting drift.
3. Batch create with compact multi-range `--file-ref foo.py:10-20^30-40^89-100` → single entry preserved verbatim in frontmatter.
4. Batch create with the same ref twice (exact string) → deduped on write.
5. Batch create with `foo.py:10-20^30-40` and `foo.py:30-40^10-20` → **two** entries (order-sensitive exact dedup; documented behavior).
6. Batch update `--file-ref c.py` on existing task → appended.
7. Batch update `--remove-file-ref a.py` → removed.
8. `get_file_references` round-trip: create → parse back via the helper.
9. `aitask_find_by_file.sh a.py` → returns `Ready` tasks with entries starting with `a.py:` or exactly `a.py` (path-only match; compact multi-range entries `a.py:10-20^30-40` are also hits).
10. Status filter: a task with status `Postponed`, `Done`, `Folded`, or `Implementing` is NOT returned even when it references the file.
11. Malformed input rejection: `--file-ref foo.py:abc` exits non-zero with a clear error; `--file-ref foo.py:10-20^bad` same.

## Implementation sequence

1. `lib/task_utils.sh` — add `get_file_references` (mirrors `extract_related_issues`) and `validate_file_ref`.
2. `aitask_update.sh` — extend `parse_yaml_frontmatter`, add `process_file_references_operations`, extend `write_task_file` (+ update 3 call sites), add `--file-ref` / `--remove-file-ref` to `parse_args`, wire into main update flow.
3. `aitask_create.sh` — declare `BATCH_FILE_REFS`, add `--file-ref` to `parse_args` and `show_help`, add `format_file_references_yaml`, emit in both `create_task_file` and `create_child_task_file`, populate from interactive file-attach loop.
4. `aitask_find_by_file.sh` — new file, source `lib/task_utils.sh`, implement scan.
5. `tests/test_file_references.sh` — all eleven cases.
6. `shellcheck` on everything touched.

## Verification

- `bash tests/test_file_references.sh` — PASS.
- Regression: `bash tests/test_draft_finalize.sh` — PASS (the closest existing test that exercises frontmatter round-tripping).
- `shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_find_by_file.sh .aitask-scripts/lib/task_utils.sh` — clean.
- Manual smoke:
  ```bash
  ./.aitask-scripts/aitask_create.sh --batch --commit \
    --name tmp --priority low --effort low --type chore --labels testing \
    --file-ref foo.py:10-20 --file-ref bar.py --desc "x"
  ```
  Inspect the created task file — frontmatter should contain `file_references: [foo.py:10-20, bar.py]`.
- Manual:
  ```bash
  ./.aitask-scripts/aitask_find_by_file.sh foo.py
  ```
  Returns the task above; after flipping its status to `Folded` via `aitask_update.sh`, the helper no longer returns it.

## Out of scope

- Fold-time union of `file_references` — t540_7.
- Board widget rendering (and compact display collapse of multiple same-path entries) — t540_5.
- `aitask_create.sh` auto-merge logic — t540_3.
- Codebrowser integration — t540_4.
- **Range-union merging** — deliberately deferred. If `foo.py:10-20` and `foo.py:15-25` both exist, they stay as separate entries. A future task can introduce a normalization pass if real usage shows drift is a problem.

## Post-implementation

Standard archival via `./.aitask-scripts/aitask_archive.sh 540_1` per task-workflow Step 9. The archived plan file will serve as the primary reference for t540_3, t540_4, t540_5, t540_7 — include a comprehensive **Final Implementation Notes** section during Step 8 that explicitly documents the compact-no-union format decision (entry syntax, exact-string dedup rule, and the deliberate deferral of range-union), so subsequent siblings can align without re-litigating.

**Sibling plan drift note:** The existing `aiplans/p540/p540_3_*.md`, `p540_5_*.md`, and `p540_7_*.md` plan files were written assuming the pre-decision flat format. They should be re-verified (via `plan_preference_child: verify`) when those child tasks are picked — the format decision here may cascade small changes into their logic (especially t540_7's fold union, which now stays as exact-string dedup rather than range-union).

## Final Implementation Notes

- **Actual work done:**
  - `lib/task_utils.sh`: added `get_file_references()` (mirrors `extract_related_issues`) and `validate_file_ref()` (regex `^[^:]+(:[0-9]+(-[0-9]+)?(\^[0-9]+(-[0-9]+)?)*)?$`).
  - `aitask_update.sh`: added `BATCH_ADD_FILE_REFS` / `BATCH_REMOVE_FILE_REFS` arrays, `--file-ref` / `--remove-file-ref` flags, `CURRENT_FILE_REFERENCES` global, a `file_references)` case in `parse_yaml_frontmatter`, new `process_file_references_operations()` helper, 21st optional `file_references` param on `write_task_file` (emitted after `labels:`, behind an `if [[ -n ... ]]` guard), `has_update` check extended to include the two new arrays, and all 3 `write_task_file` call sites updated to pass `new_file_references`.
  - `aitask_create.sh`: added `BATCH_FILE_REFS=()`, `--file-ref` flag, new `format_file_references_yaml()` (mirrors `format_labels_yaml`), new `dedup_file_refs()` helper (bash assoc-array, preserves first-occurrence order), `file_references` trailing param on `create_task_file` / `create_child_task_file` / `create_draft_file`, emission blocks after `labels:` in all three, dedup'd call-site wiring for all 3 batch paths, and a marker-based channel (`__FILE_REFS_MARKER__`) to propagate structured refs from the interactive `get_task_definition` subshell back to `run_draft_interactive`.
  - `aitask_find_by_file.sh`: new script — path-only match, scans `aitasks/*.md` and `aitasks/t*/t*_*.md` (skips `archived/`), filters by `read_task_status` (only `Ready` / `Editing` emitted), outputs `TASK:<task_id>:<task_file>`.
  - `tests/test_file_references.sh`: 21 cases covering single/multi/compact/dedup/order-sensitive/update-append/update-remove/helper-round-trip/find-hit/find-miss/status-filter/malformed-rejection/syntax-check. **21/21 passing.**
  - `aiplans/p540/p540_1_foundation_file_references_field.md`: rewrote in verify mode with the compact-no-union decision captured.

- **Format decision (LOCKED — do not re-litigate in siblings):**
  - **Entry syntax:** `path` | `path:RANGE_SPEC`, where `RANGE_SPEC = N(-M)?(^N(-M)?)*`. Line numbers are 1-indexed, inclusive.
  - **Dedup:** exact-string match only. Order-sensitive: `foo.py:10-20^30-40` and `foo.py:30-40^10-20` are distinct entries.
  - **No range-union merging:** `foo.py:10-20` and `foo.py:15-25` stay as two entries. Deferred indefinitely until real usage demonstrates drift is a problem.
  - **Line-range-agnostic search:** `aitask_find_by_file.sh` strips from the first `:` onward for matching — compact multi-range entries still count as a file-path hit.
  - This rule set must be honored by t540_3 (auto-merge), t540_5 (board rendering), and t540_7 (fold-time union, which in this framing becomes exact-string union).

- **Deviations from plan:**
  - **`has_update` check in `aitask_update.sh`:** the initial plan did not call out that `run_batch_mode`'s `has_update` gate had to be extended to include the new arrays. Without this, `--file-ref` / `--remove-file-ref` used as the *only* update flag caused the script to die with "No update parameters specified". Caught by test 6 during the first test run. Fix added at `aitask_update.sh:1300-1301`.
  - **Pre-existing bug at interactive-update `write_task_file` call site (line ~1209):** the second call to `write_task_file` in the interactive update flow was passing 19 args instead of 20 (`implemented_with` was omitted). Since I needed to add `file_references` as a 21st positional arg with aligned positions, I had to also pass `CURRENT_IMPLEMENTED_WITH` — fixing the pre-existing omission as a necessary side effect, not scope creep.
  - **Interactive flow cross-subshell channel:** `get_task_definition` in `aitask_create.sh` is called via command substitution, so a naive `BATCH_FILE_REFS+=("$selected_file")` from inside that subshell cannot propagate back. Introduced a marker-based protocol: `get_task_definition` prints `task_desc`, a literal `__FILE_REFS_MARKER__` separator, then one ref per line. `run_draft_interactive` splits on the marker and feeds the collected refs through `dedup_file_refs` before calling `create_draft_file`. Outer-scope `all_file_refs` array tracks across rounds so removals in the same round are reflected at emit time.
  - **Empty-entry edge in `get_file_references`:** the helper strips brackets and trims quotes; the implementation had to handle both `file_references: []` (empty list, emit nothing) and missing-field (no match, emit nothing) without a wrapping guard fork.

- **Issues encountered:**
  - Test 6/7 initially failed silently — the root cause was the `has_update` gate, not the processor itself. Detection flow: update command exited non-zero (swallowed by `>/dev/null 2>&1` in the test), file stayed unchanged, test assertion saw pre-update content.
  - The test harness needed `archive_utils.sh` AND `archive_scan.sh` copied into the isolated repo for `aitask_claim_id.sh --init` and `aitask_create.sh --commit` to work. Pre-existing `test_draft_finalize.sh` also fails to include these and is broken on `main` (25 failures) — **not caused by this task**; a follow-up task should fix the harness.
  - `shellcheck` surfaced three new SC2001 notes at lines 1144/1154/1164 of `aitask_create.sh` (suggesting `${var//search/replace}` instead of `sed 's/,/, /g'`). These are `info`-level only and mirror the pre-existing `format_yaml_list` / `format_labels_yaml` pattern — left as-is for symmetry. Shellcheck `warning`/`error` count is identical on main and on this branch.

- **Key decisions:**
  - **Positional-param growth** for `write_task_file`/`create_task_file` rather than introducing an options-object pattern: the existing codebase uses 14–20 positional args across multiple call sites, so staying consistent was simpler than a refactor. A future task may consolidate all frontmatter writers into a single struct-passing helper.
  - **Exact-string dedup, order-sensitive:** simpler to implement and audit, and avoids any notion of "range normalization" that would force a canonical form. If two authors add `foo.py:10-20^30-40` and `foo.py:30-40^10-20`, both entries stay — the extra noise is acceptable and obvious to a reader.
  - **Bash assoc-array for dedup (`declare -A`)** requires bash 4+; the codebase already requires bash 5.x via `#!/usr/bin/env bash` per `CLAUDE.md` shebang convention, so this is safe. No macOS portability concern.
  - **`aitask_find_by_file.sh` status filter:** only `Ready` / `Editing` are returned. `Implementing` is excluded because the point of the helper is "find pending work that touches this file" — an in-flight task is not pending. This matches the framing in the plan.

- **Notes for sibling tasks:**
  - **t540_3 (auto-merge):** when deciding whether to merge a new `--file-ref` into an existing task, use `get_file_references` + exact-string compare. Do NOT attempt range union. Two distinct `^`-spec entries for the same path are a valid state.
  - **t540_4 (codebrowser integration):** the `^`-separated multi-range format lets a codebrowser emit one compact entry per file (e.g., the three visible regions in a diff). Prefer compact entries over multiple bare entries when the source is one interaction.
  - **t540_5 (board widget):** consider visually collapsing multiple same-path entries (rendering "foo.py (3 refs)") — the data model keeps them distinct but the UI can summarize.
  - **t540_7 (fold-time union):** the plan for t540_7 was written assuming flat-path entries. Under the compact-no-union rule, "union" becomes simple exact-string set union across the folded and primary tasks' `file_references` arrays. No range arithmetic needed. Re-verify that plan via `plan_preference_child: verify` before implementation.
  - **Helper surface:** `get_file_references` returns one entry per line, verbatim. Callers that need path-only matching should do `${entry%%:*}`. `validate_file_ref` is available for any script that accepts user-supplied refs.
  - **Test harness:** `tests/test_file_references.sh` is the template for t540 tests — it shows the minimum set of libs needed (`terminal_compat.sh`, `task_utils.sh`, `archive_utils.sh`, `archive_scan.sh`) in an isolated repo, and how to drive both `--commit` (real ID) and draft paths.
