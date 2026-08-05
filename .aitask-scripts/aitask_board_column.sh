#!/usr/bin/env bash

# aitask_board_column.sh - Headless board-column reader/writer (t1377_1).
#
# Lists a project's board columns, reports which column a task sits in, and
# moves a parent task into a column with a correctly gap-computed `boardidx`.
# Exists so `ait minimonitor` (and any other headless caller) can do those
# things without importing the board TUI, which pulls in Textual at module
# scope and parses every task file just to construct a TaskManager.
#
#   list-columns   --root R [--task-dir D] [--include-unordered]
#                       -> COLUMN:<id>|<color>|<title>   (one per line)
#   current-column --root R [--task-dir D] --task N
#                       -> CURRENT:<task_id>|<col_id>
#   move           --root R [--task-dir D] --task N --column C
#                       -> MOVED:<filename>|<col>|<idx>
#   create         --root R [--task-dir D] --title T [--color C]
#                       -> CREATED:<col_id>|<color>|<title>
#
# Refusals print `ERROR:<reason>` and exit 1; a usage error exits 2. Reasons are
# stable machine tokens (unknown_column, malformed_task_id, ambiguous_task_id,
# not_a_parent_task, not_found, unsafe_task_dir, unsupported_layout, vanished,
# empty_title, invalid_color) so a caller branches on them rather than on prose.
#
# `create` omits --color to auto-assign the next unused palette colour; pass
# `--color ''` for a colourless column. A malformed colour is REFUSED rather than
# stored: it is a middle field (so a `|` would be silently stripped on emit) and
# it is interpolated into rich markup by the TUIs. Titles, by contrast, are kept
# verbatim — they are last precisely so a `|` survives.
#
# Titles may contain `|`, so the title is the LAST field — split on the first
# two separators only.
#
# This wrapper writes NOTHING itself: it is a thin CLI over lib/board_columns.py,
# which owns every file write via lib/atomic_write.py. So it deliberately does
# not source lib/atomic_write.sh and is out of scope for t1396's shell
# truncate-then-write sweep. Keep it that way — adding a shell-side write here
# would make it a t1396 surface.
#
# Deliberately NOT wired into the `ait` dispatcher (that surface is user-facing
# only) and deliberately carrying no code-agent allowlist entries: those apply
# to skill-invoked helpers, and this one is shelled out from a TUI. See
# aidocs/framework/aitasks_extension_points.md.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/aitask_path.sh
source "$SCRIPT_DIR/lib/aitask_path.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

PYTHON="$(require_ait_python)"

exec "$PYTHON" "$SCRIPT_DIR/lib/board_columns.py" "$@"
