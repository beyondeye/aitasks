"""Structure guard for the engine release wiring (t1852_3).

A release without the ait-testmap assets breaks every `ait setup` that
fetches the engine, and nothing but a real `v*` tag exercises release.yml.
These assertions pin the wiring statically:

- release.yml: the `goengines` job builds and uploads the assets, `release`
  needs it, downloads them and attaches them in BOTH gh-release steps, the
  VERSION guard still runs first, and `packaging` is unchanged.
- goengines-check.yml: it triggers on every file these guards protect and
  runs them, and only its bench job is advisory.

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
    "tests/test_release_workflow_goengines.py",
]


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
                      "tests/test_goengines_benchci.sh"):
            self.assertIn(guard, runs)
        self.assertIn("gofmt", runs)
        self.assertIn("./build.sh all", runs)

    def test_only_bench_is_advisory(self):
        self.assertIs(self.jobs["bench"].get("continue-on-error"), True)
        self.assertNotIn("continue-on-error", self.jobs["check"])
        runs = "\n".join(str(s.get("run", "")) for s in self.jobs["bench"]["steps"])
        self.assertIn("go run ./internal/tools/benchgate -baseline", runs)
        self.assertNotIn("-partial", runs)
        self.assertIn("./ci/benchci.sh summary", runs)


if __name__ == "__main__":
    unittest.main()
