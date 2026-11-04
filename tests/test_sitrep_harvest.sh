#!/usr/bin/env bash
# End-to-end tests for aitask_sitrep_harvest.sh (t2175_2).
#
# Real helper, real store writer, real session-store wrapper -- all under a
# scratch HOME / session store / frozen dir / project registry, with TMUX unset,
# so nothing reaches the real ~/.config. Fixtures: tests/fixtures/sitrep_harvest/
# (synthetic, see its README).
#
#   1  record: items, receipt, ignore rule, git status clean
#   2  re-harvest: receipt short-circuit and --force are both no-ops
#   3  piped then captured: Complete (commit), Stopped with / without marker
#   4  same banner, different prose: a new linked item, also after dismissal
#   5  identical repeats: N runs -> N items; a dismissed run plus a new pipe
#   6  literal-content collisions after harvest + dismissal: never merged
#   7  repeated harvest/dismiss cycles on a restored record stay no-ops
#   8  linked worktree: one store at the main root, readable after removal
#   9  roots: non-git root works; removed standalone root fails, no receipt
#  10  nothing found: no store directory, but a receipt
#  11  writer lock held: HARVEST_FAILED writer:lock_busy, no receipt
#  12  follow-ups: local, unresolved and resolved cross-repo
#  13  concurrent record + banner: one triage item
#  14  purge gate: frozen (missing ANSI) and live (dead_window/dead_pane) keep text
#  15  store drop gate: no / stale / valid receipt, --skip-harvest
#  16  acceptance: harvest -> drop -> every pointer still SOURCE_OK and readable
#  17  explore Created: lines and trail handles
#  18  argument validation
#  19  the sitrep agent's own window is never harvested (t2175_4); near-miss
#      window names are harvested normally
#
# Bodies run in the main shell (no subshell asserts), so the plain counters
# are enough.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

HV="$PROJECT_DIR/.aitask-scripts/aitask_sitrep_harvest.sh"
WR="$PROJECT_DIR/.aitask-scripts/aitask_sitrep_todo.sh"
SESS="$PROJECT_DIR/.aitask-scripts/aitask_agent_sessions.sh"
FIX="$PROJECT_DIR/tests/fixtures/sitrep_harvest"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_harvest_XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
BG_PIDS=()
cleanup() {
    local p
    for p in "${BG_PIDS[@]:-}"; do
        [[ -n "$p" ]] && kill -9 "$p" 2>/dev/null
    done
    exec 7>&- 2>/dev/null
    chmod -R u+w "$TMP" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

# Resolve the interpreter BEFORE switching HOME: the framework python wrapper
# finds its venv through $HOME.
AIT_PYTHON="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" && require_ait_python)"
export AIT_PYTHON
export HOME="$TMP/home"
mkdir -p "$HOME/.config/aitasks"
export AITASKS_AGENT_SESSIONS_FILE="$HOME/.config/aitasks/agent_sessions.json"
export AITASKS_FROZEN_DIR="$TMP/frozen"
export AITASKS_PROJECTS_INDEX="$TMP/projects.yaml"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"
export AITASK_SITREP_NOW="2026-11-02T10:00:00Z"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
unset TMUX TMUX_PANE AITASK_SITREP_DIR AITASK_SITREP_PAUSE_FIFO AITASK_SITREP_LOCK_TIMEOUT \
      AITASK_SITREP_HARVEST_PAUSE_FIFO AITASK_SITREP_HARVEST_LOCK_TIMEOUT \
      AITASK_SITREP_HARVEST_RUN_ID

# --- helpers -----------------------------------------------------------------

new_repo() {   # new_repo <name> -> echoes the path of a fresh git repo
    local d="$TMP/$1"
    mkdir -p "$d/aitasks/metadata"
    : > "$d/aitasks/metadata/project_config.yaml"
    git -C "$d" init -q
    git -C "$d" add -A
    git -C "$d" commit -q -m init
    printf '%s' "$d"
}

# make_record <root> <window> <task> <op> <capture file> -> echoes the record id
make_record() {
    local root="$1" win="$2" task="$3" op="$4" cap="$5" out id nonce
    out="$("$SESS" upsert --root "$root" --window "$win" --pane %9 --pane-pid $$ \
        --operation "$op" --task-id "$task")"
    id="$(printf '%s' "$out" | sed -n 's/^UPSERTED:\([0-9a-f]\{8\}\).*/\1/p')"
    mkdir -p "$AITASKS_FROZEN_DIR/$id"
    cp "$cap" "$AITASKS_FROZEN_DIR/$id/capture.txt"
    cp "$cap" "$AITASKS_FROZEN_DIR/$id/capture.ansi"
    out="$("$SESS" freeze-begin "$id" --owner-pid $$ \
        --capture-ansi "$AITASKS_FROZEN_DIR/$id/capture.ansi" \
        --capture-txt "$AITASKS_FROZEN_DIR/$id/capture.txt" --lines 10)"
    nonce="$(printf '%s' "$out" | tail -1 | grep -o '[0-9a-f]\{8\}$')"
    "$SESS" freeze-commit "$id" --nonce "$nonce" --pane "" --pane-pid 0 >/dev/null
    printf '%s' "$id"
}

cap_of() { printf '%s' "$AITASKS_FROZEN_DIR/$1/capture.txt"; }

harvest() {   # harvest <args...>  (stdin as given) -> OUT, RC
    RC=0
    OUT="$("$HV" "$@" 2>"$TMP/err")" || RC=$?
}

store_of() { printf '%s' "$1/.aitask-sitrep"; }

items() {   # items <root> -> list --machine output
    AITASK_SITREP_DIR="$(store_of "$1")" "$WR" list 2>/dev/null
}

count_items() {   # count_items <root> <kind> [state]
    local want="${3:-}"
    items "$1" | awk -F'|' -v k="$2" -v s="$want" \
        '$3==k && (s=="" || $4==s) {n++} END {print n+0}'
}

ctx() { AITASK_SITREP_DIR="$(store_of "$1")" "$WR" context "$2" 2>/dev/null; }

wr() {   # wr <root> <writer args...>
    local root="$1"; shift
    AITASK_SITREP_DIR="$(store_of "$root")" "$WR" "$@"
}

first_id() {   # first_id <root> <kind>
    items "$1" | awk -F'|' -v k="$2" '$3==k {sub(/^ITEM:/,"",$1); print $1; exit}'
}

stopped_capture() {   # stopped_capture <out file> <prose>  (stopped_a with its prose replaced)
    "$AIT_PYTHON" - "$FIX/pick_stopped_a.txt" "$1" "$2" <<'PY'
import sys
src, out, prose = sys.argv[1:4]
lines = open(src, encoding="utf-8").read().split("\n")
old = "● Plan approved and committed. Push main before you pick it up again."
idx = next(i for i, l in enumerate(lines) if l.startswith(old))
lines[idx:idx + 1] = prose.split("\n")
open(out, "w", encoding="utf-8").write("\n".join(lines))
PY
}

# --- 1. record ----------------------------------------------------------------
echo "--- 1. record: items, receipt, ignore rule"
R1="$(new_repo r1)"
ID1="$(make_record "$R1" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
harvest record "$ID1"
assert_eq "1 record exit 0" "0" "$RC"
assert_contains "1 triage item added" "|added|question|-" "$OUT"
assert_contains "1 final line" "HARVESTED:$ID1|added=1|existing=0" "$OUT"
assert_file_exists "1 receipt written" "$(cap_of "$ID1").harvested"
assert_contains "1 receipt names the sha" "sha256=$(sha256sum "$(cap_of "$ID1")" | cut -d' ' -f1)" \
    "$(cat "$(cap_of "$ID1").harvested")"
assert_eq "1 one open triage item" "1" "$(count_items "$R1" question open)"
assert_contains "1 exclude rule added" ".aitask-sitrep/" "$(cat "$R1/.git/info/exclude")"
assert_eq "1 git status stays clean" "" "$(git -C "$R1" status --porcelain)"
C1="$(first_id "$R1" question)"
CTX1="$(ctx "$R1" "$C1")"
assert_contains "1 origin names agent, task, commit, skill" \
    "origin: agent=agent-pick-42 task=t42 commit=9f8e7d6c5" "$CTX1"
assert_contains "1 commit source" "commit: 9f8e7d6c5" "$CTX1"
assert_eq "1 four capture sources (passage, banner, complete key, passage key)" "4" \
    "$(printf '%s\n' "$CTX1" | grep -c 'capture: sources/')"
PASSAGE1="$(printf '%s\n' "$CTX1" | grep -m1 'capture:' | sed 's/.*capture: //; s/#.*//')"
assert_contains "1 the passage starts at the closing message" "● t42 is done" \
    "$(head -1 "$(store_of "$R1")/$PASSAGE1")"
assert_contains "1 the passage ends at the banner" "follow-ups created: none" \
    "$(tail -1 "$(store_of "$R1")/$PASSAGE1")"

# --- 2. re-harvest --------------------------------------------------------------
echo "--- 2. re-harvest is a no-op"
SUM_BEFORE="$(sha256sum "$(store_of "$R1")/todo.md")"
harvest record "$ID1"
assert_contains "2 receipt short-circuit" "HARVEST_NONE:$ID1|already_harvested" "$OUT"
harvest record "$ID1" --force
assert_contains "2 --force reports the existing item" "|exists|question|-" "$OUT"
assert_contains "2 --force adds nothing" "added=0" "$OUT"
assert_eq "2 todo.md byte-identical" "$SUM_BEFORE" "$(sha256sum "$(store_of "$R1")/todo.md")"

# --- 3. piped then captured -----------------------------------------------------
echo "--- 3. piped then captured"
R3="$(new_repo r3)"
OUT="$(cd "$R3" && "$HV" banner --task 42 --skill pick < "$FIX/pick_complete_piped.txt")"
assert_contains "3 pipe prints the run id first" "HARVEST_RUN:" "$(printf '%s\n' "$OUT" | head -1)"
assert_contains "3 pipe adds the triage item" "|added|question|-" "$OUT"
ID3="$(make_record "$R3" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
harvest record "$ID3"
assert_contains "3 captured Complete matches the pipe (commit key)" "|exists|question|-" "$OUT"
assert_eq "3 one triage item for the Complete run" "1" "$(count_items "$R3" question)"

R3B="$(new_repo r3b)"
OUT="$(cd "$R3B" && AITASK_SITREP_HARVEST_RUN_ID=0123456789abcdef \
    "$HV" banner --task 77 --skill pick < "$FIX/pick_stopped_marker.txt")"
assert_contains "3 pinned run id" "HARVEST_RUN:0123456789abcdef" "$OUT"
ID3B="$(make_record "$R3B" agent-pick-77 77 pick "$FIX/pick_stopped_marker.txt")"
harvest record "$ID3B"
assert_contains "3 Stopped capture with a visible marker matches" "|exists|question|-" "$OUT"
assert_eq "3 one triage item for the marked Stopped run" "1" "$(count_items "$R3B" question)"

R3C="$(new_repo r3c)"
OUT="$(cd "$R3C" && "$HV" banner --task 77 --skill pick < "$FIX/pick_stopped_a.txt")"
ID3C="$(make_record "$R3C" agent-pick-77 77 pick "$FIX/pick_stopped_a.txt")"
harvest record "$ID3C"
assert_contains "3 Stopped capture without a marker is added" "|added|question|-" "$OUT"
assert_eq "3 two items for the unmarked Stopped run" "2" "$(count_items "$R3C" question)"
SECOND="$(items "$R3C" | awk -F'|' '$3=="question" {sub(/^ITEM:/,"",$1); id=$1} END {print id}')"
FIRST="$(first_id "$R3C" question)"
assert_contains "3 the duplicate links to the original" "related: $FIRST" "$(ctx "$R3C" "$SECOND")"

# --- 4. same banner, different prose -------------------------------------------
echo "--- 4. same banner, different prose"
R4="$(new_repo r4)"
ID4="$(make_record "$R4" agent-pick-77 77 pick "$FIX/pick_stopped_a.txt")"
harvest record "$ID4"
A4="$(first_id "$R4" question)"
wr "$R4" dismiss "$A4" >/dev/null
cp "$FIX/pick_stopped_b.txt" "$(cap_of "$ID4")"
harvest record "$ID4"
assert_contains "4 run B is added after A was dismissed" "|added|question|-" "$OUT"
B4="$(items "$R4" | awk -F'|' '$3=="question" && $4=="open" {sub(/^ITEM:/,"",$1); print $1}')"
assert_contains "4 B links to A" "related: $A4" "$(ctx "$R4" "$B4")"
assert_eq "4 A stays dismissed" "1" "$(count_items "$R4" question dismissed)"
SUM4="$(sha256sum "$(store_of "$R4")/todo.md")"
harvest record "$ID4" --force
assert_eq "4 re-harvesting B adds nothing" "$SUM4" "$(sha256sum "$(store_of "$R4")/todo.md")"

# --- 5. identical repeats -------------------------------------------------------
echo "--- 5. identical repeats"
R5="$(new_repo r5)"
head -9 "$FIX/pick_stopped_a.txt" > "$TMP/twice.txt"
head -9 "$FIX/pick_stopped_a.txt" >> "$TMP/twice.txt"
ID5="$(make_record "$R5" agent-pick-77 77 pick "$TMP/twice.txt")"
harvest record "$ID5"
assert_eq "5 two identical runs give two items" "2" "$(count_items "$R5" question)"
wr "$R5" dismiss "$(first_id "$R5" question)" >/dev/null
OUT="$(cd "$R5" && "$HV" banner --task 77 --skill pick < "$FIX/pick_stopped_a.txt")"
assert_contains "5 a new identical pipe is a new run" "|added|question|-" "$OUT"
assert_eq "5 three items now" "3" "$(count_items "$R5" question)"

# --- 6. literal-content collisions -------------------------------------------------
echo "--- 6. literal-content collisions are never merged"
collide() {   # collide <label> <prose A> <prose B>
    local label="$1" root id
    root="$(new_repo "r6_$label")"
    stopped_capture "$TMP/c_a.txt" "$2"
    stopped_capture "$TMP/c_b.txt" "$3"
    id="$(make_record "$root" agent-pick-77 77 pick "$TMP/c_a.txt")"
    harvest record "$id"
    wr "$root" dismiss "$(first_id "$root" question)" >/dev/null
    cp "$TMP/c_b.txt" "$(cap_of "$id")"
    harvest record "$id"
    assert_contains "6 $label: the second text is added" "|added|question|-" "$OUT"
    assert_eq "6 $label: two items" "2" "$(count_items "$root" question)"
}
collide asterisks "● Run find . -name '**cache**' first." "● Run find . -name 'cache' first."
printf -v NL_A '● printf one\n  printf two'
collide newline "$NL_A" "● printf one printf two"
collide space '● cp "release candidate.env" .env' '● cp "releasecandidate.env" .env'

# --- 7. restored record, repeated cycles -------------------------------------------
echo "--- 7. harvest/dismiss cycles on a restored record"
R7="$(new_repo r7)"
ID7="$(make_record "$R7" agent-pick-77 77 pick "$FIX/pick_stopped_a.txt")"
N7="$("$SESS" restore-begin "$ID7" --owner-pid $$ --mode resume | sed -n 's/.*|//p')"
"$SESS" restore-abort "$ID7" --nonce "$N7" >/dev/null
"$SESS" standin-respawned "$ID7" --nonce "$N7" --pane "" --pane-pid 0 >/dev/null 2>&1 || true
assert_eq "7 the record has restore history" "1" \
    "$("$SESS" show "$ID7" | sed -n 's/^restore_attempts://p')"
harvest record "$ID7"
for cycle in 1 2 3; do
    for c in $(items "$R7" | awk -F'|' '$4=="open" {sub(/^ITEM:/,"",$1); print $1}'); do
        wr "$R7" dismiss "$c" >/dev/null
    done
    SUM7="$(sha256sum "$(store_of "$R7")/todo.md")"
    harvest record "$ID7"
    assert_eq "7 cycle $cycle: receipt path is a no-op" "$SUM7" "$(sha256sum "$(store_of "$R7")/todo.md")"
    harvest record "$ID7" --force
    assert_eq "7 cycle $cycle: --force path is a no-op" "$SUM7" "$(sha256sum "$(store_of "$R7")/todo.md")"
done
cat "$FIX/pick_stopped_a.txt" "$FIX/pick_stopped_b.txt" > "$(cap_of "$ID7")"
harvest record "$ID7"
assert_contains "7 a new capture with one new run adds exactly one item" "added=1|" "$OUT"

# --- 8. linked worktree ---------------------------------------------------------
echo "--- 8. linked worktree"
R8="$(new_repo r8)"
WT="$R8/aiwork/t42_x"
git -C "$R8" worktree add -q --detach "$WT"
OUT="$(cd "$WT" && "$HV" banner --task 42 --skill pick < "$FIX/pick_complete_piped.txt")"
ID8="$(make_record "$WT" agent-pick-42 42 pick "$FIX/pick_complete_followups.txt")"
harvest record "$ID8"
assert_eq "8 no store inside the worktree" "no" "$([[ -e "$WT/.aitask-sitrep" ]] && echo yes || echo no)"
assert_eq "8 both harvests reach the main store" "2" "$(count_items "$R8" question)"
git -C "$R8" worktree remove --force "$WT"
CHK="$(wr "$R8" check-sources)"
assert_not_contains "8 nothing missing after the worktree is removed" "SOURCE_MISSING" "$CHK"
assert_contains "8 sources still reported" "SOURCE_OK:" "$CHK"
ID8B="$(make_record "$WT" agent-pick-77 77 pick "$FIX/pick_stopped_a.txt")"
harvest record "$ID8B"
assert_eq "8 a removed aiwork root still maps to its repo" "0" "$RC"

# --- 9. roots -------------------------------------------------------------------
echo "--- 9. roots"
PLAIN="$TMP/plain_root"
mkdir -p "$PLAIN"
ID9="$(make_record "$PLAIN" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
harvest record "$ID9"
assert_eq "9 a non-git root works" "0" "$RC"
assert_eq "9 its store has the item" "1" "$(count_items "$PLAIN" question)"
GONE="$TMP/gone_root"
mkdir -p "$GONE"
ID9B="$(make_record "$GONE" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
rm -rf "$GONE"
harvest record "$ID9B"
assert_eq "9 a removed standalone root fails" "1" "$RC"
assert_contains "9 reason root_missing" "HARVEST_FAILED:$ID9B|root_missing" "$OUT"
assert_file_not_exists "9 no receipt on failure" "$(cap_of "$ID9B").harvested"
# A tracked .gitignore negation outranks info/exclude: the local rule cannot
# ignore the store, so the harvest must refuse rather than litter git status.
R9N="$(new_repo r9n)"
printf '!.aitask-sitrep/\n!.aitask-sitrep/**\n' > "$R9N/.gitignore"
git -C "$R9N" add .gitignore && git -C "$R9N" commit -q -m negate
ID9N="$(make_record "$R9N" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
harvest record "$ID9N"
assert_eq "9 un-ignorable store: exit 1" "1" "$RC"
assert_contains "9 reason store_not_ignorable" "HARVEST_FAILED:$ID9N|store_not_ignorable" "$OUT"
assert_eq "9 nothing written into the repo" "no" "$([[ -e "$R9N/.aitask-sitrep" ]] && echo yes || echo no)"
assert_file_not_exists "9 no receipt" "$(cap_of "$ID9N").harvested"

# --- 10. nothing found ----------------------------------------------------------
echo "--- 10. nothing found"
R10="$(new_repo r10)"
ID10="$(make_record "$R10" agent-raw-1 "" raw "$FIX/raw_no_banner.txt")"
harvest record "$ID10"
assert_contains "10 nothing_found" "HARVEST_NONE:$ID10|nothing_found" "$OUT"
assert_eq "10 no store directory" "no" "$([[ -e "$R10/.aitask-sitrep" ]] && echo yes || echo no)"
assert_eq "10 no exclude line" "no" "$(grep -q 'aitask-sitrep' "$R10/.git/info/exclude" && echo yes || echo no)"
assert_file_exists "10 receipt written" "$(cap_of "$ID10").harvested"

# --- 11. writer lock held -------------------------------------------------------
echo "--- 11. writer lock held"
R11="$(new_repo r11)"
# Initialize the store first: on a fresh store the writer pauses at
# init:after_qa before write:after_backup, and one `go` releases only one.
wr "$R11" qa <<<"init" >/dev/null
FIFO="$TMP/w.fifo"
mkfifo "$FIFO"
exec 7<>"$FIFO"
AITASK_SITREP_DIR="$(store_of "$R11")" AITASK_SITREP_PAUSE_FIFO="$FIFO" \
    "$WR" qa </dev/null <<<"hold the lock" >/dev/null 2>&1 &
BG_PIDS+=("$!")
for _ in $(seq 1 100); do [[ -e "$FIFO.reached" ]] && break; sleep 0.05; done
ID11="$(make_record "$R11" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
RC=0
OUT="$(AITASK_SITREP_LOCK_TIMEOUT=1 "$HV" record "$ID11" 2>/dev/null)" || RC=$?
assert_eq "11 exit 1" "1" "$RC"
assert_contains "11 writer lock busy" "HARVEST_FAILED:$ID11|writer:lock_busy" "$OUT"
assert_file_not_exists "11 no receipt" "$(cap_of "$ID11").harvested"
printf 'go\n' >&7
wait "${BG_PIDS[-1]}" 2>/dev/null
harvest record "$ID11"
assert_eq "11 a later harvest succeeds" "0" "$RC"

# --- 12. follow-ups -------------------------------------------------------------
echo "--- 12. follow-ups"
R12="$(new_repo r12)"
: > "$R12/aitasks/t154_example_local_followup.md"
mkdir -p "$R12/aitasks/t45"
: > "$R12/aitasks/t45/t45_19_example_child_followup.md"
ID12="$(make_record "$R12" agent-pick-153 153 pick "$FIX/pick_complete_followups.txt")"
harvest record "$ID12"
L12="$(items "$R12")"
assert_contains "12 local follow-up found, open" "|task|open|next|" "$(printf '%s\n' "$L12" | grep '|t154|')"
assert_contains "12 local follow-up title" "t154 example_local_followup — follow-up of t153" "$L12"
assert_contains "12 child follow-up found" "t45_19 example_child_followup" "$L12"
assert_contains "12 missing task file -> unknown" "|task|unknown|next|" "$(printf '%s\n' "$L12" | grep '|t155|')"
assert_contains "12 unresolved cross-repo is unverified" "(cross-repo, unverified)" \
    "$(printf '%s\n' "$L12" | grep '|xproj#2171|')"
C154="$(printf '%s\n' "$L12" | grep '|t154|' | cut -d'|' -f1 | sed 's/ITEM://')"
assert_contains "12 follow-up context points at its task file" \
    "task: aitasks/t154_example_local_followup.md" "$(ctx "$R12" "$C154")"
assert_contains "12 follow-up context links the triage item" "related: c" "$(ctx "$R12" "$C154")"
XP="$TMP/xproj"
mkdir -p "$XP/aitasks/metadata"
: > "$XP/aitasks/metadata/project_config.yaml"
: > "$XP/aitasks/t2171_example_cross_repo.md"
printf 'projects:\n  - name: xproj\n    path: %s\n    last_opened: 2026-11-01\n' "$XP" > "$AITASKS_PROJECTS_INDEX"
R12B="$(new_repo r12b)"
ID12B="$(make_record "$R12B" agent-pick-153 153 pick "$FIX/pick_complete_followups.txt")"
harvest record "$ID12B"
assert_contains "12 resolved cross-repo is open" "|task|open|next|" \
    "$(items "$R12B" | grep '|xproj#2171|')"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"

# --- 13. concurrency ------------------------------------------------------------
echo "--- 13. concurrent record + banner"
R13="$(new_repo r13)"
ID13="$(make_record "$R13" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
"$HV" record "$ID13" >"$TMP/c1.out" 2>&1 &
P1=$!
(cd "$R13" && "$HV" banner --task 42 --skill pick < "$FIX/pick_complete_piped.txt") >"$TMP/c2.out" 2>&1 &
P2=$!
wait "$P1"; wait "$P2"
assert_eq "13 one triage item" "1" "$(count_items "$R13" question)"

# --- 14. purge gate -------------------------------------------------------------
echo "--- 14. purge gate"
R14="$(new_repo r14)"
ID14="$(make_record "$R14" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
rm -f "$AITASKS_FROZEN_DIR/$ID14/capture.ansi"
printf 'ROOT\t%s\n' "$R14" > "$TMP/obs.txt"
OUT="$("$SESS" purge --observed "$TMP/obs.txt")"
assert_contains "14 frozen, ANSI missing, unharvested: kept" "KEPT:$ID14|unharvested_text" "$OUT"
assert_contains "14 nothing purged" "PURGED:0" "$OUT"
assert_file_exists "14 the text survives" "$(cap_of "$ID14")"
harvest record "$ID14"
OUT="$("$SESS" purge --observed "$TMP/obs.txt")"
assert_contains "14 after a harvest it is purged" "DROPPED:$ID14|capture_missing" "$OUT"

R14L="$(new_repo r14l)"
ID14L="$(make_record "$R14L" agent-pick-77 77 pick "$FIX/pick_stopped_a.txt")"
# The restored agent's pid must be provably dead for the dead_pane rule.
sleep 0 & DEADPID=$!
wait "$DEADPID"
N14="$("$SESS" restore-begin "$ID14L" --owner-pid $$ --mode resume | sed -n 's/.*|//p')"
"$SESS" restore-launched "$ID14L" --nonce "$N14" --pane %10 --pane-pid "$DEADPID" >/dev/null
OUT="$("$SESS" restore-confirm "$ID14L" --nonce "$N14" --pane %10 --pane-pid "$DEADPID")"
assert_contains "14 liveness-only restore" "LIVE:$ID14L|liveness" "$OUT"
assert_file_exists "14 live record keeps its text" "$(cap_of "$ID14L")"
printf 'ROOT\t%s\n' "$R14L" > "$TMP/obs_dw.txt"
OUT="$("$SESS" purge --observed "$TMP/obs_dw.txt")"
assert_contains "14 dead_window keeps unharvested live text" "KEPT:$ID14L|unharvested_text" "$OUT"
printf 'ROOT\t%s\nWINDOW\t%s\tagent-pick-77\nPANE\t%s\tagent-pick-77\t%%10\t999999\t1\n' \
    "$R14L" "$R14L" "$R14L" > "$TMP/obs_dp.txt"
OUT="$("$SESS" purge --observed "$TMP/obs_dp.txt")"
assert_contains "14 dead_pane keeps unharvested live text" "KEPT:$ID14L|unharvested_text" "$OUT"
assert_file_exists "14 the live text survives both" "$(cap_of "$ID14L")"
"$SESS" drop "$ID14L" --skip-harvest >/dev/null
assert_file_not_exists "14 --skip-harvest discards it" "$(cap_of "$ID14L")"
R14N="$(new_repo r14n)"
"$SESS" upsert --root "$R14N" --window agent-pick-5 --pane %11 --pane-pid $$ >/dev/null
printf 'ROOT\t%s\n' "$R14N" > "$TMP/obs_n.txt"
OUT="$("$SESS" purge --observed "$TMP/obs_n.txt")"
assert_contains "14 a live record without text is still purged" "|dead_window" "$OUT"

# --- 15. store drop gate --------------------------------------------------------
echo "--- 15. store drop gate"
R15="$(new_repo r15)"
ID15="$(make_record "$R15" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
RC=0; OUT="$("$SESS" drop "$ID15" 2>&1)" || RC=$?
assert_eq "15 no receipt: exit 9" "9" "$RC"
assert_contains "15 HARVEST_REQUIRED" "HARVEST_REQUIRED:$ID15" "$OUT"
assert_file_exists "15 capture intact" "$(cap_of "$ID15")"
harvest record "$ID15"
printf '\nmore output\n' >> "$(cap_of "$ID15")"
RC=0; OUT="$("$SESS" drop "$ID15" 2>&1)" || RC=$?
assert_eq "15 stale receipt: exit 9" "9" "$RC"
harvest record "$ID15"
RC=0; OUT="$("$SESS" drop "$ID15" 2>&1)" || RC=$?
assert_eq "15 valid receipt: dropped" "0" "$RC"
assert_contains "15 DROPPED" "DROPPED:$ID15" "$OUT"
ID15B="$(make_record "$R15" agent-pick-43 43 pick "$FIX/pick_stopped_a.txt")"
RC=0; OUT="$("$SESS" drop "$ID15B" --skip-harvest 2>&1)" || RC=$?
assert_eq "15 --skip-harvest drops" "0" "$RC"

# --- 16. acceptance ---------------------------------------------------------------
echo "--- 16. acceptance: pointers survive the drop"
R16="$(new_repo r16)"
ID16="$(make_record "$R16" agent-pick-153 153 pick "$FIX/pick_complete_followups.txt")"
harvest record "$ID16"
"$SESS" drop "$ID16" >/dev/null
assert_eq "16 the capture directory is gone" "no" "$([[ -e "$AITASKS_FROZEN_DIR/$ID16" ]] && echo yes || echo no)"
CHK="$(wr "$R16" check-sources)"
assert_not_contains "16 no SOURCE_MISSING after drop" "SOURCE_MISSING" "$CHK"
C16="$(first_id "$R16" question)"
P16="$(ctx "$R16" "$C16" | grep -m1 'capture:' | sed 's/.*capture: //; s/#.*//')"
assert_contains "16 the retained passage still shows the closing message" "● t153 is archived" \
    "$(cat "$(store_of "$R16")/$P16")"

# --- 17. explore and trails -------------------------------------------------------
echo "--- 17. explore Created: lines and trails"
R17="$(new_repo r17)"
: > "$R17/aitasks/t562_example_first_task.md"
ID17="$(make_record "$R17" agent-explore-1 "" explore "$FIX/explore_created.txt")"
harvest record "$ID17"
L17="$(items "$R17")"
assert_contains "17 created parent task" "t562 example_first_task — created by agent-explore-1" "$L17"
assert_contains "17 created child task (file not found -> unknown)" "|task|unknown|next|" \
    "$(printf '%s\n' "$L17" | grep '|t562_1|')"
assert_not_contains "17 drafts are not tasks" "draft" "$L17"
R17T="$(new_repo r17t)"
ID17T="$(make_record "$R17T" agent-pick-99 99 pick "$FIX/trail_mention.txt")"
harvest record "$ID17T"
CT="$(ctx "$R17T" "$(first_id "$R17T" question)")"
assert_contains "17 trail pointer on the triage item" "trail: art:trail-example-plan-2" "$CT"
assert_eq "17 a trail already pointed at gets no separate watch item" "0" "$(count_items "$R17T" watch)"
printf '● Read the trail art:trail-lonely-1 later.\n' > "$TMP/lonely.txt"
ID17L="$(make_record "$R17T" agent-raw-2 "" raw "$TMP/lonely.txt")"
harvest record "$ID17L"
assert_eq "17 a trail outside any wrap-up becomes a watch item" "1" "$(count_items "$R17T" watch)"

# --- 17b. a '|' in a root path is data, not a separator --------------------------
echo "--- 17b. root paths with '|' and control characters"
RP="$(new_repo 'pipe|root')"
PREFIX="$TMP/pipe"
mkdir -p "$PREFIX"
harvest capture --root "$RP" --agent a --task 42 --operation pick < "$FIX/pick_complete_nofollowups.txt"
assert_eq "17b capture into a '|' root succeeds" "0" "$RC"
assert_file_exists "17b the store is in the requested repo" "$RP/.aitask-sitrep/todo.md"
assert_eq "17b nothing under the path prefix" "no" "$([[ -e "$PREFIX/.aitask-sitrep" ]] && echo yes || echo no)"
IDP="$(make_record "$RP" agent-pick-77 77 pick "$FIX/pick_stopped_a.txt")"
harvest record "$IDP"
assert_eq "17b record with a '|' root succeeds" "0" "$RC"
assert_eq "17b record harvest lands in the same store" "2" "$(count_items "$RP" question)"
NLROOT="$TMP/nl
root"
mkdir -p "$NLROOT"
harvest capture --root "$NLROOT" < "$FIX/pick_complete_nofollowups.txt"
assert_eq "17b a line break in a root fails" "1" "$RC"
assert_contains "17b root_unsupported" "HARVEST_FAILED:capture|root_unsupported" "$OUT"
assert_eq "17b nothing created there" "no" "$([[ -e "$NLROOT/.aitask-sitrep" ]] && echo yes || echo no)"
# A safe-looking symlink that RESOLVES to a line-break path: the check must
# apply to the final root, not only to the supplied string.
mkdir -p "$TMP/real"
ln -s "$NLROOT" "$TMP/alias_plain"
harvest capture --root "$TMP/alias_plain" < "$FIX/pick_complete_nofollowups.txt"
assert_eq "17b resolved line-break root (non-git) fails" "1" "$RC"
assert_contains "17b resolved: root_unsupported" "HARVEST_FAILED:capture|root_unsupported" "$OUT"
assert_eq "17b no store under the truncated prefix" "no" \
    "$([[ -e "$TMP/nl/.aitask-sitrep" || -e "$TMP/real/.aitask-sitrep" ]] && echo yes || echo no)"
NLGIT="$TMP/nlgit
repo"
mkdir -p "$NLGIT"
git -C "$NLGIT" init -q && git -C "$NLGIT" commit -q --allow-empty -m init
ln -s "$NLGIT" "$TMP/alias_git"
harvest capture --root "$TMP/alias_git" < "$FIX/pick_complete_nofollowups.txt"
assert_eq "17b resolved line-break root (git) fails" "1" "$RC"
assert_contains "17b resolved git: root_unsupported" "HARVEST_FAILED:capture|root_unsupported" "$OUT"
assert_eq "17b no store under the truncated git prefix" "no" \
    "$([[ -e "$TMP/nlgit/.aitask-sitrep" ]] && echo yes || echo no)"
assert_eq "17b no store inside the line-break repo either" "no" \
    "$([[ -e "$NLGIT/.aitask-sitrep" ]] && echo yes || echo no)"

# --- 18. argument validation ------------------------------------------------------
echo "--- 18. arguments"
harvest record nothex
assert_eq "18 bad record id: exit 2" "2" "$RC"
harvest capture --root "$TMP/../etc" </dev/null
assert_eq "18 '..' root: exit 2" "2" "$RC"
harvest banner --task notanid </dev/null
assert_eq "18 bad task id: exit 2" "2" "$RC"
harvest frobnicate
assert_eq "18 unknown verb: exit 2" "2" "$RC"

# --- 19. the sitrep agent's own record (t2175_4) ----------------------------------
# Its screen only echoes the store; a harvest would feed the store back into
# itself. The skip still writes the receipt, so drop/purge are not blocked.
echo "--- 19. sitrep agent window"
R19="$(new_repo r19)"
ID19="$(make_record "$R19" agent-sitrep "" raw "$FIX/pick_complete_followups.txt")"
harvest record "$ID19"
assert_eq "19 sitrep window: exit 0" "0" "$RC"
assert_contains "19 HARVEST_NONE sitrep_agent" "HARVEST_NONE:$ID19|sitrep_agent" "$OUT"
assert_not_contains "19 no item harvested" "HARVEST_ITEM:" "$OUT"
assert_eq "19 no store created" "absent" "$([[ -e "$(store_of "$R19")" ]] && echo present || echo absent)"
assert_file_exists "19 receipt written" "$(cap_of "$ID19").harvested"
RC=0; OUT="$("$SESS" drop "$ID19" 2>&1)" || RC=$?
assert_eq "19 store drop passes the receipt gate" "0" "$RC"
ID19B="$(make_record "$R19" agent-sitrep-2 "" raw "$FIX/pick_complete_followups.txt")"
harvest all --root "$R19"
assert_contains "19 all: agent-sitrep-2 skipped too" "HARVEST_NONE:$ID19B|sitrep_agent" "$OUT"
assert_eq "19 all: still no store" "absent" "$([[ -e "$(store_of "$R19")" ]] && echo present || echo absent)"
# Controls: the regex is anchored, so near-miss names are ordinary agents.
for win in agent-sitrepx agent-pick-sitrep agent-sitrep-0; do
    R19C="$(new_repo "r19_$win")"
    ID19C="$(make_record "$R19C" "$win" "" raw "$FIX/pick_complete_followups.txt")"
    harvest record "$ID19C"
    assert_contains "19 control $win is harvested" "HARVESTED:$ID19C|" "$OUT"
    assert_not_contains "19 control $win not skipped" "sitrep_agent" "$OUT"
done

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
fi
[[ "$FAIL" -eq 0 ]]
