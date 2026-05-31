---
Task: t868_manual_verification_fix_shortcut_persist_yaml_guard_followup.md
Worktree: (none — working on current branch per profile 'fast')
Branch: main
Base branch: main
---

# Auto-Verification Log: shortcut-persist YAML guard (t868, verifies t865)

Autonomous auto-verification of the manual checklist for t865's fix
(guard `userconfig_persist._load_full()` against malformed YAML; write paths
fail loud, read paths degrade). The four checklist items describe TUI behavior
that is exercised here through the implementer's own unit tests plus direct
logic smokes — the import-time read hooks and the modal `action_save()` logic
are the determinants of the behavior the manual steps observe.

## Execution Log

### Item 1 — malformed config: save shows error toast, modal stays open
- Item text: With a deliberately malformed `userconfig.yaml`, open the shortcut
  editor, rebind a key, press `s` to save — confirm an error toast ("Cannot
  save shortcuts: ... Fix or delete userconfig.yaml") and the modal stays OPEN.
- Approach: CLI invocation of the modal unit suite (Textual `App` driven via
  the project's direct-method modal test).
- Action run: `python3 tests/test_shortcut_editor_modal.py`
- Output (trimmed): `Ran 17 tests in 0.768s / OK`. The targeted case
  `test_save_aborts_on_malformed_config` writes a malformed
  `userconfig.yaml`, sets a pending rebind, calls `action_save()`, and asserts
  `app.notify(..., severity="error")` fired AND `dismiss` was NOT called AND
  the pending edit survived. The error string in
  `shortcut_editor_modal.py:264-266` is exactly
  `"Cannot save shortcuts: {exc}. Fix or delete userconfig.yaml, then retry."`.
- Verdict: pass

### Item 2 — failed save leaves userconfig.yaml byte-for-byte unchanged
- Item text: After that failed save, confirm `userconfig.yaml` is byte-for-byte
  unchanged — `email` and `last_used_labels` are NOT erased.
- Approach: Direct logic smoke (scratch workspace) + unit/bash test corroboration.
- Action run: scratch `userconfig.yaml` =
  `email: me@x.test\nlast_used_labels: [a, b]\n- orphan\n`; `sha256sum` before;
  `shortcut_persist.save_override("board","pick","o")` under
  `TASK_DIR=<scratch>/aitasks`; `sha256sum` after.
- Output (trimmed): `save_override` raised `MalformedUserConfigError`; sha256
  identical before/after (`958f0f00…a4c573`); file still contained `email` and
  `last_used_labels`. `_load_full()` raises before any `_atomic_dump`, so no
  whole-file overwrite occurs. Corroborated by
  `test_shortcut_editor_modal.py::test_save_aborts_on_malformed_config` (file
  unchanged) and `tests/test_keybinding_registry.sh` Case 8 (9/9 pass).
- Verdict: pass

### Item 3 — valid config: rebind+save persists + success toast (regression)
- Item text: With a VALID `userconfig.yaml`, repeat the rebind+save and confirm
  the normal success toast still appears and the override persists.
- Approach: Direct logic smoke (scratch workspace) + unit test corroboration.
- Action run: valid scratch config; `shortcut_persist.save_override("board",
  "pick","o")`; re-read YAML; then `clear_override("board","pick")`; re-read.
- Output (trimmed): override persisted (`shortcuts.board.pick == "o"`); `email`
  and `last_used_labels` siblings preserved; after `clear_override` the
  `shortcuts` key is removed and siblings remain intact. The modal success path
  (`test_save_persists_and_clears`) confirms `action_save()` on a valid config
  reaches the information-severity success notify and `dismiss(None)`, with the
  `email` sibling preserved.
- Verdict: pass

### Item 4 — malformed config: TUIs launch normally (read-side degrade)
- Item text: With a malformed `userconfig.yaml` present, confirm TUIs still
  launch normally (overrides ignored, no crash at import).
- Approach: Direct logic smoke of the import-time read hooks (run with cwd
  inside a malformed workspace) + bash test corroboration.
- Action run: `cd <scratch>` (malformed `aitasks/metadata/userconfig.yaml`);
  `keybinding_registry.load_user_overrides()`; and separately
  `userconfig_persist.get_last_used_labels()` under `TASK_DIR=<scratch>/aitasks`.
- Output (trimmed): `load_user_overrides()` returned `{}` with a stderr warning
  (`keybinding_registry: ignoring malformed …`) and NO exception (exit 0);
  `get_last_used_labels()` returned `[]` with a stderr warning. These are the
  startup read hooks every TUI hits; both degrade to defaults rather than
  raising. Corroborated by `tests/test_keybinding_registry.sh` Case 7 and
  `tests/test_last_used_labels.sh` (18/18 pass).
- Verdict: pass
- Note: A full visual `ait board` launch against a malformed file was NOT run.
  `ait` cd's to the repo root and the board reads the cwd-relative
  `aitasks/metadata/userconfig.yaml`; exercising the malformed case via a real
  launch would require corrupting the real, user-owned (gitignored)
  `userconfig.yaml`, which the auto-verification procedure forbids. The
  import-time read hooks that determine whether a TUI crashes at launch are
  verified above to degrade gracefully.

## Cleanup

- Scratch workspaces under `${TMPDIR:-/tmp}/auto_verify_868_*` — removed.
- No tmux sessions created.
- No user-owned files mutated (only the checklist task file was annotated).
