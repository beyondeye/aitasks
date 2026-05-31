"""Registry of TUI key bindings and resolver for per-user overrides.

Records every TUI App's default `(scope, action_id) -> (key, label)` mapping
at registration time, and substitutes user-customised keys read from
`aitasks/metadata/userconfig.yaml` (key: `shortcuts`).

No TUI is wired up to this module yet — it is the library foundation for the
t848 "customisable shortcuts" series. Consumers will call
`register_app_bindings(scope, BINDINGS)` from each `App`'s class body or
`__init__`, then use `resolve_key(scope, action_id, default)` from any
label-rendering code that needs the active key outside of a `Binding`.
"""

from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

# (scope, action_id) -> (default_key, label)
_DEFAULTS: dict[tuple[str, str], tuple[str, str]] = {}

# scope -> {action_id: key}; None = not loaded yet
_OVERRIDES_CACHE: dict[str, dict[str, str]] | None = None

SHARED_ACTION_IDS: frozenset[str] = frozenset(
    {"quit", "tui_switcher", "refresh", "open_shortcuts_editor"}
)


def _userconfig_path() -> Path:
    """Resolve userconfig.yaml via the canonical persistence layer.

    Delegates to ``userconfig_persist._userconfig_path`` so the ``TASK_DIR``
    env override is honored identically to the single writer of this file
    (tests / non-default layouts set ``TASK_DIR``). Imported locally to keep
    yaml off this module's import path until a read actually happens — see the
    deferred ``import yaml`` in ``load_user_overrides``.
    """
    from userconfig_persist import _userconfig_path as _canonical_path

    return _canonical_path()


def load_user_overrides() -> dict[str, dict[str, str]]:
    """Return the cached `shortcuts:` section of userconfig.yaml.

    Returns an empty dict if the file or the `shortcuts` key is missing.
    """
    global _OVERRIDES_CACHE
    if _OVERRIDES_CACHE is not None:
        return _OVERRIDES_CACHE

    path = _userconfig_path()
    if not path.is_file():
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE

    import yaml  # local import: tests may run before yaml is on sys.path

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as exc:
        # A malformed (gitignored) userconfig.yaml must not crash every
        # board/TUI at import time; degrade to "no overrides" like the
        # missing-file case above.
        sys.stderr.write(
            f"keybinding_registry: ignoring malformed {path}: {exc}\n"
        )
        _OVERRIDES_CACHE = {}
        return _OVERRIDES_CACHE
    shortcuts = data.get("shortcuts") or {}
    if not isinstance(shortcuts, dict):
        shortcuts = {}
    # Normalise: drop non-dict scopes / non-str keys defensively.
    normalised: dict[str, dict[str, str]] = {}
    for scope, mapping in shortcuts.items():
        if isinstance(mapping, dict):
            normalised[str(scope)] = {
                str(aid): str(key) for aid, key in mapping.items()
            }
    _OVERRIDES_CACHE = normalised
    return _OVERRIDES_CACHE


def refresh(scope: str | None = None) -> None:
    """Drop the cached overrides so the next read re-loads from disk.

    `scope` is accepted for API symmetry with future granular invalidation
    but the cache is a single dict, so the whole map is dropped either way.
    """
    global _OVERRIDES_CACHE
    _OVERRIDES_CACHE = None


def refresh_all() -> None:
    refresh(None)


def register_app_bindings(scope: str, bindings: list[Any]) -> list[Any]:
    """Record defaults for `bindings` under `scope`, return overrides-applied list.

    Each entry is a Textual `Binding` (frozen dataclass). For every binding,
    we record `(scope, binding.action) -> (binding.key, binding.description)`
    in `_DEFAULTS`. If the user has overridden the key for that action in
    that scope, we return a new `Binding` with the override key substituted;
    otherwise the original `Binding` is returned unchanged.
    """
    all_overrides = load_user_overrides()
    overrides = all_overrides.get(scope, {})
    shared_overrides = all_overrides.get("shared", {})
    result: list[Any] = []
    for b in bindings:
        action = getattr(b, "action", None)
        default_key = getattr(b, "key", None)
        label = getattr(b, "description", "") or ""
        if action and default_key is not None:
            action_s = str(action)
            # A binding whose action is already registered under "shared"
            # (e.g. the `j` TUI switcher, spliced into every App's BINDINGS via
            # TuiSwitcherMixin.SWITCHER_BINDINGS) is a cross-TUI shared binding.
            # Resolve its override from the shared scope and do NOT shadow it
            # with a per-App-scope copy, so the in-TUI shortcut editor lists it
            # once (under "shared") and an edit there applies in every TUI.
            if scope != "shared" and ("shared", action_s) in _DEFAULTS:
                shared_default = _DEFAULTS[("shared", action_s)][0]
                override_key = shared_overrides.get(action_s)
                if override_key is not None and override_key != shared_default:
                    result.append(dataclasses.replace(b, key=override_key))
                    continue
                result.append(b)
                continue
            _DEFAULTS[(scope, action_s)] = (str(default_key), str(label))
            override_key = overrides.get(action_s)
            if override_key is not None and override_key != default_key:
                result.append(dataclasses.replace(b, key=override_key))
                continue
        result.append(b)
    return result


def resolve_key(
    scope: str, action_id: str, default_key: str | None = None
) -> str | None:
    """Look up the effective key for `(scope, action_id)`.

    Priority: user override > recorded default (from prior register call)
    > caller-supplied `default_key` fallback > None.
    """
    override = load_user_overrides().get(scope, {}).get(action_id)
    if override is not None:
        return override
    recorded = _DEFAULTS.get((scope, action_id))
    if recorded is not None:
        return recorded[0]
    return default_key


def coherence_lint(scopes_to_check: list[str] | None = None) -> list[str]:
    """Return warnings for shared actions bound to different keys across scopes.

    For each action in `SHARED_ACTION_IDS`, gather the effective key in each
    registered scope. If more than one distinct key is in use, emit one
    warning naming the action and listing the conflicting keys.

    `scopes_to_check` narrows the scan to a subset of scopes; default is
    every scope present in `_DEFAULTS`.
    """
    all_scopes: set[str] = {scope for (scope, _) in _DEFAULTS}
    if scopes_to_check is not None:
        all_scopes &= set(scopes_to_check)

    warnings: list[str] = []
    for action in sorted(SHARED_ACTION_IDS):
        per_scope_key: dict[str, str] = {}
        for scope in all_scopes:
            if (scope, action) not in _DEFAULTS:
                continue
            key = resolve_key(scope, action)
            if key is not None:
                per_scope_key[scope] = key
        distinct_keys = set(per_scope_key.values())
        if len(distinct_keys) > 1:
            parts = ", ".join(
                f"`{key}` in {scope}"
                for scope, key in sorted(per_scope_key.items())
            )
            warnings.append(f"`{action}` is bound to {parts}")
    return warnings


def iter_scope_bindings(prefix: str) -> list[tuple[str, str, str, str]]:
    """Return ``(scope, action_id, default_key, label)`` rows for the editor.

    Includes every recorded binding whose scope equals ``prefix`` or starts
    with ``prefix + "."`` (a TUI's own scope plus its modal sub-scopes), plus
    the global ``shared`` / ``shared.*`` scopes — those bindings (e.g. the
    ``j`` TUI switcher) are active in every TUI, so the in-TUI shortcut editor
    surfaces them too. Sorted by ``(scope, action_id)`` for a stable order.
    """
    out: list[tuple[str, str, str, str]] = []
    for (scope, action_id), (default_key, label) in _DEFAULTS.items():
        if (
            scope == prefix
            or scope.startswith(prefix + ".")
            or scope == "shared"
            or scope.startswith("shared.")
        ):
            out.append((scope, action_id, default_key, label))
    return sorted(out, key=lambda row: (row[0], row[1]))


def iter_all_bindings() -> list[tuple[str, str, str, str]]:
    """Return every recorded ``(scope, action_id, default_key, label)`` row.

    Unlike :func:`iter_scope_bindings`, this is not prefix-filtered — it
    surfaces the complete cross-TUI binding set for the Settings → Shortcuts
    tab. Sorted by ``(scope, action_id)`` for a stable table order.
    """
    return sorted(
        (
            (scope, action_id, default_key, label)
            for (scope, action_id), (default_key, label) in _DEFAULTS.items()
        ),
        key=lambda row: (row[0], row[1]),
    )


def _reset_for_tests() -> None:
    """Clear all module state. Test-only — do not call from production code."""
    global _OVERRIDES_CACHE
    _DEFAULTS.clear()
    _OVERRIDES_CACHE = None
