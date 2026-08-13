#!/usr/bin/env python3
"""Classify existing tasks by auto-spawned-follow-up provenance (t1468_6).

Pure classifier for the `followup_kind` backfill. Given task file paths it
decides, for each, which follow-up kind the task would have carried had
`followup_kind:` existed when it was created.

Deliberately side-effect free: no writes, no git, no subprocess. The driver
(`aitask_followup_backfill.sh`) owns all of that, so rule order can be
unit-tested without touching a task file.

Two properties are load-bearing and easy to get wrong:

1. **Frontmatter rules are scoped to the leading `---` block.** A whole-file
   grep for `issue_type: manual_verification` false-positives on tasks that
   quote an example frontmatter block in their body (the corpus contains one:
   t583_9, whose real type is `test`). We therefore parse with the canonical
   `task_yaml.parse_frontmatter` rather than matching lines.

2. **Body patterns are anchored on the producer's full sentence**, including
   the `from t<id>` / `for t<id>` tail. The bare marker prefixes appear inside
   markdown rule tables in the tasks that SPECIFY this feature (t1468 and
   t1468_6), so a prefix match classifies the spec as its own subject.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from task_yaml import parse_frontmatter  # noqa: E402


# --- rule order -------------------------------------------------------------
#
# First match wins. Prose-provenance rules come BEFORE the `issue_type`
# fallback: body prose records *who spawned the task*, while `issue_type`
# records *what kind of work it is*. A risk-mitigation follow-up that happens
# to be a manual-verification checklist is a risk mitigation whose work is
# verification -- and the live Step-8d creation seam agrees, having already
# marked t1477 and t1508 `followup_kind: risk_mitigation` despite their
# `issue_type: manual_verification`.
#
# `manual_verification` is therefore the FALLBACK for MV-typed tasks with no
# more specific provenance. This also keeps the cross-field invariant
# (`followup_kind: manual_verification` requires `issue_type:
# manual_verification`) true by construction: this is the only rule that
# produces that kind, and it fires only when the type already matches.
RULE_ORDER = (
    "carry_over",
    "risk_mitigation",
    "upstream_defect",
    "verification_failure",
    "manual_verification",
    "review_finding",
    "qa_test_gap",
    "docs_gap",
)

# The prose-provenance rules. Each task was spawned by exactly one producer, so
# two of these matching one task is a rule bug -- reported as a CONFLICT rather
# than silently resolved by ordering.
#
# `manual_verification` is NOT in this set: it is the issue_type fallback and
# legitimately co-occurs with `carry_over` (7 tasks) and `risk_mitigation`
# (8 tasks). Asserting disjointness against it would fire on correct data.
PROSE_PROVENANCE_RULES = frozenset(
    {"carry_over", "risk_mitigation", "upstream_defect", "verification_failure"}
)

_TASK_REF = r"t\d+(?:_\d+)?"

# aitask_archive.sh:601 emits the whole sentence; requiring the `from t<id>`
# tail is what excludes the spec tables that quote only the prefix.
RE_CARRY_OVER = re.compile(
    r"Carry-over of deferred manual-verification items from " + _TASK_REF
)

# risk-mitigation-followup.md emits TWO shapes and they differ:
#   :409  Risk-mitigation ("before") for t<id>,
#   :524  Risk-mitigation ("after") follow-up for t<id>,
# The "before" variant has no "follow-up", so that word must be optional or
# every pre-implementation mitigation is missed.
RE_RISK_MITIGATION = re.compile(
    r"Risk-mitigation \((?:\"before\"|\"after\")\)(?: follow-up)? for " + _TASK_REF
)

RE_UPSTREAM_HEADING = re.compile(r"^## Upstream defect", re.MULTILINE)
RE_UPSTREAM_SPAWNED = re.compile(r"Spawned from " + _TASK_REF + r" during Step 8b review")
RE_VERIFICATION_FAILURE = re.compile(r"^## Failed verification item from t", re.MULTILINE)
RE_ORIGIN_HEADING = re.compile(r"^## Origin", re.MULTILINE)


def _labels(metadata):
    """Frontmatter labels as a list of exact tokens."""
    raw = metadata.get("labels")
    if not raw:
        return []
    if isinstance(raw, str):
        return [t.strip() for t in raw.strip("[]").split(",") if t.strip()]
    return [str(t).strip() for t in raw]


def _rule_matches(rule, metadata, body, filename):
    """Does a single rule fire? Pure predicate, no ordering applied."""
    if rule == "carry_over":
        return bool(RE_CARRY_OVER.search(body))
    if rule == "risk_mitigation":
        return bool(RE_RISK_MITIGATION.search(body))
    if rule == "upstream_defect":
        return bool(RE_UPSTREAM_HEADING.search(body) or RE_UPSTREAM_SPAWNED.search(body))
    if rule == "verification_failure":
        return bool(RE_VERIFICATION_FAILURE.search(body))
    if rule == "manual_verification":
        return metadata.get("issue_type") == "manual_verification"
    if rule == "review_finding":
        return "review" in _labels(metadata)
    if rule == "qa_test_gap":
        return "qa" in _labels(metadata)
    if rule == "docs_gap":
        return "docs_gaps_since_" in filename
    raise ValueError("unknown rule: %s" % rule)


def classify(metadata, body, filename):
    """Classify one task.

    Returns a dict with:
        kind        -- assigned followup_kind, or None for residue
        rule        -- the rule that fired, or None
        conflict    -- sorted list of prose-provenance rules that co-fired
                       (len > 1 means a rule bug), else []
        already     -- existing followup_kind value, or None
        has_origin  -- whether the body carries a `## Origin` heading
    """
    matched = [r for r in RULE_ORDER if _rule_matches(r, metadata, body, filename)]
    prose = sorted(r for r in matched if r in PROSE_PROVENANCE_RULES)

    result = {
        "kind": None,
        "rule": None,
        "conflict": prose if len(prose) > 1 else [],
        "already": metadata.get("followup_kind") or None,
        "has_origin": bool(RE_ORIGIN_HEADING.search(body)),
    }
    if matched:
        # RULE_ORDER is the precedence; `matched` preserves it.
        result["rule"] = matched[0]
        result["kind"] = matched[0]
    return result


def classify_path(path):
    """Classify a task file. Returns None when the file has no frontmatter."""
    with open(path, "r", encoding="utf-8") as fh:
        raw = fh.read()
    parsed = parse_frontmatter(raw)
    if parsed is None:
        return None
    metadata, body, _ = parsed
    return classify(metadata, body, os.path.basename(path))


def task_id_from_path(path):
    """`aitasks/t1468/t1468_6_foo.md` -> `1468_6`."""
    stem = os.path.basename(path)
    m = re.match(r"^t(\d+(?:_\d+)?)_", stem)
    return m.group(1) if m else None


def _norm_scalar(v):
    """Canonicalise a value for COMPARISON only (never for writing).

    `aitask_update.sh` rewrites frontmatter through its own serializer, which
    canonicalises task-id lists -- `verifies: ['635_11']` comes back as
    `verifies: [t635_11]`. That is the framework's normal behaviour on any
    `ait update`, not something the backfill introduces, so the delta check
    must not mistake it for corruption. Compare id-ish strings with quotes and
    the `t` prefix removed.
    """
    if isinstance(v, list):
        return [_norm_scalar(x) for x in v]
    s = str(v).strip().strip("'\"")
    if re.fullmatch(r"t?\d+(?:_\d+)?", s):
        return s.lstrip("t")
    return s


def delta_report(before_text, after_text, kind):
    """Compare two versions of a task file SEMANTICALLY.

    Line diffs are the wrong instrument here: the serializer may legitimately
    reorder keys (YAML mapping order is not semantic) and canonicalise id
    lists. What actually matters is that nothing is LOST and nothing unrelated
    is changed.

    Returns (verdict, details) where verdict is one of:
        OK              -- only followup_kind added, only updated_at changed
        OK_NORMALIZED   -- the above, plus framework id-canonicalisation
        BAD             -- a key was lost, or an unrelated value changed
    """
    b = parse_frontmatter(before_text)
    a = parse_frontmatter(after_text)
    if b is None or a is None:
        return "BAD", ["frontmatter unparseable"]
    bmeta, bbody, _ = b
    ameta, abody, _ = a

    details = []
    verdict = "OK"

    if bbody != abody:
        # The serializer normalises blank lines around the body (a task written
        # with `---\n\n\n## Origin` comes back with one blank line). That is
        # whitespace-only and loses nothing. Anything else -- including any
        # change to internal whitespace -- is a real body edit and is BAD, so
        # no content can hide behind this tolerance.
        if bbody.strip() == abody.strip():
            verdict = "OK_NORMALIZED"
            details.append("body leading/trailing whitespace normalised")
        else:
            return "BAD", ["task body changed"]

    added = set(ameta) - set(bmeta)
    removed = set(bmeta) - set(ameta)
    if removed:
        return "BAD", ["key(s) REMOVED: %s" % ", ".join(sorted(removed))]
    if added != {"followup_kind"}:
        unexpected = added - {"followup_kind"}
        if unexpected:
            return "BAD", ["unexpected key(s) added: %s" % ", ".join(sorted(unexpected))]
        return "BAD", ["followup_kind was not added"]
    if ameta.get("followup_kind") != kind:
        return "BAD", ["followup_kind is %r, expected %r" % (ameta.get("followup_kind"), kind)]

    for key in sorted(set(bmeta) & set(ameta)):
        if key == "updated_at":
            continue
        if bmeta[key] == ameta[key]:
            continue
        if _norm_scalar(bmeta[key]) == _norm_scalar(ameta[key]):
            verdict = "OK_NORMALIZED"
            details.append("%s: %r -> %r (framework id canonicalisation)"
                           % (key, bmeta[key], ameta[key]))
            continue
        return "BAD", ["%s changed: %r -> %r" % (key, bmeta[key], ameta[key])]

    return verdict, details


def _cmd_delta(argv):
    before, after, kind = argv[0], argv[1], argv[2]
    with open(before, encoding="utf-8") as fh:
        btext = fh.read()
    with open(after, encoding="utf-8") as fh:
        atext = fh.read()
    verdict, details = delta_report(btext, atext, kind)
    sys.stdout.write(verdict + "\n")
    for d in details:
        sys.stdout.write("  %s\n" % d)
    return 0 if verdict != "BAD" else 1


def main(argv):
    if argv and argv[0] == "--delta":
        return _cmd_delta(argv[1:])
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        sys.stderr.write("usage: followup_backfill_classify.py <task-file>...\n")
        return 2

    for path in sorted(paths):
        res = classify_path(path)
        if res is None:
            sys.stdout.write("-\tNO_FRONTMATTER\t-\t-\t%s\n" % path)
            continue
        tid = task_id_from_path(path)
        if tid is None:
            # A task file whose name carries no numeric id. These exist in real
            # corpora (see t1338 / t1364) and one of them is a genuine
            # upstream-defect follow-up. `aitask_update.sh --batch` cannot
            # target it, so it can never be written -- but dropping the row
            # silently is the exact defect t1338 records against the work
            # report. Surface it as residue WITH A REASON instead.
            sys.stdout.write("-\tUNPARSEABLE_ID\t-\t-\t%s\n" % path)
            continue
        if res["conflict"]:
            rule = "CONFLICT:" + "+".join(res["conflict"])
            kind = "-"
        elif res["already"]:
            rule = "ALREADY"
            kind = res["already"]
        else:
            rule = res["rule"] or "-"
            kind = res["kind"] or "-"
        sys.stdout.write(
            "%s\t%s\t%s\t%s\t%s\n"
            % (tid, rule, kind, "origin" if res["has_origin"] else "-", path)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
