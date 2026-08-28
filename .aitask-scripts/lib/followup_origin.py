#!/usr/bin/env python3
"""Resolve a follow-up task's ORIGIN from its existing metadata (t1569_2).

Pure resolver. Deliberately side effect free: no writes, no git, no subprocess
-- the same contract `lib/followup_backfill_classify.py` states, so the rules
can be unit-tested without touching a task file.

Origin is a separate concern from *classification*. `followup_kind` already
settles "is this a follow-up, and of what category"; this module answers "which
task caused it", and deliberately never reads `followup_kind` to do so.

Four rules are load-bearing and each is a silent-wrong-answer bug if dropped:

1. **`anchor` is never an exact origin.** It is a topic-group key that by
   contract "always points at the root and never chains" -- `--followup-of` at
   creation merely *derives* it. Reporting it as `exact` would claim direct
   causation the data does not support.

2. **A malformed entry disqualifies `exact`; it is not merely reported.** If a
   `verifies:` list holding one good and one unparseable id still returned
   `exact` over the valid subset, a consumer would compute a verdict from a
   silently incomplete origin surface and could call it CLEAR. This is the
   framework's established rule for `aitask_verification_stale.sh`: "UNKNOWN
   drives the verdict, not advisory -- a path that cannot be checked means the
   check covers *less* scope than it claims, so FRESH would be a false
   all-clear." The malformed tokens stay fully recoverable through
   `resolve_detailed()`, so degradation loses no information; what is withheld
   is only the strongest quality claim.

3. **Ids must be canonicalised, and the seam already exists.** Over the live
   corpus `anchor` is *always* a Python `int`, while `verifies` entries appear
   as `'t1018_1'`, `int`, and bare `'1018_1'` -- `task_yaml`'s normalisation
   covers neither field (it prefixes only a `^\\d+_\\d+$` *string* and preserves
   int type, and `verifies` is not in its normalise list at all). Uncanonicalised,
   every anchor and most `verifies` entries miss a bare-string-keyed map. Reuse
   `dep_resolution.canonical_dep_id` rather than writing a second canonicaliser.

4. **Parse with `task_yaml.parse_frontmatter`**, not `stats_data`'s same-named
   function (`stats_data.py:394`) -- they live side by side and are not
   interchangeable. Note its real signature: it takes raw file *text* and
   returns a `(metadata, body, key_order)` 3-tuple, or `None`.
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dep_resolution import canonical_dep_id  # noqa: E402
from task_yaml import parse_frontmatter  # noqa: E402

#: The closed quality vocabulary. A malformed relation degrades within these
#: three values rather than adding a fourth -- the downstream protocol already
#: treats `topic` and `unknown` as degraded, so no new verdict is needed.
EXACT = "exact"
TOPIC = "topic"
UNKNOWN = "unknown"

#: Field 4 of the CLI record is the only one carrying raw user text, so it is
#: the only escaping hazard. `%` MUST be encoded first -- that ordering is what
#: makes the encoding injective.
_ENCODE = (("%", "%25"), ("\t", "%09"), ("\n", "%0A"), ("\r", "%0D"), (",", "%2C"))


def encode_residue(token):
    """Make one raw token safe for a tab-separated, comma-joined field."""
    out = str(token)
    for raw, escaped in _ENCODE:
        out = out.replace(raw, escaped)
    return out


def decode_residue(token):
    """Inverse of `encode_residue`. `%` is decoded LAST, mirroring the encode."""
    out = str(token)
    for raw, escaped in reversed(_ENCODE):
        out = out.replace(escaped, raw)
    return out


def _as_list(value):
    """A scalar or list field -> a list. `None` / absent -> []."""
    if value is None or value == "":
        return []
    return list(value) if isinstance(value, (list, tuple)) else [value]


def _partition(raw_values):
    """Split raw id tokens into (canonical valid ids, raw invalid tokens)."""
    valid, residue = [], []
    for item in raw_values:
        canonical = canonical_dep_id(item)
        if canonical is None:
            residue.append(item)
        elif canonical not in valid:
            valid.append(canonical)
    return valid, residue


def resolve_detailed(metadata):
    """Full result: ``{"origins", "quality", "residue", "degraded_origins"}``.

    - `origins` — the ids actually claimed at `quality`.
    - `residue` — every raw token that did not canonicalise.
    - `degraded_origins` — ids that DID canonicalise but are deliberately not
      claimed, because a malformed sibling made the relation incomplete.

    The third field is what makes the degradation lossless. Withholding the
    strongest quality claim is the point (see Rule 2); silently discarding the
    ids that parsed is not, and a diagnostic caller needs both halves to explain
    *why* a task degraded and *what* it would otherwise have pointed at.
    """
    metadata = metadata or {}

    verifies_valid, verifies_residue = _partition(_as_list(metadata.get("verifies")))
    anchor_valid, anchor_residue = _partition(_as_list(metadata.get("anchor")))

    # Rule 2: any unparseable `verifies:` entry disqualifies `exact` -- the
    # surface it describes is short by an unknown amount, so it is not evidence
    # of a direct origin. Fall through to `anchor`.
    if verifies_valid and not verifies_residue:
        return {
            "origins": verifies_valid,
            "quality": EXACT,
            "residue": [],
            "degraded_origins": [],
        }

    residue = list(verifies_residue)
    # Parsed, but not claimed: kept so the drop is inspectable rather than silent.
    degraded = list(verifies_valid)

    if anchor_valid and not anchor_residue:
        # Rule 1: a topic ROOT, never an exact origin.
        return {
            "origins": anchor_valid,
            "quality": TOPIC,
            "residue": residue,
            "degraded_origins": degraded,
        }

    residue.extend(anchor_residue)
    degraded.extend(anchor_valid)
    return {
        "origins": [],
        "quality": UNKNOWN,
        "residue": residue,
        "degraded_origins": degraded,
    }


def resolve(metadata):
    """``(origins, quality)`` -- the published two-tuple contract.

    Deliberately NOT widened to carry residue: the consumer this feeds was
    designed around a two-value result. Residue is available from
    `resolve_detailed()` and from the CLI's fourth field.
    """
    result = resolve_detailed(metadata)
    return result["origins"], result["quality"]


def resolve_path(path):
    """Read one task file and resolve it. `None` when it has no frontmatter."""
    with open(path, "r", encoding="utf-8") as handle:
        parsed = parse_frontmatter(handle.read())
    if parsed is None:
        return None
    # parse_frontmatter returns (metadata, body, original_key_order).
    return resolve_detailed(parsed[0])


_ID_FROM_PATH_RE = re.compile(r"^t(\d+(?:_\d+)?)_")


def task_id_from_path(path):
    """`aitasks/t16/t16_2_x.md` -> `16_2`. `None` when the name carries no id."""
    match = _ID_FROM_PATH_RE.match(os.path.basename(path))
    return match.group(1) if match else None


# --- CLI -------------------------------------------------------------------
#
# Five tab-separated fields, `path` last, mirroring
# `followup_backfill_classify.py`'s protocol positionally so a shell consumer's
# parser is unchanged:
#
#     <task_id>\t<quality>\t<origins csv>\t<residue csv>\t<path>
#
# A sixth field would break that contract; residue therefore rides in field 4,
# percent-encoded (see `encode_residue`).


def _row(task_id, quality, origins, residue, path):
    return "%s\t%s\t%s\t%s\t%s\n" % (
        task_id or "-",
        quality,
        ",".join(origins) if origins else "-",
        ",".join(encode_residue(r) for r in residue) if residue else "-",
        path,
    )


def main(argv):
    paths = [a for a in argv if not a.startswith("--")]
    if not paths:
        sys.stderr.write("usage: followup_origin.py <task-file>...\n")
        return 2

    for path in sorted(paths):
        try:
            result = resolve_path(path)
        except OSError as exc:
            sys.stderr.write("cannot read %s: %s\n" % (path, exc))
            return 2
        if result is None:
            sys.stdout.write(_row("-", "NO_FRONTMATTER", [], [], path))
            continue
        task_id = task_id_from_path(path)
        if task_id is None:
            # A task file whose name carries no numeric id. These exist in real
            # corpora; dropping the row silently is the defect the reference
            # module records against, so surface it WITH a reason instead.
            sys.stdout.write(_row("-", "UNPARSEABLE_ID", [], [], path))
            continue
        sys.stdout.write(
            _row(task_id, result["quality"], result["origins"], result["residue"], path)
        )
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
