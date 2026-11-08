---
priority: low
effort: low
depends: []
issue_type: test
status: Ready
labels: [sitrep]
gates: [risk_evaluated]
anchor: 2175
followup_kind: risk_mitigation
created_at: 2026-11-08 08:53
updated_at: 2026-11-08 08:53
---

## Origin

Risk-mitigation ("after") follow-up for t2226, created at Step 8d after implementation landed.

## Risk addressed

GNU tar vs bsdtar exclusion semantics — `tar` exclusion behaviour differs between GNU tar and bsdtar (macOS). · severity: low · → mitigation: macos_tar_exclusion_check

## Goal

t2226 added `copy_framework_tree` (`tests/lib/framework_copy.sh`), which copies the
framework into test fixtures with
`tar -C src --exclude='__pycache__' --exclude='*.pyc' -cf - . | tar -C dst -xmf -`.
It is now used by 26 bash test files (including `tests/lib/sync_fixture.sh`), and
it was only verified with GNU tar 1.35 on Linux.

On a macOS host (bsdtar / libarchive):
- Run `bash tests/test_framework_copy.sh`. Section 1 plants `__pycache__` dirs at
  top level and nested, plus a stray top-level `*.pyc`, and asserts none are copied;
  that every other file, the exec bit and dotfiles survive; and that a copy into an
  existing destination merges with no nesting. Section 2 checks `setup_repo`.
- Confirm bsdtar's `--exclude` is unanchored, so nested `__pycache__` and `*.pyc`
  at any depth are dropped, and that `-m` (no mtime restore) is accepted.
- Spot-run a couple of converted consumers (e.g. `tests/test_crew_runner.sh`,
  `tests/test_sync.sh`).

If bsdtar differs, adjust `copy_framework_tree` (for example, add
`--exclude='*/__pycache__'`) so both tars agree, and keep
`tests/test_framework_copy.sh` green on both platforms.
