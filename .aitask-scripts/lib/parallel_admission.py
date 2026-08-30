"""Parallel-admission verdict logic -- the single definition of "safe" (t1569_3).

Two consumers, one verdict function:

  * ``aitask_parallel_admission.sh`` (t1569_4's blocking preflight) -- goes
    through ``parallel_admission_collect.collect()`` for live state.
  * the background-work roadmap (t1569_5) -- imports ``decide`` /
    ``input_from_records`` directly and NEVER imports the collector. Its data is
    already-materialised gatherer and batch-map text.

Two implementations would mean two subtly different definitions of "safe", which
is exactly what this module exists to prevent.

PURE. No ``os``, no ``time``, no ``subprocess``, no I/O. Everything the verdict
depends on -- including the clock -- is a field of ``AdmissionInput``. That is
what makes ``decide``/``render`` byte-deterministic over a frozen input and lets
t1569_5 reuse them with no subprocess. ``tests/test_parallel_admission_purity.py``
enforces it by importing this module with ``subprocess`` poisoned and by an AST
scan; do not add an import to work around a fixture.

The caller is responsible for having ``.aitask-scripts/lib`` on ``sys.path``
(the same convention ``plan_paths.py`` uses) -- this module does not manipulate
it, because that would require ``os``.

CLEAR IS AN OBSERVATION, NOT A RESERVATION. This checker takes a snapshot; it
does not reserve the candidate's planned surface. Another agent can begin
overlapping work in the instant after ``VERDICT:CLEAR`` -- the task lock reserves
the *task*, never the *file surface*. Hence the fixed wording "no known conflict
at check time", never "safe to run in parallel". The residual closes only when
t1343's declared-claims backend is adopted; this checker deliberately does not
attempt that reservation.
"""

from dataclasses import dataclass, field

import parallel_admission_vocab as vocab
from parallel_admission_vocab import VocabularyError, check_member, encode_path

# The shared default claim-age bound. `--max-claim-age` and any future profile
# knob are OVERRIDES, never independent defaults: two consumers using different
# bounds would be two definitions of "safe".
#
# 14 days is read off the live claim ages, which separate by two orders of
# magnitude -- every anchored lock is <= 11 days old, while the anchorless
# 2026-02-26 lock this bound exists for is 184 days. The exact value is not
# load-bearing; it only has to sit inside that gap.
MAX_CLAIM_AGE_S = 14 * 24 * 3600

# Default hub threshold, in DISTINCT tasks touching a path (t1569_3 Step 1).
# The knee of the measured precision/recall curve: 20 -> 10 moves precision
# 26% -> 44%, while 10 -> 8 buys 3pp of precision for 5pp of recall.
HUB_THRESHOLD = 10

# In-flight surface resolutions that mean "this task could not be compared
# against at all". A blocking-eligible source in one of these states is an
# UNCHECKABLE cause, named per source so the consumer can offer a remedy.
_INVISIBLE_SURFACE = ("no_plan", "unreadable", "no_tokens", "all_phantom")

_DISPLAY_CLEAR = "no known conflict at check time"


@dataclass(frozen=True)
class Surface:
    """A task's file surface plus how well it is known."""

    ref: str
    provenance: str
    paths: tuple = ()          # RAW paths, codepoint-sorted; encoded at render
    resolution: str = "resolved"
    quality: str = "n/a"


@dataclass(frozen=True)
class SourceEvidence:
    """Health of one enumeration probe. Probe health only -- never a task fact."""

    name: str
    status: str = "ok"
    age_s: int = None
    reason: str = None


@dataclass(frozen=True)
class CorpusEvidence:
    """Health of one path-classification corpus (code branch / task-data branch)."""

    name: str
    status: str = "ok"
    n_files: int = 0
    reason: str = None


@dataclass(frozen=True)
class LockEvidence:
    mode: str = "allow-cached"
    state: str = "fetched"
    age_s: int = None
    reason: str = None


@dataclass(frozen=True)
class InflightClaim:
    """One task the checker must rule out.

    ``claim_at_s`` is the epoch second of the claim (a lock's ``locked_at``, or
    the task's ``updated_at`` for a status-only claim). The AGE is derived in
    ``decide`` from ``AdmissionInput.now`` so that clock-skew detection is pure
    and fixture-testable; ``claim_age_reason`` carries the collector's reason
    when the timestamp could not be read at all.
    """

    ref: str
    sources: tuple = ()
    task_status: str = "-"
    liveness: str = "unknown"
    same_host: bool = None       # None => unknown => liveness forced to "unknown"
    claim_at_s: int = None
    claim_age_reason: str = None   # "absent" | "malformed"  (None when readable)
    surface: Surface = None


@dataclass(frozen=True)
class AdmissionInput:
    candidate: Surface
    enumeration: tuple            # EXACTLY three: gate, lock, status
    inflight: tuple = ()
    locks: LockEvidence = field(default_factory=LockEvidence)
    corpora: tuple = ()
    touch_counts: dict = field(default_factory=dict)   # path -> DISTINCT tasks
    hub_threshold: int = HUB_THRESHOLD
    max_lock_age_s: int = None
    max_claim_age_s: int = MAX_CLAIM_AGE_S
    now: int = 0
    recovered_used: bool = False   # RECOVERED_* contributed a cause/caveat


@dataclass(frozen=True)
class AdmissionResult:
    verdict: str
    lines: tuple = ()


# --- tier -------------------------------------------------------------------


def claim_age(claim, now):
    """Return ``(age_s, unknown_reason)``.

    ``unknown_reason`` is one of the ``unknown_claim_age`` sub-vocabulary tokens
    when the age cannot be established, and ``None`` when ``age_s`` is valid.
    A future timestamp is ``clock_skew`` -- the same name t1569_1's
    ``_locks_cache_age`` gives it -- never a negative age.
    """
    if claim.claim_age_reason is not None:
        return None, claim.claim_age_reason
    if claim.claim_at_s is None:
        return None, "absent"
    age = now - claim.claim_at_s
    if age < 0:
        return None, "clock_skew"
    return age, None


def tier(claim, max_claim_age_s, now):
    """Overlap eligibility: ``blocking`` | ``advisory`` | ``excluded``.

    Derived, never stored -- keeping it a function of liveness and age is what
    makes the eligibility matrix a single expression the fixtures drive
    directly, instead of a property a collector could set inconsistently.

    Liveness OUTRANKS age: a provably-dead holder is excluded however recent its
    claim, because age cannot make a dead process concurrent. An UNKNOWN age
    keeps the source blocking-eligible -- "cannot miss a collision" is the
    conservative direction, and an unparseable timestamp must not become a back
    door that demotes a live holder.
    """
    check_member(claim.liveness, vocab.LIVENESS_CLASSES, "liveness")
    if claim.liveness == "dead":
        return "excluded"
    age, unknown = claim_age(claim, now)
    if unknown is not None:
        return "blocking"
    return "advisory" if age > max_claim_age_s else "blocking"


# --- decide -----------------------------------------------------------------


def _validate_enumeration(enumeration):
    """Exactly three probes, one per declared name.

    A missing, duplicated or unknown name is a PROGRAMMING error, not a content
    state: emitting a partial record set is precisely the silent-absence failure
    the completeness rule exists to prevent, so raise instead.
    """
    names = [e.name for e in enumeration]
    if sorted(names) != sorted(vocab.SOURCE_NAMES):
        raise VocabularyError(
            "enumeration must carry exactly one entry per %r, got %r"
            % (vocab.SOURCE_NAMES, names))
    for e in enumeration:
        check_member(e.status, vocab.SOURCE_STATUSES, "enumeration status")
    return {e.name: e for e in enumeration}


def _classify_overlap(path, touch_counts, hub_threshold):
    return "hub" if touch_counts.get(path, 0) >= hub_threshold else "specific"


def decide(inp):
    """Compute the verdict. Total over content states -- raises only on
    programming errors (an undeclared enum, an incomplete enumeration tuple).
    """
    by_name = _validate_enumeration(inp.enumeration)
    check_member(inp.candidate.provenance, vocab.PROVENANCES, "provenance")
    check_member(inp.locks.state, vocab.LOCK_STATES, "lock state")
    check_member(inp.locks.mode, vocab.LOCK_MODES, "lock mode")

    require_fresh = inp.locks.mode == "require-fresh"

    overlaps = []        # (ref, cls, n_tasks, path, tier)
    narrowed = {}        # path -> (cls, n_tasks)
    caveat_records = []  # (scope, code, param)   -- everything rendered
    verdict_caveats = [] # subset that actually drives CLEAR_CAVEATED
    causes = []          # (scope, code, param)
    inflight_rows = []

    def caveat(scope, code, param=None, drives=True):
        caveat_records.append((scope, code, param))
        if drives:
            verdict_caveats.append((scope, code, param))

    # --- corpora --------------------------------------------------------
    for c in sorted(inp.corpora, key=lambda c: c.name):
        check_member(c.name, vocab.CORPUS_NAMES, "corpus name")
        check_member(c.status, vocab.CORPUS_STATUSES, "corpus status")
        if c.status == "unavailable":
            # A classification run over a corpus that could not be read would
            # otherwise look healthy.
            caveat("corpus", "corpus_unavailable", c.name)

    # --- enumeration health ---------------------------------------------
    for name in vocab.SOURCE_NAMES:
        e = by_name[name]
        if e.status == "degraded":
            caveat("locks" if name == "lock" else "inflight:%s" % name,
                   "source_degraded", name)
        elif e.status in ("unavailable", "not_consulted"):
            # `not_consulted` is treated as `unavailable`: a probe that never
            # ran rules nothing out. In-flight work may exist that was never
            # listed, so this is never silent.
            if require_fresh:
                causes.append(("locks" if name == "lock" else "candidate",
                               "source_unavailable", name))
            else:
                caveat("locks" if name == "lock" else "inflight:%s" % name,
                       "source_unavailable", name)

    # --- candidate surface ----------------------------------------------
    cand = inp.candidate
    check_member(cand.resolution, vocab.SURFACE_RESOLUTIONS, "candidate resolution")
    if cand.resolution != "resolved":
        # An empty intersection is meaningless when the candidate side is
        # unknown, so this is UNCHECKABLE and never CLEAR.
        causes.append(("candidate", cand.resolution, None))

    # --- lock freshness --------------------------------------------------
    if inp.locks.state != "fetched":
        reason = inp.locks.reason
        if require_fresh:
            # Neither mode may report CLEAR on lock evidence it could not
            # establish; require-fresh refuses to proceed on a cached ref.
            causes.append(("locks", reason or "no_local_ref", None))
        elif inp.locks.state == "cached":
            days = 0 if inp.locks.age_s is None else inp.locks.age_s // 86400
            caveat("locks", "locks_cached", "%dd" % days)
        else:
            caveat("locks", "source_unavailable", "lock")
    elif require_fresh and inp.max_lock_age_s is not None \
            and inp.locks.age_s is not None and inp.locks.age_s > inp.max_lock_age_s:
        causes.append(("locks", "timeout", None))

    # --- in-flight sources -----------------------------------------------
    for claim in sorted(inp.inflight, key=lambda c: c.ref):
        t = tier(claim, inp.max_claim_age_s, inp.now)
        surf = claim.surface or Surface(claim.ref, "plan_declared", (), "no_plan")
        check_member(surf.resolution, vocab.SURFACE_RESOLUTIONS, "inflight resolution")
        n_paths = len(surf.paths)
        path_state = _path_state(surf)
        inflight_rows.append(
            (claim.ref, ",".join(claim.sources) or "-", claim.liveness,
             n_paths, path_state, t))

        if t == "excluded":
            # A provably-dead holder is not concurrent work, so its declared
            # surface is not evidence of anything. One INFLIGHT: row keeps the
            # exclusion visible rather than silent -- and nothing else.
            continue

        scope = "inflight:%s" % claim.ref

        if t == "blocking":
            if surf.resolution in _INVISIBLE_SURFACE:
                causes.append((scope, surf.resolution, None))
            elif surf.resolution != "resolved":
                causes.append((scope, surf.resolution, None))

        hit = sorted(set(cand.paths) & set(surf.paths))
        for p in hit:
            cls = _classify_overlap(p, inp.touch_counts, inp.hub_threshold)
            overlaps.append((claim.ref, cls, inp.touch_counts.get(p, 0), p, t))
            if cls == "hub":
                narrowed[p] = ("hub", inp.touch_counts.get(p, 0))

        if t == "advisory":
            # Reported so the age is visible, but it does NOT drive the verdict:
            # a months-old lock must not veto every future pick.
            age, _ = claim_age(claim, inp.now)
            caveat(scope, "stale_claim", "%dd" % ((age or 0) // 86400), drives=False)
            for (_r, _c, _n, p, _t) in [o for o in overlaps if o[0] == claim.ref]:
                caveat(scope, "stale_claim_overlap", p)
        else:
            _age, unknown = claim_age(claim, inp.now)
            if unknown is not None:
                caveat(scope, "unknown_claim_age", unknown)
            if claim.same_host is False or claim.same_host is None:
                if claim.liveness == "unknown":
                    caveat(scope, "cross_host_lock")
            if claim.liveness == "status_only":
                caveat(scope, "no_liveness_token")
            elif claim.liveness == "lock_only":
                caveat(scope, "lock_only_holder")
            elif claim.liveness == "unknown" and claim.same_host is True:
                caveat(scope, "unknown_liveness")

    if inp.recovered_used:
        # RECOVERED_* may name a cause or caveat a verdict, and may NEVER assert
        # a conflict or move a verdict toward CLEAR.
        caveat("candidate", "recovered_only")

    # --- aggregate --------------------------------------------------------
    blocking_specific = [o for o in overlaps if o[4] == "blocking" and o[1] == "specific"]
    hub_only = [o for o in overlaps if o[4] == "blocking" and o[1] == "hub"]

    if blocking_specific:
        verdict = "CONFLICT"
    elif causes:
        verdict = "UNCHECKABLE"
    else:
        for (ref, _cls, _n, p, _t) in hub_only:
            caveat("inflight:%s" % ref, "hub_overlap_only", p)
        verdict = "CLEAR_CAVEATED" if verdict_caveats else "CLEAR"

    if verdict == "CONFLICT":
        for (ref, _cls, _n, p, _t) in hub_only:
            caveat("inflight:%s" % ref, "hub_overlap_only", p, drives=False)

    lines = _render_lines(inp, by_name, inflight_rows, overlaps, narrowed,
                          caveat_records, causes, verdict, verdict_caveats)
    return AdmissionResult(verdict=verdict, lines=tuple(lines))


def _path_state(surf):
    if not surf.paths:
        return "none"
    return "resolved" if surf.resolution == "resolved" else "phantom"


# --- render -----------------------------------------------------------------


def _display(verdict, overlaps, causes, driving_caveats, inp):
    if verdict == "CONFLICT":
        refs = sorted({o[0] for o in overlaps if o[1] == "specific" and o[4] == "blocking"})
        files = sorted({o[3] for o in overlaps if o[1] == "specific" and o[4] == "blocking"})
        return ("conflict with %s on %d file(s): %s"
                % (", ".join(refs), len(files), ", ".join(files[:3])))
    if verdict == "UNCHECKABLE":
        named = sorted({"%s (%s)" % (s, c) for (s, c, _p) in causes})
        return "could not compare: " + "; ".join(named)
    if verdict == "CLEAR_CAVEATED":
        return ("%s, but evidence was unverified: %s"
                % (_DISPLAY_CLEAR,
                   "; ".join(sorted({c for (_s, c, _p) in driving_caveats}))))
    return "%s (max_claim_age=%ds, hub_threshold=%d)" % (
        _DISPLAY_CLEAR, inp.max_claim_age_s, inp.hub_threshold)


def _render_lines(inp, by_name, inflight_rows, overlaps, narrowed,
                  caveat_records, causes, verdict, driving_caveats):
    out = []
    for c in sorted(inp.corpora, key=lambda c: c.name):
        out.append("CORPUS:%s|%s|%d|%s"
                   % (c.name, c.status, c.n_files, c.reason or "-"))
    # Emitted unconditionally and exactly once each, in this fixed order. A
    # probe that never ran reports `not_consulted`, never absence.
    for name in vocab.SOURCE_NAMES:
        e = by_name[name]
        out.append("INFLIGHT_SOURCE:%s|%s|%s|%s"
                   % (e.name, e.status,
                      "-" if e.age_s is None else e.age_s, e.reason or "-"))
    cand = inp.candidate
    resolved = ("resolved" if cand.resolution == "resolved"
                else "unresolved:%s" % cand.resolution)
    out.append("CANDIDATE:%s|%s|%d|%s|%s"
               % (cand.ref, cand.provenance, len(cand.paths), resolved,
                  check_member(cand.quality, vocab.ORIGIN_QUALITIES, "quality")))
    out.append("LOCKS:%s|%s|%s"
               % (inp.locks.state,
                  "-" if inp.locks.age_s is None else inp.locks.age_s,
                  inp.locks.reason or "-"))
    for (ref, sources, liveness, n_paths, path_state, _t) in inflight_rows:
        out.append("INFLIGHT:%s|%s|%s|%d|%s"
                   % (ref, sources,
                      check_member(liveness, vocab.LIVENESS_CLASSES, "liveness"),
                      n_paths,
                      check_member(path_state, vocab.PATH_STATES, "path state")))
    for (ref, cls, n, p, _t) in sorted(overlaps, key=lambda o: (o[0], o[3])):
        out.append("OVERLAP:%s|%s|%d|%s"
                   % (ref, check_member(cls, vocab.OVERLAP_CLASSES, "overlap class"),
                      n, encode_path(p)))
    for p in sorted(narrowed):
        cls, n = narrowed[p]
        out.append("NARROWED:%s|%s|%d"
                   % (encode_path(p),
                      check_member(cls, vocab.NARROWED_CLASSES, "narrowed class"), n))
    for (scope, code, param) in sorted(set(caveat_records)):
        out.append("CAVEAT:%s|%s" % (scope, vocab.format_reason("CAVEAT", code, param)))
    for (scope, code, param) in sorted(set(causes)):
        out.append("UNCHECKABLE_CAUSE:%s|%s"
                   % (scope, vocab.format_reason("UNCHECKABLE_CAUSE", code, param)))
    out.append("DISPLAY:" + _display(verdict, overlaps, causes, driving_caveats, inp))
    out.append("VERDICT:" + check_member(verdict, vocab.VERDICTS, "verdict"))
    return out


def render(result):
    """Render an AdmissionResult to the line protocol (trailing newline)."""
    return "".join(line + "\n" for line in result.lines)


# --- adapters ---------------------------------------------------------------
# Parsing text is pure, so these live in the core. They are what let t1569_5
# build an AdmissionInput from already-materialised gatherer / batch-map output
# and call `decide` directly -- no subprocess, no second definition of "safe".
#
# t1569_2 emits paths RAW (it protects only its NUL-framed input), so every
# parse below is right-to-left or bounded-prefix. A left-to-right split would
# corrupt any path containing `|`.

_RESOLVED_CLASSES = ("tracked", "planned_new", "untracked_data")
_SENTINELS = ("no_plan", "no_tokens", "unreadable", "unclassified")


def _strip(prefix, line):
    return line[len(prefix):] if line.startswith(prefix) else None


def touch_counts_from_batch_map(lines):
    """``COMMIT:`` rows -> ``{path: distinct-task count}``.

    The row count is a COMMIT count and is the WRONG number -- a path touched
    twice by one task would count 2. Union the task ids instead.

    The result is a systematic LOWER BOUND: 78% of commits in this repo name no
    task, and those rows contribute nothing. Under-counting makes narrowing
    under-aggressive, which is the safe direction, but it is not a true touch
    count.
    """
    seen = {}
    for line in lines:
        rest = _strip("COMMIT:", line.rstrip("\n"))
        if rest is None:
            continue
        parts = rest.rsplit("|", 3)
        if len(parts) != 4:
            continue
        path, _sha, _ct, ids = parts
        bucket = seen.setdefault(path, set())
        for tid in ids.split(","):
            if tid:
                bucket.add(tid)
    return {p: len(v) for p, v in seen.items()}


def surfaces_from_batch_map(lines, ids=None):
    """``TASKFILES:`` / ``STATUS:`` rows -> ``{task_id: Surface}`` (origin-derived).

    ``STATUS:<id>|UNKNOWN_HISTORY`` means "unrecognized by the oracle's
    disk-derived expansion", NOT "touched no files" -- so it becomes an
    unresolved surface, never an empty-but-resolved one, which would be a false
    no-conflict.
    """
    paths, states = {}, {}
    for line in lines:
        line = line.rstrip("\n")
        rest = _strip("TASKFILES:", line)
        if rest is not None:
            tid, _, path = rest.partition("|")
            paths.setdefault(tid, set()).add(path)
            continue
        rest = _strip("STATUS:", line)
        if rest is not None:
            tid, _, state = rest.partition("|")
            states[tid] = state
    wanted = set(ids) if ids is not None else set(states) | set(paths)
    out = {}
    for tid in sorted(wanted):
        state = states.get(tid, "UNKNOWN_HISTORY")
        if state == "UNKNOWN_HISTORY":
            res = "unknown_history"
        elif state == "NO_FILES":
            res = "no_extractable_paths"
        else:
            res = "resolved"
        out[tid] = Surface(ref=tid, provenance="origin_derived",
                           paths=tuple(sorted(paths.get(tid, ()))),
                           resolution=res, quality="n/a")
    return out


def surfaces_from_inflight_records(lines, local_name=None, data_tracked=None):
    """Gatherer ``INFLIGHT_PATH:`` rows -> ``{ref: Surface}`` (plan-declared).

    ``planned_new`` counts as RESOLVED: it is a legitimately planned new file,
    not a phantom. Treating it otherwise would report ``all_phantom`` for a plan
    that only creates files.

    ``data_tracked`` is the set of paths tracked on the task-data branch. The
    gatherer classifies against ``git ls-files`` on the CODE branch, where
    ``aitasks/`` and ``aiplans/`` are gitignored symlinks and therefore track
    ZERO paths -- so every task-data path arrives here marked ``phantom``.
    Passing the set reclassifies them, which is what stops two tasks editing the
    same profile YAML from reporting no conflict. Omitting it reproduces the
    upstream blind spot, so callers on the injected path must supply it.
    """
    resolved, phantom, sentinel = {}, {}, {}
    for line in lines:
        rest = _strip("INFLIGHT_PATH:", line.rstrip("\n"))
        if rest is None:
            continue
        ref, _, tail = rest.partition("|")
        cls, _, path = tail.partition("|")
        if local_name and ref.startswith(local_name + "#"):
            ref = ref.split("#", 1)[1]
        if cls in _SENTINELS:
            sentinel[ref] = cls
        elif cls in _RESOLVED_CLASSES:
            resolved.setdefault(ref, set()).add(path)
        elif cls == "phantom" and data_tracked and path in data_tracked:
            resolved.setdefault(ref, set()).add(path)
        else:
            phantom.setdefault(ref, set()).add(path)
    out = {}
    for ref in sorted(set(resolved) | set(phantom) | set(sentinel)):
        if ref in sentinel:
            res, paths = sentinel[ref], ()
        elif resolved.get(ref):
            res, paths = "resolved", tuple(sorted(resolved[ref]))
        else:
            res, paths = "all_phantom", ()
        out[ref] = Surface(ref=ref, provenance="plan_declared", paths=paths,
                           resolution=res, quality="n/a")
    return out


def input_from_records(candidate_ref, candidate_surface, inflight_lines,
                       batch_map_lines, enumeration=None, inflight_claims=None,
                       locks=None, corpora=(), now=0, data_tracked=None,
                       hub_threshold=HUB_THRESHOLD,
                       max_claim_age_s=MAX_CLAIM_AGE_S, max_lock_age_s=None,
                       recovered_used=False):
    """Assemble an AdmissionInput from materialised records.

    The candidate is EXCLUDED from every source here, before overlap is ever
    evaluated -- not filtered from the results afterwards. task-workflow claims
    the candidate at its Step 4 (status Implementing AND the lock) long before
    the plan exists, so without this the candidate overlaps 100% of its own plan
    and every pick is a CONFLICT. A post-filter would leave the INFLIGHT: rows
    and the replay counts wrong, and the next reader would re-introduce the bug.
    """
    key = canonical_ref(candidate_ref)
    surfaces = surfaces_from_inflight_records(
        inflight_lines, data_tracked=data_tracked)
    # Canonicalise BOTH sides of the lookup. The gatherer spells refs
    # `<project>#t<id>` / `t<id>`, the claims may spell them bare; comparing a
    # canonical key against a raw one silently finds nothing, and a missing
    # surface reads as `no_plan` -- an UNCHECKABLE that looks like a real
    # evidence gap rather than the lookup bug it is.
    surfaces = {canonical_ref(k): v for k, v in surfaces.items()}
    touch = touch_counts_from_batch_map(batch_map_lines)
    claims = []
    for c in (inflight_claims or ()):
        if canonical_ref(c.ref) == key:
            continue
        surf = c.surface or surfaces.get(canonical_ref(c.ref))
        claims.append(c if surf is c.surface else _with_surface(c, surf))
    if enumeration is None:
        enumeration = tuple(SourceEvidence(n) for n in vocab.SOURCE_NAMES)
    return AdmissionInput(
        candidate=candidate_surface,
        enumeration=tuple(enumeration),
        inflight=tuple(claims),
        locks=locks or LockEvidence(),
        corpora=tuple(corpora),
        touch_counts=touch,
        hub_threshold=hub_threshold,
        max_lock_age_s=max_lock_age_s,
        max_claim_age_s=max_claim_age_s,
        now=now,
        recovered_used=recovered_used,
    )


def _with_surface(claim, surface):
    return InflightClaim(
        ref=claim.ref, sources=claim.sources, task_status=claim.task_status,
        liveness=claim.liveness, same_host=claim.same_host,
        claim_at_s=claim.claim_at_s, claim_age_reason=claim.claim_age_reason,
        surface=surface or Surface(claim.ref, "plan_declared", (), "no_plan"))


def canonical_ref(ref):
    """Normalise a task ref for identity comparison.

    Accepts ``aitasks#1569_3``, ``t1569_3``, ``1569_3``. The project prefix is
    stripped and a leading ``t`` dropped, because the candidate may be a child
    and the three sources spell refs differently.
    """
    ref = str(ref)
    if "#" in ref:
        ref = ref.split("#", 1)[1]
    if ref.startswith("t") and ref[1:2].isdigit():
        ref = ref[1:]
    return ref
