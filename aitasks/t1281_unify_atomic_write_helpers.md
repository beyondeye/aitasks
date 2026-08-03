---
priority: low
effort: medium
depends: []
issue_type: refactor
status: Ready
labels: [ait_settings]
anchor: 1223
created_at: 2026-07-28 01:19
updated_at: 2026-08-03 10:46
boardidx: 51200
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

Route the framework's open-coded atomic writers through the shared helper
`.aitask-scripts/lib/atomic_write.py`, deleting each local copy.

**t1371 created that module**; `lib/frontmatter_patch.py` is its only caller so
far. It was written as the consolidation target: stdlib only (so a deliberately
yaml-free CLI can import it) with `config_utils`' semantics — `realpath` before
choosing the temp dir, `fchmod` to the target's existing mode, `makedirs`,
cleanup on `BaseException`, and an explicit "no fsync — atomic *visibility*, not
crash durability" contract in the docstring. Its public surface:

| symbol | purpose |
|---|---|
| `atomic_write(path, render)` | one-shot; resolves `realpath`, then prepare+commit |
| `atomic_write_text(path, text)` | wrapper for callers holding the full text |
| `prepare(path, render)` / `commit(tmp, path)` | the staging split `config_utils.import_all_configs` needs to make several files visible together |
| `target_mode(path)` | target's own mode, else `0o666 & ~umask` |
| `discard(tmp)` | best-effort temp removal |

So this is now a re-pointing exercise, not a design one. **Until it runs,
`atomic_write.py` is an additional implementation rather than a replacement** —
that transitional duplication is the whole reason this task exists.

## Call sites to migrate

Re-surveyed 2026-08-03 during t1371 — there are more than the three originally
recorded:

| site | notes |
|---|---|
| `lib/gate_ledger.py:357` `_atomic_write` | PID-derived fixed temp name, **not `O_EXCL`** — collision-prone across threads. Cleanup in `finally`, so it also runs on success (an extra stat per write). Umask-default mode, no `makedirs`. Also called cross-module from `lib/gate_registry_sync.py:519`. |
| `lib/attachment_meta.py:65` `atomic_write` | `mkstemp`, so the result is left **0600**; no `realpath`. |
| `lib/artifact_manifest.py:132` `atomic_write` | `mkstemp`; validates the record before writing. |
| `lib/config_utils.py:175/196/213` | The most complete — the semantics `atomic_write.py` copied. Preserve the prepare/commit split when re-pointing. |
| `lib/skill_template.py:258` `_atomic_write` | Fixed `.tmp` sibling name and **no cleanup on failure** — leaves residue. |
| `lib/userconfig_persist.py:93` `_atomic_dump` | `mkstemp`; target path implicit. |
| `lib/agent_marks.py:243` `dump` | Already has `realpath` + `fchmod`; closest to the shared helper. |
| `lib/framework_version.py:239-250` | Inline, inside the handoff writer. |
| `chatlink/relay.py:447` `_atomic_write_json`, `chatlink/wizard_draft.py:95-100` | Inline `.tmp` + `os.replace`. |

Naming collision to plan for: `attachment_meta.py` and `artifact_manifest.py`
each define a *function* named `atomic_write`, so importing the module of the
same name into them needs an alias (`from atomic_write import atomic_write as
_atomic_write`) or the local definition removed in the same edit.

The fsync question the original task raised is **already decided** — the shared
helper documents "no fsync". Re-opening it is optional, but the docstring must
stay the single place that says so.

## Verification

- `python3 tests/test_atomic_write.py` — the shared helper's contract tests plus
  its negative controls (t1371). They must keep passing as call sites move onto
  it.
- `python3 tests/test_cross_repo_settings.py` — its mode-preservation, symlink
  and atomicity negative controls already pin the required behavior; they must
  pass unchanged.
- `python3 tests/test_config_utils.py`, `python3 tests/test_gate_ledger.py` and
  the attachment tests must pass unchanged.
- Add a test that the shared helper leaves no `.tmp` residue when the rename
  fails, for each migrated call site.
