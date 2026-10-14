#!/usr/bin/env bash
# test_sync_autostash_ignored.sh - `ait sync` never stashes, and never lets a
# fast-forward overwrite an ignored file (t1792).
#
# Run: bash tests/test_sync_autostash_ignored.sh
#
# THREE DEFECTS, ONE CELL FAMILY EACH.
#   autostash  `pull --rebase` honoured a user's rebase.autoStash and the
#              behind-only `merge --ff-only` honoured merge.autoStash: both
#              stashed and re-applied the files the sweep left protected.
#              Pinned by setting the config PER REPO, which the fixture's global
#              isolation leaves in place, and proving the protected file was
#              never rewritten (inode + ctime, not just bytes: a stash round trip
#              restores the bytes).
#   ignored    the behind-only fast-forward ran with git's default
#              --overwrite-ignore, and the `pull --rebase` it fell back to
#              overwrote too. Every behind-only pull is now a fast-forward to a
#              PINNED upstream SHA with --no-overwrite-ignore, and a refusal is
#              reported, never retried as a rebase.
#   isolation  run_sync inherited the developer's global git config.
#
# The diverged route (`pull --rebase`) can still overwrite an ignored file an
# incoming commit writes; that is a documented limitation, not covered here.
#
# Seams (marker-gated, aitask_sync.sh's seam list): pre_pull runs before the
# pin, pre_pull_apply between the ignored-file check and the fast-forward.

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

UC=aitasks/metadata/userconfig.yaml

# --- Helpers --------------------------------------------------------------

dgit() { local t="$1"; shift; git -C "$t/local/.aitask-data" "$@"; }
dsubject() { dgit "$1" log -1 --format=%s 2>/dev/null; }
remote_sha() { git -C "$1/remote.git" rev-parse refs/heads/aitask-data 2>/dev/null; }
# Hash from stdin: given a NAME with a newline or backslash, GNU sha256sum
# escapes it and prefixes the digest with '\'.
sha_of() { { sha256sum < "$1"; } 2>/dev/null | cut -d' ' -f1; }
sha_of_text() { printf '%s' "$1" | sha256sum | cut -d' ' -f1; }
first_line() { printf '%s\n' "$1" | head -n1; }
# inode + ctime: a stash round trip restores the bytes but rewrites the file.
file_ident() {
    python3 -c 'import os,sys; s=os.lstat(sys.argv[1]); print(s.st_ino, s.st_ctime_ns)' "$1" 2>/dev/null
}
# Two-letter porcelain state of one path in the data worktree ("!!" = ignored).
st_of() { dgit "$1" status --porcelain --ignored -- "$2" 2>/dev/null | cut -c1-2; }

# pc2 <tmpdir> <label> <snippet> — commit <snippet>'s changes from a sibling
# clone, push, and fetch them into the local clone. Asserts the remote moved:
# a silently failing helper would leave every later assertion testing nothing.
pc2() {
    local t="$1" label="$2" snippet="$3" before after
    before="$(remote_sha "$t")"
    rm -rf "$t/pc2"
    git clone -q --branch aitask-data "$t/remote.git" "$t/pc2" 2>/dev/null
    (
        cd "$t/pc2" || exit 1
        git config user.email pc2@test.com
        git config user.name PC2
        git config commit.gpgsign false
        mkdir -p aitasks/metadata aiplans
        eval "$snippet"
        git add -A && git commit -q -m "pc2: advance" && git push -q origin aitask-data
    ) >/dev/null 2>&1
    dgit "$t" fetch -q origin 2>/dev/null
    after="$(remote_sha "$t")"
    if [[ -n "$after" && "$after" != "$before" ]]; then
        assert_eq "$label: fixture — pc2 advanced the remote" "advanced" "advanced"
    else
        assert_eq "$label: fixture — pc2 advanced the remote" "advanced" "unchanged"
    fi
}

# A hook snippet (run by a seam, inside the sync process) that pushes a commit
# force-adding userconfig.yaml from a racer clone, then fetches it locally so
# @{u} moves too.
racer_force_add_uc() {
    local t="$1"
    printf '%s' "rm -rf '$t/racer' && git clone -q --branch aitask-data '$t/remote.git' '$t/racer' >/dev/null 2>&1 && git -C '$t/racer' config user.email racer@test.com && git -C '$t/racer' config user.name Racer && git -C '$t/racer' config commit.gpgsign false && mkdir -p '$t/racer/aitasks/metadata' && printf 'email: racer@x.com\n' > '$t/racer/$UC' && git -C '$t/racer' add -f '$UC' && git -C '$t/racer' commit -q -m 'racer: force-add userconfig' && git -C '$t/racer' push -q origin aitask-data >/dev/null 2>&1 && git -C '$t/local/.aitask-data' fetch -q origin"
}

# t10 locked by a LIVE process (this shell) with a tracked edit: the sweep
# leaves it dirty and protected.
protect_t10() {
    plant_lock "$1" 10 "$(lock_yaml_live 10)"
    printf 'edit10\n' >> "$1/local/.aitask-data/aitasks/t10_alpha.md"
}

enable_seams() { mkdir -p "$1/locks" && touch "$1/locks/.ait_sync_test_seams"; }

# run_sync_with_seam <tmpdir> <point> <hook> — run_sync with one seam armed.
run_sync_with_seam() {
    local t="$1" point="$2" hook="$3"
    enable_seams "$t"
    export "AIT_SYNC_SEAM_${point}=$hook"
    run_sync "$t"
    unset "AIT_SYNC_SEAM_${point}"
}

seam_fired() {
    assert_contains "$1: fixture — the $3 seam fired" \
        "TEST SEAM ACTIVE - running $3" "$(sync_err "$2")"
}

echo "=== aitask_sync.sh: no autostash, no ignored-file overwrite (t1792) ==="
echo ""

# --- C1 / C1c: the fast-forward ignores merge.autoStash --------------------
for cfg in on off; do
    label="C1"; [[ "$cfg" == off ]] && label="C1c"
    echo "--- $label: behind-only + protected t10, merge.autoStash=$cfg -> PULLED, t10 never rewritten ---"
    T="$(setup_repo)"
    pc2 "$T" "$label" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
    protect_t10 "$T"
    [[ "$cfg" == on ]] && dgit "$T" config merge.autoStash true
    F="$T/local/.aitask-data/aitasks/t10_alpha.md"
    PRE_SHA="$(sha_of "$F")"; PRE_ID="$(file_ident "$F")"
    OUT="$(run_sync "$T")"
    assert_eq "$label: verdict" "PULLED" "$(first_line "$OUT")"
    assert_eq "$label: HEAD is the remote tip" "$(remote_sha "$T")" "$(data_head "$T")"
    assert_eq "$label: protected t10 bytes unchanged" "$PRE_SHA" "$(sha_of "$F")"
    assert_eq "$label: protected t10 never rewritten (inode+ctime)" "$PRE_ID" "$(file_ident "$F")"
    assert_eq "$label: t10 still dirty" " M" "$(st_of "$T" aitasks/t10_alpha.md)"
done

# --- C2 / C2c: the rebase ignores rebase.autoStash -------------------------
# The pre_pull seam commits a t20 edit after main's gate saw a behind-only
# branch — a holder committing its own work mid-run — so the run reaches the
# rebase with t10 still dirty. Without --no-autostash, rebase.autoStash would
# stash t10, rebase, re-apply it and report SYNCED.
for cfg in on off; do
    label="C2"; [[ "$cfg" == off ]] && label="C2c"
    echo "--- $label: holder commits mid-run, rebase.autoStash=$cfg -> pull refuses, t10 never rewritten ---"
    T="$(setup_repo)"
    pc2 "$T" "$label" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
    protect_t10 "$T"
    [[ "$cfg" == on ]] && dgit "$T" config rebase.autoStash true
    F="$T/local/.aitask-data/aitasks/t10_alpha.md"
    PRE_SHA="$(sha_of "$F")"; PRE_ID="$(file_ident "$F")"
    D="$T/local/.aitask-data"
    OUT="$(run_sync_with_seam "$T" pre_pull \
        "printf 'holder\n' >> '$D/aitasks/t20_beta.md' && git -C '$D' add aitasks/t20_beta.md && git -C '$D' commit -q -m 'holder: commit' -- aitasks/t20_beta.md")"
    seam_fired "$label" "$T" pre_pull
    assert_eq "$label: verdict" "ERROR:pull_rebase_failed" "$(first_line "$OUT")"
    assert_eq "$label: HEAD is still the holder's commit" "holder: commit" "$(dsubject "$T")"
    assert_eq "$label: protected t10 bytes unchanged" "$PRE_SHA" "$(sha_of "$F")"
    assert_eq "$label: protected t10 never rewritten (inode+ctime)" "$PRE_ID" "$(file_ident "$F")"
done

# --- C3 / C4: the ignored-file check names the file before the fast-forward --
for prot in yes no; do
    label="C3"; [[ "$prot" == no ]] && label="C4"
    echo "--- $label: behind-only (protected=$prot), pc2 force-adds userconfig.yaml -> refused, local copy kept ---"
    T="$(setup_repo)"
    set_userconfig_email "$T" "mine@x.com"
    pc2 "$T" "$label" "printf 'email: theirs@x.com\n' > $UC && git add -f $UC"
    [[ "$prot" == yes ]] && protect_t10 "$T"
    F="$T/local/.aitask-data/$UC"
    assert_eq "$label: fixture — userconfig.yaml is ignored" "!!" "$(st_of "$T" "$UC")"
    PRE_SHA="$(sha_of "$F")"; PRE_ID="$(file_ident "$F")"; PRE_HEAD="$(data_head "$T")"
    OUT="$(run_sync "$T")"
    assert_eq "$label: verdict" "ERROR:pull_overwrites_ignored" "$(first_line "$OUT")"
    assert_contains "$label: stderr names the file" "$UC" "$(sync_err "$T")"
    assert_eq "$label: HEAD unchanged" "$PRE_HEAD" "$(data_head "$T")"
    assert_eq "$label: userconfig bytes unchanged" "$PRE_SHA" "$(sha_of "$F")"
    assert_eq "$label: userconfig never rewritten (inode+ctime)" "$PRE_ID" "$(file_ident "$F")"
    assert_eq "$label: userconfig still ignored" "!!" "$(st_of "$T" "$UC")"
done

# --- C3b: a path with a newline and an escape stays ONE quoted stderr line ----
# The refusal names the path through _gm_show (printf %q). warn() would run that
# through `echo -e` and decode it again: the newline would split the line and the
# ESC would reach the terminal raw. Ignored here only by the local info/exclude,
# so pc2 commits it with a plain `git add` — a differing ignore rule.
echo "--- C3b: ignored file named with a newline and ESC -> refused, path printed quoted on one line ---"
T="$(setup_repo)"
ODD=$'aitasks/metadata/odd\nname\e[31m.local'
printf 'aitasks/metadata/*.local\n' >> "$T/local/.git/info/exclude"
printf 'mine\n' > "$T/local/.aitask-data/$ODD"
# shellcheck disable=SC2016  # $ODD is expanded by pc2's eval, not here
pc2 "$T" "C3b" 'printf "theirs\n" > "$ODD"'
assert_eq "C3b: fixture — the odd file is ignored locally" "!!" "$(st_of "$T" "$ODD")"
PRE_SHA="$(sha_of "$T/local/.aitask-data/$ODD")"
OUT="$(run_sync "$T")"
ERR="$(sync_err "$T")"
assert_eq "C3b: verdict" "ERROR:pull_overwrites_ignored" "$(first_line "$OUT")"
assert_contains "C3b: stderr carries the %q-quoted path verbatim" "$(printf '%q' "$ODD")" "$ERR"
assert_eq "C3b: the newline did not split the refusal line" "0" \
    "$(printf '%s\n' "$ERR" | grep -c '^name' || true)"
assert_eq "C3b: local bytes unchanged" "$PRE_SHA" "$(sha_of "$T/local/.aitask-data/$ODD")"

# --- C5: no false positive -------------------------------------------------
echo "--- C5: local userconfig.yaml, pc2 touches t30 -> PULLED, userconfig untouched ---"
T="$(setup_repo)"
set_userconfig_email "$T" "mine@x.com"
pc2 "$T" "C5" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
F="$T/local/.aitask-data/$UC"
PRE_SHA="$(sha_of "$F")"; PRE_ID="$(file_ident "$F")"
OUT="$(run_sync "$T")"
assert_eq "C5: verdict" "PULLED" "$(first_line "$OUT")"
assert_eq "C5: HEAD is the remote tip" "$(remote_sha "$T")" "$(data_head "$T")"
assert_eq "C5: userconfig bytes unchanged" "$PRE_SHA" "$(sha_of "$F")"
assert_eq "C5: userconfig never rewritten (inode+ctime)" "$PRE_ID" "$(file_ident "$F")"

# --- C7: the fixture isolates global git config ----------------------------
echo "--- C7: a global merge.autoStash=true never reaches the sweep ---"
T="$(setup_repo)"
printf '[merge]\n\tautoStash = true\n' > "$T/fake_gitconfig"
assert_eq "C7: control — the fake global config is visible without isolation" "true" \
    "$(GIT_CONFIG_GLOBAL="$T/fake_gitconfig" git -C "$T/local/.aitask-data" config --get merge.autoStash 2>/dev/null)"
printf 'edit20\n' >> "$T/local/.aitask-data/aitasks/t20_beta.md"
OUT="$(GIT_CONFIG_GLOBAL="$T/fake_gitconfig" run_sync_with_seam "$T" pre_group_commit \
    "{ git -C '$T/local/.aitask-data' config --get merge.autoStash; echo \"rc=\$?\"; } > '$T/seen' 2>&1")"
seam_fired "C7" "$T" pre_group_commit
assert_eq "C7: the sweep saw no merge.autoStash" "rc=1" "$(cat "$T/seen" 2>/dev/null)"

# --- C10: an ignored file created AFTER the check -> git refuses at write time --
echo "--- C10: userconfig.yaml appears after the check -> fast-forward refuses, bytes kept ---"
T="$(setup_repo)"
pc2 "$T" "C10" "printf 'email: theirs@x.com\n' > $UC && git add -f $UC"
F="$T/local/.aitask-data/$UC"
assert_eq "C10: fixture — no local userconfig at the check" "absent" "$([[ -e "$F" ]] && echo present || echo absent)"
PRE_HEAD="$(data_head "$T")"
LATE="email: mine-late@x.com"
OUT="$(run_sync_with_seam "$T" pre_pull_apply "printf '%s\n' '$LATE' > '$F'")"
seam_fired "C10" "$T" pre_pull_apply
assert_eq "C10: verdict" "ERROR:pull_ff_refused" "$(first_line "$OUT")"
assert_eq "C10: HEAD unchanged" "$PRE_HEAD" "$(data_head "$T")"
assert_eq "C10: the late private copy is intact" "$(sha_of_text "$LATE"$'\n')" "$(sha_of "$F")"
assert_eq "C10: and still ignored" "!!" "$(st_of "$T" "$UC")"

# --- C10b: git's own refusal text is printed verbatim, never decoded ---------
# Same race as C10. Git's message names the file raw, and git itself already
# turns control characters into '?'; what it does NOT neutralise is a LITERAL
# backslash sequence in the name. warn() (`echo -e`) would decode the `\e` below
# into a real ESC.
echo "--- C10b: ignored file named with a newline and a literal backslash-e appears after the check -> one clean refusal line ---"
T="$(setup_repo)"
ODD=$'aitasks/metadata/odd\nname\\e[31m.local'
printf 'aitasks/metadata/*.local\n' >> "$T/local/.git/info/exclude"
# shellcheck disable=SC2016  # $ODD is expanded by pc2's eval, not here
pc2 "$T" "C10b" 'printf "theirs\n" > "$ODD"'
# The hook is eval'd inside the sync process, so the path travels pre-quoted.
OUT="$(run_sync_with_seam "$T" pre_pull_apply "printf 'mine\n' > $(printf '%q' "$T/local/.aitask-data/$ODD")")"
seam_fired "C10b" "$T" pre_pull_apply
assert_eq "C10b: verdict" "ERROR:pull_ff_refused" "$(first_line "$OUT")"
FFLINE="$(sync_err "$T" | grep 'Fast-forward to' | head -n1)"
assert_contains "C10b: fixture — the refusal line names the odd file" "odd" "$FFLINE"
# Strip warn's own colour codes; any ESC left came from the file name.
FFLINE="${FFLINE//$'\e[1;33m'/}"; FFLINE="${FFLINE//$'\e[0m'/}"
assert_eq "C10b: no raw ESC reaches the terminal" "clean" \
    "$([[ "$FFLINE" == *$'\e'* ]] && echo raw-esc || echo clean)"
assert_contains "C10b: the backslash sequence is printed literally" 'name\e[31m.local' "$FFLINE"
assert_eq "C10b: the private copy is intact" "$(sha_of_text $'mine\n')" "$(sha_of "$T/local/.aitask-data/$ODD")"

# --- C13: the fast-forward applies the PINNED upstream, never a later one ---
echo "--- C13: a commit fetched after the check is not applied ---"
T="$(setup_repo)"
set_userconfig_email "$T" "mine@x.com"
pc2 "$T" "C13" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
U="$(remote_sha "$T")"
F="$T/local/.aitask-data/$UC"
PRE_SHA="$(sha_of "$F")"; PRE_ID="$(file_ident "$F")"
OUT="$(run_sync_with_seam "$T" pre_pull_apply "$(racer_force_add_uc "$T")")"
seam_fired "C13" "$T" pre_pull_apply
assert_eq "C13: fixture — the racer moved @{u}" "moved" \
    "$([[ "$(dgit "$T" rev-parse '@{u}' 2>/dev/null)" != "$U" ]] && echo moved || echo same)"
assert_eq "C13: verdict" "PULLED" "$(first_line "$OUT")"
assert_eq "C13: HEAD is the pinned upstream, not the racer's commit" "$U" "$(data_head "$T")"
assert_eq "C13: userconfig bytes unchanged" "$PRE_SHA" "$(sha_of "$F")"
assert_eq "C13: userconfig never rewritten (inode+ctime)" "$PRE_ID" "$(file_ident "$F")"
OUT2="$(run_sync "$T")"
assert_eq "C13: the next run refuses the racer's commit" "ERROR:pull_overwrites_ignored" "$(first_line "$OUT2")"
assert_eq "C13: userconfig still unchanged after it" "$PRE_SHA" "$(sha_of "$F")"

# --- C22: a refused fast-forward is never retried as a rebase ---------------
echo "--- C22: a commit lands after the check -> fast-forward refuses, nothing rebased ---"
T="$(setup_repo)"
pc2 "$T" "C22" 'printf "from pc2\n" >> aitasks/t30_gamma.md'
F30="$T/local/.aitask-data/aitasks/t30_gamma.md"
PRE_HEAD="$(data_head "$T")"; PRE_ID30="$(file_ident "$F30")"
OUT="$(run_sync_with_seam "$T" pre_pull_apply \
    "printf 'late10\n' >> aitasks/t10_alpha.md && ./ait git add aitasks/t10_alpha.md && ./ait git commit -q -m 'late: t10' -- aitasks/t10_alpha.md")"
seam_fired "C22" "$T" pre_pull_apply
assert_eq "C22: verdict" "ERROR:pull_ff_refused" "$(first_line "$OUT")"
assert_eq "C22: HEAD is the late commit" "late: t10" "$(dsubject "$T")"
assert_eq "C22: the late commit sits directly on the pre-run HEAD (no rebase)" "$PRE_HEAD" \
    "$(dgit "$T" rev-parse HEAD^ 2>/dev/null)"
assert_eq "C22: the incoming path was never written (inode+ctime)" "$PRE_ID30" "$(file_ident "$F30")"

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
