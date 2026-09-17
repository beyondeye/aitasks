"""Source-level "single home" checks for code moved out of aitask_board.py.

Lifted verbatim from tests/test_board_trail_view.py (t1794_3) when t1794_4 needed
the same checks for board_task_model / board_workflow_phase /
board_task_manager. Re-export identity cannot see a stale copy left ABOVE the
board's import (the import rebinds the name, identity stays true, the dead
duplicate survives), so each moved name is checked on the SOURCE. The negative
controls for these helpers stay in test_board_trail_view.SingleHomeTests.

Pure `ast` over source strings: no board import, no fixture.
"""

from __future__ import annotations

import ast


def _name_targets(node):
    if isinstance(node, ast.Name):
        yield node
    elif isinstance(node, (ast.Tuple, ast.List)):
        for elt in node.elts:
            yield from _name_targets(elt)
    elif isinstance(node, ast.Starred):
        yield from _name_targets(node.value)


def _top_level_bindings(source: str) -> dict[str, list[int]]:
    """Names bound at MODULE scope -> the lines binding them.

    Covers `def` / `async def` / `class` and assignment targets (plain,
    annotated, augmented; tuples unpacked), including those nested in
    module-level `if` / `try` / `with` blocks. Function and class bodies are
    not module scope and are not walked. Imports are deliberately NOT bindings:
    the board importing a moved name back is the contract, not a copy.
    """
    found: dict[str, list[int]] = {}

    def add(name, lineno):
        found.setdefault(name, []).append(lineno)

    def walk(body):
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef,
                                 ast.ClassDef)):
                add(node.name, node.lineno)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    for name in _name_targets(target):
                        add(name.id, node.lineno)
            elif isinstance(node, (ast.AnnAssign, ast.AugAssign)):
                for name in _name_targets(node.target):
                    add(name.id, node.lineno)
            elif isinstance(node, ast.If):
                walk(node.body)
                walk(node.orelse)
            elif isinstance(node, ast.Try):
                walk(node.body)
                for handler in node.handlers:
                    walk(handler.body)
                walk(node.orelse)
                walk(node.finalbody)
            elif isinstance(node, ast.With):
                walk(node.body)

    walk(ast.parse(source).body)
    return found


def _single_home_findings(board_src: str, view_src: str, names, *,
                          board_label: str = "aitask_board.py",
                          view_label: str = "board_trail_view.py") -> list[str]:
    """One finding per name that is not defined exactly once in the view, or
    that the board still defines anywhere at module scope."""
    board = _top_level_bindings(board_src)
    view = _top_level_bindings(view_src)
    findings = []
    for name in names:
        where = view.get(name, [])
        if not where:
            findings.append(f"{name}: not defined in {view_label}")
        elif len(where) > 1:
            findings.append(f"{name}: defined {len(where)}x in {view_label} "
                            f"(lines {where})")
        for lineno in board.get(name, []):
            findings.append(f"{name}: still defined in {board_label}:{lineno}")
    return findings


def _imported_from(source: str, module: str) -> set[str]:
    """Names the module body imports from `module` under their own name."""
    names: set[str] = set()
    for node in ast.parse(source).body:
        if (isinstance(node, ast.ImportFrom) and node.module == module
                and node.level == 0):
            names |= {a.name for a in node.names if a.asname is None}
    return names
