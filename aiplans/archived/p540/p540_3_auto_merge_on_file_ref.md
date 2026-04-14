---
Task: t540_3_auto_merge_on_file_ref.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Parent Plan: aiplans/p540_task_creation_from_codebrowser.md
Sibling Tasks: aitasks/t540/t540_1_*.md, aitasks/t540/t540_2_*.md, aitasks/t540/t540_4_*.md, aitasks/t540/t540_5_*.md, aitasks/t540/t540_6_*.md, aitasks/t540/t540_7_*.md
Archived Sibling Plans: aiplans/archived/p540/p540_1_*.md, aiplans/archived/p540/p540_2_*.md
Worktree: (none — working on current branch)
Branch: main
Base branch: main
---

# Plan — t540_3: auto-merge when `--file-ref` is used (verified)

## Scope (locked after verification)

When `aitask_create.sh` is invoked with `--batch --commit` AND one or more
`--file-ref` flags, detect existing pending tasks that reference the same
path(s) and offer to fold them into the newly-created task — reusing the
existing `aitask_fold_*` scripts.

**In scope (this task):**
- Batch `--commit` direct parent path (lines 1412-1428).
- Batch `--commit` direct child path (lines 1379-1396).
- New CLI flags `--auto-merge` / `--no-auto-merge`, default `false`.
- No new fold logic is written — everything delegates to
  `aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`.

**Out of scope (deferred):**
- `finalize_draft()` auto-merge. Draft + finalize is the path interactive
  mode and `--batch --finalize` use. The task description says "any
  invocation of `aitask_create.sh` with `--file-ref` triggers the check",
  which is broader than what the "Key files to modify" section explicitly
  enumerates. Hooking `finalize_draft` requires reading `file_references`
  back from the finalized file (the flag is consumed at draft time), and
  adds new interactive code paths. Keep this task tight: follow the explicit
  "after `create_task_file` call" scope from the task spec. If t540_4
  (codebrowser integration) needs it, it can add the hook there, or a
  follow-up task can extend scope.
- Interactive fzf multi-select picker. Only reachable via `finalize_draft`
  (see above), so out of scope here.
- Fold-time frontmatter union of `file_references` — that's t540_7.

## Depends on

- **t540_1 (archived)** — provides `--file-ref` flag, `file_references`
  field, `get_file_references`, `validate_file_ref`, and
  `aitask_find_by_file.sh`. All already landed.
- Benefits from (but does not require) t540_7 — the frontmatter
  `file_references` union on fold. Without t540_7, the body merge still
  happens but the primary's `file_references` list is not unioned.

## Verification against current codebase

**File paths confirmed to exist with expected interfaces:**

| Script | Path | Interface |
|---|---|---|
| `aitask_find_by_file.sh` | `.aitask-scripts/aitask_find_by_file.sh` | `<path>` → `TASK:<id>:<file>` per line. Filters status to Ready/Editing. Path-only match. |
| `aitask_fold_validate.sh` | `.aitask-scripts/aitask_fold_validate.sh` | `--exclude-self <id> <ids...>` → `VALID:<id>:<file>` / `INVALID:<id>:<reason>` per id. |
| `aitask_fold_content.sh` | `.aitask-scripts/aitask_fold_content.sh` | `<primary_file> <folded1> [<folded2>...]` → merged body to stdout. |
| `aitask_fold_mark.sh` | `.aitask-scripts/aitask_fold_mark.sh` | `--commit-mode fresh <primary_id> <folded_ids...>` → marks folds, handles transitive, commits. |
| `aitask_update.sh --desc-file -` | `.aitask-scripts/aitask_update.sh` | Reads description body from stdin via `--desc-file -`. |

**Line number drift from the task spec (which said ~1300-1356):**

| Symbol | Actual line | Used as |
|---|---|---|
| `parse_args()` | 119 | Add `--auto-merge` / `--no-auto-merge` parsing. |
| `BATCH_FILE_REFS` declaration | 45 | Declare `BATCH_AUTO_MERGE=false` next to it. |
| `--file-ref` parse case | 139 | Add `--auto-merge` / `--no-auto-merge` right next to it. |
| `create_child_task_file()` | 343 | (not modified — no param change needed) |
| `format_labels_yaml()` | 1148 | Insert helper function below here. |
| `format_file_references_yaml()` | 1158 | (already present from t540_1) |
| `dedup_file_refs()` | 1170 | Insert `run_auto_merge_if_needed()` below this. |
| `create_task_file()` | 1185 | (not modified) |
| **Child `--commit` path** | **1379-1396** | Add `run_auto_merge_if_needed "${BATCH_PARENT}_${child_num}" "$filepath"` after the commit at line 1393, before `release_child_lock`. |
| **Parent `--commit` path** | **1412-1428** | Add `run_auto_merge_if_needed "$claimed_id" "$filepath"` after the commit at line 1427. |

**Existing state from t540_1 (already landed):**
- `BATCH_FILE_REFS=()` array declared at line 45.
- `--file-ref` flag parse at line 139 with `validate_file_ref` call.
- `format_file_references_yaml()` at line 1158.
- `dedup_file_refs()` at line 1170.
- `create_task_file` / `create_child_task_file` emit `file_references:`
  frontmatter when set.
- `aitask_find_by_file.sh` already scans and status-filters correctly.

## Design details (locked)

### Auto-merge safety layers (three, as designed in t540 parent plan)

1. `aitask_find_by_file.sh` filters by status — folded tasks never surface.
2. After candidate collection, `aitask_fold_validate.sh --exclude-self
   <new_id>` double-checks status before the fold runs. Any `INVALID:` lines
   are warned and excluded.
3. `aitask_fold_mark.sh`'s transitive logic handles chains cleanly with
   dedup (verified in `aitask_fold_mark.sh` lines 100-144).

### Fold execution sequence (`run_auto_merge_if_needed`)

Called AFTER the new task file is created AND committed (the creation
commit lands first; auto-merge creates a second commit via fold_mark).

1. Read `file_references` from the new task file via `get_file_references`.
   If empty, return silently.
2. Collect distinct path-only portions (strip from first `:` onward) into
   a unique list.
3. For each unique path, call `aitask_find_by_file.sh <path>` and union
   all `TASK:<id>:<file>` lines. Dedup by `<id>` (one task can match
   multiple paths).
4. Exclude `<new_id>` from candidate set (belt + braces — the find helper
   should not return the new task because path matching would require the
   new task to be on disk with matching refs, which it IS by this point;
   the exclusion prevents self-fold).
5. If no candidates remain → return silently.
6. **Batch decision:**
   - `BATCH_AUTO_MERGE=true` → all candidates are selected.
   - `BATCH_AUTO_MERGE=false` (default) → `warn()` lists candidates with
     paths and return (no fold).
7. Validate: `aitask_fold_validate.sh --exclude-self <new_id>
   <cand_ids...>`. Parse `VALID:<id>:<file>` → collect `valid_ids` and
   `valid_files` arrays. `INVALID:<id>:<reason>` → warn and skip.
8. If no valid candidates → return.
9. Body merge:
   ```bash
   aitask_fold_content.sh <new_file> <valid_files...> | \
     aitask_update.sh --batch <new_id> --desc-file - --silent >/dev/null
   ```
10. Mark + commit:
    ```bash
    aitask_fold_mark.sh --commit-mode fresh <new_id> <valid_ids...>
    ```
11. Log `info()` / `success()` summary.

### CLI flags

- `--auto-merge` — sets `BATCH_AUTO_MERGE=true`.
- `--no-auto-merge` — sets `BATCH_AUTO_MERGE=false` (default).
- Last-wins if both given (shell semantics with two separate case arms).

### Warn text for default (`--no-auto-merge`) case

When candidates exist but the user didn't pass `--auto-merge`:
```
Found N pending task(s) that already reference this file:
  - t42 (foo.py) → aitasks/t42_example.md
  - t43_2 (foo.py:10-20) → aitasks/t43/t43_2_other.md
Auto-merge skipped (pass --auto-merge to fold them into this task).
```

## Implementation sequence

1. Add `BATCH_AUTO_MERGE=false` declaration near `BATCH_FILE_REFS` (line 45
   area).
2. Add `--auto-merge` / `--no-auto-merge` to `parse_args` (next to
   `--file-ref` at line 139).
3. Add `--auto-merge` / `--no-auto-merge` to `show_help` docs (line 54-117).
4. Implement `run_auto_merge_if_needed(new_id, new_file)` — place below
   `dedup_file_refs` (around line 1184, before `create_task_file`).
5. Wire into child `--commit` path after its commit at line 1393.
6. Wire into parent `--commit` path after its commit at line 1427.
7. Write `tests/test_auto_merge_file_ref.sh` (see Test plan below).
8. Shellcheck.

## Test plan — `tests/test_auto_merge_file_ref.sh`

Harness mirrors `tests/test_file_references.sh`. Must copy into the isolated
repo:
- `aitask_create.sh`, `aitask_claim_id.sh`, `aitask_update.sh`
- `aitask_find_by_file.sh`
- `aitask_fold_validate.sh`, `aitask_fold_content.sh`, `aitask_fold_mark.sh`
- `lib/terminal_compat.sh`, `lib/task_utils.sh`, `lib/archive_utils.sh`
- (and if needed by the harness: `lib/archive_scan.sh`)

Chmod all `.sh` files to +x. Init atomic counter via
`aitask_claim_id.sh --init`. Task types file present.

**Test cases:**

1. **Default no-auto-merge:** Create A with `--file-ref foo.py --commit` and
   NO `--auto-merge`. Then create B with `--file-ref foo.py --commit` (also
   no flag). Expect: A still exists and is Ready (no fold occurred). B has
   no `folded_tasks` field.

2. **Explicit `--auto-merge`:** Create A with `--file-ref foo.py --commit`.
   Create B with `--file-ref foo.py --commit --auto-merge`. Expect:
   A.status == Folded, A.folded_into == B's ID, B has `folded_tasks:`
   containing A's ID.

3. **Explicit `--no-auto-merge`:** Create A, then create B with
   `--file-ref foo.py --commit --no-auto-merge`. Expect: A still Ready,
   B standalone (same as default but flag is explicit).

4. **Status filter:** Create A with `--file-ref foo.py --commit`. Set A's
   status to `Postponed` via `aitask_update.sh`. Create D with
   `--file-ref foo.py --commit --auto-merge`. Expect: A NOT folded (its
   status made it invisible to the find helper). D standalone.

5. **Transitive fold:** Set up a pre-existing state where B has A already
   folded (run `aitask_fold_mark.sh fresh B A` in the harness). Both A and
   B initially reference `foo.py` (A before fold, B now after absorbing
   A's body). Create E with `--file-ref foo.py --commit --auto-merge`.
   Expect: B.status == Folded, B.folded_into == E, A.folded_into updated
   to E (transitive), E has `folded_tasks:` containing at least B and A.

6. **No candidates is a no-op:** Create X with `--file-ref baz.py
   --commit --auto-merge`. No other task references `baz.py`. Expect:
   X created normally, no fold commits, no warnings, exit 0.

7. **No `--file-ref` is a no-op:** Create Y with `--commit` (no
   `--file-ref` at all, `--auto-merge` passed). Expect: Y created
   normally, no fold occurred (nothing to match against).

8. **Syntax check:** `bash -n` on `aitask_create.sh` and the new test file.

## Verification

- `bash tests/test_auto_merge_file_ref.sh` — PASS.
- `bash tests/test_file_references.sh` — still PASS (no regression).
- `shellcheck .aitask-scripts/aitask_create.sh` — no new warnings.
- `bash -n .aitask-scripts/aitask_create.sh` — clean.

## Out of scope

- `finalize_draft` auto-merge hook (see Scope section above).
- Interactive fzf picker for candidate selection.
- Codebrowser "c" keybinding — t540_4.
- Fold-time frontmatter union of `file_references` — t540_7.
- Board field widget — t540_5.

## Post-implementation

Archival via `./.aitask-scripts/aitask_archive.sh 540_3`.

## Final Implementation Notes

- **Actual work done:**
  - `.aitask-scripts/aitask_create.sh`:
    - Added `BATCH_AUTO_MERGE=false` next to `BATCH_FILE_REFS=()` at
      the batch-mode variable block.
    - Added `--auto-merge` / `--no-auto-merge` flag parsing in
      `parse_args` next to `--file-ref`.
    - Documented both flags in `show_help`.
    - Added `run_auto_merge_if_needed(new_id, new_file)` helper right
      after `dedup_file_refs`. Helper reads the new task's
      `file_references` via `get_file_references`, strips path-only
      portions, calls `aitask_find_by_file.sh` per unique path,
      unions candidate IDs (dedup + self-exclude), honors
      `BATCH_AUTO_MERGE` (warn + skip on false, fold on true), then
      runs the canonical 3-step fold chain:
      1. `aitask_fold_validate.sh --exclude-self`,
      2. `aitask_fold_content.sh ... | aitask_update.sh --desc-file -`,
      3. `aitask_fold_mark.sh --commit-mode fresh`.
    - Wired the helper into the child `--commit` path right after the
      creation `task_git commit` and before `release_child_lock`, and
      into the parent `--commit` path right after its creation commit.
  - `tests/test_auto_merge_file_ref.sh`: 8 test groups, 21 assertions,
    all passing. Covers: default no-fold, explicit `--auto-merge` fold,
    explicit `--no-auto-merge`, status filter (Postponed not folded),
    transitive fold re-pointing, no-op when no candidates, no-op when
    no `--file-ref`, syntax check.
  - `aiplans/p540/p540_3_auto_merge_on_file_ref.md`: rewrote in verify
    mode with current line numbers, scope lock, and final notes.

- **Scope decision (locked):**
  - **Batch `--commit` only.** `finalize_draft` (interactive mode and
    `--batch --finalize`) does NOT auto-merge. This honors the task
    spec's "Key files to modify" list which explicitly enumerates the
    `create_task_file` / `create_child_task_file` call sites, not
    `finalize_draft`. The task spec's broader "any invocation with
    `--file-ref` triggers the check" framing is deferred to a
    follow-up (possibly t540_4, since codebrowser integration will
    want interactive flow).
  - **No interactive fzf picker.** It would only be reachable through
    `finalize_draft`, which is out of scope.

- **Deviations from plan:** none. Line-number drift was captured in
  verify mode before implementation and the plan was updated to match
  the current codebase.

- **Issues encountered:** none. Tests passed on first run after
  implementation. All fold tests, `test_file_references.sh`, and the
  new `test_auto_merge_file_ref.sh` pass cleanly.

- **Key decisions:**
  - **Helper placement after the creation commit, not before.** The
    fold chain creates its own commit via
    `aitask_fold_mark.sh --commit-mode fresh`. By running the helper
    after the creation commit has landed, the two commits stay
    separate in history: `ait: Add task tN: ...` followed by
    `ait: Fold tasks into tN: merge t...`. This is consistent with
    how the fold scripts are designed to be used and makes the git
    history easy to read.
  - **Candidate dedup by ID, not by file.** A single task can match
    multiple paths in the new task's `file_references`. We collect
    `(id, file)` pairs from `aitask_find_by_file.sh` but dedup by ID
    so each candidate is passed to `fold_validate` exactly once.
  - **Self-exclude is belt + braces.** `aitask_find_by_file.sh` does
    not return the newly-created task because its candidate set is
    built from the file-ref paths after the new task is on disk, so
    the new task IS a technical match. The helper filters it out in
    the collection loop, and `aitask_fold_validate.sh --exclude-self`
    would filter it again. Both layers are kept for defense in depth.
  - **Warn-but-skip default.** `BATCH_AUTO_MERGE=false` is the
    default. The helper prints a visible `warn()` listing the
    candidates so the user sees what they missed. Opt-in to actually
    fold via `--auto-merge`.
  - **No `--file-ref` in the new task is a silent no-op.** The helper
    returns immediately if `get_file_references` is empty. `--auto-merge`
    with no `--file-ref` never produces warnings or errors.

- **Notes for sibling tasks:**
  - **t540_4 (codebrowser integration):** if the codebrowser launches
    `aitask_create.sh --batch --commit --file-ref ... --auto-merge`,
    auto-merge will work out-of-the-box. For the interactive codebrowser
    experience, it may make sense to either (a) extend this helper to
    support `finalize_draft`, or (b) invoke
    `aitask_find_by_file.sh` from the codebrowser itself and present
    matches in a codebrowser-native picker before calling
    `aitask_create.sh`.
  - **t540_5 (board widget):** no interaction; board reads frontmatter
    `file_references` which already displays correctly from t540_1.
  - **t540_6 (labels-from-previous-task):** independent; no overlap.
  - **t540_7 (fold-time `file_references` union):** this is orthogonal.
    When t540_7 lands, the primary task (the new task in this helper's
    flow) will have its `file_references` automatically unioned with
    the folded tasks' `file_references` during
    `aitask_fold_mark.sh` / `aitask_fold_content.sh`. No change to this
    helper is needed.
  - **Helper reusability:** `run_auto_merge_if_needed` is kept inside
    `aitask_create.sh` as a private function. If a future task needs
    the same logic from another script, it can be extracted to
    `lib/task_utils.sh` with minimal refactoring.
