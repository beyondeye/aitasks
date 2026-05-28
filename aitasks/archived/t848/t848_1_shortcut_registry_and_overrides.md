---
priority: medium
effort: medium
depends: []
issue_type: feature
status: Done
labels: [custom_shortcuts]
assigned_to: dario-e@beyond-eye.com
implemented_with: claudecode/opus4_7_1m
created_at: 2026-05-27 17:27
updated_at: 2026-05-28 08:11
completed_at: 2026-05-28 08:11
---

## Context

Foundation child for t848 (customizable shortcuts). Builds the registry that records every TUI's default key bindings and the persistence layer that reads/writes per-user overrides in `aitasks/metadata/userconfig.yaml`. **No TUI is touched in this task** — purely library + tests. Subsequent children (t848_2…t848_6) consume these helpers.

The framework's existing layering (`load_layered_config` in `lib/config_utils.py`) and the precedent of `email:` / `last_used_labels:` in `userconfig.yaml` justify keeping shortcut overrides in the same per-user YAML rather than a sibling file.

## Key Files to Modify

- **NEW** `.aitask-scripts/lib/keybinding_registry.py`
  - `register_app_bindings(scope: str, bindings: list[Binding]) -> list[Binding]` — called by each App. Records `(scope, action_id) -> (default_key, label)` into module-level `_DEFAULTS`. Returns the list, with any `key` field substituted from user overrides.
  - `load_user_overrides() -> dict[str, dict[str, str]]` — reads `aitasks/metadata/userconfig.yaml` (key: `shortcuts:`). Returns `{}` on missing file/key.
  - `resolve_key(scope, action_id, default_key) -> str` — used by label renderer when querying the active key outside of a `Binding`.
  - `coherence_lint(scopes_to_check=None) -> list[str]` — pure function returning warning strings like ``"`quit` is bound to `q` in board but `x` in monitor"``.
  - `SHARED_ACTION_IDS = frozenset({"quit", "tui_switcher", "refresh", "shortcuts_editor"})`.
  - `refresh_all()` / `refresh(scope)` — clears any in-process override cache so live edits via t848_4 see new values.

- **NEW** `.aitask-scripts/lib/shortcut_persist.py`
  - `save_override(scope, action_id, key)` / `clear_override(scope, action_id)` / `reset_scope(scope)`.
  - Writes `aitasks/metadata/userconfig.yaml` atomically. Preserves unrelated top-level keys (`email`, `last_used_labels`).
  - Prefer `ruamel.yaml` if already vendored anywhere under `.aitask-scripts/` (check `lib/config_utils.py` imports); otherwise PyYAML `safe_load` + `safe_dump` is acceptable — comments **don't** need to survive (no existing config helper preserves them).

- **NEW** `tests/test_keybinding_registry.sh` — sources `tests/lib/test_scaffold.sh`, invokes Python one-liners against the new module. Cases:
  1. Empty overrides: `register_app_bindings("board", [Binding("p","pick_task","Pick")])` returns the binding unchanged.
  2. Override present (`shortcuts: {board: {pick_task: o}}`): returned binding has `key == "o"`.
  3. Coherence lint: register `quit` as `q` in scope A and `x` in scope B → returns one warning matching `r'quit.*q.*x'`.
  4. Coherence lint: register `tui_switcher` as `j` in two scopes → returns no warning.
  5. Round-trip: `save_override("board","pick_task","o")` writes the yaml; subsequent `load_user_overrides()` returns `{"board": {"pick_task": "o"}}`; the pre-existing `email:` key survives.
  6. `reset_scope("board")` removes the `board:` subtree but leaves other scopes intact.

## Reference Files for Patterns

- `.aitask-scripts/lib/config_utils.py` — `load_layered_config`, `load_yaml_config`, `deep_merge` (lines 46-147). Use the same YAML helpers; do not re-implement.
- `.aitask-scripts/lib/tui_switcher.py` — pattern of small library module under `lib/` consumed by every App.
- `tests/test_scaffold.sh` — bootstrap pattern for tests touching `aitasks/metadata/userconfig.yaml`. Note: any new top-level `lib/` module sourced by `./ait` must also be added to `setup_fake_aitask_repo()` (per CLAUDE.md). Verify whether `keybinding_registry.py` is loaded at `./ait` startup — likely **not** (only TUIs need it), so no scaffold update required. Confirm by grepping `./ait` for `lib/`.

## Implementation Plan

1. Create `lib/keybinding_registry.py` with module-level `_DEFAULTS: dict[tuple[str,str], tuple[str,str]]` (key=(scope, action_id), value=(default_key, label)) and `_OVERRIDES_CACHE: dict[str, dict[str,str]] | None`.
2. `register_app_bindings` iterates `bindings`, records each `(scope, b.action)` → `(b.key, b.description)`, then if `b.action` has an override, constructs a new `Binding` with the override key (Textual's `Binding` is a frozen dataclass — use `dataclasses.replace`). Return the resulting list.
3. `load_user_overrides()` lazily caches; checks `aitasks/metadata/userconfig.yaml` existence.
4. `coherence_lint` iterates `SHARED_ACTION_IDS`, gathers the effective key per scope (override-then-default), groups scopes by key, emits a warning when more than one group exists.
5. Create `lib/shortcut_persist.py`. Use `os.replace` for atomic write.
6. Write `tests/test_keybinding_registry.sh`. Each test creates a fresh temp `userconfig.yaml`, calls the registry/persist functions via a small Python -c invocation, and asserts via `assert_eq` / `assert_contains` from `tests/lib/test_assert.sh`.

## Verification Steps

```bash
bash tests/test_keybinding_registry.sh
shellcheck tests/test_keybinding_registry.sh
python3 -c "from importlib import import_module; import_module('lib.keybinding_registry')" \
  # run from .aitask-scripts/ to verify the module loads cleanly
```

All assertions must pass and no shellcheck warnings. No behavior change in any TUI is expected since nothing consumes the registry yet.

## Notes for sibling tasks

- The exact `Binding` mutation API (frozen vs not) matters for t848_2's `ShortcutsMixin` — record findings in this child's "Final Implementation Notes" so t848_2 doesn't re-investigate.
- If `ruamel.yaml` ends up vendored, note the import path; t848_5 export/import code may want it for round-trip fidelity.
