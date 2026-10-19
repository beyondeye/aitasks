#!/usr/bin/env bash
# test_ait_git_gateway_pull.sh - `./ait git pull` through the real dispatcher (t1739)
# Run: bash tests/test_ait_git_gateway_pull.sh
#
# Every case runs the copied `ait` dispatcher in a branch-mode fixture (a real
# .aitask-data worktree on the aitask-data branch, upstream origin/aitask-data),
# so what is tested is the gateway as a user reaches it — routing, guard, owned
# pull, cleanup and reporting together. The library-level halves live in
# tests/test_task_git.sh (parser, guard) and tests/test_task_push.sh (the
# shared pull core and its postcondition).

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()
HOLDER_PID=""

# Developer git config never reaches this file — pull.rebase, rebase.autoStash
# and user.* would all change what these cases mean. AFTER the counter init, so
# a failed probe is counted.
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
assert_git_config_isolated

cleanup() {
    [[ -n "$HOLDER_PID" ]] && kill "$HOLDER_PID" 2>/dev/null
    local d
    for d in "${CLEANUP_DIRS[@]}"; do rm -rf "$d" 2>/dev/null; done
}
trap cleanup EXIT

# setup_data_branch lives in aitask_setup.sh, which needs task_utils.sh.
SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
source "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

assert_nonzero() {
    local desc="$1" rc="$2"
    TOTAL=$((TOTAL + 1))
    if [[ "$rc" -ne 0 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc (expected a non-zero exit, got 0)"
    fi
}

# --- Fixture -----------------------------------------------------------------

# Build a fresh branch-mode project. Sets FX (tmp root), FX_REMOTE, FX_LOCAL,
# DATA (the data worktree) and GD (its admin git-dir).
make_fixture() {
    FX="$(mktemp -d "${TMPDIR:-/tmp}/ait_gwpull_XXXXXX")"
    CLEANUP_DIRS+=("$FX")
    FX_REMOTE="$FX/remote.git"
    FX_LOCAL="$FX/local"
    git init --bare --quiet "$FX_REMOTE"
    git clone --quiet "$FX_REMOTE" "$FX_LOCAL" 2>/dev/null
    git -C "$FX_LOCAL" config user.email "test@test.com"
    git -C "$FX_LOCAL" config user.name "Test"
    echo "# fixture" > "$FX_LOCAL/README.md"
    git -C "$FX_LOCAL" add README.md
    git -C "$FX_LOCAL" commit -m "init" --quiet
    git -C "$FX_LOCAL" push --quiet origin HEAD 2>/dev/null
    # The framework is copied, not committed: the cases are about the data
    # branch, and the code branch's status plays no part in them.
    cp "$PROJECT_DIR/ait" "$FX_LOCAL/ait"
    cp -r "$PROJECT_DIR/.aitask-scripts" "$FX_LOCAL/.aitask-scripts"
    chmod +x "$FX_LOCAL/ait"
    printf '/ait\n/.aitask-scripts/\n' >> "$FX_LOCAL/.git/info/exclude"
    SCRIPT_DIR="$FX_LOCAL/.aitask-scripts"
    (cd "$FX_LOCAL" && setup_data_branch </dev/null >/dev/null 2>&1)
    # shellcheck disable=SC2034  # read by the sourced aitask_setup.sh / task_utils.sh
    SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
    DATA="$FX_LOCAL/.aitask-data"
    GD="$(git -C "$DATA" rev-parse --absolute-git-dir 2>/dev/null)"
    # A precondition that can fail silently is not a precondition.
    assert_eq_trim "fixture: data worktree tracks origin/aitask-data" "origin/aitask-data" \
        "$(git -C "$DATA" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"
}

# Commit <file> = <content> on the remote aitask-data branch from a second
# clone. Verifies the remote actually advanced.
remote_commit() {
    local file="$1" content="$2" tmp before after
    before="$(git -C "$FX_REMOTE" rev-parse refs/heads/aitask-data 2>/dev/null)"
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/ait_gwpull_other_XXXXXX")"
    git clone --quiet -b aitask-data "$FX_REMOTE" "$tmp/other" 2>/dev/null
    git -C "$tmp/other" config user.email "other@test.com"
    git -C "$tmp/other" config user.name "Other"
    mkdir -p "$(dirname "$tmp/other/$file")"
    printf '%s\n' "$content" > "$tmp/other/$file"
    git -C "$tmp/other" add -A
    git -C "$tmp/other" commit -m "remote: $file" --quiet
    git -C "$tmp/other" push --quiet 2>/dev/null
    rm -rf "$tmp"
    after="$(git -C "$FX_REMOTE" rev-parse refs/heads/aitask-data 2>/dev/null)"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$after" && "$after" != "$before" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: fixture: remote_commit $file did not advance the remote"
    fi
}

local_commit() {
    local file="$1" content="$2"
    mkdir -p "$(dirname "$DATA/$file")"
    printf '%s\n' "$content" > "$DATA/$file"
    git -C "$DATA" add -A
    git -C "$DATA" commit -m "local: $file" --quiet
}

# Local commit + a different remote body for the same non-task file: the next
# rebase stops on a content conflict the auto-merge cannot resolve.
force_conflict() {
    remote_commit conflict.txt "remote"
    local_commit conflict.txt "local"
}

# Re-implemented from `ls` rather than calling the library helper under test.
probe_wedge() {
    local s
    for s in rebase-merge rebase-apply MERGE_HEAD CHERRY_PICK_HEAD REVERT_HEAD BISECT_LOG; do
        [[ -e "$GD/$s" ]] && { printf '%s' "$s"; return 0; }
    done
    printf ''
}

# Run `./ait git <args>` in the fixture. Sets RC and ERR (stdout is discarded:
# every assertion here is about the exit status and what was reported on stderr).
run_ait() {
    local e="$FX/run_err"
    (cd "$FX_LOCAL" && ./ait git "$@") >/dev/null 2>"$e"
    RC=$?
    ERR="$(cat "$e")"
}

# The reason code the gateway warned with, or "".
gateway_reason() {
    printf '%s\n' "$ERR" | sed -n 's/.*did not complete (\([a-z_]*\)).*/\1/p' | head -n1
}

# Does a later `./ait git commit` succeed? (A leftover wedge makes the guard
# refuse it — the incident this whole change closes.)
next_commit_rc() {
    local name="probe_$RANDOM.txt"
    echo "after" > "$DATA/$name"
    (cd "$FX_LOCAL" && ./ait git add "$name" && ./ait git commit -m "probe" --quiet -- "$name") \
        >/dev/null 2>&1
    echo $?
}

# The observable outcome of a conflicted gateway pull, as one comparable tuple.
pull_outcome() {
    printf 'nonzero=%s|wedge=%s|lock=%s|reason=%s|next=%s' \
        "$([[ $RC -ne 0 ]] && echo 1 || echo 0)" \
        "$(probe_wedge)" \
        "$([[ -e "$GD/aitask-pull.lock" ]] && echo present || echo absent)" \
        "$(gateway_reason)" \
        "$(next_commit_rc)"
}

echo "=== ./ait git pull gateway Tests ==="
echo ""

# --- Test A: the bare form cleans up its own conflicted rebase ---
echo "--- Test A: ./ait git pull --rebase under a conflict -> no wedge ---"
make_fixture
force_conflict
assert_eq_trim "A: control — clean before the pull" "" "$(probe_wedge)"
run_ait pull --rebase
assert_nonzero "A: the conflicted pull exits non-zero" "$RC"
outcome_A="$(pull_outcome)"
assert_eq "A: outcome — no wedge, no lock, rebase_conflict, next commit works" \
    "nonzero=1|wedge=|lock=absent|reason=rebase_conflict|next=0" "$outcome_A"
assert_contains "A: the abort is reported" "rebase aborted after conflict" "$ERR"

# --- Test A2: an explicit autostash flag is refused before anything runs ---
# Same fixture: push a new remote commit, then prove neither HEAD nor the
# remote-tracking ref moved — nothing was fetched or pulled.
echo "--- Test A2: --autostash (and an abbreviation) is refused ---"
remote_commit later.txt "later"
head_A2="$(git -C "$DATA" rev-parse HEAD)"
track_A2="$(git -C "$DATA" rev-parse origin/aitask-data)"
for flag_A2 in --autostash --au; do
    run_ait pull --rebase "$flag_A2"
    assert_nonzero "A2 ($flag_A2): refused" "$RC"
    assert_contains "A2 ($flag_A2): the message names the flag" "'$flag_A2' is not supported" "$ERR"
    assert_eq "A2 ($flag_A2): HEAD did not move" "$head_A2" "$(git -C "$DATA" rev-parse HEAD)"
    assert_eq "A2 ($flag_A2): nothing was fetched" "$track_A2" \
        "$(git -C "$DATA" rev-parse origin/aitask-data)"
done

# --- Test B: the option-prefixed form behaves exactly like the bare form ---
# Compared against A's computed tuple, not a hand-written one, so the two cannot
# drift apart.
echo "--- Test B: ./ait git -c core.pager=cat pull --rebase == the bare form ---"
make_fixture
force_conflict
run_ait -c core.pager=cat pull --rebase
assert_eq "B: same outcome as the bare form" "$outcome_A" "$(pull_outcome)"

# --- Test C: merge mode — bounded, reported truthfully ---
echo "--- Test C: ./ait git -c pull.rebase=false pull -> MERGE_HEAD, data_midop ---"
make_fixture
force_conflict
run_ait -c pull.rebase=false pull
assert_nonzero "C: the conflicted merge-mode pull exits non-zero" "$RC"
assert_eq_trim "C: MERGE_HEAD is left in place (the documented bound)" "MERGE_HEAD" "$(probe_wedge)"
assert_eq "C: reported as data_midop" "data_midop" "$(gateway_reason)"
# The discriminator: OUR lines (sentinels and the warning) must not describe a
# merge as a rebase nor hand it `rebase --abort`. git's own lines are git's.
ours_C="$(printf '%s\n' "$ERR" | grep -E '^aitask:|did not complete' || true)"
assert_contains "C: our sentinel names the actual state" "mid-MERGE_HEAD" "$ours_C"
assert_not_contains "C: no line of ours says 'rebase'" "rebase" "$ours_C"
rm -f "$GD/MERGE_HEAD" "$GD/MERGE_MSG" "$GD/MERGE_MODE"

# --- Test D: a pre-existing wedge is refused by the guard, never touched ---
echo "--- Test D: pre-existing foreign rebase -> guard refuses, wedge survives ---"
make_fixture
mkdir -p "$GD/rebase-merge"
echo "0000000000000000000000000000000000000000" > "$GD/rebase-merge/orig-head"
run_ait pull --rebase
assert_nonzero "D: refused" "$RC"
assert_contains "D: by the wedged-worktree guard" "stuck mid-rebase-merge" "$ERR"
assert_eq_trim "D: the foreign rebase is still there" "rebase-merge" "$(probe_wedge)"
# The latent recovery bug through the real dispatcher: the advertised recovery,
# behind a global option, is now let through by the guard.
run_ait -c core.pager=cat rebase --abort
assert_not_contains "D: -c ... rebase --abort reaches git — the guard did not refuse it" \
    "stuck mid-" "$ERR"
rm -rf "$GD/rebase-merge"

# --- Test E: repository-redirecting options are refused; -c is kept ---
echo "--- Test E: -C / --git-dir refused at the gateway, -c preserved ---"
run_ait -C /tmp status
assert_nonzero "E: -C is refused" "$RC"
assert_contains "E: ... naming the option" "'-C' points git away" "$ERR"
run_ait --git-dir=/nonexistent pull
assert_nonzero "E: --git-dir=... is refused" "$RC"
assert_contains "E: ... naming the option without its value" "'--git-dir' points git away" "$ERR"
run_ait -c core.pager=cat status --porcelain
assert_eq "E: -c name=value still runs" "0" "$RC"

# --- Test F: another managed pull holds the mutex ---
echo "--- Test F: pull mutex held by a live session -> pull_locked, nothing pulled ---"
make_fixture
remote_commit other.txt "other"
head_F="$(git -C "$DATA" rev-parse HEAD)"
bash -c 'source "$1"; stale_lock_acquire "$2" 3 0.05 "test holder" && touch "$3" && sleep 60' \
    _ "$PROJECT_DIR/.aitask-scripts/lib/stale_lock.sh" "$GD/aitask-pull.lock" "$FX/held" &
HOLDER_PID=$!
for _ in $(seq 1 50); do [[ -e "$FX/held" ]] && break; sleep 0.1; done
assert_eq "F: precondition — a live holder owns the mutex" "yes" \
    "$([[ -e "$FX/held" ]] && echo yes || echo no)"
run_ait pull --rebase
assert_nonzero "F: the pull is skipped with a non-zero exit" "$RC"
assert_eq "F: reported as pull_locked" "pull_locked" "$(gateway_reason)"
assert_eq "F: nothing was pulled" "$head_F" "$(git -C "$DATA" rev-parse HEAD)"
kill "$HOLDER_PID" 2>/dev/null; wait "$HOLDER_PID" 2>/dev/null; HOLDER_PID=""
rm -rf "$GD/aitask-pull.lock"

# --- Test G: autostash from config is overridden ---
# A dirty tracked file overlapping the incoming change. Through raw git with
# autostash this returns 0 and leaves an unmerged index (the control, run LAST
# because it mutates the fixture); through the gateway the pull must refuse.
echo "--- Test G: rebase.autoStash=true (repo config and -c) -> refused, nothing stashed ---"
make_fixture
remote_commit f.txt "base"
git -C "$DATA" pull --quiet --rebase 2>/dev/null
remote_commit f.txt "remote change"
printf 'local dirty edit\n' > "$DATA/f.txt"
dirty_sha_G="$(git -C "$DATA" hash-object f.txt)"

g_check() {   # <label>
    assert_nonzero "G ($1): the pull refuses" "$RC"
    assert_eq "G ($1): reported as dirty_worktree" "dirty_worktree" "$(gateway_reason)"
    assert_eq "G ($1): no unmerged path" "" "$(git -C "$DATA" diff --name-only --diff-filter=U)"
    assert_eq "G ($1): nothing was stashed" "" "$(git -C "$DATA" stash list)"
    assert_eq "G ($1): the dirty edit is byte-identical" "$dirty_sha_G" \
        "$(git -C "$DATA" hash-object f.txt)"
}
git -C "$DATA" config rebase.autoStash true
run_ait pull --rebase
g_check "inherited repo config"
git -C "$DATA" config --unset rebase.autoStash
run_ait -c rebase.autoStash=true pull --rebase
g_check "-c on the command line"

# Control: the same fixture through raw git reproduces the hazard.
git -C "$DATA" -c rebase.autoStash=true pull --rebase --quiet >/dev/null 2>&1
raw_rc_G=$?
assert_eq "G control: raw autostash pull returns 0" "0" "$raw_rc_G"
TOTAL=$((TOTAL + 1))
if [[ -n "$(git -C "$DATA" diff --name-only --diff-filter=U)" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1)); echo "FAIL: G control: raw autostash pull left no unmerged path (fixture does not reproduce the hazard)"
fi

# --- Test H: interactive rebase is refused before anything runs ---
# The captured gateway takes the terminal from the sequence editor, and an
# `edit` stop would end the pull with rc 0 mid-rebase. So every route that
# selects interactive mode — arguments, either config level, the user's own -c
# or --config-env — is refused up front. A logging sequence editor proves the
# rebase never started; HEAD and the tracking ref prove nothing was fetched.
echo "--- Test H: interactive mode (arguments or config) refused up front ---"
make_fixture
remote_commit other.txt "other"
local_commit mine.txt "mine"
ED_H="$FX/seq_editor.sh"
printf '#!/bin/sh\necho invoked >> "%s"\n' "$FX/seq_editor.log" > "$ED_H"
chmod +x "$ED_H"
head_H="$(git -C "$DATA" rev-parse HEAD)"
track_H="$(git -C "$DATA" rev-parse origin/aitask-data)"

h_refused() {   # <label>
    assert_nonzero "H ($1): refused" "$RC"
    assert_contains "H ($1): names the reason" "interactive rebase is not supported" "$ERR"
    assert_eq "H ($1): the sequence editor never ran" "no" \
        "$([[ -e "$FX/seq_editor.log" ]] && echo yes || echo no)"
    assert_eq "H ($1): HEAD did not move" "$head_H" "$(git -C "$DATA" rev-parse HEAD)"
    assert_eq "H ($1): nothing was fetched" "$track_H" "$(git -C "$DATA" rev-parse origin/aitask-data)"
    assert_eq_trim "H ($1): no wedge" "" "$(probe_wedge)"
}
export GIT_SEQUENCE_EDITOR="$ED_H"
run_ait pull --rebase=interactive;                h_refused "--rebase=interactive"
run_ait pull -qri;                                h_refused "-qri (short cluster)"
# A value-taking option consumes the next token: these later `--rebase` tokens
# are a server option / strategy option, NOT a mode override — git still runs
# the interactive rebase, so the gateway must still refuse.
run_ait pull --rebase=interactive --server-option --rebase
h_refused "--server-option consumes a later --rebase"
run_ait pull --rebase=interactive --strategy-option --rebase
h_refused "--strategy-option consumes a later --rebase"
run_ait pull --rebase=interactive --server --rebase
h_refused "abbreviated --server consumes a later --rebase"
run_ait -c pull.rebase=interactive pull;          h_refused "-c pull.rebase=interactive"
PR_H=interactive run_ait --config-env=pull.rebase=PR_H pull
h_refused "--config-env=pull.rebase=PR_H"
git -C "$DATA" config branch.aitask-data.rebase i
run_ait pull;                                     h_refused "branch.aitask-data.rebase=i"
# Precedence: branch config beats pull.rebase, exactly as git applies it.
git -C "$DATA" config pull.rebase true
run_ait pull;                                     h_refused "branch config over pull.rebase=true"
git -C "$DATA" config --unset pull.rebase
git -C "$DATA" config --unset branch.aitask-data.rebase

# Control: an explicit --rebase overrides an interactive config (git's own rule),
# so that pull is allowed and completes non-interactively.
run_ait -c pull.rebase=interactive pull --rebase
assert_eq "H control: --rebase over an interactive config pulls (exit 0)" "0" "$RC"
assert_eq "H control: ... non-interactively" "no" \
    "$([[ -e "$FX/seq_editor.log" ]] && echo yes || echo no)"
assert_eq "H control: ... and it really pulled" "$(git -C "$DATA" rev-parse origin/aitask-data)" \
    "$(git -C "$DATA" merge-base HEAD origin/aitask-data)"
unset GIT_SEQUENCE_EDITOR

# --- Test K: no merge-message editor ever opens ---
# Under a real terminal plain git opens the merge editor for a non-conflicting
# merge-mode pull. The gateway captures git's output, so an editor would get no
# terminal: it forces --no-edit (beating GIT_MERGE_AUTOEDIT=yes) and refuses a
# user --edit before anything is fetched. Driven under a real PTY
# (tests/lib/pty_drive.py), so stdin is a terminal exactly as for a user.
echo "--- Test K: merge-mode pull never opens an editor (real PTY) ---"
make_fixture
remote_commit other.txt "other"
local_commit mine.txt "mine"
ED_K="$FX/merge_editor.sh"
printf '#!/bin/sh\necho invoked >> "%s"\n' "$FX/merge_editor.log" > "$ED_K"
chmod +x "$ED_K"
export GIT_EDITOR="$ED_K"
PTY_K="$PROJECT_DIR/tests/lib/pty_drive.py"
editor_ran_K() { [[ -e "$FX/merge_editor.log" ]] && echo yes || echo no; }

# Control: plain git under the same PTY opens the editor — the fixture is real.
(cd "$DATA" && python3 "$PTY_K" --answers '' -- git pull --no-rebase) >/dev/null 2>&1
assert_eq "K control: plain git under a PTY opens the merge editor" "yes" "$(editor_ran_K)"
git -C "$DATA" reset --hard --quiet ORIG_HEAD
rm -f "$FX/merge_editor.log"
# The control fetched, so origin/aitask-data is already current. Advance the
# remote again, so "nothing was fetched" below can actually fail if a refused
# pull fetched before refusing.
remote_commit other2.txt "other2"
head_K="$(git -C "$DATA" rev-parse HEAD)"
track_K="$(git -C "$DATA" rev-parse origin/aitask-data)"

# --edit is refused before anything runs, in every spelling git accepts,
# including when it is the LAST of an --edit/--no-edit pair.
for args_K in "--no-rebase --edit" "--no-rebase --ed" "--no-rebase --no-edit --edit"; do
    read -r -a argv_K <<< "$args_K"
    (cd "$FX_LOCAL" && python3 "$PTY_K" --answers '' -- ./ait git pull "${argv_K[@]}") \
        > "$FX/k_out" 2>&1
    rc_K=$?
    assert_nonzero "K ($args_K): refused" "$rc_K"
    assert_contains "K ($args_K): names the reason" "is not supported" "$(cat "$FX/k_out")"
    assert_eq "K ($args_K): the editor never ran" "no" "$(editor_ran_K)"
    assert_eq "K ($args_K): HEAD did not move" "$head_K" "$(git -C "$DATA" rev-parse HEAD)"
    assert_eq "K ($args_K): nothing was fetched" "$track_K" \
        "$(git -C "$DATA" rev-parse origin/aitask-data)"
    assert_eq_trim "K ($args_K): no MERGE_HEAD" "" "$(probe_wedge)"
done

# Accepted: a merge-mode pull completes with git's default message and no
# editor — even with GIT_MERGE_AUTOEDIT=yes, which forces one in plain git.
(cd "$FX_LOCAL" && GIT_MERGE_AUTOEDIT=yes python3 "$PTY_K" --answers '' -- ./ait git pull --no-rebase) \
    >/dev/null 2>&1
rc_K=$?
assert_eq "K: the merge-mode pull completes (exit 0)" "0" "$rc_K"
assert_eq "K: ... without opening an editor" "no" "$(editor_ran_K)"
assert_eq_trim "K: ... leaving no MERGE_HEAD" "" "$(probe_wedge)"
assert_eq "K: ... as a real merge commit" "2" \
    "$(git -C "$DATA" log -1 --format=%p | wc -w | tr -d ' ')"
unset GIT_EDITOR

# --- Test L: a merge that stops for a NON-conflict reason ---
# A refusing pre-merge-commit hook stops a non-conflicting merge-mode pull with
# MERGE_HEAD in place and no conflict text. The cleanup must leave it alone and
# name it as the merge it is: data_midop with the merge recovery hint — never
# rebase wording, never `rebase --abort` / `--continue` advice.
echo "--- Test L: non-conflict merge failure -> data_midop, no rebase wording ---"
make_fixture
remote_commit other.txt "other"
local_commit mine.txt "mine"
HOOK_L="$(git -C "$DATA" rev-parse --git-path hooks/pre-merge-commit)"
case "$HOOK_L" in /*) ;; *) HOOK_L="$DATA/$HOOK_L" ;; esac
mkdir -p "$(dirname "$HOOK_L")"
printf '#!/bin/sh\necho "pre-merge-commit: refused by test hook" >&2\nexit 1\n' > "$HOOK_L"
chmod +x "$HOOK_L"
run_ait pull --no-rebase
assert_nonzero "L: the stopped merge exits non-zero" "$RC"
assert_contains "L: precondition — the hook really refused" "refused by test hook" "$ERR"
assert_eq_trim "L: MERGE_HEAD is left in place" "MERGE_HEAD" "$(probe_wedge)"
assert_eq "L: reported as data_midop" "data_midop" "$(gateway_reason)"
ours_L="$(printf '%s\n' "$ERR" | grep -E '^aitask:|did not complete' || true)"
assert_contains "L: our sentinel names the actual state" "mid-MERGE_HEAD" "$ours_L"
assert_contains "L: the hint gives merge recovery" "--abort" "$ours_L"
assert_not_contains "L: no line of ours says 'rebase'" "rebase" "$ours_L"
rm -f "$HOOK_L"

# --- Test I: the user's -c config reaches the continuation ---
# A frontmatter-only task conflict the auto-merge resolves, in a repo with no
# identity configured. The replay's `rebase --continue` needs the identity the
# user supplied with -c; without it the continue fails, the rebase is aborted
# and the pull exits non-zero.
echo "--- Test I: -c user.* is carried through the auto-merge continue ---"
make_fixture
write_task_I() {   # <path> <boardcol> <labels>
    mkdir -p "$(dirname "$1")"
    printf -- '---\npriority: high\nstatus: Ready\nboardcol: %s\nlabels: %s\nupdated_at: 2026-01-01 10:00\n---\nTask body stays the same\n' \
        "$2" "$3" > "$1"
}
tmp_I="$(mktemp -d "${TMPDIR:-/tmp}/ait_gwpull_I_XXXXXX")"; CLEANUP_DIRS+=("$tmp_I")
git clone --quiet -b aitask-data "$FX_REMOTE" "$tmp_I/o" 2>/dev/null
git -C "$tmp_I/o" config user.email "other@test.com"; git -C "$tmp_I/o" config user.name "Other"
write_task_I "$tmp_I/o/aitasks/t1_sample.md" backlog "[ui]"
git -C "$tmp_I/o" add -A; git -C "$tmp_I/o" commit -m "seed" --quiet; git -C "$tmp_I/o" push --quiet 2>/dev/null
git -C "$DATA" pull --quiet --rebase 2>/dev/null
write_task_I "$tmp_I/o/aitasks/t1_sample.md" now "[ui]"
git -C "$tmp_I/o" commit -am "remote: boardcol" --quiet; git -C "$tmp_I/o" push --quiet 2>/dev/null
write_task_I "$DATA/aitasks/t1_sample.md" backlog "[api, ui]"
git -C "$DATA" commit -am "local: labels" --quiet
# No identity from anywhere but the command line.
git -C "$FX_LOCAL" config --unset user.email
git -C "$FX_LOCAL" config --unset user.name
git -C "$FX_LOCAL" config user.useConfigOnly true
(
    unset EMAIL GIT_AUTHOR_NAME GIT_AUTHOR_EMAIL GIT_COMMITTER_NAME GIT_COMMITTER_EMAIL
    run_ait -c user.name=T -c user.email=t@t.example pull --rebase
    printf '%s\n%s\n' "$RC" "$ERR" > "$FX/I_result"
)
rc_I="$(head -n1 "$FX/I_result")"
err_I="$(tail -n +2 "$FX/I_result")"
assert_eq "I: the pull completes (exit 0)" "0" "$rc_I"
assert_contains "I: through the auto-merge" "auto-merged task-data conflict(s) during pull" "$err_I"
assert_eq_trim "I: no wedge" "" "$(probe_wedge)"
assert_eq "I: the replayed commit carries the supplied committer" "t@t.example" \
    "$(git -C "$DATA" log -1 --format=%ce)"

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
