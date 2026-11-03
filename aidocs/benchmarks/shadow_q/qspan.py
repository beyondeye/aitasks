"""Locate and substitute the shadow skill's ``>q`` bullet (t2179_1).

The bullet is the unit every variant replaces. It starts at the one line that
begins with ``- `>q``` and runs up to (not including) the next line that opens
another top-level item: a ``- `` bullet at column 0, a ``**`` paragraph lead or
a ``#`` heading. Blank lines inside the span are kept; trailing blank lines are
not part of it, so a substitution leaves the separator before the next item
untouched.

Stdlib only. Shared by ``freeze.py``, ``harness.py`` and the tests.
"""
from __future__ import annotations

import difflib

BULLET_PREFIX = "- `>q`"


class SpanError(ValueError):
    """The ``>q`` bullet is missing, duplicated, or a substitution leaked."""


def _is_item_start(line: str) -> bool:
    return line.startswith("- ") or line.startswith("**") or line.startswith("#")


def find_q_span(text: str) -> tuple[int, int]:
    """Return ``(start, end)`` 0-based line indices of the ``>q`` bullet.

    ``end`` is exclusive. Raises :class:`SpanError` unless the bullet occurs
    exactly once.
    """
    lines = text.split("\n")
    starts = [i for i, ln in enumerate(lines) if ln.startswith(BULLET_PREFIX)]
    if len(starts) != 1:
        raise SpanError(f">q bullet must occur exactly once, found {len(starts)}")
    start = starts[0]
    end = start + 1
    while end < len(lines) and not _is_item_start(lines[end]):
        end += 1
    while end - 1 > start and lines[end - 1].strip() == "":
        end -= 1
    return start, end


def extract_q_bullet(text: str) -> str:
    start, end = find_q_span(text)
    return "\n".join(text.split("\n")[start:end])


def substitute_q_bullet(text: str, replacement: str) -> str:
    """Replace the ``>q`` bullet with ``replacement`` and prove nothing else moved.

    The replacement must itself be a single ``>q`` bullet. The diff between the
    original and the result must touch only lines inside the original span.
    """
    if extract_q_bullet(replacement + "\n") != replacement.rstrip("\n"):
        raise SpanError("replacement is not exactly one >q bullet")
    start, end = find_q_span(text)
    lines = text.split("\n")
    new_lines = lines[:start] + replacement.rstrip("\n").split("\n") + lines[end:]
    result = "\n".join(new_lines)
    assert_only_span_changed(text, result)
    return result


def assert_only_span_changed(original: str, result: str) -> None:
    """Every differing line of ``original`` lies inside its ``>q`` span."""
    start, end = find_q_span(original)
    find_q_span(result)  # the result must still carry exactly one bullet
    a = original.split("\n")
    b = result.split("\n")
    matcher = difflib.SequenceMatcher(a=a, b=b, autojunk=False)
    for tag, i1, i2, _j1, _j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag == "insert":
            # A pure insertion before original line i1 (i1 == i2).
            if not (start <= i1 <= end):
                raise SpanError(f"insertion outside the >q span at line {i1 + 1}")
            continue
        if i1 < start or i2 > end:
            raise SpanError(
                f"change outside the >q span: lines {i1 + 1}-{i2} (span {start + 1}-{end})"
            )
