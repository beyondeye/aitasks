"""General-purpose fuzzy subsequence matching for TUI filter boxes (t958).

A query matches a candidate when the query's characters appear *in order*
inside the candidate (a subsequence). :func:`match` returns a score so callers
can rank results — higher is better — together with the matched character
positions. :func:`rank` is the convenience wrapper the filter boxes use:
filter a list of items to those that match, best first.

Adapted from the alignment/scoring algorithm in
``codebrowser/file_search.py`` (``PathFuzzySearch``, itself adapted from toad),
with the path-specific heuristics removed: word boundaries are spaces rather
than ``/`` and there is no filename boost. This scorer is for plain-text rows
(shortcut listings, list items), not file paths — the codebrowser matcher
stays path-specialised and is intentionally not shared with this one.
"""

from __future__ import annotations

import re
from functools import lru_cache
from operator import itemgetter
from typing import Callable, Iterable, Sequence, TypeVar

T = TypeVar("T")

_EMPTY: tuple[float, Sequence[int]] = (0.0, ())


@lru_cache(maxsize=1024)
def _word_starts(candidate: str) -> frozenset[int]:
    """Indexes that begin a word: position 0 and every index after a space."""
    return frozenset({0, *(m.start() + 1 for m in re.finditer(r" ", candidate))})


def _score(candidate: str, positions: Sequence[int]) -> float:
    """Score one alignment: more matched chars, more word-start hits, and
    fewer gaps (longer consecutive runs) all raise the score."""
    word_starts = _word_starts(candidate)
    offset_count = len(positions)
    score = float(offset_count + len(word_starts.intersection(positions)))

    groups = 1
    last_offset, *rest = positions
    for offset in rest:
        if offset != last_offset + 1:
            groups += 1
        last_offset = offset

    normalized_groups = (offset_count - (groups - 1)) / offset_count
    score *= 1 + (normalized_groups * normalized_groups)
    return score


def _alignments(
    query: str, candidate: str
) -> Iterable[tuple[float, Sequence[int]]]:
    """Yield ``(score, positions)`` for every in-order alignment of ``query``
    inside ``candidate``. Yields a single ``_EMPTY`` and stops as soon as a
    query letter has no remaining position (not a subsequence)."""
    letter_positions: list[list[int]] = []
    position = 0
    for offset, letter in enumerate(query):
        last_index = len(candidate) - offset
        positions: list[int] = []
        letter_positions.append(positions)
        index = position
        while (location := candidate.find(letter, index)) != -1:
            positions.append(location)
            index = location + 1
            if index >= last_index:
                break
        if not positions:
            yield _EMPTY
            return
        position = positions[0] + 1

    possible: list[list[int]] = []
    qlen = len(query)

    def _collect(offsets: list[int], pi: int) -> None:
        for off in letter_positions[pi]:
            if not offsets or off > offsets[-1]:
                new = [*offsets, off]
                if len(new) == qlen:
                    possible.append(new)
                else:
                    _collect(new, pi + 1)

    _collect([], 0)
    for offsets in possible:
        yield _score(candidate, offsets), offsets


def match(
    query: str, candidate: str, *, case_sensitive: bool = False
) -> tuple[float, Sequence[int]]:
    """Best-alignment score of ``query`` inside ``candidate``.

    Returns ``(score, matched_positions)`` for the highest-scoring alignment,
    or ``(0.0, ())`` when ``query`` is not a subsequence of ``candidate`` (or
    is empty). Case-insensitive by default.
    """
    if not query:
        return _EMPTY
    if not case_sensitive:
        query = query.casefold()
        candidate = candidate.casefold()
    return max(_alignments(query, candidate), key=itemgetter(0), default=_EMPTY)


def rank(query: str, items: Iterable[T], *, key: Callable[[T], str]) -> list[T]:
    """Filter ``items`` to those whose ``key(item)`` fuzzily matches ``query``,
    best match first.

    A blank/whitespace-only ``query`` returns the items unchanged (original
    order, no filtering) — the "no filter active" case.
    """
    items = list(items)
    if not query or not query.strip():
        return items
    scored: list[tuple[float, T]] = []
    for item in items:
        score, _ = match(query, key(item))
        if score > 0:
            scored.append((score, item))
    # Negative-score key keeps Python's stable sort from reversing ties, so
    # equal-scoring items retain their original relative order.
    scored.sort(key=lambda pair: -pair[0])
    return [item for _, item in scored]
