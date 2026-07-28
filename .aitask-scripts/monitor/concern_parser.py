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
- **Last block wins:** when several blocks are present, only the most recent
  one is parsed (a re-issued review supersedes an earlier one).

Three strictness tiers. The first two share :func:`_last_block_region`, diverging
only on ``require_close``; the third shares it too but consumes a *different
capture shape* and never yields concerns:

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
=============================== ============================== ==========================================
"""
from __future__ import annotations

import hashlib
import re
from typing import NamedTuple

try:
    from .ansi_utils import strip_ansi
except ImportError:  # imported flat (tests put MONITOR_DIR on sys.path)
    from ansi_utils import strip_ansi  # noqa: E402

_OPEN = "===AITASK-CONCERNS==="
_CLOSE = "===END-CONCERNS==="

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

DEFAULT_PREAMBLE = (
    "I have some concerns: please verify them and if valid "
    "please address in the plan"
)


class Concern(NamedTuple):
    priority: str   # one of {"high", "medium", "low"}
    region: str     # free-text plan-region / axis label
    body: str       # free-text concern body (wrap-joined)


def _norm_priority(raw: str) -> str:
    p = raw.strip().lower()
    return p if p in _VALID else "low"


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


def _parse_items(region: str) -> list[Concern]:
    """Extract concerns from a block region (the only home of the grammar).

    A line matching the item marker starts a new concern; any other non-blank
    line is a wrap continuation and is appended (space-joined) to the current
    concern's body. Blank lines are ignored.

    A row that *starts* like a marker but whose bracket never closes on that row
    is offered to :func:`_join_split_marker`, which rejoins a bounded number of
    following rows to recover a marker the renderer hard-wrapped mid-bracket.
    """
    # Each entry: [priority, region, [body_parts]].
    items: list[list] = []
    lines = region.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = _ITEM.match(line)
        consumed = 1
        if m is None and _MARKER_START.match(line) and "]" not in line:
            m, consumed = _join_split_marker(lines, i)
        if m:
            items.append([m.group("priority"), m.group("region"), [m.group("body")]])
        elif line.strip() and items:
            items[-1][2].append(line)
        i += consumed
    out: list[Concern] = []
    for priority, region_label, parts in items:
        body = " ".join(p.strip() for p in parts if p.strip()).strip()
        out.append(Concern(_norm_priority(priority), region_label.strip(), body))
    return out


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


def build_clipboard_payload(
    concerns: list[Concern], preamble: str = DEFAULT_PREAMBLE
) -> str:
    """Render selected concerns into a clipboard payload for the code-agent.

    A preamble line, a blank line, then each concern in canonical
    ``- [priority | region] body`` form, in order.
    """
    lines = [preamble, ""]
    for c in concerns:
        lines.append(f"- [{c.priority} | {c.region}] {c.body}")
    return "\n".join(lines)
