"""Persistence layer for per-user keyboard shortcut overrides.

Reads/writes the `shortcuts:` section of `aitasks/metadata/userconfig.yaml`,
preserving sibling top-level keys (`email`, `last_used_labels`, ...).

The low-level whole-file round-trip (`_load_full` / `_atomic_dump`) lives in
`userconfig_persist`, the single persistence module for userconfig.yaml, so the
shortcut writer and the bash `last_used_labels` writer can never disagree on the
file's representation. Writes are atomic; YAML comments are not preserved.
"""

from __future__ import annotations

import keybinding_registry

from userconfig_persist import _atomic_dump, _load_full


def save_override(scope: str, action_id: str, key: str) -> None:
    """Persist `shortcuts.<scope>.<action_id> = key`, refresh the cache."""
    data = _load_full()
    shortcuts = data.setdefault("shortcuts", {})
    if not isinstance(shortcuts, dict):
        shortcuts = {}
        data["shortcuts"] = shortcuts
    scope_map = shortcuts.setdefault(scope, {})
    if not isinstance(scope_map, dict):
        scope_map = {}
        shortcuts[scope] = scope_map
    scope_map[action_id] = key
    _atomic_dump(data)
    keybinding_registry.refresh(scope)


def clear_override(scope: str, action_id: str) -> None:
    """Drop a single override; remove empty scope/shortcuts containers."""
    data = _load_full()
    shortcuts = data.get("shortcuts")
    if not isinstance(shortcuts, dict):
        return
    scope_map = shortcuts.get(scope)
    if not isinstance(scope_map, dict) or action_id not in scope_map:
        return
    del scope_map[action_id]
    if not scope_map:
        del shortcuts[scope]
    if not shortcuts:
        del data["shortcuts"]
    _atomic_dump(data)
    keybinding_registry.refresh(scope)


def reset_scope(scope: str) -> None:
    """Remove every override for `scope`, leaving other scopes intact."""
    data = _load_full()
    shortcuts = data.get("shortcuts")
    if not isinstance(shortcuts, dict) or scope not in shortcuts:
        return
    del shortcuts[scope]
    if not shortcuts:
        del data["shortcuts"]
    _atomic_dump(data)
    keybinding_registry.refresh(scope)
