#!/usr/bin/env bash
# aitask_model_stats_strip.sh - strip the legacy stats counters from a task-data
# model registry and commit the result path-scoped (t1912_5).
#
# Internal: invoked only by lib/model_stats_migrate.py in NO-REMOTE mode, where
# the migration source is the committed task-data HEAD and the strip has to land
# through the worktree. In remote mode the migration builds and pushes its strip
# with plumbing and never runs this.
#
# Usage:
#   aitask_model_stats_strip.sh --path <repo-rel registry path> \
#       --expect-blob <sha> --expect-stripped-blob <sha> --message-file <file> \
#       [--scratch-dir <existing dir>]
#
# Steps:
#   1. ait_cas_rewrite the registry through lib/model_stats_strip.jq. The
#      snapshot must hash to --expect-blob (the committed HEAD blob the caller
#      pinned) or to --expect-stripped-blob. The second is this migration's own
#      interrupted state: a strip killed after the rewrite and before its commit.
#      The retry resumes it, because stripping stripped bytes reproduces them.
#      Anything else is someone's edit: deferred, file untouched.
#   2. aitask_task_commit.sh -m <message> <path> (path-scoped; the message carries
#      the Stats-Migration-* trailers the caller identifies the commit by).
#   3. A reported commit failure restores the pre-rewrite bytes, CAS-guarded
#      (only while the file still holds exactly the bytes this run rendered,
#      captured before the swap; any other content is left alone). A stripped but
#      uncommitted file would otherwise under-report and read "dirty" on every
#      later run.
#
# Output (last stdout line; prints NO commit sha: the caller resolves the commit
# by its unique Stats-Migration-Id, never by sampling HEAD):
#   STRIPPED                     committed
#   STRIP_DEFERRED:<reason>      nothing committed (dirty, contended, missing,
#                                commit_failed:<detail>, ...)
#   STRIP_ERROR:<reason>         usage / environment error
# Exit: 0 STRIPPED, 2 STRIP_DEFERRED, 1 STRIP_ERROR.
#
# Test seam: AIT_STATS_STRIP_AFTER_REWRITE_HOOK names a script that runs between
# the rewrite and the commit, with AIT_STATS_STRIP_PID exported (the termination
# test SIGKILLs this process from it). Its stdout goes to stderr.
#
# Scratch: the work dir (under --scratch-dir, else $TMPDIR) is removed by one
# EXIT trap on every exit, a fatal TERM/INT/HUP included (bash runs EXIT on
# those). SIGKILL runs nothing, so the caller (lib/model_stats_migrate.py) passes
# a --scratch-dir it owns and removes afterwards. It is a flag rather than a
# TMPDIR override on purpose: ait_lock_dir derives the framework's shared mutex
# base from $TMPDIR, and a private TMPDIR would give this process tree a private
# lock namespace.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/terminal_compat.sh
source "$SCRIPT_DIR/lib/terminal_compat.sh"
# shellcheck source=lib/task_utils.sh
source "$SCRIPT_DIR/lib/task_utils.sh"
# shellcheck source=lib/registry_cas.sh
source "$SCRIPT_DIR/lib/registry_cas.sh"

STRIP_JQ="$SCRIPT_DIR/lib/model_stats_strip.jq"
REG_PATH=""
EXPECT_BLOB=""
EXPECT_STRIPPED=""
MSG_FILE=""
SCRATCH_PARENT=""
STRIP_REASON=""
WORK_DIR=""

strip_error() {
    printf 'STRIP_ERROR:%s\n' "$1"
    exit 1
}

strip_deferred() {
    printf 'STRIP_DEFERRED:%s\n' "$1"
    exit 2
}

# EXIT handler: errexit is live inside it, so it must never fail.
# shellcheck disable=SC2329  # invoked indirectly via the EXIT trap
_strip_cleanup() {
    if [[ -n "$WORK_DIR" ]]; then rm -rf -- "$WORK_DIR" 2>/dev/null || true; fi
    return 0
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --path) REG_PATH="${2:-}"; shift 2 ;;
        --expect-blob) EXPECT_BLOB="${2:-}"; shift 2 ;;
        --expect-stripped-blob) EXPECT_STRIPPED="${2:-}"; shift 2 ;;
        --message-file) MSG_FILE="${2:-}"; shift 2 ;;
        --scratch-dir) SCRATCH_PARENT="${2:-}"; shift 2 ;;
        -h|--help) sed -n '2,48p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; exit 0 ;;
        *) strip_error "usage:unknown argument $1" ;;
    esac
done

[[ -n "$REG_PATH" && -n "$EXPECT_BLOB" && -n "$EXPECT_STRIPPED" && -n "$MSG_FILE" ]] \
    || strip_error "usage:--path, --expect-blob, --expect-stripped-blob and --message-file are required"
# A repo-relative registry path under <TASK_DIR>/metadata, and nothing else:
# this script rewrites and commits exactly that file.
if [[ ! "$REG_PATH" =~ ^[A-Za-z0-9._-]+/metadata/models_[a-z][a-z0-9]*\.json$ ]] \
        || [[ "$REG_PATH" == ../* || "$REG_PATH" == ./* ]]; then
    strip_error "usage:not a registry path: $REG_PATH"
fi
[[ "$REG_PATH" == "${TASK_DIR:-aitasks}/"* ]] || strip_error "usage:path outside ${TASK_DIR:-aitasks}/"
[[ -f "$MSG_FILE" ]] || strip_error "usage:message file not found"
[[ -z "$SCRATCH_PARENT" || -d "$SCRATCH_PARENT" ]] || strip_error "usage:scratch dir not found"
command -v jq >/dev/null 2>&1 || strip_error "jq_missing"

_ait_detect_data_worktree
DEST="$_AIT_DATA_WORKTREE/$REG_PATH"
[[ -f "$DEST" ]] || strip_deferred "missing"

# Armed before the dir exists (WORK_DIR is "" until then, so no window).
# lib/archive_utils.sh claims the single EXIT trap at source time; the re-arm
# chains its sweep around ours instead of dropping it (aitask_task_commit.sh).
trap _strip_cleanup EXIT
ait_archive_rearm_exit_trap
WORK_DIR="$(mktemp -d "${SCRATCH_PARENT:-${TMPDIR:-/tmp}}/ait_stats_strip.XXXXXX")" || strip_error "mktemp_failed"
ORIG_COPY="$WORK_DIR/original"
WROTE_COPY="$WORK_DIR/stripped"

# Renderer for ait_cas_rewrite: must `return`, never `exit` (registry_cas.sh).
# shellcheck disable=SC2329  # invoked indirectly via ait_cas_rewrite
_strip_render() {
    local snap="$1" sha
    if [[ -z "$snap" ]]; then
        STRIP_REASON="missing"
        return 1
    fi
    sha="$(git hash-object --no-filters -- "$snap")" || { STRIP_REASON="hash_failed"; return 1; }
    if [[ "$sha" != "$EXPECT_BLOB" && "$sha" != "$EXPECT_STRIPPED" ]]; then
        STRIP_REASON="dirty"
        return 1
    fi
    cp "$snap" "$ORIG_COPY" || { STRIP_REASON="copy_failed"; return 1; }
    # Capture the exact bytes this run publishes BEFORE the swap: the rollback
    # compares the live file against this capture, never against a sample of
    # the live file taken after the swap (a competing edit landing in between
    # would be mistaken for ours and then "restored" away).
    jq -f "$STRIP_JQ" "$snap" > "$WROTE_COPY" || { STRIP_REASON="jq_failed"; return 1; }
    if [[ "$(git hash-object --no-filters -- "$WROTE_COPY")" != "$EXPECT_STRIPPED" ]]; then
        STRIP_REASON="unexpected_render"
        return 1
    fi
    cat "$WROTE_COPY"
}

# Rollback renderer: the original bytes, only while the file still holds the
# bytes this run wrote — a later edit by anyone else is never overwritten.
# shellcheck disable=SC2329  # invoked indirectly via ait_cas_rewrite
_restore_render() {
    local snap="$1"
    if [[ -z "$snap" ]] || ! cmp -s "$snap" "$WROTE_COPY"; then
        STRIP_REASON="changed_since_strip"
        return 1
    fi
    cat "$ORIG_COPY"
}

cas_rc=0
ait_cas_rewrite "$DEST" 3 _strip_render || cas_rc=$?
case "$cas_rc" in
    0) ;;
    2) strip_deferred "contended" ;;
    *) strip_deferred "${STRIP_REASON:-render_failed}" ;;
esac

if [[ -n "${AIT_STATS_STRIP_AFTER_REWRITE_HOOK:-}" ]]; then
    AIT_STATS_STRIP_PID=$$ bash "$AIT_STATS_STRIP_AFTER_REWRITE_HOOK" >&2 || true
fi

commit_rc=0
commit_out="$("$SCRIPT_DIR/aitask_task_commit.sh" -m "$(cat "$MSG_FILE")" "$REG_PATH" 2>&1)" \
    || commit_rc=$?
if [[ "$commit_rc" -eq 0 && "$commit_out" == *COMMITTED:* ]]; then
    echo "STRIPPED"
    exit 0
fi

detail="$(printf '%s' "$commit_out" | tr '\n|' '  ' | cut -c1-160)"
restore_rc=0
STRIP_REASON=""
ait_cas_rewrite "$DEST" 3 _restore_render || restore_rc=$?
if [[ "$restore_rc" -ne 0 ]]; then
    echo "aitask_model_stats_strip.sh: commit failed and the registry was NOT restored (${STRIP_REASON:-rc $restore_rc}): $DEST" >&2
fi
strip_deferred "commit_failed:${detail:-exit $commit_rc}"
