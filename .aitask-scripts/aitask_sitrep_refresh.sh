#!/usr/bin/env bash
# aitask_sitrep_refresh.sh - Deterministic refresh of the sitrep store's Part 1
# (t2175_3). Re-checks every open/unknown item it knows how to verify against
# the real state and writes the results through the one writer
# (aitask_sitrep_todo.sh `set-state --batch`, CAS on the observed rev).
#
# Usage: aitask_sitrep_refresh.sh [--root <path>] [--budget <seconds>] [--dry-run]
#
#   --root     any path inside the repository (default: cwd). A linked
#              `aiwork/<task>` worktree maps to the main worktree: one store per
#              repository (lib/sitrep_harvest.py canonical_root).
#   --budget   the WHOLE run's deadline, checks plus write (default 60, or
#              AITASK_SITREP_REFRESH_BUDGET). A caller's hard timeout must be at
#              least budget + 15 s.
#   --dry-run  compute and report, write nothing.
#
# What is checked, the evidence rules ("done" only on positive evidence, never
# re-checked once done), the no-fetch push rule, the deadline/worker design and
# the ordering rule are documented in lib/sitrep_refresh.py's module docstring.
#
# Output (free text always LAST):
#   REFRESH_ITEM:c<N>|<kind>|<old>-><new>|applied|stale|kept|not_found|dry_run|<outcome>
#   REFRESH_WARN:budget_exhausted|<n> not reached
#   REFRESHED:checked=<n>|changed=<c>|stale=<s>|kept=<k>|unknown=<u>   final, exit 0
#   REFRESH_NONE:no_store|no_targets                                 final, exit 0
#   REFRESH_FAILED:<reason>                                          final, exit 1
#     reasons: deadline, lock_busy, store_unusable[:<detail>], root:<why>,
#     worker:<rc>, worker_protocol:<detail>, writer_timeout, writer:<detail>,
#     no_python
# `stale` = the item or its context entry changed after the snapshot -- an
# edit, a dismissal, another refresh -- so the line was not applied (re-read
# next run, never retried); `kept` = the line named a dismissed item at its
# current rev, which the writer never touches. `changed`
# counts lines whose state or outcome differ (the checked_at stamp alone is not
# a change). Nothing is ever created: a root without an established store is
# REFRESH_NONE:no_store.
#
# Exit codes: 0 success (incl. NONE), 1 failed (nothing written), 2 usage or a
# `..` root (refused before any filesystem access).
#
# Callers: the monitor's trailing maintenance tick
# (monitor/monitor_shared.py `_maybe_refresh_sitrep`), the sitrep skill
# (t2175_4, which owes the code-agent permission touchpoints when its SKILL.md
# first calls this), and on-demand use. Deliberately not an `ait` verb.
#
# `task_utils.sh` is NOT sourced (it claims the EXIT trap at source time; the
# same reason as aitask_sitrep_todo.sh).
#
# TEST SEAMS (test-only). AITASK_SITREP_REFRESH_PAUSE_FIFO: before the write the
# run writes `refresh:before_write` to `<fifo>.reached` and blocks reading one
# line from the fifo (the write then gets a fresh reserve). AITASK_SITREP_REFRESH_ARTIFACT_SH:
# the artifact CLI used to fetch trails. AITASK_SITREP_REFRESH_BATCH_LOG: a file
# receiving the exact batch sent to the writer. AITASK_SITREP_NOW pins the
# checked_at stamp.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/python_resolve.sh
source "$SCRIPT_DIR/lib/python_resolve.sh"

CORE="$SCRIPT_DIR/lib/sitrep_refresh.py"

usage() {
    echo "Usage: aitask_sitrep_refresh.sh [--root <path>] [--budget <seconds>] [--dry-run]" >&2
    exit 2
}

err_usage() {
    printf 'Error: %s\n' "$1" >&2
    exit 2
}

root="."
budget=""
dry_run=()
while [[ $# -gt 0 ]]; do
    case "$1" in
        --root)
            [[ $# -ge 2 ]] || usage
            root="$2"; shift 2 ;;
        --budget)
            [[ $# -ge 2 ]] || usage
            [[ "$2" =~ ^[0-9]+([.][0-9]+)?$ ]] || err_usage "--budget must be a number of seconds"
            budget="$2"; shift 2 ;;
        --dry-run)
            dry_run=(--dry-run); shift ;;
        -h|--help)
            usage ;;
        *)
            err_usage "unknown argument '$1'" ;;
    esac
done

[[ -n "$root" ]] || err_usage "--root must not be empty"
case "/$root/" in
    */../*) err_usage "path '$root' contains a '..' segment" ;;
esac

PY="$(resolve_python)"
if [[ -z "$PY" ]]; then
    echo "REFRESH_FAILED:no_python"
    exit 1
fi

args=(run --root "$root" "${dry_run[@]}")
[[ -n "$budget" ]] && args+=(--budget "$budget")
exec "$PY" "$CORE" "${args[@]}"
