#!/usr/bin/env bash
# scratch_cwd.sh - start a bash test from an empty, read-only directory (t1826).
#
# Usage, right after PROJECT_DIR is derived and BEFORE any `ORIG_DIR="$(pwd)"`
# capture (a capture taken earlier would point back at the invoking directory):
#
#   . "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
#   enter_scratch_cwd
#
# Why. t1815 found fixture task files and commits in the live repository: a test
# ran `cd "$fixture"` with no guard, the cd failed, and the relative writes and
# `git commit` that followed ran in the invoking directory -- the repo root. Two
# layers keep that from recurring:
#
#   1. Every cd/pushd in tests/ is exit-guarded (`cd "$X" || exit 1`) or confined
#      to a subshell `&&` chain. tests/lib/cd_guard_scan.py defines the rule and
#      tests/test_cd_guard_lint.sh enforces it. This is the invariant: it holds
#      wherever the cwd happens to be, including after a file deliberately
#      returns to "$PROJECT_DIR".
#   2. This helper. It covers what the lint cannot see: relative writes a file
#      makes before its first cd, and cd's the scanner misses (eval, computed
#      command names). Invoking directory is never the fallback.
#
# The directory is per-user, empty and mode 0555, and it is never deleted. A
# stray relative write fails with EACCES instead of landing somewhere. No EXIT
# trap is involved, which matters because most adopting files install their own
# `trap ... EXIT` and would silently replace one set here. Concurrent runs share
# it safely (nothing can write into it), and `find .` from it is instant.
#
# Root ignores 0555, so under root a stray write CAN land in the directory --
# never in the repository. Retention stays bounded: it is always the same single
# path, and the next run refuses to start while it is non-empty, naming it.
#
# mktemp and TMPDIR can place the directory inside a repository, and an exported
# GIT_DIR makes every directory look like one, so "outside any repository" is
# checked with git rather than assumed.

enter_scratch_cwd() {
    command -v git >/dev/null 2>&1 || { echo "FAIL: git not found"; exit 1; }
    local base dir
    base="${TMPDIR:-/tmp}"
    base="${base%/}"
    dir="$base/ait-test-cwd-$(id -u)"
    if [[ ! -d "$dir" ]]; then
        mkdir -m 0555 "$dir" 2>/dev/null || [[ -d "$dir" ]] \
            || { echo "FAIL: cannot create scratch cwd '$dir'"; exit 1; }
    fi
    [[ -O "$dir" && ! -L "$dir" ]] \
        || { echo "FAIL: scratch cwd '$dir' is not a directory owned by uid $(id -u)"; exit 1; }
    chmod 0555 "$dir" || { echo "FAIL: cannot make scratch cwd '$dir' read-only"; exit 1; }
    if [[ -n "$(ls -A "$dir")" ]]; then
        echo "FAIL: scratch cwd '$dir' is not empty -- a test wrote into it" \
             "(possible under root, which ignores 0555); inspect it, then remove it"
        exit 1
    fi
    if git -C "$dir" rev-parse --git-dir >/dev/null 2>&1; then
        echo "FAIL: scratch cwd '$dir' resolves to a git repository" \
             "(TMPDIR='${TMPDIR:-}' GIT_DIR='${GIT_DIR:-}'); refusing to run fixtures there"
        exit 1
    fi
    cd "$dir" || { echo "FAIL: cannot enter scratch cwd '$dir'"; exit 1; }
}
