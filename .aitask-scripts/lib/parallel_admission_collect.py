"""Live-state collection for the parallel-admission checker (t1569_3).

This is the IMPURE half. It owns every subprocess, exactly as
``aitask_revert_analyze.sh`` owns them for ``task_file_sets.py``, and hands
``parallel_admission.decide()`` a frozen ``AdmissionInput``.

t1569_5 (the roadmap) must NOT import this module -- it builds an
``AdmissionInput`` from already-materialised records via
``parallel_admission.input_from_records`` and calls the same ``decide``. One
verdict logic, two consumers.

Every external interaction goes through a module-level seam (``_GATE_PROBE``,
``_LOCK_PROBE``, ...) so tests can rebind it, following the
``trail_gather._GATE_PROBE`` convention.
"""

import datetime
import os
import re
import subprocess
import sys
import time

_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

import parallel_admission as pa          # noqa: E402
import parallel_admission_sweep as pas   # noqa: E402
import plan_paths                        # noqa: E402

_LOCKS_REF = "origin/aitask-locks"
_LOCKS_REF_LOCAL = "aitask-locks"
_DATA_REF = "aitask-data"
_DATA_REF_REMOTE = "origin/aitask-data"
_PROBE_TIMEOUT_S = 5
_BATCH_TIMEOUT_S = 60
_FETCH_TIMEOUT_S = 10

_LOCK_FILE_RE = re.compile(r"^t(\d+(?:_\d+)?)_lock\.yaml$")
_TASK_FILE_RE = re.compile(r"^t\d+(?:_\d+)?_.*\.md$")


def _git(root, *args, **kw):
    """Run git, returning ``(rc, stdout)``. Never raises on a non-zero exit."""
    timeout = kw.get("timeout", _PROBE_TIMEOUT_S)
    try:
        p = subprocess.run(["git", "-C", str(root)] + list(args),
                           capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, OSError):
        return 1, ""
    return p.returncode, p.stdout


# --- corpora ----------------------------------------------------------------


def data_tracked_sets(root):
    """Paths tracked on the task-data branch, plus their directory prefixes.

    ``aitasks/`` and ``aiplans/`` are gitignored symlinks into ``.aitask-data/``,
    so ``git ls-files`` on the code branch tracks ZERO of them and every such
    path classifies ``phantom``. Measured over the live corpus that is a ~6x
    inflation of the all-phantom rate AND it drops the task-data paths from
    overlap comparison entirely -- two tasks editing the same profile YAML would
    report no conflict.

    A missing ref is a CONTENT state, not an error: on a single-branch (legacy)
    clone ``aitasks/`` is already in ``git ls-files``, the union is empty, and
    behaviour degrades to the code-branch-only classification.

    Returns ``(files, dirs, reason)`` -- ``reason`` is ``None`` on success.
    """
    for ref in (_DATA_REF, _DATA_REF_REMOTE):
        rc, out = _git(root, "ls-tree", "-r", "--name-only", ref)
        if rc == 0 and out.strip():
            files = set(out.splitlines())
            dirs = set()
            for p in files:
                parts = p.split("/")
                for i in range(1, len(parts)):
                    dirs.add("/".join(parts[:i]))
            return files, dirs, None
    return set(), set(), "no_local_ref"


def locks_cache_age(root):
    """Age of this clone's cached locks ref, reusing t1569_1's reason vocabulary.

    Delegates to ``trail_gather._locks_cache_age`` rather than re-deriving it:
    its ``no_local_ref`` (never fetched) vs ``timeout`` (probe exceeded budget)
    distinction is exactly what ``--lock-freshness`` turns on, and forking it
    would let the two drift apart. Imported lazily so the collector's own import
    cost stays low.
    """
    try:
        import pathlib
        import trail_gather
        return trail_gather._locks_cache_age(pathlib.Path(str(root)))
    except Exception:
        return None, "scan_error"


# --- enumeration probes -----------------------------------------------------


def probe_gate_source(root):
    """In-flight tasks with a recorded gate ledger."""
    try:
        p = subprocess.run(
            [os.path.join(_LIB_DIR, os.pardir, "aitask_query_files.sh"), "inflight"],
            capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S, cwd=str(root))
    except (subprocess.TimeoutExpired, OSError):
        return pa.SourceEvidence("gate", "unavailable", None, "timeout"), {}
    if p.returncode != 0:
        return pa.SourceEvidence("gate", "unavailable", None, "scan_error"), {}
    ids = {}
    for line in p.stdout.splitlines():
        if line.startswith("INFLIGHT:"):
            parts = line[len("INFLIGHT:"):].split("|")
            if parts:
                ids[parts[0]] = {}
    return pa.SourceEvidence("gate", "ok", None, None), ids


def probe_lock_source(root):
    """Locked task ids from the locks ref. Reads only -- the fetch is separate."""
    rc, out = _git(root, "rev-parse", "--verify", "--quiet", _LOCKS_REF + "^{tree}")
    ref = _LOCKS_REF
    if rc != 0:
        rc, out = _git(root, "rev-parse", "--verify", "--quiet",
                       _LOCKS_REF_LOCAL + "^{tree}")
        ref = _LOCKS_REF_LOCAL
        if rc != 0:
            return pa.SourceEvidence("lock", "unavailable", None, "no_local_ref"), {}
    rc, listing = _git(root, "ls-tree", "--name-only", ref)
    if rc != 0:
        return pa.SourceEvidence("lock", "unavailable", None, "unreadable_tree"), {}
    ids = {}
    for name in listing.splitlines():
        m = _LOCK_FILE_RE.match(name.strip())
        if not m:
            continue
        rc, blob = _git(root, "show", "%s:%s" % (ref, name.strip()))
        ids[m.group(1)] = _parse_lock_yaml(blob) if rc == 0 else {}
    return pa.SourceEvidence("lock", "ok", None, None), ids


def probe_status_source(root, task_dir="aitasks"):
    """Tasks whose frontmatter says ``status: Implementing``.

    THE THIRD SOURCE, and it is not redundant. ``gate`` requires a
    ``## Gate Runs`` ledger and ``lock`` requires a lock; a task that is
    ``Implementing`` with neither -- verified live -- is in NEITHER, so the union
    of the other two misses it entirely. A task the checker never enumerates
    cannot be classified, and its absence reads as "no such in-flight work":
    a silent false CLEAR against a task that may have a perfectly usable plan.

    Pure filesystem, no git, no subprocess -- the cheapest of the three probes
    and the one with the fullest coverage of the state task-workflow's Step 4
    actually writes.
    """
    base = os.path.join(str(root), task_dir)
    if not os.path.isdir(base):
        return pa.SourceEvidence("status", "unavailable", None, "scan_error"), {}
    ids = {}
    try:
        for dirpath, dirnames, filenames in os.walk(base, followlinks=True):
            if "archived" in dirpath.split(os.sep):
                dirnames[:] = []
                continue
            dirnames[:] = [d for d in dirnames if d != "archived"]
            for fn in filenames:
                if not _TASK_FILE_RE.match(fn):
                    continue
                full = os.path.join(dirpath, fn)
                meta = _read_frontmatter(full)
                if meta.get("status") == "Implementing":
                    ids[_task_id_from_name(fn)] = {"updated_at": meta.get("updated_at")}
    except OSError:
        return pa.SourceEvidence("status", "unavailable", None, "scan_error"), {}
    return pa.SourceEvidence("status", "ok", None, None), ids


def _task_id_from_name(filename):
    m = re.match(r"^t(\d+(?:_\d+)?)_", filename)
    return m.group(1) if m else filename


def _read_frontmatter(path):
    out = {}
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            if fh.readline().strip() != "---":
                return out
            for line in fh:
                if line.strip() == "---":
                    break
                k, sep, v = line.partition(":")
                if sep:
                    out[k.strip()] = v.strip()
    except OSError:
        return out
    return out


def _parse_lock_yaml(blob):
    out = {}
    for line in blob.splitlines():
        k, sep, v = line.partition(":")
        if sep:
            out[k.strip()] = v.strip()
    return out


# --- liveness ---------------------------------------------------------------


def lock_holder_liveness(pid, starttime, kind):
    """Shell out to ``lib/pid_anchor.sh::lock_holder_liveness``.

    That function ECHOES on stdout and always exits 0 -- never branch on ``$?``.
    It returns ``unknown``, not ``dead``, when the anchor token is absent.
    """
    script = os.path.join(_LIB_DIR, "pid_anchor.sh")
    cmd = ['source "$1"; lock_holder_liveness "$2" "$3" "$4"']
    try:
        p = subprocess.run(["bash", "-c", cmd[0], "_", script,
                            str(pid or ""), str(starttime or "-"), str(kind or "proc")],
                           capture_output=True, text=True, timeout=_PROBE_TIMEOUT_S)
    except (subprocess.TimeoutExpired, OSError):
        return "unknown"
    val = p.stdout.strip()
    return val if val in ("alive", "dead", "unknown") else "unknown"


def classify_liveness(lock_meta, is_implementing, local_host):
    """Return ``(liveness, same_host)``.

    THE HOSTNAME GUARD IS MANDATORY BEFORE ANY ``dead`` CLAIM.
    ``lock_holder_liveness`` compares the recorded PID against the LOCAL process
    table, so on a different host an absent PID yields ``dead`` -- a fabricated
    crash claim about a live agent elsewhere, and ``dead`` is the one class the
    verdict logic DROPS. ``aitask_lock.sh:221-223`` already gates its anchor
    check on ``locked_hostname == current_hostname`` and excludes a literal
    ``unknown`` hostname ("two machines both reporting it would compare equal").
    Cross-host is therefore ``unknown``, never ``dead``.
    """
    if not lock_meta:
        # Implementing with no lock at all: a status without a lock, the mirror
        # of lock_only. Its surface is knowable, so it can still CONFLICT; only
        # its liveness is unevidenced, so it can never certify CLEAR.
        return ("status_only", None) if is_implementing else ("unknown", None)
    host = lock_meta.get("hostname", "")
    same_host = bool(host) and host != "unknown" and host == local_host
    if not same_host:
        return "unknown", False
    liveness = _LIVENESS(lock_meta.get("pid"), lock_meta.get("pid_starttime"),
                         lock_meta.get("pid_starttime_kind"))
    if liveness == "alive":
        return ("live", True) if is_implementing else ("lock_only", True)
    if liveness == "dead":
        return "dead", True
    return ("unknown", True) if is_implementing else ("lock_only", True)


# --- timestamps -------------------------------------------------------------


def parse_ts(value):
    """``YYYY-MM-DD HH:MM`` -> ``(epoch, None)`` or ``(None, reason)``."""
    if not value:
        return None, "absent"
    for fmt in ("%Y-%m-%d %H:%M", "%Y-%m-%d %H:%M:%S"):
        try:
            return int(datetime.datetime.strptime(value.strip(), fmt).timestamp()), None
        except ValueError:
            continue
    return None, "malformed"


# --- surfaces ---------------------------------------------------------------


def strip_frontmatter(text):
    """Drop a leading ``---`` block.

    The workflow-written ``Parent Task:`` / ``Sibling Tasks:`` lines are metadata
    of identical shape in every plan, never a work surface. Removing them BEFORE
    extraction is the whole citation fix -- there is deliberately no namespace
    rule demoting ``aitasks/``/``aiplans/`` paths, because a plan may legitimately
    declare a task document as a file it modifies.
    """
    if not text.startswith("---"):
        return text, []
    end = text.find("\n---", 3)
    if end == -1:
        return text, []
    head, body = text[:end], text[end + 4:]
    return body, sorted(set(plan_paths.extract(head)))


def plan_extraction(ref, plan_path, tracked, tracked_dirs, body_transform=None):
    """Extract a plan's paths AND the accounting ``surface_from_plan`` discards.

    THE ONE EXTRACTOR. ``surface_from_plan`` delegates here, so the phantom-token
    drop count t1643's drift probe reports comes from the same pass that produced
    the surface -- a second extractor could disagree with the surface it claims
    to describe, and the disagreement would be invisible.

    ``body_transform`` is applied to the body AFTER frontmatter stripping and
    BEFORE token extraction. It defaults to None (identity) so every existing
    call site is unchanged; t1643's ``--plan-scope pre-implementation`` passes
    ``parallel_admission_sweep.cut_post_implementation``.

    Returns ``(PlanExtraction, stripped_frontmatter_tokens)``.
    """
    try:
        with open(plan_path, "r", encoding="utf-8") as fh:
            text = fh.read()
    except (OSError, UnicodeDecodeError):
        return pas.PlanExtraction(ref, (), "unreadable", 0, 0), []
    body, stripped = strip_frontmatter(text)
    if body_transform is not None:
        body = body_transform(body)
    tokens = plan_paths.extract(body)
    if not tokens:
        return pas.PlanExtraction(ref, (), "no_extractable_paths", 0, 0), stripped
    keep = []
    for tok in tokens:
        # `planned_new` is a legitimately planned NEW file, not a phantom.
        if plan_paths.classify(tok, tracked, tracked_dirs) in ("tracked", "planned_new"):
            keep.append(tok)
    dropped = len(tokens) - len(keep)
    if not keep:
        return pas.PlanExtraction(ref, (), "all_phantom", len(tokens), dropped), stripped
    return (pas.PlanExtraction(ref, tuple(sorted(keep)), "resolved",
                               len(tokens), dropped), stripped)


def surface_from_plan(ref, plan_path, tracked, tracked_dirs, body_transform=None):
    """Build a plan-declared Surface, or an unresolved one with a named reason.

    A thin projection of `plan_extraction` -- see there for why the two must not
    be separate implementations.
    """
    extraction, stripped = plan_extraction(ref, plan_path, tracked, tracked_dirs,
                                           body_transform=body_transform)
    return extraction.as_surface(), stripped


# --- injectable seams -------------------------------------------------------

_GATE_PROBE = probe_gate_source
_LOCK_PROBE = probe_lock_source
_STATUS_PROBE = probe_status_source
_TRACKED_SETS = plan_paths.tracked_sets
_DATA_TREE = data_tracked_sets
_LIVENESS = lock_holder_liveness
_LOCAL_HOST = None      # None => resolve via platform.node() at call time


def _local_host():
    if _LOCAL_HOST is not None:
        return _LOCAL_HOST
    import platform
    return platform.node()


def _fetch_locks(root):
    rc, _ = _git(root, "fetch", "origin", "aitask-locks", "--quiet",
                 timeout=_FETCH_TIMEOUT_S)
    return rc == 0


def _batch_map(root, with_recovered=False):
    script = os.path.join(_LIB_DIR, os.pardir, "aitask_revert_analyze.sh")
    cmd = [script, "--batch-map"]
    if with_recovered:
        cmd.append("--with-recovered")
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=_BATCH_TIMEOUT_S, cwd=str(root))
    except (subprocess.TimeoutExpired, OSError):
        return []
    return p.stdout.splitlines() if p.returncode == 0 else []


_FETCH = _fetch_locks
_BATCH_MAP = _batch_map


def task_file_for(root, task_id):
    """``aitasks/t<N>_*.md``, or ``aitasks/t<P>/t<P>_<C>_*.md`` for a child."""
    import glob
    if "_" in task_id:
        parent, child = task_id.split("_", 1)
        pat = os.path.join(str(root), "aitasks", "t%s" % parent,
                           "t%s_%s_*.md" % (parent, child))
    else:
        pat = os.path.join(str(root), "aitasks", "t%s_*.md" % task_id)
    hits = sorted(glob.glob(pat))
    return hits[0] if hits else None


def origin_surface(root, task_id, batch_lines):
    """Origin-derived candidate surface: the file sets of the task's ORIGIN(S).

    A follow-up's own id has landed nothing -- its work has not been done yet --
    so looking up its own file set always yields ``UNKNOWN_HISTORY``. The
    origin-derived provenance means the files the task it was spawned FROM
    touched, which is why this goes through ``followup_origin``.

    Quality is carried honestly and never upgraded: ``verifies:`` gives an
    ``exact`` origin, ``anchor:`` only a ``topic`` root (explicitly NOT an exact
    origin), and neither gives ``unknown``.
    """
    import followup_origin
    path = task_file_for(root, task_id)
    if path is None:
        return pa.Surface(task_id, "origin_derived", (), "unknown_origin", "unknown")
    detail = followup_origin.resolve_path(path)
    if detail is None:
        return pa.Surface(task_id, "origin_derived", (), "unknown_origin", "unknown")
    origins, quality = detail["origins"], detail["quality"]
    if quality == followup_origin.UNKNOWN or not origins:
        return pa.Surface(task_id, "origin_derived", (), "unknown_origin", "unknown")
    by_id = pa.surfaces_from_batch_map(batch_lines, origins)
    paths, any_resolved = set(), False
    for oid in origins:
        s = by_id.get(oid)
        if s is not None and s.resolution == "resolved":
            any_resolved = True
            paths.update(s.paths)
    if not any_resolved:
        # UNKNOWN_HISTORY on every origin: an absent map entry is
        # indistinguishable from "touched no files", so it must be its own
        # state and must never flow to CLEAR.
        return pa.Surface(task_id, "origin_derived", (), "unknown_history", quality)
    return pa.Surface(task_id, "origin_derived", tuple(sorted(paths)),
                      "resolved", quality)


def plan_path_for(root, task_id):
    """``aiplans/p<N>_*.md`` for a parent, ``aiplans/p<P>/p<P>_<C>_*.md`` for a child."""
    import glob
    if "_" in task_id:
        parent, child = task_id.split("_", 1)
        pat = os.path.join(str(root), "aiplans", "p%s" % parent,
                           "p%s_%s_*.md" % (parent, child))
    else:
        pat = os.path.join(str(root), "aiplans", "p%s_*.md" % task_id)
    hits = sorted(glob.glob(pat))
    return hits[0] if hits else None


def resolve_corpora(root):
    """``(all_tracked, all_dirs, corpus_records)`` for path classification.

    Unions the code branch and the task-data branch and hands the WIDER sets to
    the SAME shared classifier -- `plan_paths.classify` already takes the corpus
    as parameters, so there is no fork and no widening of its pinned 4-class
    vocabulary.

    Factored out so `replay` can resolve it ONCE and share it across every
    candidate; resolving it per candidate would let a concurrent commit change
    the corpus mid-run and make the reported rates incomparable.
    """
    tracked, tracked_dirs = set(), set()
    code_reason = None
    try:
        tracked, tracked_dirs = _TRACKED_SETS(str(root))
    except Exception:
        code_reason = "scan_error"
    dfiles, ddirs, data_reason = _DATA_TREE(root)
    records = (
        pa.CorpusEvidence("code", "ok" if code_reason is None else "unavailable",
                          len(tracked), code_reason),
        pa.CorpusEvidence("data", "ok" if data_reason is None else "unavailable",
                          len(dfiles), data_reason),
    )
    return tracked | dfiles, tracked_dirs | ddirs, records


def collect(root, candidate_id, source="plan", plan_path=None,
            freshness="allow-cached", max_lock_age_s=None,
            max_claim_age_s=pa.MAX_CLAIM_AGE_S, hub_threshold=pa.HUB_THRESHOLD,
            now=None, with_recovered=True, exclude_self=True,
            batch_lines=None, corpus=None, candidate_surface=None,
            surface_cache=None):
    """Gather live state into a frozen ``AdmissionInput``.

    ``exclude_self=False`` builds the comparison population WITHOUT removing the
    candidate. `replay` needs that: its base snapshot must contain every
    in-flight task, and the per-candidate exclusion happens in `_respin`.
    Building the base with self-exclusion would permanently drop whichever task
    happened to be listed first, so every later candidate would be compared
    against a world where that active task does not exist.

    ``batch_lines`` and ``corpus`` let a caller supply one already-resolved
    snapshot instead of re-deriving it per candidate.
    """
    now = int(time.time()) if now is None else int(now)
    key = pa.canonical_ref(candidate_id)
    local_host = _local_host()

    if corpus is None:
        all_tracked, all_dirs, corpora = resolve_corpora(root)
    else:
        all_tracked, all_dirs, corpora = corpus

    # --- lock freshness --------------------------------------------------
    # The gatherer reads origin/aitask-locks WITHOUT fetching so it stays
    # offline-safe -- right for an estimate, fatal for an admission decision: a
    # stale ref hides a lock another agent took seconds ago. Neither mode may
    # report CLEAR on lock evidence it could not establish.
    lock_age, lock_reason = locks_cache_age(root)
    if freshness == "require-fresh":
        if _FETCH(root):
            lock_state, lock_age, lock_reason = "fetched", 0, None
        else:
            lock_state = "unavailable"
            lock_reason = lock_reason or "timeout"
    else:
        lock_state = "cached"
    locks = pa.LockEvidence(mode=freshness, state=lock_state,
                            age_s=lock_age, reason=lock_reason)

    # --- enumerate -------------------------------------------------------
    gate_ev, gate_ids = _GATE_PROBE(root)
    lock_ev, lock_ids = _LOCK_PROBE(root)
    status_ev, status_ids = _STATUS_PROBE(root)
    enumeration = (gate_ev, lock_ev, status_ev)

    refs = {}
    for name, ids in (("gate", gate_ids), ("lock", lock_ids), ("status", status_ids)):
        for tid in ids:
            refs.setdefault(pa.canonical_ref(tid), set()).add(name)

    if batch_lines is None:
        batch_lines = _BATCH_MAP(root, with_recovered=with_recovered)
    touch = pa.touch_counts_from_batch_map(batch_lines)

    claims = []
    for ref in sorted(refs):
        if ref == key and exclude_self:
            # Self-exclusion, BEFORE overlap is evaluated -- task-workflow set
            # the candidate Implementing and took its lock at Step 4, long
            # before the plan existed.
            continue
        meta = lock_ids.get(ref) or lock_ids.get("t" + ref) or {}
        is_impl = "status" in refs[ref] or "gate" in refs[ref]
        liveness, same_host = classify_liveness(meta, is_impl, local_host)
        if meta:
            at, reason = parse_ts(meta.get("locked_at"))
        else:
            at, reason = parse_ts((status_ids.get(ref) or {}).get("updated_at"))
        p = plan_path_for(root, ref)
        if p is None:
            surf = pa.Surface(ref, "plan_declared", (), "no_plan", "n/a")
        else:
            surf = _plan_surface(ref, p, all_tracked, all_dirs, surface_cache)
        claims.append(pa.InflightClaim(
            ref=ref, sources=tuple(sorted(refs[ref])),
            task_status="Implementing" if is_impl else "-",
            liveness=liveness, same_host=same_host,
            claim_at_s=at, claim_age_reason=reason, surface=surf))

    # --- candidate surface ------------------------------------------------
    if candidate_surface is not None:
        cand = candidate_surface
    else:
        cand = resolve_candidate_surface(root, key, source, batch_lines,
                                         all_tracked, all_dirs, plan_path,
                                         cache=surface_cache)
    recovered_used = (source == "origin"
                      and cand.resolution in ("unknown_history", "unknown_origin")
                      and with_recovered)

    return pa.AdmissionInput(
        candidate=cand, enumeration=enumeration, inflight=tuple(claims),
        locks=locks, corpora=corpora, touch_counts=touch,
        hub_threshold=hub_threshold, max_lock_age_s=max_lock_age_s,
        max_claim_age_s=max_claim_age_s, now=now, recovered_used=recovered_used)


# --- CLI --------------------------------------------------------------------


def _die(msg):
    """CLI misuse dies; every CONTENT state exits 0.

    A silent verdict for a typo'd flag is the "silent-skip masks a broken
    implementation" hazard (aitask_verification_stale.sh:26-32).
    """
    sys.stderr.write("aitask_parallel_admission: %s\n" % msg)
    raise SystemExit(2)


def _parse_args(argv):
    if not argv:
        _die("missing subcommand (check|replay)")
    verb, rest = argv[0], argv[1:]
    if verb not in ("check", "replay", "sweep"):
        _die("unknown subcommand: %s" % verb)
    opts = {"from": "plan", "lock_freshness": "allow-cached", "root": ".",
            "plan": None, "max_lock_age": None,
            "max_claim_age": pa.MAX_CLAIM_AGE_S,
            "hub_threshold": pa.HUB_THRESHOLD, "candidate": None,
            "candidates": None, "thresholds": None, "exclude": None,
            "exclude_no_plan": False, "plan_scope": "full"}
    flags = {"--candidate": "candidate", "--from": "from", "--plan": "plan",
             "--lock-freshness": "lock_freshness", "--max-lock-age": "max_lock_age",
             "--max-claim-age": "max_claim_age", "--hub-threshold": "hub_threshold",
             "--root": "root", "--candidates": "candidates",
             "--thresholds": "thresholds", "--exclude": "exclude",
             "--plan-scope": "plan_scope"}
    bare = {"--exclude-no-plan": "exclude_no_plan"}
    i = 0
    saw = set()
    while i < len(rest):
        a = rest[i]
        if a in bare:
            opts[bare[a]] = True
            saw.add(a)
            i += 1
            continue
        if a not in flags:
            _die("unknown flag: %s" % a)
        if i + 1 >= len(rest):
            _die("%s requires a value" % a)
        opts[flags[a]] = rest[i + 1]
        saw.add(a)
        i += 2
    for k in ("max_lock_age", "max_claim_age", "hub_threshold"):
        if opts[k] is not None:
            try:
                opts[k] = int(opts[k])
            except (TypeError, ValueError):
                _die("--%s expects an integer" % k.replace("_", "-"))
    # SAFETY THRESHOLDS ARE ONE-WAY ON `check`.
    #
    # A CONFLICT is not overridable by design, so no ordinary flag may talk the
    # checker out of one. Both knobs are MONOTONE in strictness -- verified
    # against live conflicting candidate t1061:
    #
    #   --hub-threshold   1 -> CLEAR_CAVEATED, 5/10/50/500 -> CONFLICT
    #   --max-claim-age   1 -> CLEAR_CAVEATED, 86400/1209600/99999999 -> CONFLICT
    #
    # Raising either can only turn hub overlaps back into specific ones, or
    # advisory claims back into blocking ones -- it never hides a collision.
    # LOWERING either hides collisions wholesale: `--hub-threshold 1` demotes
    # essentially every real path (almost all have >= 1 task touch), and
    # `--max-claim-age 1` makes every claim older than a second advisory. A
    # simple `>= 1` bound is therefore NOT enough; the floor is the shared
    # default.
    #
    # `replay` is a measurement tool whose whole purpose is sweeping thresholds,
    # and it renders no admission decision, so it accepts any positive value.
    FLOORS = {"hub_threshold": pa.HUB_THRESHOLD,
              "max_claim_age": pa.MAX_CLAIM_AGE_S}
    for k, floor in FLOORS.items():
        if opts[k] is None:
            continue
        if opts[k] < 1:
            _die("--%s must be positive (got %d)" % (k.replace("_", "-"), opts[k]))
        if verb == "check" and opts[k] < floor:
            _die("--%s must be >= %d on `check` (got %d): a lower value weakens "
                 "the guard and can downgrade a real conflict to a caveat. "
                 "Raising it is allowed -- it only makes the check stricter. "
                 "Use `replay` to sweep thresholds."
                 % (k.replace("_", "-"), floor, opts[k]))
    # --- EXCLUSION IS `replay`-ONLY, and the two refusals are NOT the same ---
    #
    # `check` renders an admission decision, so dropping an in-flight task there
    # hides a real collision -- fail-open, the one direction the threshold floors
    # above already forbid.
    #
    # `sweep` measures ARCHIVED PAIRS and has no in-flight claim set at all, so
    # the flag has nothing to filter. Accepting and ignoring it would report the
    # full archive while the operator believed a population had been excluded --
    # the same accepted-and-ignored hazard `--plan` dies on for `replay`.
    #
    # Two causes, two messages: a shared one would let an operator read the
    # "nothing to filter" case as the admission-safety refusal, and vice versa.
    if verb != "replay":
        used = [f for f in ("--exclude", "--exclude-no-plan") if f in saw]
        if used and verb == "check":
            _die("%s is not valid for `check`: excluding an in-flight task at an "
                 "admission point hides a real collision. Use `replay` to measure "
                 "a counterfactual." % used[0])
        if used:
            _die("%s is not valid for `sweep`: its population is archived pairs, "
                 "which carries no in-flight claim set to filter. Use `replay` for "
                 "live exclusions." % used[0])

    # `--thresholds` sweeps; `--hub-threshold` pins one. Accepting both leaves
    # which wins ambiguous, and a silently-losing threshold is exactly the
    # accepted-and-ignored hazard above.
    if "--thresholds" in saw and "--hub-threshold" in saw:
        _die("--thresholds and --hub-threshold are mutually exclusive: pass a "
             "single value to --thresholds to pin one")
    if opts["thresholds"] is not None:
        if verb == "check":
            _die("--thresholds is not valid for `check`, which renders one "
                 "admission decision; use --hub-threshold, or `replay`/`sweep` "
                 "to sweep")
        values = []
        for raw in opts["thresholds"].split(","):
            raw = raw.strip()
            if not raw:
                _die("--thresholds contains an empty value: %r" % opts["thresholds"])
            try:
                value = int(raw)
            except ValueError:
                _die("--thresholds expects integers, got %r" % raw)
            if value < 1:
                _die("--thresholds must be positive (got %d)" % value)
            values.append(value)
        # De-duplicate but KEEP the caller's order: the report is read as a
        # sweep in the order asked for, and sorting it would silently reorder
        # the rows against the command that produced them.
        seen_th, ordered = set(), []
        for value in values:
            if value not in seen_th:
                seen_th.add(value)
                ordered.append(value)
        opts["thresholds"] = tuple(ordered)
    if opts["plan_scope"] not in ("full", "pre-implementation"):
        _die("--plan-scope expects full|pre-implementation")
    if opts["plan_scope"] != "full" and verb != "sweep":
        _die("--plan-scope is only meaningful for `sweep` (it re-reads archived "
             "plan bodies); `check` and `replay` read live plans as they stand")
    if opts["exclude"] is not None:
        refs = [pa.canonical_ref(r.strip()) for r in opts["exclude"].split(",")
                if r.strip()]
        if not refs:
            _die("--exclude was given no task ids")
        opts["exclude"] = tuple(sorted(set(refs)))
    if verb == "sweep":
        for flag, key in (("--candidate", "candidate"), ("--candidates", "candidates"),
                          ("--plan", "plan")):
            if flag in saw:
                _die("%s is not valid for `sweep`: its population is derived from "
                     "the archived corpus, not supplied" % flag)
    if opts["max_lock_age"] is not None and opts["max_lock_age"] < 0:
        _die("--max-lock-age must be >= 0 (got %d)" % opts["max_lock_age"])
    if opts["from"] not in ("plan", "origin", "auto"):
        _die("--from expects plan|origin|auto")
    if opts["lock_freshness"] not in ("require-fresh", "allow-cached"):
        _die("--lock-freshness expects require-fresh|allow-cached")
    if verb == "check" and not opts["candidate"]:
        _die("check requires --candidate <id>")
    if verb == "replay" and not opts["candidates"]:
        _die("replay requires --candidates <file|->")
    if verb == "replay" and opts["plan"] is not None:
        # --plan names ONE plan file; replay judges many candidates, so the flag
        # has no defensible meaning here. Silently ignoring it would report rates
        # for the on-disk plans while the caller believed they were measuring
        # the supplied one.
        _die("--plan is not valid for replay (it names a single candidate's "
             "plan); use `check --candidate <id> --plan <path>` instead")
    if opts["plan"] is not None and not os.path.isfile(opts["plan"]):
        _die("--plan target not found: %s" % opts["plan"])
    return verb, opts


def _collect_one(opts, cand):
    return collect(opts["root"], cand, source=opts["from"], plan_path=opts["plan"],
                   freshness=opts["lock_freshness"],
                   max_lock_age_s=opts["max_lock_age"],
                   max_claim_age_s=opts["max_claim_age"],
                   hub_threshold=opts["hub_threshold"])


def _plan_surface(ref, path, tracked, dirs, cache=None):
    """`surface_from_plan` memoised per run.

    A task can appear twice in one run -- once as the candidate and once as an
    in-flight claim -- and both roles read the SAME plan file. Reading it twice
    would let a concurrent edit give the two roles different views of one plan,
    which is the mixed-state hazard the one-snapshot contract exists to prevent.
    """
    key = (ref, path)
    if cache is not None and key in cache:
        return cache[key]
    surf, _stripped = surface_from_plan(ref, path, tracked, dirs)
    if cache is not None:
        cache[key] = surf
    return surf


def resolve_candidate_surface(root, candidate_id, source, batch_lines,
                              tracked, dirs, plan_path=None, cache=None):
    """The candidate's own surface, for one provenance.

    Standalone so `replay` can resolve EVERY candidate before it evaluates ANY
    of them: reading plans inside the reporting loop would let a concurrent edit
    mix plan states across one run, which breaks the comparability the rates
    depend on.
    """
    key = pa.canonical_ref(candidate_id)
    if source == "origin":
        return origin_surface(root, key, batch_lines)
    p = plan_path or plan_path_for(root, key)
    if p is None:
        cand = pa.Surface(key, "plan_declared", (), "no_plan", "n/a")
    else:
        cand = _plan_surface(key, p, tracked, dirs, cache)
    if source == "auto" and cand.resolution != "resolved":
        # Same fallback `collect` applies -- it must live here too, or
        # `replay --from auto` silently measures plain `plan` and the rate it
        # reports is for a mode nobody runs.
        alt = origin_surface(root, key, batch_lines)
        if alt.resolution == "resolved" and alt.paths:
            cand = pa.Surface(key, "plan_declared+origin_fallback", alt.paths,
                              "resolved", alt.quality)
    return cand


def _respin(base, candidate_id, candidate_surface, hub_threshold=None,
            exclude=()):
    """Re-aim an already-collected snapshot at a different candidate.

    `replay` is `check` in a loop over ONE collected snapshot -- same `decide`,
    no second verdict logic. Re-running `collect` per candidate would re-probe
    the locks, re-walk the task tree and re-run the batch map every iteration
    (~2.5s each), and worse, each candidate would be judged against a slightly
    different world, so the rates would not be comparable.

    Only two things vary per candidate: its own surface, and its exclusion from
    the comparison set.

    ``hub_threshold`` overrides the base's, which is what lets ONE collected
    snapshot answer for several thresholds (t1643). Sweeping by re-invoking the
    CLI instead would re-collect per threshold, and the population demonstrably
    moves between collections -- so the rates would not be comparable, which is
    the only thing a threshold sweep is for.

    ``exclude`` drops further claims by canonical ref, on top of the candidate's
    own self-exclusion. Measurement only: it answers "what would the checker say
    if these were not mid-claim", and is refused on `check` for that reason.
    """
    key = pa.canonical_ref(candidate_id)
    cand = candidate_surface
    drop = {key} | set(exclude)
    inflight = tuple(c for c in base.inflight
                     if pa.canonical_ref(c.ref) not in drop)
    return pa.AdmissionInput(
        candidate=cand, enumeration=base.enumeration, inflight=inflight,
        locks=base.locks, corpora=base.corpora, touch_counts=base.touch_counts,
        hub_threshold=(base.hub_threshold if hub_threshold is None
                       else hub_threshold),
        max_lock_age_s=base.max_lock_age_s,
        max_claim_age_s=base.max_claim_age_s, now=base.now,
        recovered_used=(cand.resolution == "unknown_history"))


def no_plan_claims(base):
    """Canonical refs of the claims that are FORCING `no_plan` UNCHECKABLEs.

    Derived from the collected snapshot itself, which is the whole point: the
    ids cannot be supplied by hand, because obtaining them needs a prior
    `check`/`replay` -- a SECOND collection -- and between the two a claim can
    appear, gain a plan, or vanish. All three happen on a busy box within a
    single session. Deriving them here makes the exclusion and the measurement
    one observation.

    BOTH halves of the predicate are required:

      * ``resolution == "no_plan"`` matches `decide` exactly -- for a blocking
        claim it appends the cause as ``surf.resolution`` itself, so this IS the
        set producing ``UNCHECKABLE_CAUSE:inflight:<id>|no_plan``. Sibling
        invisible surfaces (``all_phantom`` and friends) are deliberately NOT
        swept up: a plan that resolves to nothing is a genuine evidence gap, not
        a mid-claim artefact, and excluding it would answer a different question
        than this predicate is named for.
      * ``tier(...) == "blocking"`` is not cosmetic. `tier` returns ``excluded``
        for a provably-dead holder however recent its claim, and such a claim
        drives no cause at all -- live corpora routinely carry dead `no_plan`
        claims alongside live ones. Without this half the reported exclusion set
        would name ids that were never affecting anything, and the record would
        misdescribe its own counterfactual.
    """
    out = set()
    for claim in base.inflight:
        if pa.tier(claim, base.max_claim_age_s, base.now) != "blocking":
            continue
        surface = claim.surface
        if surface is not None and surface.resolution != "no_plan":
            continue
        out.add(pa.canonical_ref(claim.ref))
    return tuple(sorted(out))


def _read_candidates(opts):
    """Resolve `--candidates` into a list of task ids.

    `auto` derives the population from the active plan files, so a measurement
    is one reproducible command instead of an ad-hoc shell pipeline whose
    population nobody can reconstruct afterwards. Returns `(ids, source_label)`.
    """
    src = opts["candidates"]
    if src == "auto":
        return _active_plan_ids(opts["root"]), "auto"
    if src == "-":
        raw = sys.stdin.read()
    else:
        if not os.path.isfile(src):
            _die("--candidates file not found: %s" % src)
        with open(src, "r", encoding="utf-8") as fh:
            raw = fh.read()
    return [c.strip() for c in raw.splitlines() if c.strip()], "file"


def _plan_id_from_name(name):
    """`p1569_3_shared_checker.md` -> `1569_3`; None when it is not a plan file."""
    match = re.match(r"^p(\d+(?:_\d+)?)_.*\.md$", name)
    return match.group(1) if match else None


def _active_plan_ids(root):
    """Every task id with an active plan file, deduplicated, in numeric order."""
    plans = os.path.join(root, "aiplans")
    found = set()
    if not os.path.isdir(plans):
        return []
    for entry in os.listdir(plans):
        full = os.path.join(plans, entry)
        if os.path.isfile(full):
            tid = _plan_id_from_name(entry)
            if tid:
                found.add(tid)
        elif os.path.isdir(full) and entry != "archived":
            for child in os.listdir(full):
                if os.path.isfile(os.path.join(full, child)):
                    tid = _plan_id_from_name(child)
                    if tid:
                        found.add(tid)
    return sorted(found, key=lambda t: [int(p) for p in t.split("_")])


def _tally(base, cands, surfaces, hub_threshold, exclude):
    """One pass over the candidates at one threshold -> (counts, causes).

    Reads `base` -- an already-collected snapshot -- and never collects again,
    which is what makes rates at different thresholds comparable.
    """
    counts = {v: 0 for v in ("CLEAR", "CLEAR_CAVEATED", "CONFLICT", "UNCHECKABLE")}
    causes = {}
    for cand in cands:
        result = pa.decide(_respin(base, cand, surfaces[pa.canonical_ref(cand)],
                                   hub_threshold=hub_threshold,
                                   exclude=exclude))
        counts[result.verdict] += 1
        seen = set()
        for line in result.lines:
            if line.startswith("UNCHECKABLE_CAUSE:") or line.startswith("CAVEAT:"):
                reason = line.rsplit("|", 1)[-1]
                seen.add(reason.split(":", 1)[0])
        for reason in seen:
            causes[reason] = causes.get(reason, 0) + 1
    return counts, causes


def _rate_lines(prefix, threshold, n, counts, causes, cause_prefix):
    out = []
    head = "" if threshold is None else "%d|" % threshold
    out.append("%s:%s%d|%d|%d|%d|%d"
               % (prefix, head, n, counts["CLEAR"], counts["CLEAR_CAVEATED"],
                  counts["CONFLICT"], counts["UNCHECKABLE"]))
    # A bare "UNCHECKABLE 100%" cannot distinguish "this design does not work"
    # from "two named tasks need a plan". The histogram is what says which.
    for reason in sorted(causes):
        out.append("%s:%s%s|%d" % (cause_prefix, head, reason, causes[reason]))
    return out


def _run_replay(opts):
    cands, cand_source = _read_candidates(opts)
    out = []
    if not cands:
        sys.stdout.write("RATES:0|0|0|0|0\n")
        return 0
    # ONE snapshot, resolved once and re-aimed per candidate (see _respin).
    # The batch map and the corpora are resolved HERE and injected, so every
    # candidate is judged against the same world; deriving them per candidate
    # let a concurrent commit change the corpus mid-run and made the reported
    # rates incomparable. The SAME reasoning is why `--thresholds` sweeps inside
    # this one invocation rather than by re-invoking the CLI per threshold.
    batch_lines = _BATCH_MAP(opts["root"], with_recovered=True)
    tracked, dirs, corpora = resolve_corpora(opts["root"])
    # exclude_self=False: the base population must contain EVERY in-flight task.
    # Building it with self-exclusion would permanently drop whichever candidate
    # happened to be listed first, so every later candidate would be compared
    # against a world where that active task does not exist -- understating the
    # CONFLICT rate that t1569_4 uses as its entry criterion. Measured: listing a
    # live in-flight task first moved CONFLICT from 24 to 17 over 124 candidates.
    # Resolve every candidate surface up front, BEFORE any verdict is computed.
    # Reading plans inside the reporting loop would let a concurrent edit mix
    # plan states across a single run, and would read the first candidate's plan
    # twice (once for the base, once when its turn came).
    surfaces, surface_cache = {}, {}
    for c in cands:
        k = pa.canonical_ref(c)
        if k not in surfaces:
            surfaces[k] = resolve_candidate_surface(
                opts["root"], k, opts["from"], batch_lines, tracked, dirs,
                cache=surface_cache)
    base = collect(opts["root"], cands[0], source=opts["from"],
                   plan_path=None, freshness=opts["lock_freshness"],
                   max_lock_age_s=opts["max_lock_age"],
                   max_claim_age_s=opts["max_claim_age"],
                   hub_threshold=opts["hub_threshold"],
                   exclude_self=False, batch_lines=batch_lines,
                   corpus=(tracked, dirs, corpora),
                   candidate_surface=surfaces[pa.canonical_ref(cands[0])],
                   surface_cache=surface_cache)

    # The exclusion set is derived from THIS snapshot, never from a prior run.
    exclude = set(opts["exclude"] or ())
    if opts["exclude_no_plan"]:
        exclude |= set(no_plan_claims(base))
    exclude = tuple(sorted(exclude))

    thresholds = opts["thresholds"]
    if thresholds is None:
        # LEGACY SINGLE-THRESHOLD PATH -- byte-identical to what t1569_3 shipped,
        # because consumers and tests pin `RATES:`/`CAUSE_RATE:` exactly. The
        # threshold-qualified lines below appear only under `--thresholds`.
        for cand in cands:
            result = pa.decide(_respin(base, cand,
                                       surfaces[pa.canonical_ref(cand)],
                                       exclude=exclude))
            out.append("VERDICT_FOR:%s|%s"
                       % (pa.canonical_ref(cand), result.verdict))
        counts, causes = _tally(base, cands, surfaces, None, exclude)
        if exclude:
            out.append("EXCLUDED:%s" % ",".join(exclude))
        out.extend(_rate_lines("RATES", None, len(cands), counts, causes,
                               "CAUSE_RATE"))
        sys.stdout.write("".join(line + "\n" for line in out))
        return 0

    out.append("SNAPSHOT:%d|%d" % (base.now, len(base.inflight)))
    out.append("CANDIDATES:%d|%s" % (len(cands), cand_source))
    if exclude:
        out.append("EXCLUDED:%s" % ",".join(exclude))
    for threshold in thresholds:
        counts, causes = _tally(base, cands, surfaces, threshold, ())
        out.extend(_rate_lines("RATES_AT", threshold, len(cands), counts,
                               causes, "CAUSE_RATE_AT"))
        if exclude:
            # BOTH populations, from the one snapshot. A counterfactual rate is
            # structurally incapable of appearing without its unexcluded twin,
            # so it cannot be pasted onward as if it were the live figure.
            counts, causes = _tally(base, cands, surfaces, threshold, exclude)
            out.extend(_rate_lines("RATES_AT_EXCL", threshold, len(cands),
                                   counts, causes, "CAUSE_RATE_AT_EXCL"))
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


def _archived_plan_paths(root):
    """`{task_id: archived plan path}` -- the sweep's plan side."""
    base = os.path.join(root, "aiplans", "archived")
    found = {}
    if not os.path.isdir(base):
        return found
    for entry in sorted(os.listdir(base)):
        full = os.path.join(base, entry)
        if os.path.isfile(full):
            tid = _plan_id_from_name(entry)
            if tid:
                found.setdefault(tid, full)
        elif os.path.isdir(full):
            for child in sorted(os.listdir(full)):
                child_full = os.path.join(full, child)
                if os.path.isfile(child_full):
                    tid = _plan_id_from_name(child)
                    if tid:
                        found.setdefault(tid, child_full)
    return found


def sweep_population(root, plan_scope="full", batch_lines=None, corpus=None):
    """Build the archived-pairs population and the drift accounting.

    Returns ``(population, touch_counts, drift)`` where ``population`` is
    ``((ref, plan_surface, landed_paths), ...)`` and ``drift`` is
    ``(tasks, tokens_kept, tokens_dropped)``.

    A task joins only when BOTH sides are known: a resolved plan surface (what a
    `check` would have compared) and a resolved, non-empty landed file set (the
    oracle). A task missing either cannot be scored, and admitting it with an
    empty set would manufacture false no-collisions.
    """
    if batch_lines is None:
        batch_lines = _BATCH_MAP(root, with_recovered=True)
    if corpus is None:
        tracked, dirs, _corpora = resolve_corpora(root)
    else:
        tracked, dirs = corpus[0], corpus[1]
    touch = pa.touch_counts_from_batch_map(batch_lines)
    landed = pa.surfaces_from_batch_map(batch_lines)
    transform = (pas.cut_post_implementation
                 if plan_scope == "pre-implementation" else None)

    population = []
    tasks = kept = dropped = 0
    for tid, path in sorted(_archived_plan_paths(root).items()):
        landed_surface = landed.get(tid)
        if landed_surface is None or landed_surface.resolution != "resolved" \
                or not landed_surface.paths:
            continue
        extraction, _stripped = plan_extraction(tid, path, tracked, dirs,
                                                body_transform=transform)
        tasks += 1
        kept += len(extraction.paths)
        dropped += extraction.tokens_dropped
        if extraction.resolution != "resolved":
            continue
        population.append((tid, extraction.as_surface(),
                           frozenset(landed_surface.paths)))
    return tuple(population), touch, (tasks, kept, dropped)


def _run_sweep(opts):
    thresholds = opts["thresholds"] or (pa.HUB_THRESHOLD,)
    population, touch, drift = sweep_population(opts["root"],
                                                plan_scope=opts["plan_scope"])
    out = ["SWEEP_SCOPE:%s" % opts["plan_scope"]]
    # Emitted BEFORE the rows: the drop count is the size of the oracle's
    # corpus-drift bias, and a recall figure read without it looks more precise
    # than it is.
    out.append("SWEEP_DRIFT:%d|%d|%d" % drift)
    first = True
    for threshold in thresholds:
        conf = pas.confusion(population, touch, threshold)
        if first:
            out.insert(1, "SWEEP_POP:%d|%d|%d"
                       % (len(population), conf.pairs, conf.colliding))
            first = False
        out.append("SWEEP:%d|%d|%d|%d|%d|%d|%d|%d|%d"
                   % (threshold, conf.count("CLEAR"),
                      conf.count("CLEAR_CAVEATED"), conf.count("CONFLICT"),
                      conf.count("UNCHECKABLE"), conf.pred_conflict,
                      conf.tp_conflict, conf.tp_caveated, conf.missed))
        out.append("SWEEP_METRIC:%d|%s|%s|%s|%s"
                   % (threshold,
                      _fmt(pas.precision_conflict(conf)),
                      _fmt(pas.recall_flagged(conf)),
                      _fmt(pas.share_hard_stopped(conf)),
                      _fmt(pas.share_downgraded(conf))))
    sys.stdout.write("".join(line + "\n" for line in out))
    return 0


def _fmt(value):
    """A derived rate, or `-` when undefined. Never a plausible-looking default."""
    return "-" if value is None else "%.4f" % value


def main(argv):
    verb, opts = _parse_args(argv)
    if verb == "check":
        result = pa.decide(_collect_one(opts, opts["candidate"]))
        sys.stdout.write(pa.render(result))
        return 0
    if verb == "sweep":
        return _run_sweep(opts)
    return _run_replay(opts)



if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
