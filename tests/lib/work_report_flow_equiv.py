#!/usr/bin/env python3
"""Board-flow-vs-gatherer round-trip oracle (t1162_4).

Computes the exact ``--columns``/``--tasks`` args the board `w` flow would
launch for an all-selected review — using the flow's REAL code paths
(``KanbanApp._work_report_columns`` for the offered column set,
``TaskManager.get_column_tasks`` + ``TaskCard._parse_filename`` for the
grouped task ids in displayed order) — feeds them through the real gatherer
CLI, and asserts the gatherer accepts them and reproduces the same task
membership AND order per column.

This is the flow-level oracle on top of t1162_1's data-layer equivalence
(``work_report_equiv.py``): any drift (archived/child/phantom exclusion,
default boardcol, tie-breaks, Unsorted, stale column_order entries) fails
here. Reconcile by fixing the gatherer to match the board, not vice versa.

Usage: work_report_flow_equiv.py <repo_root>
Env:   TASK_DIR must point at the tree under test (read at board import time).
Out:   `FLOW_EQUIV_OK`, or a diagnostic on stderr and a nonzero exit.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

TASK_FIELDS = 9  # TASK: has 8 fixed fields + 1 free-text path, always last


def board_flow_args(repo_root: Path):
    """(col_ids, {col_id: [task_id, ...]}) exactly as the `w` flow composes them."""
    for sub in ("board", "lib"):
        path = str(repo_root / ".aitask-scripts" / sub)
        if path not in sys.path:
            sys.path.insert(0, path)
    from aitask_board import KanbanApp, TaskCard, TaskManager  # noqa: E402

    manager = TaskManager()
    shim = SimpleNamespace(manager=manager)
    columns = KanbanApp._work_report_columns(shim)
    col_ids = [col_id for col_id, _ in columns]

    grouped = {}
    for col_id in col_ids:
        ids = []
        for task in manager.get_column_tasks(col_id):
            task_num, _ = TaskCard._parse_filename(task.filename)
            if not task_num:
                continue
            ids.append(task_num.lstrip("t"))
        grouped[col_id] = ids
    return col_ids, grouped


def gatherer_columns(repo_root: Path, cols_csv: str, tasks_csv: str):
    """{col_id: [task_id, ...]} from the real CLI, run with the flow's args."""
    script = repo_root / ".aitask-scripts" / "aitask_work_report_gather.sh"
    result = subprocess.run(
        [str(script), "--columns", cols_csv, "--tasks", tasks_csv],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(f"gatherer exited {result.returncode}\n{result.stderr}",
              file=sys.stderr)
        sys.exit(1)

    errors = [line for line in result.stdout.splitlines()
              if line.startswith("ERROR:")]
    if errors:
        print("gatherer rejected board-composed args:\n" + "\n".join(errors),
              file=sys.stderr)
        sys.exit(1)

    found = {}
    for line in result.stdout.splitlines():
        if not line.startswith("TASK:"):
            continue
        fields = line[len("TASK:"):].split("|", TASK_FIELDS - 1)
        found.setdefault(fields[0], []).append(fields[1])
    return found


def main(argv):
    if len(argv) != 2:
        print("usage: work_report_flow_equiv.py <repo_root>", file=sys.stderr)
        return 2
    repo_root = Path(argv[1]).resolve()

    col_ids, expected = board_flow_args(repo_root)
    if not any(expected.values()):
        print("fixture tree produced no board tasks — oracle is vacuous",
              file=sys.stderr)
        return 1
    cols_csv = ",".join(col_ids)
    tasks_csv = ",".join(tid for cid in col_ids for tid in expected[cid])

    actual = gatherer_columns(repo_root, cols_csv, tasks_csv)

    mismatches = [
        f"  column {cid!r}:\n    board flow: {expected[cid]}\n"
        f"    gatherer:   {actual.get(cid, [])}"
        for cid in col_ids
        if expected[cid] != actual.get(cid, [])
    ]
    if mismatches:
        print("board flow / gatherer disagree:", file=sys.stderr)
        print("\n".join(mismatches), file=sys.stderr)
        return 1

    print("FLOW_EQUIV_OK")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
