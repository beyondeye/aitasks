"""Closed vocabularies for the parallel-admission checker (t1569_3).

This module is the SINGLE definition of every enum and reason code the checker
can emit. `parallel_admission.render()` builds every reason through
`format_reason()`, and the exhaustiveness guard drives its assertions from these
tables -- neither restates the vocabulary. A reason string literal anywhere else
is the defect that guard exists to catch.

PURE: no imports beyond `re`. No I/O, no subprocess, no clock. The purity guard
imports this module with `subprocess` poisoned.

RECORD GRAMMAR
    Both reason-bearing records are

        <PREFIX>:<scope>|<reason>

    split on the FIRST `|`; `reason` is the free-ish last field. `scope` and
    `reason` each split on their FIRST `:`:

        CAVEAT:inflight:t259|stale_claim:184d
                └─scope─┘ └───reason───┘

    A path parameter is `_enc()`-encoded (see `encode_path`), so an embedded
    `|` or `%` cannot break either split.

PARAMETER SHAPES
    A reason is either a bare code or `<code>:<param>`. The table maps each code
    to the shape its parameter must take; the shape is what makes an
    exhaustiveness check possible without either duplicating the list or blindly
    accepting anything after a colon.
"""

import re

# --- parameter shapes -------------------------------------------------------
# A tuple literal in the tables below is a closed sub-vocabulary of permitted
# suffix tokens; these three constants cover the non-enumerable shapes.
NONE = None          # bare code, no suffix permitted
PATH = "path"        # ':' + an encode_path()-encoded repo-relative path
DAYS = "days"        # ':' + <int> + 'd'

_DAYS_RE = re.compile(r"^(0|[1-9][0-9]*)d$")

# Sources this checker enumerates. Deliberately differs from trail_gather's
# third name (`tracked`): corpus health is carried by CORPUS: here, and `status`
# is this checker's own probe (t1569_3 Step 7).
SOURCE_NAMES = ("gate", "lock", "status")

# Probe health only -- reused verbatim from trail_gather's INFLIGHT_SOURCE:.
SOURCE_STATUSES = ("ok", "degraded", "unavailable", "not_consulted")

CORPUS_NAMES = ("code", "data")
CORPUS_STATUSES = ("ok", "unavailable")

LOCK_STATES = ("fetched", "cached", "unavailable")
LOCK_MODES = ("require-fresh", "allow-cached")

VERDICTS = ("CLEAR", "CLEAR_CAVEATED", "CONFLICT", "UNCHECKABLE")

OVERLAP_CLASSES = ("specific", "hub")
NARROWED_CLASSES = ("hub", "frontmatter")

# Liveness classes (t1569_3 Step 7). `status_only` is a status without a lock,
# `lock_only` a lock without a status -- both half-evidenced, both caveat.
LIVENESS_CLASSES = ("live", "status_only", "lock_only", "dead", "unknown")

# Overlap-eligibility tiers (Step 7 2b).
TIERS = ("blocking", "advisory", "excluded")

PROVENANCES = (
    "plan_declared",
    "origin_derived",
    "plan_declared+origin_fallback",
)

ORIGIN_QUALITIES = ("exact", "topic", "unknown", "n/a")

# Candidate/in-flight surface resolution states.
SURFACE_RESOLUTIONS = (
    "resolved",
    "no_plan",
    "unreadable",
    "no_tokens",
    "no_extractable_paths",
    "all_phantom",
    "unknown_history",
    "unknown_origin",
)

# Aggregate path state of an in-flight source's surface.
PATH_STATES = ("resolved", "phantom", "mixed", "none")

# --- reason tables ----------------------------------------------------------

CAVEAT_REASONS = {
    "hub_overlap_only": PATH,          # Step 1: only hub paths overlapped
    "stale_claim_overlap": PATH,       # Step 7 2b: advisory-tier overlap
    "stale_claim": DAYS,               # Step 3: claim past --max-claim-age
    "unknown_claim_age": ("absent", "malformed", "clock_skew"),   # Step 3
    "no_liveness_token": NONE,         # Step 7: status_only holder
    "lock_only_holder": NONE,          # Step 7: locked but not Implementing
    "unknown_liveness": NONE,          # Step 7: anchorless / weak token
    "cross_host_lock": NONE,           # Step 7: hostname guard -> unknown
    "locks_cached": DAYS,              # Step 6: allow-cached accepted a stale ref
    "corpus_unavailable": CORPUS_NAMES,        # Step 5a
    "source_unavailable": SOURCE_NAMES,        # Step 2
    "source_degraded": SOURCE_NAMES,           # Step 2
    "recovered_only": NONE,            # Step 5b: RECOVERED_* caveated the verdict
}

UNCHECKABLE_REASONS = {
    # Imported verbatim from t1569_1's INFLIGHT_PATH: per-task sentinels.
    # Must stay byte-identical to .claude/skills/aitask-trail/SKILL.md.j2.
    "no_plan": NONE,
    "no_tokens": NONE,
    "unreadable": NONE,
    "unclassified": NONE,
    # Imported verbatim from trail_gather._locks_cache_age's reason vocabulary.
    "no_local_ref": NONE,
    "unreadable_tree": NONE,
    "no_reflog": NONE,
    "clock_skew": NONE,
    "timeout": NONE,
    "scan_error": NONE,
    # This checker's own.
    "all_phantom": NONE,
    "no_extractable_paths": NONE,
    "unknown_history": NONE,
    "unknown_origin": NONE,
    "source_unavailable": SOURCE_NAMES,
}

# The halves above that are imported rather than minted here. The drift guard
# asserts these against their upstream sources so a change to t1569_1's
# goldens-pinned vocabulary breaks loudly instead of forking silently.
IMPORTED_FROM_INFLIGHT_PATH = ("no_plan", "no_tokens", "unreadable", "unclassified")
IMPORTED_FROM_LOCKS_CACHE_AGE = (
    "no_local_ref",
    "unreadable_tree",
    "no_reflog",
    "clock_skew",
    "timeout",
    "scan_error",
)

_TABLES = {
    "CAVEAT": CAVEAT_REASONS,
    "UNCHECKABLE_CAUSE": UNCHECKABLE_REASONS,
}


class VocabularyError(ValueError):
    """A code/param pair that the table does not permit.

    This is a programming error, never a content state: the checker exits 0 for
    every content state, so a bad reason must fail loudly at construction rather
    than reach stdout.
    """


# --- path encoding ----------------------------------------------------------
# aitask_verification_stale.sh:122-127. '%' FIRST is what makes it injective:
# decode in reverse ('%7C' -> '|', then '%25' -> '%'), so a literal "%7C" in a
# filename round-trips as "%257C".


def encode_path(path):
    """Encode a path for a delimited field. `%` -> `%25` first, then `|`."""
    return str(path).replace("%", "%25").replace("|", "%7C")


def decode_path(token):
    """Inverse of `encode_path` -- reverse order, `%25` last."""
    return str(token).replace("%7C", "|").replace("%25", "%")


# --- reason formatting / parsing -------------------------------------------


def _shape_for(kind, code):
    try:
        table = _TABLES[kind]
    except KeyError:
        raise VocabularyError("unknown reason table: %r" % (kind,))
    if code not in table:
        raise VocabularyError("%s: undeclared reason code %r" % (kind, code))
    return table[code]


def format_reason(kind, code, param=None):
    """Build a reason field, validating `param` against the declared shape.

    `kind` is "CAVEAT" or "UNCHECKABLE_CAUSE". Raises VocabularyError on any
    code/param pair the table does not permit -- including a bare code given a
    suffix, a DAYS code given a path, and a sub-vocabulary code given a token
    outside its tuple.
    """
    shape = _shape_for(kind, code)
    if shape is NONE:
        if param is not None:
            raise VocabularyError(
                "%s:%s takes no parameter, got %r" % (kind, code, param))
        return code
    if param is None:
        raise VocabularyError("%s:%s requires a parameter" % (kind, code))
    if shape is PATH:
        return "%s:%s" % (code, encode_path(param))
    if shape is DAYS:
        token = param if isinstance(param, str) else "%dd" % (param,)
        if not _DAYS_RE.match(token):
            raise VocabularyError(
                "%s:%s expects <int>d, got %r" % (kind, code, param))
        return "%s:%s" % (code, token)
    # shape is a tuple: a closed sub-vocabulary
    if param not in shape:
        raise VocabularyError(
            "%s:%s expects one of %r, got %r" % (kind, code, shape, param))
    return "%s:%s" % (code, param)


def parse_reason(kind, text):
    """Split a reason field into `(code, param)` and validate it.

    Raises VocabularyError when the code is undeclared or the parameter does not
    match its declared shape -- this is what lets the guard assert that no
    literal escaped `format_reason`.
    """
    code, sep, param = str(text).partition(":")
    if not sep:
        param = None
    shape = _shape_for(kind, code)
    if shape is NONE:
        if param is not None:
            raise VocabularyError(
                "%s:%s takes no parameter, got %r" % (kind, code, param))
        return code, None
    if param is None:
        raise VocabularyError("%s:%s requires a parameter" % (kind, code))
    if shape is PATH:
        return code, decode_path(param)
    if shape is DAYS:
        if not _DAYS_RE.match(param):
            raise VocabularyError(
                "%s:%s expects <int>d, got %r" % (kind, code, param))
        return code, param
    if param not in shape:
        raise VocabularyError(
            "%s:%s expects one of %r, got %r" % (kind, code, shape, param))
    return code, param


def check_member(value, vocabulary, what):
    """Return `value` if it is a declared member, else raise.

    Used at every render site so an undeclared enum fails loudly rather than
    reaching stdout and degrading silently in a downstream consumer.
    """
    if value not in vocabulary:
        raise VocabularyError(
            "%s: %r is not one of %r" % (what, value, vocabulary))
    return value
