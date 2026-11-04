---
Task: t2190_pre_frontmatter_archived_records_fail_closed_scans.md
Base branch: main
Output branch: main
---

# t2190 — Give archived t20–t22 an empty frontmatter block; drop sitrep's legacy exemption

## Context

`aitasks/archived/_b0/old0.tar.zst` holds three records written before YAML
frontmatter existed: t20 (plain prose that contains a later `---` rule), and
t21/t22 (the inline header `--- effort:med pri:…` on line 1, with a `---`
further down). Measured on the real repo, `iter_archived_frontmatter(errors=…)`
over all 2,421 archived records reports exactly these three as
`unparseable frontmatter`, so every fail-closed archive scan reports itself
incomplete:

- **trail discovery** (`trail_discovery._read_archived_unit` →
  `archive_iter.parse_archived_frontmatter(errors=unit_errors)`): the bundle is
  never cached, and `trail_links.build_export()` always carries the three
  entries in `scan_errors`. As a result, a cross-project linked-trails scan of
  this repo always comes back `PARTIAL`.
- **sitrep fold scan** (`sitrep_refresh.TaskIndex._build_folds`): t2175_3 worked
  around it with a local exemption (`_pre_frontmatter` +
  `_LEGACY_INLINE_HEADER_RE`).

**User decision (approach A):** fix the data, not the reader. Prepend an empty
YAML frontmatter block to t20–t22 inside the bundle, inventing no metadata.
Verify that their bodies and every other bundle member are unchanged. Remove
sitrep's legacy exemption, so a record without frontmatter stays a scan error
everywhere. The shared reader contract (`archive_iter`, including the existing
`t3_none.md` "headerless is reported" test) is not touched.

**Prefix choice — `---\n{}\n---\n` (measured):**

| prefix | `task_yaml.parse_frontmatter` | `stats_data.split_frontmatter` | bash `read_yaml_field` |
|---|---|---|---|
| `---\n{}\n---\n` | `({}, <old text>)`, body byte-identical | `{}`; body differs from before only by the trailing newline the line-joiner always drops | frontmatter-only search; no field |
| `---\n\n---\n` | same | same | same |
| `---\n---\n` | **raises** (ParserError / ComposerError — the later `---` is taken as the closer) | `{}` | — |

`---\n{}\n---\n` is exactly what `task_yaml.serialize_frontmatter({}, body, [])`
writes (verified for all three records), so re-saving the record later changes
nothing. Before the migration, `read_yaml_field` searched the whole file of these
records, because line 1 was not `---`. Their only `key:`-shaped body lines are
`COMPLETED: …`, which no caller reads, so no real field changes value.

**Consumer inventory after the migration:**
- trail discovery: `{}` → no owner records, no unit errors → the bundle is cacheable and the export is complete.
- sitrep: the fold scan reads `{}` → no folds (same result the exemption gave). `lookup("20")` → archived, no status →
  `reminder_verdict` gives `unknown "archived with status (none)"` and `landed_state` gives `unverifiable`. **Never done.**
- stats: metadata `{}` both before and after; body differs only by the trailing newline → no change in counts.
- codebrowser history / board archived lookups: t20–t22 now yield `{}` instead of being skipped. They appear as
  archived records with no status. Nothing depends on t20–t22.

## Implementation

### Pre-phase (risk mitigations)

1. [bundle_matches_committed_blob] Before any rewrite, prove that git holds a
   rollback copy. `git -C .aitask-data hash-object aitasks/archived/_b0/old0.tar.zst`
   must equal `git -C .aitask-data rev-parse HEAD:aitasks/archived/_b0/old0.tar.zst`,
   and `./ait git status --porcelain -- aitasks/archived/_b0/` must be empty.
   Record both ids. Stop if either check fails: the bundle has uncommitted
   changes made by someone else.

### Main steps

1. **Migration script** (one-time; lives in the scratchpad, not the repo; it is
   recorded verbatim in Final Implementation Notes as closure evidence):
   `<scratchpad>/t2190_migrate_b0.py`, run from the repo root.
   - Constants: `BUNDLE=aitasks/archived/_b0/old0.tar.zst`, and
     `EXPECTED_SHA=883ee79b652ff53052f2a4013ac79668942b26e797af457507c2e252870f431c`
     (measured during planning). `TARGETS` = the three exact member names
     (`./t20_skill_creating_aitask.md`, `./t21_rewrite_aitask_create_as_script.md`,
     `./t22_task_attributes_in_task_create.md`). `PREFIX=b"---\n{}\n---\n"`.
   - Refuse: the bundle sha256 differs from `EXPECTED_SHA`, a target is missing,
     a target already starts with `b"---\n"` (already migrated), or `zstd -dc` exits non-zero.
   - Read all members: `zstd -dc` into memory, then `tarfile` mode `r:`.
     Collect `(TarInfo, bytes|None)` in order.
   - Build the new tar (`tarfile.GNU_FORMAT`). Each `TarInfo` is a `copy.copy`
     of the original. Only the three targets change: `data = PREFIX + old` and
     the size is updated. Name, type, mode, uid/gid, uname/gname, mtime and
     member order are preserved.
   - Compress with `zstd -q -c` (default level, same as `_archive_create` in
     `lib/archive_utils.sh`). Write to `aitasks/archived/_b0/.t2190-old0.tar.zst`,
     a name outside the `_b*/old*.tar.zst` glob, so a concurrent scan never takes
     it for a bundle. fsync.
   - **Verify the temp file before the swap.** Every check must hold:
     - `zstd -t` passes; `zstd -dc tmp | tar -tf -` exits 0, and its listing equals the old listing line for line;
     - the production reader `archive_iter.iter_archive_file(tmp, errors=errs)` leaves `errs == []`;
     - the same member count and order; for every member, the header tuple
       (name, type, mode, uid, gid, uname, gname, mtime, linkname) is equal;
     - every non-target member: size and bytes equal;
     - each target: `new == PREFIX + old`, and
       `task_yaml.parse_frontmatter(new.decode()) == ({}, old.decode(), [])`.
   - Default mode is dry-run (verify, then delete the temp file). `--write`
     re-hashes the bundle (compare-and-swap against `EXPECTED_SHA`) and then
     calls `os.replace(tmp, BUNDLE)`. It prints `OLD_SHA:` / `NEW_SHA:`. On any
     failure the temp file is removed and the bundle is left untouched.
   - Run the dry-run first, then `--write`.

2. **Real-repo check of the data alone** (exemption still in place):
   `iter_archived_frontmatter(Path("aitasks/archived"), task_yaml parse, errors=errs)`
   gives `errs == []` (it was 3), with the same yielded count + 3.

3. **`.aitask-scripts/lib/sitrep_refresh.py`** — remove the exemption:
   - delete the `if rank > 0 and _pre_frontmatter(text): …` branch in `take()` (lines ~366–371);
   - delete `_LEGACY_INLINE_HEADER_RE` and `_pre_frontmatter()` (lines ~434–455);
   - `_build_folds` docstring: any read or parse failure of a task-named record
     is a scan error, *including a record with no frontmatter at all, active or archived*.

4. **`tests/test_sitrep_refresh.py`** — replace `PreFrontmatterArchive` with
   `HeaderlessArchivedRecords`. Keep the `T20/T21/T22_SHAPE` constants, with the
   comment changed to say they are the pre-migration shapes. Add
   `MIGRATED = "---\n{}\n---\n"`.
   - `test_headerless_archived_records_fail_the_scan`: for each shape (subTest,
     with a fresh tree), a bundle holding that record plus `t30` with
     `folded_tasks: [12]` → `verdict("12")` is unknown with `fold scan` in the
     outcome, and `_fold_errors` names that record.
   - `test_migrated_records_complete_the_scan`: a bundle holding `MIGRATED + shape`
     ×3 plus t30 → `verdict("12") == Verdict("done", "folded into t30 (t30: archived)")`
     and `_fold_errors == []`.
   - `test_a_migrated_historical_task_is_never_made_done`: t20/21/22 →
     `unknown`, `"archived with status (none)"`; `landed_state` is `unverifiable`.
   - Keep (moved into the new class): the headerless shapes themselves stay
     `unknown … unparseable frontmatter`; incomplete modern frontmatter, unknown
     dash header, malformed archived YAML, headerless ACTIVE file and unreadable
     archived record all still go down the scan-error path.
   - **Red proof (isolated mutant):** a scratch tree holding `tests/test_sitrep_refresh.py`
     (new) and `.aitask-scripts/lib/` with the HEAD `sitrep_refresh.py` (exemption
     present). Expect `test_headerless_archived_records_fail_the_scan` to fail
     there and every other new or kept test to pass. Never mutate the live tree.

### Step 9 reference
Current-branch mode: no merge. Step 9 runs build verification / gates, then
`aitask_archive.sh 2190` and `./ait git push`.

## Verification

- `python3 tests/test_sitrep_refresh.py`, `bash tests/test_sitrep_refresh.sh`,
  `python3 tests/test_archive_iter_consolidated.py`,
  `python3 tests/test_archive_iter_characterization.py`,
  `python3 tests/test_stats_split_frontmatter.py`, then the whole suite with
  `bash tests/run_all_python_tests.sh` (read the last-line verdict; no pipe).
- Real repo, after step 3: `sitrep_refresh.TaskIndex(".")._build_folds()` →
  `_fold_errors == []`. `python3 .aitask-scripts/lib/trail_links.py export` →
  the JSON shows `"scan_errors": []` (it refreshes the gitignored trail cache;
  that is expected).
- `shellcheck` is not affected (no shell edits).

## Commit (Step 8, after "Commit changes")

Commit the data first, then the code:
1. `./.aitask-scripts/aitask_task_commit.sh -m "ait: Give archived t20-t22 an empty frontmatter block for t2190" aitasks/archived/_b0/old0.tar.zst`
2. `git commit -F - -- .aitask-scripts/lib/sitrep_refresh.py tests/test_sitrep_refresh.py` with
   `bug: Drop sitrep's pre-frontmatter exemption after migrating archived t20-t22 (t2190)`.

If the user picks "Abort" before the commit: restore the bundle only if its sha
still equals the `NEW_SHA` we wrote (we own that content). Do this with
`./ait git checkout -- aitasks/archived/_b0/old0.tar.zst`, then re-check that
the sha equals `EXPECTED_SHA`.

## Risk

### Code-health risk: medium
- Rewriting a committed historical bundle could silently drop or alter one of its 82 members (tar metadata, order, or bytes) · severity: medium · → mitigation: inline pre-phase bundle_matches_committed_blob (in addition to the script's member-level check and compare-and-swap before the swap)
- Best-effort readers (codebrowser history, board archived lookup) now yield t20–t22 with `{}` metadata where they used to skip them · severity: low · → mitigation: TBD (the inventory finds nothing that depends on them)

### Goal-achievement risk: low
- A frontmatter parser outside the probed set (task_yaml, stats_data, bash `read_yaml_field`) could read `---\n{}\n---\n` differently · severity: low · → mitigation: TBD
- Another checkout that pulls the new code before its data branch syncs would have its sitrep fold scan fail closed on the stale bundle until `ait git pull` · severity: low · → mitigation: TBD

### Planned mitigations
- timing: pre-phase | name: bundle_matches_committed_blob | type: chore | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — rewriting a committed historical bundle could drop/alter a member | desc: before the rewrite, assert the working-tree bundle equals the committed blob at the data-branch HEAD and `_b0/` has no uncommitted changes, so git holds a rollback copy

(Post-inline reassessment: the levels are unchanged. Code-health stays medium
because the rewrite is still a data mutation, and the pre-phase only
guarantees a rollback for it.)
