"""Ranking, freshness and lane policy for the background-work roadmap (t1569_5).

Consumer #2 of the shared parallel-admission checker -- the **advisory** one.
Everything arrives as already-materialised text: t1569_1's gatherer records,
t1569_2's batch map, and this slice's own ``ORIGIN_FACT:`` rows. The verdict
comes from ``parallel_admission.decide``; the *policy* -- what a verdict is worth,
how candidates are ordered, and how the result is encoded as a trail -- lives
here and nowhere else.

PURE. No ``os``, no ``time``, no ``subprocess``, no I/O. The clock is a
parameter, exactly as it is on ``AdmissionInput.now``.
``tests/test_parallel_admission_purity.py`` enforces it by AST scan and by
importing with ``subprocess`` poisoned; the caller is responsible for having
``.aitask-scripts/lib`` on ``sys.path``.

THE LANES ARE THE CHECKER'S VERDICTS, NOT A SECOND OPINION. Nothing here
re-derives a collision. A second opinion would be a second definition of "safe",
which is the entire reason ``parallel_admission`` exists as one module with two
consumers. This module maps ``CLEAR`` / ``CLEAR_CAVEATED`` / ``CONFLICT`` /
``UNCHECKABLE`` onto waves and confidence, and stops there.

THE WHOLE OUTPUT IS AN ESTIMATE. Origin/topic evidence, in-flight state as of
the run, **reserving nothing** -- explicitly distinct from t1569_4's live,
plan-derived admission decision. ``CLEAR`` means "no known conflict at check
time"; overlapping work can begin the instant after. Never "safe to run in
parallel".

ORDERING IS LEXICOGRAPHIC, NOT A WEIGHTED SUM::

    (-risk_band, -risk_axes_at_band, -premise_band, -affinity,
     -recency_band, -priority_band, canonical_sort_id)

That is what makes "in-flight affinity must not bury urgent unrelated work" a
structural property rather than an artefact of weight tuning: affinity sits
below risk, so it can reorder within a risk band and never across one.
``followup_kind`` is absent from the key entirely -- the trail schema declares it
display-only, and ``RankingTests`` permutes it across the corpus and asserts a
byte-identical ranking.
"""

from dataclasses import dataclass, field

import parallel_admission as pa
import parallel_admission_vocab as vocab
import roadmap_premise as premise

__all__ = [
    "AXIS_BAND", "RANK", "PREMISE_CEILING", "PREMISE_BAND", "PRIORITY_BAND",
    "RECENCY_BUCKETS", "LANES", "SENTINELS",
    "Candidate", "OriginFacts", "Scored", "Roadmap",
    "axis_band", "combine_risk", "confidence_for", "lane_for",
    "parse_members", "parse_origin_facts", "reduce_origin_facts",
    "day_ordinal", "recency_band",
    "score_all", "build", "to_trail", "measurement_lines",
    "counterfactual_rank_delta", "dual_signal_refs", "EmptyRoadmapError",
]

# Values a producer writes to mean "no value". `-` is this slice's own
# collector; `unknown` / `invalid` are the gatherer's transport sentinels
# (implementation_trail.schema.json:396). Treating any of them as data is how a
# sentinel ends up rendered as a risk level or written into a schema enum.
SENTINELS = ("", "-", "unknown", "invalid", "none")

# Risk bands. `unknown` sits BETWEEN medium and low on purpose: an unknown risk
# could be high, so ranking it below `low` would hide it and above `medium`
# would over-claim.
AXIS_BAND = {"high": 3, "medium": 2, None: 1, "low": 0}

RANK = {"low": 0, "medium": 1, "high": 2}

# Premise validity is an independent axis from conflict evidence, so it applies
# as a CEILING rather than joining the confidence table. Without it a premise
# known to have changed could still be rendered as a high-confidence wave-1
# recommendation -- more reassuring than an advisory signal warrants.
PREMISE_CEILING = {premise.FRESH: "high",
                   premise.SKIP: "medium",
                   premise.ASK_STALE: "low"}

PREMISE_BAND = {premise.FRESH: 2, premise.SKIP: 1, premise.ASK_STALE: 0}

PRIORITY_BAND = {"high": 2, "medium": 1, "low": 0}

# (max age in days, band). First match wins; anything older scores 0.
RECENCY_BUCKETS = ((7, 3), (30, 2), (90, 1))

# verdict -> (lane ordinal, classification, lane title, lane purpose).
# UNCHECKABLE gets its OWN lane rather than joining coordination: "cannot tell"
# is not "conflicts with", and filing it under coordination would assert a
# conflict the checker did not find. What it may never be is wave 1.
LANES = {
    "CLEAR": (1, "core"),
    "CLEAR_CAVEATED": (1, "core"),
    "CONFLICT": (2, "coordination_only"),
    "UNCHECKABLE": (3, "optional"),
}

_LANE_TITLES = {
    1: ("Parallel-safe", "No known conflict at check time — these can be started "
        "in the background now. This is an estimate over origin/topic evidence "
        "and in-flight state as of the run; it reserves nothing."),
    2: ("Coordination", "Overlaps the declared or derived surface of work already "
        "in flight. Fold into, or queue immediately after, the in-flight task "
        "rather than starting alongside it."),
    3: ("Unresolvable", "The comparison could not be made. Named causes below — "
        "these are surfaced hedged and are deliberately not in the safe lane."),
}


class EmptyRoadmapError(Exception):
    """No candidate survived, so there is no valid trail document to emit.

    `waves` is `minItems: 1` and so is every wave's `entries`, so a zero-
    candidate scope has NO valid encoding -- emitting `waves: []` would produce
    an artifact that cannot validate while `to_trail` claims to return a
    complete document. The caller decides what a zero-candidate run means
    (usually: report it and publish nothing); this refuses to guess.
    """


def _clean(value):
    """A producer's field -> its value, or None when it is a sentinel."""
    value = str(value or "").strip()
    return None if value.lower() in SENTINELS else value


@dataclass(frozen=True)
class Candidate:
    ref: str
    status: str = None
    priority: str = None
    effort: str = None
    boardcol: str = None
    labels: tuple = ()
    followup_kind: str = None
    path: str = None
    created_at: str = None
    anchor: str = None
    verifies: tuple = ()
    risk_code_health: str = None
    risk_goal_achievement: str = None

    @property
    def task_id(self):
        return pa.canonical_ref(self.ref)


@dataclass(frozen=True)
class OriginFacts:
    """One task's origin layer, already reduced across all of its origins."""

    quality: str = "unknown"
    origins: tuple = ()
    rch: str = None                 # the axis value that SET the band
    rga: str = None
    provenance: str = "absent"      # active | archived | mixed | absent
    absent_origins: tuple = ()
    disagreeing_axes: tuple = ()    # axes whose origins did not all agree
    setter: str = None              # the origin that set the higher band
    per_origin: tuple = ()          # (origin, rch, rga) BEFORE reduction


@dataclass(frozen=True)
class Scored:
    candidate: Candidate
    verdict: str
    lane: int
    classification: str
    confidence: str
    caveats: tuple
    rationale: str
    risk_band: int
    risk_axes_at_band: int
    premise_decision: str
    affinity: int
    recency: int
    priority: int
    origin: OriginFacts
    admission_lines: tuple = ()
    premise_lines: tuple = ()

    @property
    def sort_key(self):
        return (-self.risk_band, -self.risk_axes_at_band,
                -PREMISE_BAND.get(self.premise_decision, 1), -self.affinity,
                -self.recency, -self.priority, _sort_id(self.candidate.ref))


@dataclass(frozen=True)
class Roadmap:
    entries: tuple = ()
    histogram: dict = field(default_factory=dict)
    degraded: tuple = ()
    counterfactual: tuple = (0, 0)


def _sort_id(ref):
    """`aitasks#1569_10` -> (1569, 10). A COMPARISON key only.

    Numeric so `1569_10` sorts after `1569_9`; the original ref string is what
    is written to the trail, never this.
    """
    bare = pa.canonical_ref(ref)
    parent, _, child = bare.partition("_")
    try:
        return (int(parent), int(child) if child else -1, "")
    except ValueError:
        # An id that is not numeric cannot be ordered numerically, but it must
        # still be ordered TOTALLY or the ranking stops being deterministic.
        # Same arity as the numeric key so the comparison never depends on
        # tuple length.
        return (float("inf"), 0, bare)


# --- risk -------------------------------------------------------------------

def axis_band(value):
    """One risk axis -> its band. An UNDECLARED value raises, never folds.

    Silently absorbing a typo'd level into `unknown` would be a fail-open on the
    roadmap's primary value signal -- the same `check_member` discipline
    `parallel_admission` applies to its own vocabularies.
    """
    value = _clean(value)
    if value not in AXIS_BAND:
        raise vocab.VocabularyError("risk axis: %r" % (value,))
    return AXIS_BAND[value]


def combine_risk(code_health, goal_achievement):
    """The two axes -> ``(band, axes_at_band)``.

    ``max``, and the two axes are PEERS. `risk-evaluation.md` assesses them
    independently and forbids blending them into one score, but ordering needs a
    total order -- and `max` is the only combination that is symmetric (so
    `(high, low)` and `(low, high)` rank identically) and monotone (so raising
    either axis can never lower the rank). It also cannot discard the more
    urgent axis, which "whichever field the code reads first" silently does.

    ``axes_at_band`` breaks ties WITHIN a band, so `(high, high)` precedes
    `(high, low)` without either axis being privileged.
    """
    a, b = axis_band(code_health), axis_band(goal_achievement)
    band = max(a, b)
    return band, (a == band) + (b == band)


# --- parsing ----------------------------------------------------------------

def parse_members(member_lines):
    """Gatherer ``MEMBER:`` / ``MEMBER_EXT:`` records -> ``{ref: Candidate}``.

    ``MEMBER:``'s free-ish last field is the path, so it splits left-to-right
    with a bounded maxsplit -- a path containing ``|`` stays intact.
    ``MEMBER_EXT:`` has no free field but is split the same bounded way.
    """
    base, ext = {}, {}
    for line in member_lines:
        line = line.rstrip("\n")
        if line.startswith("MEMBER:"):
            parts = line[len("MEMBER:"):].split("|", 7)
            if len(parts) == 8:
                base[parts[0]] = parts
        elif line.startswith("MEMBER_EXT:"):
            parts = line[len("MEMBER_EXT:"):].split("|", 5)
            if len(parts) == 6:
                ext[parts[0]] = parts

    out = {}
    for ref, parts in base.items():
        e = ext.get(ref, [ref] + [""] * 5)
        out[ref] = Candidate(
            ref=ref,
            status=_clean(parts[1]), priority=_clean(parts[2]),
            effort=_clean(parts[3]), boardcol=_clean(parts[4]),
            labels=tuple(x for x in parts[5].split(",") if x),
            followup_kind=_clean(parts[6]), path=parts[7] or None,
            created_at=_clean(e[1]), anchor=_clean(e[2]),
            verifies=tuple(pa.canonical_ref(v)
                           for v in e[3].split(",") if v),
            risk_code_health=_clean(e[4]), risk_goal_achievement=_clean(e[5]))
    return out


def parse_origin_facts(lines):
    """``ORIGIN_FACT:`` rows -> ``{task_id: [(origin, quality, rch, rga, source)]}``."""
    out = {}
    for line in lines:
        line = line.rstrip("\n")
        if not line.startswith("ORIGIN_FACT:"):
            continue
        parts = line[len("ORIGIN_FACT:"):].split("|", 5)
        if len(parts) != 6:
            continue
        task_id, origin, quality, rch, rga, source = (
            vocab.decode_path(p) for p in parts)
        out.setdefault(pa.canonical_ref(task_id), []).append(
            (_clean(origin), quality, _clean(rch), _clean(rga), source))
    return out


def reduce_origin_facts(rows, own_code_health=None, own_goal_achievement=None):
    """Many ``(task, origin)`` rows -> one :class:`OriginFacts`.

    THE REDUCTION IS POLICY, WHICH IS WHY IT LIVES HERE. 25 of 89 exact
    follow-ups carry more than one origin (up to 11), 13 of those disagree on a
    risk level and 6 span mixed sources (2026-08-31). A first-origin
    implementation reports t1064 as `low` while one of its origins is `medium`.

    Per axis the reduction is ``max`` over the origins AND the candidate's own
    value -- the parent task's signal is "``risk_code_health:`` on the task **or**
    its origin", and including both keeps the rule symmetric and monotone
    instead of needing a precedence tie-break. An absent origin contributes the
    `unknown` band, never 0.
    """
    if not rows:
        return OriginFacts(rch=own_code_health, rga=own_goal_achievement)

    quality = rows[0][1]
    named = [r for r in rows if r[0]]
    origins = tuple(sorted({r[0] for r in named}, key=_sort_id))
    sources = {r[4] for r in named} or {"absent"}
    absent = tuple(sorted((r[0] for r in named if r[4] == "absent"),
                          key=_sort_id))

    reduced, disagreeing, contributors = {}, [], {}
    for index, axis_name, own in ((2, "risk_code_health", own_code_health),
                                  (3, "risk_goal_achievement",
                                   own_goal_achievement)):
        origin_bands = {r[0]: axis_band(r[index]) for r in named}
        top = max(list(origin_bands.values()) + [axis_band(own)])
        reduced[axis_name] = _band_name(top)
        if len(set(origin_bands.values())) > 1:
            disagreeing.append(axis_name)
        for origin, band in origin_bands.items():
            if band == top:
                contributors[origin] = max(contributors.get(origin, 0), band)

    # The origin that set the winning band, named so the reduction is auditable
    # rather than an opaque max. Ties break on the id, for determinism.
    setter = None
    if contributors:
        best = max(contributors.values())
        setter = sorted((o for o, b in contributors.items() if b == best),
                        key=_sort_id)[0]

    if len(sources) > 1:
        provenance = "mixed"
    else:
        provenance = sources.pop()

    # The pre-reduction values are kept, not just the winner. A `max` a human
    # cannot audit is a number they cannot override, and the roadmap's whole
    # claim is that every score component is visible per entry.
    per_origin = tuple(sorted(((r[0], r[2], r[3]) for r in named),
                              key=lambda row: _sort_id(row[0])))

    return OriginFacts(quality=quality, origins=origins,
                       rch=reduced["risk_code_health"],
                       rga=reduced["risk_goal_achievement"],
                       provenance=provenance, absent_origins=absent,
                       disagreeing_axes=tuple(disagreeing), setter=setter,
                       per_origin=per_origin)


def _band_name(band):
    for name, value in AXIS_BAND.items():
        if value == band:
            return name
    raise vocab.VocabularyError("risk band: %r" % (band,))


# --- freshness --------------------------------------------------------------

def day_ordinal(stamp):
    """``YYYY-MM-DD [HH:MM]`` -> a day number, or None.

    Pure integer arithmetic (proleptic Gregorian, Hinnant's algorithm) because
    the purity guard forbids ``datetime`` -- and because the stored stamp
    carries no timezone, so anything finer than a day would be false precision.
    """
    stamp = _clean(stamp)
    if not stamp:
        return None
    try:
        y, m, d = (int(x) for x in stamp.split(" ")[0].split("-"))
    except (ValueError, IndexError):
        return None
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return None
    y -= m <= 2
    era = (y if y >= 0 else y - 399) // 400
    yoe = y - era * 400
    doy = (153 * (m + (-3 if m > 2 else 9)) + 2) // 5 + d - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def recency_band(created_at, now_ordinal):
    """How recently the follow-up was spawned, bucketed.

    An unreadable or absent stamp scores the OLDEST band rather than raising:
    recency is one weak component of a lexicographic key, and a task whose age
    is unknown should not be promoted by that ignorance.
    """
    born = day_ordinal(created_at)
    if born is None or now_ordinal is None:
        return 0
    age = max(0, now_ordinal - born)
    for limit, band in RECENCY_BUCKETS:
        if age <= limit:
            return band
    return 0


# --- lanes and confidence ---------------------------------------------------

def lane_for(verdict):
    """The checker's verdict -> ``(lane ordinal, classification)``."""
    if verdict not in LANES:
        raise vocab.VocabularyError("verdict: %r" % (verdict,))
    return LANES[verdict]


def confidence_for(verdict, origin_quality, premise_decision):
    """Conflict evidence and origin quality, then capped by premise validity.

    The table carries origin quality INTO confidence, which is what stops a
    `topic` entry from reading like an `exact` one. The premise ceiling is
    applied afterwards as a separate, independent axis.
    """
    exact = origin_quality == "exact"
    table = {"CLEAR": "high" if exact else "medium",
             "CLEAR_CAVEATED": "medium" if exact else "low",
             "CONFLICT": "high" if exact else "medium",
             "UNCHECKABLE": "low"}
    if verdict not in table:
        raise vocab.VocabularyError("verdict: %r" % (verdict,))
    ceiling = PREMISE_CEILING.get(premise_decision, "medium")
    return min(table[verdict], ceiling, key=RANK.__getitem__)


# --- scoring ----------------------------------------------------------------

def score_all(candidates, origin_rows, admission, premises, candidate_paths,
              inflight_paths, now_ordinal):
    """Everything already computed per candidate -> ranked :class:`Scored`.

    Every input is injected: ``admission`` maps a ref to the checker's
    ``AdmissionResult``, ``premises`` maps a ref to a
    :class:`roadmap_premise.PremiseResult`, ``candidate_paths`` maps a ref to
    that task's own file surface, and ``inflight_paths`` is the union of the
    in-flight surfaces. Nothing here reaches for state.
    """
    scored = []
    for ref in sorted(candidates, key=_sort_id):
        candidate = candidates[ref]
        origin = reduce_origin_facts(
            origin_rows.get(candidate.task_id, []),
            candidate.risk_code_health, candidate.risk_goal_achievement)

        result = admission.get(ref)
        verdict = result.verdict if result else "UNCHECKABLE"
        lane, classification = lane_for(verdict)

        premise_result = premises.get(ref)
        decision = premise_result.decision if premise_result else premise.SKIP

        band, axes_at_band = combine_risk(origin.rch, origin.rga)
        own_paths = set(candidate_paths.get(ref, ()) or ())
        affinity = 1 if own_paths & set(inflight_paths or ()) else 0

        caveats = _caveats(candidate, origin, verdict, premise_result, result)
        scored.append(Scored(
            candidate=candidate, verdict=verdict, lane=lane,
            classification=classification,
            confidence=confidence_for(verdict, origin.quality, decision),
            caveats=caveats,
            rationale=_rationale(candidate, origin, verdict, decision,
                                 band, axes_at_band, affinity),
            risk_band=band, risk_axes_at_band=axes_at_band,
            premise_decision=decision, affinity=affinity,
            recency=recency_band(candidate.created_at, now_ordinal),
            priority=PRIORITY_BAND.get(candidate.priority or "", 0),
            origin=origin,
            admission_lines=tuple(result.lines) if result else (),
            premise_lines=tuple(premise_result.lines) if premise_result else ()))

    return tuple(sorted(scored, key=lambda s: s.sort_key))


def _caveats(candidate, origin, verdict, premise_result, admission_result):
    """Every hedge that must be visible on the entry itself.

    `caveats[]` rather than prose because a reader scanning a wave sees the
    array; a `topic` entry that reads like an `exact` one is the failure this
    exists to prevent.
    """
    out = []
    if origin.quality != "exact":
        out.append(
            "origin resolved by %s evidence, not an exact origin — the file set "
            "may be wider than, or disjoint from, the true origin"
            % origin.quality)
    if origin.absent_origins:
        out.append("origin task(s) could not be read: %s"
                   % ", ".join(origin.absent_origins))
    if origin.disagreeing_axes:
        out.append(
            "origins disagree on %s; the band is the highest across them%s"
            % (", ".join(origin.disagreeing_axes),
               " (set by %s)" % origin.setter if origin.setter else ""))
    if not origin.origins:
        out.append("no origin resolved — risk is the task's own declaration only")

    if premise_result is not None and premise_result.decision == premise.ASK_STALE:
        out.append(
            "premise may no longer hold: %d origin file(s) changed, %d could "
            "not be checked since the origin landed"
            % (len(premise_result.changed), len(premise_result.unknown)))
    # SKIP stays silent per the convention borrowed from
    # aitask_verification_stale.sh -- it is fail-open, and it is the common
    # state. It still caps confidence, and the run summary reports the count.

    if verdict in ("CLEAR_CAVEATED", "UNCHECKABLE") and admission_result:
        for line in admission_result.lines:
            if line.startswith(("CAVEAT:", "UNCHECKABLE_CAUSE:")):
                out.append(line.split(":", 1)[1].replace("|", ": "))
    return tuple(out)


def _per_origin_text(origin):
    """`900=high/low, 901=low/low` -- compact, complete, deterministic.

    Bounded by the origin count (11 at most across the live corpus), so it is
    rendered in full rather than truncated: a partial audit trail for a `max`
    is the same problem as none.
    """
    return ", ".join("%s=%s/%s" % (ref, rch or "unknown", rga or "unknown")
                     for ref, rch, rga in origin.per_origin)


def _rationale(candidate, origin, verdict, decision, band, axes_at_band,
               affinity):
    """Every score component, as prose.

    `entry` is `additionalProperties: false` and `rendering_hints` is top-level
    and scalar-only, so structured per-entry components would need a
    `schema_version` bump touching both schema copies, `SchemaCopyDrift`, the
    validator and the goldens. Prose in `rationale` (which has `minLength: 1`
    and no maximum) carries the same information at no schema cost.
    """
    bits = [
        "%s — %s." % (verdict, _LANE_TITLES[lane_for(verdict)[0]][0]),
        "Risk band %d (%s) from code-health=%s, goal-achievement=%s across %d "
        "origin(s) [%s]; %d axis/axes at that band."
        % (band, _band_name(band) or "unknown", origin.rch or "unknown",
           origin.rga or "unknown", len(origin.origins), origin.provenance,
           axes_at_band),
        # The reduced pair above is a `max`. Without the inputs beside it the
        # human who must override the ranking cannot see WHICH origin drove it,
        # so the per-origin values are rendered whenever there is more than one.
        "Per-origin risk: %s." % _per_origin_text(origin)
        if len(origin.per_origin) > 1 else
        "Origin risk read from: %s." % (origin.setter or "the task itself"),
        "Origin quality: %s." % origin.quality,
        "Premise: %s." % decision,
        "In-flight area affinity: %s." % ("yes" if affinity else "no"),
        "Priority %s (tie-break only); effort %s (capacity, not value)."
        % (candidate.priority or "unknown", candidate.effort or "unknown"),
    ]
    if candidate.created_at:
        bits.append("Spawned %s." % candidate.created_at)
    return " ".join(bits)


# --- measurement ------------------------------------------------------------

def measurement_lines(scored, counterfactual=None):
    """Resolution-quality records for the run summary.

    The histogram is MUTUALLY EXCLUSIVE (`verifies:` wins over `anchor:`), which
    is why it is derived from the resolver's quality verdict rather than by
    counting raw signals: the raw `anchor` population double-counts every task
    that carries both, and quoting it would inflate the residual.
    """
    histogram = {"exact": 0, "topic": 0, "unknown": 0}
    causes = {}
    for entry in scored:
        histogram[entry.origin.quality] = histogram.get(
            entry.origin.quality, 0) + 1
        if entry.verdict == "UNCHECKABLE":
            for line in entry.admission_lines:
                if line.startswith("UNCHECKABLE_CAUSE:"):
                    code = line.split("|", 1)[-1].split(":", 1)[0]
                    causes[code] = causes.get(code, 0) + 1

    degraded = sum(1 for e in scored if e.verdict == "UNCHECKABLE")
    lines = [
        "ORIGIN_QUALITY:%d|%d|%d" % (histogram["exact"], histogram["topic"],
                                     histogram["unknown"]),
        "DEGRADED:%d|%s" % (degraded,
                            ",".join("%s=%d" % (k, causes[k])
                                     for k in sorted(causes)) or "-"),
    ]
    n, total = counterfactual or (0, 0)
    lines.append("COUNTERFACTUAL:%d|%d|dual_signal_mv_typed" % (n, total))
    return lines


def counterfactual_rank_delta(exact_ranking, topic_ranking, dual_refs):
    """How many dual-signal tasks actually RANK or LANE differently.

    Takes the two rankings the caller produced by running the policy twice --
    once with the exact-origin surface, once with the topic-root surface -- and
    compares each dual-signal task's real position and lane.

    IT MUST NOT BE A PROXY. Comparing the two *file sets* for inequality is
    cheaper and wrong: two different surfaces routinely leave every lane and
    position untouched, so set inequality OVERSTATES the effect, and the
    enhancement threshold for a persisted direct-origin field keys off this
    number. `CounterfactualTests` pins a fixture where the sets differ and the
    rank does not.

    Measurable ONLY on tasks carrying both signals -- the true origin of the
    topic-only population is unknown, so nothing can measure the fallback's
    effect on them. Because the exact signal is written only by the
    manual-verification seams, that sample is entirely MV-typed and therefore
    NOT representative: report it as "n of N dual-signal tasks (MV-typed)" and
    never extrapolate it.
    """
    def placement(ranking):
        return {entry.candidate.ref: (position, entry.lane)
                for position, entry in enumerate(ranking)}

    exact_place, topic_place = placement(exact_ranking), placement(topic_ranking)
    wanted = [ref for ref in dual_refs
              if ref in exact_place and ref in topic_place]
    differing = sum(1 for ref in wanted
                    if exact_place[ref] != topic_place[ref])
    return differing, len(wanted)


def dual_signal_refs(candidates):
    """The refs carrying BOTH an exact-origin signal and a topic root."""
    return tuple(sorted((ref for ref, c in candidates.items()
                         if c.verifies and c.anchor), key=_sort_id))


# --- trail encoding ---------------------------------------------------------

def to_trail(scored, trail_id, title, owner, scope, generation, freshness,
             narrative, evidence, inflight_refs=()):
    """Ranked entries -> a complete ``implementation_trail`` document.

    ALL EXISTING VOCABULARY, NO SCHEMA BUMP. Waves, `classification`,
    `coordinates_with` / `advisory`, the three observation kinds and
    `source_type: command_output` all exist today; a `schema_version` bump would
    touch both schema copies, `SchemaCopyDrift` (a byte-for-byte compare), the
    validator and the goldens for no gain.

    DEPTH IS `deep`, NOT THE DEFAULT `lite`. A lite document must omit
    `observations`, `relations`, `exclusions` and per-entry `evidence_refs` and
    carry exactly one `evidence` record -- this contract needs all of them.

    A ZERO-CANDIDATE SCOPE RAISES :class:`EmptyRoadmapError` rather than
    emitting `waves: []`, which no valid document may contain.

    ONLY NON-EMPTY WAVES ARE BUILT. `wave.entries` is `minItems: 1`, and the
    coordination lane is empty on the live corpus today (simulated: coordination
    0, parallel-safe 220), so an author that always emits three waves produces an
    INVALID document on the very first real run. Ordinals are assigned 1..n over
    the lanes that actually have entries, which keeps them strictly increasing
    without pretending a lane exists.
    """
    if not scored:
        raise EmptyRoadmapError(
            "no candidates: `waves` is minItems:1, so a zero-candidate scope "
            "has no valid trail encoding")

    evidence_ids = tuple(e["evidence_id"] for e in evidence)
    waves, ordinal = [], 0
    for lane in sorted({s.lane for s in scored}):
        members = [s for s in scored if s.lane == lane]
        if not members:
            continue
        ordinal += 1
        lane_title, purpose = _LANE_TITLES[lane]
        waves.append({
            "wave_id": "wave-%d" % ordinal,
            "ordinal": ordinal,
            "title": lane_title,
            "purpose": purpose,
            "entries": [_entry(s, position, evidence_ids)
                        for position, s in enumerate(members, start=1)],
        })

    document = {
        "schema_version": "1.1.0",
        "trail_id": trail_id,
        "title": title,
        "owner": owner,
        "scope": scope,
        "generation": generation,
        "freshness": freshness,
        "narrative": narrative,
        "waves": waves,
        "evidence": list(evidence),
        "rendering_hints": {"depth": "deep"},
    }

    relations = _relations(scored, inflight_refs)
    if relations:
        document["relations"] = relations
    observations = _observations(scored, evidence_ids)
    if observations:
        document["observations"] = observations
    return document


def _entry(scored, position, evidence_ids):
    entry = {
        "entry_id": "e%s" % pa.canonical_ref(scored.candidate.ref),
        "task": scored.candidate.ref,
        "topic": _topic_ref(scored.candidate),
        "position": position,
        "classification": scored.classification,
        "snapshot": _snapshot(scored.candidate),
        "rationale": scored.rationale,
        "confidence": scored.confidence,
    }
    if scored.caveats:
        entry["caveats"] = list(scored.caveats)
    if evidence_ids:
        entry["evidence_refs"] = list(evidence_ids)
    return entry


def _topic_ref(candidate):
    """The anchor root as a task_ref, falling back to the task itself.

    `anchor` is a topic ROOT, never an exact origin -- it is a projection, and
    a task that is its own root carries no anchor at all.
    """
    if not candidate.anchor:
        return candidate.ref
    project = candidate.ref.split("#", 1)[0]
    return "%s#%s" % (project, pa.canonical_ref(candidate.anchor))


def _snapshot(candidate):
    """The member's frozen state, with every sentinel OMITTED, not written.

    Writing the gatherer's `unknown` / `invalid` transport sentinel into
    `priority`, `effort` or `followup_kind` invalidates the whole document --
    those are closed enums. `_clean` has already turned them into None.
    """
    snapshot = {"status": candidate.status or "unknown"}
    for key, value in (("priority", candidate.priority),
                       ("effort", candidate.effort),
                       ("boardcol", candidate.boardcol),
                       ("followup_kind", candidate.followup_kind)):
        if value is not None:
            snapshot[key] = value
    return snapshot


def _relations(scored, inflight_refs):
    """`coordinates_with` / `advisory`, backlog -> in-flight.

    Advisory provenance is mandatory here: the schema forbids writing an
    advisory edge back to task metadata, which is exactly right for a
    recommendation the checker made by observation and never reserved.
    """
    relations = []
    for entry in scored:
        if entry.classification != "coordination_only":
            continue
        for ref in sorted(_overlapping_refs(entry) & set(inflight_refs),
                          key=_sort_id):
            relations.append({
                "from": entry.candidate.ref,
                "to": ref,
                "type": "coordinates_with",
                "provenance": "advisory",
                "note": "shares a file surface with work in flight at check "
                        "time; this is an estimate and reserves nothing",
            })
    return relations


def _overlapping_refs(scored):
    """The in-flight refs the checker actually reported an overlap against."""
    refs = set()
    for line in scored.admission_lines:
        if line.startswith("OVERLAP:"):
            refs.add(line[len("OVERLAP:"):].split("|", 1)[0])
    return refs


def _observations(scored, evidence_ids):
    """`in_flight_conflict` and `stale_premise`, each with real evidence refs.

    `evidence_refs` is `minItems: 1` and every ref must resolve to an
    `evidence[].evidence_id`, so an observation cannot be emitted without
    evidence to point at -- which is the schema enforcing that an assertion
    carries its receipt.
    """
    if not evidence_ids:
        return []
    observations = []
    for entry in scored:
        if entry.classification == "coordination_only":
            # `affects` carries BOTH ends. That is semantically right -- the
            # collision affects the in-flight task as much as the backlog one --
            # and it is also what makes the matching `coordinates_with` relation
            # legal: the validator resolves a relation endpoint against entry
            # tasks, exclusions, snapshot `depends` and observation `affects`,
            # and an in-flight task has no entry of its own in this document.
            affected = [entry.candidate.ref] + sorted(
                _overlapping_refs(entry), key=_sort_id)
            observations.append({
                "observation_id": "obs-conflict-%s"
                                  % pa.canonical_ref(entry.candidate.ref),
                "kind": "in_flight_conflict",
                "statement": "%s overlaps the surface of work in flight at "
                             "check time." % entry.candidate.ref,
                "affects": affected,
                "evidence_refs": list(evidence_ids),
            })
        if entry.premise_decision == premise.ASK_STALE:
            observations.append({
                "observation_id": "obs-premise-%s"
                                  % pa.canonical_ref(entry.candidate.ref),
                "kind": "stale_premise",
                "statement": "The origin files behind %s have changed since "
                             "the origin landed, so the premise this follow-up "
                             "was written against may no longer hold."
                             % entry.candidate.ref,
                "affects": [entry.candidate.ref],
                "evidence_refs": list(evidence_ids),
            })
    return observations


def build(candidates, origin_rows, admission, premises, candidate_paths,
          inflight_paths, now_ordinal, counterfactual=None):
    """Score, rank and summarise in one call -- the entry point t1569_6 uses."""
    scored = score_all(candidates, origin_rows, admission, premises,
                       candidate_paths, inflight_paths, now_ordinal)
    histogram = {"exact": 0, "topic": 0, "unknown": 0}
    for entry in scored:
        histogram[entry.origin.quality] = histogram.get(
            entry.origin.quality, 0) + 1
    return Roadmap(entries=scored, histogram=histogram,
                   degraded=tuple(e.candidate.ref for e in scored
                                  if e.verdict == "UNCHECKABLE"),
                   counterfactual=counterfactual or (0, 0))
