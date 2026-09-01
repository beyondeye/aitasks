"""Premise-drift signal for the background-work roadmap (t1569_5).

Has a follow-up's premise churned since its origin landed? Deliberately narrow,
deliberately advisory, and deliberately **replaceable**.

THIS IS NOT A STALENESS FRAMEWORK, AND MUST NOT BECOME ONE. t1561 generalizes
task staleness for every task type; when it lands, the roadmap drops this module
and consumes t1561's mechanism instead. That substitution is the reason the
public surface is frozen in ``__all__`` -- two functions, two records, three
decisions, the reason vocabularies and one default -- and why
``tests/test_roadmap_premise.py::PublicSurfaceTests`` fails the moment a name
appears that ``__all__`` does not list. Growing this module is how the framework
ends up with two permanent staleness mechanisms, which is the outcome the
roadmap's design record forbids.

PURE. No ``os``, no ``time``, no ``subprocess``, no I/O. Every input arrives as
already-materialised text (t1569_2's ``--batch-map`` records), which is what
lets the verdict be byte-deterministic over a frozen fixture.
``tests/test_parallel_admission_purity.py`` enforces it; the caller is
responsible for having ``.aitask-scripts/lib`` on ``sys.path``.

CONVENTIONS BORROWED FROM ``aitask_verification_stale.sh`` -- conventions only.
That helper reads its scope from ``file_references:`` (0 of 483 active tasks
carry it) and its baseline from ``verification_baseline:`` (absent on
follow-ups), so neither of its inputs exists here; only the protocol shape is
reused:

* line protocol, one record per line, free-ish field LAST;
* every content state returns -- only programming errors raise;
* tri-state ``FRESH`` / ``ASK_STALE`` / ``SKIP``, with ``SKIP`` fail-open;
* **``UNKNOWN`` drives the verdict, it is not advisory.** A path that cannot be
  checked means the check covers *less* scope than it claims, so reporting
  ``FRESH`` would be a false all-clear. Implemented the way the shell helper
  does it -- ``UNKNOWN`` records go into the *same* evidence list as ``CHANGED``
  and the verdict is an emptiness test on that list, so the two can never drift
  apart;
* ``%``-then-``|`` injective encoding, via ``vocab.encode_path`` rather than a
  second copy of the rule.

TWO ACCEPTED NARROWINGS, both stated so a reader does not go looking for them:

1. **No ``DELETED:`` record.** The ``COMMIT:`` index records paths *touched*,
   not whether a commit deleted them, so a deletion surfaces as ``CHANGED:``.
   That is a smaller claim than the shell helper's, not a silent one.
2. **No ``:(literal)`` pathspec guard.** That guard exists because git
   fnmatch-globs a pathspec; this module runs no git and compares paths as
   opaque strings, so there is nothing to glob.

WHAT COUNTS AS THE BASELINE. The origin's newest **landing** commit -- not
merely its newest ``(tNN)``-tagged commit. ``ait git commit`` tags task-data
commits the same way, and measured over this repo's whole history (2026-08-31)
61 of 1714 tagged commits touch no code path while 35 of 1615 tagged ids have a
metadata-only *newest* tagged commit. Taking those would move the baseline
forward past real code changes, which would then read as pre-baseline and be
silently reported ``FRESH``.
"""

from dataclasses import dataclass, field

import parallel_admission_vocab as vocab

# The substitution contract with t1561. Pinned by PublicSurfaceTests -- adding a
# name here is a deliberate widening of what t1561 must replace, never a tidy-up.
__all__ = [
    "FRESH", "ASK_STALE", "SKIP", "DECISIONS",
    "BASELINE_REASONS", "PATH_REASONS", "SCOPE_REASONS", "REASONS",
    "DEFAULT_DATA_PREFIXES",
    "Baseline", "PremiseResult",
    "baseline_for", "check",
]

FRESH = "FRESH"
ASK_STALE = "ASK_STALE"
SKIP = "SKIP"
DECISIONS = (FRESH, ASK_STALE, SKIP)

# Why no baseline could be computed. Closed vocabulary; each is a distinct
# remedy, which is the whole reason they are not one "no baseline" bucket.
BASELINE_REASONS = (
    "no_origin",         # the follow-up resolved to no origin at all
    "unknown_history",   # origin known, but no `(tNN)`-tagged commit anywhere
    "metadata_only",     # tagged commits exist, every one of them task-data
)

# Why one curated path could not be checked. Both drive the verdict.
PATH_REASONS = (
    "no_index_history",    # the path has no COMMIT row at all in the index
    "absent_at_baseline",  # rows exist, but none at or before the baseline
)

# Why the check covered nothing even though a baseline existed.
SCOPE_REASONS = (
    "empty_scope",         # the candidate has no known file surface to check
)

REASONS = BASELINE_REASONS + PATH_REASONS + SCOPE_REASONS

# Trees that hold task data rather than code. A commit touching only these is
# not a landing. Injected rather than hardcoded at the use site because
# TASK_DIR / PLAN_DIR are configurable -- a pure module must not assume one
# deployment's layout.
DEFAULT_DATA_PREFIXES = ("aitasks/", "aiplans/", ".aitask-gates/")


@dataclass(frozen=True)
class Baseline:
    """The origin's last landing commit, or why there is none."""

    sha: str = None
    committed_at: int = None
    reason: str = None      # one of BASELINE_REASONS when sha is None

    @property
    def resolved(self):
        return self.sha is not None


@dataclass(frozen=True)
class PremiseResult:
    decision: str
    baseline: Baseline
    changed: tuple = ()     # (path, n_commits, task_ids tuple)
    unknown: tuple = ()     # (path, reason)
    lines: tuple = field(default_factory=tuple)
    reason: str = None      # a SCOPE_REASONS value, or the baseline's reason


def _commit_rows(commit_lines):
    """``COMMIT:<path>|<sha>|<ct>|<ids csv>`` -> ``(path, sha, ct, ids)``.

    Paths are emitted RAW by t1569_2 (it protects only its NUL-framed input), so
    the split is right-to-left with a bounded count: a path containing ``|``
    would corrupt any left-to-right parse. A malformed row is skipped rather
    than raised on -- this is a content state, and the caller's own evidence
    lines already report what could not be checked.
    """
    for line in commit_lines:
        line = line.rstrip("\n")
        if not line.startswith("COMMIT:"):
            continue
        parts = line[len("COMMIT:"):].rsplit("|", 3)
        if len(parts) != 4:
            continue
        path, sha, ct, ids = parts
        try:
            ct = int(ct)
        except ValueError:
            continue
        yield path, sha, ct, tuple(i for i in ids.split(",") if i)


def baseline_for(origin_ids, commit_lines, data_prefixes=DEFAULT_DATA_PREFIXES):
    """The origin's newest LANDING commit, or a Baseline naming why there is none.

    A landing commit is one that names an origin id AND touches at least one
    path outside ``data_prefixes``. Ties on ``committed_at`` break on the sha so
    the answer is total and deterministic.
    """
    return _baseline_from_rows(_commit_rows(commit_lines), origin_ids,
                               data_prefixes)


def _baseline_from_rows(rows, origin_ids, data_prefixes):
    wanted = {str(o) for o in (origin_ids or ()) if str(o)}
    if not wanted:
        return Baseline(reason="no_origin")

    prefixes = tuple(data_prefixes)
    tagged = False
    landing = set()
    for path, sha, ct, ids in rows:
        if wanted.isdisjoint(ids):
            continue
        tagged = True
        if not path.startswith(prefixes):
            landing.add((ct, sha))

    if landing:
        ct, sha = max(landing)
        return Baseline(sha=sha, committed_at=ct)
    return Baseline(reason="metadata_only" if tagged else "unknown_history")


def check(origin_ids, origin_paths, commit_lines,
          baseline=None, data_prefixes=DEFAULT_DATA_PREFIXES):
    """Has anything in ``origin_paths`` churned since the origin landed?

    ``baseline`` is computed by :func:`baseline_for` when not supplied. An
    uncomputable baseline is ``SKIP`` -- fail-open and silent -- never a
    fabricated one.
    """
    rows = list(_commit_rows(commit_lines))
    if baseline is None:
        baseline = _baseline_from_rows(rows, origin_ids, data_prefixes)

    paths = sorted({str(p) for p in (origin_paths or ()) if str(p)})
    head = [_baseline_line(baseline), "FILES:%d" % len(paths)]

    if not baseline.resolved:
        return _result(SKIP, baseline, (), (), head + [
            "DISPLAY:premise not checked (%s) — no landing commit for the origin."
            % baseline.reason], reason=baseline.reason)

    if not paths:
        # A RESOLVED baseline over an EMPTY scope checked nothing, so `FRESH`
        # here would be the module's own false all-clear -- "all 0 files
        # unchanged" reads as verified and would raise the confidence ceiling to
        # `high`. `SKIP` is the honest state: fail-open, silent, and capped.
        # It is not ASK_STALE either -- there is no evidence the premise moved,
        # only an absence of anything to check.
        return _result(SKIP, baseline, (), (),
                       head + ["UNCHECKED:empty_scope",
                               "DISPLAY:premise not checked — the candidate has "
                               "no known file surface, so nothing was compared."],
                       reason="empty_scope")

    by_path = {}
    for path, sha, ct, ids in rows:
        by_path.setdefault(path, []).append((ct, ids))

    changed, unknown, evidence = [], [], []
    for p in paths:
        seen = by_path.get(p)
        if not seen:
            unknown.append((p, "no_index_history"))
            evidence.append("UNKNOWN:%s|no_index_history" % vocab.encode_path(p))
            continue
        if not any(ct <= baseline.committed_at for ct, _ in seen):
            unknown.append((p, "absent_at_baseline"))
            evidence.append("UNKNOWN:%s|absent_at_baseline" % vocab.encode_path(p))
            continue
        later = [ids for ct, ids in seen if ct > baseline.committed_at]
        if later:
            tids = tuple(sorted({t for ids in later for t in ids}))
            changed.append((p, len(later), tids))
            evidence.append("CHANGED:%s|%d|%s"
                            % (vocab.encode_path(p), len(later), ",".join(tids)))

    # UNKNOWN and CHANGED share one evidence list on purpose: the verdict is an
    # emptiness test over it, so "a path I could not check" can never quietly
    # stop counting while "a path that changed" still does.
    if not evidence:
        return _result(FRESH, baseline, (), (), head + [
            "DISPLAY:all %d origin file(s) unchanged since %s — premise looks current."
            % (len(paths), baseline.sha[:9])])

    return _result(ASK_STALE, baseline, tuple(changed), tuple(unknown),
                   head + evidence + [_stale_display(baseline, changed, unknown)])


def _baseline_line(baseline):
    if not baseline.resolved:
        return "BASELINE:NONE"
    return "BASELINE:%s|%d" % (vocab.encode_path(baseline.sha),
                               baseline.committed_at)


def _stale_display(baseline, changed, unknown):
    """DISPLAY names the two causes separately -- the remedies differ."""
    bits = []
    if changed:
        bits.append("%d file(s) changed since %s: %s"
                    % (len(changed), baseline.sha[:9],
                       ", ".join(p for p, _, _ in changed[:3])))
    if unknown:
        bits.append("%d file(s) could not be checked: %s"
                    % (len(unknown), ", ".join(p for p, _ in unknown[:3])))
    return "DISPLAY:premise may no longer hold — " + "; ".join(bits)


def _result(decision, baseline, changed, unknown, lines, reason=None):
    lines = tuple(lines) + ("DECISION:%s" % decision,)
    return PremiseResult(decision=decision, baseline=baseline,
                         changed=changed, unknown=unknown, lines=lines,
                         reason=reason)
