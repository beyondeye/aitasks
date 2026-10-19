#!/usr/bin/env bash
# tests/lib/fixture_root.sh — one registered temp root per suite, so fixture
# factories can be called as `$(factory)` without leaking (t2055).
#
# Source AFTER tests/lib/asserts.sh (assert_fixture_registered records through
# its counters):
#     . "$PROJECT_DIR/tests/lib/asserts.sh"
#     . "$PROJECT_DIR/tests/lib/fixture_root.sh"
#
# Why. A factory that does `CLEANUP_DIRS+=("$d")` and is called as
# `d="$(factory)"` registers the dir inside the command-substitution subshell.
# The append dies with the subshell, the suite's cleanup never sees the dir, and
# the suite leaks while reporting green (t2031, t2055). Instead, the suite
# creates one root in its top-level shell and every factory creates its dir
# under it:
#
#     CLEANUP_DIRS=()
#     new_fixture() {
#         local tmp
#         tmp="$(fixture_mktemp_d test_foo)" || return 1
#         ...
#         echo "$tmp"
#     }
#     ...prerequisite checks, SKIP exits...
#     fixture_root_init                    # top level, just before the first fixture
#     assert_fixture_registered "new_fixture dirs land under the registered FIXTURE_ROOT" \
#         "$(new_fixture)"
#
# The suite's own cleanup — an EXIT trap or a footer loop over the array —
# removes the root, and every fixture with it, whatever shell created them.
#
# Call fixture_root_init AFTER any successful-skip exit (`exit 0` on a missing
# prerequisite): a suite that cleans up only in its footer would otherwise leak
# the root on that path.
#
# bash-3.2-safe (no declare -n, mapfile or declare -A).

# Idempotent: guard against double-sourcing.
[[ -n "${_AIT_FIXTURE_ROOT_LOADED:-}" ]] && return 0
_AIT_FIXTURE_ROOT_LOADED=1

# fixture_root_init [array_name] — create FIXTURE_ROOT and append it to the
# named cleanup array (default CLEANUP_DIRS) in the CALLING shell. Must run in
# the suite's top-level shell, never inside `$( )`. Exits the suite on failure,
# like assert_counters_init: a suite with no root cannot clean up.
fixture_root_init() {
    local arr="${1:-CLEANUP_DIRS}" root
    if [[ ! "$arr" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "FAIL: fixture_root_init: invalid array name '$arr'" >&2
        exit 1
    fi
    if ! root="$(mktemp -d "${TMPDIR:-/tmp}/ait_fixture_root_XXXXXX")"; then
        echo "FAIL: fixture_root_init could not create a temp root" >&2
        exit 1
    fi
    # Physical path, so a factory's own `pwd -P` (and macOS /var ->
    # /private/var) still compares as "under the root".
    if ! FIXTURE_ROOT="$(cd "$root" && pwd -P)"; then
        echo "FAIL: fixture_root_init could not resolve $root" >&2
        rm -rf "$root"
        exit 1
    fi
    FIXTURE_ROOT_ARRAY="$arr"
    eval "$arr+=(\"\$FIXTURE_ROOT\")"
    return 0
}

# fixture_mktemp_d <prefix> — print a fresh dir under FIXTURE_ROOT. Fails closed
# (rc 1, empty stdout) when the root is missing: falling back to $TMPDIR would
# silently bring the leak back.
fixture_mktemp_d() {
    local prefix="$1"
    if [[ -z "${FIXTURE_ROOT:-}" || ! -d "$FIXTURE_ROOT" ]]; then
        echo "fixture_mktemp_d: FIXTURE_ROOT is not set up — call fixture_root_init in the suite's top-level shell first" >&2
        return 1
    fi
    mktemp -d "$FIXTURE_ROOT/${prefix}_XXXXXX"
}

# assert_fixture_registered <desc> <dir> — one assertion: <dir> exists, lies
# under FIXTURE_ROOT, and FIXTURE_ROOT is an element of its cleanup array. The
# emptiness check comes first: an empty <dir> would otherwise slip through a
# substring-style membership test (t2031).
assert_fixture_registered() {
    # shellcheck disable=SC2034  # d is the loop variable inside the eval below
    local desc="$1" dir="$2" state="registered" found=0 d arr
    if [[ -z "$dir" ]]; then
        state="empty fixture path"
    elif [[ ! -d "$dir" ]]; then
        state="not a directory: $dir"
    elif [[ -z "${FIXTURE_ROOT:-}" ]]; then
        state="FIXTURE_ROOT unset (fixture_root_init not called)"
    elif [[ "$dir" != "$FIXTURE_ROOT"/* ]]; then
        state="outside FIXTURE_ROOT ($FIXTURE_ROOT): $dir"
    else
        arr="${FIXTURE_ROOT_ARRAY:-CLEANUP_DIRS}"
        # The loop body is an `if`, never `[[ … ]] && found=1`: the loop's status
        # is its last command's, so a root followed by any other entry would make
        # the eval return 1 and kill a `set -e` suite before assert_eq ran.
        if [[ "$arr" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
            eval 'for d in ${'"$arr"'[@]+"${'"$arr"'[@]}"}; do if [[ "$d" == "$FIXTURE_ROOT" ]]; then found=1; fi; done'
        fi
        [[ "$found" -eq 1 ]] || state="FIXTURE_ROOT not in $arr"
    fi
    assert_eq "$desc" "registered" "$state"
}
