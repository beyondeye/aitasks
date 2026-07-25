"""Discovery guard: every ``tests/test_*.py`` must contribute ≥1 collected test.

t1211 fixed the Python aggregate suite (``bash tests/run_all_python_tests.sh``)
after finding six script-style / import-guarded test files that contributed
**zero** collected tests and therefore silently dropped out of the gate
(102 previously-unrun checks). This guard (t1229) makes that failure mode
impossible to reintroduce silently: it asserts that every ``tests/test_*.py``
file contributes at least one collected test under ``unittest`` discovery, and
that no test module fails to import.

**Which branch this validates.** ``run_all_python_tests.sh`` prefers ``pytest``
when it is installed and falls back to ``unittest`` discovery. This guard
validates the **unittest-discovery** branch: it always runs its own
``unittest discover`` in a subprocess regardless of whether pytest is present,
so its verdict is deterministic and independent of the local pytest install.

**Why the check is external (subprocess), not an in-process TestCase.** Counting
discovery from inside a running TestCase would have to import every sibling test
module into *this* process — circular (the guard is itself a ``test_*.py``) and
side-effect-laden (import-time registrations, ``sys.modules`` mutations). Instead
the guard shells out to a probe subprocess that runs ``unittest`` discovery in
isolation, so no sibling import can pollute the harness process.

**Attribution is per-file, not per-class.** A single flattened discovery keyed by
``type(test).__module__`` would credit each test to the module where its
``TestCase`` class is *defined*, so a wrapper/re-export file could look empty even
though it contributes runnable tests. The probe therefore discovers each file
independently (``discover(pattern="<exact filename>")``) and counts every
``TestCase`` reachable *from that file*.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Explicit, commented, and empty by design. At t1229 completion every
# tests/test_*.py collects ≥1 test, so no file needs waiving. If a file
# *legitimately* collects zero tests (e.g. a pure data/fixture module that
# should never have matched test_*.py), add its stem here with a one-line
# justification — NEVER a silent skip. An entry here waives a real file, so it
# must be a deliberate, reviewed decision.
ZERO_COLLECTION_ALLOWLIST: frozenset[str] = frozenset()

# Runs in a subprocess (argv[1]=tests_dir, argv[2]=result_path). Discovers each
# tests/test_*.py file on its own, counts the tests reachable from it, flags any
# file that fails to import, and writes the result as JSON to the result FILE —
# never to stdout, so an import-time banner/print cannot corrupt the protocol.
_PROBE_SRC = r'''
import glob
import json
import os
import sys
import unittest
import unittest.loader


def _walk(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _walk(item)
        else:
            yield item


def main():
    tests_dir, result_path = sys.argv[1], sys.argv[2]
    loader = unittest.TestLoader()
    counts = {}
    failed = []
    for path in sorted(glob.glob(os.path.join(tests_dir, "test_*.py"))):
        basename = os.path.basename(path)
        stem = basename[:-3]
        suite = loader.discover(start_dir=tests_dir, pattern=basename)
        collected = 0
        broke = False
        for test in _walk(suite):
            # A module that fails to import is surfaced as a
            # unittest.loader._FailedTest instance (not attributed to its own
            # module); count it as a breakage, not as a collected test. Match by
            # CLASS IDENTITY (isinstance), not by name — a legitimate TestCase
            # that happens to be named "_FailedTest" must not be misclassified.
            if isinstance(test, unittest.loader._FailedTest):
                broke = True
            else:
                collected += 1
        counts[stem] = collected
        if broke:
            failed.append(stem)
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump({"counts": counts, "failed": failed}, handle)


if __name__ == "__main__":
    main()
'''


def _run_probe(tests_dir: str | os.PathLike) -> tuple[dict[str, int], list[str]]:
    """Run the discovery probe over ``tests_dir`` and return (counts, failed).

    ``counts`` maps every ``test_*.py`` stem to the number of tests reachable
    from that file (a zero-collection file is present with value 0, not absent).
    ``failed`` lists the stems whose module failed to import.
    """
    env = dict(os.environ)
    # Mirror run_all_python_tests.sh so board/lib imports resolve even on a
    # direct `python tests/test_no_zero_collection.py` run (not only under the
    # harness that already exports PYTHONPATH).
    board = str(REPO_ROOT / ".aitask-scripts" / "board")
    lib = str(REPO_ROOT / ".aitask-scripts" / "lib")
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([board, lib] + ([existing] if existing else []))
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    handle, result_path = tempfile.mkstemp(prefix="zero_collection_probe_", suffix=".json")
    os.close(handle)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _PROBE_SRC, str(tests_dir), result_path],
            capture_output=True,
            text=True,
            env=env,
        )
        if proc.returncode != 0:
            raise AssertionError(
                "discovery probe subprocess exited %d\n--- stdout ---\n%s\n"
                "--- stderr ---\n%s" % (proc.returncode, proc.stdout, proc.stderr)
            )
        with open(result_path, encoding="utf-8") as handle_r:
            data = json.load(handle_r)
        return data["counts"], data["failed"]
    finally:
        try:
            os.unlink(result_path)
        except OSError:
            pass


def _write(dir_path: str, name: str, content: str) -> None:
    with open(os.path.join(dir_path, name), "w", encoding="utf-8") as handle:
        handle.write(content)


class NoZeroCollectionTests(unittest.TestCase):
    """Assert the live tree has no zero-collection or import-failing test file."""

    counts: dict[str, int]
    failed: list[str]

    @classmethod
    def setUpClass(cls) -> None:
        # One discovery sweep for the whole case (~0.5 s); both tests read it.
        cls.counts, cls.failed = _run_probe(REPO_ROOT / "tests")

    def test_every_test_file_contributes_a_collected_test(self) -> None:
        zero = {stem for stem, n in self.counts.items() if n == 0}
        zero -= ZERO_COLLECTION_ALLOWLIST
        self.assertFalse(
            zero,
            "These tests/test_*.py files collect zero tests under `unittest "
            "discover` and silently drop out of `run_all_python_tests.sh`: %s. "
            "Give each file a real TestCase, or (only with a justification) add "
            "its stem to ZERO_COLLECTION_ALLOWLIST in this file."
            % sorted(zero),
        )

    def test_no_test_module_fails_to_import(self) -> None:
        self.assertEqual(
            sorted(self.failed),
            [],
            "These tests/test_*.py files fail to import under `unittest discover` "
            "(surfaced as unittest.loader._FailedTest, which would otherwise mask "
            "the breakage as a passing test): %s. Run `python -m unittest "
            "tests.<name>` to see the underlying ImportError."
            % sorted(self.failed),
        )


class GuardFalsifiabilityTests(unittest.TestCase):
    """Negative control: prove the guard's oracle is not vacuous.

    Runs the same probe against a synthetic tests/ dir whose files deliberately
    exhibit each defect (and each hardening property). This keeps the two
    hardening guarantees — per-file attribution and the isolated result channel
    — permanently pinned: a refactor that reintroduced class-origin attribution
    or bare-stdout parsing would make one of these assertions fail.
    """

    def test_oracle_flags_synthetic_defects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = os.path.join(tmp, "tests")
            os.makedirs(tdir)

            # Baseline positive.
            _write(
                tdir, "test_good.py",
                "import unittest\n"
                "class Good(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
            )
            # The zero-collection defect: script-style, __main__-guarded, no
            # TestCase.
            _write(
                tdir, "test_zerocollect.py",
                "def main():\n"
                "    return 0\n"
                'if __name__ == "__main__":\n'
                "    raise SystemExit(main())\n",
            )
            # The import-failure defect.
            _write(
                tdir, "test_broken.py",
                "import a_module_that_does_not_exist_zzz  # noqa\n"
                "import unittest\n"
                "class Broken(unittest.TestCase):\n"
                "    def test_x(self):\n"
                "        pass\n",
            )
            # Per-file-attribution fixture: the base defines the tests; the
            # wrapper only re-imports Base (no own method, no subclass). Under
            # the rejected class-origin attribution the wrapper would count 0.
            _write(
                tdir, "test_base_fixture.py",
                "import unittest\n"
                "class Base(unittest.TestCase):\n"
                "    def test_shared(self):\n"
                "        pass\n",
            )
            _write(
                tdir, "test_wrapper_reexport.py",
                "import os\n"
                "import sys\n"
                "sys.path.insert(0, os.path.dirname(__file__))\n"
                "from test_base_fixture import Base  # noqa: F401  re-export only\n",
            )
            # Isolated-channel fixture: prints to stdout at import time but has a
            # real TestCase. If the probe regressed to parsing bare stdout JSON,
            # this banner would corrupt the parse.
            _write(
                tdir, "test_noisy.py",
                "import unittest\n"
                'print("BANNER: import-time stdout noise")\n'
                "class Noisy(unittest.TestCase):\n"
                "    def test_n(self):\n"
                "        pass\n",
            )
            # Identity-vs-name fixture: a legitimate, importable TestCase whose
            # class name is exactly "_FailedTest". Pins isinstance-based
            # detection — a name-only check would misclassify it as a broken
            # import and report the file as zero-collection.
            _write(
                tdir, "test_lookalike.py",
                "import unittest\n"
                "class _FailedTest(unittest.TestCase):\n"
                "    def test_real(self):\n"
                "        self.assertTrue(True)\n",
            )

            counts, failed = _run_probe(tdir)

        # Zero-collection defect is flagged.
        self.assertEqual(counts.get("test_zerocollect"), 0)
        # Import-failure defect is flagged — and ONLY that file.
        self.assertEqual(failed, ["test_broken"])
        # Positive baseline collects.
        self.assertGreaterEqual(counts.get("test_good", 0), 1)
        # Per-file attribution: the pure re-export wrapper is credited.
        self.assertGreaterEqual(counts.get("test_wrapper_reexport", 0), 1)
        # Isolated channel: the stdout banner did not break the protocol.
        self.assertGreaterEqual(counts.get("test_noisy", 0), 1)
        # Identity-based detection: a valid TestCase named "_FailedTest" is
        # collected, not misreported as a broken import.
        self.assertGreaterEqual(counts.get("test_lookalike", 0), 1)
        self.assertNotIn("test_lookalike", failed)


if __name__ == "__main__":
    unittest.main()
