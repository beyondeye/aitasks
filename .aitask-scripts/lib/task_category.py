"""Base-layer module: the unified **category axis** for ait stats.

One dimension over two vocabularies -- auto-spawned follow-up *kinds*
(`risk_mitigation`, `manual_verification`, `upstream_defect`, ...) and ordinary
*issue types* (`bug`, `feature`, ...) -- so a backlog table can show them as a
single readable axis. Pure: no rendering, no I/O, no writes.

Keys are **namespaced**: ``kind:<k>`` or ``type:<t>``. That is load-bearing and
must not be "simplified" to a flat string. ``manual_verification`` is a member
of *both* vocabularies, and a flat axis would depend on the argument that
`classify()`'s manual_verification rule fires on
``issue_type == 'manual_verification'``, so an MV task never reaches the
issue-type fallback. That is true today, but ``aitasks/metadata/task_types.txt``
is user-extensible: a user adding `docs_gap` or `review_finding` as an issue
type would silently merge two categories. The namespace removes the whole class
of ambiguity and turns display dispatch into a prefix check rather than a
precedence rule.

Consumed by the stats collection layer, the CLI text/CSV report, and the stats
TUI panes. Its **display half** (`type_display_name`, `category_display_name`,
`is_followup_category`) is deliberately dependency-free -- see
:func:`resolve_category` for why the classifier is imported lazily.
"""

from __future__ import annotations

import os
import sys
from typing import Dict, Optional

# Sibling lib/ modules; `lib/` is already sys.path[0] when run as a script, and
# a test that imports this module puts lib/ on sys.path itself.
_LIB_DIR = os.path.dirname(os.path.abspath(__file__))
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)
from followup_kinds import followup_kind_field, label_for  # noqa: E402
from record_protocol import INVALID_ENUM, UNKNOWN_ENUM  # noqa: E402

KIND_PREFIX = "kind:"
TYPE_PREFIX = "type:"

#: Issue-type display names. Moved here verbatim from
#: ``aitask_stats.py::get_type_display_name`` (which now delegates). The map is
#: deliberately incomplete: `manual_verification` and `enhancement` have no
#: entry and render through the ``raw.capitalize()`` fallback as
#: ``Manual_verification`` / ``Enhancement``. That is what ``ait stats`` prints
#: today, so adding entries for them would change existing output.
TYPE_DISPLAY_NAMES: Dict[str, str] = {
    "feature": "Features",
    "bug": "Bug Fixes",
    "refactor": "Refactors",
    "documentation": "Documentation",
    "performance": "Performance",
    "style": "Style Changes",
    "test": "Tests",
    "chore": "Chores",
    "parent": "Parent Tasks",
    "child": "Child Tasks",
}


def _unquote(value) -> str:
    """Strip surrounding quotes and whitespace from a flat-parser value.

    Exists **only** to compensate for ``stats_data.parse_frontmatter``, the flat
    string scanner, which keeps values verbatim -- so ``followup_kind:
    "carry_over"`` arrives with its quotes and would otherwise clamp to
    ``invalid``. Delete it when t1304 (consolidate the two ``lib/``
    ``parse_frontmatter`` functions) lands and this path gets typed values.

    Measured: **zero** quoted values exist in the corpus today (442 live + 1844
    archived tasks), so this is purely defensive.

    Deliberately NOT reusing ``followup_backfill_classify._norm_scalar``, which
    does the same strip and then removes a leading ``t`` from id-shaped strings.
    That one is an identity-key canonicalizer for task ids; borrowing it for a
    vocabulary key would silently mangle any future kind that looked id-ish.
    """
    if value is None:
        return ""
    return str(value).strip().strip("'\"").strip()


def type_display_name(raw: str) -> str:
    """Display name for an issue type. The canonical site for this mapping."""
    return TYPE_DISPLAY_NAMES.get(raw, raw.capitalize())


def category_display_name(cat: str) -> str:
    """Display name for a namespaced category key -- dispatch on the prefix.

    ``kind:`` goes to the follow-up vocabulary's own labels, ``type:`` to the
    issue-type map. Neither side is re-cased here: ``label_for`` is the single
    source of truth for those strings and they are *not* uniformly lowercase
    (``QA test gap`` is capitalised, ``carry-over`` is hyphenated). The
    **namespace prefix**, not the casing, is what separates the two halves of
    the axis -- so do not write a caller or test that assumes a case convention.
    """
    if cat.startswith(KIND_PREFIX):
        kind = cat[len(KIND_PREFIX):]
        # label_for returns "" for an unrecognised kind. resolve_category only
        # emits kinds that passed the vocabulary clamp or came from RULE_ORDER,
        # so this should be unreachable -- fall back to the bare key rather
        # than render an empty cell if it ever is not.
        return label_for(kind) or kind
    if cat.startswith(TYPE_PREFIX):
        return type_display_name(cat[len(TYPE_PREFIX):])
    return cat


def is_followup_category(cat: str) -> bool:
    """True for an auto-spawned follow-up, False for genuine new work."""
    return cat.startswith(KIND_PREFIX)


def resolve_category(
    metadata,
    body: str,
    filename: str,
    tally: Optional[dict] = None,
) -> str:
    """Resolve one task to a namespaced category key.

    Precedence:

    1. ``followup_kind`` from frontmatter, clamped through
       :func:`followup_kinds.followup_kind_field` -> ``kind:<k>``;
    2. otherwise the kind retro-derived by
       ``followup_backfill_classify.classify()`` -> ``kind:<k>``;
    3. otherwise ``type:<issue_type>`` -- the task is genuine new work.
       ``type:unknown`` when ``issue_type`` is missing.

    ``tally`` is an optional :class:`collections.Counter` (anything supporting
    ``+= 1`` on a missing key). When a ``followup_kind`` is *present but
    unrecognised*, the clamp yields ``invalid`` and this falls through to
    `classify()` -- but the fall-through is **counted** as
    ``invalid_followup_kind`` rather than silently absorbed, because a bad value
    that vanishes is indistinguishable from a task that was never a follow-up
    (see ``followup_kinds.marker_for``). Passing a counter keeps this module
    stateless: the caller folds the count into its own excluded-task reporting.

    Zero invalid values exist in the corpus today, so the tally is a free
    tripwire rather than an active counter.
    """
    # Imported lazily, not at module scope, so the display half of this module
    # stays dependency-free: aitask_stats.get_type_display_name and the stats
    # TUI panes need only type_display_name / category_display_name and should
    # not transitively load the classifier to render a string map.
    from followup_backfill_classify import classify

    # _unquote runs BEFORE the clamp on purpose: '"carry_over"' must resolve to
    # carry_over, not invalid, so the tally counts genuinely bogus values rather
    # than quoting artefacts.
    declared = followup_kind_field(_unquote(metadata.get("followup_kind")))
    if declared not in (UNKNOWN_ENUM, INVALID_ENUM):
        return KIND_PREFIX + declared
    if declared == INVALID_ENUM and tally is not None:
        tally["invalid_followup_kind"] += 1

    # classify() returns kind=None for residue (no rule fired); when truthy it
    # is always a member of RULE_ORDER, so the key is namespace-safe.
    derived = classify(metadata, body, filename).get("kind")
    if derived:
        return KIND_PREFIX + derived

    return TYPE_PREFIX + (_unquote(metadata.get("issue_type")) or "unknown")
