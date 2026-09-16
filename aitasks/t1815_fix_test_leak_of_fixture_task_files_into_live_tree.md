---
priority: medium
effort: low
depends: []
issue_type: bug
status: Ready
labels: [trails, python]
gates: [risk_evaluated]
anchor: 1794
followup_kind: upstream_defect
created_at: 2026-09-16 11:20
updated_at: 2026-09-16 11:20
---

## Origin

Spawned from t1809 during Step 8b review.

## Upstream defect

- `tests/test_data_branch_setup.sh:779-781 — zero-byte fixture task files (t1_alpha.md, t2_beta.md, t10_gamma.md) leak into the live aitasks/ tree and are tracked on the aitask-data branch (swept in by 2dabfae81, "ait: Auto-commit task changes before sync", 2026-08-27; t1_alpha.md rewritten 2026-09-02, so the leak recurs). These names are written by this test's Test 11 and by tests/test_boardcol_update.sh; which run actually leaks them is NOT proven — the Test 11 subshell appears isolated. They make every By-Trail discovery toast report "Trail scan skipped 4 unreadable active task file(s)".`

## Diagnostic context

Surfaced while fixing t1809 (trail_gather plan containment in a linked
worktree). The three files are visible in the live tree today:

```
-rw-r--r-- 0 2026-09-02 09:09 aitasks/t1_alpha.md
-rw-r--r-- 0 2026-08-27 14:22 aitasks/t2_beta.md
-rw-r--r-- 0 2026-08-27 14:22 aitasks/t10_gamma.md
```

`./ait git ls-files` lists all three, so they are **committed on the
aitask-data branch**, not merely untracked local debris — removing them needs a
scoped `./ait git` commit, not an `rm`.

`./ait git log --diff-filter=A` attributes their addition to a single syncer
auto-commit (`2dabfae81`), which means the sweep captured them rather than a
test committing them directly. The differing mtime on `t1_alpha.md` (2026-09-02
vs 2026-08-27 for the other two) shows at least two separate leak events, so
this is recurring rather than a one-off.

`tests/test_data_branch_setup.sh:779-781` writes exactly these three names with
`: >` (zero-byte, matching what is on disk), but it does so inside
`(cd "$TMPDIR_11/local/.aitask-data" || exit 1 ...)` — which looks correctly
isolated. `tests/test_boardcol_update.sh` seeds `t1_alpha.md` / `t2_beta.md`
too, but with content rather than empty. The actual leaking path is therefore
unproven and needs reproduction before any fix.

## Suggested fix

Reproduce first — run each suspect test from a dirty cwd and watch whether
`aitasks/` gains the files (a failed `setup_data_branch` inside the subshell
would leave the `cd` target missing and could drop the writes into the live
tree). Fix that test's isolation (cwd or TASK_DIR), then delete the three files
with a path-scoped `./ait git` commit once no other session owns them.
