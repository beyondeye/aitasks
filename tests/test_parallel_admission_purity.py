"""Purity guard for the parallel-admission core and the roadmap policy layer.

Inline post-phase risk mitigation `purity_guard` (t1569_3) and
`purity_and_whitelist_guard` (t1569_5).

The pure/impure split IS the design: t1569_5 requires "no git, no subprocess,
fully fixture-testable", while t1569_4 needs live state. If `decide` ever
reaches for the filesystem, the clock or a subprocess, that requirement breaks
and a second definition of "safe" grows back in the roadmap.

The same guard covers t1569_5's own pure modules -- `roadmap_policy` and
`roadmap_premise` -- because the machinery (an AST scan plus an import with the
forbidden names poisoned) is generic and duplicating it would give two lists
that can disagree about what "pure" means. The file keeps its
parallel-admission name: renaming it would break every reference in the landed
t1569_3 plan and its commit trail for no behavioural gain. Its scope is this
docstring, not its filename.

A docstring saying "no subprocess" decays. This poisons the namespace instead,
so the constraint is enforced rather than asserted.
"""

import ast
import importlib
import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
LIB_DIR = os.path.join(REPO_ROOT, ".aitask-scripts", "lib")
sys.path.insert(0, LIB_DIR)

PURE_MODULES = ("parallel_admission", "parallel_admission_vocab",
                "parallel_admission_sweep",
                "roadmap_policy", "roadmap_premise")
PURE_SOURCES = tuple(os.path.join(LIB_DIR, m + ".py") for m in PURE_MODULES)

# The impure half is allowed all of these; the pure half is allowed none.
FORBIDDEN_MODULES = ("subprocess", "shutil", "socket")
FORBIDDEN_IMPORTS = ("os", "time", "subprocess", "shutil", "socket", "pathlib",
                     "glob", "platform", "datetime")


def _fresh_import(name):
    sys.modules.pop(name, None)
    return importlib.import_module(name)


class PoisonedNamespaceTests(unittest.TestCase):
    """Import and run the core with the impure modules made unimportable."""

    def setUp(self):
        self._saved = {m: sys.modules.get(m) for m in FORBIDDEN_MODULES}
        self._saved_pure = {m: sys.modules.get(m) for m in PURE_MODULES}
        self.addCleanup(self._restore)

    def _restore(self):
        for m, mod in self._saved.items():
            if mod is None:
                sys.modules.pop(m, None)
            else:
                sys.modules[m] = mod
        # Re-import the pure modules cleanly so later test modules in this same
        # process are unaffected by the poisoning.
        for m in PURE_MODULES:
            sys.modules.pop(m, None)
        for m in PURE_MODULES:
            importlib.import_module(m)

    def _poison(self):
        for m in FORBIDDEN_MODULES:
            sys.modules[m] = None
        for m in PURE_MODULES:
            sys.modules.pop(m, None)

    def test_core_imports_with_subprocess_poisoned(self):
        self._poison()
        vocab = _fresh_import("parallel_admission_vocab")
        pa = _fresh_import("parallel_admission")
        self.assertTrue(hasattr(pa, "decide"))
        self.assertTrue(hasattr(vocab, "format_reason"))

    def test_decide_still_emits_the_golden_bytes_while_poisoned(self):
        # Build the golden with a normal import first...
        pa = _fresh_import("parallel_admission")
        inp = _fixture(pa)
        golden = pa.render(pa.decide(inp))
        self.assertIn("VERDICT:", golden)

        # ...then prove the same input produces the same bytes with the impure
        # modules unimportable. A core that had quietly grown a subprocess call
        # would fail to import, or diverge here.
        self._poison()
        pa2 = _fresh_import("parallel_admission")
        self.assertEqual(pa2.render(pa2.decide(_fixture(pa2))), golden)

    def test_the_poison_is_real(self):
        """Negative control: a poisoned import genuinely fails.

        Without this, a no-op poison would make every assertion above vacuous.
        """
        self._poison()
        for m in FORBIDDEN_MODULES:
            with self.assertRaises(ImportError, msg=m):
                importlib.import_module(m)


def _fixture(pa):
    surface = pa.Surface("cand", "plan_declared", ("a.py", "hub.py"), "resolved", "n/a")
    claim = pa.InflightClaim(
        ref="t9", sources=("lock",), task_status="Implementing", liveness="live",
        same_host=True, claim_at_s=999_000,
        surface=pa.Surface("t9", "plan_declared", ("hub.py",), "resolved", "n/a"))
    return pa.AdmissionInput(
        candidate=surface,
        enumeration=(pa.SourceEvidence("gate"), pa.SourceEvidence("lock"),
                     pa.SourceEvidence("status")),
        inflight=(claim,), touch_counts={"hub.py": 40}, now=1_000_000)


class StaticPurityTests(unittest.TestCase):
    """AST scan -- catches an impure import even if no fixture exercises it."""

    def _tree(self, path):
        with open(path, encoding="utf-8") as fh:
            return ast.parse(fh.read(), filename=path)

    def test_pure_modules_import_nothing_impure(self):
        for path in PURE_SOURCES:
            for node in ast.walk(self._tree(path)):
                if isinstance(node, ast.Import):
                    names = [a.name.split(".")[0] for a in node.names]
                elif isinstance(node, ast.ImportFrom):
                    names = [(node.module or "").split(".")[0]]
                else:
                    continue
                for name in names:
                    self.assertNotIn(
                        name, FORBIDDEN_IMPORTS,
                        "%s must not import %r -- the clock and the filesystem "
                        "are fields of AdmissionInput, not ambient state"
                        % (os.path.basename(path), name))

    def test_no_clock_call_anywhere_in_the_pure_half(self):
        for path in PURE_SOURCES:
            for node in ast.walk(self._tree(path)):
                if not isinstance(node, ast.Call):
                    continue
                fn = node.func
                dotted = ""
                if isinstance(fn, ast.Attribute) and isinstance(fn.value, ast.Name):
                    dotted = "%s.%s" % (fn.value.id, fn.attr)
                elif isinstance(fn, ast.Name):
                    dotted = fn.id
                self.assertNotIn(dotted, ("time.time", "time.monotonic",
                                          "datetime.now", "os.getcwd"),
                                 "%s calls %s" % (os.path.basename(path), dotted))

    def test_the_scan_is_not_vacuous(self):
        """Negative control: the same scan flags a module that IS impure."""
        collector = os.path.join(LIB_DIR, "parallel_admission_collect.py")
        found = set()
        for node in ast.walk(self._tree(collector)):
            if isinstance(node, ast.Import):
                found.update(a.name.split(".")[0] for a in node.names)
        self.assertTrue(found & set(FORBIDDEN_IMPORTS),
                        "the collector should trip the scan; if it no longer "
                        "imports anything impure, this guard proves nothing")


class BoundaryTests(unittest.TestCase):
    def test_the_roadmap_path_never_needs_the_collector(self):
        """t1569_5 reuses the verdict logic without importing the impure half."""
        sys.modules.pop("parallel_admission_collect", None)
        pa = _fresh_import("parallel_admission")
        inp = pa.input_from_records(
            candidate_ref="1569_5",
            candidate_surface=pa.Surface("1569_5", "origin_derived", ("a.py",),
                                         "resolved", "topic"),
            inflight_lines=["INFLIGHT_PATH:t9|tracked|a.py"],
            batch_map_lines=["COMMIT:a.py|" + "a" * 40 + "|1|t1"],
            inflight_claims=[pa.InflightClaim(
                ref="t9", sources=("lock",), liveness="live", same_host=True,
                claim_at_s=1_000_000)],
            now=1_000_000)
        self.assertEqual(pa.decide(inp).verdict, "CONFLICT")
        self.assertNotIn("parallel_admission_collect", sys.modules)


if __name__ == "__main__":
    unittest.main()
