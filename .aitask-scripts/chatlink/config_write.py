"""Merge-and-write helper for the chatlink gateway config (t1149_3).

Textual-free on purpose: the wizard screens (``wizard.py``) call this, but
the writer itself is headlessly unit-testable and importable anywhere the
daemon-side modules are.

Write policy (pinned t1149 parent-plan contract — merge, never drop):

- The existing file (if any) is ``yaml.safe_load``-ed and every key the
  wizard did not edit is carried through verbatim — explicitly including
  ``sandbox_env_passthrough`` and unknown/future keys.
- The merge extends **one level into mappings**: when a key exists in both
  the base and the edits and BOTH values are mappings, the edit overlays
  per-subkey instead of replacing the whole mapping — so a pre-existing
  ``intake_channel.metadata`` (or a future provider-specific subkey)
  survives a wizard save that edits only the exposed intake fields.
- A malformed existing file (unparseable YAML / non-mapping top level) is
  an explicit conflict: :class:`ConfigWriteError` is raised and the file is
  left untouched. Callers may retry with ``allow_replace=True`` after the
  user explicitly confirms replacing the file. An empty or fully-commented
  file loads as ``None`` and merges as ``{}`` (normal fresh path).
- PyYAML only (the repo has no ruamel.yaml dep): comments in the existing
  file are not preserved; the output is written under the fixed curated
  header below.
"""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import yaml

#: Curated header written above every wizard-saved config (condensed from
#: seed/chatlink_config.yaml — see that file / the docs for full per-key
#: comments).
HEADER = """\
# chatlink gateway configuration (t1120 chat bridge)
#
# Shared, checked-in config for the chatlink gateway daemon: bug-report
# intake channel, who may initiate, and sandbox resource ceilings.
# Written by the `ait chatlink` config wizard; hand-editing stays fine.
# Full per-key documentation: seed/chatlink_config.yaml (framework repo)
# and the bug-report-intake workflow docs.
#
# The bot token is NOT stored here — it lives in the gitignored per-PC
# file aitasks/metadata/chatlink_sessions/bot_token (0600).
"""


class ConfigWriteError(Exception):
    """Existing config cannot be merged (unparseable YAML or non-mapping
    top level). The file was left untouched."""


#: Edit-value sentinel: remove the key from the config instead of writing
#: a value. This is how the wizard CLEARS an exposed optional field (e.g.
#: an emptied ``repo_name``) — omitting the key would preserve the stale
#: value under the merge-never-drop contract.
DELETE = object()


def _load_base(path: Path, allow_replace: bool) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        if allow_replace:
            return {}
        raise ConfigWriteError(
            f"{path}: existing file is not valid YAML ({exc})") from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        if allow_replace:
            return {}
        raise ConfigWriteError(
            f"{path}: existing top level is not a mapping "
            f"({type(data).__name__})")
    return data


def _merge(base: dict, edits: dict) -> dict:
    """Overlay ``edits`` onto ``base``: top-level keys replace, except when
    both sides hold mappings — those merge one level deep (edited subkeys
    overlaid, unedited subkeys carried through verbatim). An edit value of
    :data:`DELETE` removes the key (at either level) instead."""
    merged = dict(base)
    for key, val in edits.items():
        if val is DELETE:
            merged.pop(key, None)
        elif (isinstance(val, dict)
                and isinstance(merged.get(key), dict)):
            sub = dict(merged[key])
            for subkey, subval in val.items():
                if subval is DELETE:
                    sub.pop(subkey, None)
                else:
                    sub[subkey] = subval
            merged[key] = sub
        else:
            merged[key] = val
    return merged


def write_config(path: str | Path, edits: dict, *,
                 allow_replace: bool = False) -> None:
    """Merge ``edits`` into the config at ``path`` and write it atomically
    (tmp file + ``os.replace`` in the target dir) under :data:`HEADER`.

    Raises :class:`ConfigWriteError` (file untouched) when the existing
    file cannot be merged, unless ``allow_replace`` is true.
    """
    path = Path(path)
    merged = _merge(_load_base(path, allow_replace), edits)
    body = yaml.dump(merged, default_flow_style=False, sort_keys=False,
                     allow_unicode=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(HEADER)
            fh.write("\n")
            fh.write(body)
        os.replace(tmp_name, path)
    except BaseException:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise
