---
Task: t1037_1_concern_format_spec_and_parser.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_2_*.md, aitasks/t1037/t1037_3_*.md, aitasks/t1037/t1037_4_*.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_*_*.md
Worktree: (current branch — fast profile)
Branch: (current branch)
Base branch: main
plan_verified:
  - claudecode/opus4_8 @ 2026-06-21 11:55
---

# Plan: Concern-block format spec + pure parser (t1037_1)

Foundation child. Pins the concern-block contract and ships the pure parser +
payload builder. No tmux, no Textual — this is the headless unit, pulled first
and unit-tested in isolation.

## 1. Format decision (write the spec first)

Author `aidocs/framework/shadow_concern_format.md` defining:

- **Fence:** `===AITASK-CONCERNS===` … `===END-CONCERNS===` (ASCII, won't
  collide with markdown ``` fences, survives tmux capture).
- **Item marker:** a line matching `^\s*-\s+\[\s*(?P<priority>\w+)\s*\|\s*(?P<region>[^\]]*)\]\s*(?P<body>.*)$`.
  The leading `- ` (dash + space) is **MANDATORY** (collision hardening — see
  below). The producer (t1037_2) MUST emit it on every concern line.
- **Wrap-join rule (load-bearing):** `tmux capture-pane` returns *visually
  wrapped* lines. Between the fences, a line matching the item marker starts a
  new concern; any other non-blank line appends (space-joined, stripped) to the
  current concern's body. Blank lines ignored.
- **Collision hardening (mandatory dash):** tmux soft-wrapping never inserts a
  leading `- ` on a continuation line, so requiring the dash means a wrapped
  body line — even one whose text contains bracket-looking (`[high | x] …`) or
  key-value-looking (`priority=high …`) substrings, common in technical
  critique — **cannot** be misread as a new concern. This is why the dash is
  mandatory, not optional.
- **Fields:** priority ∈ {high, medium, low}, case-insensitive; unknown →
  `low` (item retained, never dropped). region = free text. body = free text.
- **Missing closing fence:** parse from the opening fence to EOF.
- **Multi-block policy:** **last block wins** (a re-issued review supersedes an
  earlier one). Document this; it answers the parent's open question.
- **Trigger vs action contract:** document that detecting a block for the UI
  *auto-offer* requires a COMPLETE block (both fences) with ≥1 parseable
  concern (`has_concern_block`, strict), whereas the *explicit* user action
  parses forgivingly (`parse_concerns`, EOF-tolerant). Producers must emit the
  closing fence so the auto-offer fires.
- Worked example + a note that this file is the single source of truth cited by
  t1037_2 (producer) and t1037_3/_4 (consumers).
- Add a one-line pointer from `aidocs/framework/shadow_agent.md`.

## 2. Parser module

Create `.aitask-scripts/monitor/concern_parser.py` (sibling to
`prompt_patterns.py`):

```python
from __future__ import annotations
import re
from typing import NamedTuple

_OPEN = "===AITASK-CONCERNS==="
_CLOSE = "===END-CONCERNS==="
# Leading "- " is MANDATORY (collision hardening — continuation lines never
# carry it, so they can never be misread as a new concern).
_ITEM = re.compile(r"^\s*-\s+\[\s*(?P<priority>\w+)\s*\|\s*(?P<region>[^\]]*)\]\s*(?P<body>.*)$")
_VALID = {"high", "medium", "low"}
DEFAULT_PREAMBLE = ("I have some concerns: please verify them and if valid "
                    "please address in the plan")

class Concern(NamedTuple):
    priority: str
    region: str
    body: str

def has_concern_block(text: str) -> bool:
    # STRICT trigger predicate (used by t1037_4's auto-offer): require a
    # COMPLETE block — both fences present (closing after opening) — AND at
    # least one successfully-parsed concern. Deliberately stricter than a bare
    # `_OPEN in text` so the picker is NOT offered for an incomplete (still
    # streaming), empty, or malformed block. (See concern #1.)
    if _OPEN not in text or _CLOSE not in text:
        return False
    if text.index(_CLOSE) < text.index(_OPEN):  # close before open in last block
        ...  # handle by parsing; simplest: rely on parse_concerns result
    return bool(parse_concerns(text))

def parse_concerns(capture_text: str) -> list[Concern]:
    # FORGIVING explicit-action path (used when the user pressed 'c').
    # locate the LAST opening fence (last block wins)
    # collect lines until _CLOSE or EOF (missing close → parse to EOF; the
    #   user asked for it and scrollback may have truncated the closing fence)
    # wrap-join: item marker -> new concern; else append to current body
    # normalize priority (lower, default low), strip region/body
    ...

def build_clipboard_payload(concerns, preamble: str = DEFAULT_PREAMBLE) -> str:
    # preamble line, blank line, then each concern rendered verbatim in the
    # canonical "- [priority | region] body" form, in order
    ...
```

Implementation notes:
- **Two consumers, two strictnesses (concern #1):** `has_concern_block` is the
  **strict** gate for the *auto-offer* (t1037_4) — complete block + ≥1 concern,
  so a still-streaming or empty/malformed block does not trigger the picker.
  `parse_concerns` is the **forgiving** path for the *explicit* `c` press —
  parses to EOF even without a closing fence. This split also resolves the
  latent tension between "parse to EOF when no closing fence" and "offer on
  presence": being forgiving on EOF would otherwise fire the auto-offer
  mid-stream; gating the offer on the strict predicate prevents that.
- `parse_concerns`: find last `_OPEN`; if none → `[]`. Iterate following lines;
  stop at `_CLOSE`. Build concerns via the marker/append rule. Normalize.
- `build_clipboard_payload`: render selected concerns back to canonical form so
  the followed agent receives them cleanly.

## 3. Tests — `tests/test_concern_parser.py`

Pytest-style (match `tests/test_board_*.py`). Cases:
1. canonical 2-item block → 2 Concerns with right fields.
2. **wrap-join round-trip:** take a long-body concern, hard-wrap at ~40 cols
   (simulating tmux), assert body rejoins to the original.
3. **marker-collision (concern #2):** a concern whose wrapped body continuation
   lines contain marker-*looking* text — one line literally containing
   `[high | something]` and another literally containing `priority=high …`,
   **neither with a leading `- `**. Assert the parser produces exactly ONE
   concern (the continuation text is appended to its body, NOT split into new
   items). This proves the mandatory-dash hardening.
4. no block → `[]`; `has_concern_block` False.
5. unknown priority (e.g. `- [critical | x] …`) → `low`, item retained.
6. missing closing fence → `parse_concerns` still parses to EOF, **but
   `has_concern_block` returns False** (strict trigger requires the closing
   fence — concern #1).
7. **strict trigger (concern #1):** empty block (both fences, no items) and a
   malformed block (opening fence + garbage, no valid marker) → `parse_concerns`
   → `[]` and `has_concern_block` → False; a complete block with ≥1 concern →
   `has_concern_block` → True.
8. multi-block input → only the LAST block's concerns returned.
9. `build_clipboard_payload([c0, c2])` → preamble + those two verbatim, in
   order.

Generate fixture #2 by piping a hand-written block through
`./.aitask-scripts/aitask_shadow_capture.sh -` to mimic real cleaning.

## 4. Verification

- Run `tests/test_concern_parser.py` (repo's `.py` test invocation) — all pass.
- Round-trip a real capture by hand; confirm extraction.
- `shellcheck` only if shell touched (none expected).

## 5. Final Implementation Notes (fill at completion)

Record prominently — siblings t1037_2/_3/_4 depend on these exact values:
- the FINAL sentinel strings and the exact item-marker regex (with the
  **mandatory leading `- `**);
- the multi-block policy (last block wins);
- the **strict `has_concern_block`** contract (t1037_4's auto-offer gates on it;
  t1037_2's producer must emit the closing fence so it fires).

See parent task t1037 and **Step 9 (Post-Implementation)** of the task workflow
for archival/merge.

## Risk

### Code-health risk: low
- None identified. Additive new files only (`concern_parser.py` + spec doc);
  the sole edit to existing code is a one-line pointer in
  `aidocs/framework/shadow_agent.md`. No load-bearing path touched.

### Goal-achievement risk: low
- Wrap-join could misfire if a body continuation line coincidentally matches the
  item-marker regex, splitting one concern into two · severity: low · →
  mitigation: covered in-task by a dedicated wrap-join + marker-collision test
  (no separate mitigation task needed).

