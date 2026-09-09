---
priority: medium
effort: medium
depends: []
issue_type: test
status: Ready
labels: [script-performance]
followup_kind: risk_mitigation
created_at: 2026-08-03 22:42
updated_at: 2026-08-13 23:07
boardidx: 3072
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

## Inbox
<!-- Appended by the note framework. Do not edit by hand; use `./ait note`. -->

> **✉ note:t1745** id=2026-09-09T05:45:10Z.e73193acc69977ca9350a79b from=t1745 from_verified=yes at=2026-09-09T05:45:10Z base=56f8810ca5163322b81ebb943d70edd708a58d7a base_branch=main dirty=yes host=omg16
>
> | t1745 landed a *derivation* for the Python side of the copy-list drift class you
> | guard against. This may change your approach; it is context, not an instruction.
> | 
> | What landed (commit 56f8810ca, `bug: Derive the fixture startup-source closure
> | instead of hand-listing it (t1745)`):
> | 
> | - `tests/lib/shell_startup_closure.py` — reads the startup `source` chain out of
> |   the scripts themselves and copies its transitive closure. Raises on an empty
> |   closure and on a referenced lib missing under `lib_dir`.
> | - `tests/test_desync_state.py` — its private seven-name list (which had gone
> |   stale on `stale_lock.sh` since t1725_1) now calls `copy_startup_closure()`.
> | - `tests/test_shell_startup_closure.py` — a **format-contract test** asserting
> |   that every column-0 `source` line in every scanned lib uses one of three
> |   recognised spellings. Measured 0 offenders at the time of writing.
> | - `aidocs/framework/shell_conventions.md` — the `source-on-startup` bullet now
> |   states the contract: a lib needed at startup is sourced unconditionally, at
> |   column 0, in one of those spellings; lazy/conditional stays indented.
> | 
> | Two things that bear on a guard design:
> | 
> | 1. **A derivation may beat a guard where the consumer can compute the list.** It
> |    removes the class rather than detecting drift in it. That is only available
> |    where a fixture builds its copy set programmatically — the shell scaffold's
> |    own hand-maintained "Current baseline" list in `shell_conventions.md` is not
> |    in that position and is still a duplicate.
> | 2. **Classifying startup-vs-lazy by parsing shell was prototyped and rejected.**
> |    Lexical function-body depth falsely flags the idiomatic top-level conditional
> |    `if [[ -r … ]]; then source "${SCRIPT_DIR}/lib/opt.sh"; fi`, turning a
> |    legitimate edit into a suite-wide failure. The shipped design enforces the
> |    written convention and tests that contract instead of inferring intent. If
> |    your guard plans to detect "is this a startup source", that result is worth
> |    knowing before you build it.
> | 
> | Scope note: t1745 swept the whole suite for this class and found exactly ONE
> | Python fixture with a private copy list over `task_utils.sh`'s startup chain
> | (`test_desync_state.py`). Every shell test that copies `task_utils.sh` already
> | goes through `tests/lib/test_scaffold.sh`. So the ~10 per-test `cp` lists your
> | task cites are a shell-side surface that t1745 did not touch.
