---
Task: t540_7_fold_file_references_union.md
Parent Task: aitasks/t540_task_creation_from_codebrowser.md
Archived Sibling Plans: aiplans/archived/p540/p540_1_foundation_file_references_field.md, aiplans/archived/p540/p540_2_codebrowser_focus_mechanism.md, aiplans/archived/p540/p540_3_auto_merge_on_file_ref.md, aiplans/archived/p540/p540_4_codebrowser_create_from_selection.md, aiplans/archived/p540/p540_5_board_file_references_field.md, aiplans/archived/p540/p540_6_use_labels_from_previous_task.md, aiplans/archived/p540/p540_8_finalize_draft_auto_merge_hook.md
Base branch: main
plan_verified:
  - claudecode/opus4_6 @ 2026-04-15 12:35
---

# t540_7: union `file_references` during fold (VERIFIED)

## Context

The parent task t540 adds a structured `file_references` frontmatter
field and wires it into auto-merge (t540_3) and a board widget (t540_5).
When the auto-merge flow folds pending tasks into a new primary, it
calls `aitask_fold_mark.sh` — but that script currently rewrites only
`folded_tasks` on the primary. The folded tasks' `file_references`
never make it into the primary's structured list, so
`aitask_find_by_file.sh` will miss them after a fold, breaking the
exclusion guarantees the auto-merge flow depends on.

This task extends the fold-mark rewrite so the primary ends up with
the deduped union of its own entries plus every folded (and transitive
folded) task's entries, written in a single atomic fold commit.

## Verification of existing plan

The external plan lives at
`aiplans/p540/p540_7_fold_file_references_union.md` and is still fully
accurate against the current codebase:

- `get_file_references` exists in `.aitask-scripts/lib/task_utils.sh`
  (lines ~489–516) and returns one verbatim entry per line. Reusable.
- `union_file_references` does NOT yet exist in `lib/task_utils.sh`
  (grep confirmed). Must be added.
- `aitask_fold_mark.sh` still owns the primary-frontmatter rewrite via
  `aitask_update.sh --batch <id> --folded-tasks <csv>` (line 151). The
  new union logic will piggyback on that same `aitask_update.sh` call
  by passing additional repeated `--file-ref` flags, so the fold
  commit stays atomic.
- `aitask_update.sh` already supports `--file-ref <ref>` (repeatable)
  and `process_file_references_operations` does exact-string dedup
  against current entries (verified in `tests/test_file_references.sh`
  test 6). Passing the full ordered union as individual `--file-ref`
  flags produces the same primary-first, folded-in-arg-order,
  first-occurrence-dedup behavior the plan specifies — no new flag on
  `aitask_update.sh` is needed.
- `resolve_file_by_id` is already defined inside `aitask_fold_mark.sh`
  and can be reused to resolve transitive IDs to files.
- `tests/test_fold_mark.sh` demonstrates the fold-test harness (local
  bare-repo clone, `write_task`, structured-output assertions); new
  test will follow the same pattern.
- No `tests/test_fold_file_refs_union.sh` exists yet — must be
  created.

## Critical files

1. `.aitask-scripts/lib/task_utils.sh` — add `union_file_references`
   helper. Pure bash; reuses `get_file_references`; produces a CSV on
   stdout.
2. `.aitask-scripts/aitask_fold_mark.sh` — after the existing
   transitive-id collection, resolve each folded and transitive id to
   a file, call `union_file_references`, split the CSV, and append
   repeated `--file-ref <entry>` args to the single
   `aitask_update.sh --batch ... --folded-tasks ...` call.
3. `tests/test_fold_file_refs_union.sh` *(new)* — covers basic,
   dedup, transitive, and empty-union cases; syntax-check block at
   the end.

## Design (confirmed)

### New helper `union_file_references`

```bash
# union_file_references <primary_file> [<folded_file> ...]
# Reads file_references from primary first, then each folded file in
# argument order. Dedupes by first-occurrence exact-string match.
# Prints the unioned list as CSV on stdout (empty if nothing to emit).
union_file_references() {
    local primary_file="$1"
    shift
    local -a merged=()
    declare -A seen=()
    local entry f

    if [[ -n "$primary_file" && -f "$primary_file" ]]; then
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            if [[ -z "${seen[$entry]:-}" ]]; then
                seen[$entry]=1
                merged+=("$entry")
            fi
        done < <(get_file_references "$primary_file")
    fi

    for f in "$@"; do
        [[ -z "$f" || ! -f "$f" ]] && continue
        while IFS= read -r entry; do
            [[ -z "$entry" ]] && continue
            if [[ -z "${seen[$entry]:-}" ]]; then
                seen[$entry]=1
                merged+=("$entry")
            fi
        done < <(get_file_references "$f")
    done

    local IFS=','
    echo "${merged[*]}"
}
```

### Call site in `aitask_fold_mark.sh`

Inside the existing block that builds `full_csv` and calls
`aitask_update.sh --folded-tasks`, add:

```bash
# Collect file paths for direct folded tasks
folded_files=()
for fid in "${folded_ids[@]}"; do
    fid="${fid#t}"
    f=$(resolve_file_by_id "$fid")
    [[ -n "$f" ]] && folded_files+=("$f")
done

# Collect file paths for transitive folded tasks
transitive_files=()
for tid in "${transitive_ids[@]}"; do
    tid="${tid#t}"
    [[ -z "$tid" ]] && continue
    f=$(resolve_file_by_id "$tid")
    [[ -n "$f" ]] && transitive_files+=("$f")
done

# Compute deduped union of file_references
union_csv=$(union_file_references "$primary_file" \
    ${folded_files[@]+"${folded_files[@]}"} \
    ${transitive_files[@]+"${transitive_files[@]}"})

# Build optional --file-ref flags
file_ref_args=()
if [[ -n "$union_csv" ]]; then
    IFS=',' read -ra union_entries <<< "$union_csv"
    for entry in "${union_entries[@]}"; do
        [[ -z "$entry" ]] && continue
        file_ref_args+=(--file-ref "$entry")
    done
fi
```

Then extend the existing `aitask_update.sh` call with the array, using
the `${arr[@]+...}` idiom for safety under `set -u`:

```bash
"$SCRIPT_DIR/aitask_update.sh" --batch "$primary_id" \
    --folded-tasks "$full_csv" \
    ${file_ref_args[@]+"${file_ref_args[@]}"} \
    --silent >/dev/null
```

No changes to the structured-output lines (`PRIMARY_UPDATED`,
`FOLDED`, `TRANSITIVE`, `COMMITTED`) — downstream parsers remain
stable.

### Why this preserves plan ordering

`process_file_references_operations` keeps the file's current entries
in place (in order), then appends new entries not already present.
Passing the full union `[P1, P2, F1, F2, ...]` where `P*` are
primary's existing entries produces: start `[P1, P2]`, dedup-skip
`P1`, dedup-skip `P2`, append `F1`, append `F2` → `[P1, P2, F1, F2]`.
Identical to the plan's "primary first, then folded in arg order,
first-occurrence dedup" spec.

## Test plan (`tests/test_fold_file_refs_union.sh`)

Follow the structure of `tests/test_fold_mark.sh` (bare-repo clone,
`write_task` helper, `read_frontmatter_field`, structured-output
assertions). Test cases:

1. **Basic union** — primary `[a.py:1-5]`, folded `[b.py, a.py:10-20]`.
   After `--commit-mode none 10 20`: primary `file_references:
   [a.py:1-5, b.py, a.py:10-20]`.
2. **Dedup** — primary `[a.py:1-5]`, folded `[a.py:1-5]`. After fold:
   primary `[a.py:1-5]` (single entry).
3. **Transitive** — primary `[p.py]`, folded Q `[q.py]` with
   `folded_tasks: [R]` and R with status Folded `[r.py]`. After fold
   of Q into P: primary `[p.py, q.py, r.py]`.
4. **Empty union** — primary no `file_references`, folded no
   `file_references`. After fold: primary still has no
   `file_references` line (or an empty one — confirm neither asserts
   a spurious entry).
5. **Syntax check** — `bash -n` both touched scripts at the end.

## Verification steps

- `bash tests/test_fold_file_refs_union.sh` — all asserts pass.
- `bash tests/test_fold_mark.sh` — no regression (existing flows
  untouched).
- `bash tests/test_file_references.sh` — sanity check on the
  `--file-ref` append/dedup semantics the new code piggybacks on.
- `shellcheck .aitask-scripts/lib/task_utils.sh
  .aitask-scripts/aitask_fold_mark.sh` — clean.
- Manual end-to-end (optional): create a pending task with
  `file_references: [x.py]`, then create a new task with `--file-ref
  x.py --auto-merge`; confirm the new primary's
  `file_references` line contains both entries and the single fold
  commit diff shows `folded_tasks` + `file_references` updated
  together.

## Out of scope

- Range merging (e.g., collapsing `foo.py:10-20` and `foo.py:15-25`
  into `foo.py:10-25`). Explicit follow-up; first pass keeps distinct
  ranges as distinct entries.
- `aitask_fold_content.sh` body merging — untouched.
- Any changes to `aitask_update.sh` flag surface — the repeated
  `--file-ref` approach is used precisely to avoid new flags.

## Post-implementation

Archive via `./.aitask-scripts/aitask_archive.sh 540_7`.
