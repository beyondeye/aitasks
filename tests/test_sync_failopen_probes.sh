#!/usr/bin/env bash
# test_sync_failopen_probes.sh - rows A3, A4 and A10 of the fail-open git-probe
# sweep in aitask_sync.sh (t1747_3), plus the call-site identity scan.
#
# Rule, fix shape and dispositions: aidocs/framework/failopen_git_probes.md.
# Row A5 lives in tests/test_sync_branch_mode_automerge.sh (Tests 18-20), next to
# the conflict fixture it needs.
#
# Every fail-closed case below has:
#   - an argv-keyed git shim that fails exactly ONE probe shape and logs that it
#     fired (a shim that never fires makes a green test vacuous);
#   - an asserted fixture precondition, pinning both the fixture's identity and
#     the symptom it produces;
#   - a probe-only mutant, applied to the fixture's copy only, under which the
#     defect is observed.
#
# Run: bash tests/test_sync_failopen_probes.sh

set -uo pipefail

TEST_SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

# --- Helpers shared with tests/test_sync_deferral_and_quarantine.sh ---------
remote_data_sha() { git -C "$1/remote.git" rev-parse refs/heads/aitask-data 2>/dev/null; }
enable_seams() { mkdir -p "$1/locks" && touch "$1/locks/.ait_sync_test_seams"; }
quarantine_file() { echo "$1/local/.git/worktrees/-aitask-data/ait-sync-quarantine"; }
run_sync_seam() {
    local tmpdir="$1" point="$2" hook="$3"; shift 3
    (
        cd "$tmpdir/local"
        export PATH="$PWD/bin:$PATH"
        export TEST_HOSTNAME="${TEST_HOSTNAME:-testhost}"
        export AITASKS_LOCK_DIR="$tmpdir/locks"
        export "AIT_SYNC_SEAM_${point}=$hook"
        ./.aitask-scripts/aitask_sync.sh --batch "$@" 2>"$tmpdir/sync_stderr"
    )
}

# run_sync_wt <tmpdir> [args] — tests/lib/sync_fixture.sh::run_sync, but run from
# the linked worktree <tmpdir>/wt. Kept local rather than parametrizing the shared
# fixture.
run_sync_wt() {
    local tmpdir="$1"; shift
    (
        cd "$tmpdir/wt"
        export PATH="$PWD/bin:$PATH"
        export TEST_HOSTNAME="${TEST_HOSTNAME:-testhost}"
        export AITASKS_LOCK_DIR="$tmpdir/locks"
        export AITASKS_TMUX_SOCKET="${SYNC_FIXTURE_TMUX_SOCKET:-ait_syncfx_nosrv_$$}"
        ./.aitask-scripts/aitask_sync.sh --batch "$@" 2>"$tmpdir/sync_stderr"
    )
}

# advance_remote_touching <tmpdir> <relpath> — a second clone appends to <relpath>
# on aitask-data and pushes, so local is behind AND the incoming commit writes a
# path local holds dirty. That shape blocks the rebase (the guarded merge
# declines on a protected path), so the run ends in DEFERRED:protected_dirty and
# prints its DEFERRED_FILE records.
advance_remote_touching() {
    local tmpdir="$1" rel="$2"
    rm -rf "$tmpdir/pc2"
    git clone -q --branch aitask-data "$tmpdir/remote.git" "$tmpdir/pc2" 2>/dev/null
    (
        cd "$tmpdir/pc2"
        git config user.email pc2@test.com
        git config user.name PC2
        git config commit.gpgsign false
        printf 'from pc2\n' >> "$rel"
        git add -A && git commit -q -m "pc2: touch $rel"
        git push -q origin aitask-data 2>/dev/null
    ) >/dev/null 2>&1
    (cd "$tmpdir/local" && git -C .aitask-data fetch -q origin 2>/dev/null)
}

first_line() { printf '%s\n' "$1" | head -n1; }
_eq() { [[ "$1" == "$2" ]]; }
_ne() { [[ "$1" != "$2" ]]; }

_debug() { [[ -n "${FAILOPEN_TEST_DEBUG:-}" ]] && printf '  [debug] %s\n' "$*" >&2; return 0; }

# install_probe_shim <bindir> <mode> <log> — an argv-keyed `git` in <bindir>, which
# must be the checkout's bin/ (run_sync puts it first on PATH). It fails exactly one
# argv shape, appends each call it failed to <log>, and passes everything else
# through to the real git. Each shape below has exactly one caller on the route
# its test drives:
#   cached-name-only  `diff --cached --name-only`: A3's staged guard
#                     (_commit_group). t1747_2's `diff --cached --quiet HEAD` has a
#                     different shape.
#   status-path:<p>   `status --porcelain` WITHOUT -z, with <p> as its last
#                     argument: A4's settlement probe. The sweep's own dirty scan
#                     uses `-z -uall`.
#   absgitdir         `rev-parse --absolute-git-dir`: A10. Its caller is
#                     _ait_data_gitdir's linked-worktree route; from a primary
#                     checkout the fast path makes no git call at all.
install_probe_shim() {
    local bindir="$1" mode="$2" log="$3" real_git
    real_git="$(command -v git)"
    mkdir -p "$bindir"
    cat > "$bindir/git" <<SHIMEOF
#!/usr/bin/env bash
_has() { local n="\$1" a; shift; for a in "\$@"; do [[ "\$a" == "\$n" ]] && return 0; done; return 1; }
_fail=0
case '$mode' in
    cached-name-only)
        _has diff "\$@" && _has --cached "\$@" && _has --name-only "\$@" && _fail=1 ;;
    status-path:*)
        _p='${mode#status-path:}'
        _has status "\$@" && _has --porcelain "\$@" && ! _has -z "\$@" \\
            && [[ "\${@: -1}" == "\$_p" ]] && _fail=1 ;;
    absgitdir)
        _has rev-parse "\$@" && _has --absolute-git-dir "\$@" && _fail=1 ;;
esac
if [[ \$_fail -eq 1 ]]; then
    printf '%s\n' "\$*" >> '$log'
    echo "fatal: simulated probe failure (test shim)" >&2
    exit 128
fi
exec '$real_git' "\$@"
SHIMEOF
    chmod +x "$bindir/git"
}

# --- Mutant installers (the shape of tests/test_sync_branch_mode_automerge.sh) --
# Each regresses ONE probe in a fixture's copy of aitask_sync.sh — never the real
# repo — fails loudly on a stale anchor, proves its substitution landed, and
# proves the rest of the guard survived. Otherwise a control would observe "no
# guard" rather than "fail-open guard".

# _replace_once <file> <old> <new> — exactly-once literal replacement.
_replace_once() {
    python3 - "$1" "$2" "$3" <<'PY'
import sys
p, old, new = sys.argv[1:4]
s = open(p).read()
n = s.count(old)
if n != 1:
    sys.stderr.write("FATAL: mutant anchor matched %d times (stale?): %r\n" % (n, old))
    sys.exit(1)
open(p, "w").write(s.replace(old, new, 1))
PY
}

# _require <present|absent> <file> <fixed-string> <what went wrong>
_require() {
    local want="$1" f="$2" needle="$3" msg="$4" found=absent
    grep -qF -- "$needle" "$f" && found=present
    if [[ "$found" != "$want" ]]; then
        echo "FAIL: negative control — $msg"
        FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
        return 1
    fi
}
_control_ok() { TOTAL=$((TOTAL + 1)); PASS=$((PASS + 1)); }
_control_install_failed() {
    echo "FAIL: negative control — could not install the $1 mutant (anchor gone stale?)"
    FAIL=$((FAIL + 1)); TOTAL=$((TOTAL + 1))
}

# assert_defect_present <desc> <condition-cmd...> — the control INVERTS: the
# defect must be observable against the regressed build. (tests/test_fold_mark.sh)
assert_defect_present() {
    local desc="$1"; shift
    TOTAL=$((TOTAL + 1))
    if "$@"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: negative control — $desc (the regressed build did NOT exhibit the defect; the test above proves nothing)"
    fi
}

# A3: the staged guard's probe back to `|| staged=""`.
install_a3_probe_mutant() {
    local f="$1/.aitask-scripts/aitask_sync.sh"
    _replace_once "$f" \
'    staged="$(task_git diff --cached --name-only -- "${paths[@]}" 2>/dev/null)" || s_rc=$?' \
'    staged="$(task_git diff --cached --name-only -- "${paths[@]}" 2>/dev/null)" || staged=""' \
        || { _control_install_failed "A3 probe"; return 1; }
    _require present "$f" '2>/dev/null)" || staged=""' "A3: the fail-open probe was not installed" || return 1
    _require absent  "$f" 'staged="$(task_git diff --cached --name-only -- "${paths[@]}" 2>/dev/null)" || s_rc=$?' "A3: the status capture is still in place" || return 1
    _require present "$f" '_protect "staged_elsewhere"' "A3: the positive detection was excised" || return 1
    _control_ok
}

# A4: the settlement probe back to reading a failed status as "clean".
install_a4_probe_mutant() {
    local f="$1/.aitask-scripts/aitask_sync.sh"
    _replace_once "$f" \
'                st="$(task_git status --porcelain -- "$p" 2>/dev/null)" || st_rc=$?' \
'                st="$(task_git status --porcelain -- "$p" 2>/dev/null)" || st=""' \
        || { _control_install_failed "A4 probe"; return 1; }
    _require present "$f" '2>/dev/null)" || st=""' "A4: the fail-open probe was not installed" || return 1
    _require present "$f" 'quarantine released (owner gone, state settled)' "A4: the release clause was excised" || return 1
    _require present "$f" '_holder_verdict "$tid"' "A4: the ownership half of the clause was excised" || return 1
    _control_ok
}

# A10: _sync_gitdir back to its two fabricated fallbacks.
install_a10_gitdir_mutant() {
    local f="$1/.aitask-scripts/aitask_sync.sh"
    _replace_once "$f" \
'    gd="$(_data_wedge_gitdir)"
    [[ -n "$gd" ]] || return 2
    printf '"'"'%s'"'"' "$gd"' \
'    gd="$(_ait_data_gitdir)"
    if [[ -z "$gd" ]]; then
        gd="$(git rev-parse --git-dir 2>/dev/null)" || gd=".git"
    fi
    printf '"'"'%s'"'"' "${gd:-.git}"' \
        || { _control_install_failed "A10 git-dir"; return 1; }
    _require present "$f" '|| gd=".git"' "A10: the fabricated fallback was not installed" || return 1
    _require present "$f" '_worktree_wedged() {' "A10: the wedge check was excised" || return 1
    _require present "$f" 'ait-sync-quarantine' "A10: the quarantine ledger was excised" || return 1
    _control_ok
}

# build_a10_fixture <tmpdir> — a withheld raced commit in the quarantine ledger
# (the Test 8 recipe of test_sync_deferral_and_quarantine.sh), then a LINKED
# worktree <tmpdir>/wt of the code branch. Echoes a precondition verdict line.
build_a10_fixture() {
    local t="$1" out link
    enable_seams "$t"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    out="$(run_sync_seam "$t" pre_group_commit \
        "printf 'RACED\n' >> '$t/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
    [[ "$out" == *"DEFERRED:publication_blocked"* ]] || { echo "run1-not-withheld"; return 0; }
    [[ -s "$(quarantine_file "$t")" ]] || { echo "ledger-empty"; return 0; }
    git -C "$t/local" worktree add -q --detach "$t/wt" main >/dev/null 2>&1 \
        || { echo "worktree-add-failed"; return 0; }
    # The fixture's `git add -A` commits .aitask-data into the code branch as a
    # gitlink, so the checkout leaves an EMPTY directory where a real linked
    # worktree has nothing. Remove it only if it really is empty.
    if [[ -d "$t/wt/.aitask-data" && ! -L "$t/wt/.aitask-data" ]]; then
        [[ -z "$(ls -A "$t/wt/.aitask-data")" ]] || { echo "gitlink-dir-not-empty"; return 0; }
        rmdir "$t/wt/.aitask-data"
    fi
    link="$(cd "$t/local" && ./.aitask-scripts/aitask_init_data.sh --link-worktree "$t/wt" 2>&1)"
    [[ "$link" == *LINKED* ]] || { echo "link-refused: $link"; return 0; }
    echo "ok"
}

echo "=== aitask_sync.sh fail-open probes (t1747_3) ==="
echo ""

# --- A10-1: an unresolvable data git-dir must refuse, not relocate the ledger ---
echo "--- A10-1: linked worktree + unresolvable data git-dir -> ERROR, ledger kept ---"
T10="$(setup_repo)"
BEFORE10="$(remote_data_sha "$T10")"
assert_eq "A10-1 precondition: raced commit withheld, ledger written, worktree linked" \
    "ok" "$(build_a10_fixture "$T10")"
QF10="$(quarantine_file "$T10")"
assert_contains "A10-1 precondition: the ledger holds t10's entry" \
    "aitasks/t10_alpha.md" "$(cat "$QF10" 2>/dev/null)"
# Unshimmed from wt the run must reach the REAL ledger: the precondition, and the
# permit direction.
OUT10B="$(run_sync_wt "$T10")"
_debug "A10-1 unshimmed wt: $(first_line "$OUT10B")"
assert_contains "A10-1 precondition: unshimmed, the linked worktree reads the real ledger" \
    "DEFERRED:publication_blocked" "$OUT10B"
assert_eq "A10-1 precondition: nothing was published yet" "$BEFORE10" "$(remote_data_sha "$T10")"

install_probe_shim "$T10/wt/bin" absgitdir "$T10/shim.log"
OUT10C="$(run_sync_wt "$T10")"; RC10C=$?
rm -f "$T10/wt/bin/git"
_debug "A10-1 shimmed wt: rc=$RC10C out=$(first_line "$OUT10C") | $(tail -3 "$T10/sync_stderr" | tr '\n' ' ')"
assert_contains "A10-1: the probe shim fired" "--absolute-git-dir" "$(cat "$T10/shim.log" 2>/dev/null)"
assert_eq "A10-1: refuses with ERROR:data_gitdir_unresolved" \
    "ERROR:data_gitdir_unresolved" "$(first_line "$OUT10C")"
assert_exit_nonzero_rc "A10-1: exits non-zero" "$RC10C"
assert_contains "A10-1: the refusal names its recovery" "git worktree repair" "$(sync_err "$T10")"
assert_eq "A10-1: the withheld commit was NOT published" "$BEFORE10" "$(remote_data_sha "$T10")"
assert_contains "A10-1: the held entry survives in the real ledger" \
    "aitasks/t10_alpha.md" "$(cat "$QF10" 2>/dev/null)"
OUT10D="$(run_sync "$T10")"
assert_contains "A10-1: a later unshimmed run from the primary still withholds" \
    "DEFERRED:publication_blocked" "$OUT10D"

# --- A10-2: an unresolvable git-dir is never read as "not wedged" ------------
echo "--- A10-2: wedged data worktree + unresolvable git-dir -> ERROR, never 'not wedged' ---"
WEDGE10="$T10/local/.git/worktrees/-aitask-data/rebase-merge"
mkdir -p "$WEDGE10"
OUT10E="$(run_sync_wt "$T10")"
assert_contains "A10-2 precondition: unshimmed, the wedge is visible from the linked worktree" \
    "DEFERRED:worktree_wedged" "$OUT10E"
rm -f "$T10/shim.log"
install_probe_shim "$T10/wt/bin" absgitdir "$T10/shim.log"
OUT10F="$(run_sync_wt "$T10")"; RC10F=$?
rm -f "$T10/wt/bin/git"
rmdir "$WEDGE10"
assert_contains "A10-2: the probe shim fired" "--absolute-git-dir" "$(cat "$T10/shim.log" 2>/dev/null)"
assert_eq "A10-2: refuses with ERROR:data_gitdir_unresolved" \
    "ERROR:data_gitdir_unresolved" "$(first_line "$OUT10F")"
assert_exit_nonzero_rc "A10-2: exits non-zero" "$RC10F"
assert_eq "A10-2: nothing was published" "$BEFORE10" "$(remote_data_sha "$T10")"

# --- A10 negative control: the old fallbacks publish the withheld commit ------
T10m="$(setup_repo)"
BEFORE10m="$(remote_data_sha "$T10m")"
if [[ "$(build_a10_fixture "$T10m")" == ok ]] && install_a10_gitdir_mutant "$T10m/wt"; then
    install_probe_shim "$T10m/wt/bin" absgitdir "$T10m/shim.log"
    run_sync_wt "$T10m" >/dev/null
    rm -f "$T10m/wt/bin/git"
    assert_defect_present "A10: with the fabricated fallback the withheld commit is published" \
        _ne "$BEFORE10m" "$(remote_data_sha "$T10m")"
else
    assert_record_fail; echo "FAIL: A10 negative control could not be built"
fi

# --- A3-1: an unread staged guard defers the group, touching nothing ---------
echo "--- A3-1: unreadable shared index -> group deferred, foreign stage intact ---"
T3="$(setup_repo)"
(cd "$T3/local" \
    && printf 'staged-content\n' >> .aitask-data/aitasks/t10_alpha.md \
    && git -C .aitask-data add -- aitasks/t10_alpha.md \
    && printf 'worktree-only\n' >> .aitask-data/aitasks/t10_alpha.md \
    && printf 'edit20\n' >> .aitask-data/aitasks/t20_beta.md)
BEFORE3="$(remote_data_sha "$T3")"
advance_remote_touching "$T3" aitasks/t10_alpha.md
assert_eq "A3-1 precondition: the remote really moved" "yes" \
    "$([[ "$(remote_data_sha "$T3")" != "$BEFORE3" ]] && echo yes || echo no)"
IDX3="$(git -C "$T3/local/.aitask-data" rev-parse :aitasks/t10_alpha.md)"
assert_eq "A3-1 precondition: unshimmed, t10 really is staged by another session" \
    "aitasks/t10_alpha.md" \
    "$(git -C "$T3/local/.aitask-data" diff --cached --name-only -- aitasks/t10_alpha.md)"
install_probe_shim "$T3/local/bin" cached-name-only "$T3/shim.log"
OUT3="$(run_sync "$T3")"
rm -f "$T3/local/bin/git"
_debug "A3-1: $(first_line "$OUT3") | rows: $(printf '%s\n' "$OUT3" | grep -c DEFERRED_FILE)"
assert_contains "A3-1: the probe shim fired" "--cached --name-only" "$(cat "$T3/shim.log" 2>/dev/null)"
assert_contains "A3-1: a recognised deferral is reported" "DEFERRED:protected_dirty" "$(first_line "$OUT3")"
assert_contains "A3-1: t10 is recorded as unverifiable" \
    "DEFERRED_FILE:unverifiable|10|aitasks/t10_alpha.md|" "$OUT3"
assert_contains "A3-1: the report says the index could not be read" \
    "could not read the shared index" "$(sync_err "$T3")"
assert_not_contains "A3-1: t10's group was NOT committed" "Auto-commit t10 " "$(data_log "$T3")"
assert_eq "A3-1: the foreign staged blob is byte-identical" \
    "$IDX3" "$(git -C "$T3/local/.aitask-data" rev-parse :aitasks/t10_alpha.md)"

# --- A3-2: permit direction — the deferred group commits once the index reads --
echo "--- A3-2: control - index readable again, foreign stage gone -> group commits ---"
T3p="$(setup_repo)"
(cd "$T3p/local" \
    && printf 'staged-content\n' >> .aitask-data/aitasks/t10_alpha.md \
    && git -C .aitask-data add -- aitasks/t10_alpha.md)
install_probe_shim "$T3p/local/bin" cached-name-only "$T3p/shim.log"
run_sync "$T3p" >/dev/null
rm -f "$T3p/local/bin/git"
assert_not_contains "A3-2 precondition: the shimmed run deferred t10" "Auto-commit t10 " "$(data_log "$T3p")"
git -C "$T3p/local/.aitask-data" reset -q -- aitasks/t10_alpha.md
run_sync "$T3p" >/dev/null
assert_contains "A3-2: the previously deferred group now commits" \
    "ait: Auto-commit t10 task data before sync" "$(data_log "$T3p")"

# --- A3 negative control: `|| staged=""` replaces the foreign stage ----------
T3m="$(setup_repo)"
(cd "$T3m/local" \
    && printf 'staged-content\n' >> .aitask-data/aitasks/t10_alpha.md \
    && git -C .aitask-data add -- aitasks/t10_alpha.md \
    && printf 'worktree-only\n' >> .aitask-data/aitasks/t10_alpha.md)
IDX3m="$(git -C "$T3m/local/.aitask-data" rev-parse :aitasks/t10_alpha.md)"
if install_a3_probe_mutant "$T3m/local"; then
    install_probe_shim "$T3m/local/bin" cached-name-only "$T3m/shim.log"
    run_sync "$T3m" >/dev/null
    rm -f "$T3m/local/bin/git"
    assert_defect_present "A3: with the fail-open probe the foreign staged entry is replaced" \
        _ne "$IDX3m" "$(git -C "$T3m/local/.aitask-data" rev-parse :aitasks/t10_alpha.md 2>/dev/null)"
fi

# --- A4: an unreadable quarantined path is not "settled" ---------------------
# build_a4_fixture <tmpdir> — the Test 11 recipe: a live lock, a raced commit
# quarantined, then the owner's lock replaced by one whose anchor is provably dead.
build_a4_fixture() {
    local t="$1" out
    enable_seams "$t"
    plant_lock "$t" 10 "$(lock_yaml_live 10)"
    (cd "$t/local" && printf 'edit10\n' >> .aitask-data/aitasks/t10_alpha.md)
    out="$(run_sync_seam "$t" pre_group_commit \
        "printf 'RACED\n' >> '$t/local/.aitask-data/aitasks/t10_alpha.md'" --assume-unlocked)"
    [[ "$out" == *"DEFERRED:publication_blocked"* ]] || { echo "run1-not-withheld"; return 0; }
    grep -qF "aitasks/t10_alpha.md" "$(quarantine_file "$t")" 2>/dev/null || { echo "ledger-missing-t10"; return 0; }
    plant_lock "$t" 10 "$(lock_yaml_dead 10)"
    echo "ok"
}
# lock_yaml_dead anchors pid 999999 to starttime 12345: dead unless a process with
# exactly that pid AND starttime exists, which the holder verdict itself checks.
_dead_anchor() {
    [[ ! -e /proc/999999/stat ]] || [[ "$(awk '{print $22}' /proc/999999/stat 2>/dev/null)" != "12345" ]]
}

echo "--- A4-1: owner gone + unreadable path state -> still held, nothing published ---"
T4="$(setup_repo)"
BEFORE4="$(remote_data_sha "$T4")"
assert_eq "A4-1 precondition: raced commit quarantined, owner's lock replaced" "ok" "$(build_a4_fixture "$T4")"
assert_eq "A4-1 precondition: the planted owner anchor is not alive" "yes" \
    "$(_dead_anchor && echo yes || echo no)"
install_probe_shim "$T4/local/bin" "status-path:aitasks/t10_alpha.md" "$T4/shim.log"
OUT4="$(run_sync "$T4")"
rm -f "$T4/local/bin/git"
assert_contains "A4-1: the probe shim fired" "status --porcelain" "$(cat "$T4/shim.log" 2>/dev/null)"
assert_contains "A4-1: the entry is still held" "DEFERRED:publication_blocked" "$(first_line "$OUT4")"
assert_eq "A4-1: nothing was published" "$BEFORE4" "$(remote_data_sha "$T4")"
assert_contains "A4-1: the entry is still in the ledger" \
    "aitasks/t10_alpha.md" "$(cat "$(quarantine_file "$T4")" 2>/dev/null)"
assert_contains "A4-1: the report says the state could not be read" \
    "could not be read" "$(sync_err "$T4")"

echo "--- A4-2: control - same fixture, probe readable -> released and published ---"
T4c="$(setup_repo)"
BEFORE4c="$(remote_data_sha "$T4c")"
assert_eq "A4-2 precondition: raced commit quarantined, owner's lock replaced" "ok" "$(build_a4_fixture "$T4c")"
assert_eq "A4-2 precondition: the planted owner anchor is not alive" "yes" \
    "$(_dead_anchor && echo yes || echo no)"
OUT4c="$(run_sync "$T4c")"
assert_not_contains "A4-2: the settled entry is released" "DEFERRED:publication_blocked" "$OUT4c"
assert_eq "A4-2: and the withheld commit is published" "yes" \
    "$([[ "$(remote_data_sha "$T4c")" != "$BEFORE4c" ]] && echo yes || echo no)"

# --- A4 negative control: a failed status reads as "clean" and releases ------
T4m="$(setup_repo)"
BEFORE4m="$(remote_data_sha "$T4m")"
if [[ "$(build_a4_fixture "$T4m")" == ok ]] && install_a4_probe_mutant "$T4m/local"; then
    install_probe_shim "$T4m/local/bin" "status-path:aitasks/t10_alpha.md" "$T4m/shim.log"
    run_sync "$T4m" >/dev/null
    rm -f "$T4m/local/bin/git"
    assert_defect_present "A4: with the fail-open probe the unread entry is released and published" \
        _ne "$BEFORE4m" "$(remote_data_sha "$T4m")"
else
    assert_record_fail; echo "FAIL: A4 negative control could not be built"
fi

# --- S: every consumer of the changed helpers has a recorded disposition -----
echo "--- S: helper call sites equal the disposition table ---"
# One `file::function::helper<TAB>tagged|untagged` row per CALL site: definition
# lines and comment lines excluded, function spans tracked via `name() {` / `}`.
# A call is "tagged" only when the comment block DIRECTLY above it carries
# `unverified:`, so a second call cannot borrow the first one's tag. Copied from
# tests/test_sync_branch_mode_automerge.sh (Test 13).
#
# What it does not buy: the tag's TEXT is never checked against the code under it
# — every tagged consumer's rc-2 branch is driven live instead (A10-1/A10-2 above,
# and Test 20 in test_sync_branch_mode_automerge.sh for do_pull_rebase) — and
# legacy mode is not driven live: the fixture is branch-mode only, and the
# `[[ -n "$gd" ]] || return 2` it would exercise is shared by both modes.
SYNC_CALLSITE_AWK='
BEGIN { n = split(HELPERS, HL, " ") }
{
    s = $0; sub(/^[ \t]+/, "", s)
    if (s ~ /^#/) { cblock = cblock " " s; next }
    if ($0 ~ /^[A-Za-z_][A-Za-z0-9_]*\(\) *\{/) {
        fn = $0; sub(/\(\).*/, "", fn); cblock = ""; next
    }
    if ($0 ~ /^\} *$/) { fn = ""; cblock = ""; next }
    for (i = 1; i <= n; i++)
        if (index($0, HL[i]) > 0)
            printf "%s::%s::%s\t%s\n", REL, (fn == "" ? "<toplevel>" : fn), HL[i], \
                (cblock ~ /unverified:/ ? "tagged" : "untagged")
    cblock = ""
}'
SYNC_HELPERS="_data_wedge_gitdir _sync_gitdir _worktree_wedged _quarantine_path"
sync_callsites() {
    awk -v HELPERS="$SYNC_HELPERS" -v REL="$(basename "$1")" "$SYNC_CALLSITE_AWK" "$1" | LC_ALL=C sort
}

# The scanner can fail: a second call borrowing a tag, a top-level call, and a
# comment that merely NAMES a helper must each be classified correctly.
SELFS="$(mktemp -d)"
cat > "$SELFS/x.sh" <<'SELFEOF'
f_one() {
    # unverified: only the first call carries this
    _sync_gitdir
    _sync_gitdir
}
# a comment naming _quarantine_path is not a call
_worktree_wedged
SELFEOF
assert_eq "S: scanner self-test (attribution and per-site tags)" \
    "$(printf 'x.sh::<toplevel>::_worktree_wedged\tuntagged\nx.sh::f_one::_sync_gitdir\ttagged\nx.sh::f_one::_sync_gitdir\tuntagged\n' | LC_ALL=C sort)" \
    "$(sync_callsites "$SELFS/x.sh")"
rm -rf "$SELFS"

SYNC_SH="$PROJECT_DIR/.aitask-scripts/aitask_sync.sh"
rowsS="$(sync_callsites "$SYNC_SH")"
expectedS="$(printf '%s\n' \
    'aitask_sync.sh::_quarantine_path::_sync_gitdir' \
    'aitask_sync.sh::_sync_gitdir::_data_wedge_gitdir' \
    'aitask_sync.sh::_worktree_wedged::_sync_gitdir' \
    'aitask_sync.sh::auto_commit::_quarantine_path' \
    'aitask_sync.sh::do_pull_rebase::_worktree_wedged' \
    'aitask_sync.sh::main::_worktree_wedged' \
    | LC_ALL=C sort)"
idsS="$(printf '%s\n' "$rowsS" | cut -f1)"
assert_eq "S: call-site identities equal the disposition table" "$expectedS" "$idsS"
if [[ "$idsS" != "$expectedS" ]]; then
    echo "  -> a consumer of $SYNC_HELPERS changed in aitask_sync.sh."
    echo "     Give it an explicit disposition for 'unverified' (see"
    echo "     aidocs/framework/failopen_git_probes.md rows A3/A4/A5/A10), then update this table."
fi
# A scan that finds nothing must fail, not pass: pin the count and the definitions.
assert_eq "S: exactly six call sites" "6" "$(printf '%s\n' "$rowsS" | grep -c .)"
for defn in '_sync_gitdir() {' '_quarantine_path() {' '_worktree_wedged() {'; do
    assert_eq "S: $defn is defined once in aitask_sync.sh" "1" "$(grep -cF "$defn" "$SYNC_SH")"
done
assert_eq "S: _data_wedge_gitdir is defined once in lib/task_utils.sh" "1" \
    "$(grep -cF '_data_wedge_gitdir() {' "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh")"
assert_eq "S: every call site carries its own unverified: tag" "" \
    "$(printf '%s\n' "$rowsS" | grep -F "$(printf '\tuntagged')" || true)"

# --- Summary ---
echo ""
echo "=== Results: $PASS passed, $FAIL failed (of $TOTAL) ==="
[[ $FAIL -eq 0 ]] || exit 1
exit 0
