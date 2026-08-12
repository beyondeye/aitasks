"""Parse the shadow agent's structured concern block from a captured pane.

The shadow agent (``aitask-shadow`` skill) emits a fenced, machine-parseable
block of plan concerns alongside its human-readable list. Minimonitor captures
the shadow pane and uses this module to extract those concerns for the
concern-picker modal (t1037).

This module is **pure**: no tmux, no Textual, no I/O. It operates only on the
already-cleaned capture text produced by ``aitask_shadow_capture.sh``.

The capture handed in **must be wrap-joined** (``tmux capture-pane -J`` or
equivalent): the parser space-joins continuation lines onto a concern body,
which is correct only for agent-emitted word-boundary breaks — raw soft-wrap
would split a long line mid-word. The capture path (minimonitor, t1037_4) owns
the join; see ``.claude/skills/aitask-shadow/concern-format.md``.

Format (single source of truth: ``.claude/skills/aitask-shadow/concern-format.md``)::

    ===AITASK-CONCERNS===
    Round: 2 @ 2026-08-11T14:03:27Z
    - [high | Step 7 ownership guard] The guard re-runs aitask_pick_own.sh which
      double-commits when the lock was already held.
    - [medium | parser module] Multi-block accumulation is undefined.
    ===END-CONCERNS===

- ASCII sentinel fences — survive tmux capture, do not collide with markdown
  code fences.
- One concern per ``- [priority | region] body`` marker. The leading ``- ``
  (dash + space) is **mandatory**: tmux soft-wrapping never prefixes a
  continuation line with it, so a wrapped body line — even one containing
  bracket- or ``key=value``-looking text — can never be misread as a new item.
- A marker whose ``[priority | region]`` bracket was split across rows by an
  agent TUI's own hard-wrap is rejoined, bounded to
  ``_MAX_MARKER_JOIN_ROWS`` following rows (t1167). Within that envelope
  ``priority`` and ``body`` are exact and ``region`` is best-effort; a wider
  split is still dropped. The producer-side short-region rule remains the
  primary defense — see ``concern-format.md``.
- ``priority`` is normalized case-insensitively to {high, medium, low}; an
  unknown value degrades to ``low`` (the item is never dropped).
- A region-less marker (``- [medium] body``) parses with an empty ``region``
  instead of being swallowed as a wrap continuation (t1274).
- ``disposition`` and ``verdict`` are **derived**, not marker fields: they are
  read from the terminal ``Disposition: … Verified: …`` run the implementation
  review appends to the body. ``body`` itself is left canonical so
  :func:`build_clipboard_payload` forwards the trailer intact; display surfaces
  call :meth:`Concern.display_body`.
- **Round header (t1159_1):** the first line inside the fences is
  ``Round: <N> @ <ISO-8601-UTC-seconds>Z``, read by :func:`parse_block_meta`.
  It sits in the one slot the item scanner already drops (a non-marker line
  before the first item), so every concern-yielding entry point is unaffected;
  it deliberately perturbs :func:`concern_block_signature`. A **metadata-only**
  block (fences + header, no items) records a clean round;
  :func:`has_concern_block` stays False for it and the strict
  :func:`is_metadata_only_block` certifies it (complete fence + exactly the
  header). Absent header = pre-t1159_1 block, byte-identical behavior
  everywhere.
- **Last block wins:** when several blocks are present, only the most recent
  one is parsed (a re-issued review supersedes an earlier one).

Three strictness tiers over two capture shapes. The concern-yielding entry
points share :func:`_last_block_region`, diverging on ``require_close``
(forgiving readers pass ``False``, the strict trigger ``True``); the signature
tier shares it too but consumes a *different capture shape* and never yields
concerns:

=============================== ============================== ==========================================
Entry point                     Input shape                    Purpose
=============================== ============================== ==========================================
:func:`parse_concerns`          wrap-joined, ANSI-free (``-J``) **forgiving** — the *explicit* user action
                                                               (picker hotkey): parses the newest block to
                                                               EOF even if its closing fence was truncated
                                                               from scrollback.
:func:`has_concern_block`       wrap-joined, ANSI-free (``-J``) **strict** trigger for the UI *auto-offer*:
                                                               the newest opening fence must have its own
                                                               closing fence after it and yield >=1 concern,
                                                               so the picker is never offered for an
                                                               incomplete, empty, or malformed block.
:func:`concern_block_signature` **raw tick capture**            **trigger only** — a reflow-stable equality
                                (``-p -e``, NOT wrap-joined,    token over data the refresh tick already
                                ANSI-bearing)                   holds, so N agents can be badged at zero
                                                               extra tmux traffic. Never parsed into
                                                               forwardable concerns.
:func:`unrecovered_markers`     wrap-joined, ANSI-free (``-J``) **report** — the marker-looking lines the
                                                               same (forgiving) region yielded no concern
                                                               for, so the picker can say how many items
                                                               were lost instead of degrading silently.
:func:`block_region`            wrap-joined, ANSI-free (``-J``) **display only** — the same (forgiving)
                                                               region's text, verbatim, so a human can read
                                                               what the parser could not use (t1293). Never
                                                               parsed into forwardable concerns.
:func:`parse_block_meta`        wrap-joined, ANSI-free (``-J``) **metadata** — the same (forgiving) region's
                                                               round header, as a :class:`BlockMeta`, or
                                                               ``None`` when absent (t1159_1). Never yields
                                                               concerns; fail-open on malformed headers.
=============================== ============================== ==========================================
"""
from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import NamedTuple

try:
    from .ansi_utils import strip_ansi
except ImportError:  # imported flat (tests put MONITOR_DIR on sys.path)
    from ansi_utils import strip_ansi  # noqa: E402

_OPEN = "===AITASK-CONCERNS==="
_CLOSE = "===END-CONCERNS==="

#: The one timestamp shape producers are told to emit, shell-sourced with
#: ``date -u +%Y-%m-%dT%H:%M:%SZ``. Used for BOTH parsing and the canonical
#: round-trip check in :func:`parse_reviewed_at_epoch`, so the strictness check
#: can never drift from the grammar it enforces (t1493).
_REVIEWED_AT_FMT = "%Y-%m-%dT%H:%M:%SZ"

# Narrowest pane width at which the sentinels are guaranteed not to soft-wrap.
# They are 21 (`_OPEN`) and 18 (`_CLOSE`) chars; below this a fence can be split
# across rows and `concern_block_signature` — which reads a NON-wrap-joined
# capture — stops seeing the block at all. Exported so the caller can fall back
# to an authoritative `-J` capture for such panes rather than read the `None` as
# "no concerns" (t1216_1; the same class of silent false negative as t1187).
_SENTINEL_SAFE_COLS = 24

# Leading "- " (dash + space) is MANDATORY — collision hardening: a wrapped
# continuation line never carries it, so it can never start a spurious concern.
_ITEM = re.compile(
    r"^\s*-\s+\[\s*(?P<priority>\w+)\s*\|\s*(?P<region>[^\]]*)\]\s*(?P<body>.*)$"
)

# A marker that omits the `| region` half entirely: `- [medium] body`. Tried only
# after `_ITEM` fails. Without this the row is neither an item nor (because it
# contains `]`) a split-marker candidate, so it falls through to continuation
# handling and is silently APPENDED to the previous concern's body — or dropped
# outright when it is the first item in the block (t1274).
#
# The priority alternation is deliberately the CLOSED vocabulary, not `\w+`.
# `_ITEM` can afford `\w+` because the `|` separator already makes the shape
# unmistakable; without that separator a permissive class would let an ordinary
# wrapped body line (`- [see below] …`) start a spurious concern, breaking the
# collision-hardening guarantee the whole format rests on.
_ITEM_NO_REGION = re.compile(
    r"^\s*-\s+\[\s*(?P<priority>high|medium|low)\s*\]\s*(?P<body>.+)$",
    re.IGNORECASE,
)

# A row that *starts* like an item marker. Used only to detect a marker whose
# bracket was split across rows by an agent TUI's own hard-wrap (t1167).
_MARKER_START = re.compile(r"^\s*-\s+\[")

# Max continuation rows joined to close a split bracket, so a marker spans at
# most _MAX_MARKER_JOIN_ROWS + 1 = 3 rows. At the ~55-column width where the
# failure was observed that covers ~165 chars of marker — a region of ~150
# chars, roughly 5x the producer's 30-char short-region rule and 3x the 53-char
# region that actually broke. Deliberately generous rather than tight: it exists
# only to absorb producer violations of that rule, while staying narrow enough
# that over-joining (the sole new risk) stays implausible. A wider split is
# still dropped — that is the accepted, documented limit, and the producer-side
# short-region rule remains the primary defense.
_MAX_MARKER_JOIN_ROWS = 2

_VALID = {"high", "medium", "low"}

#: Dispositions the shadow's implementation review assigns to a finding, in
#: partition order. Single source of the vocabulary on the consumer side; the
#: rubric that *defines* them lives in
#: ``.claude/skills/aitask-shadow/impl-review-angles.md``.
DISPOSITIONS = ("blocking", "follow-up", "informational")

_VERDICTS = ("CONFIRMED", "PLAUSIBLE", "REFUTED")

# The disposition / verdict trailer the implementation review appends to a
# concern body as prose (`… Disposition: informational. Verified: CONFIRMED.`).
#
# Anchored to the END of the body on purpose. These are metadata that TERMINATE
# the body, so only a terminal run counts: a body that quotes or discusses
# `Disposition: informational.` mid-prose must neither be classified by it nor
# have that prose stripped from the display (t1274). Sentence order within the
# run is free.
_TRAILER_SENTENCE = (
    r"(?:Disposition:\s*(?:blocking|follow[- ]?up|informational)"
    r"|Verified:\s*(?:CONFIRMED|PLAUSIBLE|REFUTED))\.?"
)
_TRAILER_SPAN = re.compile(rf"(?:\s*{_TRAILER_SENTENCE})+\s*$", re.IGNORECASE)
_DISPOSITION_IN_TRAILER = re.compile(
    r"Disposition:\s*(blocking|follow[- ]?up|informational)", re.IGNORECASE
)
_VERDICT_IN_TRAILER = re.compile(
    r"Verified:\s*(CONFIRMED|PLAUSIBLE|REFUTED)", re.IGNORECASE
)

DEFAULT_PREAMBLE = (
    "I have some concerns: please verify them and if valid "
    "please address in the plan"
)

# The round header a producer emits as the first line inside the fences:
# `Round: 2 @ 2026-08-11T14:03:27Z` (t1159_1). The timestamp part after `@`
# is captured verbatim and never validated — the producers shell-source it,
# but the parser stays fail-open on whatever actually arrived.
#
# The round is a POSITIVE integer of at most 9 digits IN THE GRAMMAR
# (1..999999999, documented in concern-format.md). Bounded because `int()` on
# an unbounded digit run raises past sys.get_int_max_str_digits() (4300 on
# 3.11+), which would violate the parser's never-raise contract on
# agent-emitted garbage; positive because rounds are 1-based — `Round: 0` (or
# a zero-padded round) is not a value a compliant producer can emit. Either
# violation simply fails the line match, so the header reads as malformed
# (meta = None) rather than crashing or certifying a bogus round.
_META_LINE = re.compile(
    r"^\s*Round:\s*(?P<round>[1-9]\d{0,8})\s*(?:@\s*(?P<at>.*?))?\s*$"
)


class BlockMeta(NamedTuple):
    """Round metadata parsed from a concern block's header line (t1159_1).

    **Consumer contract (t1448): the freshness key is the
    ``(round, reviewed_at)`` PAIR — never ``round`` alone.** A restarted shadow
    session starts counting at 1 again, so equal round numbers from different
    sessions are routine; the seconds-resolution timestamp is what
    disambiguates them.
    """

    round: int          # 1-based round the producer emitted
    reviewed_at: str    # verbatim text after '@' ("" when absent or empty)


class Concern(NamedTuple):
    priority: str        # one of {"high", "medium", "low"}
    region: str          # free-text plan-region / axis label
    body: str            # free-text concern body (wrap-joined) — see below
    disposition: str = ""  # one of DISPOSITIONS, or "" when unspecified
    verdict: str = ""      # one of _VERDICTS, or "" when absent

    # ``body`` is CANONICAL: exactly what the producer emitted, trailer included.
    # :func:`build_clipboard_payload` re-renders it verbatim, so stripping the
    # trailer here would delete the disposition from what gets forwarded to the
    # followed agent. Display surfaces call :meth:`display_body` instead; the
    # clipboard path must always use ``body``.

    def display_body(self) -> str:
        """``body`` minus its terminal ``Disposition:`` / ``Verified:`` run.

        Exactly the span :data:`_TRAILER_SPAN` matched is removed — never more —
        so prose that merely mentions a disposition survives intact. Returns
        ``body`` unchanged when there is no terminal trailer.
        """
        match = _TRAILER_SPAN.search(self.body)
        return self.body[: match.start()].rstrip() if match else self.body


def needs_addressing(concern: Concern) -> bool:
    """False only for an explicitly ``informational`` concern.

    The single home of the actionable/not rule, so display surfaces never
    re-derive it. An *unspecified* disposition (the three ``plan-*`` producers
    emit no trailer at all, and older blocks may predate it) counts as needing
    attention — the safe direction.
    """
    return concern.disposition != "informational"


def _norm_priority(raw: str) -> str:
    p = raw.strip().lower()
    return p if p in _VALID else "low"


def _parse_trailer(body: str) -> tuple[str, str]:
    """Return ``(disposition, verdict)`` read from ``body``'s terminal trailer.

    Both default to ``""`` — when there is no terminal trailer, or when the
    trailer carries only one of the two sentences.
    """
    match = _TRAILER_SPAN.search(body)
    if match is None:
        return "", ""
    trailer = match.group(0)
    disposition = ""
    verdict = ""
    if (d := _DISPOSITION_IN_TRAILER.search(trailer)) is not None:
        disposition = re.sub(r"\s+", "-", d.group(1).strip().lower())
        disposition = disposition.replace("followup", "follow-up")
    if (v := _VERDICT_IN_TRAILER.search(trailer)) is not None:
        verdict = v.group(1).upper()
    return disposition, verdict


def _last_block_region(text: str, *, require_close: bool) -> str | None:
    """Return the text between the LAST opening fence and its scope end.

    All fence detection is scoped to the *last* opening fence (``rfind``) so an
    older block's closing fence cannot satisfy the check while a newer block is
    still streaming. Returns ``None`` when no opening fence exists, or — when
    ``require_close`` is set — when the last opening fence has no closing fence
    after it.
    """
    open_idx = text.rfind(_OPEN)
    if open_idx == -1:
        return None
    body_start = open_idx + len(_OPEN)
    close_idx = text.find(_CLOSE, body_start)
    if close_idx == -1:
        # Newest block has no closing fence yet.
        return None if require_close else text[body_start:]
    return text[body_start:close_idx]


def _join_sep(joined: str) -> str:
    """Separator to use when rejoining a hard-wrapped marker fragment.

    The renderers observed in the wild break at word *and* intra-token
    boundaries: an intra-token break loses nothing, a word break consumes the
    space. A fragment ending in ``-`` or ``/`` is taken as an intra-token break
    (this reconstructs a wrapped path exactly); anything else is treated as a
    word break and gets its space back.

    This is a **heuristic**, and deliberately so: a capture cannot distinguish
    "the renderer consumed a space here" from "the token continues here". See
    :func:`_join_split_marker` for why an approximation is acceptable.
    """
    return "" if joined.endswith(("-", "/")) else " "


def _join_split_marker(lines: list[str], start: int):
    """Rejoin a marker bracket split across rows by an agent TUI's hard-wrap.

    Agent TUIs that render markdown themselves (observed: Codex CLI at ~55
    columns) hard-wrap long rows with **literal newlines** that ``tmux
    capture-pane -J`` cannot rejoin. A wrap landing inside ``[priority |
    region]`` leaves no row matching :data:`_ITEM`, and the whole item used to
    be silently dropped (t1167).

    Returns ``(match, rows_consumed)`` on success and ``(None, 1)`` otherwise.
    On failure **nothing is consumed**, so the rows fall through to the normal
    continuation handling and a failed join can never swallow a following item.

    ``priority`` and ``body`` are reconstructed exactly; ``region`` is
    **best-effort** (see :func:`_join_sep`) — it is a display label rendered in
    the picker, never a key, so the load-bearing guarantee here is only that the
    item is no longer dropped. The known imperfect case is a prose region
    containing a spaced slash broken right after the slash (``foo / bar`` ->
    ``foo /bar``): accepted, cosmetic, and pinned by a test.
    """
    joined = lines[start]
    for k in range(1, _MAX_MARKER_JOIN_ROWS + 1):
        nxt_idx = start + k
        if nxt_idx >= len(lines):
            break
        nxt = lines[nxt_idx]
        # A real continuation never carries "- [" — that is a new item, so stop
        # rather than swallow it (preserves the collision-hardening guarantee).
        if _MARKER_START.match(nxt):
            break
        joined += _join_sep(joined) + nxt.lstrip()
        if "]" in nxt:
            m = _ITEM.match(joined)
            if m:
                return m, k + 1
            break
    return None, 1


def _scan_items(region: str) -> tuple[list[Concern], list[str]]:
    """Extract concerns from a block region (the only home of the grammar).

    Returns ``(concerns, unrecovered)``. A line matching the item marker starts a
    new concern; any other non-blank line is a wrap continuation and is appended
    (space-joined) to the current concern's body. Blank lines are ignored.

    Three marker shapes are recognised, in order: the canonical
    ``- [priority | region] body`` (:data:`_ITEM`); a bracket the renderer
    hard-wrapped mid-marker, rejoined by :func:`_join_split_marker` within its
    bounded envelope; and the region-less ``- [priority] body``
    (:data:`_ITEM_NO_REGION`), which yields an empty region rather than being
    swallowed as a continuation.

    ``unrecovered`` collects every remaining line that *looks* like a marker
    (:data:`_MARKER_START`) but produced no concern — an over-bound split, a
    malformed bracket, an unclosed one. A genuine continuation line can never
    begin ``- [`` (that is the collision-hardening invariant the format rests
    on), so such a line is by definition a marker the parser could not recover.
    Those lines still fall through to continuation handling as before — nothing
    is lost — but the caller can now *report* them instead of degrading
    silently (t1274).
    """
    # Each entry: [priority, region, [body_parts]].
    items: list[list] = []
    unrecovered: list[str] = []
    lines = region.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _ITEM.match(line)
        consumed = 1
        if m is None and _MARKER_START.match(line) and "]" not in line:
            m, consumed = _join_split_marker(lines, i)
        region_label = m.group("region") if m else ""
        if m is None:
            m = _ITEM_NO_REGION.match(line)
        if m:
            items.append([m.group("priority"), region_label, [m.group("body")]])
        else:
            if _MARKER_START.match(line):
                unrecovered.append(line.strip())
            if line.strip() and items:
                items[-1][2].append(line)
        i += consumed
    out: list[Concern] = []
    for priority, region_label, parts in items:
        body = " ".join(p.strip() for p in parts if p.strip()).strip()
        disposition, verdict = _parse_trailer(body)
        out.append(
            Concern(
                _norm_priority(priority),
                region_label.strip(),
                body,
                disposition,
                verdict,
            )
        )
    return out, unrecovered


def _parse_items(region: str) -> list[Concern]:
    """Concerns only — see :func:`_scan_items` for the grammar."""
    return _scan_items(region)[0]


def _iter_block_regions(text: str):
    """Yield the region after EACH opening fence up to its next close (or EOF).

    Unlike :func:`_last_block_region`, which scopes to the *last* opening fence
    (the runtime "last block wins" semantics), this walks **every** block in
    order — so an embedded example block that is not the newest one is still
    visible. Used only by the authoring-safety check :func:`contains_any_concern_block`.
    """
    idx = 0
    while True:
        open_idx = text.find(_OPEN, idx)
        if open_idx == -1:
            return
        body_start = open_idx + len(_OPEN)
        close_idx = text.find(_CLOSE, body_start)
        yield text[body_start:close_idx] if close_idx != -1 else text[body_start:]
        idx = body_start


def contains_any_concern_block(text: str) -> bool:
    """True if ANY opening fence (not just the newest) encloses >=1 concern.

    The runtime parser (:func:`parse_concerns` / :func:`has_concern_block`)
    deliberately looks only at the *last* fence. This is the stricter **authoring**
    check for the shadow sub-procedure docs, which must embed NO contiguous
    ``open -> item -> close`` example *anywhere*: a live shadow-pane capture is a
    bounded window, so a partial capture can isolate an earlier embedded block
    even when a later inline sentinel mention would "mask" it under the
    last-block-wins rule. Minimonitor's picker would then forward the doc's
    placeholder items instead of the agent's real concerns (t1123).
    """
    return any(_parse_items(region) for region in _iter_block_regions(text))


def parse_concerns(capture_text: str) -> list[Concern]:
    """Parse the newest concern block (forgiving — EOF-tolerant).

    Used for the explicit user action. Returns ``[]`` when no opening fence is
    present.
    """
    region = _last_block_region(capture_text, require_close=False)
    return _parse_items(region) if region is not None else []


def unrecovered_markers(capture_text: str) -> list[str]:
    """Marker-looking lines in the newest block that yielded no concern.

    The companion of :func:`parse_concerns` for the same (forgiving) block
    region: what the parser saw but could not turn into a forwardable item. A
    non-empty result means the user is looking at fewer concerns than the shadow
    emitted — the picker surfaces the count so the loss is visible rather than
    silent (t1274).

    Deliberately a *report*, not a recovery. Widening the marker-join envelope
    (:data:`_MAX_MARKER_JOIN_ROWS`) is the documented t1167 trade-off and is not
    revisited here.
    """
    region = _last_block_region(capture_text, require_close=False)
    return _scan_items(region)[1] if region is not None else []


def parse_block_meta(capture_text: str) -> BlockMeta | None:
    """Round metadata from the newest block's header line, or ``None``.

    Same forgiving scope as :func:`parse_concerns` (``require_close=False``), so
    meta and concerns always describe the same (newest) block. Only the **first
    non-blank line** of the region is consulted: a ``Round:`` line appearing
    after an item is body text by the item grammar (it was wrap-joined into that
    item), and believing it here would report a round the block does not carry.

    Fail-open and pure: ``reviewed_at`` is returned verbatim, unvalidated.
    Absent header ⇒ ``None`` and every other entry point behaves exactly as
    before the header existed.

    **Parser safety.** The header occupies the one slot the item scanner already
    ignores: ``_scan_items`` drops a non-blank, non-marker line seen before the
    first item (``items`` empty ⇒ no continuation join), so
    :func:`parse_concerns` / :func:`has_concern_block` /
    :func:`unrecovered_markers` are unaffected by its presence. It
    **deliberately** changes :func:`concern_block_signature` and
    :func:`block_region` — a round bump re-hashes the monitor's freshness
    badge. The header must never itself begin ``- [`` (that shape is recorded
    as an unrecovered marker even before the first item).

    **Consumer contract (t1448):** the freshness key is the
    ``(round, reviewed_at)`` pair — see :class:`BlockMeta`.

    A **metadata-only block** (fences with only the header between them) is the
    producers' machine-readable record of a clean round: this function reads its
    round while :func:`has_concern_block` stays ``False`` for it. Reading the
    round is NOT certifying cleanliness — consumers that auto-clear state must
    use the strict :func:`is_metadata_only_block` instead (this forgiving
    reader also returns meta for a still-streaming or prose-polluted block).
    """
    region = _last_block_region(capture_text, require_close=False)
    if region is None:
        return None
    for line in region.splitlines():
        if not line.strip():
            continue
        match = _META_LINE.match(line)
        if match is None:
            return None
        return BlockMeta(
            int(match.group("round")), (match.group("at") or "").strip()
        )
    return None


def parse_reviewed_at_epoch(reviewed_at: str) -> float | None:
    """Epoch seconds for a block header's ``reviewed_at``, or ``None`` (t1493).

    ``reviewed_at`` is verbatim producer text that :data:`_META_LINE` captures
    as ``.*?`` — the parser validates nothing about its shape. This is the one
    place that turns it into a *time*, so it must be strict and fail to ``None``
    ("cannot tell") rather than guess: a confident freshness verdict derived
    from malformed metadata is worse than no verdict at all.

    **``strptime`` alone is not strict enough.** It accepts non-zero-padded
    components, so ``2026-8-1T1:2:3Z`` parses to a real datetime. The shape is
    therefore pinned by a **canonical round-trip** — re-format the parsed value
    with the same :data:`_REVIEWED_AT_FMT` and require byte equality. One format
    constant drives both directions, so the check cannot drift from the grammar.
    A regex second-guard was rejected for exactly that drift risk.

    **Clock trust.** The producer runs ``date -u +%Y-%m-%dT%H:%M:%SZ`` in the
    shadow pane and the monitor derives its comparison point from
    ``time.time()`` — same host, so the epochs are directly comparable. The
    ``Z``/UTC attachment is explicit rather than naive-local, so the result does
    not depend on the monitor process's timezone.

    Pure. ``""`` (header absent or empty after ``@``) is a normal input, not an
    error.
    """
    text = (reviewed_at or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.strptime(text, _REVIEWED_AT_FMT)
    except ValueError:
        return None
    if parsed.strftime(_REVIEWED_AT_FMT) != text:
        return None  # non-zero-padded components — malformed, not a time
    return parsed.replace(tzinfo=timezone.utc).timestamp()


def contains_block_evidence(text: str) -> bool:
    """True when the capture shows a block whose *age* could be asked about.

    The applicability half of the block-age signal (t1493). "There is no block"
    and "there is a block whose age I cannot establish" are different states:
    collapsing them makes an explain-only shadow — one never asked for a review
    — report "freshness unknown" forever, about feedback that does not exist.

    Deliberately **not** :func:`contains_any_concern_block`: that one requires
    at least one parsed *item*, so a metadata-only clean round (a block whose
    age very much matters) would read ``False``, and it is scoped to the
    authoring-time check for shadow docs rather than to runtime.

    The second arm covers the capture window that started *inside* a block: the
    opening fence is off-screen, so the region lookup finds nothing, but a block
    is plainly present and its age is simply unknown.
    """
    return (_last_block_region(text, require_close=False) is not None
            or block_head_truncated(text))


def has_invalid_round_header(text: str) -> bool:
    """True when the newest block leads with a ``Round:``-shaped line that
    fails the grammar (zero, zero-padded, oversized, or otherwise malformed).

    :func:`parse_block_meta` reads such a header as absent (``None``) — the
    fail-open contract — but consumers must not then treat the block as a
    plain headerless one: a producer *tried* to emit round metadata and got it
    wrong, which is investigable output, not silence. Same forgiving region as
    the other readers, and only the first non-blank line is consulted (a
    ``Round:`` line after an item is body text by the item grammar).
    """
    region = _last_block_region(text, require_close=False)
    if region is None:
        return False
    for line in region.splitlines():
        if not line.strip():
            continue
        return (line.lstrip().startswith("Round:")
                and _META_LINE.match(line) is None)
    return False


def is_metadata_only_block(text: str) -> bool:
    """Strict predicate: the newest block is a certified clean-round record.

    True only when the LAST opening fence has its own closing fence after it
    (``require_close=True`` — a still-streaming header-only block may be about
    to emit items, so it must **not** certify) and the enclosed region's
    non-blank content is **exactly one line, the round header**. This is
    deliberately stronger than ``parse_block_meta(text) and no concerns``:
    a header followed by stray non-marker prose parses to nothing and loses
    nothing *visible*, but the prose was silently dropped — such a block is
    malformed output to investigate, not a clean round to auto-clear.

    Consumers use this to treat a clean round as *handled* (no toast, no
    standing badge, "Clean review (round N)" on the explicit action) —
    misclassifying either direction is user-visible, hence the strictness.
    """
    region = _last_block_region(text, require_close=True)
    if region is None:
        return False
    lines = [line for line in region.splitlines() if line.strip()]
    return len(lines) == 1 and _META_LINE.match(lines[0]) is not None


def block_region(capture_text: str) -> str | None:
    """The newest block's raw region text, or ``None`` when no fence is present.

    Same forgiving scope as :func:`parse_concerns` / :func:`unrecovered_markers`
    (``require_close=False``), so all three always describe the *same* block: the
    lines a user inspects are exactly the lines those two read.

    **Display only.** The text is returned verbatim for a human to read; it is
    never parsed into forwardable items. A shadow doc read into the pane can
    carry literal ``- [priority | region]`` example lines (the t1123 hazard),
    which is why the block a user *inspects* and the block the picker *forwards*
    stay separate code paths (t1293).
    """
    return _last_block_region(capture_text, require_close=False)


def has_concern_block(text: str) -> bool:
    """Strict trigger predicate for the UI auto-offer.

    True only when the LAST opening fence has its own closing fence after it and
    the enclosed block yields at least one concern.
    """
    region = _last_block_region(text, require_close=True)
    return bool(_parse_items(region)) if region is not None else False


def block_head_truncated(text: str) -> bool:
    """True when the capture window clipped the opening fence of the block.

    A closing fence with **no opening fence anywhere in the capture** means the
    window starts inside a block: the shadow did emit concerns, but the capture
    is too shallow to see where they began. Both runtime entry points key off
    the last opening fence, so this is otherwise indistinguishable from "no
    concerns at all" — a silent false negative (t1187).

    Scoped to the **newest** block, matching the last-block-wins semantics of
    :func:`_last_block_region`: if any opening fence is present, the newest
    block's head is by definition intact and the runtime can parse it, so an
    *older* clipped block is not the user's problem and must not raise a
    capture-window warning. (An ordering variant — "the first closing fence has
    no opening fence before it" — is wrong: it fires when an older block was
    clipped and a newer review is merely still streaming.)

    Deliberately a *detector*, not a recovery: the text above an orphan closing
    fence is untrusted (a shadow doc read into the pane can carry literal
    ``- [priority | region]`` example lines — the t1123 hazard), so it is never
    parsed into forwardable concerns. Callers re-capture deeper instead.

    Known blind spot: a block clipped at the head that is *also* still
    streaming (no closing fence captured yet) is indistinguishable from a pane
    with no block at all and reads ``False``. Accepted — the caller's deeper
    capture window is the defense there.
    """
    return _CLOSE in text and _OPEN not in text


def concern_block_signature(raw_text: str) -> str | None:
    """Cheap freshness trigger over a raw tick capture (t1216_1).

    Returns a **reflow-stable** digest of the last complete block region, or
    ``None`` when no complete block is present. Its input is the NON-wrap-joined,
    ANSI-bearing text the refresh tick already captured (``capture-pane -p -e``),
    so a caller can tell "this block changed" for N agents without spending a
    single extra tmux round-trip. Compare successive return values for equality;
    that is the only supported use.

    **Trigger only — never parse this input into forwardable concerns.** Without
    ``-J`` a soft-wrapped concern body is split mid-word, which is precisely what
    the module's wrap-join contract forbids. A caller acting on a change must
    re-capture with ``-J`` and go through :func:`parse_concerns`.

    Normalisation is ANSI-strip, then whitespace runs to a single space, then
    strip. `tmux capture-pane` without ``-J`` breaks a wrapped row with a
    newline and pads rows with trailing spaces; it inserts nothing else. So this
    is exact for trailing padding and for wraps at a word boundary, and the
    digest survives a resize, a scrollbar gutter appearing, or an ANSI rendering
    change — all of which would otherwise make an unchanged block look fresh.

    Collapsing whitespace to *nothing* was considered and **rejected**: it is
    fully reflow-proof but erases token boundaries, so ``"needs review"`` and
    ``"needsreview"`` would collide and a genuinely changed concern would be
    silently missed. Missing a real change is the one failure this must not have.

    **Known residual:** a wrap landing *mid-word* injects a space that was not in
    the source, so the same block re-rendered at a different pane width can
    re-hash. Deliberately accepted, because it fails in the safe direction — at
    most **one spurious re-offer** (a badge, and one toast if the user selects
    it; nothing is lost or forwarded), never a missed real change. Pinned by a
    test so it is not "fixed" back into a collision.

    **Blind spot:** on a pane narrower than :data:`_SENTINEL_SAFE_COLS` the fence
    itself wraps and this returns ``None`` — indistinguishable here from a
    concern-free pane. Callers that can see the pane width should fall back to an
    authoritative ``-J`` capture below that width.
    """
    region = _last_block_region(strip_ansi(raw_text), require_close=True)
    if region is None:
        return None
    normalized = re.sub(r"\s+", " ", region).strip()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def concern_marker_line(c: Concern) -> str:
    """One concern in canonical ``- [priority | region] body`` marker form.

    The single renderer of that grammar (t1427_2). Both consumers are FORWARD
    paths and must agree byte-for-byte: the clipboard payload below, and the
    rejection store, whose entries the shadow later matches fresh concerns
    against — a store holding a differently-rendered line would not match.

    ``.body``, never ``display_body()``: the trailer is metadata the receiving
    agent needs. Frozen with a FORWARD role in
    tests/test_concern_body_display_contract.py (t1294).
    """
    return f"- [{c.priority} | {c.region}] {c.body}"


def build_clipboard_payload(
    concerns: list[Concern], preamble: str = DEFAULT_PREAMBLE
) -> str:
    """Render selected concerns into a clipboard payload for the code-agent.

    A preamble line, a blank line, then each concern in canonical
    ``- [priority | region] body`` form, in order.
    """
    lines = [preamble, ""]
    for c in concerns:
        lines.append(concern_marker_line(c))
    return "\n".join(lines)
