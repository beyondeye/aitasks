"""Background-work roadmap driver (t1569_6) -- the IMPURE half.

Wires the five landed t1569 slices into one run and emits a complete
``implementation_trail`` document:

    candidates -> wide snapshot (+in-flight) -> origin facts
              -> ONE admission collection, re-aimed per candidate
              -> premise drift -> score -> cap -> narrow snapshot -> encode

Everything that RANKS, HEDGES or CLASSIFIES lives in ``roadmap_policy`` /
``roadmap_premise``, which are pure and stay that way. This module owns the
subprocesses and the filesystem, exactly as ``parallel_admission_collect`` does
for the checker, and is deliberately ABSENT from ``PURE_MODULES`` in
``tests/test_parallel_admission_purity.py``.

EXIT STATUS follows ``aitask_backlog_origin_facts.sh``: every *content* state
exits 0 -- an empty corpus is an answer -- while CLI misuse exits 2 and a
refusal to publish on unsound evidence exits 3. A silent empty result for a typo
is the hazard ``aitask_verification_stale.sh:26-32`` records.

WHY A REFUSAL EXIT EXISTS AT ALL. The checker already hedges per candidate:
``decide`` names its ``UNCHECKABLE_CAUSE:`` scopes and ``roadmap_policy`` turns
those into lanes, confidence and caveats. Two conditions are NOT per-candidate
and so cannot be hedged that way -- an unavailable corpus makes every path
classification wrong, and a missing ``ORIGIN_FACT:`` row means the collector
broke rather than that a task has no origin. Publishing a plausible ranking
built on either would understate uncertainty everywhere at once.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import parallel_admission as pa                 # noqa: E402
import parallel_admission_collect as col        # noqa: E402
import roadmap_policy as rp                     # noqa: E402
import roadmap_premise as premise               # noqa: E402

_SCRIPTS_DIR = os.path.dirname(_LIB_DIR)

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_REFUSED = 3

DEFAULT_CAP = 40
TRAIL_ID = "trail-backlog-roadmap"
DEFAULT_TITLE = "Background-work roadmap"

# `narrative` is `additionalProperties: false` in the schema, so an unexpected
# key must be refused HERE with a named error rather than surfacing as an opaque
# validation failure after the document is built.
NARRATIVE_REQUIRED = ("problem_statement", "recommendation_summary")
NARRATIVE_OPTIONAL = ("overview",)

# `ait ls` renders a task filename; the id is the part between `t` and the first
# `_`. A file that carries no number at all (one exists in this repo today)
# yields NO id -- it is reported, never silently dropped and never passed on as
# an empty ref, which would make the snapshot ask about a task that cannot exist.
_TASK_FILE_ID_RE = re.compile(r"^t(\d+(?:_\d+)?)_.*\.md$")

_LS = os.path.join(_SCRIPTS_DIR, "aitask_ls.sh")
_GATHER = os.path.join(_SCRIPTS_DIR, "aitask_trail_gather.sh")
_ORIGIN_FACTS = os.path.join(_SCRIPTS_DIR, "aitask_backlog_origin_facts.sh")

# Module-level seams, following the `trail_gather._GATE_PROBE` convention so
# tests can rebind them without a subprocess.
_RUN = None            # set below; indirection kept for test rebinding


def _run(args, cwd, timeout=300):
    """Run a helper, returning ``(rc, stdout)``. Never raises on a non-zero exit."""
    try:
        proc = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout)
    except (OSError, subprocess.SubprocessError):
        return 1, ""
    return proc.returncode, proc.stdout.decode("utf-8", "replace")


_RUN = _run


# --- candidate enumeration ---------------------------------------------------

def enumerate_candidates(root):
    """``(ids, unparsable)`` -- the corpus, parents only.

    Ready tasks carrying a ``followup_kind:``, plus Ready genuine work at
    ``effort: low``. `aitask_ls.sh` lists PARENTS only, which is the corpus this
    roadmap is scoped to: a child is usually gated by its siblings, so ranking
    it as independently-startable background work would mislead.

    ``unparsable`` carries every listed filename with no task number. Reporting
    it is the point -- an empty id passed into the snapshot asks about a task
    that cannot exist, and dropping it silently would make the corpus count
    quietly disagree with the board.
    """
    ids, unparsable = [], []

    def _collect(argv, keep):
        rc, out = _RUN([_LS] + argv, cwd=root)
        if rc != 0:
            return
        for line in out.splitlines():
            line = line.strip()
            if not line or not keep(line):
                continue
            name = line.split(" ", 1)[0]
            m = _TASK_FILE_ID_RE.match(name)
            if m is None:
                unparsable.append(name)
            else:
                ids.append(m.group(1))

    # Follow-ups: `-v` renders the `Follow-up:` segment only for auto-spawned
    # tasks, so its presence IS the predicate -- no second lookup needed.
    _collect(["-v", "-s", "Ready", "9999"], lambda l: "Follow-up:" in l)
    # Genuine low-effort work. "Has children" is a parent whose children carry
    # the work, so it is not itself startable.
    _collect(["-v", "-s", "Ready", "--no-followup-kind", "9999"],
             lambda l: "Effort: Low" in l and "Has children" not in l)

    return sorted(set(ids), key=_numeric_key), sorted(set(unparsable))


def _numeric_key(task_id):
    """Sort `12_3` after `12` and both before `13`, numerically."""
    return tuple(int(p) for p in task_id.split("_"))


# --- snapshots ---------------------------------------------------------------

def snapshot(root, ids, with_inflight):
    """Gatherer records for ``ids``. Returns ``(rc, lines)``."""
    argv = [_GATHER, "snapshot", "--scope", "task"]
    if with_inflight:
        argv.append("--with-inflight")
    argv.extend(ids)
    rc, out = _RUN(argv, cwd=root)
    return rc, out.splitlines()


def origin_facts(root, ids):
    rc, out = _RUN([_ORIGIN_FACTS] + list(ids), cwd=root)
    return rc, out.splitlines()


def source_health(lines):
    """``{name: (status, reason)}`` from ``INFLIGHT_SOURCE:`` records."""
    health = {}
    for line in lines:
        if not line.startswith("INFLIGHT_SOURCE:"):
            continue
        parts = line[len("INFLIGHT_SOURCE:"):].split("|")
        if len(parts) >= 4:
            health[parts[0]] = (parts[1], parts[3])
    return health


# --- narrative ---------------------------------------------------------------

class NarrativeError(Exception):
    """A named refusal -- the message reaches the user verbatim."""


def load_narrative(path):
    """Validate the skill-authored prose BEFORE anything is encoded.

    The ordering is the contract: `to_trail` takes `narrative` as an argument
    and the schema requires two of its keys, so there is no post-hoc injection
    point. Validating here turns a malformed file into a named CLI error instead
    of an opaque schema failure after a full pipeline run.

    `method_note` is NOT accepted from the caller -- it is composed from the
    measured corpus below. A hand-written one would either need counts the skill
    has not been told, or drift from the document it describes.
    """
    if not path:
        raise NarrativeError("--narrative is required")
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except OSError as exc:
        raise NarrativeError("--narrative: cannot read %s: %s" % (path, exc))
    except ValueError as exc:
        raise NarrativeError("--narrative: %s is not valid JSON: %s"
                             % (path, exc))
    if not isinstance(data, dict):
        raise NarrativeError("--narrative: expected a JSON object, got %s"
                             % type(data).__name__)

    allowed = set(NARRATIVE_REQUIRED) | set(NARRATIVE_OPTIONAL)
    extra = sorted(set(data) - allowed)
    if extra:
        raise NarrativeError(
            "--narrative: unexpected key(s) %s; narrative accepts %s "
            "(method_note is composed from the measured corpus, not supplied)"
            % (", ".join(extra), ", ".join(sorted(allowed))))
    for key in NARRATIVE_REQUIRED:
        if key not in data:
            raise NarrativeError("--narrative: missing required key %r" % key)
    for key, value in data.items():
        if not isinstance(value, str) or not value.strip():
            raise NarrativeError(
                "--narrative: %r must be a non-empty string carrying a "
                "non-whitespace character" % key)
    return dict(data)


def method_note(corpus_size, published, cap, unparsable):
    """The factual half of the narrative, composed from what was measured."""
    if published < corpus_size:
        selection = ("Ranked all %d candidates by the policy sort key and "
                     "published the top %d (cap %d); the remaining %d are not "
                     "enumerated in this document."
                     % (corpus_size, published, cap, corpus_size - published))
    else:
        selection = ("Ranked and published all %d candidates; the corpus is "
                     "smaller than the cap of %d, so no selection was applied."
                     % (corpus_size, cap))
    note = (
        "Corpus: Ready tasks carrying a followup_kind, plus Ready genuine work "
        "at effort: low, parent tasks only. %s "
        "Lanes are an estimate from origin/topic evidence and in-flight state "
        "as of this run; the checker observes and reserves nothing, so CLEAR "
        "means no known conflict at check time." % selection)
    if unparsable:
        note += (" %d listed task file(s) carry no task number and were "
                 "excluded from the corpus: %s."
                 % (len(unparsable), ", ".join(unparsable)))
    return note


# --- the pipeline ------------------------------------------------------------

def _iso(ts):
    return datetime.datetime.fromtimestamp(
        ts, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _generation(lines, agent_string, now):
    """`generation` built from the NARROW snapshot's digest and inputs.

    Load-bearing: `cmd_drift` recomputes over `generation.inputs`, so building
    this from the wide snapshot would make every unpublished candidate a drift
    source and the trail would report STALE on churn it does not describe.
    """
    digest, inputs = None, []
    for line in lines:
        if line.startswith("DIGEST:"):
            digest = line[len("DIGEST:"):]
        elif line.startswith("INPUT:"):
            # `INPUT:<kind>|...|<ref>` -- the two kinds carry DIFFERENT field
            # counts (task_file 6, plan_file 4) and the ref is the free-ish
            # LAST field in both, so it is taken from the right, never by index.
            body = line[len("INPUT:"):]
            kind = body.split("|", 1)[0]
            ref = body.rsplit("|", 1)[-1]
            if kind and ref:
                inputs.append({"kind": kind, "ref": ref})
    return {
        "generated_at": _iso(now),
        "generator": {"agent_string": agent_string,
                      "skill": "aitask-backlog-roadmap"},
        "input_digest": digest or "",
        "inputs": inputs,
    }


def run(root, narrative_path, owner, out_path, title=DEFAULT_TITLE,
        cap=DEFAULT_CAP, agent_string="claudecode/opus5", now=None):
    """The whole pipeline. Returns ``(exit_code, report_lines)``."""
    now = int(time.time()) if now is None else int(now)
    report = []

    narrative = load_narrative(narrative_path)      # raises NarrativeError

    ids, unparsable = enumerate_candidates(root)
    for name in unparsable:
        report.append("UNPARSABLE_TASK_FILE:%s" % name)
    if not ids:
        report.append("CORPUS:0|0")
        report.append("EMPTY:no candidates -- nothing published")
        return EXIT_OK, report

    rc, wide = snapshot(root, ids, with_inflight=True)
    if rc != 0:
        report.append("REFUSED:snapshot_failed|wide snapshot exited %d" % rc)
        return EXIT_REFUSED, report
    health = source_health(wide)
    for name, (status, reason) in sorted(health.items()):
        report.append("SOURCE:%s|%s|%s" % (name, status, reason))

    candidates = rp.parse_members(wide)
    if not candidates:
        report.append("REFUSED:no_members|the snapshot returned no MEMBER "
                      "records for %d requested id(s)" % len(ids))
        return EXIT_REFUSED, report

    # Origin facts are asked about the MEMBERS THE SNAPSHOT RETURNED, not the
    # ids we requested. The gatherer expands a requested parent into the parent
    # AND its children (measured: 245 requested -> 255 members, t1157 alone
    # contributing 10), and the members are what get scored -- so asking about
    # the request set would leave every expanded child with no ORIGIN_FACT row
    # and trip the incompleteness refusal below on the driver's own omission.
    member_task_ids = sorted({c.task_id for c in candidates.values()},
                             key=_numeric_key)
    rc, fact_lines = origin_facts(root, member_task_ids)
    if rc != 0:
        report.append("REFUSED:origin_facts_failed|collector exited %d" % rc)
        return EXIT_REFUSED, report
    origin_rows = rp.parse_origin_facts(fact_lines)

    # A task with no resolvable origin still gets exactly one row
    # (`source=absent`), so a MISSING row means the collector broke. Never let
    # `reduce_origin_facts({})` quietly degrade it to the `unknown` band -- that
    # would infer a fact from an absent line, which the collector's own header
    # forbids.
    missing = sorted(ref for ref, c in candidates.items()
                     if c.task_id not in origin_rows)
    if missing:
        report.append(
            "REFUSED:origin_facts_incomplete|%d candidate(s) have no "
            "ORIGIN_FACT row: %s" % (len(missing), ", ".join(missing[:10])))
        return EXIT_REFUSED, report

    population = col.collect_population(
        root, [c.task_id for c in candidates.values()], source="origin")

    # An unavailable corpus is not a per-candidate hedge: every path
    # classification is wrong at once, so the ranking as a whole is unsound.
    unavailable = [c.name for c in population.corpora
                   if getattr(c, "status", None) == "unavailable"]
    if unavailable:
        report.append("REFUSED:corpus_unavailable|%s" % ",".join(unavailable))
        return EXIT_REFUSED, report

    inflight_paths = population.inflight_paths()
    admission, premises, candidate_paths = {}, {}, {}
    for ref, candidate in candidates.items():
        key = pa.canonical_ref(candidate.task_id)
        surface = population.surfaces.get(key)
        if surface is None:
            surface = pa.Surface(ref=candidate.task_id,
                                 provenance="origin_derived",
                                 resolution="unknown_origin")
        candidate_paths[ref] = set(surface.paths)
        admission[ref] = pa.decide(population.aim(candidate.task_id, surface))
        origins = [row[0] for row in origin_rows.get(candidate.task_id, ())
                   if row[0]]
        premises[ref] = premise.check(origins, surface.paths,
                                      population.batch_lines)

    now_ord = rp.day_ordinal(
        datetime.datetime.fromtimestamp(
            now, datetime.timezone.utc).strftime("%Y-%m-%d %H:%M"))
    roadmap = rp.build(candidates, origin_rows, admission, premises,
                       candidate_paths, inflight_paths, now_ord)

    corpus_size = len(roadmap.entries)
    published = roadmap.entries[:cap]
    report.append("CORPUS:%d|%d" % (corpus_size, len(published)))
    report.extend(rp.measurement_lines(roadmap.entries))
    # Lane composition for BOTH populations. The run summary must be able to
    # say that the parallel-safe lane is empty when it is: the lane is not part
    # of the sort key (by design -- affinity must never outrank risk), so a
    # top-N cap can legitimately publish no safe entry at all, and an empty safe
    # lane reported only by its absence would read as "nothing to worry about"
    # rather than "nothing was startable".
    report.append("LANES:%s" % _lane_counts(roadmap.entries))
    report.append("PUBLISHED_LANES:%s" % _lane_counts(published))
    # The in-flight tasks the CONFLICT verdicts are against, so the summary can
    # name them. A conflict count with no counterparty invites the reader to
    # assume a diffuse problem when it is usually one broad in-flight surface.
    project = _project_of(candidates)
    counterparties = {}
    for entry in published:
        if entry.classification == "coordination_only":
            for line in entry.admission_lines:
                if line.startswith("OVERLAP:"):
                    ref = line[len("OVERLAP:"):].split("|", 1)[0]
                    if "#" not in ref:      # same qualification the doc uses
                        ref = "%s#%s" % (project, pa.canonical_ref(ref))
                    counterparties[ref] = counterparties.get(ref, 0) + 1
    for ref in sorted(counterparties, key=lambda r: (-counterparties[r], r)):
        report.append("CONFLICT_WITH:%s|%d" % (ref, counterparties[ref]))

    # The NARROW snapshot -- only the published members reach `generation`.
    member_ids = [e.candidate.task_id for e in published]
    rc, narrow = snapshot(root, member_ids, with_inflight=False)
    if rc != 0:
        report.append("REFUSED:snapshot_failed|narrow snapshot exited %d" % rc)
        return EXIT_REFUSED, report

    narrative = dict(narrative)
    narrative["method_note"] = method_note(corpus_size, len(published), cap,
                                           unparsable)

    generation = _generation(narrow, agent_string, now)
    evidence = _evidence(len(member_task_ids), len(member_ids), _iso(now))
    # `scope.topics` lists the PUBLISHED MEMBERS, not their anchor roots.
    #
    # Two reasons, and the second is why this is not a workaround. First,
    # accuracy: this trail covers exactly the capped top-N, so naming a root
    # would claim coverage of a whole topic when 2 of its 18 tasks were
    # published. Second, drift: `new_related_task` fires for any task whose
    # topic key matches an entry in `scope.topics`, so listing roots made every
    # UNPUBLISHED sibling in a covered topic a drift reason -- and since a cap
    # guarantees unpublished siblings, the trail was born STALE and could never
    # read CURRENT. Measured before this change: 29 reasons at creation.
    scope = {"kind": "ad_hoc",
             "topics": sorted({e.candidate.ref for e in published})}
    freshness = {"state": "current", "checked_at": _iso(now)}
    # The checker's claim refs are BARE ids (`1569_6`); every ref in the trail
    # is the project-qualified `<project>#<id>` the schema's `task_ref` pattern
    # requires. Qualify against the project the members came from rather than a
    # literal, so a cross-repo member cannot be mislabelled as local.
    inflight_refs = sorted({"%s#%s" % (project, pa.canonical_ref(c.ref))
                            for c in population.base.inflight})

    try:
        document = rp.to_trail(published, TRAIL_ID, title, owner, scope,
                               generation, freshness, narrative, evidence,
                               inflight_refs=inflight_refs)
    except rp.EmptyRoadmapError as exc:
        report.append("EMPTY:%s" % exc)
        return EXIT_OK, report

    with open(out_path, "w", encoding="utf-8") as fh:
        json.dump(document, fh, indent=2, sort_keys=False)
        fh.write("\n")
    report.append("WROTE:%s" % out_path)
    for ref in (e.candidate.ref for e in published):
        report.append("MEMBER:%s" % ref)
    return EXIT_OK, report


def _lane_counts(entries):
    """`safe=<n>,coordination=<n>,unresolvable=<n>` -- every lane ALWAYS named.

    A lane with no entries is printed as `=0` rather than omitted. An absent key
    and a zero are the same fact only to a reader who already knows the
    vocabulary, and the whole point of this line is to make an empty
    parallel-safe lane impossible to miss.
    """
    names = {1: "safe", 2: "coordination", 3: "unresolvable"}
    counts = {name: 0 for name in names.values()}
    for entry in entries:
        counts[names[entry.lane]] = counts[names[entry.lane]] + 1
    return ",".join("%s=%d" % (names[k], counts[names[k]])
                    for k in sorted(names))


def _project_of(candidates):
    """The logical project name the members are qualified with.

    Taken from the gatherer's own refs rather than from a config lookup: those
    refs are what the digest was computed over, and a second source for the same
    name could disagree with them byte-for-byte.
    """
    for ref in candidates:
        if "#" in ref:
            return ref.split("#", 1)[0]
    return "aitasks"


def _topic_of(scored):
    """`scope.topics` uses the SAME anchor-root rule the entries do.

    Delegated to `roadmap_policy._topic_ref` rather than re-derived: a second
    spelling of "the topic of a candidate" would let `scope.topics` disagree
    with `entry.topic` for the very tasks whose anchor is unusual, and drift
    resolution reads both.
    """
    return rp._topic_ref(scored.candidate)


def _evidence(scanned, published, observed_at):
    """`command_output` records naming the three invocations behind the ranking.

    `ref` is the command line (a locator, never a content copy) and `summary`
    says what it produced -- the shape `evidence` requires alongside
    `evidence_id`, `source_type` and `observed_at`.
    """
    return [
        {"evidence_id": "ev-gather",
         "source_type": "command_output",
         "ref": "aitask_trail_gather.sh snapshot --scope task --with-inflight",
         "observed_at": observed_at,
         "summary": ("Member and in-flight facts for %d scanned candidate(s); "
                     "the in-flight records are digest-excluded by "
                     "construction." % scanned)},
        {"evidence_id": "ev-origin-facts",
         "source_type": "command_output",
         "ref": "aitask_backlog_origin_facts.sh",
         "observed_at": observed_at,
         "summary": ("Origin risk facts, one row per (task, origin) pair, over "
                     "the %d scanned candidate(s)." % scanned)},
        {"evidence_id": "ev-admission",
         "source_type": "command_output",
         "ref": "parallel_admission.decide (one collected snapshot, re-aimed "
                "per candidate)",
         "observed_at": observed_at,
         "summary": ("Collision verdicts for every scanned candidate against "
                     "one in-flight population; %d published. CLEAR means no "
                     "known conflict at check time." % published)},
    ]


# --- CLI ---------------------------------------------------------------------

def _positive_int(value):
    """A cap of 0 would reach `to_trail` as an empty list and report "no
    candidates" for what is really a typo, so the range is checked here."""
    try:
        n = int(value)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(
            "--cap must be an integer >= 1, got %r" % value)
    if n < 1:
        raise argparse.ArgumentTypeError(
            "--cap must be an integer >= 1, got %d" % n)
    return n


def build_parser():
    p = argparse.ArgumentParser(
        prog="aitask_backlog_roadmap.sh",
        description="Rank the background-work backlog into an "
                    "implementation_trail document.")
    p.add_argument("--narrative", required=True,
                   help="JSON object with problem_statement and "
                        "recommendation_summary (optional overview)")
    p.add_argument("--owner", required=True,
                   help="task ref that owns the artifact handle")
    p.add_argument("--out", required=True, help="path to write the trail JSON")
    p.add_argument("--title", default=DEFAULT_TITLE)
    p.add_argument("--cap", type=_positive_int, default=DEFAULT_CAP)
    p.add_argument("--agent-string", default="claudecode/opus5")
    p.add_argument("--root", default=None,
                   help="repository root (default: cwd)")
    return p


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    args = build_parser().parse_args(argv)
    root = args.root or os.getcwd()
    try:
        code, report = run(root, args.narrative, args.owner, args.out,
                           title=args.title, cap=args.cap,
                           agent_string=args.agent_string)
    except NarrativeError as exc:
        sys.stderr.write("%s\n" % exc)
        return EXIT_USAGE
    sys.stdout.write("".join(line + "\n" for line in report))
    return code


if __name__ == "__main__":
    sys.exit(main())
