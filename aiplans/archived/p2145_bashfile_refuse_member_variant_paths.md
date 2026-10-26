---
Task: t2145_bashfile_refuse_member_variant_paths.md
Base branch: main
Output branch: main
---

# t2145 — file-unit adapters: refuse inventoried paths the id grammar reads as member/variant

## Context

The `bash-file` builtin (`goengines/internal/testmap/runner/builtin/bashfile.go:93`)
lists any bound script whose root-relative path `registry.ParseID` accepts.
`ParseID` cuts `@` (variant) and `#` (member) off the path, so a committed
`tests/test_a#b.sh` parses as path `tests/test_a` + member `b.sh`. The row is
listed, but the unit can never pass: the run ends `UNIT …|error` with
`PROTOCOL_ERROR missing_start` (it fails closed, but it never passes).

**Correction to the task's premise (measured in planning):** the pytest guard the
task tells us to copy (`id, err := registry.ParseID(rel); err != nil || id.String() != rel`)
**does not refuse these paths either**. When `ParseID` succeeds, `String()` gives back
the input exactly. Probe results: `tests/test_a#b.sh`, `tests/test_a@v.sh`,
`tests/x#m@v.sh` and `tests/test_a#b.py` all parse and convert back to the same
string. Only orderings `ParseID` already rejects (e.g. `a@b#c`) fail. So
`pytestList` (`pytest.go:537`) has the same latent hole.

**The rule already exists: `registry.CheckPath`** (`registry/id.go:97`). It is the
`<path>` part of the id grammar: non-empty, repository-relative, no `\`, no
empty/`.`/`..` segment, and (through `checkChars`) no `#`, `@`, `|`, whitespace
or control character. `TestCheckPath` already covers `a#b` / `a@b`, and
`bashFileUnitCheck` already uses it on the run side. `ParseID` on a string with
no `#`/`@` is exactly `checkPath`, so `CheckPath(rel) == nil` is precisely "parses
as a plain file id". (A review of the first draft of this plan, which added a
duplicate `fileUnitID` helper, made this point.) Both discovery sites call it
directly, and no new helper or grammar table is added.

No path in this repository contains `#` or `@` (`git ls-files | grep -c '[#@]'` → 0),
so nothing that loads today stops loading.

## Implementation

### 1. `bashfile.go` `bashFileList` (line ~93)

```go
if err := registry.CheckPath(rel); err != nil || strings.ContainsFunc(p, unicode.IsControl) {
	return fmt.Errorf("%q cannot be a unit id (a plain file id: no '#' member, no '@' variant, no control character)", rel)
}
```

### 2. `pytest.go` `pytestList` (line ~537)

```go
if err := registry.CheckPath(rel); err != nil || strings.ContainsFunc(p, unicode.IsControl) || strings.Contains(p, "::") {
	return fmt.Errorf("%q cannot be a pytest unit (a plain file id: no '#' member, no '@' variant, no control character, no \"::\")", rel)
}
```

The `ContainsFunc` control check on `p` is now covered by `CheckPath(rel)`
(`p` is a suffix of `rel`). It is kept anyway, as it stands today, so this change
touches only the id clause. The `"::"` substring stays in the message, because
`TestPytestOptionShapedPath` asserts on it.

### 3. Tests (adapter-level, no new grammar table; `TestCheckPath` stays the grammar oracle)

- **`bashfile_linux_test.go`** new `TestBashFileFragmentPathsRefused`: for each of
  `tests/test_a#b.sh` and `tests/test_a@v.sh` (subtests), use a `bashRepo` with
  that file (`exit 0`) plus `tests/test_ok.sh` (`exit 0`):
  - call `bashFileList` directly and assert an error that names the path and
    contains `no '#' member`, with **no rows** (`buf.Len() == 0`);
  - `loadErr(t, r, "RUNNER_PROTOCOL:b|list|", <path>)` (the shared helper in
    `pytest_linux_test.go`, same package).
- **`pytest_linux_test.go`**: extend `TestPytestOptionShapedPath`, which already
  holds the `::` refusal, with `tests/test_a#b.py` and `tests/test_a@v.py`. Each
  gets `loadErr(t, r, <path>, "no '#' member")`. Update its doc comment to name
  the fragment refusal.

### 4. `goengines/README.md`

- bash-file row (line ~298), Inventory: add "a bound path that is not a plain file
  id (`registry.CheckPath`: a `#` member or `@` variant, a control character, …)
  refuses the list"; add `TestBashFileFragmentPathsRefused` to its test list.
- pytest row (line ~299), Discovery: change "a path with `::` refused" to "a path
  with `::`, or one that is not a plain file id (`#`, `@`, …), refused".

### 5. Isolated red proof

With the tests in place, use the Edit tool (no git restore, no stash) to
temporarily put the old clause back at both sites (`if id, err := registry.ParseID(rel); err != nil || id.String() != rel || …`
in pytest; `if _, err := registry.ParseID(rel); err != nil || …` in bash-file). Run
`go test ./internal/testmap/runner/builtin/ -run 'TestBashFileFragmentPathsRefused|TestPytestOptionShapedPath' -count=1`
and confirm both fail on the `#`/`@` cases. Then restore the `CheckPath` clauses
with Edit, re-run, and confirm green. Record both outputs in Final Implementation
Notes.

## Verification

```bash
cd goengines
gofmt -l ./internal/testmap/runner/builtin/
go vet ./internal/testmap/runner/builtin/
AIT_TESTMAP_REQUIRE_REAL_TOOLS=1 go test ./internal/testmap/runner/builtin/ -count=1
go test ./internal/testmap/... -count=1
```

## Step 9 reference

Post-implementation: commit the code (`bug: … (t2145)`), commit the plan through
`aitask_task_commit.sh`, then archive per Step 9. Current-branch mode, so there is
no merge.

## Risk

### Code-health risk: low
None identified. A one-clause change at each of two sites, reusing the existing
`registry.CheckPath` rule; no new structure.

### Goal-achievement risk: low
None identified. The equivalence (`CheckPath` ≡ fragment-free `ParseID`) is
measured, both adapters get an end-to-end regression, and the red proof shows the
old clause fails it.

## Post-Review Changes

### Change Request 1 (2026-10-26 13:10)
- **Requested by user:** `TestBashFileFragmentPathsRefused` paired the invalid path with `tests/test_ok.sh`, which sorts *after* `tests/test_a…`, so `buf.Len() == 0` never proved that a row accumulated before a later invalid file is withheld (an immediate-write overlay still passed).
- **Changes made:** the valid fixture is now `tests/test_0_ok.sh` (sorts first); the test's doc comment says why. Mutant check: replacing the buffered `fmt.Fprintf(&rows, …)` with `fmt.Fprintf(w, …)` makes both subtests fail with a leaked `tests/test_0_ok.sh\tfile\ttests/test_0_ok.sh` row; with the buffer restored, the builtin package is green (`AIT_TESTMAP_REQUIRE_REAL_TOOLS=1`). Not applied to pytest: `pytestList` refuses while building its argv, before any row exists.
- **Files affected:** `goengines/internal/testmap/runner/builtin/bashfile_linux_test.go`

## Final Implementation Notes
- **Actual work done:** `bashFileList` (`bashfile.go`) and `pytestList` (`pytest.go`) now call `registry.CheckPath(rel)` instead of `registry.ParseID(rel)` (pytest additionally dropped its no-op `id.String() != rel`), so an inventoried path with a `#` member or `@` variant refuses the listing with a message naming the path. The messages now say which grammar was violated (`a plain file id: no '#' member, no '@' variant, …`); pytest keeps `"::"`. Regressions: new `TestBashFileFragmentPathsRefused` (direct `bashFileList` call with no rows + `runner.Load` error, for `#` and `@`, with a valid fixture that sorts before the invalid one); `TestPytestOptionShapedPath` extended with `tests/test_a#b.py` / `tests/test_a@v.py`. `goengines/README.md` bash-file and pytest rows updated (rule + test name).
- **Deviations from plan:** first draft added a `fileUnitID` helper in `inventory.go` with its own grammar table; at plan review it was replaced by the existing `registry.CheckPath` (equivalent to fragment-free `ParseID`, already covered by `TestCheckPath`, already used by `bashFileUnitCheck`). One post-review test strengthening (Change Request 1).
- **Issues encountered:** the task's premise that the pytest adapter already refuses these paths was false: `ParseID` + `String()` round-trips, so `id.String() != rel` never fires once parsing succeeds (probe: `tests/test_a#b.sh`, `tests/test_a@v.sh`, `tests/x#m@v.sh`, `tests/test_a#b.py` all round-trip). Fixed in pytest too.
- **Key decisions:** kept the existing control-character check on `p` at both sites even though `CheckPath(rel)` now covers it, so that each site changes only its id clause.
- **Red proofs (isolated, Edit-only, no git restore/stash):**
  - old clauses restored at both sites → `TestBashFileFragmentPathsRefused` fails (`err <nil> rows "tests/test_a#b.sh\tfile\ttests/test_a#b.sh\n…"`, same for `@`), and `TestPytestOptionShapedPath` fails (`Load succeeded, want an error containing ["tests/test_a#b.py" "no '#' member"]`);
  - immediate-write mutant in `bashFileList` (`fmt.Fprintf(w, …)`) → both subtests fail with a leaked `tests/test_0_ok.sh` row.
  - Fix restored → `AIT_TESTMAP_REQUIRE_REAL_TOOLS=1 go test ./internal/testmap/runner/builtin/ -count=1` ok; `go test ./internal/testmap/... -count=1` all ok; gofmt/vet clean.
- **Upstream defects identified:** None
