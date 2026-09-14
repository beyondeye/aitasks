"""C1 guards for the `board/` package contract (t1794_1).

`aitask_board.py` is being split into flat-imported sibling modules
(`board/board_*.py`, parent plan t1794 "Target file map"). The contract that
keeps every loader working — the launcher, `board_fixture.load_board_module()`
(`spec_from_file_location` under a synthetic name), the shortcut sweep in
`lib/shortcut_scopes.py`, the canonical `import aitask_board` in the tests and
the subprocess loaders — is:

  * siblings are imported by **bare name** — never `board.`-qualified, never
    relative, never dynamically;
  * no `board/*.py` other than `aitask_board.py` imports `aitask_board` (under
    the fixture that would execute the canonical board with the fixture's
    `TASK_DIR` still set, rebinding `TASKS_DIR` and minting a second
    `KanbanApp`/`Task` identity — the t1613 class);
  * no two directories on the flat `sys.path` share a `*.py` basename
    (`shortcut_scopes._ensure_import_paths` builds that path from a set, so a
    duplicate resolves nondeterministically);
  * a sibling that owns a name the tests `patch.object` is bare-imported by
    `aitask_board.py`, so `ab.<module>` is a real patch target;
  * `aitask_board.py` puts its own directory on `sys.path`, so the flat imports
    resolve under every loader, not only under the tests' pre-seeded path;
  * every free global name in a `board/*.py` resolves to a module binding, a
    builtin or a module dunder, so a verbatim move that dropped an import fails
    here rather than as a `NameError` on a rarely-rendered path (t1794_2);
  * `board_widgets` imports on its own without loading `aitask_board`.

Every checker is a pure function over sources or directories, so each negative
control feeds a synthetic offender through the SAME checker that scans the
tree. A guard whose negative control also passes is testing nothing.

The C2 guard (no module but `aitask_board.py` resolves the task dir) lives in
test_board_fixture_harness.py, which the parent task's acceptance criteria name.

Run: bash tests/run_all_python_tests.sh
  or: ~/.aitask/venv/bin/python -m pytest tests/test_board_package_contract.py -q
"""

from __future__ import annotations

import ast
import functools
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / ".aitask-scripts"
BOARD_DIR = SCRIPTS / "board"
LIB_DIR = SCRIPTS / "lib"
TESTS_DIR = REPO_ROOT / "tests"
for _p in (str(TESTS_DIR / "lib"), str(LIB_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import board_fixture as bf  # noqa: E402
import shortcut_scopes  # noqa: E402

BOARD_PATH = BOARD_DIR / "aitask_board.py"

#: Pre-existing basename collisions on the flat path, pinned so they cannot
#: grow unnoticed. Both are latent, not failing: `applink/` imports `paths` /
#: `audit` flat while `chatlink/` ships modules of the same names, and the
#: shortcut sweep puts both directories on `sys.path` in set order. Why that is
#: safe today is documented in `shortcut_scopes._ensure_import_paths` (t1799).
#: A pin may never name `board` — the board package must stay collision-free.
KNOWN_COLLISIONS: dict[str, frozenset[str]] = {
    "paths.py": frozenset({"applink", "chatlink"}),
    "audit.py": frozenset({"applink", "chatlink"}),
}

#: Exact-expression exemptions from the deny-by-default dynamic-import rule,
#: keyed by `board/` filename. Empty: no board module loads anything
#: dynamically, and a flat module never needs to.
BOARD_DYNAMIC_IMPORT_ALLOWED: dict[str, frozenset[str]] = {}


# --- shared AST plumbing ------------------------------------------------------


def _parents(tree: ast.AST) -> dict[int, ast.AST]:
    parents: dict[int, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[id(child)] = node
    return parents


def _enclosing(node: ast.AST, parents: dict[int, ast.AST]) -> ast.AST:
    """Nearest enclosing Call, else nearest enclosing statement."""
    cur = node
    while id(cur) in parents:
        cur = parents[id(cur)]
        if isinstance(cur, (ast.Call, ast.stmt)):
            return cur
    return node


def _is_board_name(segment: str) -> bool:
    """A module name that can only mean a board module."""
    return (segment == "board" or segment.startswith("board_")
            or segment in bf.BOARD_MODULE_NAMES)


@functools.lru_cache(maxsize=None)
def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _py_files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _board_files() -> list[Path]:
    return sorted(BOARD_DIR.glob("*.py"))


# --- C1 (a): qualified / relative / dynamic imports ---------------------------

_DYNAMIC_IMPORT_FUNCS = frozenset({"import_module", "__import__"})


def _getattr_names(node: ast.AST, names) -> bool:
    return (isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name) and node.func.id == "getattr"
            and len(node.args) >= 2
            and isinstance(node.args[1], ast.Constant)
            and node.args[1].value in names)


def _callee_is_dynamic_import(node: ast.AST, aliases: set[str]) -> bool:
    """Does calling `node` perform `import_module` / `__import__`?"""
    if isinstance(node, ast.Name):
        return node.id in aliases
    if isinstance(node, ast.Attribute):
        # Any receiver: `importlib.import_module`, `il.import_module`,
        # `builtins.__import__`. The literal-argument rule below keeps a
        # hypothetical unrelated `.import_module` method from mattering.
        return node.attr in _DYNAMIC_IMPORT_FUNCS
    return _getattr_names(node, _DYNAMIC_IMPORT_FUNCS)


def _dynamic_import_aliases(tree: ast.AST) -> set[str]:
    """Bare names bound to `import_module` / `__import__`, through aliases."""
    aliases = {"__import__"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module in ("importlib", "builtins"):
            for alias in node.names:
                if alias.name in _DYNAMIC_IMPORT_FUNCS:
                    aliases.add(alias.asname or alias.name)
    changed = True
    while changed:  # `im = importlib.import_module`, then `load = im`, …
        changed = False
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1
                    and isinstance(node.targets[0], ast.Name)
                    and node.targets[0].id not in aliases
                    and _callee_is_dynamic_import(node.value, aliases)):
                aliases.add(node.targets[0].id)
                changed = True
    return aliases


def _dynamic_target_is_board(call: ast.Call, *, in_board: bool) -> bool:
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return False
    target = call.args[0].value
    if not isinstance(target, str):
        return False
    if target == "board" or target.startswith("board."):
        return True
    if not target.startswith("."):
        return False
    if in_board:
        return True  # any relative load from inside the flat package
    first = target.lstrip(".").split(".")[0]
    if first and _is_board_name(first):
        return True
    for kw in call.keywords:
        if (kw.arg == "package" and isinstance(kw.value, ast.Constant)
                and isinstance(kw.value.value, str)
                and (kw.value.value == "board" or kw.value.value.startswith("board."))):
            return True
    return False


def _qualified_board_imports(source: str, *, in_board: bool = False) -> list[str]:
    """Board imports that are not bare-name flat imports. Structural, via `ast`.

    `in_board` marks a file inside `board/`, where ANY relative import breaks
    flat loading. Elsewhere a relative import is only a finding when it names a
    board module, because other packages under `.aitask-scripts/` may
    legitimately use relative imports.
    """
    tree = ast.parse(source)
    aliases = _dynamic_import_aliases(tree)
    findings: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "board" or alias.name.startswith("board."):
                    findings.append(f"qualified import: {ast.unparse(node)}")
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                named = [node.module.split(".")[0]] if node.module else []
                named += [a.name for a in node.names]
                if in_board or any(_is_board_name(n) for n in named):
                    findings.append(f"relative import: {ast.unparse(node)}")
            elif node.module and (node.module == "board"
                                  or node.module.startswith("board.")):
                findings.append(f"qualified import: {ast.unparse(node)}")
        elif (isinstance(node, ast.Call)
              and _callee_is_dynamic_import(node.func, aliases)
              and _dynamic_target_is_board(node, in_board=in_board)):
            findings.append(f"dynamic import: {ast.unparse(node)}")
    return findings


# --- C1 (b): deny-by-default dynamic loading inside board/ ---------------------

_DYNAMIC_REFS = frozenset({"importlib", "import_module", "__import__",
                           "spec_from_file_location", "module_from_spec"})


def _board_dynamic_imports(source: str) -> list[str]:
    """Every reference to a dynamic-loading facility, call or value.

    Deny-by-default, like `_chdir_expressions` in test_board_fixture_harness.py:
    rejecting the *reference* catches `im = importlib.import_module` and
    `getattr(importlib, "import_module")` without any dataflow, whatever the
    argument turns out to be. Reported as the enclosing call/statement so an
    exemption can be pinned by exact expression.
    """
    tree = ast.parse(source)
    parents = _parents(tree)
    findings: list[str] = []
    seen: set[int] = set()

    def add(node):
        if id(node) not in seen:
            seen.add(id(node))
            findings.append(ast.unparse(node))

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(a.name == "importlib" or a.name.startswith("importlib.")
                   for a in node.names):
                add(node)
        elif isinstance(node, ast.ImportFrom):
            if ((node.module or "").split(".")[0] == "importlib"
                    or any(a.name in _DYNAMIC_REFS for a in node.names)):
                add(node)
        elif isinstance(node, ast.Name) and node.id in _DYNAMIC_REFS:
            add(_enclosing(node, parents))
        elif isinstance(node, ast.Attribute) and node.attr in _DYNAMIC_REFS:
            add(_enclosing(node, parents))
        elif _getattr_names(node, _DYNAMIC_REFS):
            add(_enclosing(node, parents))
    return findings


# --- C1 (c): no import-back of aitask_board -----------------------------------


def _aitask_board_imports(source: str) -> list[str]:
    findings = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            if any(a.name == "aitask_board" for a in node.names):
                findings.append(f"import-back: {ast.unparse(node)}")
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module == "aitask_board":
                findings.append(f"import-back: {ast.unparse(node)}")
    return findings


# --- C1 (d): module classification --------------------------------------------


def _unclassified_board_modules(board_dir: Path) -> list[str]:
    known = bf.BOARD_MODULE_NAMES | bf.BOARD_NON_MEMBERS
    return sorted(p.stem for p in board_dir.glob("*.py")
                  if p.stem != "__init__" and p.stem not in known)


# --- C1 (e): basename uniqueness on the flat path ------------------------------


def _flat_path_dirs() -> list[Path]:
    """The directories the flat contract makes importable, from the manifest."""
    dirs = {LIB_DIR, SCRIPTS, BOARD_DIR}
    for _name, rel_path, _scopes in shortcut_scopes.KNOWN_BINDING_SOURCES:
        dirs.add((SCRIPTS / rel_path).parent)
    return sorted(dirs)


def _basename_collisions(dirs, root: Path) -> dict[str, frozenset[str]]:
    """`{basename: {dir labels}}` for every `*.py` basename in 2+ dirs."""
    where: dict[str, set[str]] = {}
    for d in dirs:
        label = str(Path(d).relative_to(root))
        for p in Path(d).glob("*.py"):
            if p.name != "__init__.py":
                where.setdefault(p.name, set()).add(label)
    return {name: frozenset(labels) for name, labels in where.items()
            if len(labels) > 1}


def _collision_findings(collisions, pinned) -> list[str]:
    findings = []
    for name, labels in sorted(pinned.items()):
        if "board" in labels:
            findings.append(f"pin names board/: {name} {sorted(labels)}")
        if collisions.get(name) != labels:
            findings.append(f"stale pin: {name} pinned {sorted(labels)}, "
                            f"actual {sorted(collisions.get(name, ()))}")
    for name, labels in sorted(collisions.items()):
        if "board" in labels:
            findings.append(f"board collision: {name} {sorted(labels)}")
        elif pinned.get(name) != labels:
            findings.append(f"unpinned collision: {name} {sorted(labels)}")
    return findings


# --- C1 (f): patch targets owned by a sibling are bare-imported ----------------


def _patch_object_names(sources) -> set[str]:
    names: set[str] = set()
    for source in sources:
        for node in ast.walk(ast.parse(source)):
            if not (isinstance(node, ast.Call)
                    and ast.unparse(node.func).endswith("patch.object")):
                continue
            if (len(node.args) >= 2 and isinstance(node.args[1], ast.Constant)
                    and isinstance(node.args[1].value, str)):
                names.add(node.args[1].value)
            for kw in node.keywords:
                if (kw.arg == "attribute" and isinstance(kw.value, ast.Constant)
                        and isinstance(kw.value.value, str)):
                    names.add(kw.value.value)
    return names


def _top_level_names(source: str) -> set[str]:
    names: set[str] = set()
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                for leaf in ast.walk(target):
                    if isinstance(leaf, ast.Name):
                        names.add(leaf.id)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def _module_level_bare_imports(source: str) -> set[str]:
    """`import X` (no `as`) statements that bind at module level."""
    found: set[str] = set()

    def visit(stmts):
        for node in stmts:
            if isinstance(node, ast.Import):
                found.update(a.name for a in node.names if a.asname is None)
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                   ast.ClassDef)):
                continue
            else:
                for field in ("body", "orelse", "finalbody", "handlers"):
                    child = getattr(node, field, None)
                    if isinstance(child, list):
                        visit([c for c in child if isinstance(c, ast.AST)])
                        for handler in child:
                            if isinstance(handler, ast.ExceptHandler):
                                visit(handler.body)

    visit(ast.parse(source).body)
    return found


def _unpaired_patch_targets(board_dir: Path, patched: set[str],
                            board_source: str) -> list[str]:
    bare = _module_level_bare_imports(board_source)
    findings = []
    for path in sorted(board_dir.glob("board_*.py")):
        owned = _top_level_names(path.read_text(encoding="utf-8")) & patched
        if owned and path.stem not in bare:
            findings.append(
                f"{path.stem} defines patched {sorted(owned)} but "
                f"aitask_board.py has no module-level `import {path.stem}`")
    return findings


# --- C1 (g): every free global name in a board module resolves -----------------

#: Module attributes the interpreter provides without an assignment in source.
#: `__conditional_annotations__` is CPython 3.14's (PEP 649) bookkeeping for
#: module-level annotations under `if` / `try`; `symtable` reports it as a
#: referenced name (`aitask_merge.py` has one).
_MODULE_DUNDERS = frozenset({
    "__file__", "__name__", "__doc__", "__spec__", "__loader__", "__package__",
    "__builtins__", "__path__", "__annotations__", "__conditional_annotations__",
})


def _unresolved_globals(source: str, filename: str = "<source>") -> list[str]:
    """`<scope>: <name>` for every global reference nothing in the module binds.

    A verbatim move out of `aitask_board.py` fails SILENTLY when the moved code
    uses a name the new module never imported: the import succeeds and the
    `NameError` fires only when that path runs — a collapsed column header, a
    GitLab badge, a `date`-typed marker. `symtable` resolves scopes the way the
    compiler does, so locals, closures, comprehension variables and class
    attributes are not mistaken for globals. A name used only in annotations
    under `from __future__ import annotations` is a string, not a reference.
    """
    import builtins
    import symtable

    top = symtable.symtable(source, filename, "exec")
    bound = {s.get_name() for s in top.get_symbols()
             if s.is_assigned() or s.is_imported() or s.is_namespace()}
    known = bound | set(dir(builtins)) | _MODULE_DUNDERS
    findings: set[str] = set()

    def walk(table):
        for sym in table.get_symbols():
            name = sym.get_name()
            if name in known or not sym.is_referenced():
                continue
            if table is top or sym.is_global():
                findings.add(f"{'<module>' if table is top else table.get_name()}: {name}")
        for child in table.get_children():
            walk(child)

    walk(top)
    return sorted(findings)


# --- helpers for synthetic trees ------------------------------------------------


def _tmpdir(case: unittest.TestCase) -> Path:
    tmp = tempfile.TemporaryDirectory(prefix="board_c1_")
    case.addCleanup(tmp.cleanup)
    return Path(tmp.name)


def _write(root: Path, rel: str, text: str = "") -> Path:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


# =============================================================================


class QualifiedImportTests(unittest.TestCase):
    """No `board.`-qualified, relative or dynamic board import anywhere."""

    def test_tree_has_no_qualified_board_import(self):
        findings = []
        for root in (SCRIPTS, TESTS_DIR):
            for path in _py_files(root):
                in_board = path.parent == BOARD_DIR
                for f in _qualified_board_imports(_source(path), in_board=in_board):
                    findings.append(f"{path.relative_to(REPO_ROOT)}: {f}")
        self.assertEqual(findings, [],
                         "board modules are imported by bare name only (C1)")

    FLAGGED_OUTSIDE_BOARD = {
        "import_board": "import board\n",
        "import_board_dot": "import board.board_widgets\n",
        "from_board": "from board import board_widgets\n",
        "from_board_dot": "from board.board_widgets import TaskCard\n",
        "relative_names_module": "from .board_widgets import TaskCard\n",
        "relative_names_member": "from . import board_trail_view\n",
        "dyn_importlib": "import importlib\nimportlib.import_module('board.board_widgets')\n",
        "dyn_from_import": "from importlib import import_module\nimport_module('board')\n",
        "dyn_from_import_alias_relative": (
            "from importlib import import_module as im\n"
            "im('.board_x', package=__package__)\n"),
        "dyn_module_alias_relative": (
            "import importlib as il\n"
            "il.import_module('.board_task_model', package=pkg)\n"),
        "dyn_assignment_alias": (
            "import importlib\nloader = importlib.import_module\n"
            "again = loader\nagain('board.board_widgets')\n"),
        "dyn_dunder_import": "__import__('board.board_widgets')\n",
        "dyn_builtins_dunder": "import builtins\nbuiltins.__import__('board')\n",
        "dyn_getattr": "import importlib\ngetattr(importlib, 'import_module')('board.x')\n",
        "dyn_package_kwarg": "import importlib\nimportlib.import_module('.x', package='board')\n",
    }

    NOT_FLAGGED = {
        "string_literal": 'NOTE = "import board.board_widgets"\n',
        "flat_lib_module": "import importlib\nimportlib.import_module('board_columns')\n",
        "flat_import": "import board_columns\nimport board_widgets\n",
        "other_package_relative": (
            "import importlib\nimportlib.import_module('.helpers', package='monitor')\n"),
        "other_package_static_relative": "from .helpers import thing\n",
    }

    def test_every_offending_spelling_is_flagged(self):
        for label, source in self.FLAGGED_OUTSIDE_BOARD.items():
            with self.subTest(form=label):
                self.assertTrue(_qualified_board_imports(source),
                                f"{label} escaped the qualified-import guard")

    def test_benign_forms_are_not_flagged(self):
        for label, source in self.NOT_FLAGGED.items():
            with self.subTest(form=label):
                self.assertEqual(_qualified_board_imports(source), [],
                                 f"{label} is a false positive")

    def test_any_relative_import_inside_board_is_flagged(self):
        for source in ("from . import anything\n", "from .x import y\n",
                       "import importlib\nimportlib.import_module('.x', package=__package__)\n"):
            with self.subTest(source=source.strip()):
                self.assertTrue(_qualified_board_imports(source, in_board=True))
                if "importlib" not in source:
                    self.assertEqual(
                        _qualified_board_imports(source, in_board=False), [],
                        "outside board/ an unrelated relative import is legal")


class BoardDynamicImportTests(unittest.TestCase):
    """Deny-by-default: no `board/*.py` loads anything dynamically."""

    def test_board_modules_load_nothing_dynamically(self):
        for path in _board_files():
            with self.subTest(module=path.name):
                allowed = BOARD_DYNAMIC_IMPORT_ALLOWED.get(path.name, frozenset())
                found = [f for f in _board_dynamic_imports(_source(path))
                         if f not in allowed]
                self.assertEqual(
                    found, [],
                    f"{path.name}: a flat board module imports siblings by bare "
                    "name; pin a genuine need in BOARD_DYNAMIC_IMPORT_ALLOWED "
                    "by exact expression")

    def test_every_allowlist_entry_is_still_real(self):
        """A stale exemption would silently cover a future offender."""
        for name, exprs in BOARD_DYNAMIC_IMPORT_ALLOWED.items():
            path = BOARD_DIR / name
            self.assertTrue(path.is_file(), f"allowlist names missing {name}")
            found = set(_board_dynamic_imports(_source(path)))
            for expr in exprs:
                with self.subTest(module=name, expr=expr):
                    self.assertIn(expr, found, "stale exemption")

    FLAGGED = {
        "spec_from_file_location": (
            "import importlib.util\n"
            "spec = importlib.util.spec_from_file_location('x', 'y.py')\n"),
        "value_alias": "import importlib\nim = importlib.import_module\n",
        "from_import_alias": "from importlib import import_module as im\nim('x')\n",
        "dunder_import": "__import__('x')\n",
        "getattr_builtins": "import builtins\ngetattr(builtins, '__import__')('x')\n",
        "in_function": "def f():\n    import importlib\n    return importlib.import_module('x')\n",
    }

    def test_every_dynamic_spelling_is_flagged(self):
        for label, source in self.FLAGGED.items():
            with self.subTest(form=label):
                self.assertTrue(_board_dynamic_imports(source),
                                f"{label} escaped the deny-by-default rule")

    def test_benign_board_source_is_not_flagged(self):
        benign = ('"""Mentions importlib and import_module in prose only."""\n'
                  "import json\nimport board_widgets\nVALUE = json.loads('{}')\n")
        self.assertEqual(_board_dynamic_imports(benign), [])


class ImportBackTests(unittest.TestCase):
    """No `board/*.py` other than `aitask_board.py` imports `aitask_board`."""

    def test_no_sibling_imports_aitask_board(self):
        for path in _board_files():
            if path.name == "aitask_board.py":
                continue
            with self.subTest(module=path.name):
                self.assertEqual(_aitask_board_imports(_source(path)), [])

    def test_guard_flags_a_synthetic_import_back(self):
        root = _tmpdir(self)
        fake = _write(root, "board/board_fake.py",
                      "import aitask_board\nfrom aitask_board import KanbanApp\n"
                      "def f():\n    import aitask_board as ab\n")
        self.assertEqual(len(_aitask_board_imports(fake.read_text())), 3)
        self.assertEqual(_aitask_board_imports("import aitask_merge\n"), [])


class MembershipTests(unittest.TestCase):
    """Every `board/*.py` is classified, so the C2 and import guards cover it."""

    def test_every_board_module_is_classified(self):
        self.assertEqual(
            _unclassified_board_modules(BOARD_DIR), [],
            "add the new board/*.py to board_fixture.BOARD_MODULE_NAMES (part of "
            "the board app) or BOARD_NON_MEMBERS (an unrelated CLI)")

    def test_guard_flags_an_unclassified_module(self):
        root = _tmpdir(self)
        for name in ("__init__.py", "aitask_board.py", "aitask_merge.py",
                     "board_widgets.py", "board_mystery.py"):
            _write(root, name)
        self.assertEqual(_unclassified_board_modules(root), ["board_mystery"])


class BasenameCollisionTests(unittest.TestCase):
    """No `*.py` basename is shared by two directories on the flat path."""

    def test_flat_path_dirs_follow_the_manifest(self):
        labels = {str(d.relative_to(SCRIPTS)) for d in _flat_path_dirs()}
        self.assertTrue({"board", "lib", ".", "brainstorm", "applink",
                         "chatlink"} <= labels, sorted(labels))

    def test_tree_collisions_match_the_pins(self):
        collisions = _basename_collisions(_flat_path_dirs(), SCRIPTS)
        self.assertEqual(_collision_findings(collisions, KNOWN_COLLISIONS), [])

    def _layout(self, files):
        root = _tmpdir(self)
        for rel in files:
            _write(root, rel)
        dirs = sorted({(root / rel).parent for rel in files})
        return _basename_collisions(dirs, root)

    def test_board_collision_is_flagged_even_when_pinned(self):
        collisions = self._layout(["board/widgets.py", "brainstorm/widgets.py"])
        self.assertIn("board collision: widgets.py ['board', 'brainstorm']",
                      _collision_findings(collisions, {}))
        pinned = {"widgets.py": frozenset({"board", "brainstorm"})}
        self.assertTrue(any(f.startswith("pin names board/")
                            for f in _collision_findings(collisions, pinned)))

    def test_unpinned_collision_is_flagged(self):
        collisions = self._layout(["monitor/helpers.py", "stats/helpers.py"])
        self.assertEqual(_collision_findings(collisions, {}),
                         ["unpinned collision: helpers.py ['monitor', 'stats']"])

    def test_stale_pin_is_flagged(self):
        collisions = self._layout(["applink/paths.py", "chatlink/other.py"])
        findings = _collision_findings(
            collisions, {"paths.py": frozenset({"applink", "chatlink"})})
        self.assertTrue(any(f.startswith("stale pin: paths.py") for f in findings))

    def test_init_py_is_not_a_collision(self):
        self.assertEqual(self._layout(["a/__init__.py", "b/__init__.py"]), {})


class PatchPairingTests(unittest.TestCase):
    """A sibling that owns a patched name is bare-imported by aitask_board.py."""

    @staticmethod
    def _test_sources():
        return [_source(p) for p in _py_files(TESTS_DIR)]

    def test_scanner_sees_real_patch_targets(self):
        """Anti-vacuity: the check below means nothing if no names are found."""
        names = _patch_object_names(self._test_sources())
        self.assertIn("discover_trails", names)
        self.assertIn("resolve_dry_run_command", names)

    def test_tree_is_paired(self):
        findings = _unpaired_patch_targets(
            BOARD_DIR, _patch_object_names(self._test_sources()),
            _source(BOARD_PATH))
        self.assertEqual(findings, [])

    def test_guard_flags_an_unpaired_owner(self):
        root = _tmpdir(self)
        _write(root, "board_fake.py", "def discover_trails():\n    return []\n")
        patched = _patch_object_names(
            ['mock.patch.object(ab, "discover_trails", return_value=[])\n'])
        self.assertEqual(patched, {"discover_trails"})
        unpaired = _unpaired_patch_targets(root, patched, "import os\n")
        self.assertEqual(len(unpaired), 1)
        self.assertIn("board_fake", unpaired[0])
        for paired_source in ("import board_fake\n",
                              "try:\n    import board_fake\nexcept ImportError:\n    pass\n"):
            with self.subTest(board_source=paired_source):
                self.assertEqual(
                    _unpaired_patch_targets(root, patched, paired_source), [])
        # An aliased or function-local import does not make `ab.board_fake`.
        for unpaired_source in ("import board_fake as bfk\n",
                                "def f():\n    import board_fake\n"):
            with self.subTest(board_source=unpaired_source):
                self.assertTrue(
                    _unpaired_patch_targets(root, patched, unpaired_source))


class OwnDirInsertTests(unittest.TestCase):
    """`aitask_board.py` puts `board/` on `sys.path` itself.

    Deliberately a subprocess with a clean `PYTHONPATH`: every board test
    pre-inserts `board/`, so an in-process check would pass without the insert.
    """

    CODE = textwrap.dedent("""\
        import importlib.util, json, sys
        from pathlib import Path
        board = Path(sys.argv[1])
        spec = importlib.util.spec_from_file_location("aitask_board_c1_probe", board)
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        print(json.dumps({
            "board_dir": str(board.resolve().parent) in sys.path,
            "lib_dir": str(board.resolve().parent.parent / "lib") in sys.path,
        }))
        """)

    def test_loading_the_board_puts_its_directory_on_sys_path(self):
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "TASK_DIR")}
        proc = subprocess.run(
            [sys.executable, "-c", self.CODE, str(BOARD_PATH)],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
            timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        report = json.loads(proc.stdout.strip().splitlines()[-1])
        self.assertTrue(report["lib_dir"],
                        "control: the board's own lib insert must be visible")
        self.assertTrue(report["board_dir"],
                        "aitask_board.py must insert its own directory so flat "
                        "sibling imports resolve under every loader (C1)")


class UnresolvedGlobalsTests(unittest.TestCase):
    """Every free global name in every `board/*.py` resolves (t1794_2)."""

    def test_board_modules_resolve_every_global(self):
        for path in _board_files():
            with self.subTest(module=path.name):
                self.assertEqual(
                    _unresolved_globals(_source(path), str(path)), [],
                    f"{path.name} references names it neither defines nor "
                    "imports — a moved body that lost its import raises "
                    "NameError only when that path runs")

    def test_scan_covers_the_extracted_modules(self):
        names = {p.name for p in _board_files()}
        self.assertTrue({"aitask_board.py", "board_widgets.py"} <= names,
                        sorted(names))

    #: `(source, the scope the finding must name)`. Scope names for annotation
    #: scopes differ across interpreters, so only the stable ones are pinned.
    FLAGGED = {
        "function_body": ("import os\ndef f():\n    return Missing(os.sep)\n", "f"),
        "class_body": ("class C:\n    parse = staticmethod(Missing)\n", "C"),
        "module_body": ("VALUE = Missing + 1\n", "<module>"),
        "method_default": ("class C:\n    def f(self, x=Missing):\n        return x\n", None),
        "annotation_without_future": ("def f(task: Missing) -> None:\n    pass\n", None),
    }

    NOT_FLAGGED = {
        "locals_and_closures": ("def f(a):\n    b = 1\n    def g():\n"
                                "        return a + b\n    return g\n"),
        "comprehension": "def f(xs):\n    return [x * 2 for x in xs if x]\n",
        "builtins_and_dunders": "def f():\n    return len(__file__), __name__\n",
        "future_annotations": ("from __future__ import annotations\nclass C:\n"
                               "    x: Missing\n    def f(self, t: Missing) -> Missing:\n"
                               "        return t\n"),
        "imported_and_defined": ("from os import sep\nclass K:\n    pass\n"
                                 "def f():\n    return K, sep\n"),
        "attribute_via_self": ("class C:\n    y = 1\n    def f(self):\n"
                               "        return self.y\n"),
    }

    def test_every_unbound_reference_is_flagged(self):
        for label, (source, scope) in self.FLAGGED.items():
            with self.subTest(form=label):
                findings = _unresolved_globals(source)
                self.assertTrue(findings, f"{label} escaped the guard")
                self.assertTrue(all(f.endswith(": Missing") for f in findings),
                                findings)
                if scope is not None:
                    self.assertIn(f"{scope}: Missing", findings)

    def test_resolved_names_are_not_flagged(self):
        for label, source in self.NOT_FLAGGED.items():
            with self.subTest(form=label):
                self.assertEqual(_unresolved_globals(source), [],
                                 f"{label} is a false positive")


class HeadlessImportTests(unittest.TestCase):
    """`board_widgets` imports on its own and does not load the board (t1794_2).

    A subprocess whose `PYTHONPATH` is `board/` + `lib/` only, so nothing but
    the module's own imports decides what gets loaded. The test process has
    usually imported `aitask_board` already, so only a fresh interpreter can
    show that the widget layer does not drag the Kanban app in.
    """

    CODE = textwrap.dedent("""\
        import json, sys
        module = __import__(sys.argv[1])
        print(json.dumps({
            "board_loaded": "aitask_board" in sys.modules,
            "names": sorted(vars(module)),
        }))
        """)

    def _probe(self, module: str) -> dict:
        env = {k: v for k, v in os.environ.items()
               if k not in ("PYTHONPATH", "TASK_DIR")}
        env["PYTHONPATH"] = os.pathsep.join((str(BOARD_DIR), str(LIB_DIR)))
        proc = subprocess.run(
            [sys.executable, "-c", self.CODE, module],
            cwd=str(REPO_ROOT), env=env, capture_output=True, text=True,
            timeout=120)
        self.assertEqual(proc.returncode, 0, proc.stderr[-2000:])
        return json.loads(proc.stdout.strip().splitlines()[-1])

    def test_board_widgets_imports_without_the_board(self):
        report = self._probe("board_widgets")
        self.assertFalse(report["board_loaded"],
                         "importing board_widgets loaded aitask_board — the "
                         "widget layer must not depend on the Kanban app (C1)")
        for name in ("TaskCard", "PickerItem", "LoadingOverlay", "ColumnHeader",
                     "MarkedSelection", "_status_badge_text", "CardHost",
                     "ColumnHeaderHost"):
            self.assertIn(name, report["names"])

    def test_the_probe_can_see_the_board_loaded(self):
        """Negative control: the flag is observable, so `False` above means
        something."""
        self.assertTrue(self._probe("aitask_board")["board_loaded"])


if __name__ == "__main__":
    unittest.main()
