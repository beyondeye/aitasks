#!/usr/bin/env python3
"""aitask_install_merge - Merge seed config files into existing project files.

Invoked by install.sh during `ait upgrade --force` to preserve user customizations
in seed-installed config files. Existing destination values always win; only keys
absent from the destination are copied from the seed.

Usage:
    aitask_install_merge.py yaml       <src> <dest>
    aitask_install_merge.py json       <src> <dest>
    aitask_install_merge.py json-models <src> <dest>
    aitask_install_merge.py text-union <src> <dest>

Semantics:
- yaml/json: deep-merge with dest winning. New keys from src are added at any nesting
  depth. Existing dest keys keep their values (scalars, lists, and sub-dicts). Lists
  are treated atomically — not merged element-wise.
- json-models: deep-merge JSON objects with dest winning, except the top-level
  "models" arrays are unioned by model identity. Existing dest model entries are
  preserved unchanged; seed-only model entries are appended in seed order.
- text-union: line-oriented union. Dest order is preserved; src lines not already
  present in dest are appended in src order.
- If dest does not exist, the file is copied as-is (no merge needed).

Exit codes:
- 0: success (merge applied or copy performed)
- 1: parse error or I/O failure (stderr has details; dest is left untouched)
- 2: usage error
"""
from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / "lib"))

from config_utils import deep_merge  # noqa: E402


def _die(msg: str, code: int = 1) -> None:
    print(f"[aitask_install_merge] {msg}", file=sys.stderr)
    sys.exit(code)


def _copy_if_dest_missing(src: Path, dest: Path) -> bool:
    if dest.exists():
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dest)
    return True


def merge_yaml(src: Path, dest: Path) -> None:
    import yaml

    if _copy_if_dest_missing(src, dest):
        return
    try:
        with open(src, "r", encoding="utf-8") as f:
            src_data = yaml.safe_load(f) or {}
        with open(dest, "r", encoding="utf-8") as f:
            dest_data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        _die(f"YAML parse error: {e}")
    if not isinstance(src_data, dict) or not isinstance(dest_data, dict):
        _die(f"Top-level YAML value must be a mapping in both {src} and {dest}")
    merged = deep_merge(src_data, dest_data)
    with open(dest, "w", encoding="utf-8") as f:
        yaml.safe_dump(merged, f, default_flow_style=False, sort_keys=False)


def merge_json(src: Path, dest: Path) -> None:
    if _copy_if_dest_missing(src, dest):
        return
    try:
        with open(src, "r", encoding="utf-8") as f:
            src_data = json.load(f)
        with open(dest, "r", encoding="utf-8") as f:
            dest_data = json.load(f)
    except json.JSONDecodeError as e:
        _die(f"JSON parse error: {e}")
    if not isinstance(src_data, dict) or not isinstance(dest_data, dict):
        _die(f"Top-level JSON value must be an object in both {src} and {dest}")
    merged = deep_merge(src_data, dest_data)
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")


def _model_entry_key(entry: object) -> tuple[str, str]:
    if isinstance(entry, dict):
        name = entry.get("name")
        if isinstance(name, str) and name:
            return ("name", name)
        cli_id = entry.get("cli_id")
        if isinstance(cli_id, str) and cli_id:
            return ("cli_id", cli_id)
    canonical = json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return ("json", canonical)


def merge_json_models(src: Path, dest: Path) -> None:
    if _copy_if_dest_missing(src, dest):
        return
    try:
        with open(src, "r", encoding="utf-8") as f:
            src_data = json.load(f)
        with open(dest, "r", encoding="utf-8") as f:
            dest_data = json.load(f)
    except json.JSONDecodeError as e:
        _die(f"JSON parse error: {e}")
    if not isinstance(src_data, dict) or not isinstance(dest_data, dict):
        _die(f"Top-level JSON value must be an object in both {src} and {dest}")
    src_models = src_data.get("models")
    dest_models = dest_data.get("models")
    if not isinstance(src_models, list) or not isinstance(dest_models, list):
        _die(f"Top-level 'models' value must be a list in both {src} and {dest}")

    merged_models = list(dest_models)
    existing_keys = {_model_entry_key(entry) for entry in dest_models}
    for entry in src_models:
        key = _model_entry_key(entry)
        if key not in existing_keys:
            merged_models.append(entry)
            existing_keys.add(key)

    merged = deep_merge(src_data, dest_data)
    merged["models"] = merged_models
    with open(dest, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2)
        f.write("\n")


def merge_text_union(src: Path, dest: Path) -> None:
    if _copy_if_dest_missing(src, dest):
        return
    with open(dest, "r", encoding="utf-8") as f:
        dest_lines = f.read().splitlines()
    with open(src, "r", encoding="utf-8") as f:
        src_lines = f.read().splitlines()
    existing = set(dest_lines)
    additions = [line for line in src_lines if line not in existing]
    if not additions:
        return
    combined = dest_lines + additions
    with open(dest, "w", encoding="utf-8") as f:
        f.write("\n".join(combined) + "\n")


MODES = {
    "yaml": merge_yaml,
    "json": merge_json,
    "json-models": merge_json_models,
    "text-union": merge_text_union,
}


def main(argv: list[str]) -> None:
    if len(argv) != 4:
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    mode, src_arg, dest_arg = argv[1], argv[2], argv[3]
    if mode not in MODES:
        _die(f"Unknown mode '{mode}' (expected: {', '.join(MODES)})", code=2)
    src = Path(src_arg)
    dest = Path(dest_arg)
    if not src.is_file():
        _die(f"Source file not found: {src}")
    try:
        MODES[mode](src, dest)
    except OSError as e:
        _die(f"I/O error: {e}")


if __name__ == "__main__":
    main(sys.argv)
