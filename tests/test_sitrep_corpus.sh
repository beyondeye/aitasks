#!/usr/bin/env bash
# End-to-end tests for the sitrep harvest fallback and review corpus (t2175_6).
#
# Real harvest helper, real store writer, real session store -- under a scratch
# HOME / session store / frozen dir / project registry, TMUX unset, so nothing
# reaches the real ~/.config or this repository's .aitask-sitrep/.
#
#   0  legacy (pre-cert) receipts authorise nothing: drop refused, purge keeps,
#      a plain harvest re-classifies; benign input gets no case; dismissals stick
#   1  every trigger -> raw evidence, case files, ONE review item, a cert receipt
#   2  negatives -> no case, no review item
#   3  mixed success/failure: the failed occurrence is caught, the partial
#      items are written and linked
#   3b provenance: identical bytes from three source identities -> one review
#      item, three origins; an ordinary retry writes nothing
#   4  drop + worktree removal: check-sources (raw too) and case read survive;
#      a corrupted raw input is reported missing
#   5  no agent running: the queue persists; review closes it; evidence stays;
#      a dismissed review stays dismissed
#   5b forged case-record headers in harvested text change no case; a stale or
#      failed review close leaves the case pending; a retry closes it
#   5c a cached (already_harvested) result still reports the review
#   5d a renamed open / done / dismissed review keeps its case (provenance,
#      not title): no second review, its state kept
#   5e status follows the accepted completion: a stale resolved attempt is
#      history; a later resolution re-closes; a dismissal wins
#   6  --force and concurrent harvests -> one review item; closed stays closed
#   7  fault injection at every case-write point withholds the receipt; a retry
#      completes the case
#   8  the pre-fix parser misses a joined banner; the current one replays it,
#      --apply recovers the item; export -> a fixture that fails on the old copy
#   9  a raw input over the cap fails closed (no receipt)
#
# Bodies run in the main shell (no subshell asserts): the plain counters do.

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# Pipe-free overrides of the shared helpers: under `pipefail`, the shared
# `printf | grep -q` fails with SIGPIPE when grep exits before a larger
# haystack is fully written (seen as a flake on `case show` output). A
# here-string has no pipe.
assert_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if grep -qF -- "$needle" <<<"$haystack"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected output containing '$needle', got '$haystack')"
    fi
}
assert_not_contains() {
    local desc="$1" needle="$2" haystack="$3"
    if ! grep -qF -- "$needle" <<<"$haystack"; then
        assert_record_pass
    else
        assert_record_fail
        echo "FAIL: $desc (expected output NOT containing '$needle', got '$haystack')"
    fi
}

SCRIPTS="${AIT_CORPUS_TEST_SCRIPTS:-$PROJECT_DIR/.aitask-scripts}"
HV="$SCRIPTS/aitask_sitrep_harvest.sh"
WR="$SCRIPTS/aitask_sitrep_todo.sh"
SESS="$SCRIPTS/aitask_agent_sessions.sh"
FIX="$PROJECT_DIR/tests/fixtures/sitrep_harvest"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_corpus_XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
BG_PIDS=()
cleanup() {
    local p
    for p in "${BG_PIDS[@]:-}"; do
        [[ -n "$p" ]] && kill -9 "$p" 2>/dev/null
    done
    chmod -R u+w "$TMP" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

AIT_PYTHON="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" && require_ait_python)"
export AIT_PYTHON
export HOME="$TMP/home"
mkdir -p "$HOME/.config/aitasks"
export AITASKS_AGENT_SESSIONS_FILE="$HOME/.config/aitasks/agent_sessions.json"
export AITASKS_FROZEN_DIR="$TMP/frozen"
export AITASKS_PROJECTS_INDEX="$TMP/projects.yaml"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"
export AITASK_SITREP_NOW="2026-11-05T10:00:00Z"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
unset TMUX TMUX_PANE AITASK_SITREP_DIR AITASK_SITREP_PAUSE_FIFO AITASK_SITREP_LOCK_TIMEOUT \
      AITASK_SITREP_HARVEST_PAUSE_FIFO AITASK_SITREP_HARVEST_LOCK_TIMEOUT \
      AITASK_SITREP_HARVEST_RUN_ID AITASK_SITREP_HARVEST_FAULT AITASK_SITREP_RAW_MAX

# --- helpers -----------------------------------------------------------------

new_repo() {
    local d="$TMP/$1"
    mkdir -p "$d/aitasks/metadata"
    : > "$d/aitasks/metadata/project_config.yaml"
    git -C "$d" init -q
    git -C "$d" add -A
    git -C "$d" commit -q -m init
    printf '%s' "$d"
}

make_record() {   # make_record <root> <window> <task> <op> <capture file> -> id
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
harvest() { RC=0; OUT="$("$HV" "$@" 2>"$TMP/err")" || RC=$?; }
store_of() { printf '%s' "$1/.aitask-sitrep"; }
items() { AITASK_SITREP_DIR="$(store_of "$1")" "$WR" list 2>/dev/null; }
wr() { local root="$1"; shift; AITASK_SITREP_DIR="$(store_of "$root")" "$WR" "$@"; }
reviews() {   # reviews <root> [state] -> count of review items
    items "$1" | awk -F'|' -v s="${2:-}" \
        '$3=="question" && index($0, "Analyze unparsed agent output") && (s=="" || $4==s) {n++} END {print n+0}'
}
review_id() { items "$1" | awk -F'|' 'index($0, "Analyze unparsed agent output") {sub(/^ITEM:/,"",$1); print $1; exit}'; }
rev_of() { items "$1" | awk -F'|' -v c="ITEM:$2" '$1==c {print $2; exit}'; }
state_of() { items "$1" | awk -F'|' -v c="ITEM:$2" '$1==c {print $4; exit}'; }
case_cmd() { local root="$1"; shift; (cd "$root" && "$HV" case "$@"); }
case_hex() { case_cmd "$1" list | sed -n 's/^CASE:\([0-9a-f]\{16\}\)|.*/\1/p' | head -1; }
sha_of() { sha256sum "$1" | cut -d' ' -f1; }
legacy_receipt() {   # the pre-t2175_6 receipt text: sha + store, no cert
    printf 'sha256=%s\nstore=%s\n' "$(sha_of "$(cap_of "$1")")" "$(store_of "$2")" \
        > "$(cap_of "$1").harvested"
}
purge_obs() { printf 'ROOT\t%s\n' "$1" > "$TMP/obs.txt"; "$SESS" purge --observed "$TMP/obs.txt"; }

gen() {   # gen <name> -> writes $TMP/<name>.txt from an inline python recipe
    "$AIT_PYTHON" - "$FIX" "$TMP/$1.txt" "$1" <<'PY'
import sys
fix, out, name = sys.argv[1:4]
def read(n):
    return open(f"{fix}/{n}", encoding="utf-8").read()
if name == "badfollow":
    t = read("pick_complete_nofollowups.txt").replace(
        "follow-ups created: none", "follow-ups created: t154, t155.")
elif name == "trunc":
    filler = "  " + "x" * 400
    t = ("● The closing message of t66 is very long.\n"
         + "\n".join(filler for _ in range(190)) + "\n\n"
         "  ✔ aitask workflow complete — t66 example_long_message\n"
         "    outcome: archived (commit 1a2b3c4) · pushed: yes\n"
         "    follow-ups created: none\n")
elif name == "marker_ab":
    t = ("● Bash(./.aitask-scripts/aitask_sitrep_harvest.sh banner --task 76 --skill pick <<'SITREP_EOF'\n"
         "  ⎿  HARVEST_RUN:aaaaaaaaaaaaaaaa\n"
         "     HARVEST_ITEM:run-aaaaaaaaaaaaaaaa|c1|added|question|-\n\n"
         "● The t76 run ended here; its banner never rendered.\n\n"
         "❯ continue with the next task\n\n" + read("pick_stopped_marker.txt"))
elif name == "marker_only":
    t = ("● Bash(./.aitask-scripts/aitask_sitrep_harvest.sh banner --task 76 --skill pick <<'SITREP_EOF'\n"
         "  ⎿  HARVEST_RUN:bbbbbbbbbbbbbbbb\n\n"
         "● The t76 run is complete.\n")
elif name == "created_mixed":
    t = ("● Bash(./.aitask-scripts/aitask_create.sh --batch --name good)\n"
         "  ⎿  Created: aitasks/t71_good_task.md Created: aitasks/t72.md\n\n"
         "● Created the follow-up tasks.\n")
elif name == "quoted_banner":
    t = read("pick_stopped_a.txt").replace(
        "reason: ", "reason: the earlier ✔ aitask workflow complete — t5 banner was lost; ", 1)
elif name == "piped_nobanner":
    t = "Done. I pushed main and archived the task.\n"
else:
    raise SystemExit(f"unknown recipe {name}")
open(out, "w", encoding="utf-8").write(t)
PY
    printf '%s' "$TMP/$1.txt"
}

echo "=== sitrep harvest fallback and review corpus (t2175_6) ==="

# --- 0. legacy receipts ---------------------------------------------------------
echo "--- 0. legacy receipts"
R0="$(new_repo r0)"
ID0="$(make_record "$R0" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
legacy_receipt "$ID0" "$R0"
RC=0; OUT="$("$SESS" drop "$ID0" 2>&1)" || RC=$?
assert_eq "0 legacy receipt: drop refused (exit 9)" "9" "$RC"
assert_contains "0 HARVEST_REQUIRED" "HARVEST_REQUIRED:$ID0" "$OUT"
rm -f "$AITASKS_FROZEN_DIR/$ID0/capture.ansi"
assert_contains "0 legacy receipt: purge keeps the text" "KEPT:$ID0|unharvested_text" "$(purge_obs "$R0")"
harvest record "$ID0"
assert_eq "0 plain harvest exit 0" "0" "$RC"
assert_not_contains "0 no already_harvested short-circuit" "already_harvested" "$OUT"
assert_contains "0 review recorded" "HARVEST_REVIEW:$ID0|" "$OUT"
assert_contains "0 receipt carries cert=2" "cert=2" "$(cat "$(cap_of "$ID0").harvested")"
RC=0; "$SESS" drop "$ID0" >/dev/null 2>&1 || RC=$?
assert_eq "0 cert receipt: drop succeeds" "0" "$RC"

R0B="$(new_repo r0b)"
ID0B="$(make_record "$R0B" agent-pick-42 42 pick "$FIX/pick_complete_nofollowups.txt")"
harvest record "$ID0B"
T0B="$(items "$R0B" | awk -F'|' '$3=="question" {sub(/^ITEM:/,"",$1); print $1; exit}')"
wr "$R0B" dismiss "$T0B" --outcome "user: not needed" >/dev/null
legacy_receipt "$ID0B" "$R0B"
harvest record "$ID0B"
assert_not_contains "0 benign legacy re-harvest: no short-circuit" "already_harvested" "$OUT"
assert_contains "0 benign: existing item reported exists" "|$T0B|exists|question|" "$OUT"
assert_not_contains "0 benign: no review" "HARVEST_REVIEW:" "$OUT"
assert_eq "0 dismissed legacy item stays dismissed" "dismissed" "$(state_of "$R0B" "$T0B")"
assert_contains "0 benign receipt upgraded" "cert=2" "$(cat "$(cap_of "$ID0B").harvested")"
assert_dir_not_exists "0 benign: no raw store" "$(store_of "$R0B")/raw"

# --- 1. triggers ----------------------------------------------------------------
echo "--- 1. every trigger preserves raw evidence and queues one review"
check_trigger() {   # check_trigger <label> <root> <capture> <code>
    local label="$1" root="$2" cap="$3" code="$4" hex
    assert_eq "1 $label: exit 0" "0" "$RC"
    assert_contains "1 $label: HARVEST_REVIEW added with $code" "|added|case=" "$OUT"
    assert_contains "1 $label: reason $code" "$code" "$(grep '^HARVEST_REVIEW:' <<<"$OUT")"
    assert_contains "1 $label: final names the review" "|review=c" "$(grep '^HARVESTED:' <<<"$OUT")"
    assert_eq "1 $label: one review item" "1" "$(reviews "$root")"
    hex="$(case_hex "$root")"
    assert_eq "1 $label: raw input verbatim" "$(sha_of "$cap")" \
        "$(sha_of "$(store_of "$root")/raw/$hex.txt" 2>/dev/null)"
    assert_contains "1 $label: listed pending" "CASE:$hex|pending|" "$(case_cmd "$root" list --pending)"
    assert_contains "1 $label: origin, analysis, excerpt" "ANALYSIS:" "$(case_cmd "$root" show "$hex")"
}
R1A="$(new_repo r1a)"
ID1A="$(make_record "$R1A" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID1A"
check_trigger "incomplete banner" "$R1A" "$FIX/truncated_banner.txt" banner_incomplete
assert_contains "1 incomplete: cert receipt" "cert=2" "$(cat "$(cap_of "$ID1A").harvested")"

R1B="$(new_repo r1b)"
C1B="$(gen badfollow)"
ID1B="$(make_record "$R1B" agent-pick-42 42 pick "$C1B")"
harvest record "$ID1B"
check_trigger "bad follow-up" "$R1B" "$C1B" bad_followup
assert_contains "1 bad follow-up: the good token is still a task item" "|t154|" "$(items "$R1B")"

R1C="$(new_repo r1c)"
C1C="$(gen trunc)"
ID1C="$(make_record "$R1C" agent-pick-66 66 pick "$C1C")"
harvest record "$ID1C"
check_trigger "truncated passage" "$R1C" "$C1C" passage_truncated

R1D="$(new_repo r1d)"
C1D="$(gen marker_only)"
ID1D="$(make_record "$R1D" agent-pick-76 76 pick "$C1D")"
harvest record "$ID1D"
check_trigger "marker without banner" "$R1D" "$C1D" marker_without_banner

R1E="$(new_repo r1e)"
C1E="$(gen piped_nobanner)"
RC=0; OUT="$(cd "$R1E" && "$HV" banner --task 77 --skill pick < "$C1E" 2>"$TMP/err")" || RC=$?
check_trigger "pipe without banner" "$R1E" "$C1E" pipe_without_banner

R1F="$(new_repo r1f)"
harvest capture --root "$R1F" --agent agent-pick-61 --task 61 --operation pick < "$FIX/joined_banner.txt"
assert_eq "1 live capture of a reliable joined banner: no review" "0" "$(reviews "$R1F")"
assert_contains "1 the joined banner's follow-up is extracted" "|t62|" "$(items "$R1F")"

# --- 2. negatives ---------------------------------------------------------------
echo "--- 2. legitimately empty or valid input: no case"
for spec in "raw_no_banner.txt|raw|agent-raw-1|" "pick_complete_nofollowups.txt|pick|agent-pick-42|42" \
            "pick_complete_followups.txt|pick|agent-pick-153|153" "explore_created.txt|explore|agent-explore-1|" \
            "pick_stopped_marker.txt|pick|agent-pick-77|77"; do
    IFS='|' read -r f op win task <<<"$spec"
    R2="$(new_repo "r2_${f%.txt}")"
    ID2="$(make_record "$R2" "$win" "$task" "$op" "$FIX/$f")"
    harvest record "$ID2"
    assert_eq "2 $f: exit 0" "0" "$RC"
    assert_not_contains "2 $f: no review" "HARVEST_REVIEW:" "$OUT"
    assert_eq "2 $f: no review item" "0" "$(reviews "$R2")"
    assert_dir_not_exists "2 $f: no raw store" "$(store_of "$R2")/raw"
done
assert_contains "2 unresolved cross-repo stays unknown, not a reason" "xproj#2171" "$(items "$TMP/r2_pick_complete_followups")"

# --- 3. mixed success / failure -------------------------------------------------
echo "--- 3. mixed occurrences"
R3="$(new_repo r3)"
C3="$(gen marker_ab)"
ID3="$(make_record "$R3" agent-pick-77 77 pick "$C3")"
harvest record "$ID3"
SHOW="$(case_cmd "$R3" show "$(case_hex "$R3")")"
assert_contains "3 marker A unclaimed" "REASON:marker_without_banner|" "$SHOW"
assert_contains "3 it is marker A" "aaaaaaaaaaaaaaaa" "$(grep '^REASON:' <<<"$SHOW")"
assert_not_contains "3 marker B is claimed by its banner" "0123456789abcdef" "$(grep '^REASON:' <<<"$SHOW")"
assert_contains "3 B's banner still yields its task item" "|t77|" "$(items "$R3")"
assert_contains "3 the partial items are in the analysis" "ITEM:c" "$SHOW"
RID3="$(review_id "$R3")"
assert_contains "3 the review relates to the partial items" "related: c" "$(wr "$R3" context "$RID3")"

R3C="$(new_repo r3c)"
C3C="$(gen created_mixed)"
ID3C="$(make_record "$R3C" agent-explore-1 "" explore "$C3C")"
harvest record "$ID3C"
assert_contains "3 the valid Created reference is a task item" "|t71|" "$(items "$R3C")"
assert_contains "3 the malformed one on the same line is a reason" "created_unparsed" \
    "$(grep '^HARVEST_REVIEW:' <<<"$OUT")"

R3Q="$(new_repo r3q)"
C3Q="$(gen quoted_banner)"
ID3Q="$(make_record "$R3Q" agent-pick-77 77 pick "$C3Q")"
harvest record "$ID3Q"
assert_contains "3 a banner quoted inside a field is unparsed" "banner_unparsed" \
    "$(grep '^HARVEST_REVIEW:' <<<"$OUT")"
assert_contains "3 the real banner still yields its item" "|t77|" "$(items "$R3Q")"

# --- 3b. provenance ---------------------------------------------------------------
echo "--- 3b. one input, three source identities"
R3B="$(new_repo r3b)"
IDA="$(make_record "$R3B" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
IDB="$(make_record "$R3B" agent-pick-89 89 pick "$FIX/truncated_banner.txt")"
harvest record "$IDA"
harvest record "$IDB"
assert_contains "3b second record: the review exists" "|exists|case=" "$(grep '^HARVEST_REVIEW:' <<<"$OUT")"
harvest capture --root "$R3B" --agent agent-pick-88 --task 88 --operation pick < "$FIX/truncated_banner.txt"
assert_eq "3b one review item" "1" "$(reviews "$R3B")"
H3B="$(case_hex "$R3B")"
SHOW="$(case_cmd "$R3B" show "$H3B")"
assert_eq "3b three origins" "3" "$(grep -c '^ORIGIN:' <<<"$SHOW")"
assert_contains "3b record A's origin" "record=$IDA" "$SHOW"
assert_contains "3b record B's origin" "record=$IDB" "$SHOW"
assert_contains "3b the capture origin" "source=capture" "$SHOW"
assert_eq "3b one analysis per origin" "3" "$(grep -c '^ANALYSIS:' <<<"$SHOW")"
BEFORE="$(ls "$(store_of "$R3B")/sources" "$(store_of "$R3B")/raw" "$(store_of "$R3B")/cases" | sha256sum)"
NITEMS="$(items "$R3B" | wc -l)"
harvest record "$IDA" --force
assert_eq "3b retry: no new file" "$BEFORE" "$(ls "$(store_of "$R3B")/sources" "$(store_of "$R3B")/raw" "$(store_of "$R3B")/cases" | sha256sum)"
assert_eq "3b retry: no new item" "$NITEMS" "$(items "$R3B" | wc -l)"
"$SESS" drop "$IDA" >/dev/null 2>&1
"$SESS" drop "$IDB" >/dev/null 2>&1
assert_dir_not_exists "3b the captures are gone" "$AITASKS_FROZEN_DIR/$IDA"
SHOW="$(case_cmd "$R3B" show "$H3B")"
assert_eq "3b all three origins survive the drops" "3" "$(grep -c '^ORIGIN:' <<<"$SHOW")"
assert_not_contains "3b check-sources clean" "SOURCE_MISSING" "$(wr "$R3B" check-sources)"

# --- 4. drop + worktree removal ----------------------------------------------------
echo "--- 4. drop + worktree removal"
R4="$(new_repo r4)"
WT4="$R4/aiwork/t88_x"
git -C "$R4" worktree add -q --detach "$WT4"
ID4="$(make_record "$WT4" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID4"
assert_eq "4 the review reached the main store" "1" "$(reviews "$R4")"
"$SESS" drop "$ID4" >/dev/null 2>&1
git -C "$R4" worktree remove --force "$WT4"
H4="$(case_hex "$R4")"
CHK="$(wr "$R4" check-sources)"
assert_not_contains "4 nothing missing" "SOURCE_MISSING" "$CHK"
assert_contains "4 the raw input is checked" "|raw/$H4.txt" "$CHK"
assert_eq "4 case read returns the input" "$(sha_of "$FIX/truncated_banner.txt")" \
    "$(case_cmd "$R4" read "$H4" | sha256sum | cut -d' ' -f1)"
assert_contains "4 case read --lines" "aitask workflow complete" "$(case_cmd "$R4" read "$H4" --lines 3)"
printf 'x' >> "$(store_of "$R4")/raw/$H4.txt"
assert_contains "4 a corrupted raw input is reported missing" "SOURCE_MISSING:" "$(wr "$R4" check-sources)"
RC=0; OUT="$(case_cmd "$R4" read "$H4" 2>&1)" || RC=$?
assert_eq "4 case read refuses a mismatch (exit 4)" "4" "$RC"

# --- 5. the queue without a running agent -------------------------------------------
echo "--- 5. queue, review, dismissal"
R5="$(new_repo r5)"
ID5="$(make_record "$R5" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID5"
H5="$(case_hex "$R5")"
RID5="$(review_id "$R5")"
assert_contains "5 a fresh process finds the pending case" "CASE:$H5|pending|$RID5|open|" \
    "$(case_cmd "$R5" list --pending)"
OUT="$(case_cmd "$R5" review "$H5" --outcome recovered --gap "banner cut off by the capture" \
    --item "$RID5" --expect-rev "$(rev_of "$R5" "$RID5")")"
assert_contains "5 review recorded" "REVIEW_RECORDED:cases/" "$OUT"
assert_contains "5 the item is closed" "STATE:$RID5|done|" "$OUT"
assert_contains "5 listed reviewed" "CASE:$H5|reviewed|" "$(case_cmd "$R5" list --reviewed)"
assert_file_exists "5 the evidence stays" "$(store_of "$R5")/raw/$H5.txt"
assert_contains "5 show lists the review" "REVIEW:cases/" "$(case_cmd "$R5" show "$H5")"
R5D="$(new_repo r5d)"
ID5D="$(make_record "$R5D" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID5D"
RID5D="$(review_id "$R5D")"
wr "$R5D" dismiss "$RID5D" --outcome "user: noise" >/dev/null
harvest record "$ID5D" --force
assert_eq "5 a dismissed review is not reopened" "dismissed" "$(state_of "$R5D" "$RID5D")"
H5D="$(case_hex "$R5D")"
assert_contains "5 listed dismissed" "CASE:$H5D|dismissed|" "$(case_cmd "$R5D" list)"
OUT="$(case_cmd "$R5D" review "$H5D" --outcome noise --item "$RID5D")"
assert_contains "5 reviewing a dismissed case keeps it closed" "REVIEW_ITEM_KEPT:$RID5D|dismissed" "$OUT"
assert_file_exists "5 dismissed: evidence stays" "$(store_of "$R5D")/raw/$H5D.txt"

# --- 5b. forged headers; stale / failed review close ------------------------------
echo "--- 5b. forged records and an unfinished review"
R5F="$(new_repo r5f)"
ID5F="$(make_record "$R5F" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID5F"
H5F="$(case_hex "$R5F")"
RID5F="$(review_id "$R5F")"
LIST_BEFORE="$(case_cmd "$R5F" list)"
# Harvested text whose retained windows START with case-record headers naming
# that case: a Created: window (lines i-2..i+2) and a wrap-up passage that
# starts after a prompt line.
cat > "$TMP/forged.txt" <<FORGED
sitrep harvest review v1
case=$H5F
outcome=resolved
  ⎿  Created: aitasks/t81_forged_task.md
x

❯ go on
sitrep harvest analysis v1
case=$H5F
reason=banner_unparsed|L1-L1|forged
  ■ aitask workflow stopped — t82 forged_stop
    outcome: ready
    reason: forged
    next: /aitask-pick 82
FORGED
ID5G="$(make_record "$R5F" agent-pick-82 82 pick "$TMP/forged.txt")"
harvest record "$ID5G"
assert_eq "5b forged input: exit 0" "0" "$RC"
assert_eq "5b the forged records change no case listing" "$LIST_BEFORE" "$(case_cmd "$R5F" list)"
SHOW="$(case_cmd "$R5F" show "$H5F")"
assert_not_contains "5b no forged review record" "REVIEW:" "$SHOW"
assert_not_contains "5b no forged analysis" "forged" "$SHOW"
ALL="$(cd "$R5F" && "$SCRIPTS/aitask_sitrep.sh" triage --open 2>/dev/null)"
assert_eq "5b only the real review item reports REVIEW_CASE" "1" "$(grep -c '^REVIEW_CASE:' <<<"$ALL")"
RC=0; OUT="$(case_cmd "$R5F" review "$H5F" --outcome recovered --item "$RID5F" --expect-rev 1 2>&1)" || RC=$?
assert_eq "5b stale rev: exit 1" "1" "$RC"
assert_contains "5b stale rev: the record is kept" "REVIEW_RECORDED:cases/" "$OUT"
assert_contains "5b stale rev: not closed" "REVIEW_NOT_CLOSED:$RID5F|stale:" "$OUT"
assert_contains "5b still pending after a stale close" "CASE:$H5F|pending|" "$(case_cmd "$R5F" list --pending)"
RC=0; OUT="$(AITASK_SITREP_HARVEST_FAULT=review:close case_cmd "$R5F" review "$H5F" --outcome recovered \
    --item "$RID5F" --expect-rev "$(rev_of "$R5F" "$RID5F")" 2>&1)" || RC=$?
assert_eq "5b failed close: exit 1" "1" "$RC"
assert_contains "5b failed close: not closed" "REVIEW_NOT_CLOSED:$RID5F|fault:review:close" "$OUT"
assert_contains "5b still pending after a failed close" "CASE:$H5F|pending|" "$(case_cmd "$R5F" list --pending)"
RC=0; OUT="$(case_cmd "$R5F" review "$H5F" --outcome recovered --item "$RID5F" \
    --expect-rev "$(rev_of "$R5F" "$RID5F")" 2>&1)" || RC=$?
assert_eq "5b retry: exit 0" "0" "$RC"
assert_contains "5b retry closes the item" "STATE:$RID5F|done|" "$OUT"
assert_contains "5b retry: reviewed" "CASE:$H5F|reviewed|" "$(case_cmd "$R5F" list)"

# --- 5c. cached results --------------------------------------------------------------
echo "--- 5c. an already-harvested capture still reports its review"
R5C="$(new_repo r5c)"
ID5C="$(make_record "$R5C" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID5C"
RID5C="$(review_id "$R5C")"
harvest record "$ID5C"
assert_contains "5c cached: already_harvested" "HARVEST_NONE:$ID5C|already_harvested" "$OUT"
assert_contains "5c cached: the review is reported" \
    "HARVEST_REVIEW:$ID5C|$RID5C|exists|case=$(case_hex "$R5C")|banner_incomplete" "$OUT"
VERDICT="$(printf '%s' "$OUT" | "$AIT_PYTHON" -c '
import sys
sys.path.insert(0, sys.argv[1]); sys.path.insert(0, sys.argv[1] + "/lib")
from monitor import sitrep_close as sc
r = sc.parse_harvest_output(0, sys.stdin.read())
print(r.ok, r.verdict())' "$SCRIPTS" 2>&1)"
assert_contains "5c the monitor shows the review on a cached result" \
    "True Nothing new to harvest (already_harvested) — output kept for sitrep review ($RID5C)" "$VERDICT"

# --- 5d. ownership survives a rename -----------------------------------------------
echo "--- 5d. renamed reviews keep their case"
questions() { items "$1" | awk -F'|' '$3=="question"' | wc -l; }
for st5 in open "done" dismissed; do
    R5R="$(new_repo "r5r_$st5")"
    ID5R="$(make_record "$R5R" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
    harvest record "$ID5R"
    H5R="$(case_hex "$R5R")"
    RID5R="$(review_id "$R5R")"
    case "$st5" in
        done) case_cmd "$R5R" review "$H5R" --outcome nothing_missed --item "$RID5R" \
                  --expect-rev "$(rev_of "$R5R" "$RID5R")" >/dev/null ;;
        dismissed) wr "$R5R" dismiss "$RID5R" --outcome "user: noise" >/dev/null ;;
    esac
    wr "$R5R" update "$RID5R" --title "My own name for this" --expect-rev "$(rev_of "$R5R" "$RID5R")" >/dev/null
    WANT="$(case "$st5" in open) echo pending ;; done) echo reviewed ;; *) echo dismissed ;; esac)"
    assert_contains "5d renamed $st5 review: still owns its case" "CASE:$H5R|$WANT|$RID5R|" "$(case_cmd "$R5R" list)"
    NQ="$(questions "$R5R")"
    harvest record "$ID5R" --force
    assert_contains "5d renamed $st5 review: re-harvest finds it" "HARVEST_REVIEW:$ID5R|$RID5R|exists|" "$OUT"
    assert_eq "5d renamed $st5 review: no second review" "$NQ" "$(questions "$R5R")"
    assert_eq "5d renamed $st5 review: state kept" "$st5" "$(state_of "$R5R" "$RID5R")"
done

# --- 5e. status follows the accepted completion --------------------------------------
echo "--- 5e. a failed resolved attempt is history, not the outcome"
R5S="$(new_repo r5s)"
ID5S="$(make_record "$R5S" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID5S"
H5S="$(case_hex "$R5S")"
RID5S="$(review_id "$R5S")"
RC=0; case_cmd "$R5S" review "$H5S" --outcome resolved --item "$RID5S" --expect-rev 1 >/dev/null 2>&1 || RC=$?
assert_eq "5e stale resolved attempt: exit 1" "1" "$RC"
case_cmd "$R5S" review "$H5S" --outcome unrecoverable --item "$RID5S" \
    --expect-rev "$(rev_of "$R5S" "$RID5S")" >/dev/null
assert_contains "5e the accepted outcome is unrecoverable: reviewed" "CASE:$H5S|reviewed|" "$(case_cmd "$R5S" list)"
assert_contains "5e both attempts stay as history" "|resolved|" "$(case_cmd "$R5S" show "$H5S" | grep '^REVIEW:')"
OUT="$(case_cmd "$R5S" review "$H5S" --outcome resolved --parser 2 --item "$RID5S" \
    --expect-rev "$(rev_of "$R5S" "$RID5S")")"
assert_contains "5e a later resolution re-closes the done item" "STATE:$RID5S|done|" "$OUT"
assert_contains "5e now resolved" "CASE:$H5S|resolved|" "$(case_cmd "$R5S" list)"
wr "$R5S" dismiss "$RID5S" --outcome "user: not tracking" --expect-rev "$(rev_of "$R5S" "$RID5S")" >/dev/null
assert_contains "5e a dismissal wins over resolved" "CASE:$H5S|dismissed|" "$(case_cmd "$R5S" list)"
# A dismissal WITHOUT an outcome keeps the accepted `reviewed: resolved`
# outcome on the item: the dismissal must still win.
R5T="$(new_repo r5t)"
ID5T="$(make_record "$R5T" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID5T"
H5T="$(case_hex "$R5T")"
RID5T="$(review_id "$R5T")"
case_cmd "$R5T" review "$H5T" --outcome resolved --item "$RID5T" \
    --expect-rev "$(rev_of "$R5T" "$RID5T")" >/dev/null
wr "$R5T" dismiss "$RID5T" --expect-rev "$(rev_of "$R5T" "$RID5T")" >/dev/null
assert_contains "5e premise: the dismissed item keeps its accepted outcome" "|reviewed: resolved|" \
    "$(items "$R5T" | grep "^ITEM:$RID5T|")"
assert_contains "5e a dismissal without an outcome still wins" "CASE:$H5T|dismissed|" "$(case_cmd "$R5T" list)"

# --- 6. idempotency ----------------------------------------------------------------
echo "--- 6. --force and concurrent harvests"
harvest record "$ID5" --force
assert_contains "6 --force: review exists" "HARVEST_REVIEW:$ID5|$RID5|exists|" "$OUT"
assert_eq "6 still one review item" "1" "$(reviews "$R5")"
assert_eq "6 the done review stays done" "done" "$(state_of "$R5" "$RID5")"
R6="$(new_repo r6)"
ID6A="$(make_record "$R6" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
ID6B="$(make_record "$R6" agent-pick-89 89 pick "$FIX/truncated_banner.txt")"
FIFO="$TMP/pause.fifo"
mkfifo "$FIFO"
AITASK_SITREP_HARVEST_PAUSE_FIFO="$FIFO" "$HV" record "$ID6A" >"$TMP/c6a.out" 2>&1 &
P6A=$!; BG_PIDS+=("$P6A")
for _ in $(seq 1 100); do [[ -e "$FIFO.reached" ]] && break; sleep 0.1; done
assert_file_exists "6 the first harvest holds the mutex" "$FIFO.reached"
"$HV" record "$ID6B" >"$TMP/c6b.out" 2>&1 &
P6B=$!; BG_PIDS+=("$P6B")
sleep 1
printf 'go\n' > "$FIFO"
wait "$P6A"; wait "$P6B"
assert_contains "6 the first one adds the review" "|added|case=" "$(cat "$TMP/c6a.out")"
assert_contains "6 the second one finds it" "|exists|case=" "$(cat "$TMP/c6b.out")"
assert_eq "6 concurrent pair: one review item" "1" "$(reviews "$R6")"

# --- 7. fault injection ------------------------------------------------------------
echo "--- 7. a failed case write withholds the receipt"
for point in case:raw case:files case:item receipt; do
    R7="$(new_repo "r7_${point/:/_}")"
    ID7="$(make_record "$R7" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
    RC=0; OUT="$(AITASK_SITREP_HARVEST_FAULT="$point" "$HV" record "$ID7" 2>&1)" || RC=$?
    assert_eq "7 $point: exit 1" "1" "$RC"
    assert_contains "7 $point: HARVEST_FAILED" "HARVEST_FAILED:$ID7|fault:$point" "$OUT"
    assert_file_not_exists "7 $point: no receipt" "$(cap_of "$ID7").harvested"
    RC=0; "$SESS" drop "$ID7" >/dev/null 2>&1 || RC=$?
    assert_eq "7 $point: drop refused" "9" "$RC"
    rm -f "$AITASKS_FROZEN_DIR/$ID7/capture.ansi"
    assert_contains "7 $point: purge keeps the text" "KEPT:$ID7|unharvested_text" "$(purge_obs "$R7")"
    harvest record "$ID7"
    assert_eq "7 $point: retry exit 0" "0" "$RC"
    assert_eq "7 $point: retry completes one review item" "1" "$(reviews "$R7")"
    assert_contains "7 $point: retry certifies" "cert=2" "$(cat "$(cap_of "$ID7").harvested" 2>/dev/null)"
done

# --- 8. the parser-improvement loop -------------------------------------------------
echo "--- 8. old parser misses, replay recovers, export -> fixture"
OLD="$TMP/oldcopy"
mkdir -p "$OLD"
cp -r "$PROJECT_DIR/.aitask-scripts" "$OLD/"
sed -i 's/^ACCEPT_JOINED_BANNER = True$/ACCEPT_JOINED_BANNER = False/; s/^PARSER_REV = 2$/PARSER_REV = 1/' \
    "$OLD/.aitask-scripts/lib/sitrep_harvest.py"
# Counted, not assert_contains over the whole file: under pipefail a large
# haystack makes `printf | grep -q` fail with SIGPIPE once grep exits early.
assert_eq "8 premise: the copy has the pre-fix grammar" "2" \
    "$(grep -cE '^(ACCEPT_JOINED_BANNER = False|PARSER_REV = 1)$' "$OLD/.aitask-scripts/lib/sitrep_harvest.py")"
R8="$(new_repo r8)"
ID8="$(make_record "$R8" agent-pick-61 61 pick "$FIX/joined_banner.txt")"
RC=0; OUT="$("$OLD/.aitask-scripts/aitask_sitrep_harvest.sh" record "$ID8" 2>&1)" || RC=$?
assert_eq "8 old parser: exit 0" "0" "$RC"
assert_contains "8 old parser: preserved for review" "banner_unparsed" "$(grep '^HARVEST_REVIEW:' <<<"$OUT")"
assert_not_contains "8 old parser: the follow-up was missed" "|t62|" "$(items "$R8")"
H8="$(case_hex "$R8")"
RID8="$(review_id "$R8")"
TODO_BEFORE="$(sha_of "$(store_of "$R8")/todo.md")"
OUT="$(case_cmd "$R8" replay "$H8")"
assert_contains "8 replay: reliable now" "REPLAY:$H8|parser=2|class=reliable|" "$OUT"
assert_contains "8 replay: the missed follow-up is new" "REPLAY_ITEM:task|t62|new" "$OUT"
assert_contains "8 replay: the reason is resolved" "REPLAY_RESOLVED:banner_unparsed" "$OUT"
assert_eq "8 a dry replay writes nothing" "$TODO_BEFORE" "$(sha_of "$(store_of "$R8")/todo.md")"
OUT="$(case_cmd "$R8" replay "$H8" --apply)"
assert_contains "8 replay --apply: applied" "REPLAY_APPLIED:cases/" "$OUT"
assert_contains "8 replay --apply: the follow-up is now an item" "|t62|" "$(items "$R8")"
SHOW="$(case_cmd "$R8" show "$H8")"
assert_contains "8 the old analysis is kept" "|parser=1|class=review" "$SHOW"
assert_contains "8 the replay analysis is added" "origin=replay|parser=2|class=reliable" "$SHOW"
assert_eq "8 the review item is untouched" "open" "$(state_of "$R8" "$RID8")"
FX="$TMP/fixture_joined"
OUT="$(case_cmd "$R8" export "$H8" --out "$FX")"
assert_contains "8 exported" "EXPORTED:$FX" "$OUT"
assert_contains "8 export reminds to redact" "REDACT:" "$OUT"
assert_eq "8 export keeps the input verbatim" "$(sha_of "$FIX/joined_banner.txt")" "$(sha_of "$FX/input.txt")"
RC=0; OUT="$(case_cmd "$R8" export "$H8" --out "$FX" 2>&1)" || RC=$?
assert_contains "8 export never overwrites" "EXPORT_REFUSED:$H8|exists:" "$OUT"
RC=0; OUT="$("$HV" case check-fixture "$FX")" || RC=$?
assert_contains "8 the fixture passes with the current parser" "FIXTURE_OK:" "$OUT"
RC=0; OUT="$("$OLD/.aitask-scripts/aitask_sitrep_harvest.sh" case check-fixture "$FX")" || RC=$?
assert_eq "8 the fixture fails with the old parser (exit 1)" "1" "$RC"
assert_contains "8 the failure names the class" "FIXTURE_FAIL:" "$OUT"
OUT="$(case_cmd "$R8" review "$H8" --outcome resolved --parser 2 \
    --fixture tests/fixtures/sitrep_harvest/corpus/joined_banner --item "$RID8" \
    --expect-rev "$(rev_of "$R8" "$RID8")")"
assert_contains "8 resolved review closes the item" "STATE:$RID8|done|" "$OUT"
assert_contains "8 listed resolved" "CASE:$H8|resolved|" "$(case_cmd "$R8" list)"
R8U="$(new_repo r8u)"
ID8U="$(make_record "$R8U" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
harvest record "$ID8U"
RC=0; OUT="$(case_cmd "$R8U" export "$(case_hex "$R8U")" --out "$TMP/fx_unresolved" 2>&1)" || RC=$?
assert_contains "8 an unresolved case is not exported" "EXPORT_REFUSED:" "$OUT"
assert_dir_not_exists "8 nothing written for it" "$TMP/fx_unresolved"

# --- 9. cap -------------------------------------------------------------------------
echo "--- 9. a raw input over the cap fails closed"
R9="$(new_repo r9)"
ID9="$(make_record "$R9" agent-pick-88 88 pick "$FIX/truncated_banner.txt")"
RC=0; OUT="$(AITASK_SITREP_RAW_MAX=100 "$HV" record "$ID9" 2>&1)" || RC=$?
assert_eq "9 exit 1" "1" "$RC"
assert_contains "9 case_input_too_large" "HARVEST_FAILED:$ID9|case_input_too_large" "$OUT"
assert_file_not_exists "9 no receipt" "$(cap_of "$ID9").harvested"

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
fi
[[ "$FAIL" -eq 0 ]]
