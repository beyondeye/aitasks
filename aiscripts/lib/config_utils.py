"""config_utils - Shared layered config loading/saving for aitasks Python tools.

Provides JSON config file management with a per-project / per-user override
pattern. Project configs are git-tracked; user configs use .local.json suffix
and are gitignored.

Usage:
    from config_utils import load_layered_config, save_project_config

    config = load_layered_config(
        "aitasks/metadata/board_config.json",
        defaults={"auto_refresh_minutes": 5},
    )
"""
from __future__ import annotations

import copy
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_EXPORT_PATTERNS = [
    "*_config.json",
    "*_config.local.json",
    "models_*.json",
    "models_*.local.json",
]


def local_path_for(project_path: str | Path) -> Path:
    """Derive the .local.json path from a project config path.

    board_config.json -> board_config.local.json
    models_claude.json -> models_claude.local.json
    """
    p = Path(project_path)
    return p.with_name(p.name.replace(".json", ".local.json"))


def deep_merge(base: dict, override: dict) -> dict:
    """Recursively merge override into base following aitasks merge rules.

    - Dict values: recursive merge (override individual keys)
    - List values: override replaces entire list
    - Scalar values: override replaces base
    - Keys only in base are preserved
    - Keys only in override are added

    Returns a new dict (does not mutate inputs).
    """
    result = copy.deepcopy(base)
    for key, val in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(val, dict):
            result[key] = deep_merge(result[key], val)
        else:
            result[key] = copy.deepcopy(val)
    return result


def _load_json(path: Path) -> dict:
    """Load a JSON file. Returns {} if file does not exist."""
    if not path.is_file():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_layered_config(
    project_path: str | Path,
    local_path: str | Path | None = None,
    defaults: dict | None = None,
) -> dict:
    """Load and merge a layered config: defaults <- project <- local (per-user).

    Args:
        project_path: Path to the per-project config JSON (git-tracked).
        local_path: Path to the per-user override JSON (gitignored).
                    If None, derived by inserting '.local' before '.json'.
        defaults: Optional base defaults dict. If provided, serves as the
                  bottom layer.

    Returns:
        Merged config dict. Missing files are silently skipped.

    Raises:
        json.JSONDecodeError: If a config file exists but contains invalid JSON.
    """
    project = Path(project_path)
    local = Path(local_path) if local_path is not None else local_path_for(project)

    result = copy.deepcopy(defaults) if defaults else {}
    project_data = _load_json(project)
    if project_data:
        result = deep_merge(result, project_data)
    local_data = _load_json(local)
    if local_data:
        result = deep_merge(result, local_data)
    return result


def _save_json(path: Path, data: dict) -> None:
    """Write a dict as formatted JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")


def save_project_config(path: str | Path, data: dict) -> None:
    """Write a project-level config to JSON.

    Creates parent directories if they don't exist.
    Writes with indent=2 and trailing newline.
    """
    _save_json(Path(path), data)


def save_local_config(path: str | Path, data: dict) -> None:
    """Write a per-user config to JSON (gitignored overrides only).

    Same format as save_project_config. Caller is responsible for
    ensuring the path uses the .local.json naming convention.
    """
    _save_json(Path(path), data)


def split_config(
    merged: dict,
    project_keys: set[str] | None = None,
    user_keys: set[str] | None = None,
) -> tuple[dict, dict]:
    """Split a merged config dict back into project and user layers.

    Args:
        merged: The fully merged config dict.
        project_keys: Keys that belong in the project config. If None, all keys
                      not in user_keys are considered project keys.
        user_keys: Keys that belong in the per-user config. If None, defaults
                   to empty set (everything goes to project).

    Returns:
        Tuple of (project_dict, user_dict).

    If a key appears in both sets, it goes to user_keys (user wins).
    Keys not in either set go to the project dict.
    """
    user_keys = user_keys or set()
    project_keys = project_keys or set()

    project_dict: dict[str, Any] = {}
    user_dict: dict[str, Any] = {}

    for key, val in merged.items():
        if key in user_keys:
            user_dict[key] = copy.deepcopy(val)
        elif project_keys and key not in project_keys:
            # Key not in either explicit set — default to project
            project_dict[key] = copy.deepcopy(val)
        else:
            project_dict[key] = copy.deepcopy(val)

    return project_dict, user_dict


def export_all_configs(
    output_path: str | Path,
    metadata_dir: str | Path,
    patterns: list[str] | None = None,
) -> dict:
    """Bundle all config JSON files from metadata_dir into a single export file.

    Args:
        output_path: Path to write the export JSON bundle.
        metadata_dir: Path to aitasks/metadata/ directory.
        patterns: Glob patterns to match config files. Defaults to
                  *_config.json, *_config.local.json, models_*.json,
                  models_*.local.json.

    Returns:
        The export dict that was written.
    """
    meta_path = Path(metadata_dir)
    if patterns is None:
        patterns = DEFAULT_EXPORT_PATTERNS

    files: dict[str, Any] = {}
    for pattern in patterns:
        for filepath in sorted(meta_path.glob(pattern)):
            if not filepath.is_file():
                continue
            name = filepath.name
            if name in files:
                continue
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    files[name] = json.load(f)
            except (json.JSONDecodeError, ValueError):
                raw = filepath.read_text(encoding="utf-8")[:500]
                files[name] = {"_error": "invalid JSON", "_raw": raw}

    bundle: dict[str, Any] = {
        "_export_meta": {
            "version": 1,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "file_count": len(files),
        },
        "files": files,
    }

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return bundle


def import_all_configs(
    input_path: str | Path,
    metadata_dir: str | Path,
    overwrite: bool = False,
) -> list[str]:
    """Restore config files from an export bundle.

    Args:
        input_path: Path to the export JSON bundle.
        metadata_dir: Path to aitasks/metadata/ directory.
        overwrite: If True, overwrite existing files. If False, skip them.

    Returns:
        List of filenames that were written.

    Raises:
        FileNotFoundError: If input_path does not exist.
        json.JSONDecodeError: If the bundle is invalid JSON.
        ValueError: If the bundle format is unrecognized or a filename
                    contains path separators.
    """
    inp = Path(input_path)
    with open(inp, "r", encoding="utf-8") as f:
        bundle = json.load(f)

    if "files" not in bundle:
        raise ValueError("Invalid export bundle: missing 'files' key")

    meta_path = Path(metadata_dir)
    meta_path.mkdir(parents=True, exist_ok=True)

    written: list[str] = []
    for name, data in bundle["files"].items():
        # Security: prevent path traversal
        if os.sep in name or "/" in name or "\\" in name:
            raise ValueError(f"Invalid filename in bundle: {name!r}")

        # Skip error entries
        if isinstance(data, dict) and "_error" in data:
            continue

        target = meta_path / name
        if target.exists() and not overwrite:
            continue

        with open(target, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.write("\n")
        written.append(name)

    return written
