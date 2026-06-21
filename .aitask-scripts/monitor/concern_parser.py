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
the join; see ``aidocs/framework/shadow_concern_format.md``.

Format (single source of truth: ``aidocs/framework/shadow_concern_format.md``)::

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
- ``priority`` is normalized case-insensitively to {high, medium, low}; an
  unknown value degrades to ``low`` (the item is never dropped).
- **Last block wins:** when several blocks are present, only the most recent
  one is parsed (a re-issued review supersedes an earlier one).

Two consumers, two strictnesses (both share :func:`_last_block_region`, diverging
only on ``require_close``):

- :func:`parse_concerns` — **forgiving** path for the *explicit* user action
  (the user pressed the picker hotkey): parses the newest block to EOF even if
  its closing fence was truncated from scrollback.
- :func:`has_concern_block` — **strict** trigger predicate for the UI
  *auto-offer*: the newest opening fence must have *its own* closing fence
  after it and yield >=1 concern, so the picker is not offered for an
  incomplete (still streaming), empty, or malformed block.
"""
from __future__ import annotations

import re
from typing import NamedTuple

_OPEN = "===AITASK-CONCERNS==="
_CLOSE = "===END-CONCERNS==="

# Leading "- " (dash + space) is MANDATORY — collision hardening: a wrapped
# continuation line never carries it, so it can never start a spurious concern.
_ITEM = re.compile(
    r"^\s*-\s+\[\s*(?P<priority>\w+)\s*\|\s*(?P<region>[^\]]*)\]\s*(?P<body>.*)$"
)

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


def _parse_items(region: str) -> list[Concern]:
    """Extract concerns from a block region (the only home of the grammar).

    A line matching the item marker starts a new concern; any other non-blank
    line is a wrap continuation and is appended (space-joined) to the current
    concern's body. Blank lines are ignored.
    """
    # Each entry: [priority, region, [body_parts]].
    items: list[list] = []
    for line in region.splitlines():
        m = _ITEM.match(line)
        if m:
            items.append([m.group("priority"), m.group("region"), [m.group("body")]])
        elif line.strip() and items:
            items[-1][2].append(line)
    out: list[Concern] = []
    for priority, region_label, parts in items:
        body = " ".join(p.strip() for p in parts if p.strip()).strip()
        out.append(Concern(_norm_priority(priority), region_label.strip(), body))
    return out


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
