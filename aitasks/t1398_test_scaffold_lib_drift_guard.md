---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [script-performance]
created_at: 2026-08-03 22:42
updated_at: 2026-08-03 22:42
---

## Origin

Risk-mitigation ("after") follow-up for t1379, created at Step 8d after implementation landed.

## Risk addressed

Code-health risk (severity: medium), from `aiplans/archived/p1379_*.md`:

> The new lib must be added to `tests/lib/test_scaffold.sh` **and** to ~10
> hand-curated per-test `cp` lists. Those lists are a known-stale surface (t658
> found three already broken), and a missed entry fails with a bare
> `No such file or directory` far from its cause.

This is not hypothetical: during t1379 the omission fired twice before the
scaffold entry was added — `tests/test_issue_import_contributor.sh` lost 4
assertions and `tests/test_brainstorm_cli.sh` failed outright, both with an
error naming the missing lib rather than the test's actual subject.

## Goal

Add a guard test that derives, for each bash test which scaffolds a fake repo,
the set of libs the scripts it copies actually `source` — then fails when a
test's hand-curated `cp` list (or `tests/lib/test_scaffold.sh`'s baseline) is
missing one. The point is to derive the requirement from the canonical site (the
`source` lines in the copied scripts) rather than duplicating a list a third
time.

Cover the Python side too: a scaffolded test that copies `board/`, `brainstorm/`
or `diffviewer/` modules needs the `lib/*.py` those modules import
(`atomic_write.py` is the case t1379 hit).

## Verification Steps

- Removing `atomic_write.sh` from `setup_fake_aitask_repo()` must make the new
  guard fail, naming the tests that would break.
- Removing a lib from one test's curated `cp` list must make the guard fail and
  name that test.
- The guard must pass on the tree as-is.
- Confirm the guard does not false-positive on libs sourced conditionally or
  behind a `[[ -f … ]]` check (several tests copy `repo_fetch.sh` that way).
