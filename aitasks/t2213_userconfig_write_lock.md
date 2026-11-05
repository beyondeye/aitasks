---
priority: low
effort: medium
depends: []
issue_type: bug
status: Ready
labels: [minimonitor, shortcuts]
gates: [risk_evaluated]
anchor: 2212
followup_kind: risk_mitigation
created_at: 2026-11-05 10:52
updated_at: 2026-11-05 10:52
---

## Origin

Risk-mitigation ("after") follow-up for t2212, created at Step 8d after implementation landed.

## Risk addressed

unlocked read-modify-write in userconfig_persist

- `userconfig_persist` is read-modify-write with no lock; two minimonitors toggling at once, or a toggle racing the shortcut editor's save, can drop the other writer's change (pre-existing pattern shared with `shortcut_persist`, now reachable from one more key) · severity: low · → mitigation: userconfig_write_lock

## Goal

Serialize every write to `aitasks/metadata/userconfig.yaml` so concurrent writers cannot drop each
other's changes.

- `.aitask-scripts/lib/userconfig_persist.py` is the single persistence layer: every writer
  (`set_last_used_labels`, `set_minimonitor_key_hints_collapsed` from t2212, and
  `shortcut_persist.save_override` / `clear_override`) does `_load_full()` → mutate → `_atomic_dump()`.
  `_atomic_dump` is atomic per write (temp file + `os.replace`), but the load→dump window is not
  locked, so a second writer's update between them is lost (lost update, not corruption).
- Add one helper that holds an exclusive lock (e.g. `fcntl.flock` on a sibling lock file in the
  metadata dir — check macOS portability) across load+mutate+dump, and route every writer through it.
  The bash `last_used_labels` helpers go through the same Python module, so they are covered once the
  module is.
- Keep the existing guarantees: a malformed file raises `MalformedUserConfigError` before anything is
  written; read-only getters stay lock-free and fail-soft.
- Tests: two writers interleaved (e.g. a writer paused between load and dump while a second writer
  commits) — without the lock one change is lost (negative control), with it both survive; a held lock
  times out with a clear error rather than hanging a TUI's UI thread.
