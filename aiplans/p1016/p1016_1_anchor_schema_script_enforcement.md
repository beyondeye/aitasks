---
Task: t1016_1_anchor_schema_script_enforcement.md
Parent Task: aitasks/t1016_anchor_task_topic_grouping.md
Sibling Tasks: aitasks/t1016/t1016_2_*.md, aitasks/t1016/t1016_3_*.md, aitasks/t1016/t1016_4_*.md
Archived Sibling Plans: aiplans/archived/p1016/p1016_*_*.md
Worktree: aiwork/t1016_1_anchor_schema_script_enforcement
Branch: aitask/t1016_1_anchor_schema_script_enforcement
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-18 11:29
---

# Plan — t1016_1 Schema + script enforcement (anchor)

Foundation for t1016. Adds the scalar `anchor: <task_id>` field, the
`--anchor` / `--followup-of` creation flags with the inheritance rule,
**validated** editability via `aitask_update.sh`, sync-safety in
`aitask_merge.py`, and the fold no-op decision. Owns the inheritance + merge +
validation unit tests. All other t1016 children depend on this.

> **Verified 2026-06-18 (verify path):** all referenced line numbers, helper
> functions, idioms, and test patterns confirmed accurate against current code
> with **zero functional drift**. No `tests/test_anchor_create.sh` /
> `tests/test_anchor_update.sh` exist yet (correctly NEW). The
> `finalize_draft()` sed strips only `draft:`/`parent:` — a new `anchor:` line
> passes through unchanged.

> **Plan-review hardening (2026-06-18):** six integrity gaps raised in review
> are addressed below — (1) update-side validation via a **shared** helper,
> (2) reject `--parent` + explicit anchor flags, (3) `--anchor`/`--followup-of`
> are mutually exclusive (replaces the ambiguous "explicit wins" rule),
> (4) parent-aware fallback for follow-ups of legacy anchorless children,
> (5) an update-reject test, (6) **id normalization to bare form** so a
> `t`-prefixed input both resolves AND matches the root's own-id group key.
> See the **Decided rules** block.

## Anchor semantics (authoritative)

The unifying principle: **`anchor` always points at the topic ROOT.** For any
source task `S`:
- `S.anchor` is set → use it (already a root; never chains).
- else `S` is a **child** (`<p>_<c>`) → use `<p>` (the subtree's root).
- else → use `S`'s own id (`S` is itself a root).

Derived:
- Group key = `anchor` if set, else own id. Roots emit **no** `anchor:` line.
- Follow-up of `S` → the root of `S` (per the principle above; flattened).
- Child of parent `P` → root of `P` = `P.anchor` if set else `P` (auto-inherit).

## Decided rules (resolve review findings 2/3/4)

- **Mutual exclusion (finding 3):** `--anchor` and `--followup-of` are
  **mutually exclusive** → `die` if both set. (Replaces the original "explicit
  `--anchor` wins" rule, which conflicted with "validate every set flag".)
- **Child anchor is always parent-derived (finding 2):** if `--parent` is set,
  reject **either** `--anchor` **or** `--followup-of` → `die` with a hint to
  re-anchor post-creation via `aitask_update.sh --anchor`. A parent-child
  subtree therefore always groups under one topic at creation time.
- **Validate exactly the one source flag that is set (finding 3):** since combos
  are rejected, there is never an "ignored but set" flag to reason about.
- **Legacy parent-aware fallback (finding 4):** `--followup-of <legacy-child>`
  where the child has no `anchor` resolves to the child's **parent** id (the
  legacy topic root), NOT the child's own id. This is an **intentional
  refinement** of the parent task's literal `source.anchor or source.id`
  wording, honoring its stated intent ("anchor points at the root") so a loose
  follow-up of a legacy child joins that subtree's display-time group (the
  legacy grouping handled by t1016_4's `topic_key` fallback).
- **Id normalization to bare form (finding 6):** every accepted id
  (`--anchor`, `--followup-of`, `update --anchor`) is normalized by stripping an
  optional single leading `t` and asserting `^[0-9]+(_[0-9]+)?$`. The **bare**
  form (`42`, `42_1`) is what gets validated, passed to `resolve_task_file()`,
  and **stored** in `anchor:`. This guarantees the stored value equals a root's
  bare own-id group key (so `--anchor t42` and `--anchor 42` are identical) and
  avoids the `task-status` (accepts `t42`) vs `resolve_task_file` (needs bare)
  mismatch.

## Steps

### 0. `lib/task_utils.sh` — shared `normalize_anchor_id()` (NEW; resolves findings 1, 5 & 6)
Add an intra-repo, archived-inclusive **normalize-and-validate** helper mirroring
`validate_xdeps_pair` (L318-358) but local-only, so **both** `aitask_create.sh`
and `aitask_update.sh` call one implementation (no duplication). It strips an
optional leading `t`, asserts the id shape, validates existence, and **echoes
the bare id** so callers store/resolve the canonical form:
```bash
normalize_anchor_id() {           # $1 = raw id (t42|42|t42_1|42_1) -> echoes bare id; dies on bad/missing
    local raw="$1" id status
    id="${raw#t}"                 # strip optional leading t only (not p)
    if [[ ! "$id" =~ ^[0-9]+(_[0-9]+)?$ ]]; then
        die "anchor target '$raw' is not a valid task id (expected N or N_M)."
    fi
    status=$("$SCRIPT_DIR/aitask_query_files.sh" task-status "$id" 2>/dev/null || true)
    case "$status" in
        STATUS:NOT_FOUND|"") die "anchor target '$id' not found." ;;
        STATUS:*) echo "$id" ;;   # any status (incl. Done/archived) is valid
        *) die "anchor target '$id': unexpected status result '$status'." ;;
    esac
}
```
(`cmd_task_status`, aitask_query_files.sh L470-502, returns `STATUS:Done` for
archived → archived roots are allowed. Mirrors that file's local `strip_prefix`
L123-128, but `t`-only and as a shared lib function.)

### 1. `aitask_create.sh` — flags + resolution + validation
- Init `BATCH_ANCHOR=""`, `BATCH_FOLLOWUP_OF=""` near other `BATCH_*` globals
  (L25-51); parse `--anchor`/`--followup-of` in `parse_args` (L144-182).
- `resolve_anchor()` (call after parse, before file creation):
  1. **Guards (die):** `--parent` set with (`--anchor` or `--followup-of`) →
     die (finding 2). `--anchor` and `--followup-of` both set → die (finding 3).
  2. `--anchor X` → `ANCHOR=$(normalize_anchor_id "$BATCH_ANCHOR")` (bare,
     validated; finding 6).
  3. elif `--followup-of S` → `S_BARE=$(normalize_anchor_id "$BATCH_FOLLOWUP_OF")`;
     resolve src via `resolve_task_file "$S_BARE"` (archived-inclusive,
     task_utils.sh L518-602), read `src.anchor` with `read_yaml_field`
     (yaml_utils.sh L58-90):
     - `src.anchor` non-empty → `ANCHOR=src.anchor` (already stored bare).
     - elif `S_BARE` matches `<p>_<c>` (child) → `ANCHOR=<p>` (legacy fallback, finding 4).
     - else → `ANCHOR=S_BARE`.
     - tar-bundle unreadable fallback: child → `<p>`, else → `S_BARE`.
  4. elif `--parent P` → `ANCHOR = P.anchor` if non-empty else `<P-bare>`.
  5. else `ANCHOR=""` (root).
- Emit `anchor:` (conditional scalar, mirror `assigned_to`
  `if [[ -n "$x" ]]; then echo "x: $x"; fi`) in `create_task_file()` (L1723-1726),
  `create_child_task_file()` (resolve from `--parent`; issue emit L460-462),
  `create_draft_file()` (L580-582). `finalize_draft()` (L637-758) already carries
  it through — its sed (L666 child / L726 parent) strips only `draft:`/`parent:`;
  do NOT add `anchor` to any strip.
- Add `--anchor` / `--followup-of` to help text (show_help L60-142), documenting
  the mutual-exclusion + child rules.

### 2. `aitask_update.sh` — editable + validated `--anchor` (resolves finding 1)
- `--anchor` flag + `BATCH_ANCHOR=""` / `BATCH_ANCHOR_SET=false` (mirror
  `BATCH_ASSIGNED_TO` L66-67); parse at the L294 idiom
  (`--anchor) BATCH_ANCHOR="$2"; BATCH_ANCHOR_SET=true; shift 2 ;;`).
- **Normalize + validate (NEW):** after parse, if `BATCH_ANCHOR_SET == true`
  **and** `BATCH_ANCHOR` non-empty → `BATCH_ANCHOR=$(normalize_anchor_id "$BATCH_ANCHOR")`
  (stores bare, validated; finding 6). Empty value (`--anchor ""`) skips
  normalization/validation and **clears** the field.
- `CURRENT_ANCHOR` in `parse_yaml_frontmatter` (L362-497, mirror
  `CURRENT_ASSIGNED_TO` L469); new-value RMW (mirror L1740-1744:
  `local new_anchor="$CURRENT_ANCHOR"; if [[ "$BATCH_ANCHOR_SET" == true ]]; then new_anchor="$BATCH_ANCHOR"; fi`);
  add `new_anchor` to the `write_task_file` call (L1823-1830) and to
  `write_task_file()`'s positional signature (L513-542, 29 → 30 params) +
  conditional emit (mirror assigned_to L630-633). Clear-by-empty works via the
  `_SET` guard. **Care:** the positional-arg expansion must change in lockstep
  across signature + call site (see Risk).

### 3. `aitask_merge.py` — scalar merge rule
- In `merge_frontmatter` (L146-214), insert before the generic `else` (L209-212):
  `elif key == "anchor": merged[key] = local_val if local_ts >= remote_ts else
  remote_val` (newer-side-wins; mirrors `updated_at` L189-190). Keep `anchor`
  OUT of `_LIST_UNION_FIELDS` / `BOARD_KEYS` (L119-121) — it is semantic, not
  list/board-layout.

### 4. `aitask_fold_mark.sh` — fold no-op comment
- One-line comment right after the `risk_mitigation_tasks`-not-unioned block
  (L298-302), following that idiom: `anchor` is scalar, intentionally not
  unioned on fold (primary wins; folded file deleted).

## Verification

New `tests/test_anchor_create.sh`, `tests/test_anchor_update.sh` (source
`tests/lib/test_scaffold.sh` + `tests/lib/asserts.sh`; use
`assert_eq`/`assert_contains`/`assert_exit_zero`/`assert_exit_nonzero` per
`tests/test_claim_id.sh`); extend `tests/test_aitask_merge.py` with
`test_anchor_keeps_newer` (mirror `test_updated_at_keeps_newer` L124-128).

Create cases:
- root → no `anchor:`; `--anchor 42` → `anchor: 42`.
- **`--anchor t42` → `anchor: 42`** (bare-normalized, finding 6); identical to
  `--anchor 42`.
- **`--anchor xyz` / `--anchor t` → nonzero, no file** (bad id shape, finding 6).
- `--followup-of <src-no-anchor, parent>` → `<src>`; `<src-anchor=R>` → `R`;
  follow-up-of-follow-up → `R` (no chain).
- **`--followup-of <legacy anchorless child P_c>` → `anchor: P`** (parent
  fallback, finding 4 — simulate "legacy" by creating the child then
  `update --anchor ""` to clear its auto-inherited anchor).
- child of parent-no-anchor → parent id; child of parent-anchor=R → `R`.
- **`--parent P --anchor X` → nonzero, no file** (finding 2).
- **`--parent P --followup-of S` → nonzero, no file** (finding 2).
- **`--anchor X --followup-of S` → nonzero, no file** (finding 3).
- `--anchor <nonexistent>` / `--followup-of <nonexistent>` → nonzero, no file.
- `--anchor <archived-id>` → succeeds.
- draft `--finalize` preserves anchor.

Update cases:
- `update --batch <id> --anchor X` sets it; `--anchor ""` clears it.
- **`update --batch <id> --anchor <missing>` → nonzero, file unchanged**
  (findings 1 & 5).
- **`update --batch <id> --anchor t42` → stores `anchor: 42`** (bare, finding 6).

Merge case:
- `test_anchor_keeps_newer`: local `updated_at` newer → merged keeps local
  anchor and `anchor` is NOT in the unresolved list.

Run: `bash tests/test_anchor_create.sh`, `bash tests/test_anchor_update.sh`,
`bash tests/run_all_python_tests.sh`, `bash tests/test_aitask_merge.sh`,
`shellcheck .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_update.sh .aitask-scripts/lib/task_utils.sh`.

## Risk

### Code-health risk: medium
- `write_task_file` (`aitask_update.sh`) takes 29 positional params; adding
  `anchor` (30th) requires signature (L513-542), call site (L1823-1830), and
  plumbing (`CURRENT_ANCHOR`/`new_anchor`/`BATCH_ANCHOR_SET`) to change in
  lockstep — a positional mismatch silently shifts fields. · severity: medium ·
  → mitigation: in-task `test_anchor_update.sh` + existing `aitask_update.sh`
  tests + shellcheck.
- Touches load-bearing create/update scripts on every task creation/edit path;
  the new shared `normalize_anchor_id` adds one `aitask_query_files.sh` call per
  set flag. · severity: low · → mitigation: copy the proven `assigned_to` /
  `validate_xdeps_pair` idioms verbatim; new + existing tests guard it.

### Goal-achievement risk: low
- None identified. The review hardening (shared update-side validation, mutual
  exclusion, parent-aware legacy fallback) closes the integrity gaps; approach
  fully specified and verified against current code (zero drift); scope
  contained to schema + enforcement + tests; all semantics covered by explicit
  test cases.

(No `### Planned mitigations` — the code-health risk is mitigated in-task by the
testability-first design; a separate before/after task would be redundant.)

## Post-Implementation
Step 9 (review, merge to main, archive) applies when this child completes; the
parent archives automatically once all siblings are done.

## Final Implementation Notes

- **Actual work done:** Implemented the plan as approved (all 6 steps + the
  review-hardening additions). Files: `lib/task_utils.sh` (new shared
  `normalize_anchor_id`), `aitask_create.sh` (flags + `resolve_anchor` + emit ×3
  + help), `aitask_update.sh` (editable/validated `--anchor` + RMW +
  `write_task_file` 30th param), `board/aitask_merge.py` (newer-wins rule),
  `aitask_fold_mark.sh` (no-op comment). Tests: new `tests/test_anchor_create.sh`
  (20 cases), `tests/test_anchor_update.sh` (8 cases), `+2` cases in
  `tests/test_aitask_merge.py`.
- **Deviations from plan:** None substantive. The three `create_*_file` emitters
  read the resolved value from a single computed global `RESOLVED_ANCHOR`
  (set by `resolve_anchor` before file creation) rather than threading a new
  positional param through every call site — `RESOLVED_ANCHOR` is a *derived*
  value, not a raw batch input, so this is lower blast-radius than positional
  churn and stays `""` (no emit) in interactive mode.
- **Issues encountered:** The test harness must copy `aitask_query_files.sh`
  (+ `lib/archive_scan.sh`) into the fake repo, because `normalize_anchor_id`
  shells out to `aitask_query_files.sh task-status` for existence validation —
  without it every anchor would fail validation. `test_update_risk.sh` (the
  setup model) does not copy it; the anchor tests add both.
- **Key decisions:** (1) `--anchor`/`--followup-of` are mutually exclusive and
  both rejected with `--parent` (a child's anchor is always parent-derived;
  re-anchor via `aitask_update.sh --anchor`). (2) All accepted ids are
  normalized to **bare** form (`normalize_anchor_id` strips a leading `t`,
  asserts `N`/`N_M`, validates existence archived-inclusive, echoes the bare id)
  so the stored value equals a root's own-id group key and `resolve_task_file`
  always gets bare ids. (3) **Legacy parent fallback:** `--followup-of` of an
  anchorless **child** resolves to the child's **parent** (the topic root), a
  deliberate refinement of the parent task's literal `source.anchor or
  source.id` wording to honor "anchor points at the root".
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **Shared helper:** `normalize_anchor_id` (in `lib/task_utils.sh`,
    archived-inclusive, echoes the bare id, `die`s on bad/missing) is the one
    validation+normalization entry point — reuse it; do not re-validate anchors ad hoc.
  - **Bare-id invariant:** anchors are stored bare (`42`, `42_1`). Consumers
    (t1016_4 board grouping) must treat group key = `anchor` if present else the
    task's own bare id, and **keep `anchor` OUT of `BOARD_KEYS`** (it is semantic,
    not board-layout) — confirmed it is not in `_LIST_UNION_FIELDS`/`BOARD_KEYS`
    in `aitask_merge.py`.
  - **Legacy-child fallback is a rule refinement:** t1016_2 (docs) and
    t1016_3/t1016_4 must describe/assume "anchor points at the topic root"
    including the legacy-child→parent fallback, NOT the literal
    `source.anchor or source.id`. The `## Decided rules` block above is the
    authoritative wording.
  - **Roots emit no `anchor:` line**; absent anchor ⇒ own-id is the key.
  - **Merge:** anchor uses the newer-`updated_at`-wins rule (mirrors
    `updated_at`), so board/CLI edits survive concurrent sync.
