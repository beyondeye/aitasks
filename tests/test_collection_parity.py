"""Both test backends must collect the same effective set (t1354_3).

`tests/run_all_python_tests.sh` prefers pytest when it is installed and falls
back to `unittest discover`. Those two backends do **not** collect the same
things by default: pytest additionally collects module-level ``def test_*``
functions, which `unittest` ignores entirely. Six files in this suite were
written in the t1211 script-style shape — a ``main()`` driver, a tally-based
``assert_eq`` that increments a counter instead of raising, and a
``ScriptChecksTest`` wrapper asserting ``main() == 0``. Under pytest their bare
driver functions were *also* collected, so:

- in the four tally-style modules they passed **vacuously** (the tally never
  raises, so a genuinely failing check reported as a green pytest test) while
  corrupting the module-global counters their own ``ScriptChecksTest`` asserts on;
- in the two raise-style modules they simply ran everything twice.

t1354_3 renamed those drivers to ``_check_*``. This guard makes the divergence
impossible to reintroduce silently, and — unlike
``tests/test_no_zero_collection.py``, which deliberately validates only the
**unittest** branch — it is the only check that actually compares the two.

**Which branch this validates.** Both. It is skipped when pytest is absent, so
it is inert on a default install and active exactly where the claim matters: a
machine that ran the opt-in dev tier (`ait setup --with-dev`). That is also the
"machine WITH real pytest" configuration t1320 recorded as untestable here.

**Why counts, not node ids.** The two backends spell an id differently
(``tests/test_x.py::C::m`` vs ``test_x.C.m``), so only the per-file *count* is
directly comparable. It is sufficient: every divergence this guards against
changes how many tests a file contributes.

Comparison hazards checked on this tree before trusting equality (re-check if a
mismatch ever looks legitimate rather than real):
  * no module uses the ``load_tests`` protocol;
  * ``subTest`` expands at run time and does not change collected counts;
  * every ``class Test*`` that does not literally spell ``unittest.TestCase``
    inherits it through a base, so both backends see it.

Run: bash tests/run_all_python_tests.sh
  or: python3 -m unittest tests.test_collection_parity
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Explicit, commented, and empty by design — the same policy as
# ZERO_COLLECTION_ALLOWLIST in tests/test_no_zero_collection.py. A file belongs
# here ONLY if the two backends legitimately disagree about its collected count
# for a documented backend-semantic reason, never to silence a real divergence.
# Every entry needs a one-line justification.
PARITY_ALLOWLIST: frozenset[str] = frozenset()

# Runs in a subprocess (argv[1]=tests_dir, argv[2]=result_path). Counts, per
# tests/test_*.py file, how many tests `unittest discover` reaches from it —
# discovering each file on its own so a test is credited to the file it is
# reachable from, not to the module where its TestCase class is defined.
# Result goes to the result FILE, never stdout, so an import-time banner in a
# discovered module cannot corrupt the protocol.
_UNITTEST_PROBE_SRC = r'''
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
    for path in sorted(glob.glob(os.path.join(tests_dir, "test_*.py"))):
        basename = os.path.basename(path)
        suite = loader.discover(start_dir=tests_dir, pattern=basename)
        collected = 0
        for test in _walk(suite):
            # An unimportable module surfaces as _FailedTest; that is a
            # breakage (test_no_zero_collection.py owns it), not a collected
            # test, and counting it would make parity compare noise.
            if not isinstance(test, unittest.loader._FailedTest):
                collected += 1
        counts[basename[:-3]] = collected
    with open(result_path, "w", encoding="utf-8") as handle:
        json.dump(counts, handle)


if __name__ == "__main__":
    main()
'''


def _probe_env() -> dict:
    """Environment shared by both backends, mirroring the real runner.

    Parity is only meaningful if both sides see the same interpreter state, and
    `run_all_python_tests.sh` scrubs PYTHONPATH (t1236) so each test file
    exercises its own sys.path bootstrap. Seeding it here would hide a wrong
    bootstrap from one backend and not the other.
    """
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def _unittest_counts(tests_dir: str | os.PathLike) -> dict[str, int]:
    handle, result_path = tempfile.mkstemp(prefix="parity_unittest_", suffix=".json")
    os.close(handle)
    try:
        proc = subprocess.run(
            [sys.executable, "-c", _UNITTEST_PROBE_SRC, str(tests_dir), result_path],
            capture_output=True, text=True, env=_probe_env(),
        )
        if proc.returncode != 0:
            raise AssertionError(
                "unittest probe exited %d\n--- stdout ---\n%s\n--- stderr ---\n%s"
                % (proc.returncode, proc.stdout, proc.stderr)
            )
        with open(result_path, encoding="utf-8") as fh:
            return json.load(fh)
    finally:
        try:
            os.unlink(result_path)
        except OSError:
            pass


def _pytest_counts(tests_dir: str | os.PathLike) -> tuple[dict[str, int], list[str]]:
    """Per-file collected counts under pytest, plus files that errored.

    One `--collect-only` invocation over the whole directory rather than one per
    file: 177 pytest startups would cost minutes, and the node ids already carry
    the file each test belongs to.
    """
    files = sorted(glob.glob(os.path.join(str(tests_dir), "test_*.py")))
    counts = {os.path.basename(p)[:-3]: 0 for p in files}
    if not files:
        return counts, []

    proc = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *files],
        capture_output=True, text=True, cwd=str(tests_dir), env=_probe_env(),
    )
    errored: list[str] = []
    for line in proc.stdout.splitlines():
        line = line.strip()
        if "::" in line and not line.startswith("ERROR"):
            stem = os.path.basename(line.split("::", 1)[0])
            if stem.endswith(".py"):
                stem = stem[:-3]
            if stem in counts:
                counts[stem] += 1
        elif line.startswith("ERROR "):
            stem = os.path.basename(line.split(None, 1)[1].split("::", 1)[0])
            if stem.endswith(".py"):
                stem = stem[:-3]
            errored.append(stem)
    return counts, sorted(set(errored))


def _mismatches(tests_dir: str | os.PathLike) -> tuple[list[str], list[str]]:
    """(mismatch descriptions, pytest collection-error stems) for a tests dir."""
    u = _unittest_counts(tests_dir)
    p, errored = _pytest_counts(tests_dir)
    out = []
    for stem in sorted(set(u) | set(p)):
        if stem in PARITY_ALLOWLIST:
            continue
        un, pn = u.get(stem, 0), p.get(stem, 0)
        if un != pn:
            out.append(f"{stem}: unittest={un} pytest={pn}")
    return out, errored


_HAVE_PYTEST = True
try:  # pragma: no cover - trivial availability probe
    import pytest as _pytest_mod  # noqa: F401
except ImportError:
    _HAVE_PYTEST = False


@unittest.skipUnless(
    _HAVE_PYTEST,
    "pytest not installed — install the dev tier with `ait setup --with-dev`",
)
class CollectionParityTests(unittest.TestCase):
    """The live tree: every test file contributes the same count to both backends."""

    def test_backends_collect_the_same_per_file_counts(self) -> None:
        mismatch, errored = _mismatches(REPO_ROOT / "tests")
        self.assertEqual(
            mismatch, [],
            "These tests/test_*.py files are collected differently by the two "
            "backends of run_all_python_tests.sh: %s. The usual cause is a "
            "module-level `def test_*` (pytest collects it, unittest does not) "
            "— rename it to `_check_*` and call it from the module's main(). "
            "Only add a stem to PARITY_ALLOWLIST with a written justification."
            % mismatch,
        )
        self.assertEqual(
            errored, [],
            "These tests/test_*.py files ERROR during pytest collection (they "
            "run under unittest today, so the failure is invisible on the "
            "default backend): %s. A module-level `def test_x(arg)` is read by "
            "pytest as a request for a fixture named `arg`." % errored,
        )


class ParityOracleFalsifiabilityTests(unittest.TestCase):
    """Negative control: prove the comparison detects the defect it guards.

    A parity check that could not flag the exact shape t1354_3 just removed
    would be decorative. Runs against a synthetic tests dir so no real file is
    ever mutated to demonstrate a guard.
    """

    @unittest.skipUnless(_HAVE_PYTEST, "pytest not installed")
    def test_oracle_flags_a_bare_module_level_test_function(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tdir = os.path.join(tmp, "tests")
            os.makedirs(tdir)

            # Baseline: a plain TestCase. Both backends collect exactly 1.
            Path(tdir, "test_good.py").write_text(
                "import unittest\n"
                "class Good(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            # The defect: a module-level `def test_*` ALONGSIDE a TestCase.
            # unittest sees 1, pytest sees 2. Mirrors the t1211 script-style
            # shape, tally included, so the bare function passes vacuously
            # rather than failing — which is why a count check is needed and a
            # green run is not evidence.
            Path(tdir, "test_bare.py").write_text(
                "import unittest\n"
                "FAIL = 0\n"
                "def assert_eq(desc, expected, actual):\n"
                "    global FAIL\n"
                "    if expected != actual:\n"
                "        FAIL += 1\n"
                "def test_bare_driver():\n"
                "    assert_eq('never raises', 1, 1)\n"
                "def main():\n"
                "    test_bare_driver()\n"
                "    return 1 if FAIL else 0\n"
                "class ScriptChecksTest(unittest.TestCase):\n"
                "    def test_all_checks_pass(self):\n"
                "        self.assertEqual(main(), 0)\n",
                encoding="utf-8",
            )

            mismatch, errored = _mismatches(tdir)

        joined = " | ".join(mismatch)
        # Flagged BY NAME — not merely "something was flagged".
        self.assertIn("test_bare", joined, f"oracle missed the defect: {mismatch}")
        self.assertIn("unittest=1 pytest=2", joined,
                      f"oracle reported the wrong counts: {mismatch}")
        # And the clean file is NOT flagged, so the control is not passing for
        # the trivial reason that everything is flagged.
        self.assertNotIn("test_good", joined,
                         f"oracle false-positived on a clean file: {mismatch}")
        self.assertEqual(errored, [])

    @unittest.skipUnless(_HAVE_PYTEST, "pytest not installed")
    def test_oracle_flags_a_pytest_collection_error(self) -> None:
        """Proves the `errored` channel is not an unfalsifiable branch.

        Measured on pytest 8.4.2, correcting the t1354/t1354_3 task text: a
        module-level ``def test_x(arg)`` does **not** error at collection. It is
        collected fine (``--collect-only`` exits 0 listing it) and errors only at
        *run* time, when the fixture named ``arg`` cannot be resolved. That shape
        therefore shows up here as a COUNT mismatch — the control above — not on
        this channel. A genuine import-time failure is what pytest reports as
        ``ERROR <file>`` during collection, so that is what this control uses.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = os.path.join(tmp, "tests")
            os.makedirs(tdir)
            Path(tdir, "test_importerr.py").write_text(
                "import definitely_not_a_module_zzz  # noqa\n"
                "import unittest\n"
                "class W(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            _, errored = _mismatches(tdir)

        self.assertIn("test_importerr", errored,
                      f"oracle missed the collection error: {errored}")

    @unittest.skipUnless(_HAVE_PYTEST, "pytest not installed")
    def test_fixture_arg_shape_is_caught_as_a_count_mismatch(self) -> None:
        """Pin the corrected mechanism for the two functions t1354_3 renamed.

        `tests/test_stats_multistage.py:132,:164` carried
        ``def test_collect_inflight(tmp: Path)``. Keeping this control means a
        reintroduction is caught by name, and documents that the guard covering
        it is the count comparison rather than the error channel.
        """
        with tempfile.TemporaryDirectory() as tmp:
            tdir = os.path.join(tmp, "tests")
            os.makedirs(tdir)
            Path(tdir, "test_fixturearg.py").write_text(
                "import unittest\n"
                "def test_needs_a_fixture(tmp):\n"
                "    pass\n"
                "class Wrapper(unittest.TestCase):\n"
                "    def test_ok(self):\n"
                "        pass\n",
                encoding="utf-8",
            )
            mismatch, errored = _mismatches(tdir)

        joined = " | ".join(mismatch)
        self.assertIn("test_fixturearg", joined,
                      f"oracle missed the fixture-arg shape: {mismatch}")
        self.assertIn("unittest=1 pytest=2", joined,
                      f"oracle reported the wrong counts: {mismatch}")
        self.assertEqual(errored, [], "fixture-arg shape must NOT be a collect error")


if __name__ == "__main__":
    unittest.main()
