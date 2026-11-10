#!/usr/bin/env bash
# test_issue_update_ledger.sh - The release-ledger writer in
# aitask_issue_update.sh (t2261_1): one committed record per successfully
# updated issue, the --record-only recovery, and every interrupted-writer and
# competing-commit window the writer must survive without losing a record or
# leaving a tracked deletion.
#
# Drives the REAL script against scratch repos (legacy mode, plus one
# branch-mode fixture), with gh / glab / bkt stubs and a pass-through `git`
# wrapper that has opt-in failure modes:
#   AIT_TEST_FAIL_COMMIT=1      `git commit` exits 1
#   AIT_TEST_ONCE_MARKER=<f>    arms the two modes below for ONE call: the
#                               scoped-commit helper's `ls-files
#                               --error-unmatch -- <…​.rec>` probe
#     AIT_TEST_FOREIGN_COMMIT=1   commit that path first (the early window,
#                                 before the helper's status check)
#     AIT_TEST_WEDGE_ON_PROBE=1   plant MERGE_HEAD in the data worktree's git
#                                 dir, so the helper's next `add` dies
#   AIT_TEST_WEDGE_ON_ADD=1 with AIT_TEST_ADD_MARKER=<f>
#                               run the real `add` of the `.rec` path ONCE, then
#                               plant MERGE_HEAD: the record is staged when the
#                               scoped commit's guard dies (case s2, t2271)
#
# Coverage map (letters as in the t2261_1 plan):
#   (a) one record per action, fields, committed     (h) CLI issue argument
#   (b) dry run writes nothing                       (i) invalid URL refused
#   (c) failed platform call records nothing         (j) malformed reads
#   (d) dedupe                                       (k) branch mode
#   (e) parallel writers, distinct and identical     (l) bitbucket skipped
#   (f) folded route keeps the primary task id       (m) --record-only flags
#   (g) commit failure, then --record-only           (n)-(q) existing files
#   (r) competing commit, early window (rc 2)        (t) late window (rc 1)
#   (s) a real die after publish (branch mode)
#   (s2) a die with the record already staged: the cleanup's warning reaches
#       stderr through _ril_record_cleanup's wrapper (t2271)
#   (u) committed corrupt pending record     (v) released hits, whole record
#   (w) released-only keys in a pending record (t2261_2)
#
# All assertions run in the main shell, so the in-process counters are enough.
#
# Run: bash tests/test_issue_update_ledger.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config

PASS=0
FAIL=0
TOTAL=0

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_issue_update_ledger_XXXXXX")"
cleanup() { rm -rf "$TMP"; }
trap cleanup EXIT
# Private lock base, the documented isolation seam (t1496).
AITASKS_LOCK_DIR="$TMP/locks"
export AITASKS_LOCK_DIR

. "$PROJECT_DIR/tests/lib/issue_update_fixture.sh"
ifx_write_stubs

REAL_GIT="$(command -v git)"
cat > "$IFX_BIN/git" <<EOF
#!/usr/bin/env bash
# Pass-through git wrapper with opt-in failure modes (see the test header).
real="$REAL_GIT"
EOF
cat >> "$IFX_BIN/git" <<'EOF'
args=("$@")
i=0
sub=""
while (( i < ${#args[@]} )); do
    case "${args[i]}" in
        -C|-c|--git-dir|--work-tree) i=$((i + 2)) ;;
        -*) i=$((i + 1)) ;;
        *) sub="${args[i]}"; break ;;
    esac
done
pre=("${args[@]:0:i}")
last="${args[${#args[@]}-1]:-}"
if [[ "$sub" == commit && "${AIT_TEST_FAIL_COMMIT:-}" == 1 ]]; then
    echo "test git wrapper: commit refused" >&2
    exit 1
fi
if [[ "$sub" == add && "$last" == *.rec && "${AIT_TEST_WEDGE_ON_ADD:-}" == 1 \
        && -n "${AIT_TEST_ADD_MARKER:-}" && ! -e "$AIT_TEST_ADD_MARKER" ]]; then
    : > "$AIT_TEST_ADD_MARKER"
    "$real" "$@"; rc=$?
    gd="$("$real" "${pre[@]}" rev-parse --absolute-git-dir)"
    : > "$gd/MERGE_HEAD"
    exit "$rc"
fi
if [[ "$sub" == ls-files && "$last" == *.rec && -n "${AIT_TEST_ONCE_MARKER:-}" \
        && ! -e "$AIT_TEST_ONCE_MARKER" ]]; then
    : > "$AIT_TEST_ONCE_MARKER"
    if [[ "${AIT_TEST_FOREIGN_COMMIT:-}" == 1 ]]; then
        "$real" "${pre[@]}" add -- "$last" >/dev/null 2>&1
        "$real" "${pre[@]}" commit -q -m foreign -- "$last" >/dev/null 2>&1
    fi
    if [[ "${AIT_TEST_WEDGE_ON_PROBE:-}" == 1 ]]; then
        gd="$("$real" "${pre[@]}" rev-parse --absolute-git-dir)"
        : > "$gd/MERGE_HEAD"
    fi
fi
exec "$real" "$@"
EOF
chmod +x "$IFX_BIN/git"

REPO="$TMP/repo"
ifx_make_repo "$REPO"
# Extra tasks, one per case that needs its own pair.
for n in 11 12 13 14 15 16 17 18 19 21 22 30 31 32 33 34 35 36; do
    ifx_task "$REPO" "$n" "https://github.com/o/r/issues/$n"
done
git -C "$REPO" add -A
git -C "$REPO" commit -qm "ait: Add more tasks"

PENDING_REL="aitasks/metadata/release_issues/pending"

# rec_path <task_id> <issue_url> — the record path the contract names.
rec_path() {
    local key
    key="$(printf '%s' "$2" | git hash-object --stdin | cut -c1-16)"
    printf '%s/%s--%s.rec\n' "$PENDING_REL" "$1" "$key"
}

# The RELEASE_LEDGER* line of the last run ("" when there is none).
ledger_line() { printf '%s\n' "$IFX_OUT" | grep '^RELEASE_LEDGER' | tail -1; }

field() { sed -n "s/^$2=//p" "$1"; }

# A valid pending record body, for planting residue.
record_body() {
    printf 'schema=1\ntask_id=%s\nissue_url=%s\nplatform=github\naction=closed\nrecorded_at=2026-11-10T08:00:00Z\n' "$1" "$2"
}

# The --record-only command from the last run's stderr, as argv for ifx_run.
# Its leading `./.aitask-scripts/aitask_issue_update.sh` is dropped: ifx_run
# runs the real script. The words are our own %q output, so eval is safe.
hint_argv() {
    local cmd
    cmd="$(printf '%s\n' "$IFX_ERR" | sed -n 's/^  \(\.\/\.aitask-scripts\/aitask_issue_update\.sh .*\)$/\1/p' | tail -1)"
    cmd="${cmd#./.aitask-scripts/aitask_issue_update.sh }"
    eval "HINT_ARGV=($cmd)"
}

echo "=== aitask_issue_update.sh release ledger (t2261_1) ==="

# --- (a) one record per action, and (h) the CLI issue argument -------------

U10="https://github.com/o/r/issues/7"
U20="https://gitlab.com/g/p/-/issues/9"

ifx_run "$REPO" --close 10
P10="$(rec_path 10 "$U10")"
assert_eq "(a) closed: exit 0" "0" "$IFX_RC"
assert_eq "(a) closed: recorded line" "RELEASE_LEDGER:recorded:$P10" "$(ledger_line)"
assert_file_exists "(a) closed: record file" "$REPO/$P10"
assert_eq "(a) closed: schema" "1" "$(field "$REPO/$P10" schema)"
assert_eq "(a) closed: task_id" "10" "$(field "$REPO/$P10" task_id)"
assert_eq "(a) closed: issue_url" "$U10" "$(field "$REPO/$P10" issue_url)"
assert_eq "(a) closed: platform" "github" "$(field "$REPO/$P10" platform)"
assert_eq "(a) closed: action" "closed" "$(field "$REPO/$P10" action)"
assert_contains_re "(a) closed: recorded_at is ISO UTC" \
    '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' "$(field "$REPO/$P10" recorded_at)"
assert_eq "(a) closed: committed (status clean)" "" "$(git -C "$REPO" status --porcelain -- "$P10")"
assert_eq "(a) closed: commit message" "ait: Record release-pending issue for t10" \
    "$(git -C "$REPO" log -1 --format=%s -- "$P10")"
assert_contains "(h) gh receives the issue URL" "$(ifx_render gh issue close "$U10")" \
    "$(ifx_log_line 2)"

ifx_run "$REPO" 11
P11="$(rec_path 11 "https://github.com/o/r/issues/11")"
assert_eq "(a) commented: recorded" "RELEASE_LEDGER:recorded:$P11" "$(ledger_line)"
assert_eq "(a) commented: action" "commented" "$(field "$REPO/$P11" action)"

ifx_run "$REPO" --close --no-comment 12
P12="$(rec_path 12 "https://github.com/o/r/issues/12")"
assert_eq "(a) closed_silent: recorded" "RELEASE_LEDGER:recorded:$P12" "$(ledger_line)"
assert_eq "(a) closed_silent: action" "closed_silent" "$(field "$REPO/$P12" action)"

ifx_run "$REPO" --close 20
P20="$(rec_path 20 "$U20")"
assert_eq "(a) gitlab: recorded" "RELEASE_LEDGER:recorded:$P20" "$(ledger_line)"
assert_eq "(a) gitlab: platform" "gitlab" "$(field "$REPO/$P20" platform)"
assert_eq "(a) gitlab: issue_url" "$U20" "$(field "$REPO/$P20" issue_url)"
assert_contains "(h) glab receives the number and -R" "$(ifx_render glab issue close 9 -R g/p)" \
    "$(ifx_log_line 3)"
assert_eq "(a) four committed records, index clean" "" \
    "$(git -C "$REPO" status --porcelain --untracked-files=all -- aitasks/metadata)"

# --- (b) dry run ------------------------------------------------------------

head_before="$(git -C "$REPO" rev-parse HEAD)"
ifx_run "$REPO" --dry-run --close 13
assert_eq "(b) dry-run: exit 0" "0" "$IFX_RC"
assert_eq "(b) dry-run: only the auth check" "$(ifx_render gh auth status)" "$(cat "$STUB_LOG")"
assert_file_not_exists "(b) dry-run: no record" "$REPO/$(rec_path 13 "https://github.com/o/r/issues/13")"
assert_eq "(b) dry-run: no commit" "$head_before" "$(git -C "$REPO" rev-parse HEAD)"
assert_eq "(b) dry-run: no RELEASE_LEDGER line" "" "$(ledger_line)"

# --- (c) failed platform call -----------------------------------------------

export STUB_FAIL=close
ifx_run "$REPO" --close 14
unset STUB_FAIL
assert_exit_nonzero_rc "(c) failed close: non-zero exit" "$IFX_RC"
assert_eq "(c) failed close: no RELEASE_LEDGER line" "" "$(ledger_line)"
assert_file_not_exists "(c) failed close: no record" "$REPO/$(rec_path 14 "https://github.com/o/r/issues/14")"

# --- (d) dedupe ---------------------------------------------------------------

head_before="$(git -C "$REPO" rev-parse HEAD)"
ifx_run "$REPO" --close 10
assert_eq "(d) second run: exit 0" "0" "$IFX_RC"
assert_eq "(d) second run: duplicate" "RELEASE_LEDGER:duplicate:$P10" "$(ledger_line)"
assert_eq "(d) second run: no new commit" "$head_before" "$(git -C "$REPO" rev-parse HEAD)"
assert_eq "(d) still one record for the pair" "1" \
    "$(find "$REPO/$PENDING_REL" -name '10--*.rec' | wc -l | tr -d ' ')"

# --- (e) parallel writers ---------------------------------------------------

run_bg() {  # <tag> <args…>
    local tag="$1"; shift
    ( cd "$REPO" && PATH="$IFX_BIN:$PATH" STUB_LOG="$TMP/par.log" "$IFX_UPDATE" "$@" \
        > "$TMP/par_$tag.out" 2> "$TMP/par_$tag.err"; echo "$?" > "$TMP/par_$tag.rc" ) &
}
for n in 30 31 32 33 34 35; do run_bg "$n" --close "$n"; done
wait
ok=0
for n in 30 31 32 33 34 35; do
    p="$(rec_path "$n" "https://github.com/o/r/issues/$n")"
    if [[ "$(cat "$TMP/par_$n.rc")" == 0 ]] \
            && grep -qxF "RELEASE_LEDGER:recorded:$p" "$TMP/par_$n.out" \
            && [[ -n "$(git -C "$REPO" log -1 --format=%H -- "$p")" ]]; then
        ok=$((ok + 1))
    fi
done
assert_eq "(e) 6 parallel distinct writers: 6 committed records" "6" "$ok"
assert_eq "(e) parallel distinct: index and worktree clean" "" \
    "$(git -C "$REPO" status --porcelain --untracked-files=all -- aitasks/metadata)"

for k in 1 2 3 4; do run_bg "same$k" --issue-url "https://github.com/o/r/issues/99" --close 36; done
wait
rec=0
dup=0
for k in 1 2 3 4; do
    grep -q '^RELEASE_LEDGER:recorded:' "$TMP/par_same$k.out" && rec=$((rec + 1))
    grep -q '^RELEASE_LEDGER:duplicate:' "$TMP/par_same$k.out" && dup=$((dup + 1))
done
assert_eq "(e) 4 identical writers: exactly one file" "1" \
    "$(find "$REPO/$PENDING_REL" -name '36--*.rec' | wc -l | tr -d ' ')"
assert_eq "(e) identical writers: one recorded" "1" "$rec"
assert_eq "(e) identical writers: three duplicates" "3" "$dup"

# --- (f) folded route --------------------------------------------------------

UF="https://github.com/o/other/issues/5"
ifx_run "$REPO" --issue-url "$UF" --close 10
PF="$(rec_path 10 "$UF")"
assert_eq "(f) folded: recorded under the primary id" "RELEASE_LEDGER:recorded:$PF" "$(ledger_line)"
assert_eq "(f) folded: task_id is the primary" "10" "$(field "$REPO/$PF" task_id)"
assert_eq "(f) folded: issue_url is the override" "$UF" "$(field "$REPO/$PF" issue_url)"

# --- (g) commit failure, then --record-only ---------------------------------

U15="https://github.com/o/r/issues/15"
P15="$(rec_path 15 "$U15")"
export AIT_TEST_FAIL_COMMIT=1
ifx_run "$REPO" --close 15
unset AIT_TEST_FAIL_COMMIT
assert_eq "(g) commit failure: exit 3" "3" "$IFX_RC"
assert_eq "(g) commit failure: failed line" "RELEASE_LEDGER_FAILED:commit_failed" "$(ledger_line)"
assert_file_not_exists "(g) commit failure: record rolled back" "$REPO/$P15"
assert_eq "(g) commit failure: no temp file left" "" \
    "$(find "$REPO/$PENDING_REL" -name '.*' -type f)"
assert_exit_nonzero "(g) commit failure: path not in the index" \
    git -C "$REPO" ls-files --error-unmatch -- "$P15"
assert_contains "(g) commit failure: the issue WAS updated" \
    "$(ifx_render gh issue close "$U15" --comment)" "$(ifx_log_line 2)"
assert_contains "(g) commit failure: hint says do not re-run" "do not re-run" "$IFX_ERR"
hint_argv
assert_eq "(g) commit failure: hint names --record-only with the same flags" \
    "--record-only --source github --close 15" "${HINT_ARGV[*]}"
ifx_run "$REPO" "${HINT_ARGV[@]}"
assert_eq "(g) --record-only: exit 0" "0" "$IFX_RC"
assert_eq "(g) --record-only: recorded" "RELEASE_LEDGER:recorded:$P15" "$(ledger_line)"
assert_eq "(g) --record-only: zero CLI calls" "0" "$(ifx_log_count)"
assert_eq "(g) --record-only: committed" "" "$(git -C "$REPO" status --porcelain -- "$P15")"

# --- (i) invalid URL ---------------------------------------------------------

UBAD='https://github.com/o/r/issues/a"b/16'
ifx_run "$REPO" --issue-url "$UBAD" --close 16
assert_eq "(i) invalid URL: exit 3" "3" "$IFX_RC"
assert_eq "(i) invalid URL: refused" "RELEASE_LEDGER_FAILED:invalid_url" "$(ledger_line)"
assert_contains "(i) invalid URL: the issue WAS updated" "gh issue close" "$(ifx_log_line 2)"
assert_contains "(i) invalid URL: no retry will succeed" "no retry will succeed" "$IFX_ERR"
assert_eq "(i) invalid URL: nothing written for t16" "0" \
    "$(find "$REPO/$PENDING_REL" -name '16--*' | wc -l | tr -d ' ')"

# --- (j) malformed reads -----------------------------------------------------

J="$TMP/j"
mkdir -p "$J"
printf 'schema=1\ntask_id=40\ntask_id=40\n' > "$J/dup.rec"
printf 'schema=1\ntask_id=40\nissue_url=https://x/a b\n' > "$J/space.rec"
printf 'schema=1\ntask_id=40\n' > "$J/missing.rec"
printf 'schema=1\ntask_id=4\0000\n' > "$J/nul.rec"
ril_rc() {  # <function> <args…> — the rc of one lib call, in a subshell
    (
        set +u
        cd "$REPO" || exit 99
        SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts"
        . "$SCRIPT_DIR/lib/task_utils.sh"
        . "$SCRIPT_DIR/lib/release_issue_ledger.sh"
        rc=0
        "$@" >/dev/null 2>&1 || rc=$?
        echo "$rc"
    ) 2>/dev/null
}
assert_eq "(j) duplicated key: MALFORMED" "3" "$(ril_rc ril_read "$J/dup.rec" task_id)"
assert_eq "(j) bad charset: MALFORMED" "3" "$(ril_rc ril_read "$J/space.rec" issue_url)"
assert_eq "(j) missing field: MALFORMED" "3" "$(ril_rc ril_read "$J/missing.rec" recorded_at)"
assert_eq "(j) NUL byte: MALFORMED" "3" "$(ril_rc ril_read "$J/nul.rec" task_id)"
assert_eq "(j) unknown field: rc 2" "2" "$(ril_rc ril_read "$J/missing.rec" nosuchfield)"
assert_eq "(j) valid field still reads" "0" "$(ril_rc ril_read "$REPO/$P10" issue_url)"
UA="https://github.com/o/r/issues/41"
PC="$(rec_path 41 "$UA")"
record_body 41 "https://github.com/o/r/issues/4100" > "$REPO/$PC"
assert_eq "(j) same name, different stored URL: hash_collision" "4" "$(ril_rc ril_find 41 "$UA")"
rm -f "$REPO/$PC"

# --- (l) bitbucket -----------------------------------------------------------

files_before="$(find "$REPO/$PENDING_REL" -type f | sort)"
ifx_run "$REPO" --issue-url "https://bitbucket.org/w/r/issues/3" --close 10
assert_eq "(l) bitbucket: exit 0" "0" "$IFX_RC"
assert_eq "(l) bitbucket: skipped" "RELEASE_LEDGER:skipped:unsupported_platform" "$(ledger_line)"
assert_eq "(l) bitbucket: nothing written" "$files_before" "$(find "$REPO/$PENDING_REL" -type f | sort)"

# --- (m) --record-only flag rules -------------------------------------------

ifx_run "$REPO" --record-only --dry-run --close 10
assert_eq "(m) --record-only with --dry-run: refused" "1" "$IFX_RC"
assert_contains "(m) --record-only with --dry-run: says why" "cannot be combined with --dry-run" "$IFX_ERR"
assert_eq "(m) --record-only with --dry-run: zero CLI calls" "0" "$(ifx_log_count)"

# --- (n) untracked residue of a killed writer --------------------------------

U17="https://github.com/o/r/issues/17"
P17="$(rec_path 17 "$U17")"
record_body 17 "$U17" > "$REPO/$P17"
planted="$(cat "$REPO/$P17")"
ifx_run "$REPO" --record-only --close 17
assert_eq "(n) untracked residue: exit 0" "0" "$IFX_RC"
assert_eq "(n) untracked residue: committed by this run" "RELEASE_LEDGER:recorded:$P17" "$(ledger_line)"
assert_eq "(n) untracked residue: HEAD holds the planted bytes" "$planted" \
    "$(git -C "$REPO" show "HEAD:$P17")"
assert_eq "(n) untracked residue: status clean" "" "$(git -C "$REPO" status --porcelain -- "$P17")"
assert_eq "(n) untracked residue: zero CLI calls" "0" "$(ifx_log_count)"
head_before="$(git -C "$REPO" rev-parse HEAD)"
ifx_run "$REPO" --record-only --close 17
assert_eq "(n) then a duplicate" "RELEASE_LEDGER:duplicate:$P17" "$(ledger_line)"
assert_eq "(n) duplicate: HEAD unchanged" "$head_before" "$(git -C "$REPO" rev-parse HEAD)"

# --- (o) staged residue ------------------------------------------------------

U18="https://github.com/o/r/issues/18"
P18="$(rec_path 18 "$U18")"
record_body 18 "$U18" > "$REPO/$P18"
git -C "$REPO" add -- "$P18"
ifx_run "$REPO" --record-only --close 18
assert_eq "(o) staged residue: committed by this run" "RELEASE_LEDGER:recorded:$P18" "$(ledger_line)"
assert_eq "(o) staged residue: index clean" "" "$(git -C "$REPO" status --porcelain -- "$P18")"

# --- (p) invalid residue -----------------------------------------------------

U19="https://github.com/o/r/issues/19"
P19="$(rec_path 19 "$U19")"
record_body 19 "$U19" | grep -v '^recorded_at=' > "$REPO/$P19"
ifx_run "$REPO" --record-only --close 19
assert_eq "(p) invalid residue: exit 3" "3" "$IFX_RC"
assert_eq "(p) invalid residue: malformed" "RELEASE_LEDGER_FAILED:malformed_record:$P19" "$(ledger_line)"
assert_file_exists "(p) invalid residue: file kept" "$REPO/$P19"
assert_exit_nonzero "(p) invalid residue: not committed" \
    git -C "$REPO" rev-parse --verify --quiet "HEAD:$P19"
assert_contains "(p) invalid residue: the hint names the path" "$P19" "$IFX_ERR"
rm -f "$REPO/$P19"

# --- (q) an edited committed record -----------------------------------------

head_before="$(git -C "$REPO" rev-parse HEAD)"
sed -i.bak 's/^recorded_at=.*/recorded_at=2000-01-01T00:00:00Z/' "$REPO/$P10" && rm -f "$REPO/$P10.bak"
edited="$(cat "$REPO/$P10")"
ifx_run "$REPO" --record-only --close 10
assert_eq "(q) edited record: exit 3" "3" "$IFX_RC"
assert_eq "(q) edited record: uncommitted_change" "RELEASE_LEDGER_FAILED:uncommitted_change:$P10" \
    "$(ledger_line)"
assert_eq "(q) edited record: the edit is kept" "$edited" "$(cat "$REPO/$P10")"
assert_eq "(q) edited record: HEAD unchanged" "$head_before" "$(git -C "$REPO" rev-parse HEAD)"
git -C "$REPO" checkout -q -- "$P10"

# --- (u) a committed but malformed matching record --------------------------
#
# Being committed is not being valid: a committed record the release consumer
# would reject must not be reported as a duplicate.

U13="https://github.com/o/r/issues/13"
P13="$(rec_path 13 "$U13")"
record_body 13 "$U13" | sed -e 's/^schema=1$/schema=999/' -e '/^recorded_at=/d' > "$REPO/$P13"
git -C "$REPO" add -- "$P13"
git -C "$REPO" commit -qm "ait: Plant a corrupt record" -- "$P13"
corrupt="$(cat "$REPO/$P13")"
head_before="$(git -C "$REPO" rev-parse HEAD)"
ifx_run "$REPO" --record-only --close 13
assert_eq "(u) committed corrupt record: exit 3" "3" "$IFX_RC"
assert_eq "(u) committed corrupt record: malformed, not duplicate" \
    "RELEASE_LEDGER_FAILED:malformed_record:$P13" "$(ledger_line)"
assert_eq "(u) committed corrupt record: file preserved" "$corrupt" "$(cat "$REPO/$P13")"
assert_eq "(u) committed corrupt record: HEAD unchanged" "$head_before" "$(git -C "$REPO" rev-parse HEAD)"
assert_eq "(u) committed corrupt record: no tracked change" "" "$(git -C "$REPO" status --porcelain -- "$P13")"
assert_contains "(u) committed corrupt record: the hint names the path" "$P13" "$IFX_ERR"

# --- (v) released hits are validated as whole released records (t2261_2)

U11="https://github.com/o/r/issues/11"
REL_REL="aitasks/metadata/release_issues/released/v1.0.0"
mkdir -p "$REPO/$REL_REL"
# t11's pending record (from (a)) moves to released/, as the consumer does.
git -C "$REPO" mv -- "$P11" "$REL_REL/"
PR11="$REL_REL/$(basename "$P11")"
printf 'released_tag=v1.0.0\n' >> "$REPO/$PR11"
git -C "$REPO" add -- "$PR11"
git -C "$REPO" commit -qm "ait: Release t11" -- "$P11" "$PR11"
ifx_run "$REPO" --record-only 11
# Only one of the four released fields: not a released record, so not a
# duplicate of anything.
assert_eq "(v) partial released fields: malformed" \
    "RELEASE_LEDGER_FAILED:malformed_record:$PR11" "$(ledger_line)"
printf 'notified_at=2026-11-10T10:00:00Z\noutcome=posted\ncommits=%s\n' \
    "$(git -C "$REPO" rev-parse HEAD)" >> "$REPO/$PR11"
git -C "$REPO" commit -qm "ait: Complete released t11" -- "$PR11"
ifx_run "$REPO" --record-only 11
assert_eq "(v) valid released record: duplicate" "RELEASE_LEDGER:duplicate:$PR11" "$(ledger_line)"
sed -i.bak 's/^schema=1$/schema=999/' "$REPO/$PR11" && rm -f "$REPO/$PR11.bak"
git -C "$REPO" commit -qm "ait: Corrupt released t11" -- "$PR11"
ifx_run "$REPO" --record-only 11
assert_eq "(v) corrupt released record: exit 3" "3" "$IFX_RC"
assert_eq "(v) corrupt released record: malformed" \
    "RELEASE_LEDGER_FAILED:malformed_record:$PR11" "$(ledger_line)"
assert_file_not_exists "(v) corrupt released record: no new pending record" "$REPO/$P11"

# --- (w) a pending record may not carry released-only keys (t2261_2) --------
#
# ril_validate_pending_record's whitelist is pending-only. Widening it to the
# released keys would let these records validate, because the six pending
# fields are all still present and valid.

U23="https://github.com/o/r/issues/23"
ifx_task "$REPO" 23 "$U23"
ifx_run "$REPO" --record-only 23
P23="$(rec_path 23 "$U23")"
assert_eq "(w) setup: recorded" "RELEASE_LEDGER:recorded:$P23" "$(ledger_line)"
printf 'outcome=posted\n' >> "$REPO/$P23"
git -C "$REPO" commit -qm "ait: Corrupt t23" -- "$P23"
ifx_run "$REPO" --record-only 23
assert_eq "(w) extra released key: malformed" \
    "RELEASE_LEDGER_FAILED:malformed_record:$P23" "$(ledger_line)"
printf 'outcome=bogus\n' >> "$REPO/$P23"
git -C "$REPO" commit -qm "ait: Corrupt t23 again" -- "$P23"
ifx_run "$REPO" --record-only 23
assert_eq "(w) duplicated invalid released key: malformed" \
    "RELEASE_LEDGER_FAILED:malformed_record:$P23" "$(ledger_line)"
assert_exit_nonzero "(w) the validator itself refuses it" bash -c \
    "cd '$REPO' && SCRIPT_DIR='$PROJECT_DIR/.aitask-scripts' && . '$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh' && . '$PROJECT_DIR/.aitask-scripts/lib/release_issue_ledger.sh' && ril_validate_pending_record '$P23'"

# --- (r) competing commit, early window (before the status check) -----------

U21="https://github.com/o/r/issues/21"
P21="$(rec_path 21 "$U21")"
export AIT_TEST_FOREIGN_COMMIT=1 AIT_TEST_ONCE_MARKER="$TMP/once_r"
ifx_run "$REPO" --close 21
unset AIT_TEST_FOREIGN_COMMIT AIT_TEST_ONCE_MARKER
assert_file_exists "(r) early window: the wrapper fired" "$TMP/once_r"
assert_eq "(r) early window: exit 0" "0" "$IFX_RC"
assert_eq "(r) early window: recorded" "RELEASE_LEDGER:recorded:$P21" "$(ledger_line)"
assert_file_exists "(r) early window: file kept" "$REPO/$P21"
assert_exit_zero "(r) early window: HEAD holds this run's bytes" \
    git -C "$REPO" diff --quiet HEAD -- "$P21"
assert_eq "(r) early window: no tracked deletion" "" "$(git -C "$REPO" status --porcelain -- "$P21")"
assert_eq "(r) early window: the foreign commit is HEAD" "foreign" "$(git -C "$REPO" log -1 --format=%s)"

# --- (t) competing commit, late window (after the status check) -------------
#
# The helper's own seam fires between task_git_commit_scoped's status check and
# its `task_git commit`; the competing commit makes that commit fail with
# "nothing to commit", so the helper returns 1, not 2.

U22="https://github.com/o/r/issues/22"
P22="$(rec_path 22 "$U22")"
mkdir -p "$AITASKS_LOCK_DIR"
: > "$AITASKS_LOCK_DIR/.ait_commit_scoped_test_seams"
export AIT_COMMIT_SCOPED_SEAM_PREGIT="git commit -q -m foreign -- '$P22'"
ifx_run "$REPO" --close 22
unset AIT_COMMIT_SCOPED_SEAM_PREGIT
rm -f "$AITASKS_LOCK_DIR/.ait_commit_scoped_test_seams"
assert_contains "(t) late window: the seam fired" "TEST SEAM ACTIVE" "$IFX_ERR"
assert_eq "(t) late window: exit 0" "0" "$IFX_RC"
assert_eq "(t) late window: recorded" "RELEASE_LEDGER:recorded:$P22" "$(ledger_line)"
assert_file_exists "(t) late window: file kept" "$REPO/$P22"
assert_exit_zero "(t) late window: HEAD holds this run's bytes" \
    git -C "$REPO" diff --quiet HEAD -- "$P22"
assert_eq "(t) late window: no tracked deletion" "" "$(git -C "$REPO" status --porcelain -- "$P22")"
assert_eq "(t) late window: the foreign commit is HEAD" "foreign" "$(git -C "$REPO" log -1 --format=%s)"

# --- (k) branch mode, and (s) a real die after publish ----------------------

BR="$TMP/branch"
mkdir -p "$BR"
git -C "$BR" init -q -b main
git -C "$BR" config user.email t@example.com
git -C "$BR" config user.name Test
git -C "$BR" config commit.gpgsign false
printf '/aitasks\n/aiplans\n/.aitask-data/\n' > "$BR/.gitignore"
git -C "$BR" add .gitignore
git -C "$BR" commit -qm init
empty_tree="$(git -C "$BR" mktree < /dev/null)"
data_root="$(echo "ait: Initialize aitask-data branch" | git -C "$BR" commit-tree "$empty_tree")"
git -C "$BR" update-ref refs/heads/aitask-data "$data_root"
git -C "$BR" worktree add -q .aitask-data aitask-data
mkdir -p "$BR/.aitask-data/aitasks/metadata" "$BR/.aitask-data/aiplans"
ln -s .aitask-data/aitasks "$BR/aitasks"
ln -s .aitask-data/aiplans "$BR/aiplans"
git -C "$BR/.aitask-data" config user.email t@example.com
git -C "$BR/.aitask-data" config user.name Test
git -C "$BR/.aitask-data" config commit.gpgsign false
ifx_task "$BR" 10 "$U10"
ifx_task "$BR" 12 "https://github.com/o/r/issues/12"
git -C "$BR/.aitask-data" add -A
git -C "$BR/.aitask-data" commit -qm "data init"
echo x > "$BR/x.txt"
git -C "$BR" add x.txt
git -C "$BR" commit -qm "feature: x (t10)"
main_head="$(git -C "$BR" rev-parse HEAD)"

ifx_run "$BR" --close 10
PB10="$(rec_path 10 "$U10")"
assert_eq "(k) branch mode: recorded" "RELEASE_LEDGER:recorded:$PB10" "$(ledger_line)"
assert_eq "(k) branch mode: committed on aitask-data" "ait: Record release-pending issue for t10" \
    "$(git -C "$BR/.aitask-data" log -1 --format=%s -- "$PB10")"
assert_eq "(k) branch mode: data worktree clean" "" \
    "$(git -C "$BR/.aitask-data" status --porcelain --untracked-files=all)"
assert_eq "(k) branch mode: main HEAD untouched" "$main_head" "$(git -C "$BR" rev-parse HEAD)"
assert_eq "(k) branch mode: main index and worktree untouched" "" "$(git -C "$BR" status --porcelain)"

U12="https://github.com/o/r/issues/12"
PB12="$(rec_path 12 "$U12")"
data_gitdir="$(git -C "$BR/.aitask-data" rev-parse --absolute-git-dir)"
export AIT_TEST_WEDGE_ON_PROBE=1 AIT_TEST_ONCE_MARKER="$TMP/once_s"
ifx_run "$BR" --close 12
unset AIT_TEST_WEDGE_ON_PROBE AIT_TEST_ONCE_MARKER
assert_file_exists "(s) die after publish: the wrapper fired" "$TMP/once_s"
assert_eq "(s) die after publish: exit 3" "3" "$IFX_RC"
assert_eq "(s) die after publish: aborted" "RELEASE_LEDGER_FAILED:aborted" "$(ledger_line)"
# The helper's in-loop guard prints its own die message, and the recovery hint
# independently reads the wedge back from the data worktree; this pins the text
# both carry.
assert_contains "(s) die after publish: the hint names the wedge" "stuck mid-MERGE_HEAD" "$IFX_ERR"
assert_contains "(s) die after publish: the recovery hint" "--record-only" "$IFX_ERR"
assert_file_not_exists "(s) die after publish: owned file removed" "$BR/$PB12"
assert_eq "(s) die after publish: no temp file left" "" \
    "$(find "$BR/aitasks/metadata/release_issues" -name '.*' -type f 2>/dev/null)"
rm -f "$data_gitdir/MERGE_HEAD"
assert_exit_nonzero "(s) die after publish: path not in the index" \
    git -C "$BR/.aitask-data" ls-files --error-unmatch -- "$PB12"
hint_argv
started="$(date +%s)"
ifx_run "$BR" "${HINT_ARGV[@]}"
elapsed=$(( $(date +%s) - started ))
assert_eq "(s) after recovery: recorded" "RELEASE_LEDGER:recorded:$PB12" "$(ledger_line)"
# The lock was released by the dying subshell's EXIT trap: the next writer does
# not wait out the acquire retries (20 x 0.3 s).
if (( elapsed < 5 )); then assert_record_pass; else
    assert_record_fail; echo "FAIL: (s) the ledger lock was not released (recovery took ${elapsed}s)"
fi

# --- (s2) a die with the record already staged (t2271) --------------------
# The wedge lands AFTER the helper staged the new `.rec` path, so the scoped
# commit's guard dies with it in the shared index. On a wedged worktree the
# cleanup cannot prove the entry is still ours (the in-progress operation may own
# it), so it leaves it and names it on stderr (safe unwind: t2277). _ril_record_cleanup runs that
# cleanup in a nested subshell for lock-release isolation; the warning must
# survive that wrapper, which used to discard both streams.
U13="https://github.com/o/r/issues/13"
ifx_task "$BR" 13 "$U13"
git -C "$BR/.aitask-data" add -A
git -C "$BR/.aitask-data" commit -qm "add t13"
PB13="$(rec_path 13 "$U13")"
export AIT_TEST_WEDGE_ON_ADD=1 AIT_TEST_ADD_MARKER="$TMP/once_s2"
ifx_run "$BR" --close 13
unset AIT_TEST_WEDGE_ON_ADD AIT_TEST_ADD_MARKER
assert_file_exists "(s2) staged then wedged: the wrapper fired" "$TMP/once_s2"
assert_exit_nonzero_rc "(s2) staged then wedged: the run failed" "$IFX_RC"
assert_contains "(s2) staged then wedged: the guard's message" "stuck mid-MERGE_HEAD" "$IFX_ERR"
assert_contains "(s2) staged then wedged: the cleanup says it left entries" \
    "were LEFT in the shared index" "$IFX_ERR"
assert_contains "(s2) staged then wedged: the cleanup names the record" "$PB13" "$IFX_ERR"
assert_exit_zero "(s2) staged then wedged: the entry is preserved (documented limitation)" \
    git -C "$BR/.aitask-data" ls-files --error-unmatch -- "$PB13"
rm -f "$data_gitdir/MERGE_HEAD"
git -C "$BR/.aitask-data" reset -q -- "$PB13"
hint_argv
started="$(date +%s)"
ifx_run "$BR" "${HINT_ARGV[@]}"
elapsed=$(( $(date +%s) - started ))
assert_eq "(s2) after recovery: recorded" "RELEASE_LEDGER:recorded:$PB13" "$(ledger_line)"
if (( elapsed < 5 )); then assert_record_pass; else
    assert_record_fail; echo "FAIL: (s2) the ledger lock was not released (recovery took ${elapsed}s)"
fi

# --- summary -----------------------------------------------------------------
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
