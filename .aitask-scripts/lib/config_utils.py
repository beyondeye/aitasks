"""config_utils - Shared config loading/saving helpers for aitasks Python tools.

Provides JSON config file management with a per-project / per-user override
pattern, plus YAML helpers for project-scoped settings files. Project configs
are git-tracked; user configs use .local.json suffix and are gitignored.

Usage:
    from config_utils import load_layered_config, save_project_config

    config = load_layered_config(
        "aitasks/metadata/board_config.json",
        defaults={"auto_refresh_minutes": 0},
    )
"""
from __future__ import annotations

import copy
import json
import os
import stat
import tempfile
from datetime import datetime, timezone
from os import replace as _os_replace
from pathlib import Path
from typing import Any

import yaml

# Read the umask once, at import. Probing it requires os.umask(0) followed by a
# restore, which is process-global and racy — settings_app is a Textual app with
# worker threads, so doing it per write could hand another thread a mode-0
# window. New files get 0o666 & ~umask, matching what open(path, "w") produced
# before writes became atomic.
_UMASK = os.umask(0)
os.umask(_UMASK)

class ConfigMergeError(ValueError):
    """A merge-mode import cannot proceed without destroying data.

    Raised for a structural mismatch between the incoming payload and the
    destination — a dict where the other side holds a scalar/list, or a
    destination that is not a readable JSON object. A ValueError subclass so it
    satisfies the documented exception type, but distinguishable from
    json.JSONDecodeError (which is *also* a ValueError, and would otherwise make
    "malformed destination" and "type conflict" indistinguishable in a test).
    """


class ConfigImportPartialError(RuntimeError):
    """Some files were committed before an import failed.

    Callers MUST reload their in-memory config from disk on this error rather
    than assuming nothing changed. ``written`` names the files that landed.
    """

    def __init__(self, written: list[str], cause: BaseException) -> None:
        super().__init__(
            f"import partially applied after writing {written}: {cause}"
        )
        self.written = written
        self.cause = cause


EXPORT_EXTENSION = ".aitcfg.json"

DEFAULT_EXPORT_PATTERNS = [
    "*_config.json",
    "*_config.local.json",
    "models_*.json",
    "models_*.local.json",
]


def task_dir() -> Path:
    """Base task directory, honoring the ``TASK_DIR`` env override.

    Defaults to ``aitasks`` (relative to cwd) when ``TASK_DIR`` is unset, which
    matches the framework default and the path TUIs use after chdir-ing to the
    repo root. Tests and non-default layouts set ``TASK_DIR`` so module-load
    constants resolve against the right tree. Mirrors
    ``userconfig_persist._userconfig_path()``.
    """
    return Path(os.environ.get("TASK_DIR", "aitasks"))


def metadata_dir() -> Path:
    """The ``<task_dir>/metadata`` directory, honoring ``TASK_DIR``."""
    return task_dir() / "metadata"


def local_path_for(project_path: str | Path) -> Path:
    """Derive the .local.json path from a project config path.

    board_config.json -> board_config.local.json
    models_claudecode.json -> models_claudecode.local.json
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


def _target_mode(path: Path) -> int:
    """Permission bits a write to ``path`` should produce.

    Preserves an existing file's mode; falls back to the umask default for a new
    file. Without this, ``tempfile.mkstemp``'s 0600 would silently downgrade
    every config it rewrites (models_*.json is 0644 in a normal checkout).
    """
    try:
        return stat.S_IMODE(os.stat(path).st_mode)
    except OSError:
        return 0o666 & ~_UMASK


def _prepare_atomic(path: Path, render) -> str:
    """Write render(fh)'s output to a temp file beside ``path``; return its path.

    Pairs with :func:`_commit_atomic`. Splitting prepare from commit lets a
    caller validate and stage several files before any of them becomes visible.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = _target_mode(path)
    fd, tmp = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        os.fchmod(fd, mode)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            render(fh)
    except BaseException:
        _discard_temp(tmp)
        raise
    return tmp


def _commit_atomic(tmp: str, path: Path) -> None:
    """Move a prepared temp file into place. Never leaves the temp behind."""
    try:
        _os_replace(tmp, path)
    except BaseException:
        _discard_temp(tmp)
        raise


def _discard_temp(tmp: str) -> None:
    """Best-effort removal of a staged temp file."""
    try:
        os.unlink(tmp)
    except OSError:
        pass


def _atomic_write(path: Path, render) -> None:
    """Write text produced by ``render(fh)`` to ``path`` atomically.

    Temp file in the same directory + ``os.replace``, so a concurrent reader
    never observes a partial file and a failed write leaves the original intact.
    This is atomic *visibility*, not crash durability — there is no fsync, which
    matches gate_ledger and attachment_meta.

    ``path`` is resolved with ``realpath`` first: ``open(path, "w")`` follows a
    symlink, but ``os.replace`` would replace the link itself, orphaning the real
    backing file while reads kept succeeding.
    """
    resolved = Path(os.path.realpath(path))
    _commit_atomic(_prepare_atomic(resolved, render), resolved)


def _render_json(data: dict):
    """Renderer for the project's JSON config format (indent 2, trailing NL)."""

    def render(fh) -> None:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")

    return render


def _save_json(path: Path, data: dict) -> None:
    """Write a dict as formatted JSON, atomically."""
    _atomic_write(Path(path), _render_json(data))


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


MODEL_FILES = {
    "claudecode": metadata_dir() / "models_claudecode.json",
    "codex": metadata_dir() / "models_codex.json",
    "opencode": metadata_dir() / "models_opencode.json",
}


def load_all_models(
    project_root: str | Path | None = None,
    *,
    metadata_path: str | Path | None = None,
) -> dict[str, dict]:
    """Load all models_*.json files into {provider: data}.

    Three ways to say where the catalog lives, in precedence order:

    - ``metadata_path`` — used verbatim. No ambient ``TASK_DIR`` is consulted, so
      the answer cannot drift from the caller's other paths. Cross-repo callers
      MUST use this form: they need the catalog to come from the same metadata
      directory as the config layers they are reading.
    - ``project_root`` — composed as ``root / <task_dir> / metadata``. Kept for
      same-repo callers, where honoring the user's ``TASK_DIR`` is correct. An
      *absolute* ``TASK_DIR`` would make ``root / rel`` silently discard the root
      (pathlib drops the left operand), so it falls back to the framework
      default.
    - neither — today's cwd-relative module behavior.

    Providers whose file is missing or empty are omitted.
    """
    if metadata_path is not None:
        meta = Path(metadata_path)
    elif project_root is not None:
        rel = task_dir()
        if rel.is_absolute():
            rel = Path("aitasks")
        meta = Path(project_root) / rel / "metadata"
    else:
        meta = metadata_dir()

    result: dict[str, dict] = {}
    for provider in MODEL_FILES:
        data = _load_json(meta / f"models_{provider}.json")
        if data:
            result[provider] = data
    return result


def load_yaml_config(path: str | Path, defaults: dict | None = None) -> dict:
    """Load a project-scoped YAML config file.

    Returns defaults (or {}) when the file is missing or empty.
    Raises yaml.YAMLError when an existing file contains invalid YAML.
    """
    result = copy.deepcopy(defaults) if defaults else {}
    yaml_path = Path(path)
    if not yaml_path.is_file():
        return result
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if isinstance(data, dict):
        return deep_merge(result, data)
    return result


def save_yaml_config(path: str | Path, data: dict) -> None:
    """Write a project-level YAML config with stable key ordering, atomically.

    Atomicity matters most here: userconfig.yaml carries ``email`` and
    ``last_used_labels``, which exist nowhere else, whereas the JSON configs are
    recoverable from an export bundle.
    """
    _atomic_write(Path(path), _render_yaml(data))


def _render_yaml(data: dict):
    """Renderer for the project's YAML config format."""

    def render(fh) -> None:
        yaml.safe_dump(
            data, fh, default_flow_style=False, sort_keys=False, allow_unicode=True
        )

    return render


def resolve_config_path(
    config_key: str,
    default_rel: str | None = None,
    root: str | Path | None = None,
    check_readable: bool = True,
) -> str | None:
    """Resolve a settings-defined file path with a seeded-default fallback.

    This is the canonical seam for "a `project_config.yaml` value that names a
    file on disk, with a fallback to the guide/template `ait setup` installed"
    (e.g. ``learn_skill_authoring_guide`` for /aitask-learn-skill, or the nested
    ``doc_update.guide`` read by the docs_updated gate). Reading via PyYAML — the
    same parser the settings TUI writes with — means quoted values, inline
    ``# comments``, whitespace, and dotted/nested keys are all handled uniformly,
    unlike a hand-rolled ``grep`` in a skill.

    Args:
        config_key: Dotted key into ``aitasks/metadata/project_config.yaml``
            (e.g. ``"doc_update.guide"`` or a flat ``"learn_skill_authoring_guide"``).
        default_rel: Repo-root-relative fallback path, used when the key is unset
            or its file is not readable.
        root: Directory the config and returned paths are resolved against
            (default: current working directory).
        check_readable: When True (default), a candidate is only returned if it
            names an existing file; when False, the configured/default value is
            returned as-is without a filesystem check.

    Returns:
        A repo-root-relative path string (the configured value, else
        ``default_rel``), or ``None`` when neither resolves to a usable path.
    """
    base = Path(root) if root is not None else Path.cwd()
    cfg = load_yaml_config(base / "aitasks" / "metadata" / "project_config.yaml")

    val: Any = cfg
    for part in config_key.split("."):
        val = val.get(part) if isinstance(val, dict) else None
    configured = val.strip() if isinstance(val, str) and val.strip() else None

    for candidate in (configured, default_rel):
        if candidate and (not check_readable or (base / candidate).is_file()):
            return candidate
    return None


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
    include_shortcuts: bool = False,
) -> dict:
    """Bundle all config JSON files from metadata_dir into a single export file.

    Args:
        output_path: Path to write the export JSON bundle.
        metadata_dir: Path to aitasks/metadata/ directory.
        patterns: Glob patterns to match config files. Defaults to
                  *_config.json, *_config.local.json, models_*.json,
                  models_*.local.json.
        include_shortcuts: When True, extract the ``shortcuts:`` subtree from
                  ``userconfig.yaml`` (and ONLY that subtree — never the whole
                  per-user file, so ``email``/``last_used_labels`` never leak)
                  and add it as a top-level ``shortcuts`` member of the bundle.

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

    if include_shortcuts:
        userconfig = load_yaml_config(meta_path / "userconfig.yaml")
        shortcuts = userconfig.get("shortcuts")
        if isinstance(shortcuts, dict) and shortcuts:
            bundle["shortcuts"] = shortcuts
            bundle["_export_meta"]["file_count"] += 1

    _atomic_write(Path(output_path), _render_json(bundle))

    return bundle


def validate_export_bundle(bundle: dict) -> list[str]:
    """Validate an export bundle structure and return warnings.

    Args:
        bundle: Parsed JSON bundle dict.

    Returns:
        List of warning/error strings. Empty list means valid.
    """
    from fnmatch import fnmatch

    warnings: list[str] = []

    if not isinstance(bundle, dict):
        warnings.append("Bundle is not a JSON object")
        return warnings

    meta = bundle.get("_export_meta")
    if meta is None:
        warnings.append("Missing '_export_meta' field")
    elif not isinstance(meta, dict):
        warnings.append("'_export_meta' is not a dict")
    else:
        version = meta.get("version")
        if version is None:
            warnings.append("Missing version in '_export_meta'")
        elif version != 1:
            warnings.append(f"Unsupported bundle version: {version}")

    files = bundle.get("files")
    if files is None:
        warnings.append("Missing 'files' field")
        return warnings
    if not isinstance(files, dict):
        warnings.append("'files' is not a dict")
        return warnings

    for name, data in files.items():
        if isinstance(data, dict) and "_error" in data:
            continue
        if not isinstance(data, dict):
            warnings.append(f"File '{name}' has non-dict value ({type(data).__name__})")
            continue
        if not any(fnmatch(name, pat) for pat in DEFAULT_EXPORT_PATTERNS):
            warnings.append(f"Unexpected filename '{name}' (not matching known patterns)")

    return warnings


_ABSENT = object()
"""Sentinel for "no destination file". Distinct from a file holding ``null``,
which is a broken destination rather than an empty one — conflating the two
would let a merge silently overwrite it."""


def _read_destination(target: Path) -> Any:
    """Read a merge destination strictly. Missing is fine; broken is not.

    ``_load_json`` is too lossy here: it reports a directory as ``{}`` (i.e.
    indistinguishable from absent) and returns ``None`` for a file holding
    ``null``. Merge mode must fail closed on anything it cannot merge into,
    because the alternative is merging into ``{}`` and clobbering the file.
    """
    if not target.exists():
        return _ABSENT
    if not target.is_file():
        raise ConfigMergeError(
            f"destination {target.name!r} exists but is not a regular file"
        )
    with open(target, "r", encoding="utf-8") as f:
        data = json.load(f)  # JSONDecodeError propagates: malformed != conflict
    if data is None:
        raise ConfigMergeError(
            f"destination {target.name!r} holds null, which is not a mergeable value"
        )
    return data


def _describe_path(path: tuple[str, ...]) -> str:
    """Render a key path for an error message.

    Keys legitimately contain dots (``models_claudecode.json``), so segments are
    quoted and joined rather than dot-concatenated into something ambiguous.
    """
    return " -> ".join(repr(seg) for seg in path)


def _check_type_conflicts(existing: Any, incoming: Any, path: tuple[str, ...]) -> None:
    """Raise if merging ``incoming`` into ``existing`` would destroy a subtree.

    ``deep_merge`` recurses only when both sides are dicts and otherwise lets the
    override win, so a dict-vs-scalar mismatch silently drops everything under
    that key. Only *common* keys can conflict; a key present on one side alone
    merges cleanly.
    """
    for key in incoming:
        if key not in existing:
            continue
        a, b = existing[key], incoming[key]
        here = path + (key,)
        if isinstance(a, dict) and isinstance(b, dict):
            _check_type_conflicts(a, b, here)
        elif isinstance(a, dict) != isinstance(b, dict):
            raise ConfigMergeError(
                f"type conflict at {_describe_path(here)}: destination holds "
                f"{type(a).__name__}, payload holds {type(b).__name__}"
            )


def _merge_file(name: str, existing: Any, incoming: Any) -> Any:
    """Resolve one whole file's merge, or raise ConfigMergeError.

    A bundle file value is not always a dict — ``models_*.json`` round-trips as a
    bare list — so the whole-file shapes are decided before the nested walk.
    """
    if existing is _ABSENT:
        return incoming  # fresh file: write verbatim, whatever the shape
    if isinstance(existing, dict) and isinstance(incoming, dict):
        _check_type_conflicts(existing, incoming, ())
        return deep_merge(existing, incoming)
    if isinstance(existing, dict) != isinstance(incoming, dict):
        raise ConfigMergeError(
            f"type conflict in {name!r}: destination holds "
            f"{type(existing).__name__}, payload holds {type(incoming).__name__}"
        )
    return incoming  # same non-dict kind: replace, per deep_merge's list rule


def import_all_configs(
    input_path: str | Path | None = None,
    metadata_dir: str | Path | None = None,
    overwrite: bool = False,
    selected_files: list[str] | None = None,
    *,
    bundle: dict | None = None,
    merge: bool = False,
) -> list[str]:
    """Restore config files from an export bundle.

    Args:
        input_path: Path to the export JSON bundle. Mutually exclusive with
                    ``bundle``; exactly one is required.
        metadata_dir: Path to the destination aitasks/metadata/ directory.
                      Required (defaulted to None only because ``input_path``
                      now needs a default and both stay positional).
        overwrite: If True, overwrite existing files. If False, skip them.
        selected_files: If provided, only import files in this list.
                        If None, import all files in the bundle.
        bundle: An in-memory bundle, same shape as the file form. Filtered by
                ``selected_files`` and guarded against path traversal exactly
                like the file form.
        merge: Deep-merge each payload into the existing destination instead of
               replacing the file, so keys the payload does not mention survive.
               Requires ``overwrite=True``.

    Returns:
        List of filenames that were written. Includes the literal
        ``"shortcuts"`` when a shortcuts subtree was merged into
        ``userconfig.yaml``. In merge mode a file appears when it was part of
        the write plan, including a merge that changed nothing.

    Raises:
        ValueError: For invalid argument combinations, an unrecognized bundle
                    format, or a filename containing path separators.
        FileNotFoundError: If input_path does not exist.
        json.JSONDecodeError: If the bundle — or, in merge mode, a destination —
                    is invalid JSON.
        ConfigMergeError: If a merge would destroy a subtree, or a destination
                    is not a readable JSON object.
        ConfigImportPartialError: If a failure occurred after some files were
                    already committed. Reload from disk; do not assume nothing
                    changed.
    """
    # Argument validation runs before any filesystem access, so a rejected call
    # cannot leave a freshly created metadata directory behind.
    if (input_path is None) == (bundle is None):
        raise ValueError(
            "Exactly one of 'input_path' or 'bundle' is required"
        )
    if merge and not overwrite:
        raise ValueError("merge=True requires overwrite=True")
    if metadata_dir is None:
        raise ValueError("'metadata_dir' is required")

    if bundle is None:
        with open(Path(input_path), "r", encoding="utf-8") as f:
            bundle = json.load(f)

    if "files" not in bundle:
        raise ValueError("Invalid export bundle: missing 'files' key")

    meta_path = Path(metadata_dir)
    meta_path.mkdir(parents=True, exist_ok=True)

    # Stage 1 — plan. Read, conflict-check and merge everything before anything
    # becomes visible, so one bad destination writes nothing at all.
    plan: list[tuple[str, Path, Any]] = []
    for name, data in bundle["files"].items():
        # Security: prevent path traversal. Deliberately ahead of the selection
        # filter — an unselected traversal name still raises, as it always has.
        if os.sep in name or "/" in name or "\\" in name:
            raise ValueError(f"Invalid filename in bundle: {name!r}")

        # Skip files not in selection (when selection is provided)
        if selected_files is not None and name not in selected_files:
            continue

        # Skip error entries
        if isinstance(data, dict) and "_error" in data:
            continue

        target = meta_path / name
        if target.exists() and not overwrite:
            continue

        # Destination reads happen only after the skips above: a file the caller
        # excluded must never be able to fail the import.
        merged = _merge_file(name, _read_destination(target), data) if merge else data
        plan.append((name, target, _render_json(merged)))

    # Shortcuts are a distinct top-level bundle member (not a file under
    # `files`): deep-merge the subtree into userconfig.yaml, preserving every
    # other local top-level key (email/last_used_labels/...). Merged when
    # present and either no selection was given or "shortcuts" was selected.
    # Planned here (so a broken userconfig.yaml aborts before anything is
    # written) and committed last. The shallow scope-level update is the
    # long-standing semantic and is deliberately left as-is.
    shortcuts = bundle.get("shortcuts")
    if (
        isinstance(shortcuts, dict)
        and shortcuts
        and (selected_files is None or "shortcuts" in selected_files)
    ):
        userconfig_path = meta_path / "userconfig.yaml"
        userconfig = load_yaml_config(userconfig_path)
        existing = userconfig.get("shortcuts")
        if not isinstance(existing, dict):
            existing = {}
        for scope, actions in shortcuts.items():
            if not isinstance(actions, dict):
                continue
            scope_map = existing.get(scope)
            if not isinstance(scope_map, dict):
                scope_map = {}
            scope_map.update(actions)
            existing[scope] = scope_map
        userconfig["shortcuts"] = existing
        plan.append(("shortcuts", userconfig_path, _render_yaml(userconfig)))

    written: list[str] = []
    if plan:
        # Stage 2 — prepare every temp file; nothing is visible yet.
        staged: list[tuple[str, str, Path]] = []
        try:
            for name, target, render in plan:
                resolved = Path(os.path.realpath(target))
                staged.append((name, _prepare_atomic(resolved, render), resolved))
        except BaseException:
            for _, tmp, _ in staged:
                _discard_temp(tmp)
            raise

        # Stage 3 — commit. The rename loop is the only window in which a
        # partial application is possible; it cannot be closed on POSIX, so it
        # is reported instead of assumed away.
        for idx, (name, tmp, resolved) in enumerate(staged):
            try:
                _commit_atomic(tmp, resolved)
            except BaseException as exc:
                for _, pending, _ in staged[idx + 1:]:
                    _discard_temp(pending)
                if written:
                    raise ConfigImportPartialError(written, exc) from exc
                raise
            written.append(name)

    return written
