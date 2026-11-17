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
#   - A rename is two paths (t2304): staged, unstaged and committed renames list
#     the OLD half as well as the new, each classified by the ordinary rules;
#     plain deletions are still listed; `baseline` and `list` agree.
#   - Paths are RAW bytes (t2310): non-ASCII, `|` and NFD names are attributed
#     through the shared plan-reference search; a control-byte or leading-`"`
#     path is one escaped record (never split, never a raw CR); a version-1
#     (git-quoted) baseline still matches; a broken search fails closed to
#     PLANSCOPE:missing.
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
# AIT_TEST_CHANGE_SURFACE: run the same assertions against another copy of the
# script (a pre-fix control: a scratch copy of an older revision beside a `lib`
# symlink). Unset in normal runs.
CS="${AIT_TEST_CHANGE_SURFACE:-$PROJECT_DIR/.aitask-scripts/aitask_change_surface.sh}"
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
# This run's $TMPDIR writes (lock bases, logs, mktemps) land under $FIXTURE_ROOT (t2302).
. "$PROJECT_DIR/tests/lib/run_tmpdir.sh"
run_tmpdir_init test_chgsurf "$FIXTURE_ROOT"

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
    # A here-string, not `printf | grep -q`: under pipefail an early-exiting
    # grep SIGPIPEs the writer and a present line reads as absent (t2056).
    if grep -qxF -- "$line" <<<"$output"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected a line exactly '$line', got '$output')"
    fi
}

assert_no_line() {
    local desc="$1" line="$2" output="$3"
    if grep -qxF -- "$line" <<<"$output"; then
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

# ---------------------------------------------------------------------------
# 10. RENAMES ARE TWO PATHS (t2304).
#
# Git's default rename detection prints only a rename's NEW path, in both
# `git diff --name-only HEAD` (dirty set: capture/baseline and list pass B) and
# `git show --name-only` (pass A). The OLD path then never reaches the surface,
# and the testmap selector -- which escalates an absent listed path to a full
# run -- under-selects instead. Every case below runs the REAL script, and each
# rename case first proves git really pairs the rename in that fixture; without
# that the old-half assertions could pass on a fixture git never treated as a
# rename.
#
# RENAME DETECTION IS PINNED ON FOR THE PRODUCER TOO, not only for the controls.
# Under a user's `diff.renames=false` the unpatched script never hides an old
# half, so every assertion here would pass with the `--no-renames` flags removed
# -- the regression would escape. `rn` pins it through GIT_CONFIG_COUNT (command
# scope, above every config file) and drops an inherited GIT_CONFIG_PARAMETERS
# (`git -c ...` from a parent process) that could re-override it. The control
# and the producer run under the SAME `rn` environment, so a passing control
# vouches for exactly the config the producer saw.
# ---------------------------------------------------------------------------

RENAMES_ON=(env -u GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT=1
            GIT_CONFIG_KEY_0=diff.renames GIT_CONFIG_VALUE_0=true)
# rn_cs <dir> <args...> / rn_git <dir> <args...> — the helper / git, from the
# fixture root, with rename detection pinned on.
rn_cs()  { local d="$1"; shift; ( cd "$d" && "${RENAMES_ON[@]}" "$CS" "$@" ); }
rn_git() { local d="$1"; shift; ( cd "$d" && "${RENAMES_ON[@]}" git "$@" ); }

# add_files <dir> <name>... — create each file with DISTINCT content (so git
# cannot pair the wrong two) and commit them.
add_files() {
    local d="$1" n; shift
    for n in "$@"; do printf 'body of %s\n%s\n' "$n" "$n-unique-line" > "$d/$n"; done
    ( cd "$d" && git add -- "$@" && git commit -qm "add $*" ) >/dev/null 2>&1
}

# surface_paths <output> — the path field of every classified `list` line.
surface_paths() {
    sed -n -E 's/^(COMMITTED|TASK|OTHER|UNKNOWN)://p' <<<"$1" | LC_ALL=C sort
}

# 10a. Staged rename (`git mv`): the old half in each of the three classes.
fx_r="$(new_repo)"
add_files "$fx_r" ra.sh na.sh pa.sh
write_plan "$fx_r" 20 'Rename ra.sh to rb.sh.'
( cd "$fx_r" && git mv pa.sh pb.sh ) >/dev/null 2>&1        # BEFORE the claim
rn_cs "$fx_r" capture 20 >/dev/null
( cd "$fx_r" && git mv ra.sh rb.sh && git mv na.sh nb.sh ) >/dev/null 2>&1
ctl_r="$(rn_git "$fx_r" diff --name-only HEAD)"
assert_line "10a control: git pairs the staged rename (new half listed)" "rb.sh" "$ctl_r"
assert_no_line "10a control: git pairs the staged rename (old half hidden)" "ra.sh" "$ctl_r"
out_r="$(rn_cs "$fx_r" list 20)"
assert_line "staged rename, plan-named: old half is TASK" "TASK:ra.sh" "$out_r"
assert_line "staged rename, plan-named: new half is TASK" "TASK:rb.sh" "$out_r"
assert_line "staged rename, baseline-only: old half is OTHER" "OTHER:pa.sh" "$out_r"
assert_line "staged rename, baseline-only: new half is OTHER" "OTHER:pb.sh" "$out_r"
assert_line "staged rename, unowned: old half is UNKNOWN" "UNKNOWN:na.sh" "$out_r"
assert_line "staged rename, unowned: new half is UNKNOWN" "UNKNOWN:nb.sh" "$out_r"
# NEGATIVES on the halves NO plan claims: never attributed by another route.
assert_no_line "NEG: baseline-only old half is not TASK" "TASK:pa.sh" "$out_r"
assert_no_line "NEG: unowned old half is not TASK" "TASK:na.sh" "$out_r"

# 10b. Unstaged rename (`mv`; the new file is untracked).
fx_u="$(new_repo)"
add_files "$fx_u" ua.sh un.sh uo.sh
write_plan "$fx_u" 22 'Rename ua.sh to ub.sh.'
mv "$fx_u/uo.sh" "$fx_u/up.sh"                               # BEFORE the claim
rn_cs "$fx_u" capture 22 >/dev/null
mv "$fx_u/ua.sh" "$fx_u/ub.sh"
mv "$fx_u/un.sh" "$fx_u/um.sh"
out_u="$(rn_cs "$fx_u" list 22)"
assert_line "unstaged rename, plan-named: old half is TASK" "TASK:ua.sh" "$out_u"
assert_line "unstaged rename, plan-named: new half is TASK" "TASK:ub.sh" "$out_u"
assert_line "unstaged rename, baseline-only: old half is OTHER" "OTHER:uo.sh" "$out_u"
assert_line "unstaged rename, baseline-only: new half is OTHER" "OTHER:up.sh" "$out_u"
assert_line "unstaged rename, unowned: old half is UNKNOWN" "UNKNOWN:un.sh" "$out_u"
assert_line "unstaged rename, unowned: new half is UNKNOWN" "UNKNOWN:um.sh" "$out_u"
assert_no_line "NEG: unstaged baseline-only old half is not TASK" "TASK:uo.sh" "$out_u"
assert_no_line "NEG: unstaged unowned old half is not TASK" "TASK:un.sh" "$out_u"

# 10c. Committed rename in a (t<id>) commit: pass A reports both halves.
fx_c="$(new_repo)"
add_files "$fx_c" ca.sh
( cd "$fx_c" && git mv ca.sh cb.sh && git commit -qm "refactor: rename ca (t21)" ) >/dev/null 2>&1
ctl_c="$(rn_git "$fx_c" show --name-only --format= HEAD)"
assert_line "10c control: git pairs the committed rename (new half listed)" "cb.sh" "$ctl_c"
assert_no_line "10c control: git pairs the committed rename (old half hidden)" "ca.sh" "$ctl_c"
out_c="$(rn_cs "$fx_c" list 21)"
assert_line "committed rename: old half is COMMITTED" "COMMITTED:ca.sh" "$out_c"
assert_line "committed rename: new half is COMMITTED" "COMMITTED:cb.sh" "$out_c"

# 10d. Plain deletions are still listed (regression guard).
fx_d="$(new_repo)"
add_files "$fx_d" dd.sh de.sh
write_plan "$fx_d" 23 'Nothing named here.'
rn_cs "$fx_d" capture 23 >/dev/null
( cd "$fx_d" && git rm -q dd.sh ) >/dev/null 2>&1
rm "$fx_d/de.sh"
out_d="$(rn_cs "$fx_d" list 23)"
assert_line "staged deletion is listed" "UNKNOWN:dd.sh" "$out_d"
assert_line "unstaged deletion is listed" "UNKNOWN:de.sh" "$out_d"

# 10e. `baseline` (DIRTY_AT_CLAIM) and `list` agree on the same tree: both
# halves of a staged and of an unstaged rename, through both subcommands.
fx_e="$(new_repo)"
add_files "$fx_e" ea.sh ec.sh
( cd "$fx_e" && git mv ea.sh eb.sh ) >/dev/null 2>&1
mv "$fx_e/ec.sh" "$fx_e/ed.sh"
assert_eq "capture records both halves of both renames" \
    "CAPTURED:4" "$(rn_cs "$fx_e" capture 24)"
base_e="$(rn_cs "$fx_e" baseline 24 | sed -n 's/^DIRTY_AT_CLAIM://p' | LC_ALL=C sort)"
list_e="$(surface_paths "$(rn_cs "$fx_e" list 24)")"
assert_eq "baseline path set equals list path set on the same tree" "$list_e" "$base_e"
assert_eq "...and it is exactly both halves of both renames" \
    "$(printf '%s\n' ea.sh eb.sh ec.sh ed.sh)" "$base_e"

# ---------------------------------------------------------------------------
# 11. PATHS ARE RAW BYTES (t2310).
#
# Without -z git C-quotes a non-ASCII or special path under the default
# core.quotePath (`"d\303\251.md"`); that spelling never equals a plan reference
# or the raw path another consumer compares against, so such a path was never
# TASK. The plan-scope tokenizer also split `docs/a|b.md` and dropped non-ASCII
# names; P2 now asks the shared inverted search (lib/plan_paths.py).
#
# core.quotePath IS PINNED ON for the producer, not only for the controls --
# under a user's quotePath=false the unpatched script prints non-ASCII raw and
# every non-ASCII assertion would pass with -z removed. Same pinning mechanism,
# and the same reason, as RENAMES_ON in section 10.
#
# Byte-exact names are built with printf octal escapes, never typed, so an
# editor's normalization cannot change what the fixture means.
# ---------------------------------------------------------------------------

QUOTE_ON=(env -u GIT_CONFIG_PARAMETERS GIT_CONFIG_COUNT=1
          GIT_CONFIG_KEY_0=core.quotePath GIT_CONFIG_VALUE_0=true)
qp_cs()  { local d="$1"; shift; ( cd "$d" && "${QUOTE_ON[@]}" "$CS" "$@" ); }
qp_git() { local d="$1"; shift; ( cd "$d" && "${QUOTE_ON[@]}" git "$@" ); }

DEJA="$(printf 'd\303\251 j\303\240.md')"        # "dé jà.md", NFC
UNNAMED="$(printf '\303\274nnamed.md')"          # "ünnamed.md"
O_UML="$(printf '\303\266.md')"                  # "ö.md"
A_UML="$(printf '\303\244.md')"                  # "ä.md"
U_UML="$(printf '\303\274.md')"                  # "ü.md"
CAFE_NFC="$(printf 'caf\303\251.md')"            # é precomposed
CAFE_NFD="$(printf 'cafe\314\201.md')"           # e + combining acute
LS_PATH="$(printf 'docs/a\342\200\250DIRTY_AT_CLAIM:innocent.md')"   # U+2028 inside
LF_PATH=$'a\nb.md'
CR_PATH=$'x\ry.md'
VT_PATH=$'v\vw.md'
TCR_COMMITTED=$'src/a.md\r'                      # TRAILING CR on purpose
TCR_DIRTY=$'d.md\r'
LEAD_Q='"lead.md'

# escaped_count <output> — records whose path field is an escaped form.
escaped_count() { grep -c '^[A-Z_]*:"' <<<"$1" || true; }

# 11a. Non-ASCII: plan-named -> TASK, unnamed -> UNKNOWN, both raw.
fx_q="$(new_repo)"
write_plan "$fx_q" 30 "Edit \`${DEJA}\` here."
qp_cs "$fx_q" capture 30 >/dev/null
printf 'n\n' > "$fx_q/$DEJA"
printf 'n\n' > "$fx_q/$UNNAMED"
ctl_q="$(qp_git "$fx_q" ls-files --others --exclude-standard)"
assert_line "11a control: git C-quotes the non-ASCII path in this fixture" \
    '"d\303\251 j\303\240.md"' "$ctl_q"
out_q="$(qp_cs "$fx_q" list 30)"
assert_line "non-ASCII path the plan names is TASK (raw)" "TASK:${DEJA}" "$out_q"
assert_line "non-ASCII path no plan names is UNKNOWN (raw)" "UNKNOWN:${UNNAMED}" "$out_q"
assert_eq "no record of an ordinary non-ASCII path is escaped" "0" "$(escaped_count "$out_q")"

# 11b. `|` is a path byte: the plan names `docs/a|b.md` and it is attributed.
fx_p="$(new_repo)"
write_plan "$fx_p" 31 'Edit `docs/a|b.md` only.'
qp_cs "$fx_p" capture 31 >/dev/null
mkdir -p "$fx_p/docs"; printf 'n\n' > "$fx_p/docs/a|b.md"
out_p="$(qp_cs "$fx_p" list 31)"
assert_line "a plan-named path containing | is TASK" "TASK:docs/a|b.md" "$out_p"

# 11c. NFD on disk (the APFS/HFS+ shape), NFC in the plan: TASK, reported as
# git named it (the NFD bytes), never the plan's NFC spelling.
fx_n="$(new_repo)"
write_plan "$fx_n" 32 "Edit \`${CAFE_NFC}\`."
qp_cs "$fx_n" capture 32 >/dev/null
printf 'n\n' > "$fx_n/$CAFE_NFD"
out_n="$(qp_cs "$fx_n" list 32)"
assert_line "NFD file named in NFC by the plan is TASK, as git named it" "TASK:${CAFE_NFD}" "$out_n"
assert_no_line "...never under the plan's NFC spelling" "TASK:${CAFE_NFC}" "$out_n"

# 11d. N1 for non-ASCII: pre-claim dirt is OTHER; plan-named + pre-claim stays
# UNKNOWN (the signal conflict), never TASK.
new_uml_repo() {   # new_uml_repo -> a repo with ö.md / ä.md committed
    local d; d="$(new_repo)"
    printf 'o\n' > "$d/$O_UML"; printf 'a\n' > "$d/$A_UML"
    ( cd "$d" && git add -A && git commit -qm "umlauts" ) >/dev/null 2>&1
    echo "$d"
}
fx_b="$(new_uml_repo)"
write_plan "$fx_b" 33 "Edit \`${A_UML}\`."
printf 'dirty\n' >> "$fx_b/$O_UML"; printf 'dirty\n' >> "$fx_b/$A_UML"    # BEFORE the claim
ctl_b="$(qp_git "$fx_b" diff --name-only HEAD)"
assert_line "11d control: git C-quotes the modified non-ASCII path" '"\303\266.md"' "$ctl_b"
qp_cs "$fx_b" capture 33 >/dev/null
assert_line "baseline records the non-ASCII path raw" \
    "DIRTY_AT_CLAIM:${O_UML}" "$(qp_cs "$fx_b" baseline 33)"
out_b="$(qp_cs "$fx_b" list 33)"
assert_line "pre-claim non-ASCII dirt is OTHER" "OTHER:${O_UML}" "$out_b"
assert_line "plan-named AND pre-claim non-ASCII is UNKNOWN" "UNKNOWN:${A_UML}" "$out_b"
assert_no_line "NEG: plan-named pre-claim non-ASCII is not TASK" "TASK:${A_UML}" "$out_b"

# 11e. A VERSION-1 baseline (written before t2310, git-quoted) still matches:
# the transitional false-TASK guard for tasks claimed before the upgrade.
fx_v="$(new_uml_repo)"
write_plan "$fx_v" 34 "Edit \`${A_UML}\`."
printf 'dirty\n' >> "$fx_v/$O_UML"; printf 'dirty\n' >> "$fx_v/$A_UML"
mkdir -p "$fx_v/.aitask-gates/34"
{
    printf 'version=1\ntask=34\ntoplevel=%s\nhead=%s\n' \
        "$(cd "$fx_v" && git rev-parse --show-toplevel)" "$(cd "$fx_v" && git rev-parse HEAD)"
    printf 'captured_at=2026-01-01T00:00:00Z\npaths:\n'
    printf '%s\n' '"\303\244.md"' '"\303\266.md"'
} > "$fx_v/.aitask-gates/34/change_baseline"
assert_line "v1 baseline: the quoted record is decoded to the raw path" \
    "DIRTY_AT_CLAIM:${O_UML}" "$(qp_cs "$fx_v" baseline 34)"
out_v="$(qp_cs "$fx_v" list 34)"
assert_line "v1 baseline: pre-claim non-ASCII dirt is OTHER" "OTHER:${O_UML}" "$out_v"
assert_line "v1 baseline: plan-named pre-claim path stays UNKNOWN" "UNKNOWN:${A_UML}" "$out_v"
assert_no_line "NEG: v1 baseline never turns it into a false TASK" "TASK:${A_UML}" "$out_v"

# 11f. Pass A: a committed non-ASCII path is reported raw.
fx_f="$(new_repo)"
printf 'u\n' > "$fx_f/$U_UML"
( cd "$fx_f" && git add -A && git commit -qm "feature: add (t35)" ) >/dev/null 2>&1
assert_line "11f control: git C-quotes the committed non-ASCII path" \
    '"\303\274.md"' "$(qp_git "$fx_f" show --name-only --format= HEAD)"
assert_line "committed non-ASCII path is COMMITTED (raw)" \
    "COMMITTED:${U_UML}" "$(qp_cs "$fx_f" list 35)"

# 11g. A LF in a path: exactly ONE escaped record, never split into two paths,
# never TASK even when the plan names both "halves".
fx_l="$(new_repo)"
write_plan "$fx_l" 36 'Edit `a` and `b.md` and `a b.md`.'
qp_cs "$fx_l" capture 36 >/dev/null
printf 'n\n' > "$fx_l/$LF_PATH"
out_l="$(qp_cs "$fx_l" list 36)"
assert_line "a LF path is one escaped UNKNOWN record" 'UNKNOWN:"a\nb.md"' "$out_l"
assert_eq "...and the only path record" "1" "$(surface_paths "$out_l" | grep -c . || true)"
assert_no_line "NEG: no record for the first half" "UNKNOWN:a" "$out_l"
assert_no_line "NEG: no record for the second half" "UNKNOWN:b.md" "$out_l"
assert_not_contains "NEG: a LF path is never TASK" "TASK:" "$out_l"
fx_l2="$(new_repo)"
printf 'n\n' > "$fx_l2/$LF_PATH"                                  # BEFORE the claim
qp_cs "$fx_l2" capture 36 >/dev/null
assert_line "a pre-claim LF path still matches its baseline (OTHER)" \
    'OTHER:"a\nb.md"' "$(qp_cs "$fx_l2" list 36)"

# 11h. BROKEN MATCHER: when the plan-reference search cannot run, P2 is
# unavailable (PLANSCOPE:missing) -- never an "ok" that attributes nothing, and
# never a TASK. The positive control runs the SAME fixture with the search
# reachable, so the stub is the only difference.
fx_h="$(new_repo)"
write_plan "$fx_h" 37 'Edit `sub/mine.md`.'
qp_cs "$fx_h" capture 37 >/dev/null
echo edit >> "$fx_h/sub/mine.md"
mkdir -p "$FIXTURE_ROOT/no_plan_paths"
out_h_ok="$(qp_cs "$fx_h" list 37)"
assert_line "11h positive control: with the search, the plan-named file is TASK" \
    "TASK:sub/mine.md" "$out_h_ok"
assert_line "11h positive control: PLANSCOPE is ok" "PLANSCOPE:ok" "$out_h_ok"
out_h="$( cd "$fx_h" && AIT_PLAN_PATHS_DIR="$FIXTURE_ROOT/no_plan_paths" \
    "${QUOTE_ON[@]}" "$CS" list 37 2>/dev/null )"
assert_line "broken search: PLANSCOPE is missing" "PLANSCOPE:missing" "$out_h"
assert_not_contains "broken search: nothing is TASK" "TASK:" "$out_h"
assert_line "broken search: the file falls to UNKNOWN" "UNKNOWN:sub/mine.md" "$out_h"

# 11i. A grammar edge pinned ON PURPOSE (findings doc section 3): `@` continues
# a path, so `sub/mine.md@v2` is not a reference to `sub/mine.md`.
fx_i="$(new_repo)"
write_plan "$fx_i" 38 'Compare with sub/mine.md@v2 upstream.'
qp_cs "$fx_i" capture 38 >/dev/null
echo edit >> "$fx_i/sub/mine.md"
out_i="$(qp_cs "$fx_i" list 38)"
assert_line "a path@rev mention does not attribute the bare path" "UNKNOWN:sub/mine.md" "$out_i"

# 11j. Non-LF line breaks stay inside ONE record. U+2028 is not a control byte
# and stays raw; CR and VT are control bytes and are escaped. The U+2028 name
# embeds a fake `DIRTY_AT_CLAIM:innocent.md` so a reader that splits on more
# than LF would invent a record for an unrelated file.
fx_j="$(new_repo)"
mkdir -p "$fx_j/docs"
printf 'i\n' > "$fx_j/innocent.md"
( cd "$fx_j" && git add -A && git commit -qm "innocent" ) >/dev/null 2>&1
printf 'n\n' > "$fx_j/$LS_PATH"; printf 'n\n' > "$fx_j/$CR_PATH"; printf 'n\n' > "$fx_j/$VT_PATH"
qp_cs "$fx_j" capture 39 >/dev/null
echo edit >> "$fx_j/innocent.md"                                  # AFTER the claim
base_j="$(qp_cs "$fx_j" baseline 39)"
assert_line "U+2028 path: one raw baseline record" "DIRTY_AT_CLAIM:${LS_PATH}" "$base_j"
assert_line "CR path: one escaped baseline record" 'DIRTY_AT_CLAIM:"x\ry.md"' "$base_j"
assert_line "VT path: one escaped baseline record" 'DIRTY_AT_CLAIM:"v\vw.md"' "$base_j"
assert_eq "exactly three baseline records" "3" "$(grep -c '^DIRTY_AT_CLAIM:' <<<"$base_j" || true)"
assert_no_line "NEG: no invented baseline record for innocent.md" \
    "DIRTY_AT_CLAIM:innocent.md" "$base_j"
out_j="$(qp_cs "$fx_j" list 39)"
assert_line "U+2028 path is OTHER" "OTHER:${LS_PATH}" "$out_j"
assert_line "CR path is OTHER" 'OTHER:"x\ry.md"' "$out_j"
assert_line "VT path is OTHER" 'OTHER:"v\vw.md"' "$out_j"
assert_line "innocent.md, dirtied after the claim, is UNKNOWN (not OTHER)" \
    "UNKNOWN:innocent.md" "$out_j"

# 11k. TRAILING CR in the real producer record. A scanner that drops one
# trailing CR before LF (Go's bufio.ScanLines in the testmap intake) would read
# a raw `COMMITTED:src/a.md<CR>` as `src/a.md` -- the tracked neighbour below.
# An interior CR (11j) cannot expose that truncation; a trailing one can.
fx_k="$(new_repo)"
mkdir -p "$fx_k/src"; printf 'a\n' > "$fx_k/src/a.md"
( cd "$fx_k" && git add -A && git commit -qm "neighbour" ) >/dev/null 2>&1
printf 'cr\n' > "$fx_k/$TCR_COMMITTED"
( cd "$fx_k" && git add -A && git commit -qm "feature: trailing cr (t40)" ) >/dev/null 2>&1
printf 'cr\n' > "$fx_k/$TCR_DIRTY"
out_k="$(qp_cs "$fx_k" list 40)"
assert_line "a committed trailing-CR path is one escaped record" 'COMMITTED:"src/a.md\r"' "$out_k"
assert_line "an untracked trailing-CR path is one escaped record" 'UNKNOWN:"d.md\r"' "$out_k"
assert_no_line "NEG: the neighbour is not reported as committed" "COMMITTED:src/a.md" "$out_k"
assert_eq "no raw CR byte anywhere in the output" "0" \
    "$(printf '%s' "$out_k" | LC_ALL=C tr -cd '\r' | wc -c | tr -d ' ')"

# 11l. ESCAPE ROUND TRIP: every escaped shape decodes, with git's C-quote
# grammar (Python's codecs.escape_decode), to the exact bytes of the on-disk
# name -- including a name that itself begins with `"`.
fx_e2="$(new_repo)"
printf 'q\n' > "$fx_e2/$LEAD_Q"
out_e2="$(qp_cs "$fx_e2" list 41)"
assert_line "a leading-quote name is escaped (keeps the encoding injective)" \
    'UNKNOWN:"\"lead.md"' "$out_e2"
# roundtrip <desc> <field> <expected raw name>
roundtrip() {
    local got want
    got="$("$PY" -c 'import codecs, sys
f = sys.argv[1].encode("utf-8", "surrogateescape")
sys.stdout.buffer.write(codecs.escape_decode(f[1:-1])[0])' "$2" | od -An -tx1 | tr -d ' \n')"
    want="$(printf '%s' "$3" | od -An -tx1 | tr -d ' \n')"
    assert_eq "$1" "$want" "$got"
}
roundtrip "round trip: LF"           '"a\nb.md"'      "$LF_PATH"
roundtrip "round trip: interior CR"  '"x\ry.md"'      "$CR_PATH"
roundtrip "round trip: VT"           '"v\vw.md"'      "$VT_PATH"
roundtrip "round trip: trailing CR"  '"src/a.md\r"'   "$TCR_COMMITTED"
roundtrip "round trip: leading quote" '"\"lead.md"'   "$LEAD_Q"
# ...and the expected names really are the on-disk names the records came from
# (otherwise a round trip against a mistyped literal would prove nothing).
for spec in "$fx_l:$LF_PATH" "$fx_j:$CR_PATH" "$fx_j:$VT_PATH" \
            "$fx_k:$TCR_COMMITTED" "$fx_e2:$LEAD_Q"; do
    if [[ -e "${spec%%:*}/${spec#*:}" ]]; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: round-trip fixture name missing on disk: $(printf '%q' "${spec#*:}")"
    fi
done

# --- summary ---------------------------------------------------------------
echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[ "$FAIL" -eq 0 ]
