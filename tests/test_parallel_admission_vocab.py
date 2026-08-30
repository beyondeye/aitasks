"""Vocabulary exhaustiveness guard for the parallel-admission checker (t1569_3).

Inline post-phase risk mitigation `vocabulary_exhaustiveness_guard`.

Every assertion here is DRIVEN FROM `parallel_admission_vocab`'s tables. This
file deliberately contains no second copy of the vocabulary -- a duplicated list
is exactly what the mitigation exists to prevent, because it can only ever go
stale silently. Where a value is imported from an upstream module, the drift
guard at the bottom pins it against that module rather than restating it.
"""

import ast
import os
import re
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.dirname(TESTS_DIR)
LIB_DIR = os.path.join(REPO_ROOT, ".aitask-scripts", "lib")
sys.path.insert(0, LIB_DIR)

import parallel_admission as pa            # noqa: E402
import parallel_admission_vocab as vocab   # noqa: E402

CORE_SRC = os.path.join(LIB_DIR, "parallel_admission.py")

_SAMPLE = {vocab.PATH: "some/path.py", vocab.DAYS: "7d"}


def _valid_param(shape):
    if shape is vocab.NONE:
        return None
    if isinstance(shape, tuple):
        return shape[0]
    return _SAMPLE[shape]


def _all_reasons():
    for kind, table in (("CAVEAT", vocab.CAVEAT_REASONS),
                        ("UNCHECKABLE_CAUSE", vocab.UNCHECKABLE_REASONS)):
        for code, shape in table.items():
            yield kind, code, shape


class RoundTripTests(unittest.TestCase):
    """format_reason -> parse_reason is the identity, for every declared code."""

    def test_every_declared_code_round_trips(self):
        for kind, code, shape in _all_reasons():
            param = _valid_param(shape)
            text = vocab.format_reason(kind, code, param)
            self.assertEqual(vocab.parse_reason(kind, text), (code, param),
                             "%s:%s" % (kind, code))

    def test_bare_code_rejects_a_suffix(self):
        for kind, code, shape in _all_reasons():
            if shape is not vocab.NONE:
                continue
            with self.assertRaises(vocab.VocabularyError, msg="%s:%s" % (kind, code)):
                vocab.format_reason(kind, code, "anything")

    def test_parameterised_code_rejects_a_missing_param(self):
        for kind, code, shape in _all_reasons():
            if shape is vocab.NONE:
                continue
            with self.assertRaises(vocab.VocabularyError, msg="%s:%s" % (kind, code)):
                vocab.format_reason(kind, code, None)

    def test_days_code_rejects_a_path(self):
        for kind, code, shape in _all_reasons():
            if shape is not vocab.DAYS:
                continue
            with self.assertRaises(vocab.VocabularyError):
                vocab.format_reason(kind, code, "some/path.py")

    def test_sub_vocabulary_code_rejects_an_outside_token(self):
        for kind, code, shape in _all_reasons():
            if not isinstance(shape, tuple):
                continue
            with self.assertRaises(vocab.VocabularyError, msg="%s:%s" % (kind, code)):
                vocab.format_reason(kind, code, "definitely-not-a-member")

    def test_undeclared_code_is_rejected_in_both_directions(self):
        for kind in ("CAVEAT", "UNCHECKABLE_CAUSE"):
            with self.assertRaises(vocab.VocabularyError):
                vocab.format_reason(kind, "invented_reason")
            with self.assertRaises(vocab.VocabularyError):
                vocab.parse_reason(kind, "invented_reason")

    def test_a_path_param_survives_delimiters(self):
        text = vocab.format_reason("CAVEAT", "hub_overlap_only", "we|ird%.py")
        self.assertNotIn("|", text.split(":", 1)[1])
        self.assertEqual(vocab.parse_reason("CAVEAT", text)[1], "we|ird%.py")


class NoLiteralEscapesTheTableTests(unittest.TestCase):
    """Every reason the checker can emit must come through `format_reason`."""

    def _emitted_reasons(self):
        """Drive every fixture and harvest the reason records actually emitted."""
        import test_parallel_admission as core
        seen = []
        for kw in _FIXTURES:
            result = pa.decide(core.build(**kw))
            for line in result.lines:
                if line.startswith("CAVEAT:"):
                    seen.append(("CAVEAT", line))
                elif line.startswith("UNCHECKABLE_CAUSE:"):
                    seen.append(("UNCHECKABLE_CAUSE", line))
        return seen

    def test_every_emitted_reason_parses_against_the_table(self):
        emitted = self._emitted_reasons()
        self.assertTrue(emitted, "fixtures produced no reason records to check")
        for kind, line in emitted:
            reason = line.split("|", 1)[1]
            # Raises VocabularyError if the code is undeclared or the parameter
            # does not match its declared shape.
            vocab.parse_reason(kind, reason)

    def test_no_reason_literal_bypasses_format_reason(self):
        """AST scan: the core builds reason fields only via `format_reason`.

        A literal like `"stale_claim:%dd" % n` spliced straight into a record
        would satisfy every runtime assertion above while being invisible to the
        table -- which is the drift this guard exists to catch.
        """
        with open(CORE_SRC, encoding="utf-8") as fh:
            tree = ast.parse(fh.read())
        declared = set(vocab.CAVEAT_REASONS) | set(vocab.UNCHECKABLE_REASONS)
        offenders = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
                continue
            text = node.value
            if ":" not in text or not re.match(r"^[a-z_]+:", text):
                continue
            code = text.split(":", 1)[0]
            if code in declared:
                offenders.append(text)
        self.assertEqual(offenders, [],
                         "reason literals must go through format_reason: %r" % offenders)

    def test_render_uses_format_reason_for_both_record_kinds(self):
        with open(CORE_SRC, encoding="utf-8") as fh:
            src = fh.read()
        self.assertIn('vocab.format_reason("CAVEAT"', src)
        self.assertIn('vocab.format_reason("UNCHECKABLE_CAUSE"', src)


def _fixtures():
    import test_parallel_admission as core
    c = core.claim
    s = core.surface
    return [
        {},
        dict(inflight=[c(paths=("a.py",))]),
        dict(inflight=[c(paths=("hub.py",))], candidate=s("cand", ("hub.py",)),
             touch={"hub.py": 50}),
        dict(inflight=[c(paths=("a.py",), age=99 * 24 * 3600)]),
        dict(inflight=[c(paths=("z.py",), liveness="status_only")]),
        dict(inflight=[c(paths=("z.py",), liveness="lock_only")]),
        dict(inflight=[c(paths=("z.py",), liveness="unknown")]),
        dict(inflight=[c(paths=("z.py",), liveness="unknown", same_host=False)]),
        dict(inflight=[c(paths=(), resolution="no_plan")]),
        dict(inflight=[c(paths=("z.py",), age_reason="malformed")]),
        dict(candidate=s("cand", (), "all_phantom")),
        dict(candidate=s("cand", (), "unknown_history")),
        dict(recovered_used=True),
        dict(corpora=(pa.CorpusEvidence("data", "unavailable", 0, "no_local_ref"),)),
        dict(locks=pa.LockEvidence("allow-cached", "cached", 900, None)),
        dict(locks=pa.LockEvidence("require-fresh", "cached", 900, "no_reflog")),
        dict(locks=pa.LockEvidence("require-fresh", "unavailable", None, "timeout")),
    ]


_FIXTURES = _fixtures()


class ClosedSetTests(unittest.TestCase):
    """Every other closed vocabulary, same treatment."""

    SETS = {
        "verdict": "VERDICTS",
        "overlap class": "OVERLAP_CLASSES",
        "narrowed class": "NARROWED_CLASSES",
        "liveness": "LIVENESS_CLASSES",
        "path state": "PATH_STATES",
        "provenance": "PROVENANCES",
        "quality": "ORIGIN_QUALITIES",
        "corpus name": "CORPUS_NAMES",
        "corpus status": "CORPUS_STATUSES",
        "lock state": "LOCK_STATES",
        "lock mode": "LOCK_MODES",
        "enumeration status": "SOURCE_STATUSES",
    }

    def test_check_member_raises_on_an_undeclared_value(self):
        for what, name in self.SETS.items():
            with self.assertRaises(vocab.VocabularyError, msg=name):
                vocab.check_member("not-a-member", getattr(vocab, name), what)

    def test_check_member_accepts_every_declared_value(self):
        for name in self.SETS.values():
            for value in getattr(vocab, name):
                self.assertEqual(vocab.check_member(value, getattr(vocab, name), name),
                                 value)

    def test_rendered_enums_are_declared_members(self):
        import test_parallel_admission as core
        for kw in _FIXTURES:
            for line in pa.decide(core.build(**kw)).lines:
                prefix, _, rest = line.partition(":")
                if prefix == "VERDICT":
                    self.assertIn(rest, vocab.VERDICTS)
                elif prefix == "OVERLAP":
                    self.assertIn(rest.split("|")[1], vocab.OVERLAP_CLASSES)
                elif prefix == "NARROWED":
                    self.assertIn(rest.split("|")[1], vocab.NARROWED_CLASSES)
                elif prefix == "INFLIGHT":
                    self.assertIn(rest.split("|")[2], vocab.LIVENESS_CLASSES)
                    self.assertIn(rest.split("|")[4], vocab.PATH_STATES)
                elif prefix == "INFLIGHT_SOURCE":
                    self.assertIn(rest.split("|")[0], vocab.SOURCE_NAMES)
                    self.assertIn(rest.split("|")[1], vocab.SOURCE_STATUSES)
                elif prefix == "CORPUS":
                    self.assertIn(rest.split("|")[0], vocab.CORPUS_NAMES)
                    self.assertIn(rest.split("|")[1], vocab.CORPUS_STATUSES)
                elif prefix == "LOCKS":
                    self.assertIn(rest.split("|")[0], vocab.LOCK_STATES)

    def test_tier_values_are_declared(self):
        import test_parallel_admission as core
        for liveness in vocab.LIVENESS_CLASSES:
            t = pa.tier(core.claim(liveness=liveness), pa.MAX_CLAIM_AGE_S, core.NOW)
            self.assertIn(t, vocab.TIERS)


class UpstreamDriftTests(unittest.TestCase):
    """Pin the halves imported from t1569_1 so a change there breaks loudly."""

    def test_inflight_path_sentinels_match_the_gatherer_contract(self):
        contract = os.path.join(REPO_ROOT, ".claude", "skills", "aitask-trail",
                                "SKILL.md.j2")
        if not os.path.isfile(contract):
            self.skipTest("gatherer skill contract not present")
        with open(contract, encoding="utf-8") as fh:
            text = fh.read()
        decl = [l for l in text.splitlines() if l.startswith("INFLIGHT_PATH:")]
        self.assertTrue(decl, "INFLIGHT_PATH: grammar not found in the contract")
        for code in vocab.IMPORTED_FROM_INFLIGHT_PATH:
            self.assertIn(code, decl[0],
                          "%r is imported from the gatherer but is no longer in "
                          "its declared vocabulary -- reconcile, do not fork" % code)

    def test_lock_cache_reasons_match_trail_gather(self):
        src = os.path.join(LIB_DIR, "trail_gather.py")
        if not os.path.isfile(src):
            self.skipTest("trail_gather.py not present")
        with open(src, encoding="utf-8") as fh:
            text = fh.read()
        for code in vocab.IMPORTED_FROM_LOCKS_CACHE_AGE:
            self.assertIn('"%s"' % code, text,
                          "%r is imported from _locks_cache_age but no longer "
                          "appears there -- reconcile, do not fork" % code)

    def test_imported_codes_are_actually_declared_here(self):
        for code in (vocab.IMPORTED_FROM_INFLIGHT_PATH
                     + vocab.IMPORTED_FROM_LOCKS_CACHE_AGE):
            self.assertIn(code, vocab.UNCHECKABLE_REASONS)


if __name__ == "__main__":
    unittest.main()
