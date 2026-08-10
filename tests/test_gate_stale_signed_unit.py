"""Unit tests for the code-stale signature classifier and its digest channel.

``gate_ledger.stale_signed_gates`` landed in t1409 but had **no direct unit
test** anywhere in ``tests/`` — it was only exercised end-to-end through
``gates run`` / ``archive-ready``. t1416 made it the shared seam behind four more
surfaces, so its contract is pinned here directly.

Two things are asserted that an end-to-end test cannot see:

* **The four-state digest channel** (``_resolve_digest``). ``_COMPUTE_DIGEST``,
  a callable, a ``str`` and ``None`` are four *different* answers, and the branch
  order is load-bearing: ``None`` means "unverifiable, accept" and must never be
  re-read as "compute one". ``callable(None)`` is ``False``, so a mis-ordered
  check would silently turn a real answer into a subprocess.
* **Laziness.** The no-git pre-filter must run *before* the digest is resolved,
  so a provider is invoked **zero** times when no stamped witness exists and
  **once** — never once per gate — when one does. This is what makes the
  per-task surfaces (board refresh, ``ait ls``) affordable.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / ".aitask-scripts"
sys.path.insert(0, str(SCRIPTS_DIR / "lib"))

import gate_ledger as gl  # noqa: E402


def _run(name: str, status: str = "pass", gate_type: str = "human") -> gl.GateRun:
    return gl.GateRun(name=name, icon="✅",
                      fields={"run": "2026-01-01T00:00:00Z", "status": status,
                              "attempt": "1", "type": gate_type})


class StaleSignedGatesTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "sig").mkdir()
        self.registry = {
            "review": {"type": "human", "blocks_dependents": True,
                       "signal_target": str(self.root / "sig/<task-id>-<gate>.signed")},
            "build": {"type": "machine"},
        }
        self.state = {"review": _run("review"), "build": _run("build", gate_type="machine")}
        self.active = ["review", "build"]

    def _sign(self, task_id: str, digest: str | None) -> Path:
        p = self.root / "sig" / f"t{task_id}-review.signed"
        body = "signer=tester\n" + (f"code_digest={digest}\n" if digest else "")
        p.write_text(body, encoding="utf-8")
        return p

    # --- the classifier itself --------------------------------------------

    def test_stamped_mismatch_is_stale(self):
        self._sign("1", "aaaaaaaaaaaaaaaa")
        self.assertEqual(
            gl.stale_signed_gates(self.active, self.registry, self.state, "1",
                                  "bbbbbbbbbbbbbbbb"),
            ["review"])

    def test_stamped_match_is_fresh(self):
        self._sign("1", "aaaaaaaaaaaaaaaa")
        self.assertEqual(
            gl.stale_signed_gates(self.active, self.registry, self.state, "1",
                                  "aaaaaaaaaaaaaaaa"),
            [])

    def test_absent_witness_is_never_stale(self):
        # The ATTENDED lane: a signal_target is configured but the pass came from
        # the interactive approval, so no witness was ever written.
        self.assertEqual(
            gl.stale_signed_gates(self.active, self.registry, self.state, "1",
                                  "bbbbbbbbbbbbbbbb"),
            [])

    def test_unstamped_witness_is_never_stale(self):
        self._sign("1", None)
        self.assertEqual(
            gl.stale_signed_gates(self.active, self.registry, self.state, "1",
                                  "bbbbbbbbbbbbbbbb"),
            [])

    def test_machine_gate_is_never_stale(self):
        # Only `type: human` gates carry a code-bound signature. A machine gate
        # with a witness file sitting next to it must not be demoted.
        (self.root / "sig" / "t1-build.signed").write_text(
            "code_digest=aaaaaaaaaaaaaaaa\n", encoding="utf-8")
        self.assertEqual(
            gl.stale_signed_gates(["build"], self.registry, self.state, "1",
                                  "bbbbbbbbbbbbbbbb"),
            [])

    def test_unsatisfied_gate_is_never_stale(self):
        # A pending gate is already unsatisfied; demoting it again would be a
        # no-op at best and a double-report at worst.
        self._sign("1", "aaaaaaaaaaaaaaaa")
        pending = {"review": _run("review", status="pending")}
        self.assertEqual(
            gl.stale_signed_gates(self.active, self.registry, pending, "1",
                                  "bbbbbbbbbbbbbbbb"),
            [])

    # --- the four-state digest channel ------------------------------------

    def test_explicit_none_means_unverifiable_not_compute(self):
        """``None`` is a real answer (accept), NOT 'no digest supplied'."""
        self._sign("1", "aaaaaaaaaaaaaaaa")
        calls = {"n": 0}
        real = gl.code_digest

        def spy(*a, **k):
            calls["n"] += 1
            return real(*a, **k)

        gl.code_digest = spy
        self.addCleanup(setattr, gl, "code_digest", real)
        self.assertEqual(
            gl.stale_signed_gates(self.active, self.registry, self.state, "1", None),
            [])
        self.assertEqual(calls["n"], 0,
                         "an explicit None must not fall through to computing a digest")

    def test_string_digest_is_used_verbatim(self):
        self.assertEqual(gl._resolve_digest("cafecafecafecafe"), "cafecafecafecafe")

    def test_callable_is_invoked(self):
        self.assertEqual(gl._resolve_digest(lambda: "feedfeedfeedfeed"),
                         "feedfeedfeedfeed")

    def test_sentinel_computes(self):
        real = gl.code_digest
        gl.code_digest = lambda *a, **k: "computed"
        self.addCleanup(setattr, gl, "code_digest", real)
        self.assertEqual(gl._resolve_digest(gl._COMPUTE_DIGEST), "computed")

    def test_provider_exception_propagates(self):
        """_resolve_digest deliberately does NOT swallow.

        Making a provider total is the provider's job (the board's
        ``code_digest_for_refresh`` catches). Swallowing here would reinterpret a
        caller bug as 'unverifiable' and quietly accept an unvalidated signature.
        """
        def boom():
            raise RuntimeError("provider is broken")

        with self.assertRaises(RuntimeError):
            gl._resolve_digest(boom)

    # --- laziness ---------------------------------------------------------

    def test_provider_not_called_without_a_stamped_witness(self):
        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return "bbbbbbbbbbbbbbbb"

        gl.stale_signed_gates(self.active, self.registry, self.state, "1", provider)
        self.assertEqual(calls["n"], 0,
                         "the no-git pre-filter must short-circuit before the digest")

    def test_provider_called_once_not_per_gate(self):
        # Two human gates, both satisfied, both carrying a stamped witness: the
        # digest is resolved once for the whole call, not once per candidate.
        self.registry["merge"] = {
            "type": "human",
            "signal_target": str(self.root / "sig/<task-id>-<gate>.signed")}
        self.state["merge"] = _run("merge")
        self._sign("1", "aaaaaaaaaaaaaaaa")
        (self.root / "sig" / "t1-merge.signed").write_text(
            "code_digest=aaaaaaaaaaaaaaaa\n", encoding="utf-8")

        calls = {"n": 0}

        def provider():
            calls["n"] += 1
            return "bbbbbbbbbbbbbbbb"

        stale = gl.stale_signed_gates(["review", "merge"], self.registry,
                                      self.state, "1", provider)
        self.assertEqual(stale, ["review", "merge"])   # anti-vacuity: both fired
        self.assertEqual(calls["n"], 1)

    def test_returned_order_follows_the_supplied_gate_order(self):
        self.registry["merge"] = {
            "type": "human",
            "signal_target": str(self.root / "sig/<task-id>-<gate>.signed")}
        self.state["merge"] = _run("merge")
        self._sign("1", "aaaaaaaaaaaaaaaa")
        (self.root / "sig" / "t1-merge.signed").write_text(
            "code_digest=aaaaaaaaaaaaaaaa\n", encoding="utf-8")
        self.assertEqual(
            gl.stale_signed_gates(["merge", "review"], self.registry, self.state,
                                  "1", "bbbbbbbbbbbbbbbb"),
            ["merge", "review"])


class DemoteStaleSignedTest(unittest.TestCase):
    """The shared seam every re-validating surface goes through."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)
        (self.root / "sig").mkdir()
        self.registry = {
            "review": {"type": "human",
                       "signal_target": str(self.root / "sig/<task-id>-<gate>.signed")}}
        self.state = {"review": _run("review"), "build": _run("build", gate_type="machine")}

    def test_returns_the_original_object_when_nothing_is_stale(self):
        """Documented contract: the common path allocates nothing."""
        out, stale = gl.demote_stale_signed(["review"], self.registry, self.state,
                                            "1", "bbbbbbbbbbbbbbbb")
        self.assertIs(out, self.state)
        self.assertEqual(stale, [])

    def test_removes_only_the_stale_gate_and_does_not_mutate_the_input(self):
        (self.root / "sig" / "t1-review.signed").write_text(
            "code_digest=aaaaaaaaaaaaaaaa\n", encoding="utf-8")
        out, stale = gl.demote_stale_signed(["review"], self.registry, self.state,
                                            "1", "bbbbbbbbbbbbbbbb")
        self.assertEqual(stale, ["review"])
        self.assertNotIn("review", out)
        self.assertIn("build", out)
        # The caller's map is untouched — read_task_gate_state relies on this to
        # keep reporting the RAW ledger on `current` alongside `stale_signed`.
        self.assertIn("review", self.state)


class CompactSummaryStaleTest(unittest.TestCase):
    """A stale gate is counted as `stale`, never folded into the pass count."""

    def _state(self, stale_signed):
        return gl.TaskGateState(
            task_file="t.md", declared_gates=["review", "build"],
            runs=[], current={"review": _run("review"),
                              "build": _run("build", gate_type="machine")},
            status_text="", archive_decision="", archive_pending=[],
            dependents_decision="", dependents_pending=[], resume_point="",
            active_gates=["review", "build"], filtered_gates=[],
            stale_signed=stale_signed)

    def test_no_stale_reads_as_all_pass(self):
        self.assertEqual(gl.compact_gate_summary(self._state([])), "2/2 pass")

    def test_stale_is_split_out_of_the_pass_count(self):
        self.assertEqual(gl.compact_gate_summary(self._state(["review"])),
                         "1/2 pass, 1 stale")


if __name__ == "__main__":
    unittest.main()
