"""Global shortcut-scope manifest + registration sweep.

The in-TUI `?` editor only needs the *running* TUI's scopes, so each App
registers its own bindings lazily when constructed (``ShortcutsMixin.__init__``).
The Settings → Shortcuts tab is different: it lists **every** TUI's bindings in a
process where only ``SettingsApp`` is ever instantiated. Without a deliberate
sweep, ``keybinding_registry._DEFAULTS`` would hold only ``settings`` + ``shared``.

``register_all_known_bindings()`` closes that gap: it imports each TUI module
listed in ``KNOWN_BINDING_SOURCES`` (by file path, so there are no ``sys.path``
name collisions) and registers every ``ShortcutsMixin`` class's bindings
**without instantiating** any App/Screen. Importing a module also triggers any
class-body / module-level registrations (e.g. ``brainstorm.dag`` and the
``shared`` TUI-switcher binding).

Maintenance: a *new dialog inside an existing TUI module* is picked up
automatically (the sweep introspects the module's classes). Only a **brand-new
TUI module file** must be added to ``KNOWN_BINDING_SOURCES`` below — and
``tests/test_shortcut_scopes.py`` fails until it is. See the
"Shortcut-scope registration" rule in ``aidocs/framework/tui_conventions.md``.

This lives in its own module (not ``keybinding_registry``) on purpose: the TUI
modules import ``keybinding_registry``, so the registry must not import them. The
sweep is invoked lazily at runtime, by which point every module is importable.
"""

from __future__ import annotations

import importlib.util
import inspect
import sys
from pathlib import Path

import keybinding_registry

# `.aitask-scripts/lib/` (this file lives here) and its parent.
_LIB_DIR = Path(__file__).resolve().parent
_SCRIPTS_DIR = _LIB_DIR.parent

# Module files that contribute shortcut scopes. Each entry is
# ``(module_name, path_relative_to_.aitask-scripts, scopes)`` where ``scopes``
# lists every scope that module contributes — used by ``register_scope_bindings``
# to load only the modules relevant to a given TUI. `settings` is omitted —
# `SettingsApp` self-registers as the running app. Importing a module covers any
# class-body / module-level registration; the sweep additionally introspects the
# module's own `ShortcutsMixin` classes (see `register_all_known_bindings`).
KNOWN_BINDING_SOURCES: list[tuple[str, str, tuple[str, ...]]] = [
    ("aitask_board", "board/aitask_board.py", ("board", "board.detail")),
    ("brainstorm_app", "brainstorm/brainstorm_app.py", ("brainstorm", "brainstorm.compare_select")),
    ("brainstorm_dag_display", "brainstorm/brainstorm_dag_display.py", ("brainstorm.dag",)),  # class-body
    ("codebrowser_app", "codebrowser/codebrowser_app.py", ("codebrowser", "codebrowser.copypath")),
    ("applink_app", "applink/applink_app.py", ("applink", "applink.pairing", "applink.status")),
    ("monitor_app", "monitor/monitor_app.py", ("monitor",)),
    ("minimonitor_app", "monitor/minimonitor_app.py", ("minimonitor",)),
    ("syncer_app", "syncer/syncer_app.py", ("syncer",)),
    ("diffviewer_app", "diffviewer/diffviewer_app.py", ("diffviewer",)),
    ("stats_app", "stats/stats_app.py", ("stats",)),
    # Shared, cross-TUI dialogs (reused by several Apps) — their scopes live
    # under "shared.*" so every TUI's `?` editor surfaces them.
    ("agent_command_screen", "lib/agent_command_screen.py", ("shared.agent_cmd",)),
    ("stale_entry_modal", "lib/stale_entry_modal.py", ("shared.stale_entry",)),
    ("tui_switcher", "lib/tui_switcher.py", ("shared", "shared.tui_switcher")),  # module- + class-body register
]


def _ensure_import_paths() -> None:
    """Put the dirs each TUI module imports its siblings from on ``sys.path``.

    Always includes lib + the `.aitask-scripts` root (the latter for
    namespace-package imports like ``brainstorm.brainstorm_dag``). Every
    manifest module's own directory is added too, so a module importing a
    sibling by bare name (e.g. ``aitask_board`` → ``task_yaml`` in ``board/``)
    resolves. The TUI dirs have no colliding module basenames, so this is safe.
    """
    dirs = {_LIB_DIR, _SCRIPTS_DIR}
    for _module_name, rel_path, _scopes in KNOWN_BINDING_SOURCES:
        dirs.add((_SCRIPTS_DIR / rel_path).parent)
    for d in dirs:
        s = str(d)
        if s not in sys.path:
            sys.path.insert(0, s)


def _load_and_register(module_name: str, rel_path: str, failed: list[str]) -> None:
    """Import one manifest module by path and register its bindings.

    Loads the module via ``spec_from_file_location`` (so there are no
    ``sys.path`` name collisions) and registers the bindings of every
    ``ShortcutsMixin`` class defined in it — **without instantiating** any
    App/Screen. Class-body / module-level registrations (e.g. ``brainstorm.dag``,
    the ``shared`` TUI-switcher binding) fire during the import itself. Fail-soft:
    a module that cannot be imported is appended to ``failed`` and logged, never
    raising. ``register_app_bindings`` is idempotent, so repeat calls are safe.
    """
    path = _SCRIPTS_DIR / rel_path
    try:
        spec = importlib.util.spec_from_file_location(module_name, path)
        if spec is None or spec.loader is None:
            raise ImportError(f"no loader for {path}")
        module = importlib.util.module_from_spec(spec)
        # Register in sys.modules BEFORE exec_module. Under Python 3.14, a
        # `@dataclass` whose fields use string annotations (these modules carry
        # `from __future__ import annotations`) is processed by
        # dataclasses._is_type, which resolves the owning module via
        # `sys.modules.get(cls.__module__).__dict__`. Without this entry the
        # lookup returns None and the import dies with
        # "AttributeError: 'NoneType' object has no attribute '__dict__'".
        # Manifest names are unique, so there is no collision; popped on failure
        # so a half-initialized module is never left registered.
        sys.modules[module_name] = module
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully
        sys.modules.pop(module_name, None)
        failed.append(module_name)
        sys.stderr.write(
            f"shortcut_scopes: could not load {module_name} "
            f"({path}): {type(exc).__name__}: {exc}\n"
        )
        return

    # Register the bindings of every ShortcutsMixin class DEFINED in this
    # module (filter on __module__ so imported base classes are ignored).
    # Classes that register at class body (no _shortcuts_scope attr, e.g.
    # brainstorm.dag) are already handled by the exec_module above and are
    # skipped here by the truthy-_shortcuts_scope guard.
    for _name, cls in inspect.getmembers(module, inspect.isclass):
        if getattr(cls, "__module__", None) != module_name:
            continue
        scope = getattr(cls, "_shortcuts_scope", "")
        bindings = getattr(cls, "BINDINGS", None)
        if scope and bindings:
            keybinding_registry.register_app_bindings(scope, list(bindings))


def register_all_known_bindings() -> list[str]:
    """Import every known TUI module and register its bindings (no instantiation).

    Idempotent (``register_app_bindings`` overwrites the same ``_DEFAULTS``
    entries) and fail-soft: a module that cannot be imported is logged to stderr
    and skipped, never breaking the caller (e.g. the Settings tab).

    Returns the list of module names that failed to import (empty on full
    success) — useful for tests/diagnostics.
    """
    _ensure_import_paths()
    failed: list[str] = []
    for module_name, rel_path, _scopes in KNOWN_BINDING_SOURCES:
        _load_and_register(module_name, rel_path, failed)
    return failed


def _scope_relevant(scopes: tuple[str, ...], prefix: str) -> bool:
    """True if any of ``scopes`` is ``prefix``, a ``prefix.*`` sub-scope, or a
    global ``shared`` / ``shared.*`` scope.

    Mirrors the filter in ``keybinding_registry.iter_scope_bindings`` so the
    editor's filtered sweep loads exactly the modules whose scopes the editor
    will display.
    """
    for s in scopes:
        if (
            s == prefix
            or s.startswith(prefix + ".")
            or s == "shared"
            or s.startswith("shared.")
        ):
            return True
    return False


def register_scope_bindings(scope: str) -> list[str]:
    """Register only the binding sources relevant to ``scope`` (no instantiation).

    The filtered counterpart to :func:`register_all_known_bindings`, for the
    in-TUI ``?`` shortcut editor: it needs the active TUI's own scope, its modal
    sub-scopes (``scope.*``), and the global ``shared`` / ``shared.*`` scopes —
    but NOT every other TUI. Loading only the relevant manifest modules keeps
    pressing ``?`` in one TUI from importing every other TUI.

    Idempotent and fail-soft (see :func:`_load_and_register`). Returns the list
    of module names that failed to import.
    """
    _ensure_import_paths()
    failed: list[str] = []
    for module_name, rel_path, scopes in KNOWN_BINDING_SOURCES:
        if _scope_relevant(scopes, scope):
            _load_and_register(module_name, rel_path, failed)
    return failed
