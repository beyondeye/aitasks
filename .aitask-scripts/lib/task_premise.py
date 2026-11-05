"""Task premise-staleness verdict core (t1663_1).

Has the code a task's premise depends on changed since the premise was last
known valid? Design record (source of truth):
``aidocs/framework/task_premise_staleness.md``.

PURE. No ``os``, no ``time``, no ``subprocess``, no I/O. Every input arrives as
already-materialised text rows; ``tests/test_parallel_admission_purity.py``
enforces it. The caller is responsible for having ``.aitask-scripts/lib`` on
``sys.path``. The git-facing producer is ``aitask_premise_stale.sh``; it does the
git work, hands this module interchange rows on stdin, and prints what
:func:`check` returns.

THE t1655 SUBSTITUTION CONTRACT. ``lib/roadmap_premise.py`` is a temporary
stand-in for this module; t1655 swaps the roadmap onto it and deletes that file.
The public surface is therefore frozen in ``__all__`` and pinned by
``tests/test_task_premise.py::PublicSurfaceTests``. Four properties the roadmap's
tests pin must survive the swap: the landing-commit baseline
(:func:`baseline_for`, semantics unchanged), ``UNKNOWN`` drives the verdict,
silent ``SKIP`` with distinct reasons, purity.

THE GOVERNING INVARIANT. ``FRESH`` is a *positive* claim, never the absence of a
failure. It requires every scope path to be present at both ends AND to carry a
successful history query whose commit count the producer attested. Every probe
failure, every malformed or missing row, every baseline that is not an
immutable commit id maps to evidence (``ASK_STALE``) or to ``SKIP`` -- never to
the no-evidence branch.

INTERCHANGE ROWS (producer -> core), one per line, blank lines ignored::

    REV:<oid>                                   the pinned checked revision
    BASE:<enc sha>|<enc ts>|<reason-or-empty>   the stored baseline / failed precondition
    TIER:<A|B|NONE>|<n_paths>|<n_origins>       counts attest the rows below
    ORIGIN:<id>|<FILES|NO_FILES|UNKNOWN_HISTORY>
    PATH:<enc path>|ok|<n_log>                  n_log attests its LOG rows
    PATH:<enc path>|<deleted|absent_at_baseline|history_unavailable|invalid_reference|no_index_history>
    LOG:<enc path>|<oid>|<task-ids csv>
    GONE:<enc path>|<culprit>|<sanitized subject>

ROW INTEGRITY. The interchange has one producer per consumer, so a row that does
not parse is a defect report, never noise to skip. A row whose *path* is still
recoverable turns that path into ``UNKNOWN:<path>|malformed_row``; anything that
makes the scope itself unknown (an unparseable ``PATH:`` or ``ORIGIN:`` row, a
count mismatch, an unknown prefix, a missing or duplicated ``REV:``/``BASE:``/
``TIER:``) is ``SKIP``/``engine_error``. A dropped or mangled ``LOG:`` row can
therefore only *add* evidence (via its path's count), and a dropped ``PATH:`` row
can only produce ``SKIP``.

IMMUTABLE BASELINE. A ``BASE:`` row with no reason must carry a full 40- or
64-hex object id. The producer enforces the same grammar before any git probe;
this module re-checks it so no producer (t1655's adapter included) can pass a
symbol through: ``HEAD`` is an ancestor of every checked revision, so
``HEAD..<rev>`` is empty and would read ``FRESH`` over a real change.

PUBLISHED PROTOCOL (core -> producer -> caller), fixed order::

    BASELINE:<sha>|<enc ts>   or  BASELINE:NONE
    CHECKED:<oid>             or  CHECKED:NONE   (NONE: no revision was pinned)
    FINGERPRINT:<16 hex>      or  FINGERPRINT:NONE   (NONE on every SKIP)
    FILES:<n>
    CHANGED:<enc path>|<n_commits>|<task_ids>        0+ lines
    DELETED:<enc path>|<culprit_task>|<subject>      0+ lines
    UNKNOWN:<enc path or origin id>|<reason>         0+ lines
    DISPLAY:<one-line human summary>
    DECISION:<FRESH|ASK_STALE|SKIP>

TASK FIELDS (core -> producer, a third vocabulary): :func:`task_fields` turns the
frontmatter mapping the framework's YAML reader parsed into
``FIELD_BASELINE:`` / ``FIELD_REF:`` / ``FIELD_BADREF:`` lines closed by a
``FIELD_END:<n>`` count, or ``FIELD_INVALID:frontmatter``. ``file_references:``
is read as YAML, never comma-split: the valid entry ``"a,b.py"`` is one path.

ENCODING (all vocabularies): ``%`` -> ``%25`` first, then ``|`` -> ``%7C``, LF ->
``%0A``, CR -> ``%0D``; decode in reverse with ``%25`` last. It is
``parallel_admission_vocab.encode_path`` extended by LF/CR, so a newline-bearing
filename stays one field on one line; injective because ``%`` goes first.
``DISPLAY:`` is free text carrying raw paths, except LF/CR, shown as their
escapes so the line framing cannot break. The ``DELETED`` subject is sanitized
(``|`` -> space), not encoded -- display text, never an identity key.
"""

import hashlib
import json
import re
from dataclasses import dataclass, field

import parallel_admission_vocab as vocab

# The substitution contract with t1655. Pinned by PublicSurfaceTests -- adding a
# name here is a deliberate widening of what t1655 consumes, never a tidy-up.
__all__ = [
    "FRESH", "ASK_STALE", "SKIP", "DECISIONS",
    "BASELINE_REASONS", "PATH_REASONS", "SCOPE_REASONS", "ENV_REASONS", "REASONS",
    "PATH_STATES", "TIERS", "DEFAULT_DATA_PREFIXES", "FINGERPRINT_VERSION",
    "ROW_PREFIXES", "LINE_PREFIXES", "FIELD_PREFIXES", "ORIGIN_STATUSES",
    "Baseline", "PremiseResult",
    "baseline_for", "check", "fingerprint", "encode_field", "decode_field",
    "task_fields",
]

FRESH = "FRESH"
ASK_STALE = "ASK_STALE"
SKIP = "SKIP"
DECISIONS = (FRESH, ASK_STALE, SKIP)

# Why no usable baseline exists. Closed vocabulary; each value a distinct remedy.
BASELINE_REASONS = (
    "no_origin",           # baseline_for: the task resolved to no origin at all
    "unknown_history",     # baseline_for: origin known, no `(tNN)` commit anywhere
    "metadata_only",       # baseline_for: tagged commits exist, all task-data
    "no_stored_baseline",  # the task carries no premise_baseline:
    "invalid_baseline",    # premise_baseline: is not a full commit id (HEAD, a branch, ...)
    "history_rewritten",   # the baseline is not an ancestor of the checked revision
)

# Why one scope path could not be checked. Every one drives the verdict.
PATH_REASONS = (
    "no_index_history",     # (roadmap adapter) the path has no commit row at all
    "absent_at_baseline",   # the path did not exist in the baseline tree
    "invalid_reference",    # a file_references: entry that is not a path
    "history_unavailable",  # the history query for this path FAILED (not: was empty)
    "malformed_row",        # this path's evidence rows did not parse or count up
)

# Why the check covered nothing even though a baseline existed.
SCOPE_REASONS = (
    "empty_scope",          # no file surface to compare
    "scope_error",          # the scope could not be resolved (a reader/subprocess failed,
                            # or the origin map failed its own count attestation)
    "invalid_frontmatter",  # the task's frontmatter is not valid YAML
)

# Environment / engine failures. `python_unavailable` and the shell-side
# `engine_error` are emitted by the producer itself (the core is unreachable or
# untrusted there); they live here so the vocabulary has one home.
ENV_REASONS = ("not_a_git_repo", "python_unavailable", "engine_error")

REASONS = BASELINE_REASONS + PATH_REASONS + SCOPE_REASONS + ENV_REASONS

PATH_STATES = ("ok", "deleted", "absent_at_baseline", "history_unavailable",
               "invalid_reference", "no_index_history")

ORIGIN_STATUSES = ("FILES", "NO_FILES", "UNKNOWN_HISTORY")

TIERS = ("A", "B", "NONE")

# Trees that hold task data rather than code (see roadmap_premise). Injected,
# never assumed: TASK_DIR / PLAN_DIR are configurable.
DEFAULT_DATA_PREFIXES = ("aitasks/", "aiplans/", ".aitask-gates/")

FINGERPRINT_VERSION = "1"

ROW_PREFIXES = ("REV", "BASE", "TIER", "ORIGIN", "PATH", "LOG", "GONE")
LINE_PREFIXES = ("BASELINE", "CHECKED", "FINGERPRINT", "FILES", "CHANGED",
                 "DELETED", "UNKNOWN", "DISPLAY", "DECISION")
# What :func:`task_fields` emits to the producer (a third vocabulary, disjoint
# from both of the above).
FIELD_PREFIXES = ("FIELD_BASELINE", "FIELD_REF", "FIELD_BADREF", "FIELD_END",
                  "FIELD_INVALID")

# Preconditions a producer may report on the BASE row. `empty_scope` is computed
# here, never passed in; `engine_error` / `python_unavailable` never reach here.
_BASE_ROW_REASONS = BASELINE_REASONS + ("scope_error", "invalid_frontmatter",
                                        "not_a_git_repo")

_OID_RE = re.compile(r"^(?:[0-9a-f]{40}|[0-9a-f]{64})$")
_OID_ANYCASE_RE = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
_ID_RE = re.compile(r"^[0-9]+(?:_[0-9]+)?$")
_COUNT_RE = re.compile(r"^[0-9]+$")
# A well-formed encoded field: no raw delimiter or line break, and every `%`
# starts one of the four escapes.
_ENCODED_RE = re.compile(r"^(?:[^%|\r\n]|%(?:25|7C|0A|0D))*$")

_LINE_BREAKS = (("\n", "%0A"), ("\r", "%0D"))
_NUL = "\x00"


def encode_field(value):
    """``%``/``|`` via ``vocab.encode_path``, then LF and CR. Injective."""
    out = vocab.encode_path(value)
    for raw, escaped in _LINE_BREAKS:
        out = out.replace(raw, escaped)
    return out


def decode_field(token):
    """Inverse of :func:`encode_field` -- line breaks first, ``%25`` last."""
    out = str(token)
    for raw, escaped in reversed(_LINE_BREAKS):
        out = out.replace(escaped, raw)
    return vocab.decode_path(out)


def _well_formed(token):
    return bool(token) and _ENCODED_RE.match(token) is not None


def _display_safe(text):
    """Raw text for DISPLAY:, with only the line breaks escaped."""
    out = str(text)
    for raw, escaped in _LINE_BREAKS:
        out = out.replace(raw, escaped)
    return out


# --- baseline_for (carried from roadmap_premise, semantics unchanged) ---------


@dataclass(frozen=True)
class Baseline:
    """The origin's last landing commit, or why there is none."""

    sha: str = None
    committed_at: int = None
    reason: str = None      # one of BASELINE_REASONS when sha is None

    @property
    def resolved(self):
        return self.sha is not None


def _commit_rows(commit_lines):
    """``COMMIT:<path>|<sha>|<ct>|<ids csv>`` -> ``(path, sha, ct, ids)``.

    Split right-to-left (``--batch-map`` emits the path raw by default). A
    malformed row is skipped -- this function feeds only ``baseline_for``, whose
    answer is a commit *choice*, not an all-clear; the verdict path in
    :func:`check` is strict.
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

    A landing commit names an origin id AND touches at least one path outside
    ``data_prefixes``. Ties on ``committed_at`` break on the sha, so the answer
    is total and deterministic. (Measured 2026-08-31: 35 of 1615 tagged ids have
    a metadata-only newest tagged commit -- an unqualified "newest tagged
    commit" would mask real drift as FRESH.)
    """
    wanted = {str(o) for o in (origin_ids or ()) if str(o)}
    if not wanted:
        return Baseline(reason="no_origin")

    prefixes = tuple(data_prefixes)
    tagged = False
    landing = set()
    for path, sha, ct, ids in _commit_rows(commit_lines):
        if wanted.isdisjoint(ids):
            continue
        tagged = True
        if not path.startswith(prefixes):
            landing.add((ct, sha))

    if landing:
        ct, sha = max(landing)
        return Baseline(sha=sha, committed_at=ct)
    return Baseline(reason="metadata_only" if tagged else "unknown_history")


# --- fingerprint ----------------------------------------------------------------


def fingerprint(baseline_sha, tier, paths, origin_ids):
    """16-hex digest binding the METADATA inputs a verdict depended on.

    Excludes the checked revision and the baseline timestamp: ordinary new
    commits must not void a confirmation, but a concurrent edit to
    ``file_references:``, the origins, or the stored baseline must.
    """
    # Structured serialization, so list boundaries are unambiguous: a comma-
    # joined list made the scope ["a,b"] collide with ["a", "b"]. ensure_ascii
    # escapes every non-ASCII code point (lone surrogates included), so the blob
    # always encodes.
    payload = [FINGERPRINT_VERSION, "stored", str(baseline_sha or ""), str(tier or ""),
               sorted({str(p) for p in (paths or ())}),
               sorted({str(o) for o in (origin_ids or ())})]
    blob = json.dumps(payload, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("ascii")).hexdigest()[:16]


# --- task_fields -----------------------------------------------------------------


def task_fields(metadata):
    """The two task fields the producer reads, as count-attested lines.

    ``metadata`` is the frontmatter mapping as the framework's YAML reader
    (``task_yaml.parse_frontmatter``) parsed it, or ``None`` when the file has no
    parseable frontmatter. Reading the field through YAML -- not by splitting the
    flow list on commas -- is what keeps a quoted entry such as ``"a,b.py"`` one
    path. Output (every value ``encode_field``-encoded)::

        FIELD_BASELINE:<enc premise_baseline, or empty>
        FIELD_REF:<enc entry>        one per string file_references: entry
        FIELD_BADREF:<enc diagnostic>  one per entry that is not a usable string
        FIELD_END:<number of FIELD_REF + FIELD_BADREF lines>

    or the single line ``FIELD_INVALID:frontmatter``. The producer checks the
    END count, so a truncated read can never shrink the scope silently.

    ONLY A STRING IS A PATH. YAML resolves unquoted ``null``, ``on`` and ``010``
    to ``None``, ``True`` and ``8``: dropping the first would silently shrink the
    scope, and stringifying the others would watch files named ``True`` and
    ``8`` instead of ``on`` and ``010``. Every non-string entry is therefore a
    ``FIELD_BADREF`` -- present, counted, and uncheckable (``ASK_STALE``) -- never
    skipped and never coerced. A non-string ``premise_baseline:`` is likewise
    passed on as a diagnostic that fails the commit-id grammar.

    NO NUL CROSSES INTO BASH. Bash command substitution drops NUL bytes (with a
    warning on stderr), so ``"a\\0.py"`` would arrive as ``a.py``. A value holding
    NUL is rejected HERE, as a diagnostic built with ``repr`` (which escapes it);
    encoding NUL would only move the corruption to the decoder.
    """
    if not isinstance(metadata, dict):
        return ("FIELD_INVALID:frontmatter",)

    base = metadata.get("premise_baseline")
    if base is None:
        base = ""
    elif not isinstance(base, str) or _NUL in base:
        base = "<invalid premise_baseline: %r>" % (base,)

    # The string-only rule has ONE definition, shared with the shell reader
    # get_file_references(). Imported here rather than at module top: this
    # function's only callers (the producer's fields glue and the tests) already
    # load task_yaml, while the core check() path must not grow a yaml import.
    from task_yaml import file_reference_entries

    lines = ["FIELD_BASELINE:" + encode_field(base)]
    for ok, item in file_reference_entries(metadata):
        if ok:
            lines.append("FIELD_REF:" + encode_field(item))
        else:
            lines.append("FIELD_BADREF:" + encode_field(
                "<invalid file_references entry: %r>" % (item,)))
    lines.append("FIELD_END:%d" % (len(lines) - 1))
    return tuple(lines)


# --- check ----------------------------------------------------------------------


@dataclass(frozen=True)
class PremiseResult:
    decision: str
    reason: str = None          # the SKIP reason; None for FRESH / ASK_STALE
    baseline_sha: str = None
    checked: str = None
    fingerprint: str = None
    tier: str = None
    changed: tuple = ()         # (path, n_commits, task_ids tuple)
    deleted: tuple = ()         # (path, culprit, subject)
    unknown: tuple = ()         # (path-or-origin-id, reason)
    lines: tuple = field(default_factory=tuple)


class _Integrity(Exception):
    """The row set cannot be trusted as a whole -> SKIP/engine_error."""


class _Rows:
    def __init__(self):
        self.rev = None
        self.base = None        # (sha_raw, ts_raw, reason)
        self.tier = None        # (tier, n_paths, n_origins)
        self.origins = []       # [(id, status)]
        self.paths = {}         # decoded path -> {"state", "n", "malformed"}
        self.logs = {}          # decoded path -> [(sha, ids) | None-if-malformed]
        self.gone = {}          # decoded path -> (culprit, subject)


def _parse(rows):
    r = _Rows()
    for raw in rows:
        line = raw[:-1] if raw.endswith("\n") else raw
        if line == "":
            continue
        prefix, sep, rest = line.partition(":")
        if not sep or prefix not in ROW_PREFIXES:
            raise _Integrity("unknown row")
        handler = _HANDLERS[prefix]
        handler(r, rest)
    return r


def _row_rev(r, rest):
    if r.rev is not None or not _OID_RE.match(rest):
        raise _Integrity("REV")
    r.rev = rest


def _row_base(r, rest):
    parts = rest.split("|")
    if r.base is not None or len(parts) != 3:
        raise _Integrity("BASE")
    sha_tok, ts_tok, reason = parts
    if (sha_tok and not _well_formed(sha_tok)) or (ts_tok and not _well_formed(ts_tok)):
        raise _Integrity("BASE field")
    if reason and reason not in _BASE_ROW_REASONS:
        raise _Integrity("BASE reason")
    r.base = (decode_field(sha_tok), decode_field(ts_tok), reason)


def _row_tier(r, rest):
    parts = rest.split("|")
    if (r.tier is not None or len(parts) != 3 or parts[0] not in TIERS
            or not _COUNT_RE.match(parts[1]) or not _COUNT_RE.match(parts[2])):
        raise _Integrity("TIER")
    r.tier = (parts[0], int(parts[1]), int(parts[2]))


def _row_origin(r, rest):
    parts = rest.split("|")
    if (len(parts) != 2 or not _ID_RE.match(parts[0])
            or parts[1] not in ORIGIN_STATUSES
            or any(o == parts[0] for o, _ in r.origins)):
        raise _Integrity("ORIGIN")
    r.origins.append((parts[0], parts[1]))


def _row_path(r, rest):
    parts = rest.split("|")
    if not _well_formed(parts[0]) or len(parts) < 2 or parts[1] not in PATH_STATES:
        raise _Integrity("PATH")
    path = decode_field(parts[0])
    if path in r.paths:
        raise _Integrity("duplicate PATH")
    entry = {"state": parts[1], "n": None, "malformed": False}
    if parts[1] == "ok":
        if len(parts) == 3 and _COUNT_RE.match(parts[2]):
            entry["n"] = int(parts[2])
        else:
            entry["malformed"] = True
    elif len(parts) != 2:
        entry["malformed"] = True
    r.paths[path] = entry


def _row_log(r, rest):
    parts = rest.split("|")
    if not _well_formed(parts[0]):
        raise _Integrity("LOG path")
    path = decode_field(parts[0])
    ids = tuple(parts[2].split(",")) if len(parts) == 3 and parts[2] else ()
    if (len(parts) == 3 and _OID_RE.match(parts[1])
            and all(_ID_RE.match(t) for t in ids)):
        r.logs.setdefault(path, []).append((parts[1], ids))
    else:
        r.logs.setdefault(path, []).append(None)   # counted, and marks the path


def _row_gone(r, rest):
    parts = rest.split("|")
    if not _well_formed(parts[0]):
        raise _Integrity("GONE path")
    path = decode_field(parts[0])
    if path in r.gone:
        raise _Integrity("duplicate GONE")
    culprit = parts[1] if len(parts) == 3 else None
    if culprit is not None and culprit != "unknown" and not _ID_RE.match(culprit):
        culprit = None
    r.gone[path] = (culprit, parts[2] if culprit is not None else None)


_HANDLERS = {
    "REV": _row_rev, "BASE": _row_base, "TIER": _row_tier, "ORIGIN": _row_origin,
    "PATH": _row_path, "LOG": _row_log, "GONE": _row_gone,
}


def _validate(r):
    """Cross-row integrity. Raises _Integrity; marks recoverable paths malformed."""
    if r.base is None or r.tier is None:
        raise _Integrity("missing BASE/TIER")
    _, n_paths, n_origins = r.tier
    if len(r.paths) != n_paths or len(r.origins) != n_origins:
        raise _Integrity("count")
    for path in list(r.logs) + list(r.gone):
        if path not in r.paths:
            raise _Integrity("orphan evidence row")
    for path, entry in r.paths.items():
        rows = r.logs.get(path, [])
        if entry["state"] == "ok":
            if entry["malformed"] or None in rows or len(rows) != entry["n"]:
                entry["malformed"] = True
        else:
            if rows:            # history rows for a path that was not compared
                entry["malformed"] = True
        if path in r.gone and entry["state"] != "deleted":
            entry["malformed"] = True


def _hdr(baseline_sha, ts, checked, fp, files):
    base = "BASELINE:NONE" if not baseline_sha else \
        "BASELINE:%s|%s" % (baseline_sha, encode_field(ts))
    return [base,
            "CHECKED:%s" % (checked or "NONE"),
            "FINGERPRINT:%s" % (fp or "NONE"),
            "FILES:%d" % files]


_SKIP_TEXT = {
    "no_origin": "the task resolved to no origin",
    "unknown_history": "no commit names the origin",
    "metadata_only": "the origin's commits touch only task data",
    "no_stored_baseline": "the task carries no premise_baseline:",
    "invalid_baseline": "premise_baseline: is not a full commit id",
    "history_rewritten": "the baseline is not an ancestor of the checked revision (history rewritten)",
    "empty_scope": "the task has no file surface to compare",
    "scope_error": "the task's file scope could not be resolved",
    "invalid_frontmatter": "the task's frontmatter is not valid YAML",
    "not_a_git_repo": "not inside a git repository",
    "engine_error": "the premise engine received inconsistent evidence",
}


def _skip(reason, baseline_sha=None, ts="", checked=None, files=0, detail=""):
    text = _SKIP_TEXT.get(reason, reason)
    if detail:
        text = "%s (%s)" % (text, detail)
    lines = _hdr(baseline_sha, ts, checked, None, files) + [
        "DISPLAY:Premise check skipped (%s): %s." % (reason, _display_safe(text)),
        "DECISION:%s" % SKIP,
    ]
    return PremiseResult(decision=SKIP, reason=reason, baseline_sha=baseline_sha,
                         checked=checked, lines=tuple(lines))


def _names(items, cap=5):
    shown = [_display_safe(i) for i in items[:cap]]
    if len(items) > cap:
        shown.append("+%d more" % (len(items) - cap))
    return ", ".join(shown)


def check(rows):
    """Decide FRESH / ASK_STALE / SKIP from interchange rows (see module doc).

    Never raises on content: an untrustworthy row set is ``SKIP``/``engine_error``.
    """
    try:
        r = _parse(rows)
        _validate(r)
    except (_Integrity, UnicodeError):
        # UnicodeError: a non-UTF-8 byte reached the row stream (the caller
        # decodes stdin strictly) -- the rows are not what the producer meant.
        return _skip("engine_error")

    sha_raw, ts, reason = r.base
    sha_ok = bool(_OID_ANYCASE_RE.match(sha_raw))
    sha = sha_raw.lower() if sha_ok else None
    files = len(r.paths)

    if reason:
        detail = ""
        if reason == "invalid_baseline" and sha_raw:
            detail = "stored value %r" % sha_raw[:40]
        return _skip(reason, baseline_sha=sha, ts=ts, checked=r.rev, files=files,
                     detail=detail)
    if not sha_ok:
        # The producer should have caught this; the core re-checks so a symbol
        # can never reach the comparison from any producer.
        return _skip("invalid_baseline", checked=r.rev, files=files,
                     detail=("stored value %r" % sha_raw[:40]) if sha_raw else "empty")
    if r.rev is None:
        return _skip("engine_error", baseline_sha=sha, ts=ts, files=files)
    if not r.paths:
        return _skip("empty_scope", baseline_sha=sha, ts=ts, checked=r.rev)

    changed, deleted, unknown = [], [], []
    for path in sorted(r.paths):
        entry = r.paths[path]
        if entry["malformed"]:
            unknown.append((path, "malformed_row"))
        elif entry["state"] == "ok":
            if entry["n"]:
                ids = sorted({t for _, tids in r.logs.get(path, []) for t in tids},
                             key=_id_sort_key)
                changed.append((path, entry["n"], tuple(ids)))
        elif entry["state"] == "deleted":
            culprit, subject = r.gone.get(path, (None, None))
            deleted.append((path, culprit or "unknown",
                            (subject or "").replace("|", " ")))
        else:
            unknown.append((path, entry["state"]))
    for origin, status in sorted(r.origins, key=lambda o: _id_sort_key(o[0])):
        if status == "UNKNOWN_HISTORY":
            unknown.append((origin, "unknown_history"))

    tier = r.tier[0]
    fp = fingerprint(sha, tier, list(r.paths), [o for o, _ in r.origins])
    head = _hdr(sha, ts, r.rev, fp, files)

    evidence = (["CHANGED:%s|%d|%s" % (encode_field(p), n, ",".join(ids))
                 for p, n, ids in changed]
                + ["DELETED:%s|%s|%s" % (encode_field(p), c, s) for p, c, s in deleted]
                + ["UNKNOWN:%s|%s" % (encode_field(p), why) for p, why in unknown])

    # One evidence list: the verdict is an emptiness test over it, so "a path I
    # could not check" can never stop counting while "a path that changed" does.
    if not evidence:
        display = ("DISPLAY:All %d watched file(s) unchanged since %s (%s) — "
                   "premise looks current." % (files, sha[:12], _display_safe(ts)))
        return PremiseResult(decision=FRESH, baseline_sha=sha, checked=r.rev,
                             fingerprint=fp, tier=tier,
                             lines=tuple(head + [display, "DECISION:%s" % FRESH]))

    bits = []
    if changed:
        bits.append("changed: %s" % _names([p for p, _, _ in changed]))
    if deleted:
        bits.append("deleted: %s" % _names([p for p, _, _ in deleted]))
    if unknown:
        bits.append("could not check: %s" % _names(
            ["origin t%s (unknown_history)" % p if why == "unknown_history"
             else "%s (%s)" % (p, why) for p, why in unknown]))
    display = ("DISPLAY:Premise may no longer hold — since baseline %s (%s), "
               "%d watched file(s): %s." % (sha[:12], _display_safe(ts), files,
                                            "; ".join(bits)))
    return PremiseResult(decision=ASK_STALE, baseline_sha=sha, checked=r.rev,
                         fingerprint=fp, tier=tier, changed=tuple(changed),
                         deleted=tuple(deleted), unknown=tuple(unknown),
                         lines=tuple(head + evidence + [display,
                                                        "DECISION:%s" % ASK_STALE]))


def _id_sort_key(task_id):
    parts = str(task_id).split("_")
    return tuple(int(p) if p.isdigit() else 0 for p in parts)
