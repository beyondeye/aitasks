---
Task: t2080_fix_run_provenance_paths_under_subdir_registry.md
Base branch: main
Output branch: main
---

# t2080 — Root-relative run provenance under a subdirectory registry

## Context

`runner.provenance()` (`goengines/internal/testmap/runner/invoke.go:189`) records
`gitx.ModifiedPaths`, which is always **top-level-relative** (`git status
--porcelain`). When `aitestmap/` lives in a subdirectory (engine root = `sub/`,
git prefix `sub/`):

- the `.aitask-testmap/` filter misses `sub/.aitask-testmap/...`;
- `record.json`'s `modified[]` is in a different path space from every other
  engine path (ids, closure, covers, registry — all root-relative).

M3.4 anchor eligibility (`cost/eligibility.go`) fails closed on this with
`eligibility-error:root-not-toplevel`, so a subdirectory registry never anchors
on a dirty tree.

## Approach

Make the modified set **root-relative**, keeping paths outside the root (a test
can read them) as `../`-climbing relative paths. Conversion is injective for a
fixed prefix, and no engine path (ids, closure, covers — `deps` rejects `..`)
ever starts with `../`, so outside-root paths can never falsely match; a
builtin runner's `cwd`-joined `../tok` now compares correctly. Then the
`root-not-toplevel` guard is no longer needed and is removed.

## Steps

1. **`goengines/internal/gitx/status.go`** — add
   `func (r Repo) DirModifiedPaths(ctx) ([]string, error)`: `Prefix` +
   `ModifiedPaths`, each path rebased onto `Dir` by an unexported
   `rebase(prefix, p string) string`:
   - prefix `""` → `p` unchanged;
   - drop the leading segments `p` shares with the prefix (never `p`'s last
     segment, so the result always names `p`), then prepend one `../` per
     remaining prefix segment. E.g. prefix `sub/x/`: `sub/x/a`→`a`,
     `sub/y`→`../y`, `top`→`../../top`.
   - re-sort the result (rebasing changes order). Doc comment: "relative to
     Dir; paths outside Dir climb with `../`".
2. **`goengines/internal/testmap/runner/invoke.go`** — add exported
   `ModifiedPaths(ctx, git gitx.Repo) ([]string, error)` = `DirModifiedPaths`
   minus `StateDir` / `StateDir+"/"…` (moved out of `provenance()`), and make
   `provenance()` call it. Update the `Record.Modified` comment
   ("root-relative; outside the root as `../`").
3. **`goengines/internal/testmap/cost/eligibility.go`** — `load()` uses
   `runner.ModifiedPaths` (drops its duplicated StateDir filter and the
   `Prefix` call); remove `inputs.prefix` and the `root-not-toplevel` case.
4. **Tests**
   - `gitx/status_test.go`: `TestDirModifiedPaths` — repo with `sub/x/a`,
     `sub/y`, `top`; from `Dir=sub/x` expect `["../../top", "../y", "a"]`;
     from the top level equal to `ModifiedPaths`. Keep
     `TestPrefixAndTopLevelRelativeStatus` (still true of `ModifiedPaths`).
   - `runner/provenance_test.go` (`package runner`):
     `TestProvenanceSubdirectoryRoot` — no `.gitignore` for the state dir,
     untracked `sub/.aitask-testmap/r/x`, dirty `sub/src/mod` and `outside`;
     the **existing** `provenance(ctx, gitx.Repo{Dir: sub})` returns
     `["../outside", "src/mod"]` (state dir filtered, root-relative). It calls
     only pre-existing API, so it compiles against the unchanged code and
     fails there on behaviour (`[outside sub/.aitask-testmap/r/x sub/src/mod]`).
   - `cost/eligibility_test.go`: replace `TestEligibilityRootNotTopLevel`
     with `TestEligibilitySubdirectoryRoot` (`eligRepo(t, "sub/", nil)`):
     dirty `sub/docs/readme.md` + top-level `outside.txt` → anchors
     (positive control); dirty `sub/tests/test_a.sh` → `test-file`; dirty
     `sub/tests/lib/helper.sh` → `closure:tests/lib/helper.sh` (proves the
     prefix is stripped — an unstripped path would anchor falsely).
   - **Red proof (order matters):** write the runner and eligibility
     regressions **first** — both use only existing APIs — and run them
     against the unchanged code: expect the unfiltered top-level-relative
     set from `provenance()` and `eligibility-error:root-not-toplevel`. Only
     then implement Steps 1–3 (introducing `DirModifiedPaths` /
     `runner.ModifiedPaths`) and add `TestDirModifiedPaths`, which tests the
     new helper directly and so has no pre-fix red.
5. **`goengines/README.md`** — gitx row: add `DirModifiedPaths` (+ test
   name); record row: `modified` = start ∪ end of root-relative paths
   (`../` outside the root) minus `.aitask-testmap/`; eligibility row: drop
   "the repo root must be the git top level", swap the test name.

## Verification

- `cd goengines && go vet ./... && go test ./internal/gitx/ ./internal/testmap/runner/ ./internal/testmap/cost/`
- `ait engine test` (full go vet + go test).
- Red proof recorded in Final Implementation Notes.

## Post-implementation

Step 9 of the task workflow: commit, archive, no merge (current branch).

## Risk

### Code-health risk: low
- Small, contained change in two engine packages plus one gitx helper; the StateDir filter is deduplicated rather than copied · severity: low · → mitigation: none

### Goal-achievement risk: low
- Relaxing `root-not-toplevel` lets subdirectory registries anchor; a test reading an outside-root file the scanner cannot see is the same residual as an unreferenced in-root read at the top level (literal outside references are already `unresolved` → opaque) · severity: low · → mitigation: none
