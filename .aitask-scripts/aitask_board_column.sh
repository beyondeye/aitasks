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
#   columns-of     --root R [--task-dir D]
#                       -> COLOF:<col_id>|<task path relative to R>  (one per
#                          task file, parents AND children), then a terminal
#                          SCAN_OK line
#
# `columns-of` is the whole-tree amortization behind `ait ls --boardcol`: one
# call resolves every task's column through board_columns.column_of, so no
# caller re-derives that rule. Its SCAN_OK trailer is REQUIRED as the exact
# final line — without it an empty result cannot be told from a scan that died
# partway, and a consumer that assumed the former would fail open.
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
# This wrapper writes NO FILE itself: it is a thin CLI over lib/board_columns.py,
# which owns every file write via lib/atomic_write.py. So it deliberately does
# not source lib/atomic_write.sh and is out of scope for t1396's shell
# truncate-then-write sweep. Keep it that way — adding a shell-side write here
# would make it a t1396 surface.
#
# It DOES commit after a successful `create` (t1677). board_config.json has no
# derivable task id, so `ait sync` refuses to attribute it and nothing else
# committed it — a column created from minimonitor left a dirty file that blocks
# task-data sync until a human clears it. The commit is the caller's user
# gesture made durable, path-scoped through aitask_metadata_commit.sh, and it
# runs inside --root so a cross-repo create commits in the right repository.
# A failed commit is reported on STDERR (stdout is the machine protocol) and
# does not fail the create: the column exists either way.
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

# Every verb but `create` is read-only or writes task files (which sync CAN
# attribute), so they keep the exec: no post-processing, and `columns-of`
# streams its whole-tree scan straight through.
if [[ "${1:-}" != "create" ]]; then
    exec "$PYTHON" "$SCRIPT_DIR/lib/board_columns.py" "$@"
fi

# --- create: run, relay, then commit the config it wrote ---------------------

# Re-read only what the commit needs. board_columns.py remains the authority on
# argument validation — a bad value fails there, and this loop just mirrors the
# two options that decide WHERE the config lives.
_root="."
_task_dir="${TASK_DIR:-aitasks}"
_args=("$@")
_i=0
while (( _i < ${#_args[@]} )); do
    case "${_args[$_i]}" in
        --root)     _i=$((_i + 1)); _root="${_args[$_i]:-.}" ;;
        --task-dir) _i=$((_i + 1)); _task_dir="${_args[$_i]:-$_task_dir}" ;;
    esac
    _i=$((_i + 1))
done

_out=""
_rc=0
_out="$("$PYTHON" "$SCRIPT_DIR/lib/board_columns.py" "$@")" || _rc=$?
[[ -n "$_out" ]] && printf '%s\n' "$_out"

# Only a real creation has a config change to own.
if [[ $_rc -ne 0 ]] || [[ "$_out" != CREATED:* ]]; then
    exit "$_rc"
fi

# `cd` into --root, not the invoking cwd: task_git resolves .aitask-data
# relative to $PWD, so a cross-repo create must commit in the target repo.
_config="${_task_dir}/metadata/board_config.json"
_crc=0
( cd "$_root" && "$SCRIPT_DIR/aitask_metadata_commit.sh" "$_config" ) >/dev/null 2>&1 || _crc=$?
# rc 2 is "nothing to commit" — a legitimate no-op (e.g. legacy layouts where
# the file is not tracked), not a failure worth alarming the user about.
if [[ $_crc -eq 1 ]]; then
    printf 'WARN:commit_failed:%s\n' "$_config" >&2
fi

exit "$_rc"
