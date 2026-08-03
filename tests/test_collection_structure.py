"""Structural guards over the *shape* of ``tests/test_*.py`` (AST only, t1384).

This module owns guards that assert a syntactic property of every test file in
this tree. It parses each file with ``ast`` and **never imports a test module**,
so — unlike ``tests/test_no_zero_collection.py``, which must import siblings to
count discovery and therefore shells out to a probe subprocess — it needs no
isolation machinery at all. A parse costs microseconds; the whole sweep is a
handful of milliseconds over ~180 files.

Guard 1 — no class may inherit tests from a base in the same module
------------------------------------------------------------------

unittest and pytest **both** collect inherited test methods. So a class that
defines its own ``test_*`` methods *and* doubles as a helper base re-runs every
one of those methods once per subclass, silently.

t1354_4 measured the cost of one instance: ``TabbedShellTests`` in
``tests/test_syncer_rows.py`` defined 25 tests and served as the base for three
subclasses, so each subclass re-ran all 25 — **75 duplicate ``SyncerApp`` boots,
~46s, about half that file's runtime**, testing nothing the base run had not
already covered. Every duplicate passed, which is why it survived for as long as
it existed: there is no failing signal to notice, only time.

The sanctioned fix (the one t1354_4 applied) is a structural split: extract a
test-free ``_PrefixedBase`` holding only the helpers, keep the tests in a
concrete subclass, and re-point the other subclasses at the base. The leading
underscore is what keeps the base out of collection — the same pattern as
``_TabbedShellBase`` (``tests/test_syncer_rows.py``), ``GitRepoTestBase``
(``tests/test_history_data.py``) and ``BrainstormCrewTestBase``
(``tests/test_brainstorm_crew.py``).

Scope limits (deliberate — stated so they are not over-read)
------------------------------------------------------------

1. **Top-level classes only.** A class nested inside a function or another class
   is not a module attribute and is not collected by either backend.

2. **``ast.Name`` bases only.** Attribute bases (``mod.Base``) are intentionally
   out of scope. They *can* name a class in the same module, via a self-import,
   but resolving that would mean tracking import bindings; this guard declines
   to, and a control below pins the limit so it reads as deliberate rather than
   accidental.

3. **Direct edges only.** This is *detection*, not enumeration. Any chain that
   reaches a test-defining base contains a direct edge into it, so the chain is
   always flagged at that link — and the structural fix resolves the whole chain
   at once.

4. **Syntactic, not collection-aware.** The rule does not model whether either
   class is actually collected. It flags an edge purely on shape, so a hierarchy
   that no backend collects (e.g. a plain ``class Base:`` that is not a
   ``TestCase`` and is not named ``Test*``, carrying a ``def test_x``, plus a
   ``class Sub(Base)``) is flagged even though nothing re-runs. That is the
   intended trade: answering "is this collected?" would mean chasing base chains
   to ``unittest.TestCase`` through imports and attributes, which is exactly the
   fragility this guard exists to avoid. **A hit is normally answered with the
   structural refactor above, not with an allowlist entry.**

Adding a guard here
-------------------

Each guard in this module is three things: one allowlist ``frozenset`` with a
written policy comment, one live-tree ``TestCase``, and one falsifiability
``TestCase`` proving the oracle flags the defect **by name** and does not flag a
clean baseline. All of them share :func:`_iter_test_modules`.

The next intended occupant is **t1375**'s ``bare_module_test_fn_guard`` — a
structural check that no ``tests/test_*.py`` defines a module-level
``def test_*``. Today the only thing catching that shape is
``tests/test_collection_parity.py``, which is ``skipUnless(pytest importable)``
and therefore inert on a default install.

Run: python3 -m unittest tests.test_collection_structure
  or: bash tests/run_all_python_tests.sh
"""

from __future__ import annotations

import ast
import tempfile
import unittest
from pathlib import Path
from typing import Iterator, NamedTuple

REPO_ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = REPO_ROOT / "tests"

# Explicit, commented, and empty by design — the same policy as
# ZERO_COLLECTION_ALLOWLIST (tests/test_no_zero_collection.py) and
# PARITY_ALLOWLIST (tests/test_collection_parity.py). An entry is the exact pair
# key "<stem>: <Sub>(<Base>)" and needs a written justification. At t1384
# completion the live tree has zero violations, so nothing is waived.
#
# The normal answer to a hit is a STRUCTURAL REFACTOR, not an entry here: make
# the base test-free and move its tests into a concrete subclass. Waive an edge
# only when it is genuinely collected AND genuinely harmless, and say why.
INHERITED_TEST_DUP_ALLOWLIST: frozenset[str] = frozenset()


class _ScanResult(NamedTuple):
    """Findings plus the coverage counters behind the non-vacuity floor.

    ``modules`` and ``edges`` are returned rather than kept internal so a test
    can assert the sweep actually *reached* its decision points: a scan that
    silently found no files would otherwise report "no violations" — which reads
    identically to a clean tree.
    """

    findings: list[str]
    modules: int
    edges: int


def _iter_test_modules(tests_dir: str | Path) -> Iterator[tuple[str, ast.Module]]:
    """Yield ``(stem, tree)`` for every ``test_*.py`` under ``tests_dir``, sorted.

    **Fail-closed on unparsable source.** A ``SyntaxError`` is converted to an
    ``AssertionError`` naming the offending file — never caught-and-skipped,
    which would let a broken module drop silently out of every guard in this
    module while the suite stayed green. A control below exercises this branch,
    because an unexercised fail-closed path is one refactor away from a skip.
    """
    for path in sorted(Path(tests_dir).glob("test_*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise AssertionError(
                "%s does not parse, so no structural guard in "
                "tests/test_collection_structure.py can inspect it: %s"
                % (path.name, exc)
            ) from exc
        yield path.name[:-3], tree


def _own_test_methods(node: ast.ClassDef) -> list[str]:
    """``test_*`` methods defined DIRECTLY on ``node`` (sync or async).

    Direct children only: a method the class itself inherits is somebody else's
    finding, and counting it here would report the same duplication twice.
    """
    return [
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        and child.name.startswith("test_")
    ]


class _Pair(NamedTuple):
    """One offending edge: ``sub`` inherits ``base_tests`` from ``base``."""

    sub: str
    base: str
    base_tests: list[str]

    @property
    def key(self) -> str:
        """Stable allowlist key — deliberately free of the method count.

        Embedding the count would make an allowlist entry go stale the next time
        a test is added to the base, silently un-waiving it.
        """
        return f"{self.sub}({self.base})"


class _ModuleScan(NamedTuple):
    pairs: list[_Pair]
    edges: int


def _inherited_dup_pairs(tree: ast.Module) -> _ModuleScan:
    """Offending edges in one module, plus how many in-module edges were seen.

    ``edges`` counts every top-level ``ast.Name`` base that resolves to another
    top-level class in the same module — i.e. every decision point reached,
    offending or not. It is what distinguishes "clean" from "looked at nothing".
    """
    classes = {n.name: n for n in tree.body if isinstance(n, ast.ClassDef)}
    pairs: list[_Pair] = []
    edges = 0
    for name, node in classes.items():
        for base in node.bases:
            if not isinstance(base, ast.Name):
                continue  # scope limit 2: attribute bases are out of scope
            parent = classes.get(base.id)
            if parent is None:
                continue  # base is not defined in this module
            edges += 1
            owned = _own_test_methods(parent)
            if owned:
                pairs.append(_Pair(name, base.id, owned))
    return _ModuleScan(pairs, edges)


def _scan_dir(tests_dir: str | Path, allowlist: frozenset[str] | None = None) -> _ScanResult:
    """Scan a tests directory for inherited-test duplication.

    ``allowlist`` is an injectable parameter (defaulting to the module constant)
    so a control can prove the waiver mechanism is load-bearing rather than
    decorative — the live set ships empty, so nothing else would ever exercise
    it. Same shape as ``_sweep_findings(..., allowed=None)`` in
    ``tests/test_board_fixture_harness.py``.
    """
    allowed = INHERITED_TEST_DUP_ALLOWLIST if allowlist is None else allowlist
    findings: list[str] = []
    modules = 0
    edges = 0
    for stem, tree in _iter_test_modules(tests_dir):
        modules += 1
        scan = _inherited_dup_pairs(tree)
        edges += scan.edges
        for pair in scan.pairs:
            if f"{stem}: {pair.key}" in allowed:
                continue
            findings.append(
                "%s: %s re-runs %d inherited test_* method(s) defined on %s (%s)"
                % (
                    stem,
                    pair.key,
                    len(pair.base_tests),
                    pair.base,
                    ", ".join(sorted(pair.base_tests)),
                )
            )
    return _ScanResult(findings, modules, edges)


_FIX_HINT = (
    "Each of these subclasses silently re-runs every test_* method its base "
    "defines — unittest and pytest both collect inherited test methods, and "
    "every duplicate passes, so the only symptom is wall-clock time (t1354_4 "
    "measured 75 duplicate SyncerApp boots, ~46s, from one such base). Fix it "
    "structurally: extract a test-free `_PrefixedBase` holding only the "
    "helpers, keep the tests in a concrete subclass, and re-point the other "
    "subclasses at the base — the leading underscore is what keeps the base out "
    "of collection (see `_TabbedShellBase` in tests/test_syncer_rows.py). "
    "NOTE: this rule is SYNTACTIC — it does not check whether the classes are "
    "actually collected — so an uncollected hierarchy can trip it too; the "
    "answer is still the refactor. Only add a pair to "
    "INHERITED_TEST_DUP_ALLOWLIST in this file, with a written justification, "
    "when the edge is genuinely collected and genuinely harmless."
)


class NoInheritedTestDuplicationTests(unittest.TestCase):
    """The live tree: no class inherits tests from a base in the same module."""

    result: _ScanResult

    @classmethod
    def setUpClass(cls) -> None:
        # One sweep for the whole case (milliseconds); both tests read it.
        cls.result = _scan_dir(TESTS_DIR)

    def test_no_class_inherits_tests_from_a_same_module_base(self) -> None:
        self.assertEqual(
            self.result.findings, [], "%s\n\n%s" % (self.result.findings, _FIX_HINT)
        )

    def test_the_scan_reached_real_inheritance_edges(self) -> None:
        """Non-vacuity floor: a scan that found nothing is not a clean tree.

        Loose floors against a broken glob or a wrong TESTS_DIR, deliberately
        NOT pinned counts — at t1384 the tree had 183 modules and 166 in-module
        inheritance edges, and both numbers are expected to drift.
        """
        self.assertGreaterEqual(
            self.result.modules, 50,
            "only %d test module(s) were scanned — the glob or TESTS_DIR (%s) is "
            "wrong, and the guard above passed for lack of input, not for lack "
            "of violations" % (self.result.modules, TESTS_DIR),
        )
        self.assertGreaterEqual(
            self.result.edges, 1,
            "no in-module inheritance edge was examined at all, so the guard "
            "above never reached its decision point",
        )


def _write_tests_dir(root: str, files: dict[str, str]) -> str:
    """Materialise a synthetic ``tests/`` dir. Returns its path."""
    tdir = Path(root, "tests")
    tdir.mkdir()
    for name, content in files.items():
        Path(tdir, name).write_text(content, encoding="utf-8")
    return str(tdir)


_OFFENDER_SRC = (
    "import unittest\n"
    "class Base(unittest.TestCase):\n"
    "    def test_a(self):\n"
    "        pass\n"
    "    def test_b(self):\n"
    "        pass\n"
    "class Sub(Base):\n"
    "    pass\n"
)

#: The sanctioned shape t1354_4 introduced: a test-free underscore base plus a
#: concrete subclass holding the tests. Must never be flagged.
_CLEAN_SRC = (
    "import unittest\n"
    "class _Helper(unittest.TestCase):\n"
    "    def helper(self):\n"
    "        pass\n"
    "class Real(_Helper):\n"
    "    def test_a(self):\n"
    "        pass\n"
)

#: Each fixture is (source, expected-flagged-pair-keys). Together they pin every
#: scope boundary in the module docstring: a boundary with no fixture is a
#: boundary a refactor can move without anything noticing.
_DISCRIMINATION_FIXTURES: dict[str, tuple[str, list[str]]] = {
    # --- positives -------------------------------------------------------
    "a_plain": (_OFFENDER_SRC, ["Sub(Base)"]),
    "b_async": (
        "import unittest\n"
        "class Base(unittest.IsolatedAsyncioTestCase):\n"
        "    async def test_a(self):\n"
        "        pass\n"
        "class Sub(Base):\n"
        "    pass\n",
        ["Sub(Base)"],
    ),
    # Transitive chain A -> B -> C: only the B(C) link is reported, and that is
    # sufficient — fixing it (making C test-free) resolves A as well.
    "c_transitive": (
        "import unittest\n"
        "class C(unittest.TestCase):\n"
        "    def test_a(self):\n"
        "        pass\n"
        "class B(C):\n"
        "    pass\n"
        "class A(B):\n"
        "    pass\n",
        ["B(C)"],
    ),
    # Scope limit 4: syntactic, not collection-aware. Neither class here is
    # collected by unittest (not a TestCase) or pytest (not named Test*), yet
    # the edge is still flagged. Pinned as DELIBERATE: a refactor that quietly
    # made the scan collection-aware would break this fixture and have to
    # justify itself rather than silently narrowing the guard.
    "d_uncollected_hierarchy": (
        "class Base:\n"
        "    def test_x(self):\n"
        "        pass\n"
        "class Sub(Base):\n"
        "    pass\n",
        ["Sub(Base)"],
    ),
    # --- negatives -------------------------------------------------------
    "e_sanctioned_fix": (_CLEAN_SRC, []),
    "f_out_of_module_base": (
        "from somewhere import Base\n"
        "class Sub(Base):\n"
        "    def test_a(self):\n"
        "        pass\n",
        [],
    ),
    # Scope limit 2: an attribute base is not resolved even when its attribute
    # name collides with a test-defining class in this very module.
    "g_attribute_base": (
        "import unittest\n"
        "import somemod as m\n"
        "class Base(unittest.TestCase):\n"
        "    def test_a(self):\n"
        "        pass\n"
        "class Sub(m.Base):\n"
        "    pass\n",
        [],
    ),
    # Structural, not substring: the base only MENTIONS a test method in its
    # docstring. A grep-based rule would flag this.
    "h_docstring_mention": (
        "import unittest\n"
        "class Base(unittest.TestCase):\n"
        '    """Helpers only. Do not add `def test_x` to this class."""\n'
        "    def helper(self):\n"
        "        pass\n"
        "class Sub(Base):\n"
        "    def test_a(self):\n"
        "        pass\n",
        [],
    ),
    # Scope limit 1: a class defined inside a function is not a module
    # attribute and is collected by nobody.
    "i_nested_in_function": (
        "import unittest\n"
        "def factory():\n"
        "    class Base(unittest.TestCase):\n"
        "        def test_a(self):\n"
        "            pass\n"
        "    class Sub(Base):\n"
        "        pass\n"
        "    return Sub\n",
        [],
    ),
}


class InheritedDupOracleFalsifiabilityTests(unittest.TestCase):
    """Negative control: prove the oracle detects the defect it guards.

    A guard that cannot flag the exact shape t1354_4 removed would be
    decorative. Everything here runs against synthetic sources — no real test
    file is ever mutated to demonstrate a guard.
    """

    def test_oracle_flags_the_t1354_4_shape_in_a_synthetic_tests_dir(self) -> None:
        """Through ``_scan_dir`` — the same entry point the live test uses."""
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _write_tests_dir(tmp, {
                "test_offender.py": _OFFENDER_SRC,
                "test_clean.py": _CLEAN_SRC,
            })
            result = _scan_dir(tdir)

        joined = " | ".join(result.findings)
        # Flagged BY FILE AND CLASS PAIR — not merely "something was flagged".
        self.assertIn("test_offender", joined, f"oracle missed the defect: {result.findings}")
        self.assertIn("Sub(Base)", joined, f"oracle named the wrong pair: {result.findings}")
        self.assertIn("re-runs 2 inherited", joined,
                      f"oracle reported the wrong count: {result.findings}")
        # And the sanctioned shape is NOT flagged, so the control cannot pass
        # for the trivial reason that everything is flagged.
        self.assertNotIn("test_clean", joined,
                         f"oracle false-positived on the sanctioned fix: {result.findings}")
        # The coverage counters the live non-vacuity floor rests on are real:
        # two modules, and one in-module edge in each (Sub(Base), Real(_Helper)).
        self.assertEqual((result.modules, result.edges), (2, 2))

    def test_oracle_discriminates_on_each_scope_boundary(self) -> None:
        for label, (source, expected) in sorted(_DISCRIMINATION_FIXTURES.items()):
            with self.subTest(fixture=label):
                pairs = _inherited_dup_pairs(ast.parse(source)).pairs
                self.assertEqual(sorted(p.key for p in pairs), sorted(expected))

    def test_scan_fails_closed_on_an_unparsable_module(self) -> None:
        """A module that does not parse must break the scan, never be skipped.

        Without this control the fail-closed branch in ``_iter_test_modules`` is
        never executed by any test, and a later refactor could swap it for an
        ``except SyntaxError: continue`` — dropping a broken module out of every
        guard here while the whole suite stayed green.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _write_tests_dir(tmp, {
                "test_broken_syntax.py": "class Base(:\n    pass\n",
                "test_ok.py": _CLEAN_SRC,
            })
            with self.assertRaises(AssertionError) as caught:
                _scan_dir(tdir)

        self.assertIn("test_broken_syntax.py", str(caught.exception))

    def test_allowlist_entry_suppresses_exactly_the_pinned_pair(self) -> None:
        """The waiver mechanism is load-bearing, despite shipping empty.

        An allowlist no control ever exercises is a decorative lie: it could be
        wired to the wrong key, or to nothing at all, and the empty live set
        would hide it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = _write_tests_dir(tmp, {"test_offender.py": _OFFENDER_SRC})

            waived = _scan_dir(tdir, allowlist=frozenset({"test_offender: Sub(Base)"}))
            near_miss = _scan_dir(tdir, allowlist=frozenset({"test_offender: Sub(Other)"}))

        self.assertEqual(waived.findings, [], "the pinned pair was not waived")
        # The edge is still traversed — a waiver suppresses the finding, it does
        # not make the scan stop looking.
        self.assertEqual(waived.edges, 1)
        self.assertEqual(
            len(near_miss.findings), 1,
            "a near-miss allowlist key suppressed a real finding — the key is "
            "being matched loosely instead of exactly",
        )


if __name__ == "__main__":
    unittest.main()
