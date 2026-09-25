#!/usr/bin/env bash
# test_change_surface.sh - Tests for per-task change-surface attribution (t1263).
#
# The failure this guards: the docs_updated gate used to gather its change
# surface with a raw `git diff --name-only HEAD`, which returns the ENTIRE dirty
# tree. On a shared checkout it therefore inferred doc obligations from other
# tasks' in-progress work.
#
# Covers:
#   - Two tasks dirty in ONE tree, interleaved in time: each task's own file is
#     attributed and the other's is not.
#   - The concurrent-after-claim case a baseline alone CANNOT assign (the second
#     half of the observed incident) lands in UNKNOWN, never TASK.
#   - Plan scope is EXACT-FILE-ONLY: a directory named in the plan does not
#     attribute the files beneath it.
#   - Pass A (tagged commits) is independent of the dirty scan: a committed file
#     left clean is still reported, and a committed file still dirty is reported
#     exactly once.
#   - Missing/foreign signals degrade to UNKNOWN (fail-safe), never to TASK.
#   - Plan text containing regex/shell metacharacters is inert.
#   - The exclude set does not drift from gate_ledger._DIGEST_EXCLUDES.
#   - aitask_pick_own.sh writes the baseline on a fresh claim only, and its
#     stdout contract is unchanged by the capture call.
#
# Run: bash tests/test_change_surface.sh
set -u
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0; FAIL=0; TOTAL=0
CS="$PROJECT_DIR/.aitask-scripts/aitask_change_surface.sh"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || echo python3)"

# ONE parent fixture root, created and registered HERE in the parent shell.
#
# Do NOT go back to a `CLEANUP_DIRS+=(…)` inside new_repo: every caller does
# `fx="$(new_repo)"`, so the append runs in a command-substitution SUBSHELL and
# is lost before the EXIT trap ever sees it. That leaked a repo per fixture per
# run (125 stale /tmp dirs were found in review). Nesting the fixtures under one
# parent means the trap has nothing to accumulate.
FIXTURE_ROOT="$(mktemp -d "${TMPDIR:-/tmp}/test_chgsurf_XXXXXX")"
cleanup() { [[ -n "${FIXTURE_ROOT:-}" ]] && rm -rf "$FIXTURE_ROOT"; }
trap cleanup EXIT

# new_repo -> path to a fresh git repo with one commit and aitasks/ + aiplans/.
new_repo() {
    local tmp
    tmp="$(mktemp -d "$FIXTURE_ROOT/repo_XXXXXX")"
    (
        cd "$tmp" || exit 1
        git init -q .
        git config user.email test@example.com
        git config user.name Test
        mkdir -p aitasks aiplans sub
        echo seed > seed.txt
        echo mine > sub/mine.md
        echo foreign > sub/foreign.md
        git add -A
        git commit -qm "init"
    ) >/dev/null 2>&1
    echo "$tmp"
}

# write_plan <dir> <task-id> <body>
write_plan() {
    local dir="$1" id="$2" body="$3"
    printf -- '---\nstatus: Ready\n---\nbody\n' > "$dir/aitasks/t${id}_x.md"
    printf -- '---\nTask: t%s_x.md\n---\n%s\n' "$id" "$body" > "$dir/aiplans/p${id}_x.md"
}

# cs <dir> <args...> — run the helper from the fixture root.
cs() { local d="$1"; shift; ( cd "$d" && "$CS" "$@" ); }

# assert_line / assert_no_line <desc> <line> <output> — WHOLE-LINE match.
#
# Every record the helper prints is a complete `CLASS:path` line, so a check on
# one file's classification must match the whole line. The shared substring
# helpers (assert_contains / assert_not_contains) are wrong for that: the needle
# `TASK:a.md` also matches a `TASK:a.md.orig` line, so a positive check passes
# while a.md itself is UNKNOWN, and a negative check fires on a different file.
# Keep the substring helpers only for checks that really are about a prefix or
# any occurrence (`TASK:` anywhere, `aitasks/` anywhere).
assert_line() {
    local desc="$1" line="$2" output="$3"
    if printf '%s\n' "$output" | grep -qxF -- "$line"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected a line exactly '$line', got '$output')"
    fi
}

assert_no_line() {
    local desc="$1" line="$2" output="$3"
    if printf '%s\n' "$output" | grep -qxF -- "$line"; then
        assert_record_fail
        echo "FAIL: $desc (expected NO line exactly '$line', got '$output')"
    else
        assert_record_pass
    fi
}

# ---------------------------------------------------------------------------
# 1. Two tasks dirty in one tree, interleaved in time.
#
#    capture 1   (baseline = {})
#    edit a.md
#    capture 2   (baseline = {a.md})
#    edit b.md               <- concurrent, AFTER t1's claim
#
# This is the shape that exposed the original bug. A baseline alone cannot
# assign b.md for t1 (t1's baseline was empty, so b.md looks "new"), so the
# positive signal must come from the plan.
# ---------------------------------------------------------------------------
fx="$(new_repo)"
write_plan "$fx" 1 'Touch a.md and sub/mine.md and everything under sub/ and tests/.'
write_plan "$fx" 2 'Touch b.md only.'

cs "$fx" capture 1 >/dev/null
echo a > "$fx/a.md"
cs "$fx" capture 2 >/dev/null
echo b > "$fx/b.md"
echo more >> "$fx/sub/foreign.md"
echo more >> "$fx/sub/mine.md"

out1="$(cs "$fx" list 1)"
out2="$(cs "$fx" list 2)"

assert_line "list 1: own planned file is TASK" "TASK:a.md" "$out1"
assert_line "list 1: concurrent post-claim edit is UNKNOWN" "UNKNOWN:b.md" "$out1"
# NEGATIVE CONTROL — the whole point of the task. If this ever passes as TASK:,
# the gate is back to inferring doc obligations from another task's work.
assert_no_line "list 1 NEG: concurrent edit must NOT be attributed" "TASK:b.md" "$out1"

assert_line "list 2: own planned file is TASK" "TASK:b.md" "$out2"
assert_line "list 2: work in flight at claim time is OTHER" "OTHER:a.md" "$out2"
assert_no_line "list 2 NEG: other task's file must NOT be attributed" "TASK:a.md" "$out2"

# ---------------------------------------------------------------------------
# 2. Plan scope is EXACT FILE MATCHES ONLY.
#
# p1 names the directory `sub/` in prose. A plan legitimately names broad
# directories; treating them as recursive scope would attribute every dirty file
# beneath them and reopen the shared-checkout failure.
# ---------------------------------------------------------------------------
assert_line "directory token does not attribute a file beneath it" \
    "UNKNOWN:sub/foreign.md" "$out1"
assert_no_line "NEG: directory token must NOT make a child TASK" \
    "TASK:sub/foreign.md" "$out1"
# ...while an exactly-named sibling in the same directory IS attributed, in the
# same run — proving the exclusion is about the token's shape, not the directory.
assert_line "exact file token in the same directory is attributed" \
    "TASK:sub/mine.md" "$out1"

# ---------------------------------------------------------------------------
# 2b. Dot-prefixed paths are attributable.
#
# Regression: the token regex originally required a token to START with
# [A-Za-z0-9_], so `.claude/skills/x/SKILL.md` was captured as
# `claude/skills/x/SKILL.md`, resolved to nothing, and was discarded. Every
# dot-directory path was permanently unattributable — which in this framework
# means .aitask-scripts/, .claude/, .codex/, .opencode/ and .agents/.
# ---------------------------------------------------------------------------
fx_dot="$(new_repo)"
mkdir -p "$fx_dot/.hidden/deep"
write_plan "$fx_dot" 12 'Edit .hidden/deep/cfg.json and .dotfile.md.'
cs "$fx_dot" capture 12 >/dev/null          # capture BEFORE the work, as a real claim does
echo '{}' > "$fx_dot/.hidden/deep/cfg.json"
echo dot > "$fx_dot/.dotfile.md"
echo other > "$fx_dot/.hidden/deep/unrelated.json"
out_dot="$(cs "$fx_dot" list 12)"
assert_line "dot-directory path is attributable" "TASK:.hidden/deep/cfg.json" "$out_dot"
assert_line "dot-file path is attributable" "TASK:.dotfile.md" "$out_dot"
assert_line "unnamed sibling under a dot-directory stays UNKNOWN" \
    "UNKNOWN:.hidden/deep/unrelated.json" "$out_dot"

# ---------------------------------------------------------------------------
# 3. Pass A (tagged commits) is independent of the dirty scan.
# ---------------------------------------------------------------------------
( cd "$fx" && git add a.md && git commit -qm "feature: add a (t1)" ) >/dev/null 2>&1

out_dirty_committed="$(cs "$fx" list 1)"
assert_line "tagged commit is COMMITTED" "COMMITTED:a.md" "$out_dirty_committed"
# De-duplication: a path that is both tagged-committed and dirty is reported once.
echo again >> "$fx/a.md"
n_lines="$(cs "$fx" list 1 | grep -c 'a\.md' || true)"
assert_eq "committed+dirty path emitted exactly once" "1" "$n_lines"
assert_line "committed+dirty path is reported as COMMITTED" \
    "COMMITTED:a.md" "$(cs "$fx" list 1)"

# The regression the two-pass split exists to prevent: a task that committed
# code and left the file CLEAN must still contribute it to the surface.
( cd "$fx" && git checkout -- a.md ) >/dev/null 2>&1
out_clean="$(cs "$fx" list 1)"
assert_line "clean tagged commit is STILL reported" "COMMITTED:a.md" "$out_clean"

# NEGATIVE CONTROL: a task whose ONLY contribution is a clean tagged commit must
# not return an empty surface.
fx_clean="$(new_repo)"
echo z > "$fx_clean/z.md"
( cd "$fx_clean" && git add z.md && git commit -qm "bug: fix z (t9)" ) >/dev/null 2>&1
out_only="$(cs "$fx_clean" list 9)"
assert_line "clean-commit-only task has a non-empty surface" "COMMITTED:z.md" "$out_only"

# The tag is a FIXED string: (t9) must not match (t99).
( cd "$fx_clean" && echo q > q.md && git add q.md && git commit -qm "bug: fix q (t99)" ) >/dev/null 2>&1
assert_no_line "NEG: (t9) does not match the (t99) commit" \
    "COMMITTED:q.md" "$(cs "$fx_clean" list 9)"

# ---------------------------------------------------------------------------
# 4. Signal conflict: named by the plan AND already dirty at claim.
# ---------------------------------------------------------------------------
fx3="$(new_repo)"
echo d > "$fx3/d.md"                      # dirty BEFORE the claim
write_plan "$fx3" 3 'Edit d.md.'          # ...and the plan names it
cs "$fx3" capture 3 >/dev/null
out3="$(cs "$fx3" list 3)"
assert_line "conflicting signals resolve to UNKNOWN" "UNKNOWN:d.md" "$out3"
assert_no_line "NEG: conflict must not silently become TASK" "TASK:d.md" "$out3"
assert_no_line "NEG: conflict must not silently become OTHER" "OTHER:d.md" "$out3"

# ---------------------------------------------------------------------------
# 5. Degraded signals fail SAFE (toward UNKNOWN), never toward TASK.
# ---------------------------------------------------------------------------
# 5a. No baseline at all (a task claimed before this feature shipped).
fx4="$(new_repo)"
write_plan "$fx4" 4 'Edit e.md.'
echo e > "$fx4/e.md"
echo u > "$fx4/unplanned.md"
out4="$(cs "$fx4" list 4)"
assert_line "no baseline: header says missing" "BASELINE:missing" "$out4"
assert_line "no baseline: plan scope still attributes" "TASK:e.md" "$out4"
assert_line "no baseline: unplanned path is UNKNOWN" "UNKNOWN:unplanned.md" "$out4"
assert_no_line "NEG: no baseline must not attribute an unplanned path" \
    "TASK:unplanned.md" "$out4"

# 5b. Baseline captured in a DIFFERENT tree (copied checkout).
cs "$fx4" capture 4 >/dev/null
sed_out="$(sed 's|^toplevel=.*|toplevel=/nonexistent/other/tree|' "$fx4/.aitask-gates/4/change_baseline")"
printf '%s\n' "$sed_out" > "$fx4/.aitask-gates/4/change_baseline"
out4b="$(cs "$fx4" list 4)"
assert_line "foreign baseline is reported as foreign" "BASELINE:foreign" "$out4b"
assert_line "foreign baseline: unplanned path stays UNKNOWN" "UNKNOWN:unplanned.md" "$out4b"

# 5c. No plan file at all.
fx5="$(new_repo)"
printf -- '---\nstatus: Ready\n---\nbody\n' > "$fx5/aitasks/t5_x.md"
echo f > "$fx5/f.md"
out5="$(cs "$fx5" list 5)"
assert_line "no plan: header says missing" "PLANSCOPE:missing" "$out5"
assert_line "no plan: dirty path is UNKNOWN" "UNKNOWN:f.md" "$out5"
assert_not_contains "NEG: no plan must never yield TASK" "TASK:" "$out5"

# 5d. A linked worktree with no baseline must NOT blanket-attribute.
# Worktree freshness is an inference, not a proof — a reused worktree can hold
# foreign dirt, so its unnamed dirt escalates like anywhere else.
fx6="$(new_repo)"
write_plan "$fx6" 6 'Edit g.md.'
( cd "$fx6" && git worktree add -q -b aitask/t6_x wt HEAD ) >/dev/null 2>&1
if [[ -d "$fx6/wt" ]]; then
    mkdir -p "$fx6/wt/aitasks" "$fx6/wt/aiplans"
    cp "$fx6/aitasks/t6_x.md" "$fx6/wt/aitasks/" 2>/dev/null || true
    cp "$fx6/aiplans/p6_x.md" "$fx6/wt/aiplans/" 2>/dev/null || true
    echo g > "$fx6/wt/g.md"
    echo h > "$fx6/wt/stray.md"
    out6="$(cs "$fx6/wt" list 6)"
    assert_line "worktree: no baseline reported as missing" "BASELINE:missing" "$out6"
    assert_line "worktree: planned file attributed" "TASK:g.md" "$out6"
    assert_line "worktree: unplanned dirt is UNKNOWN" "UNKNOWN:stray.md" "$out6"
    assert_no_line "NEG: worktree must not blanket-attribute unplanned dirt" \
        "TASK:stray.md" "$out6"
else
    echo "SKIP: git worktree unavailable — skipping worktree isolation case"
fi

# ---------------------------------------------------------------------------
# 6. Plan text is DATA, never a pattern and never evaluated.
# ---------------------------------------------------------------------------
fx7="$(new_repo)"
write_plan "$fx7" 7 'Touch .* and dir/.* and $(touch /tmp/pwned_t1263) and `id`.'
echo v > "$fx7/victim.md"
out7="$(cs "$fx7" list 7)"
assert_line "metacharacter plan: unrelated file stays UNKNOWN" "UNKNOWN:victim.md" "$out7"
assert_no_line "NEG: '.*' in a plan must not attribute everything" "TASK:victim.md" "$out7"
assert_file_not_exists "NEG: plan text must not be executed" "/tmp/pwned_t1263"

# ---------------------------------------------------------------------------
# 7. Task/plan data paths never appear in any class.
# ---------------------------------------------------------------------------
fx8="$(new_repo)"
write_plan "$fx8" 8 'Edit aitasks/t8_x.md and aiplans/p8_x.md and w.md.'
cs "$fx8" capture 8 >/dev/null
echo w > "$fx8/w.md"
echo "extra" >> "$fx8/aitasks/t8_x.md"
out8="$(cs "$fx8" list 8)"
assert_not_contains "aitasks/ never appears in the surface" "aitasks/" "$out8"
assert_not_contains "aiplans/ never appears in the surface" "aiplans/" "$out8"
assert_line "...but real code changes still do" "TASK:w.md" "$out8"

# ---------------------------------------------------------------------------
# 8. DRIFT GUARD: the helper's exclude set must match gate_ledger's canonical one.
# ---------------------------------------------------------------------------
sh_excludes="$(grep -E '^EXCLUDES=' "$CS" \
    | sed -e "s/^EXCLUDES=(//" -e "s/)$//" -e "s/'//g" \
    | tr ' ' '\n' | sed 's/^:(exclude)//' | grep -v '^$' | LC_ALL=C sort)"
# LC_ALL=C so the comparison is byte order on both sides: Python's sorted() is
# byte order, while a locale-aware `sort` ignores the leading dot of
# `.aitask-data/**` and reorders it. Without this the guard fails on a set that
# actually matches.
py_excludes="$("$PY" -c "
import sys; sys.path.insert(0,'$PROJECT_DIR/.aitask-scripts/lib')
import gate_ledger as gl
print('\n'.join(sorted(x.replace(':(exclude)','') for x in gl._DIGEST_EXCLUDES)))
" 2>/dev/null || echo "PY_UNAVAILABLE")"
if [[ "$py_excludes" == "PY_UNAVAILABLE" ]]; then
    echo "SKIP: no python interpreter resolved — skipping exclude drift guard"
else
    assert_eq "exclude set matches gate_ledger._DIGEST_EXCLUDES (no drift)" \
        "$py_excludes" "$sh_excludes"
fi

# ---------------------------------------------------------------------------
# 9. The WRITER: aitask_pick_own.sh captures on a fresh claim only, and its
#    stdout contract is unchanged by the capture call.
# ---------------------------------------------------------------------------
# RUNTIME comparison, not a text search. Grepping the script for the guard and
# the redirection would keep passing through a reordering, an invocation-wrapper
# change, or a broken missing-helper path — none of which are textual. So run
# the real script twice over identical state, once with the helper reachable and
# once with it absent, and compare stdout byte for byte.
#
# `status: Ready` (a fresh claim) is the arm that actually invokes capture; if
# the capture could leak a line into stdout, this is where it would show.
own_repo() {
    local with_helper="$1" dir
    dir="$(mktemp -d "$FIXTURE_ROOT/own_XXXXXX")"
    (
        cd "$dir" || exit 1
        git init -q .
        git config user.email test@example.com
        git config user.name Test
        mkdir -p aitasks/metadata aiplans
        printf -- '---\npriority: medium\neffort: medium\ndepends: []\nissue_type: feature\nstatus: Ready\nlabels: []\ncreated_at: 2026-01-01 00:00\nupdated_at: 2026-01-01 00:00\n---\n\nBody.\n' \
            > aitasks/t1_claimme.md
        setup_fake_aitask_repo "$PWD"
        cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" .aitask-scripts/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/pid_anchor.sh" .aitask-scripts/lib/ 2>/dev/null || true
        cp "$PROJECT_DIR/ait" . 2>/dev/null || true
        # The ONLY difference between the two arms.
        if [[ "$with_helper" == "with" ]]; then
            cp "$CS" .aitask-scripts/
        fi
        chmod +x .aitask-scripts/*.sh ait 2>/dev/null || true
        git add -A
        git commit -qm "setup"
    ) >/dev/null 2>&1
    echo "$dir"
}

own_with="$(own_repo with)"
own_without="$(own_repo without)"
out_with="$( cd "$own_with"    && ./.aitask-scripts/aitask_pick_own.sh 1 --email "a@test.com" 2>/dev/null )"
out_without="$( cd "$own_without" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "a@test.com" 2>/dev/null )"

# Positive control first: if the claim did not actually run, comparing two empty
# strings would "pass" while proving nothing.
assert_line "pick_own actually claimed the task (positive control)" "OWNED:1" "$out_with"
assert_eq "pick_own stdout is byte-identical with and without the helper" \
    "$out_without" "$out_with"

# ...and the capture really did run in the with-helper arm (otherwise the
# byte-identical result above would be vacuous).
assert_file_exists "fresh claim writes the baseline" \
    "$own_with/.aitask-gates/1/change_baseline"
assert_file_not_exists "helper absent: no baseline, and the claim still succeeded" \
    "$own_without/.aitask-gates/1/change_baseline"

# The guard: a task already Implementing (a reclaim/resume) must NOT re-capture.
printf 'STALE\n' > "$own_with/.aitask-gates/1/change_baseline"
( cd "$own_with" && ./.aitask-scripts/aitask_pick_own.sh 1 --email "a@test.com" ) >/dev/null 2>&1
assert_eq "reclaim does NOT overwrite the original baseline" \
    "STALE" "$(cat "$own_with/.aitask-gates/1/change_baseline" 2>/dev/null || echo MISSING)"

# Capture is a full re-snapshot, so a SECOND capture after work started would
# re-baseline this session's own edits as "other work" — which is exactly why
# pick_own guards it. Pin that consequence so the guard cannot be dropped as
# harmless.
fx9="$(new_repo)"
write_plan "$fx9" 10 'Edit k.md.'
cs "$fx9" capture 10 >/dev/null
echo k > "$fx9/k.md"
assert_line "before re-capture: own work is TASK" "TASK:k.md" "$(cs "$fx9" list 10)"
cs "$fx9" capture 10 >/dev/null          # simulates an unguarded re-claim
assert_line "after re-capture: own work would be misread as OTHER" \
    "UNKNOWN:k.md" "$(cs "$fx9" list 10)"

# capture on a clean tree must still write a baseline (empty dirty set is not a
# failure — an early `grep -v` exiting 1 under pipefail used to kill it silently).
fx10="$(new_repo)"
assert_eq "capture on a clean tree records an empty baseline" \
    "CAPTURED:0" "$(cs "$fx10" capture 11)"
assert_file_exists "clean-tree capture writes the baseline file" \
    "$fx10/.aitask-gates/11/change_baseline"

# `baseline` reports the raw N1 signal, uncombined (t1873): a pre-claim-dirty
# path the plan ALSO names is still DIRTY_AT_CLAIM here, where `list` folds the
# combination into UNKNOWN and loses the N1 half.
fx11="$(new_repo)"
write_plan "$fx11" 12 'Edit sub/mine.md.'
echo pre >> "$fx11/sub/mine.md"
echo pre2 >> "$fx11/sub/foreign.md"
cs "$fx11" capture 12 >/dev/null
b12="$(cs "$fx11" baseline 12)"
assert_line "baseline: header" "BASELINE:ok" "$b12"
assert_line "baseline: plan-named pre-claim path kept" "DIRTY_AT_CLAIM:sub/mine.md" "$b12"
assert_line "baseline: unnamed pre-claim path kept" "DIRTY_AT_CLAIM:sub/foreign.md" "$b12"
assert_line "list still folds the plan-named one into UNKNOWN" \
    "UNKNOWN:sub/mine.md" "$(cs "$fx11" list 12)"
assert_eq "baseline: missing is its own state" \
    "BASELINE:missing" "$(cs "$fx11" baseline 99)"

# --- summary ---------------------------------------------------------------
echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
