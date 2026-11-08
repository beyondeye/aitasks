#!/usr/bin/env bash
# test_premise_check_workflow.sh - the premise check's workflow transactions
# (t1663_4). Run: bash tests/test_premise_check_workflow.sh
#
# task-workflow Step 3 Check 7 prompts on ASK_STALE; the user's confirmation is
# applied by `aitask_premise_stale.sh advance` with ownership held. These cases
# pin what the design record calls the required test -- the one that tells
# "correctly quiet" from "never runs": seed -> change -> prompt -> confirm ->
# advance -> NO re-fire -- for EVERY evidence class, plus the two TOCTOU axes,
# the all-or-nothing write, the overflow case and the pre-claim race.
#
#   A  changed (end-to-end, task created by aitask_create.sh --file-ref)
#   B  deleted -> retired on the re-check; all-deleted -> SKIP all_retired
#   C  never_existed: kept by default, removed only on --remove-ref, a live ref
#      is never removable, range-suffixed entries all go, a future file appears
#   D  invalid_reference recurs (documented); an invalid list is unwritable
#   E  unverifiable evidence refuses the advance
#   F  TOCTOU revision axis: the advance writes the PROMPTED sha, not HEAD
#   G  TOCTOU metadata axis: scope / baseline mutated -> MISMATCH, no write
#   H  overflow: 12 changed files, nothing truncated, all advanced past
#   I  all-or-nothing: approved removal + nonexistent --checked -> untouched
#   J  CLI misuse dies, file untouched
#   K  pre-claim race: a live holder -> the guarded claim refuses
#   L  structural pins over the rendered procedure / SKILL / planning
#   M  the helper is whitelisted on every agent surface
#
# SRC (default: this checkout's .aitask-scripts) lets a scratch mirror run the
# suite against mutated scripts (the t1663_4 red proofs). Fixtures symlink
# .aitask-scripts to SRC, so every script runs from the copy under test.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/fixture_root.sh
. "$PROJECT_DIR/tests/lib/fixture_root.sh"

SRC="${SRC:-$PROJECT_DIR/.aitask-scripts}"
SKILLS_SRC="${SKILLS_SRC:-$PROJECT_DIR/.claude/skills}"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()
cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]+"${CLEANUP_DIRS[@]}"}"; do [[ -n "$d" ]] && rm -rf "$d"; done
}
trap cleanup EXIT

PY="$( . "$SRC/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
    echo "SKIP: no Python interpreter (the premise core needs one)"
    exit 0
fi

check() {
    local desc="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $desc"
        echo "  expected: $expected"
        echo "  actual:   $actual"
    fi
}

TS="2026-11-01 09:00"

# --- Fixture ---------------------------------------------------------------

# new_project -> echoes a clone of a bare remote, scripts symlinked to SRC.
new_project() {
    local tmp
    tmp="$(fixture_mktemp_d test_premise_wf)" || return 1
    git init --bare --quiet "$tmp/remote.git"
    git clone --quiet "$tmp/remote.git" "$tmp/p" 2>/dev/null
    (
        cd "$tmp/p" || exit 1
        git config user.email "a@test.com"
        git config user.name "A"
        git config commit.gpgsign false
        mkdir -p aitasks/archived aitasks/metadata aitasks/new aiplans lib
        ln -s "$SRC" .aitask-scripts
        printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
            > aitasks/metadata/task_types.txt
        : > aitasks/metadata/labels.txt
        printf 'aitasks/new/\n.aitask-scripts\n' > .gitignore
        local f
        for f in a live live2 r m; do echo "one" > "lib/$f.sh"; done
        git add -A
        git commit -q -m "chore: seed (t1)"
        git push -q 2>/dev/null
        ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1
        ./.aitask-scripts/aitask_lock.sh --init >/dev/null 2>&1
    ) || return 1
    printf '%s' "$tmp/p"
}

# mk_task <repo> <id> <file_references flow-list body> [baseline-sha]
# Writes and commits aitasks/t<id>_x.md; echoes its repo-relative path.
mk_task() {
    local d="$1" id="$2" refs="$3" sha="${4:-}"
    [[ -n "$sha" ]] || sha="$(git -C "$d" rev-parse HEAD)"
    local rel="aitasks/t${id}_x.md"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: feature"
        echo "status: Ready"
        echo "labels: []"
        echo "file_references: [$refs]"
        echo "premise_baseline: $sha @ $TS"
        echo "created_at: $TS"
        echo "updated_at: $TS"
        echo "---"
        echo ""
        echo "Body"
    } > "$d/$rel"
    git -C "$d" add -- "$rel"
    git -C "$d" commit -q -m "ait: add t$id"
    printf '%s' "$rel"
}

edit_commit() { # edit_commit <repo> <subject> <file...>
    local d="$1" subject="$2"
    shift 2
    local f
    for f in "$@"; do mkdir -p "$d/$(dirname "$f")"; echo "$RANDOM$RANDOM" >> "$d/$f"; done
    git -C "$d" add -A -- "$@"
    git -C "$d" commit -q -m "$subject"
}

pcheck() { ( cd "$1" && ./.aitask-scripts/aitask_premise_stale.sh check "$2" 2>/dev/null ); }
OWNER="a@test.com"
# One session anchor for the whole suite: the locks this suite takes and the
# advances it runs must name the SAME session (advance proves it with
# lock_anchor_is_self). The suite's own shell is a live process for its whole run.
export AIT_AGENT_PID=$$
task_id_of() { basename "$1" | sed -E 's/^t([0-9]+(_[0-9]+)?)_.*/\1/'; }
padv() {   # padv <repo> <task> [args...] -- as the OWNER, holding the task's lock
    local d="$1" t="$2" id
    shift 2
    id=$(task_id_of "$t")
    ( cd "$d" || exit 1
      ./.aitask-scripts/aitask_lock.sh --check "$id" >/dev/null 2>&1 \
        || ./.aitask-scripts/aitask_lock.sh --lock "$id" --email "$OWNER" >/dev/null 2>&1 )
    ( cd "$d" && ./.aitask-scripts/aitask_premise_stale.sh advance "$t" --owner "$OWNER" "$@" 2>&1 )
}
dec() { printf '%s\n' "$1" | sed -n 's/^DECISION://p' | tail -n1; }
val() { printf '%s\n' "$1" | sed -n "s/^$2://p" | head -n1; }
count_of() { printf '%s\n' "$1" | grep -c "^$2" || true; }
field() {
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"
}
sha_of_baseline() { field "$1" premise_baseline | sed 's/ @ .*//'; }
digest() { cksum < "$1"; }
subject_head() { git -C "$1" log -1 --format=%s; }

fixture_root_init
P="$(new_project)"
assert_fixture_registered "new_project dirs land under the registered FIXTURE_ROOT" "$P"

# === A: changed, end-to-end ================================================
echo "=== A: changed file, task created by aitask_create.sh --file-ref ==="
ERR="$P/../create.err"
CREATED=$( cd "$P" && ./.aitask-scripts/aitask_create.sh --batch --name e2e --desc "e2e" \
    --type feature --priority medium --effort low --file-ref lib/a.sh --commit --silent 2>"$ERR" )
check "A: aitask_create produced a task file" "yes" "$([[ -n "$CREATED" && -f "$P/$CREATED" ]] && echo yes || echo no)"
TA="$CREATED"
out=$(pcheck "$P" "$TA")
check "A: freshly seeded task reads FRESH" "FRESH" "$(dec "$out")"
edit_commit "$P" "feature: touch a (t900)" lib/a.sh
out=$(pcheck "$P" "$TA")
check "A: a changed watched file reads ASK_STALE" "ASK_STALE" "$(dec "$out")"
check "A: ...naming the file and its task" "1" "$(count_of "$out" 'CHANGED:lib/a.sh|1|900')"
CK=$(val "$out" CHECKED); FP=$(val "$out" FINGERPRINT)
aout=$(padv "$P" "$TA" --checked "$CK" --fingerprint "$FP")
check "A: advance reports ADVANCED:<CHECKED>" "1" "$(count_of "$aout" "ADVANCED:$CK\$")"
check "A: stored baseline is the CHECKED sha" "$CK" "$(sha_of_baseline "$P/$TA")"
check "A: the advance was committed" "ait: Advance premise baseline for t$(basename "$TA" | sed -E 's/^t([0-9_]+)_.*/\1/')" \
    "$(subject_head "$P")"
out=$(pcheck "$P" "$TA")
check "A: immediate re-check reads FRESH (no re-fire)" "FRESH" "$(dec "$out")"

# === B: deleted ============================================================
echo "=== B: deleted watched file -> retired on the re-check ==="
edit_commit "$P" "feature: add d1 (t901)" lib/d1.sh
TB=$(mk_task "$P" 501 "lib/d1.sh, lib/live.sh")
git -C "$P" rm -q lib/d1.sh && git -C "$P" commit -q -m "chore: drop d1 (t902)"
out=$(pcheck "$P" "$TB")
check "B: deletion reads ASK_STALE" "ASK_STALE" "$(dec "$out")"
check "B: ...as DELETED with its culprit" "1" "$(count_of "$out" 'DELETED:lib/d1.sh|902|')"
aout=$(padv "$P" "$TB" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)")
check "B: advance succeeds" "1" "$(count_of "$aout" 'ADVANCED:')"
out=$(pcheck "$P" "$TB")
check "B: re-check reads FRESH (the deleted path is retired, not UNKNOWN)" "FRESH" "$(dec "$out")"
check "B: ...with no UNKNOWN row" "0" "$(count_of "$out" 'UNKNOWN:')"
check "B: ...and DISPLAY counts the retired path" "1" \
    "$(printf '%s\n' "$out" | grep -c '^DISPLAY:All 1 watched file(s) unchanged.*1 deleted at or before the baseline (retired)')"

edit_commit "$P" "feature: add d2 (t903)" lib/d2.sh
TB2=$(mk_task "$P" 502 "lib/d2.sh")
git -C "$P" rm -q lib/d2.sh && git -C "$P" commit -q -m "chore: drop d2 (t904)"
out=$(pcheck "$P" "$TB2")
padv "$P" "$TB2" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" >/dev/null
out=$(pcheck "$P" "$TB2")
check "B: all-deleted scope re-checks as SKIP, never FRESH" "SKIP" "$(dec "$out")"
check "B: ...reason all_retired" "1" "$(printf '%s\n' "$out" | grep -c '^DISPLAY:Premise check skipped (all_retired)')"

# === C: never_existed ======================================================
echo "=== C: never_existed references ==="
TC=$(mk_task "$P" 503 "lib/live2.sh, lib/future.sh")
out=$(pcheck "$P" "$TC")
check "C: a never-existing reference reads ASK_STALE" "ASK_STALE" "$(dec "$out")"
check "C: ...as UNKNOWN never_existed" "1" "$(count_of "$out" 'UNKNOWN:lib/future.sh|never_existed')"
padv "$P" "$TC" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" >/dev/null
check "C: kept by default -- the reference is still in file_references" "1" \
    "$(field "$P/$TC" file_references | grep -c 'lib/future.sh')"
out=$(pcheck "$P" "$TC")
check "C: a kept never-existing reference keeps reporting (documented)" "1" \
    "$(count_of "$out" 'UNKNOWN:lib/future.sh|never_existed')"
aout=$(padv "$P" "$TC" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" \
    --remove-ref lib/future.sh)
check "C: explicit removal reports REMOVED" "1" "$(count_of "$aout" 'REMOVED:lib/future.sh$')"
check "C: ...and ADVANCED" "1" "$(count_of "$aout" 'ADVANCED:')"
check "C: the reference is gone" "0" "$(field "$P/$TC" file_references | grep -c 'lib/future.sh')"
check "C: the live reference stays" "1" "$(field "$P/$TC" file_references | grep -c 'lib/live2.sh')"
out=$(pcheck "$P" "$TC")
check "C: re-check after removal reads FRESH" "FRESH" "$(dec "$out")"

TC2=$(mk_task "$P" 504 "lib/live2.sh, lib/ghost.sh")
out=$(pcheck "$P" "$TC2")
before=$(digest "$P/$TC2")
aout=$(padv "$P" "$TC2" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" \
    --remove-ref lib/live2.sh)
check "C: a LIVE reference is never removable" "1" "$(count_of "$aout" 'ADVANCE_REFUSED:not_removable|lib/live2.sh')"
check "C: ...task file byte-identical" "$before" "$(digest "$P/$TC2")"

TC3=$(mk_task "$P" 505 '"lib/ghost2.sh:1-3", "lib/ghost2.sh:9", lib/live2.sh')
out=$(pcheck "$P" "$TC3")
aout=$(padv "$P" "$TC3" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" \
    --remove-ref lib/ghost2.sh)
check "C: every range-suffixed entry of the removed path goes" "2" "$(count_of "$aout" 'REMOVED:lib/ghost2.sh')"
check "C: ...leaving only the live entry" "[lib/live2.sh]" "$(field "$P/$TC3" file_references)"

TC4=$(mk_task "$P" 506 "lib/later.sh")
out=$(pcheck "$P" "$TC4")
check "C: a not-yet-created file reads never_existed" "1" "$(count_of "$out" 'UNKNOWN:lib/later.sh|never_existed')"
edit_commit "$P" "feature: add later (t905)" lib/later.sh
out=$(pcheck "$P" "$TC4")
check "C: once created it reads absent_at_baseline (evidence)" "1" "$(count_of "$out" 'UNKNOWN:lib/later.sh|absent_at_baseline')"
padv "$P" "$TC4" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" >/dev/null
check "C: ...and FRESH after the advance" "FRESH" "$(dec "$(pcheck "$P" "$TC4")")"

# === D: invalid_reference ==================================================
echo "=== D: invalid references ==="
TD=$(mk_task "$P" 507 "lib/live2.sh, null")
out=$(pcheck "$P" "$TD")
check "D: a non-string entry reads ASK_STALE" "ASK_STALE" "$(dec "$out")"
padv "$P" "$TD" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" >/dev/null
out=$(pcheck "$P" "$TD")
check "D: it recurs after the advance (fixed by hand only) -- never FRESH" "ASK_STALE" "$(dec "$out")"
check "D: ...naming only the defect" "1" "$(count_of "$out" 'UNKNOWN:')"
check "D: ...as invalid_reference" "1" "$(count_of "$out" 'UNKNOWN:.*|invalid_reference')"

TD2=$(mk_task "$P" 508 "lib/ghost3.sh, null")
out=$(pcheck "$P" "$TD2")
before=$(digest "$P/$TD2")
aout=$(padv "$P" "$TD2" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" \
    --remove-ref lib/ghost3.sh)
check "D: removal from a list holding an invalid entry is refused" "1" \
    "$(count_of "$aout" 'ADVANCE_REFUSED:list_unwritable|1')"
check "D: ...task file byte-identical" "$before" "$(digest "$P/$TD2")"

# === E: unverifiable =======================================================
echo "=== E: unverifiable evidence refuses the advance ==="
TE=$(mk_task "$P" 509 "lib/m.sh")
edit_commit "$P" "feature: touch m (t906)" lib/m.sh
# Take the lock BEFORE breaking `git log`: the lock script needs a working log.
( cd "$P" && ./.aitask-scripts/aitask_lock.sh --lock 509 --email "$OWNER" >/dev/null 2>&1 )
git -C "$P" config log.date invalid-date-mode
out=$(pcheck "$P" "$TE")
check "E: a failed history query reads history_unavailable" "1" "$(count_of "$out" 'UNKNOWN:lib/m.sh|history_unavailable')"
before=$(digest "$P/$TE")
aout=$(padv "$P" "$TE" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)")
git -C "$P" config --unset log.date
check "E: advance is refused as unverifiable" "1" "$(count_of "$aout" 'ADVANCE_REFUSED:unverifiable|1')"
check "E: ...task file byte-identical" "$before" "$(digest "$P/$TE")"

# === F: TOCTOU revision axis ===============================================
echo "=== F: TOCTOU revision -- the advance writes the prompted sha ==="
TF=$(mk_task "$P" 510 "lib/r.sh")
edit_commit "$P" "feature: r one (t907)" lib/r.sh
out=$(pcheck "$P" "$TF")
CK=$(val "$out" CHECKED); FP=$(val "$out" FINGERPRINT)
edit_commit "$P" "feature: r two (t908)" lib/r.sh
HEAD_NOW=$(git -C "$P" rev-parse HEAD)
padv "$P" "$TF" --checked "$CK" --fingerprint "$FP" >/dev/null
check "F: stored baseline == prompted CHECKED" "$CK" "$(sha_of_baseline "$P/$TF")"
check "F: ...which is NOT the newer HEAD" "differs" "$([[ "$CK" != "$HEAD_NOW" ]] && echo differs || echo same)"
out=$(pcheck "$P" "$TF")
check "F: re-check names exactly the one newer commit" "1" "$(count_of "$out" 'CHANGED:lib/r.sh|1|908$')"

# === G: TOCTOU metadata axis ===============================================
echo "=== G: TOCTOU metadata -- a mutated scope or baseline voids the answer ==="
TG=$(mk_task "$P" 511 "lib/m.sh")
edit_commit "$P" "feature: m again (t909)" lib/m.sh
out=$(pcheck "$P" "$TG")
( cd "$P" && ./.aitask-scripts/aitask_update.sh --batch 511 --file-ref lib/live2.sh --silent >/dev/null 2>&1 )
check "G: the scope mutation really landed" "1" "$(field "$P/$TG" file_references | grep -c 'lib/live2.sh')"
before=$(digest "$P/$TG")
aout=$(padv "$P" "$TG" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)")
check "G: scope mutation -> MISMATCH" "1" "$(count_of "$aout" 'MISMATCH:')"
check "G: ...followed by the fresh protocol" "1" "$(count_of "$aout" 'DECISION:')"
check "G: ...task file byte-identical" "$before" "$(digest "$P/$TG")"

TG2=$(mk_task "$P" 512 "lib/m.sh")
edit_commit "$P" "feature: m third (t910)" lib/m.sh
out=$(pcheck "$P" "$TG2")
OTHER=$(git -C "$P" rev-parse HEAD~1)
( cd "$P" && ./.aitask-scripts/aitask_update.sh --batch 512 --premise-baseline "$OTHER" --silent >/dev/null 2>&1 )
check "G: the baseline mutation really landed" "$OTHER" "$(sha_of_baseline "$P/$TG2")"
before=$(digest "$P/$TG2")
aout=$(padv "$P" "$TG2" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)")
check "G: baseline mutation -> MISMATCH" "1" "$(count_of "$aout" 'MISMATCH:')"
check "G: ...task file byte-identical" "$before" "$(digest "$P/$TG2")"

# === H: overflow ===========================================================
echo "=== H: overflow -- 12 changed files, nothing truncated ==="
files=(); refs=""
for i in $(seq 1 12); do files+=("lib/o$i.sh"); refs+="${refs:+, }lib/o$i.sh"; done
edit_commit "$P" "feature: o seed (t911)" "${files[@]}"
TH=$(mk_task "$P" 513 "$refs")
edit_commit "$P" "feature: o all (t912)" "${files[@]}"
out=$(pcheck "$P" "$TH")
check "H: the check emits all 12 CHANGED rows" "12" "$(count_of "$out" 'CHANGED:')"
aout=$(padv "$P" "$TH" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)")
check "H: advance succeeds" "1" "$(count_of "$aout" 'ADVANCED:')"
check "H: re-check reads FRESH over all 12" "FRESH" "$(dec "$(pcheck "$P" "$TH")")"

# === I: all-or-nothing =====================================================
echo "=== I: approved removal + nonexistent --checked -> untouched ==="
TI=$(mk_task "$P" 514 "lib/live2.sh, lib/ghost4.sh")
out=$(pcheck "$P" "$TI")
before=$(digest "$P/$TI")
head_before=$(git -C "$P" rev-parse HEAD)
NOPE=$(printf 'e%.0s' $(seq 1 40))
aout=$(padv "$P" "$TI" --checked "$NOPE" --fingerprint "$(val "$out" FINGERPRINT)" --remove-ref lib/ghost4.sh)
check "I: the writer refuses -> ADVANCE_FAILED" "1" "$(count_of "$aout" 'ADVANCE_FAILED:')"
check "I: ...nothing reported REMOVED" "0" "$(count_of "$aout" 'REMOVED:')"
check "I: ...task file byte-identical (the approved ref is still there)" "$before" "$(digest "$P/$TI")"
check "I: ...no commit" "$head_before" "$(git -C "$P" rev-parse HEAD)"

# === J: CLI misuse =========================================================
echo "=== J: CLI misuse dies, file untouched ==="
TJ=$(mk_task "$P" 515 "lib/live2.sh")
out=$(pcheck "$P" "$TJ")
CK=$(val "$out" CHECKED); FP=$(val "$out" FINGERPRINT)
before=$(digest "$P/$TJ")
misuse() { # misuse <label> <args...>
    local label="$1" rc=0
    shift
    ( cd "$P" && ./.aitask-scripts/aitask_premise_stale.sh advance "$@" >/dev/null 2>&1 ) || rc=$?
    check "J: $label -> non-zero" "nonzero" "$([[ $rc -ne 0 ]] && echo nonzero || echo zero)"
}
misuse "--checked HEAD" "$TJ" --checked HEAD --fingerprint "$FP" --owner "$OWNER"
misuse "short sha" "$TJ" --checked "${CK:0:12}" --fingerprint "$FP" --owner "$OWNER"
misuse "fingerprint NONE" "$TJ" --checked "$CK" --fingerprint NONE --owner "$OWNER"
misuse "bad fingerprint" "$TJ" --checked "$CK" --fingerprint xyz --owner "$OWNER"
misuse "missing file" aitasks/t9999_nope.md --checked "$CK" --fingerprint "$FP" --owner "$OWNER"
misuse "unknown flag" "$TJ" --checked "$CK" --fingerprint "$FP" --owner "$OWNER" --bogus
misuse "no task file" --checked "$CK"
misuse "missing --owner" "$TJ" --checked "$CK" --fingerprint "$FP"
check "J: task file byte-identical after every misuse" "$before" "$(digest "$P/$TJ")"

# === J2: identity -- the checked file must BE the task the writer resolves ==
echo "=== J2: a copied task file is refused; a symlink alias is not ==="
TR=$(mk_task "$P" 601 "lib/live.sh")
CP_DIR="$(fixture_mktemp_d test_premise_wf_copy)"
sed 's#^file_references: .*#file_references: [lib/a.sh]#' "$P/$TR" > "$CP_DIR/t601_x.md"
edit_commit "$P" "feature: touch a and live (t913)" lib/a.sh lib/live.sh
out=$(pcheck "$P" "$CP_DIR/t601_x.md")
check "J2: the copy reads ASK_STALE (it watches lib/a.sh)" "ASK_STALE" "$(dec "$out")"
before=$(digest "$P/$TR")
head_before=$(git -C "$P" rev-parse HEAD)
rc=0
aout=$(padv "$P" "$CP_DIR/t601_x.md" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)") || rc=$?
check "J2: advance on a copy dies (non-zero)" "nonzero" "$([[ $rc -ne 0 ]] && echo nonzero || echo zero)"
check "J2: ...naming the identity refusal" "1" "$(printf '%s\n' "$aout" | grep -c 'is not the active task file for t601')"
check "J2: ...the REAL task file is byte-identical" "$before" "$(digest "$P/$TR")"
check "J2: ...no commit" "$head_before" "$(git -C "$P" rev-parse HEAD)"
check "J2: ...and the real task still reports its unreviewed change" "1" \
    "$(count_of "$(pcheck "$P" "$TR")" 'CHANGED:lib/live.sh|1|913')"

AL_DIR="$(fixture_mktemp_d test_premise_wf_alias)"
ln -s "$P/$TR" "$AL_DIR/t601_x.md"
out=$(pcheck "$P" "$AL_DIR/t601_x.md")
aout=$(padv "$P" "$AL_DIR/t601_x.md" --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)")
check "J2: a symlink alias of the real task file advances" "1" "$(count_of "$aout" 'ADVANCED:')"
check "J2: ...and commits the canonical task file" "ait: Advance premise baseline for t601" "$(subject_head "$P")"
check "J2: ...and the real task re-checks FRESH" "FRESH" "$(dec "$(pcheck "$P" "$TR")")"

# === J3: ownership -- advance only under the owner's lock ==================
echo "=== J3: no lock, or another owner's lock -> ADVANCE_REFUSED:not_owner ==="
TO=$(mk_task "$P" 602 "lib/m.sh")
edit_commit "$P" "feature: m for ownership (t914)" lib/m.sh
out=$(pcheck "$P" "$TO")
before=$(digest "$P/$TO")
head_before=$(git -C "$P" rev-parse HEAD)
aout=$( cd "$P" && ./.aitask-scripts/aitask_premise_stale.sh advance "$TO" --checked "$(val "$out" CHECKED)" \
    --fingerprint "$(val "$out" FINGERPRINT)" --owner "$OWNER" 2>&1 )
check "J3: unlocked task -> not_owner" "1" "$(count_of "$aout" 'ADVANCE_REFUSED:not_owner|no lock held on t602')"
check "J3: ...task file byte-identical" "$before" "$(digest "$P/$TO")"
( cd "$P" && ./.aitask-scripts/aitask_lock.sh --lock 602 --email other@test.com >/dev/null 2>&1 )
aout=$( cd "$P" && ./.aitask-scripts/aitask_premise_stale.sh advance "$TO" --checked "$(val "$out" CHECKED)" \
    --fingerprint "$(val "$out" FINGERPRINT)" --owner "$OWNER" 2>&1 )
check "J3: another owner's lock -> not_owner naming the holder" "1" \
    "$(count_of "$aout" 'ADVANCE_REFUSED:not_owner|locked by other@test.com@')"
check "J3: ...task file byte-identical" "$before" "$(digest "$P/$TO")"
check "J3: ...no commit" "$head_before" "$(git -C "$P" rev-parse HEAD)"
check "J3: ...and the change still reports" "ASK_STALE" "$(dec "$(pcheck "$P" "$TO")")"

# === J4: session identity -- same email, same host, different session =====
echo "=== J4: a different live session of the same user cannot advance ==="
sleep 600 & OTHER_SESSION=$!
TS4=$(mk_task "$P" 603 "lib/m.sh")
edit_commit "$P" "feature: m for sessions (t915)" lib/m.sh
( cd "$P" && AIT_AGENT_PID=$OTHER_SESSION ./.aitask-scripts/aitask_lock.sh --lock 603 --email "$OWNER" >/dev/null 2>&1 )
check "J4: the other session really holds the lock" "1" \
    "$( (cd "$P" && ./.aitask-scripts/aitask_lock.sh --check 603 2>/dev/null) | grep -c "^pid: $OTHER_SESSION\$")"
out=$(pcheck "$P" "$TS4")
before=$(digest "$P/$TS4")
head_before=$(git -C "$P" rev-parse HEAD)
aout=$( cd "$P" && ./.aitask-scripts/aitask_premise_stale.sh advance "$TS4" --checked "$(val "$out" CHECKED)" \
    --fingerprint "$(val "$out" FINGERPRINT)" --owner "$OWNER" 2>&1 )
check "J4: same email + host, different live session -> not_owner" "1" \
    "$(count_of "$aout" "ADVANCE_REFUSED:not_owner|held by another session of $OWNER on .* (pid $OTHER_SESSION)")"
check "J4: ...task file byte-identical" "$before" "$(digest "$P/$TS4")"
check "J4: ...no commit" "$head_before" "$(git -C "$P" rev-parse HEAD)"
check "J4: ...the holder's lock is untouched" "1" \
    "$( (cd "$P" && ./.aitask-scripts/aitask_lock.sh --check 603 2>/dev/null) | grep -c "^pid: $OTHER_SESSION\$")"
aout=$( cd "$P" && AIT_AGENT_PID=$OTHER_SESSION ./.aitask-scripts/aitask_premise_stale.sh advance "$TS4" \
    --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" --owner "$OWNER" 2>&1 )
check "J4: control -- the HOLDING session advances" "1" "$(count_of "$aout" 'ADVANCED:')"
kill "$OTHER_SESSION" 2>/dev/null; wait "$OTHER_SESSION" 2>/dev/null

echo "=== J4: an unprovable session identity is refused, never assumed ==="
TS5=$(mk_task "$P" 604 "lib/m.sh")
edit_commit "$P" "feature: m for anchors (t916)" lib/m.sh
( cd "$P" && env -u AIT_AGENT_PID -u TMUX -u TMUX_PANE ./.aitask-scripts/aitask_lock.sh --lock 604 --email "$OWNER" >/dev/null 2>&1 )
check "J4: the anchor-less lock really records no pid" "1" \
    "$( (cd "$P" && ./.aitask-scripts/aitask_lock.sh --check 604 2>/dev/null) | grep -c '^pid: -$')"
out=$(pcheck "$P" "$TS5")
before=$(digest "$P/$TS5")
aout=$( cd "$P" && ./.aitask-scripts/aitask_premise_stale.sh advance "$TS5" --checked "$(val "$out" CHECKED)" \
    --fingerprint "$(val "$out" FINGERPRINT)" --owner "$OWNER" 2>&1 )
check "J4: a lock without an anchor -> owner_unverifiable" "1" \
    "$(count_of "$aout" 'ADVANCE_REFUSED:owner_unverifiable|the lock on t604 records no session anchor')"
check "J4: ...task file byte-identical" "$before" "$(digest "$P/$TS5")"
TS6=$(mk_task "$P" 605 "lib/m.sh")
edit_commit "$P" "feature: m for self anchor (t917)" lib/m.sh
( cd "$P" && ./.aitask-scripts/aitask_lock.sh --lock 605 --email "$OWNER" >/dev/null 2>&1 )
out=$(pcheck "$P" "$TS6")
before=$(digest "$P/$TS6")
aout=$( cd "$P" && env -u AIT_AGENT_PID -u TMUX -u TMUX_PANE ./.aitask-scripts/aitask_premise_stale.sh advance "$TS6" \
    --checked "$(val "$out" CHECKED)" --fingerprint "$(val "$out" FINGERPRINT)" --owner "$OWNER" 2>&1 )
check "J4: a caller with no resolvable anchor -> owner_unverifiable" "1" \
    "$(count_of "$aout" 'ADVANCE_REFUSED:owner_unverifiable|this session has no resolvable anchor')"
check "J4: ...task file byte-identical" "$before" "$(digest "$P/$TS6")"

# === J5: the `owner` proof used before the procedure's other writes ========
echo "=== J5: owner verb -- OK / another session (force-claim) / no lock / anchor-less / copy ==="
pown() { ( cd "$P" && ./.aitask-scripts/aitask_premise_stale.sh owner "$@" 2>&1 ); }
TW5=$(mk_task "$P" 606 "lib/m.sh")
( cd "$P" && ./.aitask-scripts/aitask_lock.sh --lock 606 --email "$OWNER" >/dev/null 2>&1 )
check "J5: this session's own lock -> OWNER_OK" "OWNER_OK" "$(pown "$TW5" --owner "$OWNER")"
sleep 600 & FORCER=$!
( cd "$P" || exit 1
  ./.aitask-scripts/aitask_lock.sh --unlock 606 >/dev/null 2>&1
  AIT_AGENT_PID=$FORCER ./.aitask-scripts/aitask_lock.sh --lock 606 --email "$OWNER" >/dev/null 2>&1 )
check "J5: after another session's force-claim -> NOT_OWNER" "1" \
    "$(pown "$TW5" --owner "$OWNER" | grep -c "^NOT_OWNER:held by another session of $OWNER on .* (pid $FORCER)\$")"
before=$(digest "$P/$TW5")
out=$(pcheck "$P" "$TW5")
aout=$( cd "$P" && ./.aitask-scripts/aitask_premise_stale.sh advance "$TW5" --checked "$(val "$out" CHECKED)" \
    --fingerprint "$(val "$out" FINGERPRINT)" --owner "$OWNER" 2>&1 )
check "J5: ...and advance agrees (not_owner)" "1" "$(count_of "$aout" 'ADVANCE_REFUSED:not_owner|held by another session')"
check "J5: ...nothing written" "$before" "$(digest "$P/$TW5")"
check "J5: ...the new holder's lock is untouched" "1" \
    "$( (cd "$P" && ./.aitask-scripts/aitask_lock.sh --check 606 2>/dev/null) | grep -c "^pid: $FORCER\$")"
kill "$FORCER" 2>/dev/null; wait "$FORCER" 2>/dev/null
TW6=$(mk_task "$P" 607 "lib/m.sh")
check "J5: no lock -> NOT_OWNER" "NOT_OWNER:no lock held on t607" "$(pown "$TW6" --owner "$OWNER")"
( cd "$P" && env -u AIT_AGENT_PID -u TMUX -u TMUX_PANE ./.aitask-scripts/aitask_lock.sh --lock 607 --email "$OWNER" >/dev/null 2>&1 )
check "J5: anchor-less lock -> OWNER_UNVERIFIABLE" "1" \
    "$(pown "$TW6" --owner "$OWNER" | grep -c '^OWNER_UNVERIFIABLE:the lock on t607 records no session anchor$')"
rc=0; pown "$CP_DIR/t601_x.md" --owner "$OWNER" >/dev/null || rc=$?
check "J5: a copied task file dies (identity)" "nonzero" "$([[ $rc -ne 0 ]] && echo nonzero || echo zero)"
rc=0; pown "$TW6" >/dev/null || rc=$?
check "J5: missing --owner dies" "nonzero" "$([[ $rc -ne 0 ]] && echo nonzero || echo zero)"

# === K: pre-claim race, live holder ========================================
echo "=== K: another session locks the task while the prompt is open ==="
TK=$(mk_task "$P" 516 "lib/live2.sh")
git -C "$P" push -q 2>/dev/null
( cd "$P" && ./.aitask-scripts/aitask_lock.sh --lock 516 --email other@test.com >/dev/null 2>&1 )
krc=0
kout=$( cd "$P" && ./.aitask-scripts/aitask_pick_own.sh 516 --email a@test.com --expect-status Ready 2>/dev/null ) || krc=$?
check "K: the guarded claim refuses (exit 1)" "1" "$krc"
check "K: ...with LOCK_FAILED" "1" "$(count_of "$kout" 'LOCK_FAILED:other@test.com')"
check "K: ...and the task is still Ready (never Postponed, never claimed)" "Ready" "$(field "$P/$TK" status)"
check "K: ...no claim commit" "0" "$(git -C "$P" log --format=%s | grep -c '^ait: Start work on t516' || true)"

# === L: structural pins over the rendered skill text =======================
echo "=== L: structural pins (rendered procedure / SKILL / planning) ==="
TW="$SKILLS_SRC/task-workflow"
PROC="$TW/premise-staleness.md"
check "L: the procedure file exists" "yes" "$([[ -f "$PROC" ]] && echo yes || echo no)"
section() { # section <file> <heading> -> body until the next "## "
    awk -v h="$2" '$0==h {on=1; next} on && /^## / {exit} on {print}' "$1"
}
chk_sec=$(section "$PROC" "## Check")
check "L: ## Check is non-empty" "yes" "$([[ -n "$chk_sec" ]] && echo yes || echo no)"
check "L: ## Check writes no status" "0" "$(printf '%s\n' "$chk_sec" | grep -c -- '--status')"
check "L: ## Check never calls advance" "0" "$(printf '%s\n' "$chk_sec" | grep -c 'aitask_premise_stale.sh advance')"
check "L: ## Check is pre-lock and says it writes nothing" "1" \
    "$(printf '%s\n' "$chk_sec" | grep -ci 'writes nothing' | awk '{print ($1>0)?1:0}')"
check "L: the replan source is the retained protocol" "1" \
    "$(grep -c 'premise_decision.protocol' "$PROC" | awk '{print ($1>0)?1:0}')"
check "L: the 10-row cap is presentation-only" "1" \
    "$(grep -ci 'presentation only' "$PROC" | awk '{print ($1>0)?1:0}')"
keep_line=$(grep -n '"Keep them' "$PROC" | head -n1 | cut -d: -f1)
remove_line=$(grep -n '"Remove them"' "$PROC" | head -n1 | cut -d: -f1)
check "L: the never-existed question lists Keep first" "yes" \
    "$([[ -n "$keep_line" && -n "$remove_line" && "$keep_line" -lt "$remove_line" ]] && echo yes || echo no)"
check "L: the procedure carries a NON-SKIPPABLE banner" "1" \
    "$(grep -c 'NON-SKIPPABLE' "$PROC" | awk '{print ($1>0)?1:0}')"
n_adv=$(grep -c 'aitask_premise_stale.sh advance' "$PROC")
n_adv_owner=$(grep -A3 'aitask_premise_stale.sh advance' "$PROC" | grep -c -- '--owner "<email>"')
check "L: the procedure invokes advance at least once" "yes" "$([[ $n_adv -ge 1 ]] && echo yes || echo no)"
check "L: ...and every invocation passes --owner" "$n_adv" "$n_adv_owner"
ou_bullet=$(awk '/`ADVANCE_REFUSED:owner_unverifiable\|/{on=1; print; next} on && /^     - `/{exit} on {print}' "$PROC")
check "L: the procedure routes owner_unverifiable explicitly, never as a pass" "1" \
    "$(printf '%s\n' "$ou_bullet" | grep -c 'Never treat it as a pass')"
# --- caller routing for a lost task: not_owner stops every later write -------
lost=$(section "$PROC" "## Ownership lost")
check "L: ## Ownership lost exists" "yes" "$([[ -n "$lost" ]] && echo yes || echo no)"
for forbid in "revert the status" "release the lock" "materialize gates" "Approved-Plan Stop Sequence"; do
    check "L: ## Ownership lost forbids: $forbid" "1" \
        "$(printf '%s\n' "$lost" | grep -c "$forbid" | awk '{print ($1>0)?1:0}')"
done
check "L: ...and ends with a state-derived banner" "1" \
    "$(printf '%s\n' "$lost" | grep -c 'state-derived' | awk '{print ($1>0)?1:0}')"
postlock=$(section "$PROC" "## Post-lock")
no_bullet=$(printf '%s\n' "$postlock" | awk '/`ADVANCE_REFUSED:not_owner\|/{on=1; print; next} on && /^     - `/{exit} on {print}')
check "L: Post-lock routes advance's not_owner to ## Ownership lost" "1" \
    "$(printf '%s\n' "$no_bullet" | grep -c '## Ownership lost')"
check "L: ...and never says continue there" "0" "$(printf '%s\n' "$no_bullet" | grep -c '^ *Continue\.')"
ln_owner=$(printf '%s\n' "$postlock" | grep -n 'aitask_premise_stale.sh owner' | head -n1 | cut -d: -f1)
ln_postpone=$(printf '%s\n' "$postlock" | grep -n -- '--status Postponed' | head -n1 | cut -d: -f1)
check "L: the postpone write is preceded by the owner proof" "yes" \
    "$([[ -n "$ln_owner" && -n "$ln_postpone" && "$ln_owner" -lt "$ln_postpone" ]] && echo yes || echo no)"
revert=$(printf '%s\n' "$postlock" | awk '/"Pick a different task" → first run the `owner` check/{on=1} on {print} on && /--status Ready/{exit}')
check "L: the post-lock revert to Ready is preceded by the owner proof" "1" \
    "$(printf '%s\n' "$revert" | grep -c -- '--status Ready')"
adv_sec_full=$(section "$PROC" "## Advance after an approved replan")
check "L: the replan advance treats not_owner as terminal" "1" \
    "$(printf '%s\n' "$adv_sec_full" | grep '`ADVANCE_REFUSED:not_owner' | grep -c 'terminal')"
check "L: ...and forbids the stop sequence after it" "1" \
    "$(printf '%s\n' "$adv_sec_full" | grep -c 'must \*\*not\*\* run its stop sequence')"
adv_sec=$(section "$PROC" "## Advance after an approved replan")
check "L: the replan advance requires the recorded review" "1" \
    "$(printf '%s\n' "$adv_sec" | grep -c 'Evidence rows reviewed' | awk '{print ($1>0)?1:0}')"
pre_ln=$(printf '%s\n' "$adv_sec" | grep -n 'Precondition' | head -n1 | cut -d: -f1)
run_ln=$(printf '%s\n' "$adv_sec" | grep -n 'with the stored pair' | head -n1 | cut -d: -f1)
check "L: ...checked before the advance runs" "yes" \
    "$([[ -n "$pre_ln" && -n "$run_ln" && "$pre_ln" -lt "$run_ln" ]] && echo yes || echo no)"
check "L: the postpone exit uses the postponed banner outcome" "1" \
    "$(grep -c 'outcome=postponed' "$PROC" | awk '{print ($1>0)?1:0}')"

RENDER="$PY $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
for prof in default fast; do
    sk=$($RENDER "$TW/SKILL.md" "$PROJECT_DIR/aitasks/metadata/profiles/$prof.yaml" claude 2>/dev/null)
    pl=$($RENDER "$TW/planning.md" "$PROJECT_DIR/aitasks/metadata/profiles/$prof.yaml" claude 2>/dev/null)
    c7=$(printf '%s\n' "$sk" | awk '/^\*\*Check 7 /{on=1} on && /^### Step 4/{exit} on {print}')
    check "L/$prof: Check 7 is rendered" "yes" "$([[ -n "$c7" ]] && echo yes || echo no)"
    check "L/$prof: Check 7 dispatches to ## Check only" "0" \
        "$(printf '%s\n' "$c7" | grep -c 'Post-lock\|Advance after an approved replan')"
    check "L/$prof: Check 7 skips non-Ready and manual_verification" "1" \
        "$(printf '%s\n' "$c7" | grep -c 'manual_verification' | awk '{print ($1>0)?1:0}')"
    s4=$(printf '%s\n' "$sk" | awk '/^### Step 4:/{on=1} on && /^### Re-entry Routing/{exit} on {print}')
    check "L/$prof: Step 4 claims with --expect-status Ready when a premise choice is pending" "1" \
        "$(printf '%s\n' "$s4" | grep -c -- '--expect-status Ready' | awk '{print ($1>0)?1:0}')"
    check "L/$prof: Step 4 runs ## Post-lock" "1" \
        "$(printf '%s\n' "$s4" | grep -c '## Post-lock' | awk '{print ($1>0)?1:0}')"
    check "L/$prof: Step 4 handles STATUS_CHANGED and STATUS_UNVERIFIED" "2" \
        "$( { printf '%s\n' "$s4" | grep -q 'STATUS_CHANGED:' && echo x; printf '%s\n' "$s4" | grep -q 'STATUS_UNVERIFIED:' && echo x; } | grep -c x)"
    # Consumer coverage, derived from the producer: every refusal token the
    # helper documents for --expect-status must have a Step 4 branch, so a new
    # token can never reach the workflow unhandled.
    tokens=$( (cd "$P" && ./.aitask-scripts/aitask_pick_own.sh --help 2>/dev/null) \
        | sed -n 's/^  \([A-Z_][A-Z_]*\):.*/\1/p' | sort -u \
        | while read -r t; do (cd "$P" && ./.aitask-scripts/aitask_pick_own.sh --help 2>/dev/null) \
            | awk -v t="$t" '$0 ~ "^  "t":" {on=1} on && /--expect-status only/ {print t; exit} on && /^  [A-Z_]+:/ && $0 !~ "^  "t":" {exit}'; done)
    check "L/$prof: the helper documents the three guarded refusals" \
        "LOCK_REQUIRED STATUS_CHANGED STATUS_UNVERIFIED" "$(printf '%s\n' "$tokens" | sort | tr '\n' ' ' | sed 's/ $//')"
    for t in $tokens; do
        check "L/$prof: Step 4 handles $t" "1" \
            "$(printf '%s\n' "$s4" | grep -c "^  - \`$t:" | awk '{print ($1>0)?1:0}')"
    done
    req=$(printf '%s\n' "$s4" | awk '/^  - `LOCK_REQUIRED:no_email`/{on=1; print; next} on && /^  - `/{exit} on {print}')
    check "L/$prof: LOCK_REQUIRED retries WITH the guard after an email is provided" "1" \
        "$(printf '%s\n' "$req" | grep -c -- '--email "<email>" --expect-status Ready')"
    check "L/$prof: ...its email question drops Skip" "1" "$(printf '%s\n' "$req" | grep -c 'without\*\* its "Skip" option')"
    # Every claim re-run inside the LOCK_REQUIRED branch must keep the guard:
    # an unguarded recovery claim is the overwrite the guard exists to stop.
    reruns=$(printf '%s\n' "$req" | grep -c 're-run the claim')
    guarded=$(printf '%s\n' "$req" | grep 're-run the claim' | grep -c -- '--expect-status Ready')
    check "L/$prof: ...the branch has at least one claim re-run" "yes" "$([[ $reruns -ge 1 ]] && echo yes || echo no)"
    check "L/$prof: ...and every re-run keeps --expect-status Ready" "$reruns" "$guarded"
    check "L/$prof: ...no option claims without the guard" "0" \
        "$(printf '%s\n' "$req" | grep -c 'Continue without the premise answer')"
    unv=$(printf '%s\n' "$s4" | awk '/^  - `STATUS_UNVERIFIED:<reason>`/{on=1; print; next} on && /^  - `/{exit} on {print}')
    check "L/$prof: STATUS_UNVERIFIED words unreadable_status as a file problem, not sync" "1" \
        "$(printf '%s\n' "$unv" | grep '`unreadable_status`' | grep -c 'could not be read from its task file')"
    check "L/$prof: ...python_unavailable points at ait setup" "1" \
        "$(printf '%s\n' "$unv" | grep '`python_unavailable`' | grep -c 'ait setup')"
    check "L/$prof: ...ait syncer is offered only for sync reasons" "1" \
        "$(printf '%s\n' "$unv" | grep -c 'ait syncer')"
    check "L/$prof: ...and the syncer line is the sync-classifier one" "1" \
        "$(printf '%s\n' "$unv" | grep 'ait syncer' | grep -c 'sync classifier code')"
    lerr=$(printf '%s\n' "$s4" | awk '/^  - `LOCK_ERROR:<message>`/{on=1; print; next} on && /^  - `/{exit} on {print}')
    check "L/$prof: LOCK_ERROR forbids \"Continue without lock\" while a premise answer is pending" "1" \
        "$(printf '%s\n' "$lerr" | grep -c 'When `premise_decision` is set, do NOT offer "Continue without lock"')"
    check "L/$prof: ...its pending-answer retry keeps the guard" "1" \
        "$(printf '%s\n' "$lerr" | grep 'do NOT offer' | grep -c -- '--expect-status Ready')"
    check "L/$prof: the Step 7 ownership guard defers to the same rule" "1" \
        "$(printf '%s\n' "$sk" | grep 'LOCK_ERROR:<message>` — Display error' | grep -c 'never "Continue without lock" while `premise_decision` is set')"
    s7=$(printf '%s\n' "$sk" | awk '/^### Step 7:/{on=1} on && /^### Step 8:/{exit} on {print}')
    check "L/$prof: Step 7 advances only on replan" "1" \
        "$(printf '%s\n' "$s7" | grep -c 'Advance after an approved replan' | awk '{print ($1>0)?1:0}')"
    outside=$(printf '%s\n' "$sk" | awk '/^### Step 4:/{skip=1} /^### Re-entry Routing/{skip=0}
        /^### Step 7:/{skip=1} /^### Step 8:/{skip=0} /^### Procedures/{skip=1} !skip' \
        | grep -c 'Advance after an approved replan\|## Post-lock' || true)
    check "L/$prof: no write section is referenced outside Step 4 / Step 7 / the Procedures list" \
        "0" "$outside"
    pl_lost=$(printf '%s\n' "$sk" | grep '^- \*\*Apply the pending premise answer (post-lock):' | grep -c 'do NOT run the materialization below')
    check "L/$prof: Step 4 stops before materialization when ownership is lost" "1" "$pl_lost"
    ln_apply=$(printf '%s\n' "$sk" | grep -n '^- \*\*Apply the pending premise answer (post-lock):' | head -n1 | cut -d: -f1)
    ln_mat=$(printf '%s\n' "$sk" | grep -n '^- \*\*Materialize the active-gates tuple' | head -n1 | cut -d: -f1)
    check "L/$prof: ...and that step sits before the materialization" "yes" \
        "$([[ -n "$ln_apply" && -n "$ln_mat" && "$ln_apply" -lt "$ln_mat" ]] && echo yes || echo no)"
    check "L/$prof: Step 7 ends the workflow when the replan advance loses ownership" "1" \
        "$(printf '%s\n' "$s7" | grep '^\*\*Premise baseline advance (post-approval, replan only):' | grep -c 'do NOT continue to the risk-mitigation creation, the implementation or Step 8')"
    stop=$(printf '%s\n' "$pl" | awk '/^If "Approve and stop here":/{on=1} on && /^If "Abort"/{exit} on {print}')
    ln_lost=$(printf '%s\n' "$stop" | grep -n 'do \*\*not\*\* execute the stop sequence below' | head -n1 | cut -d: -f1)
    ln_seq=$(printf '%s\n' "$stop" | grep -n '^Execute the \*\*Approved-Plan Stop Sequence\*\*' | head -n1 | cut -d: -f1)
    check "L/$prof: Approve-and-stop skips the stop sequence after Ownership lost (stated before it)" "yes" \
        "$([[ -n "$ln_lost" && -n "$ln_seq" && "$ln_lost" -lt "$ln_seq" ]] && echo yes || echo no)"
    check "L/$prof: planning's Approve-and-stop advances a replan first" "1" \
        "$(printf '%s\n' "$stop" | grep -c 'Advance after an approved replan' | awk '{print ($1>0)?1:0}')"
    # Routing, not presence: the review must come BEFORE every jump out of
    # planning (the verify path's terminal step, ExitPlanMode), and its guard
    # must sit between Save Plan and the Checkpoint.
    ln_review=$(printf '%s\n' "$pl" | grep -n '^\*\*Premise evidence review (replan) — first, on every path:' | head -n1 | cut -d: -f1)
    ln_verify=$(printf '%s\n' "$pl" | grep -n '^\*\*If entering from the "Verify plan" path in 6.0:' | head -n1 | cut -d: -f1)
    ln_terminal=$(printf '%s\n' "$pl" | grep -n '^#### End-of-planning terminal step' | head -n1 | cut -d: -f1)
    ln_guard=$(printf '%s\n' "$pl" | grep -n '^\*\*Premise-review guard' | head -n1 | cut -d: -f1)
    ln_save=$(printf '%s\n' "$pl" | grep -n '^## Save Plan to External File' | head -n1 | cut -d: -f1)
    ln_ckpt=$(printf '%s\n' "$pl" | grep -n '^## Checkpoint' | head -n1 | cut -d: -f1)
    check "L/$prof: the replan review precedes the verify path" "yes" \
        "$([[ -n "$ln_review" && -n "$ln_verify" && "$ln_review" -lt "$ln_verify" ]] && echo yes || echo no)"
    check "L/$prof: ...and the end-of-planning terminal step" "yes" \
        "$([[ -n "$ln_review" && -n "$ln_terminal" && "$ln_review" -lt "$ln_terminal" ]] && echo yes || echo no)"
    check "L/$prof: the verify path itself requires the review" "1" \
        "$(printf '%s\n' "$pl" | sed -n "${ln_verify:-1}p" | grep -c 'includes\*\* the Premise evidence review')"
    check "L/$prof: the premise-review guard sits between Save Plan and the Checkpoint" "yes" \
        "$([[ -n "$ln_guard" && -n "$ln_save" && -n "$ln_ckpt" && "$ln_save" -lt "$ln_guard" && "$ln_guard" -lt "$ln_ckpt" ]] && echo yes || echo no)"
    check "L/$prof: planning reviews the full protocol on replan" "1" \
        "$(printf '%s\n' "$pl" | grep -c 'premise_decision.protocol' | awk '{print ($1>0)?1:0}')"
done

# === M: allowlist ==========================================================
echo "=== M: the helper is whitelisted on every agent surface ==="
for f in .claude/settings.local.json seed/claude_settings.local.json seed/opencode_config.seed.json \
         .codex/rules/default.rules seed/codex_rules.default.rules; do
    check "M: aitask_premise_stale.sh in $f" "1" \
        "$(grep -c 'aitask_premise_stale\.sh' "$PROJECT_DIR/$f" 2>/dev/null | awk '{print ($1>0)?1:0}')"
done

echo ""
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"
[[ "$FAIL" -eq 0 ]] && echo "ALL TESTS PASSED"
[[ "$FAIL" -eq 0 ]]
