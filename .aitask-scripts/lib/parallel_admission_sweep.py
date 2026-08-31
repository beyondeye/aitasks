"""Measurement harness for the parallel-admission checker (t1643).

Answers "what does the hub threshold buy?" against a ground truth ``decide``
cannot see: over ARCHIVED tasks, did the two tasks' actually-landed file sets
intersect? The checker's verdict is computed by ``parallel_admission.decide``
and NOWHERE ELSE here -- this module supplies the population and counts the
outcomes, so a change to the verdict logic moves these numbers automatically
instead of leaving a stale replica behind.

THE INVARIANT THIS EXISTS TO PIN. Under DEMOTION (t1569_3 Step 1) recall of
``CONFLICT u CLEAR_CAVEATED`` is INVARIANT in the hub threshold: the threshold
re-GRADES an overlap, it never discards one. Precision is not invariant, and
neither is the split between the two flagged verdicts -- which is the quantity a
consumer actually decides on, because t1569_4 makes ``CONFLICT`` a
stop-and-replan while ``CLEAR_CAVEATED`` is at most a confirmation. Reporting
invariant recall alone would hide exactly that.

THIS MODULE DECIDES NOTHING ABOUT THE THRESHOLD. It measures. The rule for what
hard-stop/confirmation trade-off is acceptable belongs to t1569_4, which owns
the ``parallel_admission: block|warn|off`` knob.

The numbers are volatile corpus statistics and are deliberately NOT frozen here
or anywhere else in the source: the archived population grows with every
archival (270 -> 281 tasks between t1569_3 and t1643, and 279 -> 281 within a
single t1643 planning session). Re-run ``aitask_parallel_admission.sh sweep``
when a number has to carry a decision, and read the dated record in
``aiplans/archived/p1643_*`` for what it said at one moment.

PURE. No ``os``, no ``time``, no ``subprocess``, no I/O -- the same contract as
``parallel_admission`` itself, enforced by ``tests/test_parallel_admission_purity.py``
(this module is listed in its ``PURE_MODULES``). The impure half -- globbing
archived plans, reading them, running the batch map -- lives in
``parallel_admission_collect``, which builds the ``PlanExtraction`` records this
module's callers consume.
"""

import itertools
import re
from dataclasses import dataclass

import parallel_admission as pa


# Headings after which a plan's body is written with HINDSIGHT -- knowledge the
# plan did not have at admission time. Cutting there approximates the plan as it
# actually stood when a `check` would have run.
#
# EXACTLY ONE ENTRY, AND THE NARROWNESS IS THE POINT. `Verification pass` looks
# like a sibling and is NOT: a re-verification section is written when a plan is
# RE-PICKED, so it sits BEFORE the implementation body it precedes -- in
# `p1569_3` itself it is at line 32, ahead of the whole Step 1-8 plan. Cutting
# on it discarded 9 of 281 tasks from the population outright (their entire plan
# body vanished, leaving no resolved surface) and inflated the reported hindsight
# correction from 3pp to 6pp. `Post-Review Changes` is likewise excluded: it is
# probably post-work, but 73 of its 79 occurrences sit BEFORE
# `Final Implementation Notes`, and "probably" is not enough to justify deleting
# genuine admission-time paths.
#
# The asymmetry is deliberate. Leaving post-hoc text IN biases the result toward
# the optimistic side and is visible as a known residual; cutting genuine plan
# text OUT silently amputates the population. So a heading joins this set only
# with proof, and the reported correction is a conservative FLOOR.
POST_WORK_HEADINGS = ("Final Implementation Notes",)

_POST_WORK_RE = re.compile(
    r"^#{1,6}[ \t]+(?:%s)[ \t]*$" % "|".join(re.escape(h) for h in POST_WORK_HEADINGS),
    re.MULTILINE,
)


@dataclass(frozen=True)
class PlanExtraction:
    """One plan's path extraction, plus the accounting the surface throws away.

    ``parallel_admission_collect.surface_from_plan`` returns only the kept
    paths, so the count of tokens DROPPED as phantom -- the size of the oracle's
    corpus-drift bias -- has nowhere to live. This record is that place, and it
    is produced by the SAME pass that produces the surface, so the drop count
    can never disagree with the surface it describes.

    ``resolution`` carries the same vocabulary as ``Surface.resolution``.
    """

    ref: str
    paths: tuple = ()
    resolution: str = "resolved"
    tokens_total: int = 0
    tokens_dropped: int = 0

    def as_surface(self):
        """The ``Surface`` this extraction represents.

        One constructor, so a caller cannot build a surface whose paths and
        resolution disagree with the record's own accounting.
        """
        return pa.Surface(ref=self.ref, provenance="plan_declared",
                          paths=self.paths, resolution=self.resolution,
                          quality="n/a")


@dataclass(frozen=True)
class Confusion:
    """Pairwise outcome tallies for one hub threshold.

    COUNTS ONLY -- no rates are stored. A stored float is a frozen statistic
    that drifts against the corpus it was derived from; the accessors below
    derive rates on demand and return ``None`` rather than a plausible-looking
    number when the denominator is zero.

    ``colliding`` is the ground truth: pairs whose actually-landed file sets
    intersect. The three ``tp_*``/``missed`` fields partition it -- every true
    collision is hard-stopped, downgraded to a caveat, or missed -- which is
    what lets a consumer see the grading cost that invariant recall hides.
    """

    hub_threshold: int
    pairs: int = 0
    colliding: int = 0
    verdicts: tuple = ()        # ((verdict, count), ...) sorted by verdict
    pred_conflict: int = 0      # pairs verdicted CONFLICT
    pred_flagged: int = 0       # pairs verdicted CONFLICT or CLEAR_CAVEATED
    tp_conflict: int = 0        # ... of which really collided
    tp_caveated: int = 0        # true collisions graded CLEAR_CAVEATED
    missed: int = 0             # true collisions not flagged at all

    def count(self, verdict):
        for name, n in self.verdicts:
            if name == verdict:
                return n
        return 0

    @property
    def tp_flagged(self):
        return self.tp_conflict + self.tp_caveated


def _ratio(num, den):
    """``num/den``, or ``None`` when undefined.

    NEVER a default of 1.0 or 0.0: an empty population that reports "100% recall"
    is the failure this returns ``None`` to prevent.
    """
    return None if not den else num / float(den)


def precision_conflict(c):
    """Of the pairs hard-stopped, how many really collided."""
    return _ratio(c.tp_conflict, c.pred_conflict)


def recall_flagged(c):
    """Of the real collisions, how many were flagged at all (CONFLICT u CAVEATED).

    The threshold-INVARIANT metric -- see the module docstring.
    """
    return _ratio(c.tp_flagged, c.colliding)


def share_hard_stopped(c):
    """Of the real collisions, how many produced a hard stop.

    THE DECISION-RELEVANT NUMBER, and the one that moves with the threshold.
    """
    return _ratio(c.tp_conflict, c.colliding)


def share_downgraded(c):
    """Of the real collisions, how many were graded down to a confirmation."""
    return _ratio(c.tp_caveated, c.colliding)


def share_missed(c):
    """Of the real collisions, how many the checker did not flag at all."""
    return _ratio(c.missed, c.colliding)


# Fixed, healthy scaffolding for a two-task comparison. Every probe, corpus and
# lock is pinned OK so that nothing but the two surfaces and the threshold can
# influence the verdict: an `UNCHECKABLE` leaking in from a degraded probe would
# silently remove a pair from the graded population and quietly move every rate.
_ENUMERATION = tuple(pa.SourceEvidence(name, "ok")
                     for name in ("gate", "lock", "status"))
_CORPORA = (pa.CorpusEvidence("code", "ok", 1),
            pa.CorpusEvidence("data", "ok", 1))
_LOCKS = pa.LockEvidence(mode="require-fresh", state="fetched", age_s=0)


def pair_input(cand_surface, other_ref, other_surface, touch_counts,
               hub_threshold, now=0):
    """The ``AdmissionInput`` for "task A starts while task B is in flight".

    The ONE place a comparison is built, so the harness cannot drift from the
    checker. The claim is deliberately ``live`` / same-host / claimed *now*: that
    is the blocking tier, the only tier whose overlaps can reach ``CONFLICT``.
    """
    claim = pa.InflightClaim(
        ref=other_ref, sources=("lock", "status"), task_status="Implementing",
        liveness="live", same_host=True, claim_at_s=now, surface=other_surface)
    return pa.AdmissionInput(
        candidate=cand_surface, enumeration=_ENUMERATION, inflight=(claim,),
        locks=_LOCKS, corpora=_CORPORA, touch_counts=touch_counts,
        hub_threshold=hub_threshold, now=now)


def pair_verdict(a_surface, b_ref, b_surface, touch_counts, hub_threshold, now=0):
    """The verdict for one ordered pair. Symmetric -- see the tests."""
    return pa.decide(pair_input(a_surface, b_ref, b_surface, touch_counts,
                                hub_threshold, now)).verdict


def confusion(population, touch_counts, hub_threshold, now=0):
    """Tally every unordered pair of ``population`` at one hub threshold.

    ``population`` is ``((ref, plan_surface, landed_paths_frozenset), ...)``.
    ``plan_surface`` is what a ``check`` would have compared; ``landed_paths`` is
    the oracle -- what the task actually changed. Unordered pairs are sound
    because the verdict is symmetric in the two surfaces (pinned by a test, not
    assumed).
    """
    counts = {}
    pairs = colliding = 0
    pred_conflict = pred_flagged = 0
    tp_conflict = tp_caveated = missed = 0

    for (_a_ref, a_surf, a_landed), (b_ref, b_surf, b_landed) in \
            itertools.combinations(population, 2):
        verdict = pair_verdict(a_surf, b_ref, b_surf, touch_counts,
                               hub_threshold, now)
        counts[verdict] = counts.get(verdict, 0) + 1
        pairs += 1
        really = bool(a_landed & b_landed)
        colliding += really
        if verdict == "CONFLICT":
            pred_conflict += 1
            pred_flagged += 1
            tp_conflict += really
        elif verdict == "CLEAR_CAVEATED":
            pred_flagged += 1
            tp_caveated += really
        elif really:
            missed += 1

    return Confusion(
        hub_threshold=hub_threshold, pairs=pairs, colliding=colliding,
        verdicts=tuple(sorted(counts.items())), pred_conflict=pred_conflict,
        pred_flagged=pred_flagged, tp_conflict=tp_conflict,
        tp_caveated=tp_caveated, missed=missed)


def cut_post_implementation(body):
    """Truncate ``body`` at the first ``POST_WORK_HEADINGS`` heading.

    Returns it unchanged when none is present. See ``POST_WORK_HEADINGS`` for
    why the set is one entry and why widening it needs proof rather than
    plausibility.
    """
    match = _POST_WORK_RE.search(body)
    return body if match is None else body[:match.start()]
