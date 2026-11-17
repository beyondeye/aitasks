#!/usr/bin/env bash
# tests/lib/run_tmpdir.sh — one run-level TMPDIR per test file, so everything the
# run writes through $TMPDIR lands in a directory its cleanup removes (t2302).
#
# Why. Producers the tests cannot see write into $TMPDIR, and on a plain
# `bash tests/test_x.sh` run that means /tmp:
#   - stale_lock.sh's ait_lock_dir creates a per-user, PER-REPO-ROOT lock base,
#     ${TMPDIR:-/tmp}/aitask-locks-<uid>-<cksum(root)>. Each fixture repo has a
#     random path, so each run adds one directory per fixture repo. A suite that
#     runs the REAL .aitask-scripts/ takes locks in the live repo's namespace,
#     the one real `ait` commands use.
#   - helpers that mktemp a log for the caller (aitask_run_project_command.sh,
#     aitask_resource_admission.sh) or strand one on a die path
#     (task_git_commit_scoped's ait_commit_scoped_err.*).
#   - Python fixtures (tempfile.mkdtemp) and bare `mktemp` calls in the tests.
# Pointing TMPDIR at one root per run catches all of them at once, and keeps
# the lock base's per-repo namespacing intact (unlike a shared AITASKS_LOCK_DIR).
#
# Usage, in the suite's TOP-LEVEL shell (never inside `$( )`), after
# enter_scratch_cwd (so the shared ait-test-cwd-<uid> stays where it is) and
# before the suite's first producer:
#
#   . "$PROJECT_DIR/tests/lib/run_tmpdir.sh"
#   run_tmpdir_init test_foo                 # standalone root under $TMPDIR
#   run_tmpdir_init test_foo "$TMP"          # or: under a root the suite owns
#
# OWNERSHIP. This file installs NO trap: most suites install their own
# `trap … EXIT` later and would silently replace it. The caller gives the root
# an owner that also runs on early exits — a footer loop alone is never enough:
#   - with <parent>: nothing to do, the parent's cleanup removes the root;
#   - the suite has an EXIT trap: call run_tmpdir_cleanup from it (or add
#     "$RUN_TMPDIR" to the array it drains);
#   - the suite has none (check the libraries it sources too):
#     `trap run_tmpdir_cleanup EXIT`.
#
# AITASKS_LOCK_DIR. ait_lock_dir gives that override precedence over TMPDIR, so
# an inherited value would put this run's locks in the caller's shared lock
# directory, outside the root. run_tmpdir_init therefore unsets it. A case that
# wants an override sets it AFTER this call.
#
# bash-3.2-safe.

[[ -n "${_AIT_RUN_TMPDIR_LOADED:-}" ]] && return 0
_AIT_RUN_TMPDIR_LOADED=1

RUN_TMPDIR=""

# run_tmpdir_init <label> [<parent>] — create <parent or $TMPDIR>/<label>_run_XXXXXX,
# set RUN_TMPDIR to its physical path, export TMPDIR to it, and unset an
# inherited AITASKS_LOCK_DIR. Exits the suite on failure (a suite with no root
# would write straight into /tmp again).
run_tmpdir_init() {
    local label="${1:-}" parent="${2:-}" root
    if [[ ! "$label" =~ ^[A-Za-z0-9_]+$ ]]; then
        echo "FAIL: run_tmpdir_init: invalid label '$label' (want [A-Za-z0-9_]+)" >&2
        exit 1
    fi
    [[ -n "$parent" ]] || parent="${TMPDIR:-/tmp}"
    parent="${parent%/}"
    [[ -n "$parent" ]] || parent="/tmp"
    if ! root="$(mktemp -d "$parent/${label}_run_XXXXXX")"; then
        echo "FAIL: run_tmpdir_init could not create a run TMPDIR under '$parent'" >&2
        exit 1
    fi
    # Physical path, so `pwd -P` comparisons (and macOS /var -> /private/var)
    # still see paths as being under the root.
    if ! RUN_TMPDIR="$(cd "$root" && pwd -P)"; then
        echo "FAIL: run_tmpdir_init could not resolve $root" >&2
        rm -rf -- "$root"
        exit 1
    fi
    export TMPDIR="$RUN_TMPDIR"
    unset AITASKS_LOCK_DIR
    return 0
}

# run_tmpdir_cleanup — remove the run root. Idempotent; never fails. Some
# fixtures make files read-only, so write permission is restored first.
run_tmpdir_cleanup() {
    [[ -n "${RUN_TMPDIR:-}" && -d "$RUN_TMPDIR" ]] || return 0
    chmod -R u+w "$RUN_TMPDIR" 2>/dev/null || true
    rm -rf -- "$RUN_TMPDIR" 2>/dev/null || true
    return 0
}
