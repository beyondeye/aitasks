"""Structure guard for the engine release wiring (t1852_3).

A release without the ait-testmap assets breaks every `ait setup` that
fetches the engine, and nothing but a real `v*` tag exercises release.yml.
These assertions pin the wiring statically:

- release.yml: the `goengines` job builds and uploads the assets, `release`
  needs it, downloads them and attaches them in BOTH gh-release steps, the
  VERSION guard still runs first, and `packaging` is unchanged.
- goengines-check.yml: it triggers on every file these guards protect and
  runs them (the annot conformance corpus sync guard included, with the t1954
  research corpus among the trigger paths, and the stubbed dashcheck.sh tests,
  t2154), and only its bench job is advisory.
- both: the hang-guard preflight (goengines/ci/preflight.sh) runs alone before
  `go test ./...`, and the suite runs only when it passes (t1998); and the
  pinned pytest the pytest adapter's real-tool tests require is installed
  before the suite, under the suite's own condition (t1854_9).
- the two modes keyed on goengines/EXPORT.txt (t2138): legacy work is skipped
  only on a positive `export` answer from goengines_integrity.sh mode (in
  release.yml the preflight and suite carry exactly LEGACY_STEP_IF, in
  goengines-check.yml check/bench carry exactly LEGACY_JOB_IF), the
  export-integrity job and the release integrity step are never skippable or
  advisory, the drift report is never blocking, and every sums file is
  verified, whatever the number of executables.

AIT_WORKFLOWS_DIR overrides the workflow directory (negative controls run
against a scratch copy, never the real files).
"""

from __future__ import annotations

import os
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
WORKFLOWS = Path(os.environ.get("AIT_WORKFLOWS_DIR", REPO / ".github" / "workflows"))

CHECK_PATHS = [
    "goengines/**",
    ".github/workflows/goengines-check.yml",
    ".github/workflows/release.yml",
    "tests/test_goengines_build.sh",
    "tests/test_goengines_benchci.sh",
    "tests/test_goengines_dashcheck.sh",
    "tests/test_release_workflow_goengines.py",
    "aidocs/testing_engine/t1954_parser_research/corpus/**",
    "tests/test_annot_conformance_corpus_sync.sh",
    ".github/scripts/**",
    "tests/test_goengines_export_integrity.sh",
]

INTEGRITY = ".github/scripts/goengines_integrity.sh"
# Fail-closed: legacy work is skipped only when the mode is positively
# `export`; an empty output (a failed detection) runs it.
LEGACY_STEP_IF = "steps.mode.outputs.mode != 'export'"
LEGACY_JOB_IF = "${{ !cancelled() && needs.mode.outputs.mode != 'export' }}"
EXPORT_STEP_IF = "steps.mode.outputs.mode == 'export'"
# The pytest adapter's supported versions (G10), pinned for its real-tool tests.
PYTEST_PIN = "pytest==8.4.2"
XDIST_PIN = "pytest-xdist==3.8.0"
# Every per-executable sums file, failing when there is none.
SUMS_LOOP = 'for s in "${sums[@]}"; do sha256sum -c "$s"; done'


def load(name: str) -> dict:
    with open(WORKFLOWS / name, encoding="utf-8") as f:
        return yaml.safe_load(f)


def triggers(wf: dict) -> dict:
    # YAML 1.1 reads the bare key `on` as the boolean True.
    return wf.get("on", wf.get(True))


def uses(step: dict, action: str) -> bool:
    return str(step.get("uses", "")).split("@")[0] == action


def needs(job: dict) -> list:
    n = job.get("needs", [])
    return [n] if isinstance(n, str) else list(n)


def assert_preflight_precedes_suite(tc: unittest.TestCase, steps: list, gate=None) -> None:
    # Inside `go test ./...` the runner package's hang-guard tripwire runs in
    # file order, after tests that could already hang, and its failure does not
    # stop them — so it runs alone first, and a failure ends the job.
    #
    # gate=None: neither step may carry an `if` (the job itself is gated).
    # gate=LEGACY_STEP_IF: both carry exactly that condition, decided by an
    # ungated mode step that runs before them — so the only way to skip them
    # is a positive export-mode answer.
    runs = [str(s.get("run", "")) for s in steps]
    pre = [i for i, r in enumerate(runs) if "./ci/preflight.sh" in r]
    suite = [i for i, r in enumerate(runs) if "go test ./..." in r]
    tc.assertEqual(len(pre), 1, "exactly one step runs ./ci/preflight.sh")
    tc.assertTrue(suite, "no step runs go test ./...")
    tc.assertLess(pre[0], min(suite), "the preflight must run before the suite")
    tc.assertNotIn("continue-on-error", steps[pre[0]], "a failing preflight must end the job")
    if gate is None:
        tc.assertNotIn("if", steps[pre[0]], "the preflight must not be skippable")
        tc.assertNotIn("if", steps[min(suite)], "the suite must not run after a failed preflight")
        return
    tc.assertEqual(steps[pre[0]].get("if"), gate, "the preflight is skipped only in export mode")
    tc.assertEqual(steps[min(suite)].get("if"), gate,
                   "the suite carries the preflight's condition and nothing that outlives its failure")
    mode = [i for i, s in enumerate(steps) if s.get("id") == "mode"]
    tc.assertEqual(len(mode), 1, "exactly one step decides the mode")
    tc.assertLess(mode[0], pre[0], "the mode is decided before the preflight")
    tc.assertNotIn("if", steps[mode[0]], "the mode step must not be skippable")
    tc.assertNotIn("continue-on-error", steps[mode[0]], "a failed mode detection must end the job")
    tc.assertIn(f"{INTEGRITY} mode", str(steps[mode[0]].get("run", "")))


def assert_pytest_pinned_before_suite(tc: unittest.TestCase, steps: list, gate=None) -> None:
    # AIT_TESTMAP_REQUIRE_REAL_TOOLS=1 turns a missing pytest into a failing
    # suite: the pinned install and its python run before it, skipped only
    # when the suite itself is.
    runs = [str(s.get("run", "")) for s in steps]
    suite = [i for i, r in enumerate(runs) if "go test ./..." in r]
    pins = [i for i, r in enumerate(runs) if "pip install" in r and PYTEST_PIN in r]
    py = [i for i, s in enumerate(steps) if uses(s, "actions/setup-python")]
    tc.assertTrue(suite, "no step runs go test ./...")
    tc.assertEqual(len(pins), 1, f"exactly one step installs {PYTEST_PIN}")
    tc.assertIn(XDIST_PIN, runs[pins[0]], f"{XDIST_PIN} is installed with it")
    tc.assertLess(pins[0], min(suite), "pytest must be installed before the suite")
    tc.assertTrue([i for i in py if i < pins[0]], "a python is set up before the pytest install")
    for i in [pins[0], max(i for i in py if i < pins[0])]:
        tc.assertEqual(steps[i].get("if"), gate, "skipped only when the suite is")
        tc.assertNotIn("continue-on-error", steps[i], "a failed install must end the job")


def step_running(tc: unittest.TestCase, steps: list, needle: str) -> tuple:
    hits = [(i, s) for i, s in enumerate(steps) if needle in str(s.get("run", ""))]
    tc.assertEqual(len(hits), 1, f"exactly one step runs {needle!r}")
    return hits[0]


def assert_integrity_steps(tc: unittest.TestCase, steps: list) -> tuple:
    # check is required (it no-ops in legacy mode by itself); drift never blocks.
    ci, check = step_running(tc, steps, f"{INTEGRITY} check")
    tc.assertNotIn("if", check, "the integrity check must not be skippable")
    tc.assertNotIn("continue-on-error", check, "a failing integrity check must fail the job")
    di, drift = step_running(tc, steps, f"{INTEGRITY} drift")
    tc.assertIs(drift.get("continue-on-error"), True, "the drift report is a warning, never a failure")
    tc.assertNotIn("if", drift)
    return ci, di


def assert_sums_loop(tc: unittest.TestCase, run: str) -> None:
    tc.assertIn("./build.sh all", run)
    tc.assertIn(SUMS_LOOP, run, "every executable's sums file is verified")
    tc.assertIn('[ -e "${sums[0]}" ] || {', run, "no sums file at all fails")
    tc.assertNotIn("ait-testmap_*_SHA256SUMS", run, "the check is not limited to one executable")


class ReleaseWorkflow(unittest.TestCase):
    def setUp(self):
        self.jobs = load("release.yml")["jobs"]

    def test_release_needs_plan_and_goengines(self):
        self.assertEqual(needs(self.jobs["release"]), ["plan", "goengines"])

    def test_goengines_job_builds_and_uploads(self):
        steps = self.jobs["goengines"]["steps"]
        runs = "\n".join(str(s.get("run", "")) for s in steps)
        self.assertIn("go vet ./...", runs)
        self.assertIn("go test ./...", runs)
        self.assertIn("./build.sh all", runs)
        up = [s for s in steps if uses(s, "actions/upload-artifact")]
        self.assertEqual(len(up), 1)
        self.assertEqual(up[0]["with"]["name"], "goengines-dist")
        self.assertEqual(up[0]["with"]["if-no-files-found"], "error")
        setup = [s for s in steps if uses(s, "actions/setup-go")]
        self.assertEqual(setup[0]["with"]["go-version-file"], "goengines/go.mod")

    def test_preflight_precedes_the_suite(self):
        assert_preflight_precedes_suite(self, self.jobs["goengines"]["steps"], gate=LEGACY_STEP_IF)

    def test_pytest_pinned_before_the_suite(self):
        assert_pytest_pinned_before_suite(self, self.jobs["goengines"]["steps"], gate=LEGACY_STEP_IF)

    def test_integrity_runs_before_the_build(self):
        steps = self.jobs["goengines"]["steps"]
        ci, di = assert_integrity_steps(self, steps)
        bi, build = step_running(self, steps, "./build.sh all")
        self.assertLess(ci, bi, "the integrity check runs before the assets are built")
        self.assertLess(di, bi)
        self.assertNotIn("if", build, "the assets are built in both modes")
        for s in (steps[ci], steps[di]):
            self.assertEqual(s.get("working-directory"), ".", "the script runs from the repository root")
        assert_sums_loop(self, str(build["run"]))
        self.assertNotIn("if", self.jobs["goengines"], "the release job itself is never skipped")

    def test_release_downloads_the_assets(self):
        down = [s for s in self.jobs["release"]["steps"] if uses(s, "actions/download-artifact")]
        self.assertEqual(len(down), 1)
        self.assertEqual(down[0]["with"]["name"], "goengines-dist")
        self.assertEqual(down[0]["with"]["path"], "goengines/dist")

    def test_both_release_steps_attach_the_assets(self):
        steps = [s for s in self.jobs["release"]["steps"] if uses(s, "softprops/action-gh-release")]
        self.assertEqual(len(steps), 2)
        for s in steps:
            files = [f.strip() for f in s["with"]["files"].splitlines() if f.strip()]
            self.assertIn("goengines/dist/*", files, s.get("name"))
            self.assertIn("aitasks-${{ github.ref_name }}.tar.gz", files, s.get("name"))
            self.assertIn("packaging/shim/ait", files, s.get("name"))
            self.assertIs(s["with"].get("fail_on_unmatched_files"), True, s.get("name"))

    def test_version_guard_runs_before_publishing(self):
        steps = self.jobs["release"]["steps"]
        names = [s.get("name", "") for s in steps]
        self.assertIn("Verify VERSION file matches tag", names)
        guard = names.index("Verify VERSION file matches tag")
        first_publish = min(i for i, s in enumerate(steps) if uses(s, "softprops/action-gh-release"))
        self.assertLess(guard, first_publish)

    def test_packaging_unchanged(self):
        self.assertEqual(needs(self.jobs["packaging"]), ["plan", "release"])
        self.assertEqual(self.jobs["packaging"]["uses"], "./.github/workflows/release-packaging.yml")


class GoenginesCheckWorkflow(unittest.TestCase):
    def setUp(self):
        self.wf = load("goengines-check.yml")
        self.jobs = self.wf["jobs"]

    def test_triggers_on_everything_the_guards_protect(self):
        on = triggers(self.wf)
        for event in ("push", "pull_request"):
            self.assertEqual(on[event]["paths"], CHECK_PATHS, event)
        self.assertIn("seed_regression", on["workflow_dispatch"]["inputs"])

    def test_check_job_runs_the_guards(self):
        runs = "\n".join(str(s.get("run", "")) for s in self.jobs["check"]["steps"])
        for guard in ("tests/test_release_workflow_goengines.py",
                      "tests/test_goengines_build.sh",
                      "tests/test_goengines_benchci.sh",
                      "tests/test_goengines_dashcheck.sh",
                      "tests/test_annot_conformance_corpus_sync.sh"):
            self.assertIn(guard, runs)
        self.assertIn("tests/test_goengines_export_integrity.sh", runs)
        self.assertIn("gofmt", runs)
        _, build = step_running(self, self.jobs["check"]["steps"], "./build.sh all")
        assert_sums_loop(self, str(build["run"]))

    def test_preflight_precedes_the_suite(self):
        assert_preflight_precedes_suite(self, self.jobs["check"]["steps"])

    def test_pytest_pinned_before_the_suite(self):
        assert_pytest_pinned_before_suite(self, self.jobs["check"]["steps"])

    def test_mode_job_decides_the_mode(self):
        job = self.jobs["mode"]
        self.assertEqual(job["outputs"]["mode"], "${{ steps.mode.outputs.mode }}")
        self.assertNotIn("if", job)
        mode = [s for s in job["steps"] if s.get("id") == "mode"]
        self.assertEqual(len(mode), 1)
        self.assertIn(f"{INTEGRITY} mode", str(mode[0]["run"]))
        self.assertNotIn("if", mode[0])

    def test_legacy_jobs_skip_only_on_positive_export(self):
        for name in ("check", "bench"):
            job = self.jobs[name]
            self.assertEqual(needs(job), ["mode"], name)
            self.assertEqual(job.get("if"), LEGACY_JOB_IF, name)

    def test_export_integrity_job(self):
        job = self.jobs["export-integrity"]
        self.assertNotIn("if", job, "export-integrity always runs")
        self.assertNotIn("continue-on-error", job, "export-integrity is never advisory")
        self.assertNotIn("needs", job)
        steps = job["steps"]
        mi = [i for i, s in enumerate(steps) if s.get("id") == "mode"]
        self.assertEqual(len(mi), 1)
        self.assertNotIn("if", steps[mi[0]])
        ci, _ = assert_integrity_steps(self, steps)
        self.assertLess(mi[0], ci)
        for guard in ("tests/test_release_workflow_goengines.py",
                      "tests/test_goengines_build.sh",
                      "tests/test_goengines_export_integrity.sh"):
            _, s = step_running(self, steps, guard)
            self.assertEqual(s.get("if"), EXPORT_STEP_IF, f"{guard} runs here in export mode only")
            self.assertNotIn("continue-on-error", s, guard)
        setup = [s for s in steps if uses(s, "actions/setup-go")]
        self.assertEqual(setup[0]["with"]["go-version-file"], "goengines/go.mod")

    def test_only_bench_is_advisory(self):
        self.assertIs(self.jobs["bench"].get("continue-on-error"), True)
        self.assertNotIn("continue-on-error", self.jobs["check"])
        self.assertNotIn("continue-on-error", self.jobs["export-integrity"])
        self.assertNotIn("continue-on-error", self.jobs["mode"])
        runs = "\n".join(str(s.get("run", "")) for s in self.jobs["bench"]["steps"])
        self.assertIn("go run ./internal/tools/benchgate -baseline", runs)
        self.assertNotIn("-partial", runs)
        self.assertIn("./ci/benchci.sh summary", runs)


class PreflightOrderControls(unittest.TestCase):
    """Negative controls for assert_preflight_precedes_suite: every way the
    suite could run without a passing preflight must be rejected."""

    PRE = {"name": "Hang-guard preflight", "run": "./ci/preflight.sh"}
    SUITE = {"name": "go test", "run": "go test ./..."}

    def test_the_wired_order_passes(self):
        assert_preflight_precedes_suite(self, [{"run": "go vet ./..."}, self.PRE, self.SUITE])

    def test_every_bypass_is_rejected(self):
        bypasses = {
            "no preflight": [self.SUITE],
            "preflight after the suite": [self.SUITE, self.PRE],
            "two preflights": [self.PRE, self.PRE, self.SUITE],
            "no suite": [self.PRE],
            "skipped preflight": [{**self.PRE, "if": "false"}, self.SUITE],
            "preflight failure tolerated": [{**self.PRE, "continue-on-error": True}, self.SUITE],
            "suite run after a failure": [self.PRE, {**self.SUITE, "if": "always()"}],
            "legacy gate where none is allowed": [{**self.PRE, "if": LEGACY_STEP_IF}, self.SUITE],
        }
        for name, steps in bypasses.items():
            with self.subTest(name), self.assertRaises(AssertionError):
                assert_preflight_precedes_suite(self, steps)

    MODE = {"name": "Detect goengines mode", "id": "mode", "run": f"{INTEGRITY} mode"}

    def gated(self, step, cond=LEGACY_STEP_IF):
        return {**step, "if": cond}

    def test_the_gated_order_passes(self):
        assert_preflight_precedes_suite(
            self, [self.MODE, {"run": "go vet ./..."}, self.gated(self.PRE), self.gated(self.SUITE)],
            gate=LEGACY_STEP_IF)

    def test_every_gated_bypass_is_rejected(self):
        g = self.gated
        bypasses = {
            "ungated preflight": [self.MODE, self.PRE, g(self.SUITE)],
            "preflight under another condition": [self.MODE, g(self.PRE, "false"), g(self.SUITE)],
            "not fail-closed (== 'legacy')": [self.MODE, g(self.PRE, "steps.mode.outputs.mode == 'legacy'"),
                                              g(self.SUITE, "steps.mode.outputs.mode == 'legacy'")],
            "suite gated differently": [self.MODE, g(self.PRE), g(self.SUITE, "always()")],
            "suite ungated": [self.MODE, g(self.PRE), self.SUITE],
            "no mode step": [g(self.PRE), g(self.SUITE)],
            "mode decided after the preflight": [g(self.PRE), self.MODE, g(self.SUITE)],
            "skippable mode step": [{**self.MODE, "if": "false"}, g(self.PRE), g(self.SUITE)],
            "tolerated mode failure": [{**self.MODE, "continue-on-error": True}, g(self.PRE), g(self.SUITE)],
            "mode step runs something else": [{**self.MODE, "run": "echo mode=export"}, g(self.PRE), g(self.SUITE)],
            "preflight failure tolerated": [self.MODE, {**g(self.PRE), "continue-on-error": True}, g(self.SUITE)],
        }
        for name, steps in bypasses.items():
            with self.subTest(name), self.assertRaises(AssertionError):
                assert_preflight_precedes_suite(self, steps, gate=LEGACY_STEP_IF)


class PytestPinControls(unittest.TestCase):
    """Negative controls for assert_pytest_pinned_before_suite."""

    PY = {"uses": "actions/setup-python@v5"}
    PIN = {"run": f"python -m pip install {PYTEST_PIN} {XDIST_PIN}"}
    SUITE = {"run": "go test ./..."}

    def test_the_wired_order_passes(self):
        assert_pytest_pinned_before_suite(self, [self.PY, self.PIN, self.SUITE])
        g = {"if": LEGACY_STEP_IF}
        assert_pytest_pinned_before_suite(self, [{**self.PY, **g}, {**self.PIN, **g}, {**self.SUITE, **g}], gate=LEGACY_STEP_IF)

    def test_every_gap_is_rejected(self):
        gaps = {
            "no install": [self.PY, self.SUITE],
            "install after the suite": [self.PY, self.SUITE, self.PIN],
            "unpinned": [self.PY, {"run": "python -m pip install pytest pytest-xdist"}, self.SUITE],
            "no xdist": [self.PY, {"run": f"python -m pip install {PYTEST_PIN}"}, self.SUITE],
            "no python before it": [self.PIN, self.PY, self.SUITE],
            "skippable install": [self.PY, {**self.PIN, "if": "false"}, self.SUITE],
            "tolerated install failure": [self.PY, {**self.PIN, "continue-on-error": True}, self.SUITE],
            "skippable python": [{**self.PY, "if": "false"}, self.PIN, self.SUITE],
            "two installs": [self.PY, self.PIN, self.PIN, self.SUITE],
        }
        for name, steps in gaps.items():
            with self.subTest(name), self.assertRaises(AssertionError):
                assert_pytest_pinned_before_suite(self, steps)


class IntegrityStepControls(unittest.TestCase):
    """Negative controls for assert_integrity_steps and assert_sums_loop."""

    CHECK = {"run": f"{INTEGRITY} check"}
    DRIFT = {"run": f"{INTEGRITY} drift", "continue-on-error": True}

    def test_the_wired_steps_pass(self):
        assert_integrity_steps(self, [self.CHECK, self.DRIFT])

    def test_every_integrity_bypass_is_rejected(self):
        bypasses = {
            "no check": [self.DRIFT],
            "skippable check": [{**self.CHECK, "if": "false"}, self.DRIFT],
            "advisory check": [{**self.CHECK, "continue-on-error": True}, self.DRIFT],
            "blocking drift": [self.CHECK, {"run": f"{INTEGRITY} drift"}],
            "no drift": [self.CHECK],
        }
        for name, steps in bypasses.items():
            with self.subTest(name), self.assertRaises(AssertionError):
                assert_integrity_steps(self, steps)

    def test_a_single_executable_sums_check_is_rejected(self):
        with self.assertRaises(AssertionError):
            assert_sums_loop(self, "./build.sh all\ncd dist\nsha256sum -c ait-testmap_*_SHA256SUMS.txt")


if __name__ == "__main__":
    unittest.main()
