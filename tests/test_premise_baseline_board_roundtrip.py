"""`premise_baseline:` (t1663_2) survives the board's and the merge driver's writers.

The board has no widget for the field, so the only way it can lose it is by
rewriting the frontmatter: `Task.save()` and `reload_and_save_board_fields()`
re-serialize the whole block through `task_yaml.serialize_frontmatter`, and the
sync merge driver does the same after resolving a conflict. A value the YAML
dumper re-quoted, or a key the board dropped, would reach the bash reader
(`aitask_update.sh`, line-oriented) and the premise reader in a different shape.

The variants cover the shapes that could plausibly re-serialize differently:
an ordinary sha, an all-digit sha (an int if the ` @ <ts>` suffix were ever
lost), and a 64-hex SHA-256 id.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for _p in (REPO_ROOT / ".aitask-scripts" / "board", REPO_ROOT / ".aitask-scripts" / "lib"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from aitask_merge import merge_frontmatter  # noqa: E402
from board_task_model import Task  # noqa: E402
from task_yaml import parse_frontmatter, serialize_frontmatter  # noqa: E402

VARIANTS = {
    "sha1": "3f2a9c" + "0" * 34 + " @ 2026-11-01 09:00",
    "all_digit": "1234567890" * 4 + " @ 2026-11-01 09:00",
    "sha256": "ab" * 32 + " @ 2026-11-01 09:00",
}


def _task_text(value: str) -> str:
    return (
        "---\n"
        "priority: medium\n"
        "effort: low\n"
        "depends: []\n"
        "issue_type: feature\n"
        "status: Ready\n"
        "labels: []\n"
        f"premise_baseline: {value}\n"
        "created_at: 2026-11-01 08:00\n"
        "updated_at: 2026-11-01 08:00\n"
        "boardcol: now\n"
        "boardidx: 10\n"
        "---\n"
        "\n"
        "Body.\n"
    )


def _baseline_line(text: str) -> str:
    lines = [l for l in text.splitlines() if l.startswith("premise_baseline:")]
    return lines[0] if len(lines) == 1 else f"<{len(lines)} premise_baseline lines>"


class BoardRoundTripTests(unittest.TestCase):

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _write(self, name: str, value: str) -> Path:
        path = self.dir / f"t{name}.md"
        path.write_text(_task_text(value), encoding="utf-8")
        return path

    def test_premise_baseline_parses_as_a_string(self):
        """Precondition for everything below: the reader needs a YAML string."""
        for name, value in VARIANTS.items():
            with self.subTest(variant=name):
                meta, _body, _order = parse_frontmatter(_task_text(value))
                self.assertIsInstance(meta["premise_baseline"], str)
                self.assertEqual(meta["premise_baseline"], value)

    def test_save_is_byte_identical(self):
        for i, (name, value) in enumerate(VARIANTS.items()):
            with self.subTest(variant=name):
                path = self._write(str(10 + i), value)
                before = path.read_bytes()
                Task(path).save()
                self.assertEqual(path.read_bytes(), before)

    def test_board_layout_save_keeps_the_field(self):
        for i, (name, value) in enumerate(VARIANTS.items()):
            with self.subTest(variant=name):
                path = self._write(str(20 + i), value)
                task = Task(path)
                task.metadata["boardidx"] = 30
                task.reload_and_save_board_fields(("boardidx",))
                text = path.read_text(encoding="utf-8")
                # Not vacuous: the board write really happened.
                self.assertIn("boardidx: 30", text)
                self.assertEqual(_baseline_line(text), f"premise_baseline: {value}")

    def test_merge_serialize_keeps_the_field(self):
        for name, value in VARIANTS.items():
            with self.subTest(variant=name):
                meta, body, order = parse_frontmatter(_task_text(value))
                # A concurrent edit the driver resolves on its own (`status`
                # always resolves to Implementing), so the merged block really is
                # re-serialized. The baseline is unchanged on both sides and must
                # come through as-is.
                remote = dict(meta, status="Implementing")
                merged, unresolved = merge_frontmatter(
                    meta, remote, batch=True, base_meta=dict(meta))
                self.assertEqual(unresolved, [])
                text = serialize_frontmatter(merged, body, order)
                self.assertIn("status: Implementing", text)
                self.assertEqual(_baseline_line(text), f"premise_baseline: {value}")


if __name__ == "__main__":
    unittest.main()
