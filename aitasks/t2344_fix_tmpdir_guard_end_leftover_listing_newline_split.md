---
priority: low
effort: low
depends: []
issue_type: bug
status: Ready
labels: [tests, test_infrastructure, tmp_cleanup]
gates: [risk_evaluated]
anchor: 2290
followup_kind: upstream_defect
created_at: 2026-11-22 11:35
updated_at: 2026-11-22 11:35
---

## Origin
Spawned from t2301 during Step 8b review.

## Upstream defect
- `tests/lib/tmpdir_guard.sh:tmpdir_guard_end` — the leftover listing (t2290/t2302 code) still splits `find` output on newlines, so a leftover whose name contains a newline is reported as two entries; the count errs high, so strict mode stays fail-safe.

## Diagnostic context
t2301 made the guard's stale-dir and orphan-control discovery NUL-delimited
(`find … -print0 | LC_ALL=C sort -z` + `read -r -d ''`) after a review showed
that a base path containing a newline handed the verdict a different path.
`tmpdir_guard_end`'s own leftover listing was left as it was:

    listing="$(find "$_TG_DIR" -mindepth 1 -maxdepth 1 2>/dev/null)"
    … while IFS= read -r f; do … done < <(printf '%s\n' "$listing" | LC_ALL=C sort)

A leftover named `a<newline>b` is listed as two names (`a`, `b`), and
`_TG_LEFTOVER_COUNT` is one too high. That count only feeds the warn-only
report and strict mode's "0 means clean" check, so it errs in the fail-safe
direction (strict fails a run it should fail anyway), but the report names
entries that do not exist.

## Suggested fix
List with `find "$_TG_DIR" -mindepth 1 -maxdepth 1 -print0` and read with
`read -r -d ''` (sort with `sort -z`); keep the "listing succeeded" signal
(`listed=1` only when find exits 0) that strict mode relies on. Add a case to
`tests/test_tmpdir_guard.sh` with a leftover whose name contains a newline:
the report names it once and the count is 1.
