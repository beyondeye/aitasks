---
Task: t1037_1_concern_format_spec_and_parser.md
Parent Task: aitasks/t1037_minimonitor_shadow_concern_picker.md
Sibling Tasks: aitasks/t1037/t1037_2_*.md, aitasks/t1037/t1037_3_*.md, aitasks/t1037/t1037_4_*.md
Archived Sibling Plans: aiplans/archived/p1037/p1037_*_*.md
Worktree: (current branch — fast profile)
Branch: (current branch)
Base branch: main
---

# Plan: Concern-block format spec + pure parser (t1037_1)

Foundation child. Pins the concern-block contract and ships the pure parser +
payload builder. No tmux, no Textual — this is the headless unit, pulled first
and unit-tested in isolation.

## 1. Format decision (write the spec first)

Author `aidocs/framework/shadow_concern_format.md` defining:

- **Fence:** `===AITASK-CONCERNS===` … `===END-CONCERNS===` (ASCII, won't
  collide with markdown ``` fences, survives tmux capture).
- **Item marker:** a line matching `^\s*-\s*\[\s*(?P<priority>\w+)\s*\|\s*(?P<region>[^\]]*)\]\s*(?P<body>.*)$`.
  Leading list dash optional.
- **Wrap-join rule (load-bearing):** `tmux capture-pane` returns *visually
  wrapped* lines. Between the fences, a line matching the item marker starts a
  new concern; any other non-blank line appends (space-joined, stripped) to the
  current concern's body. Blank lines ignored.
- **Fields:** priority ∈ {high, medium, low}, case-insensitive; unknown →
  `low` (item retained, never dropped). region = free text. body = free text.
- **Missing closing fence:** parse from the opening fence to EOF.
- **Multi-block policy:** **last block wins** (a re-issued review supersedes an
  earlier one). Document this; it answers the parent's open question.
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
_ITEM = re.compile(r"^\s*-?\s*\[\s*(?P<priority>\w+)\s*\|\s*(?P<region>[^\]]*)\]\s*(?P<body>.*)$")
_VALID = {"high", "medium", "low"}
DEFAULT_PREAMBLE = ("I have some concerns: please verify them and if valid "
                    "please address in the plan")

class Concern(NamedTuple):
    priority: str
    region: str
    body: str

def has_concern_block(text: str) -> bool:
    return _OPEN in text

def parse_concerns(capture_text: str) -> list[Concern]:
    # locate the LAST opening fence (last block wins)
    # collect lines until _CLOSE or EOF
    # wrap-join: item marker -> new concern; else append to current body
    # normalize priority (lower, default low), strip region/body
    ...

def build_clipboard_payload(concerns, preamble: str = DEFAULT_PREAMBLE) -> str:
    # preamble line, blank line, then each concern rendered verbatim in the
    # canonical "- [priority | region] body" form, in order
    ...
```

Implementation notes:
- `parse_concerns`: find last `_OPEN`; if none → `[]`. Iterate following lines;
  stop at `_CLOSE`. Build concerns via the marker/append rule. Normalize.
- `build_clipboard_payload`: render selected concerns back to canonical form so
  the followed agent receives them cleanly.

## 3. Tests — `tests/test_concern_parser.py`

Pytest-style (match `tests/test_board_*.py`). Cases:
1. canonical 2-item block → 2 Concerns with right fields.
2. **wrap-join round-trip:** take a long-body concern, hard-wrap at ~40 cols
   (simulating tmux), assert body rejoins to the original.
3. no block → `[]`; `has_concern_block` False.
4. unknown priority (e.g. `[critical | x] …`) → `low`, item retained.
5. missing closing fence → still parses to EOF.
6. multi-block input → only the LAST block's concerns returned.
7. `build_clipboard_payload([c0, c2])` → preamble + those two verbatim, in
   order.

Generate fixture #2 by piping a hand-written block through
`./.aitask-scripts/aitask_shadow_capture.sh -` to mimic real cleaning.

## 4. Verification

- Run `tests/test_concern_parser.py` (repo's `.py` test invocation) — all pass.
- Round-trip a real capture by hand; confirm extraction.
- `shellcheck` only if shell touched (none expected).

## 5. Final Implementation Notes (fill at completion)

Record the FINAL sentinel string, the exact item-marker regex, and the
multi-block policy prominently — siblings t1037_2/_3/_4 depend on these exact
values.

See parent task t1037 and **Step 9 (Post-Implementation)** of the task workflow
for archival/merge.
