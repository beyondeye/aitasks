"""Persistence layer for per-user keyboard shortcut overrides.

Reads/writes the `shortcuts:` section of `aitasks/metadata/userconfig.yaml`,
preserving sibling top-level keys (`email`, `last_used_labels`, ...).

Writes are atomic (`os.replace` of a temp file in the same directory).
YAML comments are not preserved — no existing helper in this framework
preserves them either (`config_utils.save_yaml_config` uses PyYAML safe_dump),
so vendoring `ruamel.yaml` just for shortcuts would be out of proportion.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

import keybinding_registry


_USERCONFIG_HEADER = "# Local user configuration (gitignored, not shared)\n"


def _userconfig_path() -> Path:
    return Path("aitasks/metadata/userconfig.yaml")


def _load_full() -> dict:
    path = _userconfig_path()
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data if isinstance(data, dict) else {}


def _atomic_dump(data: dict) -> None:
    path = _userconfig_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".userconfig.", suffix=".yaml.tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Emit a leading comment so freshly-created files match the
            # convention established by the task-workflow Step 4 userconfig
            # writer. Existing files keep whatever header they had — yaml
            # round-trip strips comments, and we deliberately don't try to
            # preserve them.
            if not path.is_file():
                f.write(_USERCONFIG_HEADER)
            yaml.safe_dump(
                data, f, default_flow_style=False, sort_keys=False, allow_unicode=True
            )
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


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
