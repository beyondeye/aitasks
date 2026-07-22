#!/usr/bin/env python3
"""Board-vs-gatherer membership/order equivalence oracle (t1162_1).

The board is the UI a user reviews a work-report selection in, so the gatherer
must return exactly the tasks the board shows, in exactly the board's order —
otherwise the report silently covers a different set than the one that was
picked. This compares the two directly rather than trusting that the gatherer
re-derives the board's rules correctly.

Ground truth: TaskManager.get_column_tasks (constructs headlessly, no Textual
app). Subject: the real CLI entry point, parsed with the documented maxsplit
rule.

Usage: work_report_equiv.py <repo_root>
Env:   TASK_DIR must point at the tree under test (read at board import time).
Out:   `EQUIV_OK`, or a diff on stderr and a nonzero exit.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

TASK_FIELDS = 9  # TASK: has 8 fixed fields + 1 free-text path, always last


def board_columns(repo_root: Path):
    """{col_id: [filename, ...]} straight from the board's own model."""
    for sub in ("board", "lib"):
        path = str(repo_root / ".aitask-scripts" / sub)
        if path not in sys.path:
            sys.path.insert(0, path)
    from aitask_board import TaskManager  # noqa: E402  (TASK_DIR-sensitive import)

    manager = TaskManager()
    col_ids = ["unordered"] + list(manager.column_order)
    return {cid: [t.filename for t in manager.get_column_tasks(cid)] for cid in col_ids}


def gatherer_columns(repo_root: Path, col_ids):
    """{col_id: [filename, ...]} from the real CLI."""
    script = repo_root / ".aitask-scripts" / "aitask_work_report_gather.sh"
    result = subprocess.run(
        [str(script), "--columns", ",".join(col_ids)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"gatherer exited {result.returncode}\n{result.stderr}", file=sys.stderr
        )
        sys.exit(1)

    found = {cid: [] for cid in col_ids}
    for line in result.stdout.splitlines():
        if not line.startswith("TASK:"):
            continue
        fields = line[len("TASK:"):].split("|", TASK_FIELDS - 1)
        col_id, path = fields[0], fields[-1]
        found.setdefault(col_id, []).append(os.path.basename(path))
    return found


def main(argv):
    if len(argv) != 2:
        print("usage: work_report_equiv.py <repo_root>", file=sys.stderr)
        return 2
    repo_root = Path(argv[1]).resolve()

    expected = board_columns(repo_root)
    actual = gatherer_columns(repo_root, list(expected))

    mismatches = [
        f"  column {cid!r}:\n    board:    {expected[cid]}\n    gatherer: {actual.get(cid, [])}"
        for cid in expected
        if expected[cid] != actual.get(cid, [])
    ]
    if mismatches:
        print("board/gatherer disagree:", file=sys.stderr)
        print("\n".join(mismatches), file=sys.stderr)
        return 1

    print("EQUIV_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
