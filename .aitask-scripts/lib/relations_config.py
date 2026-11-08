#!/usr/bin/env python3
"""relations_config.py - the ``relations:`` block of project_config.yaml (t1981_3).

Design: aidocs/framework/task_relations.md D5 ("Configuration", "Activation is
visible") and the "Worker API" section.

* ``load(root)`` - the effective configuration, with the D5 defaults. Read fresh
  by every job (no caching here).
* ``set_enabled(root, value)`` / ``seed_project_name(root, name)`` - SURGICAL,
  line-based edits of ``aitasks/metadata/project_config.yaml``: the file keeps
  its comments and layout. Every edit is re-parsed before it replaces the file,
  and the parsed result must equal the original parse with exactly the one
  intended change; otherwise nothing is written (``ConfigWriteError``). This is
  a primitive: its callers (``ait relations enable|disable``, setup's
  ``ask_relations_activation``) commit through ``aitask_metadata_commit.sh``.
* ``resolve_project_name(root)`` - the project-name rule of ``enable``: keep an
  existing valid ``project.name``; otherwise seed it only from ONE unambiguous
  registry binding of this repository root; otherwise refuse with how to set it.

CLI (used by ``aitask_setup.sh``)::

    relations_config.py state <root>           -> RELATIONS_KEY:absent|true|false|invalid
                                                  RELATIONS_CAP:<max_jobs_per_day>
    relations_config.py set-enabled <root> true|false
        -> [PROJECT_NAME:kept|seeded:<name>] ENABLED_SET:<v>  (exit 0)
        |  PROJECT_UNRESOLVED:<why> / WRITE_FAILED:<why>     (exit 1)
"""
from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

_LIB = os.path.dirname(os.path.abspath(__file__))
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

import config_utils  # noqa: E402

DEFAULTS = {
    "max_jobs_per_day": 40,
    "job_timeout_s": 600,
    "settle_s": 120,
    "candidate_cap": 25,
}
TRIGGERS = ("created", "plan_approved", "fold", "landed")
_PROJECT_RE = re.compile(r"^[a-z0-9_-]+$")
RESOLVE_SCRIPT = os.path.join(os.path.dirname(_LIB), "aitask_project_resolve.sh")


class ConfigWriteError(RuntimeError):
    """A config edit could not be applied safely; the file is untouched."""


class ProjectUnresolved(RuntimeError):
    """No valid project name could be kept or unambiguously seeded."""


@dataclasses.dataclass
class RelationsConfig:
    enabled: bool
    enabled_key: str  # "absent" | "true" | "false" | "invalid"
    max_jobs_per_day: int
    job_timeout_s: int
    settle_s: int
    candidate_cap: int
    triggers: dict

    def trigger_enabled(self, trigger: str) -> bool:
        return bool(self.triggers.get(trigger, True))


def config_path(root) -> Path:
    return Path(root, os.environ.get("TASK_DIR", "aitasks"), "metadata", "project_config.yaml")


def _read_cfg(root) -> dict:
    try:
        cfg = config_utils.load_yaml_config(config_path(root))
    except Exception:  # an unreadable config is "disabled", never "enabled"
        return {}
    return cfg if isinstance(cfg, dict) else {}


def _pos_int(value, default):
    if isinstance(value, int) and not isinstance(value, bool) and value > 0:
        return value
    return default


def load(root) -> RelationsConfig:
    rel = _read_cfg(root).get("relations")
    rel = rel if isinstance(rel, dict) else {}
    raw = rel.get("enabled", None) if "enabled" in rel else None
    if "enabled" not in rel:
        key = "absent"
    elif raw is True:
        key = "true"
    elif raw is False:
        key = "false"
    else:
        key = "invalid"
    trig = rel.get("triggers")
    trig = trig if isinstance(trig, dict) else {}
    triggers = {t: (trig.get(t) is not False) for t in TRIGGERS}
    return RelationsConfig(
        enabled=raw is True,
        enabled_key=key,
        max_jobs_per_day=_pos_int(rel.get("max_jobs_per_day"), DEFAULTS["max_jobs_per_day"]),
        job_timeout_s=_pos_int(rel.get("job_timeout_s"), DEFAULTS["job_timeout_s"]),
        settle_s=_pos_int(rel.get("settle_s"), DEFAULTS["settle_s"]) if rel.get("settle_s") != 0 else 0,
        candidate_cap=_pos_int(rel.get("candidate_cap"), DEFAULTS["candidate_cap"]),
        triggers=triggers,
    )


# ------------------------------------------------------------ surgical edits

_TOP_RE = re.compile(r"^([A-Za-z_][\w-]*):(.*)$")


def _is_top_level(line: str) -> bool:
    return bool(line) and not line[0].isspace() and not line.startswith("#")


def _scalar(value) -> str:
    """A YAML literal that round-trips to ``value`` (bool or string)."""
    if isinstance(value, bool):
        return "true" if value else "false"
    import yaml
    text = str(value)
    if yaml.safe_load(text) == text and ":" not in text and "#" not in text:
        return text
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def edit_nested(text: str, block: str, key: str, value) -> str:
    """Return ``text`` with ``<block>.<key>`` set to ``value`` (line-based).

    Replaces the key's line inside the block, inserts it as the block's first
    child, or appends the block. Refuses a block header carrying an inline value
    (flow style), which a line edit cannot handle.
    """
    lines = text.split("\n")
    literal = _scalar(value)
    header = None
    for i, line in enumerate(lines):
        m = _TOP_RE.match(line)
        if m and m.group(1) == block:
            rest = m.group(2).split("#", 1)[0].strip()
            if rest:
                raise ConfigWriteError(f"unsupported_shape:{block} has an inline value")
            header = i
            break
    if header is None:
        tail = "" if text.endswith("\n") or not text else "\n"
        return text + tail + f"{block}:\n  {key}: {literal}\n"
    end = len(lines)
    for j in range(header + 1, len(lines)):
        if _is_top_level(lines[j]):
            end = j
            break
    indent = None
    for j in range(header + 1, end):
        stripped = lines[j].lstrip()
        if stripped and not stripped.startswith("#"):
            indent = lines[j][: len(lines[j]) - len(stripped)]
            break
    indent = indent or "  "
    key_re = re.compile(rf"^{re.escape(indent)}{re.escape(key)}:(\s|$)")
    for j in range(header + 1, end):
        if key_re.match(lines[j]):
            lines[j] = f"{indent}{key}: {literal}"
            return "\n".join(lines)
    lines.insert(header + 1, f"{indent}{key}: {literal}")
    return "\n".join(lines)


def _guarded_write(path: Path, old_text: str, new_text: str, block: str, key: str, value) -> None:
    import yaml
    try:
        before = yaml.safe_load(old_text) if old_text.strip() else {}
        after = yaml.safe_load(new_text)
    except yaml.YAMLError as exc:
        raise ConfigWriteError(f"reparse_failed:{exc.__class__.__name__}") from None
    before = before if isinstance(before, dict) else {}
    if not isinstance(after, dict):
        raise ConfigWriteError("reparse_failed:not a mapping")
    expected = dict(before)
    sub = dict(expected.get(block) or {}) if isinstance(expected.get(block), dict) or expected.get(block) is None else None
    if sub is None:
        raise ConfigWriteError(f"unsupported_shape:{block} is not a mapping")
    sub[key] = value
    expected[block] = sub
    if after != expected:
        raise ConfigWriteError("readback_mismatch")
    real = Path(os.path.realpath(path))
    try:
        mode = real.stat().st_mode & 0o7777
    except FileNotFoundError:
        mode = 0o644
    fd, tmp = tempfile.mkstemp(dir=str(real.parent), prefix=".relations_config.")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(new_text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(tmp, mode)
        os.replace(tmp, real)
    except BaseException:
        try:
            os.unlink(tmp)
        except FileNotFoundError:
            pass
        raise


def _set(root, block: str, key: str, value) -> None:
    path = config_path(root)
    try:
        old = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ConfigWriteError(f"missing:{path}") from None
    new = edit_nested(old, block, key, value)
    if new == old:
        return
    _guarded_write(path, old, new, block, key, value)


def set_enabled(root, value: bool) -> None:
    _set(root, "relations", "enabled", bool(value))


def seed_project_name(root, name: str) -> None:
    if not _PROJECT_RE.match(name or ""):
        raise ConfigWriteError(f"invalid_name:{name!r}")
    _set(root, "project", "name", name)


# --------------------------------------------------------- project-name rule

_HINT = ("set it explicitly in aitasks/metadata/project_config.yaml as "
         "'project:' / '  name: <name>' (lowercase letters, digits, '_' or '-'), "
         "or register this repository with 'ait projects add'")


def current_project_name(root):
    project = _read_cfg(root).get("project")
    name = project.get("name") if isinstance(project, dict) else None
    return name


def registry_bindings(root):
    """``(names, complete)``: registry names bound to ``root`` (canonical path)."""
    try:
        proc = subprocess.run([RESOLVE_SCRIPT, "bindings", str(root)], capture_output=True,
                              text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        return [], False
    names, complete = [], False
    for line in proc.stdout.splitlines():
        if line.startswith("BINDING:registry:"):
            names.append(line[len("BINDING:registry:"):].strip())
        elif line == "BINDINGS_COMPLETE":
            complete = True
    return sorted(set(names)), complete and proc.returncode == 0


def resolve_project_name(root, *, write=True) -> "tuple[str, str]":
    """``("kept"|"seeded", name)`` or raise ``ProjectUnresolved(why)``."""
    existing = current_project_name(root)
    if existing is not None:
        if isinstance(existing, str) and _PROJECT_RE.match(existing.strip()):
            return "kept", existing.strip()
        raise ProjectUnresolved(f"invalid project.name {existing!r} -- {_HINT}")
    names, complete = registry_bindings(root)
    if not complete:
        raise ProjectUnresolved(f"the project registry could not be read completely -- {_HINT}")
    if not names:
        raise ProjectUnresolved(f"project.name is not set and no registry entry points at this repository -- {_HINT}")
    if len(names) > 1:
        raise ProjectUnresolved(f"project.name is not set and the registry binds this repository to "
                                f"several names ({', '.join(names)}) -- {_HINT}")
    name = names[0]
    if not _PROJECT_RE.match(name):
        raise ProjectUnresolved(f"the registry name {name!r} is not a valid project name -- {_HINT}")
    if write:
        seed_project_name(root, name)
    return "seeded", name


def enable(root) -> list:
    """Resolve the project name, then set ``relations.enabled: true``."""
    how, name = resolve_project_name(root)
    set_enabled(root, True)
    return [f"PROJECT_NAME:{how}:{name}", "ENABLED_SET:true"]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) == 2 and argv[0] == "state":
        cfg = load(argv[1])
        print(f"RELATIONS_KEY:{cfg.enabled_key}")
        print(f"RELATIONS_CAP:{cfg.max_jobs_per_day}")
        return 0
    if len(argv) == 3 and argv[0] == "set-enabled" and argv[2] in ("true", "false"):
        root = argv[1]
        try:
            if argv[2] == "true":
                print("\n".join(enable(root)))
            else:
                set_enabled(root, False)
                print("ENABLED_SET:false")
        except ProjectUnresolved as exc:
            print(f"PROJECT_UNRESOLVED:{exc}")
            return 1
        except ConfigWriteError as exc:
            print(f"WRITE_FAILED:{exc}")
            return 1
        return 0
    sys.stderr.write("usage: relations_config.py state <root> | set-enabled <root> true|false\n")
    return 2


if __name__ == "__main__":
    sys.exit(main())
