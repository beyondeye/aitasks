#!/usr/bin/env bash
# test_task_git.sh - Tests for task_git(), task_sync(), task_push() and ait git command
# Run: bash tests/test_task_git.sh

set -e

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---
# Core helpers live in tests/lib/asserts.sh. This file's original assert_eq
# trimmed whitespace (xargs) and assert_contains was case-insensitive (grep -qi),
# so call sites are remapped to assert_eq_trim / assert_contains_ci below.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Setup helpers ---

# Get default branch name for the system
DEFAULT_BRANCH="$(git config --global init.defaultBranch 2>/dev/null || echo "main")"

setup_repo_with_remote() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    git init --bare --quiet "$tmpdir/remote.git"
    git clone --quiet "$tmpdir/remote.git" "$tmpdir/local" 2>/dev/null
    (
        cd "$tmpdir/local"
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
        git push --quiet 2>/dev/null
    )
    echo "$tmpdir"
}

setup_local_repo() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    (
        cd "$tmpdir"
        git init --quiet
        git config user.email "test@test.com"
        git config user.name "Test"
        echo "# Test Project" > README.md
        git add README.md
        git commit -m "init" --quiet
    )
    echo "$tmpdir"
}

# Source libraries for direct function testing
# aitask_setup.sh sets SCRIPT_DIR from BASH_SOURCE — we override it after sourcing
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
# Restore SCRIPT_DIR — each test that needs setup_data_branch will set it explicitly
SCRIPT_DIR="$TEST_SCRIPT_DIR"
set +euo pipefail

echo "=== task_git / ait git Tests ==="
echo ""

# --- Test 1: Legacy mode detection ---
echo "--- Test 1: Legacy mode detection ---"

TMPDIR_1="$(setup_local_repo)"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_1" >/dev/null
_ait_detect_data_worktree
assert_eq_trim "Legacy mode: _AIT_DATA_WORKTREE is '.'" "." "$_AIT_DATA_WORKTREE"
popd >/dev/null

rm -rf "$TMPDIR_1"

# --- Test 2: Branch mode detection (.git file) ---
echo "--- Test 2: Branch mode detection (.git file) ---"

TMPDIR_2="$(setup_local_repo)"

mkdir -p "$TMPDIR_2/.aitask-data"
echo "gitdir: ../.git/worktrees/.aitask-data" > "$TMPDIR_2/.aitask-data/.git"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_2" >/dev/null
_ait_detect_data_worktree
assert_eq_trim "Branch mode (.git file): _AIT_DATA_WORKTREE is '.aitask-data'" ".aitask-data" "$_AIT_DATA_WORKTREE"
popd >/dev/null

rm -rf "$TMPDIR_2"

# --- Test 3: Branch mode detection (.git directory) ---
echo "--- Test 3: Branch mode detection (.git directory) ---"

TMPDIR_3="$(setup_local_repo)"

mkdir -p "$TMPDIR_3/.aitask-data/.git"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_3" >/dev/null
_ait_detect_data_worktree
assert_eq_trim "Branch mode (.git dir): _AIT_DATA_WORKTREE is '.aitask-data'" ".aitask-data" "$_AIT_DATA_WORKTREE"
popd >/dev/null

rm -rf "$TMPDIR_3"

# --- Test 4: task_git passthrough in legacy mode ---
echo "--- Test 4: task_git passthrough (legacy) ---"

TMPDIR_4="$(setup_local_repo)"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_4" >/dev/null
tg_toplevel=$(task_git rev-parse --show-toplevel 2>/dev/null)
g_toplevel=$(git rev-parse --show-toplevel 2>/dev/null)
assert_eq_trim "task_git toplevel matches git toplevel" "$g_toplevel" "$tg_toplevel"
popd >/dev/null

rm -rf "$TMPDIR_4"

# --- Test 5: task_git targets worktree in branch mode ---
echo "--- Test 5: task_git targets worktree (branch mode) ---"

TMPDIR_5="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_5/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"

(cd "$TMPDIR_5/local" && setup_data_branch </dev/null >/dev/null 2>&1)

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_5/local" >/dev/null
tg_branch=$(task_git branch --show-current 2>/dev/null)
g_branch=$(git branch --show-current 2>/dev/null)
assert_eq_trim "task_git on aitask-data branch" "aitask-data" "$tg_branch"
assert_eq_trim "git on default branch" "$DEFAULT_BRANCH" "$g_branch"
popd >/dev/null

rm -rf "$TMPDIR_5"

# --- Test 6: ait git in legacy mode ---
echo "--- Test 6: ait git in legacy mode ---"

TMPDIR_6="$(setup_repo_with_remote)"

# Copy ait and aiscripts to test repo
cp "$PROJECT_DIR/ait" "$TMPDIR_6/local/ait"
cp -r "$PROJECT_DIR/.aitask-scripts" "$TMPDIR_6/local/.aitask-scripts"
chmod +x "$TMPDIR_6/local/ait"

(
    cd "$TMPDIR_6/local"
    git add -A && git commit -m "add scripts" --quiet
)

TOTAL=$((TOTAL + 1))
if ait_status_output=$(cd "$TMPDIR_6/local" && ./ait git status 2>/dev/null); then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: ait git status in legacy mode failed"
fi

output=$(cd "$TMPDIR_6/local" && ./ait git branch --show-current 2>/dev/null)
assert_eq_trim "ait git shows default branch (legacy)" "$DEFAULT_BRANCH" "$output"

rm -rf "$TMPDIR_6"

# --- Test 7: ait git in branch mode ---
echo "--- Test 7: ait git in branch mode ---"

TMPDIR_7="$(setup_repo_with_remote)"

# Copy ait and aiscripts
cp "$PROJECT_DIR/ait" "$TMPDIR_7/local/ait"
cp -r "$PROJECT_DIR/.aitask-scripts" "$TMPDIR_7/local/.aitask-scripts"
chmod +x "$TMPDIR_7/local/ait"

(cd "$TMPDIR_7/local" && git add -A && git commit -m "add scripts" --quiet && git push --quiet 2>/dev/null)

# setup_data_branch uses SCRIPT_DIR/.. to find the project root
SCRIPT_DIR="$TMPDIR_7/local/.aitask-scripts"
(cd "$TMPDIR_7/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Create a test file in the data worktree
mkdir -p "$TMPDIR_7/local/.aitask-data/aitasks"
echo "test content" > "$TMPDIR_7/local/.aitask-data/aitasks/test_untracked.md"

# ait git should see changes in the data worktree
ait_output=$(cd "$TMPDIR_7/local" && ./ait git status --porcelain 2>/dev/null)
assert_contains_ci "ait git sees data worktree changes" "aitasks" "$ait_output"

# plain git should NOT see it (gitignored)
git_output=$(cd "$TMPDIR_7/local" && git status --porcelain 2>/dev/null)
assert_not_contains_ci "plain git does NOT see data worktree file" "test_untracked" "$git_output"

# ait git branch should show data branch
ait_branch=$(cd "$TMPDIR_7/local" && ./ait git branch --show-current 2>/dev/null)
assert_eq_trim "ait git on aitask-data branch" "aitask-data" "$ait_branch"

rm -rf "$TMPDIR_7"

# --- Test 8: task_sync pulls remote changes ---
echo "--- Test 8: task_sync pulls remote changes ---"

TMPDIR_8="$(setup_repo_with_remote)"

# Push a change from a second clone
git clone --quiet "$TMPDIR_8/remote.git" "$TMPDIR_8/pc2" 2>/dev/null
(
    cd "$TMPDIR_8/pc2"
    git config user.email "test@test.com"
    git config user.name "Test"
    echo "synced content" > synced_file.txt
    git add synced_file.txt
    git commit -m "add synced file" --quiet
    git push --quiet 2>/dev/null
)

# Sync in the original clone
_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_8/local" >/dev/null
task_sync
assert_file_exists "task_sync pulled synced_file.txt" "$TMPDIR_8/local/synced_file.txt"
popd >/dev/null

rm -rf "$TMPDIR_8"

# --- Test 9: task_push sends changes ---
echo "--- Test 9: task_push sends changes ---"

TMPDIR_9="$(setup_repo_with_remote)"

(
    cd "$TMPDIR_9/local"
    echo "pushed content" > pushed_file.txt
    git add pushed_file.txt
    git commit -m "add pushed file" --quiet
)

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_9/local" >/dev/null
task_push
popd >/dev/null

# Verify by cloning and checking
git clone --quiet "$TMPDIR_9/remote.git" "$TMPDIR_9/verify" 2>/dev/null
assert_file_exists "task_push sent pushed_file.txt to remote" "$TMPDIR_9/verify/pushed_file.txt"

rm -rf "$TMPDIR_9"

# --- Test 10: Caching behavior ---
echo "--- Test 10: Caching behavior ---"

TMPDIR_10="$(setup_local_repo)"

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_10" >/dev/null

# First detection: no .aitask-data, should be legacy
_ait_detect_data_worktree
assert_eq_trim "First detect: legacy mode" "." "$_AIT_DATA_WORKTREE"

# Now create .aitask-data/.git (would trigger branch mode on fresh detection)
mkdir -p ".aitask-data"
echo "gitdir: fake" > ".aitask-data/.git"

# Second detection: should still return cached "." value
_ait_detect_data_worktree
assert_eq_trim "Second detect: still cached as legacy" "." "$_AIT_DATA_WORKTREE"

popd >/dev/null

rm -rf "$TMPDIR_10"

# --- Test 11: Syntax check + shellcheck ---
echo "--- Test 11: Syntax check ---"

TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" 2>/dev/null; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: bash -n task_utils.sh (syntax error)"
fi

if command -v shellcheck &>/dev/null; then
    TOTAL=$((TOTAL + 1))
    sc_errors=$(shellcheck --severity=error "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" 2>&1 | wc -l | tr -d ' ')
    if [[ "$sc_errors" -eq 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: shellcheck found errors in task_utils.sh"
        shellcheck --severity=error "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" 2>&1 | head -20
    fi
fi

# --- Test 12: _ait_data_gitdir resolves from inside a linked worktree (t1616) ---
#
# A task worktree is given the primary's data layout (.aitask-data symlink plus
# the aitasks/aiplans links), so _ait_detect_data_worktree() correctly selects
# BRANCH mode there. But `.git` is a FILE in a linked worktree, so the relative
# admin path `.git/worktrees/-aitask-data` does not exist — and the old
# trailing `[[ -d "$gd" ]] && printf ...` then returned 1. Every caller does
# `gitdir="$(_ait_data_gitdir)"` under `set -e`, so that aborted the caller with
# no output at all: `ait git-health` exited 1 silently from inside a worktree.
#
# Two properties are pinned: the function must ALWAYS exit 0, and it must
# resolve the real git-dir rather than giving up (which would leave
# assert_data_worktree_clean fail-open inside every worktree).
echo "--- Test 12: _ait_data_gitdir inside a linked worktree ---"

TMPDIR_12="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_12/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
(cd "$TMPDIR_12/local" && setup_data_branch </dev/null >/dev/null 2>&1)

# Positive control: it resolves in the primary checkout.
_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_12/local" >/dev/null
primary_rc=0
primary_gitdir="$(_ait_data_gitdir)" || primary_rc=$?
popd >/dev/null
assert_eq_trim "12: exits 0 in the primary checkout" "0" "$primary_rc"
TOTAL=$((TOTAL + 1))
if [[ -n "$primary_gitdir" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 12: no git-dir resolved in the primary checkout"
fi

# Now the linked worktree, given the same data layout.
git -C "$TMPDIR_12/local" worktree add -q -b aitask/tG \
    "$TMPDIR_12/local/aiwork/tG" HEAD
bash "$PROJECT_DIR/.aitask-scripts/aitask_init_data.sh" \
    --link-worktree "$TMPDIR_12/local/aiwork/tG" >/dev/null 2>&1

_AIT_DATA_WORKTREE=""
pushd "$TMPDIR_12/local/aiwork/tG" >/dev/null
# Precondition: .git really is a file here, so the relative admin path is absent.
assert_eq_trim "12: .git is a file in the linked worktree" "file" \
    "$([[ -f .git ]] && echo file || echo notfile)"
assert_eq_trim "12: relative admin path is absent" "absent" \
    "$([[ -d .git/worktrees/-aitask-data ]] && echo present || echo absent)"
# Branch mode must be selected — that is what makes the old bug reachable.
_ait_detect_data_worktree
assert_eq_trim "12: branch mode detected in the worktree" ".aitask-data" "$_AIT_DATA_WORKTREE"

wt_rc=0
wt_gitdir="$(_ait_data_gitdir)" || wt_rc=$?
popd >/dev/null

assert_eq_trim "12: exits 0 inside the worktree (never aborts a set -e caller)" "0" "$wt_rc"
TOTAL=$((TOTAL + 1))
if [[ -n "$wt_gitdir" && -d "$wt_gitdir" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: 12: git-dir not resolved inside the worktree (got '$wt_gitdir')"
fi

rm -rf "$TMPDIR_12"

# --- Test 13: data-worktree resolution across every cwd shape (t1658_2) ---
#
# CHARACTERIZATION -> FLIPPED. This block pins the answer
# _ait_detect_data_worktree() gives from each cwd shape. It was first written
# against the PRE-fix behaviour (every off-root shape answered "." — a silent
# fall back to legacy mode from inside a branch-mode project, which made the
# 15 data-branch scripts operate on whatever branch the caller happened to be
# on), then flipped to the values below when the resolution ladder landed. The
# pre-fix run is what makes this a demonstrated flip rather than an untested
# green.
#
# The shapes are the four ladder rungs plus the legacy answer:
#   rung 1  repo root of a branch-mode project        -> ".aitask-data"
#   rung 2  any subdirectory of one                   -> <root>/.aitask-data
#   rung 3  inside .aitask-data itself                -> <root>/.aitask-data
#   rung 3  a linked worktree never --link-worktree'd -> <root>/.aitask-data
#   rung 4  a genuine legacy project                  -> "."
echo "--- Test 13: data-worktree resolution across every cwd shape ---"

TMPDIR_13="$(setup_repo_with_remote)"
SCRIPT_DIR="$TMPDIR_13/local/.aitask-scripts"
mkdir -p "$SCRIPT_DIR"
(cd "$TMPDIR_13/local" && setup_data_branch </dev/null >/dev/null 2>&1)
ROOT_13="$TMPDIR_13/local"

# Probe helper: resolve with a cold cache from <dir>, echo the answer.
detect_from() {
    _AIT_DATA_WORKTREE=""
    pushd "$1" >/dev/null || { echo "PUSHD_FAILED"; return 0; }
    _ait_detect_data_worktree
    popd >/dev/null
    printf '%s' "$_AIT_DATA_WORKTREE"
}

# Precondition: the fixture really is a branch-mode project.
assert_eq_trim "13: fixture has a real .aitask-data worktree" "yes" \
    "$([[ -e "$ROOT_13/.aitask-data/.git" ]] && echo yes || echo no)"

# Rung 1 — the repo root. MUST stay the relative ".aitask-data": this is every
# ./ait-dispatched invocation, and the value is byte-identical to pre-fix.
assert_eq_trim "13a: repo root resolves to the relative .aitask-data" \
    ".aitask-data" "$(detect_from "$ROOT_13")"

# Rung 2 — a subdirectory. Pre-fix this was "." and task_sync pulled the CODE
# branch while reporting success.
mkdir -p "$ROOT_13/website"
assert_eq_trim "13b: a subdirectory resolves to the data worktree, not '.'" \
    "$ROOT_13/.aitask-data" "$(detect_from "$ROOT_13/website")"

# Rung 3 — inside the data worktree itself. Its own toplevel is .aitask-data,
# which has no .aitask-data of its own, so rung 2 misses and rung 3 answers.
assert_eq_trim "13c: inside .aitask-data resolves to itself by absolute path" \
    "$ROOT_13/.aitask-data" "$(detect_from "$ROOT_13/.aitask-data")"

# Rung 3 — the crew-worktree case: a linked worktree that was deliberately NOT
# given the data layout (no --link-worktree), so it has no .aitask-data of its
# own and its toplevel is the worktree, not the primary checkout.
git -C "$ROOT_13" worktree add -q -b crew/t1658_2 \
    "$ROOT_13/.aitask-crews/crew-x" HEAD
assert_eq_trim "13d: unlinked linked worktree has no .aitask-data of its own" "absent" \
    "$([[ -e "$ROOT_13/.aitask-crews/crew-x/.aitask-data" ]] && echo present || echo absent)"
assert_eq_trim "13d: unlinked linked worktree resolves to the MAIN checkout's data worktree" \
    "$ROOT_13/.aitask-data" "$(detect_from "$ROOT_13/.aitask-crews/crew-x")"

# Rung 4 — a genuine legacy project, from its root and from a subdirectory.
# This answer is correct today and must not change.
TMPDIR_13L="$(setup_local_repo)"
mkdir -p "$TMPDIR_13L/sub"
assert_eq_trim "13e: legacy project root stays '.'" "." "$(detect_from "$TMPDIR_13L")"
assert_eq_trim "13e: legacy project subdirectory stays '.'" "." "$(detect_from "$TMPDIR_13L/sub")"

# --- 13f: the ladder must never abort a `set -e` caller -------------------
#
# The in-process probes above cannot see this: the file runs `set +euo pipefail`
# before its test bodies, while every framework script runs `set -euo pipefail`.
# An unguarded `root="$(git rev-parse --show-toplevel 2>/dev/null)"` inside the
# ladder exits 128 and kills the caller with NO message from any non-repo cwd.
# So drive a real subprocess and require the sentinel to survive.
NONREPO_13="$(mktemp -d)"
sub_out_13="$(cd "$NONREPO_13" && bash -c '
set -euo pipefail
SCRIPT_DIR="$1"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/task_utils.sh"
_ait_detect_data_worktree
echo "SENTINEL:$_AIT_DATA_WORKTREE"
' _ "$PROJECT_DIR/.aitask-scripts" 2>/dev/null)"
sub_rc_13=$?
assert_eq_trim "13f: set -e caller survives the ladder from a non-repo cwd" \
    "SENTINEL:." "$sub_out_13"
assert_eq_trim "13f: and exits 0, not 128" "0" "$sub_rc_13"
rm -rf "$NONREPO_13"

# --- 13g: the NAMED consumers agree under both spellings ------------------
#
# Rungs 2/3 hand consumers an ABSOLUTE path where rung 1 hands them the relative
# ".aitask-data". Every consumer is either `git -C "$_AIT_DATA_WORKTREE"` or a
# "$_AIT_DATA_WORKTREE/<suffix>" prefix, so the two spellings must name the same
# physical location. This drives the REAL consumer functions, sourced from the
# repo under test — re-deriving their expressions here would only test this
# file's own copy of them.
#
# SCOPE, stated rather than implied: the four path-prefix consumers below, plus
# _ait_data_git and _ait_data_gitdir. aitask_sync.sh's two sites (its `git_args`
# and `_path_state`) are NOT exercised — that script calls main() at import, so
# it cannot be sourced. They are the same "$_AIT_DATA_WORKTREE/<suffix>" prefix
# shape as the four that are; this is a known gap, not claimed coverage.
# shellcheck source=../.aitask-scripts/lib/artifact_manifest.sh
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_manifest.sh"
# shellcheck source=../.aitask-scripts/lib/attachment_meta.sh
source "$PROJECT_DIR/.aitask-scripts/lib/attachment_meta.sh"
# shellcheck source=../.aitask-scripts/lib/attachment_lock.sh
source "$PROJECT_DIR/.aitask-scripts/lib/attachment_lock.sh"
# shellcheck source=../.aitask-scripts/lib/artifact_backends/local.sh
source "$PROJECT_DIR/.aitask-scripts/lib/artifact_backends/local.sh"

# Echo the CANONICAL directory each named consumer resolves to, for a given
# (_AIT_DATA_WORKTREE value, cwd) pair. Presetting the global short-circuits
# detection, so this asserts the consumer contract independently of which rung
# produced the value. `mkdir -p` then `cd && pwd -P` is what makes the
# comparison physical rather than textual: two spellings of one directory
# collapse to the same answer, and two different directories cannot.
consumer_canon() {
    local val="$1" dir="$2" p
    _AIT_DATA_WORKTREE="$val"
    pushd "$dir" >/dev/null || { echo "PUSHD_FAILED"; return 0; }
    for p in "$(artifact_manifest_dir)" "$(attach_meta_dir)" \
             "$(attachment_lock_dir)" "$(_artifact_local_root)"; do
        mkdir -p "$p"
        (cd "$p" && pwd -P)
    done
    popd >/dev/null
    _AIT_DATA_WORKTREE=""
}

consumers_rel_root_13="$(consumer_canon ".aitask-data" "$ROOT_13")"
consumers_abs_sub_13="$(consumer_canon "$ROOT_13/.aitask-data" "$ROOT_13/website")"

# The contract: the absolute value used off-root names exactly what the relative
# value names at the root, for every consumer.
assert_eq_trim "13g: all four named consumers agree under both spellings" \
    "$consumers_rel_root_13" "$consumers_abs_sub_13"
assert_eq_trim "13g: and there really were four of them" "4" \
    "$(printf '%s\n' "$consumers_rel_root_13" | grep -c .)"

# NEGATIVE CONTROL — without it the assertion above could not fail. The RELATIVE
# spelling used from a subdirectory is precisely the pre-ladder bug: it resolves
# under website/, not under the data worktree. If this matched, the comparison
# would be blind to the prefix and the assertion above would be worthless.
consumers_rel_sub_13="$(consumer_canon ".aitask-data" "$ROOT_13/website")"
assert_eq_trim "13g: negative control — the relative spelling off-root does NOT agree" \
    "differs" \
    "$([[ "$consumers_rel_sub_13" == "$consumers_rel_root_13" ]] && echo "MATCHED" || echo "differs")"

# The `git -C` consumers, driven from a SUBDIRECTORY with the absolute value.
_AIT_DATA_WORKTREE="$ROOT_13/.aitask-data"
pushd "$ROOT_13/website" >/dev/null
abs_branch_13="$(_ait_data_git rev-parse --abbrev-ref HEAD 2>/dev/null)"
# _ait_data_gitdir's relative fast path (.git/worktrees/-aitask-data) cannot hit
# from here, so this exercises its `git -C ... --absolute-git-dir` fallback.
gitdir_rc_13=0
abs_gitdir_13="$(_ait_data_gitdir)" || gitdir_rc_13=$?
popd >/dev/null
_AIT_DATA_WORKTREE=""

assert_eq_trim "13g: _ait_data_git reaches the data branch from a subdirectory" \
    "aitask-data" "$abs_branch_13"
assert_eq_trim "13g: _ait_data_gitdir exits 0 off-root" "0" "$gitdir_rc_13"
assert_eq_trim "13g: _ait_data_gitdir resolves a real git-dir off-root" "dir" \
    "$([[ -n "$abs_gitdir_13" && -d "$abs_gitdir_13" ]] && echo dir || echo "missing:$abs_gitdir_13")"

unset -f detect_from consumer_canon
rm -rf "$TMPDIR_13" "$TMPDIR_13L"

# --- Test 14: indeterminate topology REFUSES, never falls back (t1658_2) ---
#
# ait_main_worktree_root() has three states, and rung 3 must not conflate them.
# `git init --separate-git-dir` is a documented layout that answers 2
# ("inside a repository, but the root could not be resolved" — the KNOWN LAYOUT
# BOUNDARY note in data_symlinks.sh). An unlinked linked worktree of such a
# BRANCH-MODE primary reaches rung 3 with state 2, and a ladder that treated 2
# as "fall through to legacy" would answer "." there and commit task data to
# that worktree's own code branch — reinstating the very bug this ladder
# removes, in a different layout.
#
# The contract is therefore: REFUSE loudly, never answer legacy silently. Driven
# as real subprocesses because the refusal is a die().
echo "--- Test 14: indeterminate topology refuses instead of falling back ---"

TMPDIR_14="$(mktemp -d)"

# (A) A BRANCH-MODE primary with a SEPARATE git dir, plus an unlinked worktree.
mkdir -p "$TMPDIR_14/a_primary" "$TMPDIR_14/a_gitdir"
git init --quiet --separate-git-dir "$TMPDIR_14/a_gitdir" "$TMPDIR_14/a_primary"
(
    cd "$TMPDIR_14/a_primary" || exit 1
    git config user.email "test@test.com"; git config user.name "Test"
    echo code > f.txt; git add f.txt; git commit --quiet -m init
    git worktree add -q -b aitask-data .aitask-data
    git worktree add -q -b crew-x "$TMPDIR_14/a_crew"
) >/dev/null 2>&1

# (B) A LEGACY project with a SEPARATE git dir and no .aitask-data at all.
# This is the NEGATIVE CONTROL for the refusal: it also reaches state 2, and it
# must still resolve to "." — a blanket refusal on state 2 would break every
# legacy --separate-git-dir project, which is a real regression, not a fix.
mkdir -p "$TMPDIR_14/b_primary" "$TMPDIR_14/b_gitdir"
git init --quiet --separate-git-dir "$TMPDIR_14/b_gitdir" "$TMPDIR_14/b_primary"
(
    cd "$TMPDIR_14/b_primary" || exit 1
    git config user.email "test@test.com"; git config user.name "Test"
    echo code > f.txt; git add f.txt; git commit --quiet -m init
    mkdir -p sub
) >/dev/null 2>&1

# Probe helper: a real subprocess under `set -euo pipefail`, so a die() shows up
# as a non-zero status with no ANSWER line.
detect_subproc_14() {
    (cd "$1" && bash -c '
set -euo pipefail
SCRIPT_DIR="$1"
# shellcheck disable=SC1091
source "$SCRIPT_DIR/lib/task_utils.sh"
_ait_detect_data_worktree
echo "ANSWER:$_AIT_DATA_WORKTREE"
' _ "$PROJECT_DIR/.aitask-scripts" 2>&1)
}

# Preconditions: the layout really is the one under test.
assert_eq_trim "14: (A) primary is branch mode" "yes" \
    "$([[ -e "$TMPDIR_14/a_primary/.aitask-data/.git" ]] && echo yes || echo no)"
assert_eq_trim "14: (A) the crew worktree has no .aitask-data of its own" "absent" \
    "$([[ -e "$TMPDIR_14/a_crew/.aitask-data" ]] && echo present || echo absent)"

a_out_14="$(detect_subproc_14 "$TMPDIR_14/a_crew")"
a_rc_14=$?

# The load-bearing pair: it must NOT answer, and it must fail.
assert_eq_trim "14: (A) never silently answers legacy" "no-answer" \
    "$(printf '%s' "$a_out_14" | grep -q '^ANSWER:' && echo "ANSWERED:$a_out_14" || echo "no-answer")"
assert_eq_trim "14: (A) refuses with a non-zero status" "nonzero" \
    "$([[ "$a_rc_14" -ne 0 ]] && echo nonzero || echo "zero")"
assert_contains_ci "14: (A) the refusal names the cause" "could not be resolved" "$a_out_14"

# NEGATIVE CONTROL: a legacy --separate-git-dir project still resolves.
b_out_14="$(detect_subproc_14 "$TMPDIR_14/b_primary/sub")"
b_rc_14=$?
assert_eq_trim "14: (B) legacy separate-git-dir still answers '.'" "ANSWER:." "$b_out_14"
assert_eq_trim "14: (B) and exits 0 — the refusal is not blanket" "0" "$b_rc_14"

# And rung 1 is untouched by any of this.
c_out_14="$(detect_subproc_14 "$TMPDIR_14/a_primary")"
assert_eq_trim "14: (C) the branch-mode root still answers '.aitask-data'" \
    "ANSWER:.aitask-data" "$c_out_14"

unset -f detect_subproc_14
rm -rf "$TMPDIR_14"

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
