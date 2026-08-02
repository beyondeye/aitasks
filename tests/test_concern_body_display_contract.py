"""Structural guard for the canonical-body vs display-body contract (t1294).

``Concern.body`` is CANONICAL — exactly what the shadow emitted, terminal
``Disposition:`` / ``Verified:`` trailer included — and ``Concern.display_body()``
is that text minus the trailer. The rule is asymmetric and both misuses are
silent:

* the forward path (``build_clipboard_payload``) MUST read ``.body``, or the
  disposition is deleted from what the followed agent receives;
* the display path (``_ConcernRow.render``) MUST read ``display_body()``, or the
  picker shows metadata instead of prose.

t1274 enforced that only in prose comments. This module freezes it as data:
every Concern-body read in ``.aitask-scripts/monitor/`` is classified with a
ROLE, and each role forbids the accessor it must never use.

Pattern followed: ``tests/test_board_persistence_seam.py`` (lines 490-577) — a
frozen registry, a fail-closed AST scanner, and negative controls that mutate an
in-memory copy of the real source. There is no written guard-test convention in
``aidocs/framework/testing_conventions.md``; the convention is precedent-only,
hence the explicit citation.

**Why AST and not grep.** ``.body`` appears in CSS inside triple-quoted strings
(``monitor_shared.py``'s ``DEFAULT_CSS``) and on unrelated types; a regex cannot
tell those apart from a Concern read.

**Why the whole ``monitor/`` package.** ``Concern`` is a monitor-package type
that is never exported, so the package is the true frontier: a Concern-body read
added in ANY monitor file surfaces here as an unclassified key. A per-file
whitelist would miss it, and a whitelist of ``concern_parser`` importers would
not correlate (all three current importers read no body at all). Scope stops at
``monitor/`` deliberately — widening to all of ``.aitask-scripts/`` drags in
unrelated ``.body`` on other types and buys nothing.

**Runtime half — cross-referenced, not duplicated.** These two already pin the
behaviour at runtime and would fail if either accessor were swapped:

* ``tests/test_concern_picker_modal.py::ConcernPickerNarrowLayoutTests::test_display_body_hides_the_trailer_from_the_row``
* ``tests/test_concern_parser.py::TestDispositionDerivation::test_body_stays_canonical_and_forwarding_is_byte_identical``

Only ``DisplayBodyContractTests`` below needs an import from the tree; the AST
half imports nothing, so the guard still runs when ``textual`` is unavailable.

**Known blind spot.** A ``Concern`` that reaches an unannotated parameter in a
module that never names ``Concern``, and is then read by tuple index there, is
not caught: the scanner cannot link that name to ``Concern``. Indexed reads
through names it CAN link are caught (see ``_concern_linked_names``). The
alternative — flagging every integer subscript in the package — would drown the
guard in ``lines[0]`` / ``args[1]`` noise.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_concern_body_display_contract -v
"""

from __future__ import annotations

import ast
import hashlib
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(REPO_ROOT / ".aitask-scripts" / "board"))

MONITOR_DIR = REPO_ROOT / ".aitask-scripts" / "monitor"
PARSER_SRC = MONITOR_DIR / "concern_parser.py"
SHARED_SRC = MONITOR_DIR / "monitor_shared.py"

#: The two accessor spellings this guard tracks. ``display_body`` is defined on
#: exactly one class in the whole repo (``concern_parser.Concern``), so any read
#: of it is concern-bearing by construction and is NEVER exempted.
TRACKED = ("body", "display_body")

FORWARD = "forward"      # re-emits to the followed agent — MUST NOT read display_body()
DISPLAY = "display"      # renders for the human        — MUST NOT read .body (or [2])
INTERNAL = "internal"    # Concern's own canonical reader

#: Index of ``body`` in the ``Concern`` NamedTuple — ``c[2]`` is a working
#: bypass of ``display_body()`` and is treated exactly like ``.body``.
BODY_INDEX = 2

_FORBIDDEN = {
    FORWARD: frozenset({"display_body"}),
    DISPLAY: frozenset({"body", f"[{BODY_INDEX}]"}),
}

# Source: .aitask-scripts/monitor/concern_parser.py:176-183 ("``body`` is
#   CANONICAL … Display surfaces call display_body instead; the clipboard path
#   must always use ``body``") and
#   .aitask-scripts/monitor/monitor_shared.py:1290-1292 ("display_body(), never
#   .body — the Disposition:/Verified: trailer is metadata for the receiving
#   agent, not for this row").
#
# FROZEN, and every row is a real Concern surface — there are no filler rows to
# rubber-stamp. A new or moved Concern-body read must consciously add a row
# here, WITH a role. A silent pass after a refactor is a bug in this table.
#
# If a display surface one day legitimately needs the canonical body, do NOT
# widen its accessor set — move that read into a separate helper carrying its
# own FORWARD/INTERNAL role. Widening the set is what this guard exists to stop.
EXPECTED_ACCESSES = {
    ("concern_parser.py", "Concern.display_body", "self"): (
        INTERNAL, frozenset({"body"})),
    ("concern_parser.py", "build_clipboard_payload", "c"): (
        FORWARD, frozenset({"body"})),
    ("monitor_shared.py", "_ConcernRow.render", "self._concern"): (
        DISPLAY, frozenset({"display_body"})),
}

#: Concrete types whose instances are provably NOT Concerns. POSITIVE list: an
#: annotation must resolve to one of these to exempt a read. A negative test
#: ("the annotation does not mention Concern") would be unsound — ``Any``,
#: ``object``, a bare TypeVar, a Protocol or an unresolved alias can each carry
#: a Concern without spelling its name.
NON_CONCERN_TYPES = {"TaskInfo"}  # monitor_core.TaskInfo — the task-record type

#: There is deliberately NO per-site exemption list. The only two ways to clear
#: an unclassified read are to make it classifiable: annotate the receiver with
#: its concrete type, or — if that type is genuinely never a Concern — add it to
#: NON_CONCERN_TYPES above. A suppression list keyed by call site would let a
#: real misuse be waved through with a plausible-looking justification, which is
#: exactly the review signal this guard exists to produce.


# --------------------------------------------------------------------------
# AST helpers
# --------------------------------------------------------------------------

def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _owner_chain(parents, node) -> list[str]:
    """Every enclosing ClassDef/FunctionDef name, outermost first.

    Walks to the module root rather than stopping at the first enclosing
    function: a bare ``render`` collides across classes and loses the
    ``_ConcernRow.`` prefix that carries the meaning.
    """
    parts: list[str] = []
    cur = parents.get(node)
    while cur is not None:
        if isinstance(cur, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            parts.append(cur.name)
        cur = parents.get(cur)
    return list(reversed(parts))


def _qualname(parents, node) -> str:
    return ".".join(_owner_chain(parents, node)) or "<module>"


def _receiver(node: ast.AST) -> str | None:
    """Dotted receiver name, or None when it is not a plain Name/Attribute chain.

    Built by hand rather than via ``ast.unparse`` so the frozen registry cannot
    drift with a Python version bump. None means UNANALYSABLE — never dropped.
    """
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _receiver(node.value)
        return f"{base}.{node.attr}" if base else None
    return None


def _resolve_annotation(ann: ast.AST | None) -> str | None:
    """Positively resolve an annotation to a NON_CONCERN_TYPES member, else None.

    Closed-world on purpose: only a bare Name/Attribute in the allowlist,
    ``Optional[X]``, or an ``X | None`` union resolving to a single such type
    counts. Everything else — Any, object, TypeVars, Protocols, unresolved
    aliases, generics — returns None and leaves the read UNCLASSIFIED.
    """
    if ann is None:
        return None
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        try:
            ann = ast.parse(ann.value, mode="eval").body
        except SyntaxError:
            return None
    if isinstance(ann, ast.BinOp) and isinstance(ann.op, ast.BitOr):
        parts: list[ast.AST] = []

        def _flatten(n: ast.AST) -> None:
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr):
                _flatten(n.left)
                _flatten(n.right)
            else:
                parts.append(n)

        _flatten(ann)
        named = [p for p in parts
                 if not (isinstance(p, ast.Constant) and p.value is None)]
        resolved = {_resolve_annotation(p) for p in named}
        if len(resolved) == 1 and None not in resolved:
            return resolved.pop()
        return None
    if isinstance(ann, ast.Subscript):
        base = ann.value.id if isinstance(ann.value, ast.Name) else None
        return _resolve_annotation(ann.slice) if base == "Optional" else None
    if isinstance(ann, ast.Name):
        return ann.id if ann.id in NON_CONCERN_TYPES else None
    if isinstance(ann, ast.Attribute):
        return ann.attr if ann.attr in NON_CONCERN_TYPES else None
    return None


def _mentions_concern(ann: ast.AST | None) -> bool:
    if ann is None:
        return False
    if isinstance(ann, ast.Constant) and isinstance(ann.value, str):
        return "Concern" in ann.value
    return "Concern" in ast.dump(ann)


def _functions(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            yield node


def _nonconcern_names(tree, parents) -> set[tuple[tuple[str, ...], str]]:
    """Names positively bound to a concrete non-Concern type.

    Scoped to the function (or, for ``self.<attr>``, the class) that binds them.
    Three rules, all requiring POSITIVE resolution:

    1. a parameter whose annotation resolves into ``NON_CONCERN_TYPES``;
    2. ``self.<attr> = <param>`` in ``__init__`` for such a parameter;
    3. ``x = self.<attr>`` where ``self.<attr>`` is already non-Concern.
    """
    found: set[tuple[tuple[str, ...], str]] = set()
    for fn in _functions(tree):
        chain = _owner_chain(parents, fn)
        scope = tuple(chain + [fn.name])
        cls = tuple(chain)
        for arg in list(fn.args.args) + list(fn.args.kwonlyargs):
            if _resolve_annotation(arg.annotation) is None:
                continue
            found.add((scope, arg.arg))
            if fn.name != "__init__":
                continue
            for stmt in ast.walk(fn):
                if not (isinstance(stmt, ast.Assign)
                        and isinstance(stmt.value, ast.Name)
                        and stmt.value.id == arg.arg):
                    continue
                for target in stmt.targets:
                    name = _receiver(target)
                    if name and name.startswith("self."):
                        found.add((cls, name))
    for fn in _functions(tree):
        chain = _owner_chain(parents, fn)
        scope = tuple(chain + [fn.name])
        cls = tuple(chain)
        for stmt in ast.walk(fn):
            if not isinstance(stmt, ast.Assign):
                continue
            src = _receiver(stmt.value)
            if not src or (cls, src) not in found:
                continue
            for target in stmt.targets:
                if isinstance(target, ast.Name):
                    found.add((scope, target.id))
    return found


def _concern_linked_names(tree, parents, label: str) -> set[tuple[tuple[str, ...], str]]:
    """Names the scanner can link to ``Concern``. Additive inference only.

    Imprecision costs recall, never false alarms — a name this misses simply
    falls through to UNCLASSIFIED rather than being wrongly flagged.
    """
    linked: set[tuple[tuple[str, ...], str]] = set()
    for cls_node in ast.walk(tree):
        if isinstance(cls_node, ast.ClassDef) and cls_node.name == "Concern":
            for fn in _functions(cls_node):
                chain = _owner_chain(parents, fn)
                linked.add((tuple(chain + [fn.name]), "self"))
    for fn in _functions(tree):
        chain = _owner_chain(parents, fn)
        scope = tuple(chain + [fn.name])
        containers: set[str] = set()
        for arg in list(fn.args.args) + list(fn.args.kwonlyargs):
            if not _mentions_concern(arg.annotation):
                continue
            if isinstance(arg.annotation, ast.Subscript):
                containers.add(arg.arg)
            else:
                linked.add((scope, arg.arg))
        for stmt in ast.walk(fn):
            if (isinstance(stmt, ast.For) and isinstance(stmt.iter, ast.Name)
                    and stmt.iter.id in containers
                    and isinstance(stmt.target, ast.Name)):
                linked.add((scope, stmt.target.id))
            if isinstance(stmt, ast.Assign) and isinstance(stmt.value, ast.Call):
                fname = _receiver(stmt.value.func)
                if fname in ("Concern", "parse_concerns"):
                    for target in stmt.targets:
                        if isinstance(target, ast.Name):
                            linked.add((scope, target.id))
    for (file_label, qualname, receiver) in EXPECTED_ACCESSES:
        if file_label != label:
            continue
        scope = tuple(qualname.split("."))
        linked.add((scope, receiver))
        # Also link at the OWNING scope: a declared ``self._concern`` holds a
        # Concern for the whole class, so a sibling method reading it is a new
        # surface (an undeclared key), not an unclassifiable one.
        if len(scope) > 1:
            linked.add((scope[:-1], receiver))
    return linked


def _accessor_map(source: str, label: str) -> dict[tuple[str, str, str], set[str]]:
    """Map every tracked Concern-body read in ``source`` to its accessor set.

    Keys are ``(label, qualname, receiver)``; values are the set of accessor
    spellings used there (``body``, ``display_body``, ``[2]``). Reads through a
    receiver positively resolved as a non-Concern type are dropped; anything the
    scanner cannot resolve is emitted with an ``UNCLASSIFIED``/``UNANALYSABLE``
    marker so it can never compare equal to an expected entry.

    A file that fails to parse RAISES — a guard that skips what it cannot read
    is a guard that passes on a broken tree.
    """
    tree = ast.parse(source)
    parents = _parent_map(tree)
    nonconcern = _nonconcern_names(tree, parents)
    linked = _concern_linked_names(tree, parents, label)
    found: dict[tuple[str, str, str], set[str]] = {}

    def _scopes(node):
        chain = tuple(_owner_chain(parents, node))
        return chain, chain[:-1]

    def _record(node, receiver: str | None, accessor: str, *, tracked_attr: bool):
        fn_scope, cls_scope = _scopes(node)
        qualname = ".".join(fn_scope) or "<module>"
        if receiver is None:
            key = (label, qualname, "UNANALYSABLE: non-name receiver")
            found.setdefault(key, set()).add(accessor)
            return
        is_linked = (fn_scope, receiver) in linked or (cls_scope, receiver) in linked
        is_nonconcern = ((fn_scope, receiver) in nonconcern
                         or (cls_scope, receiver) in nonconcern)
        if is_linked and is_nonconcern:
            key = (label, qualname, f"CONTRADICTION: {receiver}")
            found.setdefault(key, set()).add(accessor)
            return
        # display_body is defined on Concern alone — never exempt it.
        if is_nonconcern and not (tracked_attr and accessor == "display_body"):
            return
        if is_linked:
            found.setdefault((label, qualname, receiver), set()).add(accessor)
            return
        # Neither Concern-linked nor positively proven non-Concern. Exemption
        # requires proof; absence of proof is never exemption.
        key = (label, qualname, f"UNCLASSIFIED: {receiver}")
        found.setdefault(key, set()).add(accessor)

    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr in TRACKED:
            _record(node, _receiver(node.value), node.attr, tracked_attr=True)
        elif isinstance(node, ast.Call) and _receiver(node.func) == "getattr":
            if len(node.args) < 2:
                continue
            name_arg = node.args[1]
            if isinstance(name_arg, ast.Constant) and name_arg.value in TRACKED:
                _record(node, _receiver(node.args[0]), name_arg.value,
                        tracked_attr=True)
            elif not isinstance(name_arg, ast.Constant):
                recv = _receiver(node.args[0])
                fn_scope, cls_scope = _scopes(node)
                qualname = ".".join(fn_scope) or "<module>"
                if recv is None:
                    # The receiver is an expression (a call, a subscript, a
                    # comprehension result), so it cannot be proven non-Concern.
                    # Dropping it would let ``getattr(make_concern(), name)``
                    # walk straight past the guard. Report, never drop.
                    found.setdefault(
                        (label, qualname,
                         "UNANALYSABLE: dynamic getattr on an expression"),
                        set()).add("UNANALYSABLE: unresolved receiver")
                elif ((fn_scope, recv) in linked or (cls_scope, recv) in linked
                        or (fn_scope, recv) in nonconcern
                        or (cls_scope, recv) in nonconcern):
                    found.setdefault(
                        (label, qualname, recv), set()
                    ).add("UNANALYSABLE: dynamic getattr")
        elif isinstance(node, ast.Subscript):
            recv = _receiver(node.value)
            fn_scope, cls_scope = _scopes(node)
            if not ((fn_scope, recv) in linked or (cls_scope, recv) in linked):
                continue
            index = node.slice
            if isinstance(index, ast.Constant) and isinstance(index.value, int):
                _record(node, recv, f"[{index.value}]", tracked_attr=False)
            elif not isinstance(index, ast.Slice):
                _record(node, recv, "UNANALYSABLE: dynamic index",
                        tracked_attr=False)
    return found


def _scan_package(directory: Path) -> dict[tuple[str, str, str], set[str]]:
    merged: dict[tuple[str, str, str], set[str]] = {}
    for path in sorted(directory.rglob("*.py")):
        label = str(path.relative_to(directory))
        merged.update(_accessor_map(path.read_text(encoding="utf-8"), label))
    return merged


def _expected_accessor_sets() -> dict[tuple[str, str, str], set[str]]:
    return {key: set(accessors) for key, (_role, accessors)
            in EXPECTED_ACCESSES.items()}


def _diff_message(got, expected) -> str:
    undeclared, unclassified, vanished, changed = [], [], [], []
    for key, accessors in sorted(got.items(), key=str):
        marker = key[2]
        if key in expected:
            if accessors != expected[key]:
                changed.append(f"    {key}: expected {sorted(expected[key])}, "
                               f"found {sorted(accessors)}")
        elif marker.startswith(("UNCLASSIFIED", "UNANALYSABLE", "CONTRADICTION")):
            unclassified.append(f"    {key} -> {sorted(accessors)}")
        else:
            undeclared.append(f"    {key} -> {sorted(accessors)}")
    for key in sorted(set(expected) - set(got), key=str):
        vanished.append(f"    {key} -> {sorted(expected[key])}")

    out = []
    if changed:
        out.append("accessor set CHANGED (this is the swap this file exists to "
                   "catch):\n" + "\n".join(changed))
    if undeclared:
        out.append("undeclared Concern-body reads (classify them in "
                   "EXPECTED_ACCESSES, WITH a role):\n" + "\n".join(undeclared))
    if unclassified:
        out.append("reads the evidence pass could not resolve — annotate the "
                   "receiver with its concrete type, or add that type to "
                   "NON_CONCERN_TYPES if it is never a Concern:\n"
                   + "\n".join(unclassified))
    if vanished:
        out.append("declared reads that vanished (a refactor moved or removed "
                   "them):\n" + "\n".join(vanished))
    return "\n" + "\n".join(out) if out else ""


# --------------------------------------------------------------------------
# 1. The contract
# --------------------------------------------------------------------------

class ConcernAccessorContractTests(unittest.TestCase):
    """The frozen accessor table, and the role rule it cannot be edited around."""

    def test_every_concern_body_read_in_the_monitor_package_is_declared(self):
        got = _scan_package(MONITOR_DIR)
        expected = _expected_accessor_sets()
        self.assertEqual(got, expected, _diff_message(got, expected))

    def test_no_surface_reads_the_accessor_its_role_forbids(self):
        """Cannot be silenced by editing observed facts.

        A maintainer who swaps a surface and then 'fixes' the red equality test
        by editing its expected set turns that test green but leaves this one
        red — the role, not the observation, is the contract.
        """
        got = _scan_package(MONITOR_DIR)
        for key, (role, _accessors) in EXPECTED_ACCESSES.items():
            banned = _FORBIDDEN.get(role, frozenset())
            observed = got.get(key, set())
            self.assertTrue(observed, f"{key} declares role {role!r} but reads "
                                      f"nothing — the surface moved or vanished")
            for accessor in banned:
                self.assertNotIn(
                    accessor, observed,
                    f"{key} has role {role!r} and must never read {accessor!r}; "
                    f"observed {sorted(observed)}")

    def test_evidence_classification_is_unambiguous(self):
        """The premises the exemption pass rests on."""
        self.assertNotIn("Concern", NON_CONCERN_TYPES)
        for key, accessors in _scan_package(MONITOR_DIR).items():
            self.assertFalse(
                key[2].startswith("CONTRADICTION"),
                f"{key} resolves as both Concern-linked and non-Concern")
            self.assertFalse(
                key[2].startswith("UNCLASSIFIED"),
                f"{key} -> {sorted(accessors)} could not be classified")


# --------------------------------------------------------------------------
# 2. The one runtime precondition the source scan cannot see
# --------------------------------------------------------------------------

class DisplayBodyContractTests(unittest.TestCase):

    def test_display_body_is_not_an_alias_of_body(self):
        """The precondition the whole source guard rests on.

        Every assertion above compares WHICH accessor is called. If
        ``display_body`` were reimplemented as ``return self.body`` the map is
        unchanged and the guard is blind — this is the only thing that sees it.
        """
        from monitor.concern_parser import Concern

        concern = Concern(
            "high", "r",
            "Real prose. Disposition: blocking. Verified: CONFIRMED.",
            "blocking", "CONFIRMED",
        )
        self.assertIn("Disposition:", concern.body)
        self.assertNotIn("Disposition:", concern.display_body())
        self.assertNotIn("Verified:", concern.display_body())
        self.assertNotEqual(concern.display_body(), concern.body)
        self.assertIn("Real prose.", concern.display_body())


# --------------------------------------------------------------------------
# 3. Negative controls — a guard that cannot fail is testing nothing
# --------------------------------------------------------------------------

class GuardDiscriminationTests(unittest.TestCase):
    """Every control mutates an in-memory copy; nothing on disk changes."""

    def _variant(self, path: Path, old: str, new: str):
        src = path.read_text(encoding="utf-8")
        self.assertEqual(
            src.count(old), 1,
            f"anchor is not unique in {path.name}: {old!r} — a control that "
            f"substitutes the wrong site proves nothing")
        return _accessor_map(src.replace(old, new, 1), path.name)

    def test_positive_control_unmutated_sources_match_the_registry(self):
        """A failing control below must never be blamable on a broken fixture."""
        got = _scan_package(MONITOR_DIR)
        self.assertEqual(got, _expected_accessor_sets(), _diff_message(
            got, _expected_accessor_sets()))

    def test_guard_fails_when_the_row_reads_the_canonical_body(self):
        """AC #1 — _ConcernRow.render switched to .body."""
        got = self._variant(
            SHARED_SRC,
            "escape(self._concern.display_body())",
            "escape(self._concern.body)")
        key = ("monitor_shared.py", "_ConcernRow.render", "self._concern")
        self.assertEqual(got[key], {"body"})
        self.assertIn("body", _FORBIDDEN[DISPLAY])
        self.assertNotEqual(got[key], EXPECTED_ACCESSES[key][1])

    def test_guard_fails_when_the_clipboard_path_strips_the_trailer(self):
        """AC #2 — build_clipboard_payload switched to display_body()."""
        got = self._variant(
            PARSER_SRC,
            'f"- [{c.priority} | {c.region}] {c.body}"',
            'f"- [{c.priority} | {c.region}] {c.display_body()}"')
        key = ("concern_parser.py", "build_clipboard_payload", "c")
        self.assertEqual(got[key], {"display_body"})
        self.assertIn("display_body", _FORBIDDEN[FORWARD])

    def test_guard_fails_on_an_indexed_bypass_of_display_body(self):
        """``c[2]`` reads the canonical body straight past display_body()."""
        got = self._variant(
            SHARED_SRC,
            "escape(self._concern.display_body())",
            "escape(self._concern[2])")
        key = ("monitor_shared.py", "_ConcernRow.render", "self._concern")
        self.assertEqual(got[key], {f"[{BODY_INDEX}]"})
        self.assertIn(f"[{BODY_INDEX}]", _FORBIDDEN[DISPLAY])

    def test_guard_flags_a_brand_new_surface(self):
        """The catcher a fixed two-surface check cannot provide."""
        got = self._variant(
            SHARED_SRC,
            "        return self._concern\n",
            "        return self._concern.body\n")
        key = ("monitor_shared.py", "_ConcernRow.concern", "self._concern")
        self.assertIn(key, got)
        self.assertNotIn(key, EXPECTED_ACCESSES)

    def test_guard_fails_closed_on_a_dynamic_getattr(self):
        """An Attribute-only scan would be blind to getattr()."""
        got = self._variant(
            SHARED_SRC,
            "escape(self._concern.display_body())",
            "escape(getattr(self._concern, which))")
        self.assertTrue(
            any("UNANALYSABLE" in a for accessors in got.values()
                for a in accessors),
            f"dynamic getattr was silently dropped: {got}")

    def test_guard_fails_closed_on_a_dynamic_getattr_over_an_expression(self):
        """A NEW surface reaching a Concern through an unresolvable receiver.

        ``getattr(make_concern(), accessor)`` names neither a tracked attribute
        nor a resolvable receiver. An earlier revision recorded nothing here, so
        adding such a surface left the map byte-identical and the guard passed
        silently — the exact opposite of the documented fail-closed contract.
        """
        baseline = _accessor_map(
            SHARED_SRC.read_text(encoding="utf-8"), "monitor_shared.py")
        got = self._variant(
            SHARED_SRC,
            "        return self._concern\n",
            "        return self._concern\n\n"
            "    def leak(self, accessor):\n"
            "        return getattr(make_concern(), accessor)\n")
        self.assertNotEqual(got, baseline,
                            "a dynamic getattr on an expression was dropped")
        self.assertTrue(
            any("UNANALYSABLE" in k[2] for k in got),
            f"the unresolved receiver was not reported: {sorted(got)}")

    def test_guard_sees_a_constant_getattr(self):
        got = self._variant(
            SHARED_SRC,
            "escape(self._concern.display_body())",
            'escape(getattr(self._concern, "body"))')
        key = ("monitor_shared.py", "_ConcernRow.render", "self._concern")
        self.assertEqual(got[key], {"body"})


class EvidencePassTests(unittest.TestCase):
    """The exemption pass must absorb churn WITHOUT hiding misuse."""

    def _variant(self, path: Path, old: str, new: str):
        src = path.read_text(encoding="utf-8")
        self.assertEqual(src.count(old), 1,
                         f"anchor is not unique in {path.name}: {old!r}")
        return _accessor_map(src.replace(old, new, 1), path.name)

    def _baseline(self) -> dict:
        return _accessor_map(SHARED_SRC.read_text(encoding="utf-8"),
                             "monitor_shared.py")

    def test_renaming_an_unrelated_method_does_not_churn_the_registry(self):
        got = self._variant(SHARED_SRC, "def _detail_widgets(self)",
                            "def _detail_widgets_renamed(self)")
        self.assertEqual(got, self._baseline())

    def test_a_second_read_through_an_evidenced_receiver_does_not_churn(self):
        got = self._variant(
            SHARED_SRC,
            "        self._showing_plan = False\n",
            "        self._showing_plan = False\n"
            "        self._cached = self._info.body\n")
        self.assertEqual(got, self._baseline())

    def test_dropping_the_annotation_brings_the_read_back_into_review(self):
        got = self._variant(SHARED_SRC, "def __init__(self, info: TaskInfo)",
                            "def __init__(self, info)")
        self.assertTrue(
            any(k[2].startswith("UNCLASSIFIED") for k in got),
            f"an unannotated receiver was silently exempted: {sorted(got)}")

    def test_a_broad_annotation_is_never_treated_as_proof(self):
        """Any/object can each carry a Concern without spelling its name."""
        for broad in ("Any", "object"):
            with self.subTest(annotation=broad):
                got = self._variant(
                    SHARED_SRC, "def __init__(self, info: TaskInfo)",
                    f"def __init__(self, info: {broad})")
                self.assertTrue(
                    any(k[2].startswith("UNCLASSIFIED") for k in got),
                    f"{broad!r} was wrongly accepted as proof of non-Concern: "
                    f"{sorted(got)}")

    def test_annotation_resolution_accepts_only_concrete_allowlisted_types(self):
        def resolve(src: str):
            return _resolve_annotation(
                ast.parse(f"def f(x: {src}): ...").body[0].args.args[0].annotation)

        self.assertEqual(resolve("TaskInfo"), "TaskInfo")
        self.assertEqual(resolve('"TaskInfo | None"'), "TaskInfo")
        self.assertEqual(resolve("Optional[TaskInfo]"), "TaskInfo")
        for unsound in ("Any", "object", "T", "SomeAlias", "Renderable",
                        "list[TaskInfo]", "Concern"):
            with self.subTest(annotation=unsound):
                self.assertIsNone(resolve(unsound))


class EndToEndAcceptanceTests(unittest.TestCase):
    """Run the real scanner over a real package DIRECTORY, mutated in a copy.

    The production tree is never opened for writing: the swaps are applied to a
    temp copy and the originals are asserted byte-identical afterwards. No
    manual undo, no ``git checkout``, nothing left behind on interruption.
    """

    def _hashes(self) -> dict[str, str]:
        return {
            str(p.relative_to(MONITOR_DIR)):
                hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(MONITOR_DIR.rglob("*.py"))
        }

    def test_each_contract_swap_fails_against_a_mutated_package_copy(self):
        before = self._hashes()
        tmp_root = Path(tempfile.mkdtemp(prefix="aitask-t1294-"))
        self.addCleanup(shutil.rmtree, tmp_root, ignore_errors=True)

        swaps = [
            ("monitor_shared.py",
             "escape(self._concern.display_body())",
             "escape(self._concern.body)"),
            ("concern_parser.py",
             'f"- [{c.priority} | {c.region}] {c.body}"',
             'f"- [{c.priority} | {c.region}] {c.display_body()}"'),
            ("monitor_shared.py",
             "escape(self._concern.display_body())",
             "escape(self._concern[2])"),
        ]

        for index, (filename, old, new) in enumerate(swaps):
            pkg = tmp_root / f"case{index}"
            shutil.copytree(MONITOR_DIR, pkg,
                            ignore=shutil.ignore_patterns("__pycache__"))
            target = pkg / filename
            src = target.read_text(encoding="utf-8")
            self.assertEqual(src.count(old), 1,
                             f"anchor is not unique in {filename}: {old!r}")
            target.write_text(src.replace(old, new, 1), encoding="utf-8")

            got = _scan_package(pkg)
            with self.subTest(swap=new):
                self.assertNotEqual(
                    got, _expected_accessor_sets(),
                    f"the equality assertion did not notice {new!r}")
                violated = any(
                    accessor in got.get(key, set())
                    for key, (role, _a) in EXPECTED_ACCESSES.items()
                    for accessor in _FORBIDDEN.get(role, frozenset()))
                self.assertTrue(
                    violated, f"the role rule did not notice {new!r}: {got}")

        self.assertEqual(self._hashes(), before,
                         "the production package was modified — it must not be")


if __name__ == "__main__":
    unittest.main()
