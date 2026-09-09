#!/usr/bin/env bash
# test_sync_rebase_gate.sh - the tree-state rebase gate as an explicit truth
# table (t1725_3, risk mitigation `rebase_gate_truth_table`).
#
# Run: bash tests/test_sync_rebase_gate.sh
#
# WHY A TABLE
#
# The gate used to be "any protected file AND remote_ahead > 0". Replacing it
# with a five-way rule is the kind of change whose cells are easy to get right
# individually and wrong as a set: while planning this task the specification
# was written twice, and BOTH drafts would have broken an existing pin — once by
# deferring a behind-only branch that can simply fast-forward, once by deferring
# a push that needs no clean tree at all. Enumerating the cells is what turns
# the gate from an emergent property into a stated one.
#
# THE TABLE IS DRIVEN END-TO-END, through `run_sync` on the real fixture, not by
# sourcing the script: aitask_sync.sh calls `main` on its last line, so sourcing
# it would run a sync, and adding a library-only guard to a production script
# purely for a test is the wrong trade.
#
# Each row states the four inputs and the expected verdict:
#
#   tree_state    tracked | untracked   (the protected file's porcelain state)
#   local_ahead   0 | >0                (do we have commits to replay?)
#   remote_ahead  0 | >0                (is there anything to rebase onto?)
#   incoming      no | yes              (does an incoming commit touch our path?)
#
# `unknown` is not a fixture-reachable state — it is set defensively when the
# incoming set cannot be read — so it is covered by the parser/unit level and by
# the fail-closed branch in main(), not here.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# --- Fixture builders -----------------------------------------------------

# Advance origin/aitask-data with a commit touching <path> (created if absent).
advance_remote_touching() {
    local tmpdir="$1" path="$2" content="${3:-from pc2}"
    rm -rf "$tmpdir/pc2"
    git clone -q --branch aitask-data "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2"
        git config user.email pc2@test.com
        git config user.name PC2
        git config commit.gpgsign false
        # aiplans/ holds no committed file in the fixture, so git never tracked
        # the directory and a clone does not have it.
        mkdir -p "$(dirname "$path")"
        printf '%s\n' "$content" >> "$path"
        git add -A && git commit -q -m "pc2: touch $path"
        git push -q origin aitask-data 2>/dev/null
    ) >/dev/null 2>&1
    (cd "$tmpdir/local" && git -C .aitask-data fetch -q origin 2>/dev/null)
}

# gate_case <label> <tree_state> <local_ahead> <remote_ahead> <incoming> <expect>
#
# <expect> is `blocked` or `open`. Builds a fixture with exactly those inputs, a
# live lock on t10 so the file is protected, and asserts the verdict.
#
# PROTECTED_PATH is t10's; local_ahead>0 is produced by dirtying UNLOCKED t20,
# whose group commits and therefore leaves a local commit to replay.
gate_case() {
    local label="$1" tree_state="$2" local_ahead="$3" remote_ahead="$4"
    local incoming="$5" expect="$6" path="${7:-}"
    local t; t="$(setup_repo)"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"

    local ppath
    if [[ "$tree_state" == "tracked" ]]; then
        ppath="${path:-aitasks/t10_alpha.md}"
        (cd "$t/local" && printf 'edit10\n' >> ".aitask-data/$ppath")
    else
        ppath="${path:-aiplans/p10_x.md}"
        (cd "$t/local" && mkdir -p "$(dirname ".aitask-data/$ppath")" \
                       && printf 'draft\n' > ".aitask-data/$ppath")
    fi

    [[ "$local_ahead" == "0" ]] || \
        (cd "$t/local" && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)

    if [[ "$remote_ahead" != "0" ]]; then
        if [[ "$incoming" == "yes" ]]; then
            advance_remote_touching "$t" "$ppath" theirs
        else
            advance_remote_touching "$t" aitasks/t30_gamma.md
        fi
    fi

    local out; out="$(run_sync "$t")"
    if [[ "$expect" == "blocked" ]]; then
        assert_contains "$label -> blocked" "DEFERRED:protected_dirty" "$out"
    else
        assert_not_contains "$label -> open" "DEFERRED" "$out"
    fi
    # In EVERY cell the protected file's own bytes must survive untouched. A
    # gate that let a rebase through would show up here even if the verdict
    # string happened to match.
    assert_file_exists "$label: the protected file still exists" \
        "$t/local/.aitask-data/$ppath"
}

echo "=== rebase gate truth table (t1725_3) ==="
echo ""

# --- remote_ahead == 0: nothing to rebase onto, so nothing can block ------
# Rule 1, and the clause a draft of this task omitted. Without it the tracked +
# local_ahead>0 row below would defer a push that needs no clean tree at all,
# breaking the deliberate asymmetry pinned since t1599_3.
echo "--- remote_ahead == 0 (rule 1: never blocked) ---"
gate_case "tracked   / local 0  / remote 0 / not incoming" tracked   0  0 no  open
gate_case "tracked   / local >0 / remote 0 / not incoming" tracked   1  0 no  open
gate_case "untracked / local 0  / remote 0 / not incoming" untracked 0  0 no  open
gate_case "untracked / local >0 / remote 0 / not incoming" untracked 1  0 no  open

# --- tracked, remote ahead ------------------------------------------------
# Rule 3: replaying local commits needs a clean tree. With nothing to replay,
# main fast-forwards instead (t1696's case).
echo "--- tracked, remote ahead (rules 3 and 5) ---"
gate_case "tracked   / local >0 / remote >0 / not incoming" tracked   1  1 no  blocked
gate_case "tracked   / local 0  / remote >0 / not incoming" tracked   0  1 no  open
gate_case "tracked   / local >0 / remote >0 / IS incoming"  tracked   1  1 yes blocked
gate_case "tracked   / local 0  / remote >0 / IS incoming"  tracked   0  1 yes blocked

# --- untracked, remote ahead ---------------------------------------------
# Rule 4 is the ONLY thing that blocks an untracked path: git rebase ignores one
# entirely unless an incoming commit creates it.
echo "--- untracked, remote ahead (rules 4 and 5) ---"
gate_case "untracked / local >0 / remote >0 / not incoming" untracked 1  1 no  open
gate_case "untracked / local 0  / remote >0 / not incoming" untracked 0  1 no  open
gate_case "untracked / local >0 / remote >0 / IS incoming"  untracked 1  1 yes blocked
gate_case "untracked / local 0  / remote >0 / IS incoming"  untracked 0  1 yes blocked

# --- the same incoming cells, with a HOSTILE path -------------------------
# A git path may contain any byte but NUL. The membership test compares against
# paths read from `status --porcelain -z` (raw, unquoted), so building the
# incoming set with a line-oriented `diff --name-only` fails two ways at once —
# a newline path is split into two names that match nothing, and git C-quotes
# unusual paths by default so neither form compares equal. BOTH failures are
# fail-OPEN: the gate concludes "not incoming" and lets the checkout proceed
# over the very file it is protecting.
echo "--- hostile paths through the incoming membership test ---"
NL_PATH="$(printf 'aiplans/p10_a\nb.md')"
gate_case "untracked / newline path / IS incoming"     untracked 0 1 yes blocked "$NL_PATH"
gate_case "untracked / newline path / not incoming"    untracked 0 1 no  open    "$NL_PATH"
gate_case "untracked / quote+backslash / IS incoming"  untracked 0 1 yes blocked 'aiplans/p10_q"\.md'

echo ""
echo "==================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
    exit 0
else
    echo "SOME TESTS FAILED"
    exit 1
fi
