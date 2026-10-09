"""Fail fast when a stale or foreign module shadows a shared ``lib/`` module.

Several TUIs put their own directory AHEAD of ``lib/`` on ``sys.path`` so their
sibling modules import by bare name (``board/`` for ``ait board`` / ``ait
trails``, ``syncer/``, the ``.aitask-scripts`` root for settings). Any file in
such a directory named like a ``lib/`` module then wins the import. That is
exactly how t1217's move of ``board/task_yaml.py`` to ``lib/task_yaml.py``
broke upgraded projects: the upgrade left the old ``board/`` copy behind, and
every fresh ``ait board`` died with an opaque ``ImportError`` for a name the
stale copy lacks.

``ait upgrade`` / ``ait setup`` now prune such leftovers
(``retired_scripts_manifest.txt``), but a locally modified leftover is kept by
design, and a user file can take the same name. So each own-dir-first TUI calls
:func:`assert_lib_not_shadowed` right after its ``sys.path`` setup: it names
the shadowing file and the fix, and exits — instead of letting a later import
fail somewhere unrelated.

Pure stdlib, no side effects beyond the diagnostic and the exit.
"""

from __future__ import annotations

import os
import sys

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))


def _lib_module_names(lib_dir: str) -> set[str]:
    names = set()
    try:
        entries = os.listdir(lib_dir)
    except OSError:
        return names
    for entry in entries:
        if entry.endswith(".py") and entry != "__init__.py":
            names.add(entry[:-3])
        elif os.path.isfile(os.path.join(lib_dir, entry, "__init__.py")):
            names.add(entry)
    return names


def _same_dir(a: str, b: str) -> bool:
    try:
        return os.path.samefile(a, b)
    except OSError:
        return os.path.realpath(a) == os.path.realpath(b)


def _is_framework_lib(directory: str) -> bool:
    # Another checkout's lib/ (a test process can hold the real tree and a
    # fixture copy at once). Its modules are the same framework modules, not
    # shadows — skip it rather than flag every name it shares.
    return os.path.isfile(os.path.join(directory, "module_shadow_guard.py"))


def find_lib_shadows(lib_dir: str = _LIB_DIR) -> list[tuple[str, str]]:
    """Return ``(shadowing_path, module_name)`` pairs, empty when clean.

    Two checks against the module names ``lib_dir`` provides:

    1. every ``sys.path`` entry that precedes the first ``lib_dir`` entry
       (``''`` is the current directory), skipping any other framework
       ``lib/``, for ``<name>.py`` or ``<name>/__init__.py`` — the file a bare
       import would load instead;
    2. every already-imported module with such a name that was loaded from
       neither ``lib_dir`` nor another framework ``lib/`` — a shadow that has
       already won, whatever ``sys.path`` says now.
    """
    names = _lib_module_names(lib_dir)
    if not names:
        return []

    shadows: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add(path: str, name: str) -> None:
        real = os.path.realpath(path)
        if real not in seen:
            seen.add(real)
            shadows.append((path, name))

    ahead: list[str] = []
    for entry in sys.path:
        directory = os.path.abspath(entry or os.curdir)
        if _same_dir(directory, lib_dir):
            break
        if os.path.isdir(directory) and not _is_framework_lib(directory):
            ahead.append(directory)

    for directory in ahead:
        for name in sorted(names):
            for candidate in (os.path.join(directory, name + ".py"),
                              os.path.join(directory, name, "__init__.py")):
                if os.path.isfile(candidate):
                    add(candidate, name)

    # A shadow that already WON: Python reuses the cached module whatever the
    # current sys.path order, so a stale board/task_yaml.py imported before
    # lib/ moved ahead still breaks `from task_yaml import …`. Any cached
    # lib-named module must come from lib_dir — or from another framework
    # lib/ (a test fixture's copy of the same module, see _is_framework_lib).
    for name in sorted(names):
        module = sys.modules.get(name)
        module_file = getattr(module, "__file__", None) if module else None
        if not module_file:
            continue
        home = os.path.dirname(os.path.realpath(module_file))
        if os.path.basename(module_file) == "__init__.py":
            home = os.path.dirname(home)
        if _same_dir(home, lib_dir) or _is_framework_lib(home):
            continue
        add(module_file, name)

    return shadows


def assert_lib_not_shadowed(lib_dir: str = _LIB_DIR) -> None:
    """Exit with a diagnostic naming each file that shadows a ``lib/`` module.

    Pass the calling TUI's own ``lib/`` (``<pkg>/../lib``): under a test
    harness the guard module may already be cached from a different checkout.
    """
    lib_dir = os.path.abspath(str(lib_dir))
    shadows = find_lib_shadows(lib_dir)
    if not shadows:
        return
    lines = ["aitasks: a file shadows a shared framework module and would be "
             "imported in its place:"]
    for path, name in shadows:
        lines.append(f"    {path}  shadows  {os.path.join(lib_dir, name + '.py')}")
    lines += [
        "",
        "This is usually a file a framework release moved into lib/ or deleted,",
        "left behind by an upgrade (kept because it differs from every shipped",
        "version, or because the project predates the cleanup).",
        "Run 'ait setup' to prune retired framework files, or remove it yourself:",
    ]
    for path, _name in shadows:
        lines.append(f"    git rm {path}   (then commit it by name; plain rm if untracked)")
    print("\n".join(lines), file=sys.stderr)
    raise SystemExit(1)
