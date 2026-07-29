"""Frontmatter key-ordering contract for lib/task_yaml.py (t1302).

`serialize_frontmatter` documents "board keys (boardcol, boardidx) always last",
but it used to insert `original_key_order` first and then *re-assign* the board
keys. Re-assigning a key already present in a dict does not move it, so a task
file with `boardcol` mid-frontmatter kept it mid-frontmatter. t1243_8 adds
`boardgroup` to the same ordering rule and would have inherited the broken
guarantee.

The fix has two halves and both are pinned here:

1. board keys genuinely move last (the contract), and
2. board keys that are ALREADY last keep their existing relative order.

Half 2 is not cosmetic: 36 live task files end `boardidx, boardcol`, so a tail
loop that iterates BOARD_KEYS in canonical order would rewrite every one of them
on its next save. `tests/test_board_movement.py` also depends on unchanged-value
writes being byte-identical.

Run: python3 tests/test_task_yaml_key_order.py -v
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
_LIB = str(REPO_ROOT / ".aitask-scripts" / "lib")
if _LIB not in sys.path:
    sys.path.insert(0, _LIB)

from task_yaml import parse_frontmatter, serialize_frontmatter  # noqa: E402

_BODY = "body\n"


def _frontmatter_keys(text: str) -> list[str]:
    """Top-level frontmatter keys, in emitted order."""
    block = text.split("---\n")[1]
    return [ln.split(":")[0] for ln in block.split("\n") if re.match(r"^\w+:", ln)]


def _roundtrip(raw: str) -> str:
    return serialize_frontmatter(*parse_frontmatter(raw))


class BoardKeyOrderingTests(unittest.TestCase):
    def test_mid_frontmatter_board_key_moves_last(self):
        """The task's verbatim reproduction: boardcol in the middle moves last."""
        raw = (
            "---\n"
            "priority: high\n"
            "boardcol: now\n"
            "status: Ready\n"
            "boardidx: 10\n"
            "---\n" + _BODY
        )
        self.assertEqual(
            ["priority", "status", "boardcol", "boardidx"],
            _frontmatter_keys(_roundtrip(raw)),
        )

    def test_reverse_order_board_keys_are_byte_stable(self):
        """A file ending `boardidx, boardcol` must NOT be reordered.

        This is the regression a canonical-order tail loop would cause; 36 live
        task files have exactly this shape.
        """
        raw = (
            "---\n"
            "priority: high\n"
            "status: Ready\n"
            "boardidx: 10\n"
            "boardcol: now\n"
            "---\n" + _BODY
        )
        out = _roundtrip(raw)
        self.assertEqual(raw, out, "reverse-order board keys were rewritten")
        self.assertEqual(
            ["priority", "status", "boardidx", "boardcol"], _frontmatter_keys(out)
        )

    def test_forward_order_board_keys_are_byte_stable(self):
        raw = (
            "---\n"
            "priority: high\n"
            "status: Ready\n"
            "boardcol: now\n"
            "boardidx: 10\n"
            "---\n" + _BODY
        )
        self.assertEqual(raw, _roundtrip(raw))

    def test_single_board_key_is_byte_stable(self):
        """The most common live shape: boardidx alone, already last."""
        raw = "---\npriority: high\nstatus: Ready\nboardidx: 10\n---\n" + _BODY
        self.assertEqual(raw, _roundtrip(raw))

    def test_no_board_keys_is_byte_stable(self):
        raw = "---\npriority: high\nstatus: Ready\n---\n" + _BODY
        self.assertEqual(raw, _roundtrip(raw))

    def test_new_non_board_key_lands_before_board_keys(self):
        raw = "---\npriority: high\nboardcol: now\nboardidx: 10\n---\n" + _BODY
        meta, body, order = parse_frontmatter(raw)
        meta["status"] = "Ready"
        self.assertEqual(
            ["priority", "status", "boardcol", "boardidx"],
            _frontmatter_keys(serialize_frontmatter(meta, body, order)),
        )

    def test_new_board_key_appends_after_existing_board_keys(self):
        """A board key absent from the original order appends after the ones present."""
        raw = "---\npriority: high\nboardidx: 10\n---\n" + _BODY
        meta, body, order = parse_frontmatter(raw)
        meta["boardcol"] = "next"
        self.assertEqual(
            ["priority", "boardidx", "boardcol"],
            _frontmatter_keys(serialize_frontmatter(meta, body, order)),
        )


if __name__ == "__main__":
    unittest.main()
