---
Task: t2299_1_sitrep_store_recover_ref_and_recovery_apply.md
Parent Task: aitasks/t2299_sitrep_track_crashed_agents_for_resume.md
Sibling Tasks: aitasks/t2299/t2299_2_*.md, aitasks/t2299/t2299_3_*.md, aitasks/t2299/t2299_4_*.md
Archived Sibling Plans: aiplans/archived/p2299/p2299_*_*.md
Base branch: main
Output branch: main
---

# Plan: store support for recovery items (t2299_1)

## Context

t2299 tracks crashed agents in sitrep as **one recovery item per task**. The
item is `kind=task` with the stable ref `recover:t<N>`. Its evidence is updated
in place, a done item reopens, and a dismissal covers one *episode* (one claim
attempt).

This child adds the store mechanics the detector (t2299_2) and refresh/TUI
(t2299_3) rely on:
- the ref grammar;
- the `incarnation` origin key;
- an atomic, rev-guarded `recovery-apply` verb that enforces the dismissal rule;
- store format 3.

The task file holds the full fact sheet (line numbers at af0dca45c).

## Steps

1. **Ref grammar** (`lib/sitrep_todo.py`).
   - Add `RECOVER_REF_RE = re.compile(r"^recover:t(\d+(?:_\d+)?)$")`.
   - `normalize_ref` accepts it verbatim. The `t` is strict: no bare number and no upper case.
   - `parse_recover_ref(ref) -> str | None` returns `"12"` / `"12_3"`.
   - In `_check_item_values`, a `recover:` ref requires `kind == "task"`; a mismatch raises a FormatError at parse time and a RequestError at add/update time.
   - `op_update` applies the same binding when `--ref` or `--kind` changes.
2. **Origin key.**
   - Add `ORIGIN_KEYS |= {"incarnation"}`.
   - `INCARNATION_RE = ^[0-9a-f]{12}$`, validated where origin pairs are parsed (py:363-430) and in `_check_context_values`.
   - Add a helper `context_incarnation(entry) -> str | None`.
3. **Format 3.**
   - `TODO_FORMAT_VERSION = 3`, `TODO_READ_FORMATS = (1, 2, 3)`, `RECOVER_FORMAT = 3`.
   - In `parse_todo`, next to the `PUSH_REF_FORMAT` gate (py:483-485): a file whose format is below 3 and that holds a `recover:` ref or an `incarnation` origin raises `FormatError("… requires format 3")`.
   - The upgrade-on-first-changing-write path (`_commit_todo` py:1029-1036) already renders the current format; check it, and that v1 and v2 files re-render byte-identical when nothing changes.
4. **`op_recovery_apply`** (the core).

   Arguments:
   - `--ref` (required; must parse as recover)
   - `--expect-rev` (`absent` or an int; required)
   - `--incarnation` (12 hex; required)
   - `--state` (`open|unknown|done`)
   - `--outcome` (required, ≤200 characters, no `|`)
   - `--title`, `--group` (optional)
   - `--checked-at` (`now` or a timestamp)
   - `--input` (the context; optional)

   Steps:
   1. Validate everything before loading the store.
   2. A context's origin incarnation must equal `--incarnation`, else exit 2.
   3. `load_todo`; `owner = _ref_owner(store, ref)`.

   | case | result |
   |---|---|
   | `absent` and owner exists | `STALE:c<owner>\|<rev>` |
   | `absent` and no owner | require context and title; allocate the id (`alloc_id`) and a rev; add a `derived=script` item; group defaults to `next` → `ADDED:c<N>\|<rev>` (+ `@NEXT_ID`) |
   | int rev ≠ item rev | `STALE` |
   | item dismissed, no context | `KEPT:c<N>\|dismissed` |
   | item dismissed, recorded incarnation missing | `KEPT:c<N>\|dismissed_no_incarnation` |
   | item dismissed, recorded == given | `KEPT:c<N>\|dismissed` |
   | item dismissed, differs, `--state open` | apply all → `REOPENED` |
   | item dismissed, differs, state ≠ open | `KEPT:c<N>\|dismissed` |
   | item done and `--state open` | apply all → `REOPENED` |
   | otherwise | apply all → `APPLIED`, or `UNCHANGED` when nothing differs |

   Rules for applying:
   - "Apply all" sets `state`, `outcome`, `checked_at`, `title?`, `group?` and the `context?` in memory, takes ONE fresh rev when anything changed, and makes ONE `_commit_todo`.
   - A context change also bumps the rev, as `op_upsert_context` does; here it is the same rev.
   - Never touch `derived` or `kind`.
5. **Wrapper** (`aitask_sitrep_todo.sh`).
   - Add the verb to the dispatch.
   - Add a flag loop like `add`'s (sh:433-453); `--context-file -` maps to `--input -`.
   - It runs under `mutate()`.
   - Header contract lines: the verb, its result lines, and exit codes 0/2/3/4.
6. **Refresh exclusion** (`lib/sitrep_refresh.py` `select_targets`): `if it.kind == "task" and st.parse_recover_ref(it.ref): continue`, placed before the generic task branch. Add a comment pointing at t2299_3.
7. **Ref-consumer inventory.**
   - Run `grep -rn "normalize_ref\|_LOCAL_REF_RE\|parse_push_ref\|ref_owner\|task_ref_id\|_known(" .aitask-scripts/`.
   - For each hit, confirm whether it ignores `recover:` or needs a change (expected: none beyond step 6, because the TUI's `classify` gives `pick_noref` until t2299_3).
   - List the results in Final Implementation Notes.
8. **Fixtures.**
   - Copy today's `tests/fixtures/sitrep/store` to `store_v2/` first.
   - Then edit `store/todo.md`:
     - line 2 becomes format=3;
     - add `c7` (kind=task, open, `ref=recover:t42`, group now, with outcome `crashed · …`);
     - add `c8` (kind=task, dismissed, `ref=recover:t43`);
     - add contexts for both, with `origin: task=t42 incarnation=0123456789ab` and similar.
   - Build them through the real writer, then copy the result in, so they are canonical. Update `next_id` and `next_rev`.
   - Regenerate `expected_list.txt` and `expected_check_sources.txt` with the writer; review the diffs by hand.
9. **Tests.**
   - `tests/test_sitrep_todo.sh`:
     - a new section for the recovery-apply matrix (every row of the table);
     - add/update kind binding (exit 2);
     - a bad incarnation (exit 2);
     - a v2 store plus a `recover:` line (exit 4);
     - Test 16 extended for format 3;
     - new 16c: v2 is read byte-identical and upgraded to 3 on the first changing write, with all other lines unchanged.
   - `tests/test_sitrep_todo_format.py`: round trip of the new fixture.
   - `tests/test_sitrep_refresh.py`: `select_targets` skips a recover item.

## Verification

- `bash tests/test_sitrep_todo.sh`
- `python3 -m pytest tests/test_sitrep_todo_format.py tests/test_sitrep_refresh.py tests/test_sitrep_corpus.py tests/test_sitrep_tui_app.py -q`
- `bash tests/test_sitrep_refresh.sh`, `bash tests/test_sitrep_harvest.sh`, `bash tests/test_sitrep_corpus.sh` (consumers of the store)
- `shellcheck .aitask-scripts/aitask_sitrep_todo.sh`

## Risk

### Code-health risk: medium
- The format bump makes older framework code reading this store report "unsupported format", for example a linked worktree on an old checkout. This is the same trade-off `push:` accepted. · severity: low · → mitigation: TBD
- `recovery-apply` is a second write path for item state, beside `set-state`. Its dismissal exception must not leak to other refs. · severity: medium · → mitigation: the matrix test includes a non-recover ref and a dismissed non-recover item
- Fixture regeneration can silently change expected outputs. · severity: low · → mitigation: review the `expected_*.txt` diffs by hand

### Goal-achievement risk: low
- None identified. The verb contract was reviewed against the atomicity concern.

## Step 9

Post-implementation: commit only this task's paths (`feature: … (t2299_1)`), then archive through Step 9.
