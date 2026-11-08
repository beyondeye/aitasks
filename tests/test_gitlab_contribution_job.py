"""Behaviour of the GitLab contribution-check CI job's scheduled scan (t2241).

GitLab silently drops labels supplied by authors who are not project members,
so the scheduled scan must find contribution issues by the `contribution` label
OR the `<!-- aitask-contribute-metadata` block, across every page of recently
updated open issues — and only those, because the check script posts a
"no fingerprint" comment on any issue it is pointed at.

The job runs on `alpine:latest`, whose `date` is BusyBox: it has no relative
time input ("6 hours ago") and no `-v`. The script is run here with a `date`
stub that models exactly that, under POSIX shells, so a host with GNU date
cannot hide a dependency on it. The real Alpine image is covered by live
verification, not here.
"""

from __future__ import annotations

import datetime as dt
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = REPO_ROOT / ".aitask-scripts" / "ci_templates" / "gitlab" / "contribution-check-job.yml"
STUB_LIB = REPO_ROOT / "tests" / "lib" / "glab_contribution_stub.sh"
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
CONTRIBUTIONS = ["101", "100", "15", "12"]

# BusyBox date (coreutils/date.c): TIME formats are @seconds_since_1970,
# hh:mm[:ss], [YYYY.]MM.DD-hh:mm[:ss], YYYY-MM-DD hh:mm[:ss],
# [[[[[YY]YY]MM]DD]hh]mm[.ss]; there is no -v option.
BUSYBOX_DATE = """#!/usr/bin/env bash
printf '%s\\n' "$*" >> '{log}'
prev=""
for a in "$@"; do
    case "$a" in -v*) echo "date: invalid option -- 'v'" >&2; exit 1 ;; esac
    if [ "$prev" = "-d" ]; then
        case "$a" in
            @[0-9]*) ;;
            *) echo "date: invalid date '$a'" >&2; exit 1 ;;
        esac
    fi
    prev="$a"
done
exec '{real}' "$@"
"""

LEGACY_CUTOFF = (
    "SINCE=$(date -u -d '6 hours ago' '+%Y-%m-%dT%H:%M:%SZ' 2>/dev/null \\\n"
    "  || date -u -v-6H '+%Y-%m-%dT%H:%M:%SZ')\n"
    'printf "%s" "$SINCE"\n'
)


def _job_script() -> str:
    with TEMPLATE.open(encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
    return doc["contribution-check"]["script"][0]


def _shells() -> list[tuple[str, list[str]]]:
    shells = [("sh", ["sh"]), ("bash --posix", ["bash", "--posix"])]
    if shutil.which("dash"):
        shells.append(("dash", ["dash"]))
    return shells


class GitLabContributionJob(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t2241_job_"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.stub = self.tmp / "stub"
        subprocess.run(
            ["bash", "-c", '. "$1"; glab_contribution_stub_install "$2"', "_", str(STUB_LIB), str(self.stub)],
            check=True,
        )
        real_date = shutil.which("date")
        self.assertIsNotNone(real_date)
        self.date_log = self.tmp / "date_calls"
        self.date_log.touch()
        date_stub = self.stub / "bin" / "date"
        date_stub.write_text(BUSYBOX_DATE.format(log=self.date_log, real=real_date))
        date_stub.chmod(0o755)

        self.work = self.tmp / "work"
        (self.work / ".aitask-scripts").mkdir(parents=True)
        self.checked = self.tmp / "checked"
        self.checked.touch()
        fake = self.work / ".aitask-scripts" / "aitask_contribution_check.sh"
        fake.write_text(f"#!/usr/bin/env bash\nprintf '%s\\n' \"$1\" >> '{self.checked}'\n")
        fake.chmod(0o755)

    def _env(self, **extra: str) -> dict:
        env = {k: v for k, v in os.environ.items() if k != "ISSUE_IID"}
        env.update(
            PATH=f"{self.stub / 'bin'}:{env.get('PATH', '')}",
            GITLAB_TOKEN="test-token",
            CI_PROJECT_PATH="o/r",
            CI_API_V4_URL="https://gitlab.example/api/v4",
        )
        env.update(extra)
        return env

    def _run(self, argv: list[str], script: str, **extra: str) -> subprocess.CompletedProcess:
        for name in ("curl_calls", "glab_calls"):
            (self.stub / name).write_text("")
        self.checked.write_text("")
        self.date_log.write_text("")
        return subprocess.run(
            [*argv, "-c", script], cwd=self.work, env=self._env(**extra),
            capture_output=True, text=True, timeout=60,
        )

    def _curl_calls(self) -> list[str]:
        return [l for l in (self.stub / "curl_calls").read_text().splitlines() if l]

    def test_scheduled_scan_checks_label_or_metadata_issues_only(self):
        script = _job_script()
        for name, argv in _shells():
            with self.subTest(shell=name):
                started = time.time()
                res = self._run(argv, script)
                self.assertEqual(res.returncode, 0, res.stderr)
                self.assertEqual(self.checked.read_text().split(), CONTRIBUTIONS)
                calls = self._curl_calls()
                self.assertGreaterEqual(len(calls), 2, "second page must be requested")
                self.assertTrue(any("page=2" in c for c in calls))
                for call in calls:
                    self.assertNotIn("labels=", call)
                    self.assertIn("state=opened", call)
                    m = re.search(r"updated_after=([^&]*)", call)
                    self.assertIsNotNone(m, call)
                    since = m.group(1)
                    self.assertRegex(since, ISO)
                    cutoff = dt.datetime.strptime(since, "%Y-%m-%dT%H:%M:%SZ").replace(
                        tzinfo=dt.timezone.utc).timestamp()
                    self.assertLessEqual(abs((started - cutoff) - 21600), 120, since)

    def test_cutoff_needs_no_gnu_or_bsd_date(self):
        res = self._run(["sh"], _job_script())
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.date_log.read_text(), "", "the job must not depend on date")

    def test_busybox_date_stub_rejects_the_legacy_cutoff(self):
        # Pre-fix control: the cutoff the job shipped with before t2241 yields
        # no usable value under BusyBox date semantics.
        res = self._run(["sh"], LEGACY_CUTOFF)
        self.assertTrue(res.returncode != 0 or not ISO.match(res.stdout), res.stdout)
        res = self._run(["sh"], 'date -u -d "@0" "+%Y-%m-%dT%H:%M:%SZ"')
        self.assertEqual(res.stdout.strip(), "1970-01-01T00:00:00Z", "stub must still serve @epoch")

    def test_listing_failure_fails_the_job(self):
        res = self._run(["sh"], _job_script(), GLAB_STUB_CURL_FAIL_PAGE="2")
        self.assertNotEqual(res.returncode, 0)
        self.assertEqual(self.checked.read_text(), "")

    def test_repeated_page_fails_the_job_promptly(self):
        # A server or proxy that ignores 'page' keeps returning a full page 1;
        # the scan must stop on the repeat, not run until the CI timeout.
        res = self._run(["sh"], _job_script(), GLAB_STUB_CURL_REPEAT_PAGE="1")
        self.assertNotEqual(res.returncode, 0)
        self.assertIn("repeats page 1", res.stderr)
        self.assertEqual(len(self._curl_calls()), 2)
        self.assertEqual(self.checked.read_text(), "")

    def test_page_cap_is_bounded(self):
        script = _job_script()
        self.assertIn("MAX_PAGES=1000", script)
        self.assertIn('if [ "$PAGE" -ge "$MAX_PAGES" ]; then', script)

    def test_trigger_mode_unchanged(self):
        res = self._run(["sh"], _job_script(), ISSUE_IID="42")
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(self.checked.read_text().split(), ["42"])
        self.assertEqual(self._curl_calls(), [])

    def test_predicate_structure(self):
        script = _job_script()
        self.assertNotIn("labels=contribution", script)
        self.assertIn('any(.labels[]?; . == "contribution")', script)
        self.assertIn('contains("<!-- aitask-contribute-metadata")', script)


if __name__ == "__main__":
    unittest.main()
