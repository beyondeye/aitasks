"""The candidate-provider contract (t1981_3), shared by the worker and t1981_2.

Fixtures: tests/fixtures/relation_candidates/ -- ``valid_*.json`` must pass,
``invalid_*`` must fail with the reason in ``expected_errors.json``.

**Reusable by the producer (t1981_2).** ``assert_conforms(json_text,
text_output=None)`` checks one provider answer: the exactly-one-object rule,
every field and the snapshot echoes, and -- when the text rendering is given --
that it carries the same provider, evidence, coverage and truncation
information. Set ``AIT_CANDIDATES_UNDER_TEST`` to a shell command printing a
``--json`` answer (and optionally ``AIT_CANDIDATES_UNDER_TEST_TEXT`` for the text
one) to run the same assertions against a real generator.

Run: python3 tests/test_relation_candidates_contract.py
"""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
import unittest
from pathlib import Path

TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(TESTS.parent / ".aitask-scripts" / "lib"))
sys.path.insert(0, str(TESTS))

import relation_candidates_contract as cc  # noqa: E402

FIX = TESTS / "fixtures" / "relation_candidates"
EXPECTED = json.loads((FIX / "expected_errors.json").read_text())


def assert_conforms(json_text: str, text_output: str = None) -> dict:
    """Raise AssertionError unless the answer conforms; return the parsed result."""
    try:
        obj = cc.validate(cc.parse_json_stdout(json_text))
    except cc.ContractError as exc:
        raise AssertionError(f"provider output violates the contract: {exc}") from None
    if text_output is not None:
        try:
            back = cc.parse_text(text_output)
        except cc.ContractError as exc:
            raise AssertionError(f"text rendering violates the contract: {exc}") from None
        if back != obj:
            raise AssertionError("text and JSON renderings carry different information")
    return obj


class ContractFixtures(unittest.TestCase):
    def test_valid_fixtures_pass_and_round_trip(self):
        valid = sorted(FIX.glob("valid_*.json"))
        self.assertGreaterEqual(len(valid), 4)
        for path in valid:
            with self.subTest(fixture=path.name):
                obj = assert_conforms(path.read_text())
                assert_conforms(path.read_text(), cc.to_text(obj))
                self.assertEqual(cc.parse_text(cc.to_text(obj)), obj)

    def test_invalid_fixtures_fail_with_their_reason(self):
        invalid = sorted(p for p in FIX.iterdir() if p.name.startswith("invalid_"))
        self.assertEqual({p.name for p in invalid}, set(EXPECTED))
        for path in invalid:
            with self.subTest(fixture=path.name):
                with self.assertRaises(cc.ContractError) as ctx:
                    cc.validate(cc.parse_json_stdout(path.read_text()))
                self.assertIn(EXPECTED[path.name], str(ctx.exception))

    def test_core_missing_is_never_zero_candidates(self):
        obj = json.loads((FIX / "valid_zero.json").read_text())
        obj["coverage"]["answered"] = ["mention_in", "mention_out"]
        with self.assertRaisesRegex(cc.ContractError, "core_missing:cites"):
            cc.validate(obj)

    def test_text_stream_without_end_is_rejected(self):
        obj = json.loads((FIX / "valid_truncated.json").read_text())
        text = cc.to_text(obj)
        cut = "\n".join(text.splitlines()[:-1]) + "\n"
        with self.assertRaisesRegex(cc.ContractError, "no END line"):
            cc.parse_text(cut)

    def test_text_carries_free_text_safely(self):
        obj = json.loads((FIX / "valid_full.json").read_text())
        obj["candidates"][0]["card"] = "a | b\nEND:candidates=0\nc"
        obj["candidates"][0]["evidence"][0]["detail"] = "x|y|z"
        self.assertEqual(cc.parse_text(cc.to_text(obj)), cc.validate(obj))

    def test_text_round_trip_of_awkward_optional_fields(self):
        """Optional evidence fields are encoded unambiguously in the text rendering."""
        base = json.loads((FIX / "valid_full.json").read_text())
        for section in ("plan | API contract", "line one\nline two", "-", "", '"quoted"', "|", "a|b|c",
                        "nel\u0085here", "ls\u2028here", "ps\u2029here", "vt\x0bff\x0cfs\x1c",
                        " leading and trailing \u2028 "):
            with self.subTest(section=section):
                obj = json.loads(json.dumps(base))
                obj["candidates"][0]["evidence"][0]["section"] = section
                obj["candidates"][0]["evidence"][1]["detail"] = section
                obj["candidates"][0]["card"] = section
                obj["provider"]["detail"] = section
                self.assertEqual(cc.parse_text(cc.to_text(obj)), cc.validate(obj))
        obj = json.loads(json.dumps(base))
        del obj["candidates"][0]["evidence"][0]["section"]
        del obj["candidates"][0]["evidence"][0]["line"]
        back = cc.parse_text(cc.to_text(obj))
        self.assertNotIn("section", back["candidates"][0]["evidence"][0])  # absence survives
        self.assertNotIn("line", back["candidates"][0]["evidence"][0])
        self.assertEqual(back, cc.validate(obj))

    def test_screening_digest_tracks_evidence_not_echoes(self):
        obj = json.loads((FIX / "valid_full.json").read_text())
        base = cc.screening_digest(obj)
        other = json.loads(json.dumps(obj))
        other["candidates"][0]["inputs"]["body_sha256"] = "9" * 64  # digests are not screening
        self.assertEqual(cc.screening_digest(other), base)
        other["candidates"][0]["evidence"].append({"source": "token", "detail": "new"})
        self.assertNotEqual(cc.screening_digest(other), base)

    def test_snapshot_manifest(self):
        good = cc.snapshot_manifest("/r", "aitasks#10", {"aitasks#10": "a" * 40})
        self.assertIs(cc.validate_snapshot(good), good)
        with self.assertRaises(cc.ContractError):
            cc.validate_snapshot(dict(good, stamps={"aitasks#10": "abc"}))


class WorkerConsumesEveryFixture(unittest.TestCase):
    """The worker's consumption of each fixture: records for valid, failed jobs for invalid."""

    def test_worker_outcome_per_fixture(self):
        import test_relations_worker as tw
        for path in sorted(FIX.iterdir()):
            if not (path.name.startswith(("valid_", "invalid_"))):
                continue
            with self.subTest(fixture=path.name):
                case = tw.WBase("run")
                case.setUp()
                try:
                    echo = case.tmp / "echo.sh"
                    # Echo the fixture with the source rewritten to the job's task
                    # and the digest echoes replaced by the real ones (validity is
                    # about shape; agreement is tested in test_relations_worker).
                    echo.write_text(_ECHO_PROVIDER.format(fixture=path, py=sys.executable,
                                                          lib=TESTS.parent / ".aitask-scripts" / "lib"))
                    echo.chmod(0o755)
                    os.environ["AIT_RELATIONS_CANDIDATES_CMD"] = str(echo)
                    case.agent("ok", relations=[], considered=[])
                    sp = case.run_job()
                    state = sp.job_state("10")
                    if path.name.startswith("valid_"):
                        self.assertIsNone(state, state)
                        self.assertTrue(case.record()["analysed"])
                    else:
                        self.assertTrue(state and state.startswith("failed("), state)
                        self.assertIsNone(case.record())
                finally:
                    case.tearDown()


_ECHO_PROVIDER = r'''#!/bin/sh
# Echo a fixture as a provider answer for the scratch repo: the source becomes
# the job's task, every full candidate becomes t11, and the digest echoes are
# the real ones. Truncated refs name tasks that do not exist, so the worker
# drops them; invalid fixtures keep the defect they were written to carry.
exec "{py}" - "$@" <<'PYEOF'
import json, os, sys
sys.path.insert(0, "{lib}")
import relations_store as rst
text = open("{fixture}").read()
try:
    obj = json.loads(text)
except ValueError:
    sys.stdout.write(text)
    sys.exit(0)
idx = rst.TaskIndex(os.getcwd())
def echo(tid):
    return {{"body_sha256": idx.body_digest(tid), "plan_sha256": idx.plan_digest(tid)}}
obj["source"] = "aitasks#10"
if "source_inputs" in obj:
    obj["source_inputs"] = echo("10")
for cand in obj.get("candidates", []):
    cand["ref"] = "aitasks#11"
    if "inputs" in cand:
        cand["inputs"] = echo("11")
print(json.dumps(obj))
PYEOF
'''


class ProducerUnderTest(unittest.TestCase):
    """Runs ``assert_conforms`` against a real generator when one is named."""

    def _run(self, var):
        cmd = os.environ.get(var)
        return subprocess.run(shlex.split(cmd), capture_output=True, text=True,
                              check=True).stdout if cmd else None

    def test_producer_under_test(self):
        if not os.environ.get("AIT_CANDIDATES_UNDER_TEST"):
            # Exercise the hook itself with a fixture-echo producer.
            fixture = FIX / "valid_truncated.json"
            os.environ["AIT_CANDIDATES_UNDER_TEST"] = f"cat {fixture}"
            obj = json.loads(fixture.read_text())
            try:
                assert_conforms(self._run("AIT_CANDIDATES_UNDER_TEST"), cc.to_text(obj))
            finally:
                del os.environ["AIT_CANDIDATES_UNDER_TEST"]
            return
        assert_conforms(self._run("AIT_CANDIDATES_UNDER_TEST"),
                        self._run("AIT_CANDIDATES_UNDER_TEST_TEXT"))


if __name__ == "__main__":
    unittest.main()
