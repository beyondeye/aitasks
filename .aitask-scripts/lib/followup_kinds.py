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

# `record_protocol` is a pure, import-free policy module, so this stays cheap
# for the TUI call sites (the board imports this module on the PyPy fast path).
from record_protocol import INVALID_ENUM, UNKNOWN_ENUM, enum_field

# kind -> (glyph, colour, label). Declaration order is the canonical order.
FOLLOWUP_KINDS: "dict[str, tuple[str, str, str]]" = {
    "manual_verification":  ("◇", "cyan",         "manual verification"),
    "risk_mitigation":      ("▲", "yellow",       "risk mitigation"),
    "upstream_defect":      ("▼", "red",          "upstream defect"),
    "verification_failure": ("✗", "red",          "verification failure"),
    "carry_over":           ("↻", "cyan",         "carry-over"),
    "qa_test_gap":          ("◐", "magenta",      "QA test gap"),
    "review_finding":       ("◈", "magenta",      "review finding"),
    # `#808080`, not `bright_black` (t1468_3). Rich resolves `bright_black` to
    # exactly this grey, but Textual CANNOT parse the name — `Color.parse` there
    # raises "did you mean 'ansi_bright_black'?" — and a style it fails to parse
    # silently falls back to the default FOREGROUND. The glyph therefore reached
    # the board's compositor as truecolor `#e0e0e0`, pixel-identical to ordinary
    # card text, so `docs_gap` had no colour signal at all. A hex is the only
    # spelling of this grey that both libraries accept.
    "docs_gap":             ("▤", "#808080",      "docs gap"),
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


def followup_kind_field(value) -> str:
    """The line-protocol field for a task's ``followup_kind`` (t1468_5).

    Wraps ``record_protocol.enum_field`` and additionally **clamps to the
    vocabulary**: anything that is neither absent nor a real kind becomes
    ``invalid``. So the emitted value is always one of the eight kinds,
    ``unknown`` (the task had no ``followup_kind`` at all — the common case,
    since most tasks are genuine new work) or ``invalid``.

    Clamping is what lets every consumer treat "neither sentinel" as
    "recognised" **by construction**, without carrying its own copy of the
    vocabulary. Both consumers need that guarantee for different reasons, and
    neither can get it from ``enum_field`` alone, which preserves any
    transport-safe string:

    - the trail writer stores the value into a schema ``enum``, where an
      out-of-vocabulary value fails the WHOLE document as
      ``ERROR:invalid_trail``;
    - the work report renders it as manager-facing prose, where a typo or a
      kind from a newer framework version would otherwise be announced as a
      real provenance category ("follow-up: typo kind").

    This is the last point at which "not a kind" is still knowable, so the
    clamp belongs here rather than in each consumer.

    **Absence is decided from the RAW input, never from the encoded result.**
    ``unknown`` is a *sentinel*, not a reserved word, so a task can literally
    carry ``followup_kind: unknown`` in its frontmatter — that value is
    PRESENT and is not a kind, so it must classify as ``invalid``. Reading
    absence off ``enum_field``'s output instead would let it impersonate the
    absent sentinel: the work report would hide a malformed value as genuine
    new work while :func:`marker_for` still painted the same string as an
    unrecognised follow-up on the board. The two surfaces disagreeing about
    one frontmatter value is exactly what this module exists to prevent.

    One difference from :func:`normalize_followup_kind` is deliberate: a
    non-string (a hand-edited list, an int) classifies as ``invalid`` here —
    it *is* present — where the normalizer coerces it to "not a follow-up"
    because it exists to decide *equality* for merges, not presence. Both
    still agree on the outcome that matters: no consumer reports such a task
    as carrying a kind.
    """
    if value is None or value == "":
        return UNKNOWN_ENUM
    field = enum_field(value)
    return field if field in VALID_FOLLOWUP_KINDS else INVALID_ENUM


def marker_for(kind):
    """``(glyph, colour)`` for a follow-up kind, or ``None`` when it is absent.

    The framework's render boundary over ``followup_kind`` — shared by the board
    card (t1468_3) and the monitor/minimonitor sibling picker (t1468_5) so the
    same value never grows a second, subtly different totality rule.

    Deliberately NOT :func:`glyph_for` / :func:`colour_for`: those were written
    for validation and answer ``("·", None)`` for an **absent** kind exactly as
    they do for an unknown one, which on any task list would paint a marker on
    every ordinary task. The three cases must stay distinct:

    - absent / empty / junk (``None``, a list, an int, a hand-edited dict —
      ``normalize_followup_kind`` coerces all of them) -> ``None``, so the
      caller yields no marker at all;
    - a recognised kind -> its own glyph and severity-family colour;
    - present but unrecognised (a typo, or a kind from a newer framework
      version) -> the :data:`UNKNOWN_GLYPH` fallback with **no** colour. It
      still renders, because a bad value that silently vanishes is
      indistinguishable from a task that was never a follow-up.

    Returning a tuple-or-``None`` rather than a bare glyph string is what keeps
    "no marker" structurally distinct from "a marker that happens to be ``·``",
    so every call site is a single ``if marker:``.
    """
    normalized = normalize_followup_kind(kind)
    if not normalized:
        return None
    entry = FOLLOWUP_KINDS.get(normalized)
    return (entry[0], entry[1]) if entry else (UNKNOWN_GLYPH, None)


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
