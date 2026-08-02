---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [ait_settings]
anchor: 1223
created_at: 2026-07-28 01:19
updated_at: 2026-07-28 01:19
boardidx: 290
---

## Origin

Risk-mitigation ("after") follow-up for t1223_4, created at Step 8d after
implementation landed.

## Risk addressed

From `aiplans/p1223/p1223_4_cross_repo_settings_seam.md`, code-health risk:

> This task adds a **third** temp-file + `os.replace` implementation alongside
> `gate_ledger._atomic_write` and `attachment_meta.atomic_write`, which already
> differ from each other. · severity: low · → mitigation:
> unify_atomic_write_helpers

## Goal

Extract the three atomic-write implementations into one shared helper with
consistent semantics, then route all three call sites through it.

Current state (verified during t1223_4):

| | `gate_ledger._atomic_write:357-373` | `attachment_meta.atomic_write:65-78` | `config_utils._prepare_atomic` / `_commit_atomic` (new) |
|---|---|---|---|
| temp creation | `os.path.join` + PID-derived fixed name (not `O_EXCL`, collision-prone across threads) | `tempfile.mkstemp` | `tempfile.mkstemp` |
| cleanup trigger | `finally` — also runs on success (an extra `os.path.exists` stat per write) | `except BaseException` | `except BaseException` |
| resulting mode | umask default | **0600** (inherits `mkstemp`) | preserves the target's existing mode, else `0o666 & ~umask` |
| `makedirs` | no | yes | yes |
| symlink handling | replaces the link itself | replaces the link itself | resolves with `realpath` first |
| `fsync` | no | no | no |

The `config_utils` version is the most complete and is the natural base. Two of
its properties are load-bearing and must survive the unification:

- **Mode preservation.** `mkstemp` creates 0600; without an explicit `fchmod` to
  the target's existing mode, a rewrite silently downgrades a 0644 config
  (`models_claudecode.json` is 0644 in a normal checkout).
- **`realpath` before choosing the temp dir.** `open(path, "w")` follows a
  symlink but `os.replace` replaces the link itself, orphaning the real backing
  file while reads keep succeeding.

Also decide explicitly whether the shared helper should `fsync` before the
rename. None of the three do today; `os.replace` alone gives atomic *visibility*
against concurrent readers but not crash durability. Whichever is chosen, say so
in the docstring rather than leaving "atomic" ambiguous.

`config_utils` additionally exposes a `_prepare_atomic` / `_commit_atomic` split
(used to stage several files before any becomes visible). The shared helper
should keep that split available, with `_atomic_write` as the one-shot wrapper.

## Verification

- `python3 tests/test_cross_repo_settings.py` — its mode-preservation, symlink
  and atomicity negative controls already pin the required behavior; they must
  pass unchanged.
- `python3 tests/test_config_utils.py`, `python3 tests/test_gate_ledger.py` and
  the attachment tests must pass unchanged.
- Add a test that the shared helper leaves no `.tmp` residue when the rename
  fails, for each of the three call sites.
