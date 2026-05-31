---
priority: medium
effort: low
depends: []
issue_type: bug
status: Done
labels: [tui]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_8
created_at: 2026-05-31 10:27
updated_at: 2026-05-31 11:16
completed_at: 2026-05-31 11:16
---

## Origin

Spawned from t863 during Step 8b review.

## Upstream defect

- `.aitask-scripts/lib/shortcut_persist.py:34-35 — _load_full() calls yaml.safe_load without catching yaml.YAMLError; a malformed (gitignored) aitasks/metadata/userconfig.yaml therefore raises a ParserError on the shortcut-editor write paths (save_override / clear_override / reset_scope). Same bug class as keybinding_registry.load_user_overrides(), which was guarded in t863. The helper already guards the missing-file case (if not path.is_file(): return {}) but not the malformed-content case.`

## Diagnostic context

While fixing t863 (an unguarded `yaml.safe_load` in `keybinding_registry.load_user_overrides()` that crashed every board/TUI at *import time*), the Step 8b sanity-check inspected the sibling module `shortcut_persist.py`, which reads/writes the same `aitasks/metadata/userconfig.yaml`. Its `_load_full()` helper (`shortcut_persist.py:30-36`) has the identical pattern: it guards the missing-file case but calls `yaml.safe_load(f)` with no try/except. A malformed userconfig.yaml therefore raises and crashes `save_override` / `clear_override` / `reset_scope`.

Unlike `keybinding_registry` (which runs at module-import time via every TUI's `register_app_bindings()` chain), `_load_full()` only runs on interactive shortcut-editor writes, so the blast radius is the save/clear/reset action rather than TUI launch — lower severity, but the same defect class.

## Suggested fix

Wrap the `yaml.safe_load(f)` in `_load_full()` in a `try/except yaml.YAMLError`, mirroring the t863 fix and the existing missing-file fallback.

**Important nuance (do not blindly copy t863):** `shortcut_persist` *writes back* via `_atomic_dump`, which rewrites the whole file. A silent `{}` fallback on a corrupt file means the next `save_override` would overwrite userconfig.yaml from `{}`, destroying the user's other top-level keys (`email`, `last_used_labels`). For a read-only consumer like `keybinding_registry` the `{}` fallback is harmless, but here the write path should likely **abort the save with a clear error** (and warn the user) rather than silently discard unparseable content. Decide between read-side graceful-degrade and write-side fail-loud accordingly.
