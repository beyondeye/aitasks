"""Single persistence layer for the per-user (gitignored) userconfig.yaml.

This module is the canonical home for reading and writing top-level keys of
`aitasks/metadata/userconfig.yaml` (`email`, `last_used_labels`, `shortcuts`,
…). `shortcut_persist` and the bash `last_used_labels` helpers both go through
the `_load_full` / `_atomic_dump` round-trip defined here, so no two writers can
disagree on the file's representation.

Every write round-trips the **whole file** through `yaml.safe_load` /
`yaml.safe_dump` and replaces it atomically (`os.replace` of a temp file in the
same directory). That is what makes the file safe against the writer-style
collision that previously corrupted it: no caller ever line-edits a multi-line
YAML value, so a block-style value can never be left with orphaned `- item`
continuation lines.

`last_used_labels` is emitted in flow style (`[a, b]`) for compactness; nested
mappings such as `shortcuts:` stay in block style.

YAML comments are not preserved across a round-trip (PyYAML safe_dump drops
them); the standard header comment is re-emitted only for freshly-created
files. No existing framework helper preserves comments either
(`config_utils.save_yaml_config` uses PyYAML safe_dump), so this matches the
established convention.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import yaml


_USERCONFIG_HEADER = "# Local user configuration (gitignored, not shared)\n"


class _FlowList(list):
    """A list subclass rendered in YAML flow style (``[a, b]``)."""


def _represent_flow_list(dumper, data):
    return dumper.represent_sequence(
        "tag:yaml.org,2002:seq", list(data), flow_style=True
    )


yaml.SafeDumper.add_representer(_FlowList, _represent_flow_list)


def _userconfig_path() -> Path:
    """Path to userconfig.yaml, honoring the ``TASK_DIR`` env override.

    Defaults to ``aitasks`` (relative to cwd) when ``TASK_DIR`` is unset, which
    matches the framework default and the path TUIs use after chdir-ing to the
    repo root. The bash helpers pass ``TASK_DIR`` through explicitly so tests
    and non-default layouts target the right file.
    """
    base = os.environ.get("TASK_DIR", "aitasks")
    return Path(base) / "metadata" / "userconfig.yaml"


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

    # Emit last_used_labels in flow style ([a, b]) while leaving nested mappings
    # (e.g. shortcuts:) in block style. Normalize on a shallow copy so the
    # caller's dict is not mutated.
    labels = data.get("last_used_labels")
    if isinstance(labels, list) and not isinstance(labels, _FlowList):
        data = {**data, "last_used_labels": _FlowList(labels)}

    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=".userconfig.", suffix=".yaml.tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            # Re-emit the standard header only for freshly-created files; a
            # round-trip of an existing file drops comments (PyYAML).
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


def get_last_used_labels() -> list[str]:
    """Return the last_used_labels list (empty if absent or not a list)."""
    val = _load_full().get("last_used_labels")
    if val is None:
        return []
    if isinstance(val, str):
        # Tolerate a stray scalar "a,b" just in case.
        return [s.strip() for s in val.split(",") if s.strip()]
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return []


def set_last_used_labels(labels: list[str]) -> None:
    """Persist last_used_labels, round-tripping the whole file safely."""
    data = _load_full()
    data["last_used_labels"] = list(labels)
    _atomic_dump(data)


def _csv_to_list(csv: str) -> list[str]:
    return [s.strip() for s in csv.split(",") if s.strip()]


def _main(argv: list[str]) -> int:
    if not argv:
        sys.stderr.write(
            "usage: userconfig_persist.py {get-labels|set-labels [csv]}\n"
        )
        return 2
    cmd = argv[0]
    if cmd == "get-labels":
        print(",".join(get_last_used_labels()))
        return 0
    if cmd == "set-labels":
        set_last_used_labels(_csv_to_list(argv[1] if len(argv) > 1 else ""))
        return 0
    sys.stderr.write(f"unknown command: {cmd}\n")
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
