"""Single source of truth for auto-spawned follow-up kinds (t1468_1).

`followup_kind:` is an orthogonal scalar frontmatter field marking a task as an
auto-spawned follow-up rather than genuine new work. It is deliberately NOT an
`issue_type` value: `issue_type` is a behavioural dispatch key, and an upstream
defect genuinely *is* a bug that deserves the bug workflow.

All call sites that validate, enumerate, or render follow-up kinds must import
from this module. The shell bridge (``followup_kinds_sh.sh``) shells out here at
runtime so shell consumers stay in sync automatically — there is no second copy
of the vocabulary to drift.

One value per creation seam in the framework. Users must NOT extend this set:
unlike `labels.txt` / `task_types.txt` these are framework-semantic, which is
why the vocabulary lives here in `lib/` rather than in `aitasks/metadata/`.

Presentation columns (glyph, colour) are consumed by the board (t1468_3).
Colour is assigned in **families** — colour signals the severity class so
follow-ups read as a group down a column, while the glyph distinguishes which
kind. Glyphs are single-cell geometric characters (East-Asian-Width *Ambiguous*,
width 1 outside CJK locales), the same class as the house precedent
``TRAIL_CLASSIFICATION_GLYPHS`` in ``board/aitask_board.py``.
"""
from __future__ import annotations

import sys

# kind -> (glyph, colour, label). Declaration order is the canonical order.
FOLLOWUP_KINDS: "dict[str, tuple[str, str, str]]" = {
    "manual_verification":  ("◇", "cyan",         "manual verification"),
    "risk_mitigation":      ("▲", "yellow",       "risk mitigation"),
    "upstream_defect":      ("▼", "red",          "upstream defect"),
    "verification_failure": ("✗", "red",          "verification failure"),
    "carry_over":           ("↻", "cyan",         "carry-over"),
    "qa_test_gap":          ("◐", "magenta",      "QA test gap"),
    "review_finding":       ("◈", "magenta",      "review finding"),
    "docs_gap":             ("▤", "bright_black", "docs gap"),
}

VALID_FOLLOWUP_KINDS: frozenset = frozenset(FOLLOWUP_KINDS)

#: Fallback glyph for an unknown/malformed value. Mirrors `_trail_badge_text`'s
#: `·` fallback: a hand-edited bad value must render, never crash.
UNKNOWN_GLYPH: str = "·"


def validate_followup_kind(val: str) -> bool:
    return val in VALID_FOLLOWUP_KINDS


def normalize_followup_kind(raw) -> str:
    """Canonicalise for *comparison only* — never for storage.

    An absent key, an explicit ``None``, a non-string (a hand-edited list) and
    an empty string all read as *not a follow-up*, so that a side which deleted
    the key and a side which never had it compare equal.

    A real value is returned **verbatim, not stripped**: the value is an
    identity key, and silently trimming it would make ``"carry_over "`` compare
    equal to ``"carry_over"`` and discard a genuine edit. Validation rejects a
    bad value at the write seams; this only decides equality.
    """
    if isinstance(raw, str):
        return raw if raw.strip() else ""
    return ""


def followup_kinds_pipe() -> str:
    """Sorted pipe-separated alternation for shell regex consumers."""
    return "|".join(sorted(VALID_FOLLOWUP_KINDS))


def glyph_for(kind) -> str:
    """Single-cell glyph, with a safe fallback for an unknown value."""
    entry = FOLLOWUP_KINDS.get(normalize_followup_kind(kind))
    return entry[0] if entry else UNKNOWN_GLYPH


def colour_for(kind):
    """Colour name for the kind, or ``None`` when it is unknown/absent."""
    entry = FOLLOWUP_KINDS.get(normalize_followup_kind(kind))
    return entry[1] if entry else None


def label_for(kind) -> str:
    """Human-readable label, or ``""`` when the kind is unknown/absent."""
    entry = FOLLOWUP_KINDS.get(normalize_followup_kind(kind))
    return entry[2] if entry else ""


def main(argv) -> int:
    if len(argv) == 2 and argv[1] == "--pipe":
        sys.stdout.write(followup_kinds_pipe())
        return 0
    if len(argv) == 2 and argv[1] == "--list":
        sys.stdout.write("\n".join(FOLLOWUP_KINDS))
        return 0
    sys.stderr.write("usage: followup_kinds.py --pipe | --list\n")
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv))
