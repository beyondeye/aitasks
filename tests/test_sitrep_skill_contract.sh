#!/usr/bin/env bash
# test_sitrep_skill_contract.sh - the sitrep skill's documented commands against
# the real helpers (t2175_4). The render itself is test_skill_render_aitask_sitrep.sh.
#
#   a  every ./.aitask-scripts/<helper> the rendered skill names exists and has
#      exactly one entry in each of the 5 code-agent permission files
#   b  every `aitask_sitrep_todo.sh <verb>` / `aitask_sitrep.sh <verb>` the skill
#      uses is a verb of that helper's header
#   c  end to end FROM A HARVESTED TRIAGE ITEM, in a scratch repository with a
#      scratch HOME and session store: `ait sitrep triage` reports the trail
#      handle as unwatched (the triage question's own pointer does not count);
#      the skill's example blocks, filled in, are accepted by the writer; the
#      trail watch is then reported watched, and refresh selects it while open;
#      after a dismissal (the writer call the sitrep TUI's `x` makes; the skill
#      no longer dismisses) it stays watched and refresh no longer selects it; a
#      second triage naming the same handle is told it is watched; a non-watch
#      item carrying a trail pointer does not count
#   c2 two wrap-ups naming one trail, BOTH pending before the first write:
#      `triage --open` coalesces them into ONE BATCH_TRAIL_UNWATCHED line, and
#      the documented watch (related to both) covers both afterwards
#   e  an unparsed-output review (t2175_6): triage reports REVIEW_CASE, the
#      case reads back, and the case-review example closes the item
#   d  the advisory sentences are present, and every paragraph naming a
#      repository-writing action is a prohibition
#   r  request parity (t2211_5): every `>` code the sitrep TUI types
#      (AGENT_REQUESTS) is listed in the skill's "Requests from the sitrep TUI"
#      section and has its own capability heading (### `>code`), and the
#      section lists no code the TUI does not type
#   m  each of a, b, c (trail source), d and r is red against a broken copy
#
# Bodies run in the main shell, so the plain counters are enough.
# Run: bash tests/test_sitrep_skill_contract.sh

set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

SCRIPTS="$PROJECT_DIR/.aitask-scripts"
HV="$SCRIPTS/aitask_sitrep_harvest.sh"
WR="$SCRIPTS/aitask_sitrep_todo.sh"
RF="$SCRIPTS/aitask_sitrep_refresh.sh"
SR="$SCRIPTS/aitask_sitrep.sh"
TEMPLATE="$PROJECT_DIR/.claude/skills/aitask-sitrep/SKILL.md.j2"
PERMISSION_FILES=(
    "$PROJECT_DIR/.claude/settings.local.json"
    "$PROJECT_DIR/.codex/rules/default.rules"
    "$PROJECT_DIR/seed/claude_settings.local.json"
    "$PROJECT_DIR/seed/codex_rules.default.rules"
    "$PROJECT_DIR/seed/opencode_config.seed.json"
)

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_sitrep_contract_XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
trap 'rm -rf "$TMP"' EXIT

# The interpreter BEFORE switching HOME: the python wrapper finds its venv there.
AIT_PYTHON="$(source "$SCRIPTS/lib/python_resolve.sh" && require_ait_python)"
export AIT_PYTHON
if ! "$AIT_PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv. Run 'ait setup' first."
    exit 0
fi
SKILL="$TMP/SKILL.md"
"$AIT_PYTHON" "$SCRIPTS/lib/skill_template.py" "$TEMPLATE" \
    "$PROJECT_DIR/aitasks/metadata/profiles/default.yaml" claude > "$SKILL"

export HOME="$TMP/home"
mkdir -p "$HOME/.config/aitasks"
export AITASKS_AGENT_SESSIONS_FILE="$HOME/.config/aitasks/agent_sessions.json"
export AITASKS_FROZEN_DIR="$TMP/frozen"
export AITASKS_PROJECTS_INDEX="$TMP/projects.yaml"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
unset TMUX TMUX_PANE AITASK_SITREP_DIR AITASK_SITREP_PAUSE_FIFO AITASK_SITREP_NOW \
      AITASK_SITREP_HARVEST_RUN_ID AITASK_SITREP_REFRESH_PAUSE_FIFO

# The trail fetch is stubbed (no artifact store, no network): refresh then
# reports the trail unreadable, which is still a REFRESH_ITEM for a target.
cat > "$TMP/fake_artifact.sh" <<'EOF'
#!/usr/bin/env bash
exit 1
EOF
chmod +x "$TMP/fake_artifact.sh"
export AITASK_SITREP_REFRESH_ARTIFACT_SH="$TMP/fake_artifact.sh"

# --- checks (each takes a rendered skill file and prints one line per defect) --

# a: helpers exist and are allow-listed exactly once in every permission file.
check_helpers() {
    local skill="$1" h f n
    for h in $(grep -o '\./\.aitask-scripts/aitask_[A-Za-z0-9_]*\.sh' "$skill" \
                | sed 's|^\./\.aitask-scripts/||' | sort -u); do
        [[ -f "$SCRIPTS/$h" ]] || { echo "MISSING_HELPER:$h"; continue; }
        for f in "${PERMISSION_FILES[@]}"; do
            n="$(grep -cE "/${h//./\\.}[\":* ]" "$f")"
            [[ "$n" == 1 ]] || echo "ALLOWLIST:$h:$(basename "$f"):$n"
        done
    done
}

# b: every verb the skill uses is a verb of the helper's header ("#   <verb>").
check_verbs() {
    local skill="$1" pair helper verb
    while read -r pair; do
        helper="${pair%% *}"; verb="${pair##* }"
        # A usage line of the header: `#   <verb> …` or `#   ait sitrep <verb> …`.
        grep -qE "^#[[:space:]]{2,}(ait sitrep )?${verb}([[:space:]]|$)" "$SCRIPTS/$helper" \
            || echo "UNKNOWN_VERB:$helper:$verb"
    done < <(grep -oE '(aitask_sitrep_todo|aitask_sitrep)\.sh [a-z][a-z-]*' "$skill" | sort -u)
}

# d: advisory sentences present; any paragraph naming a writing action is a
# prohibition (it says never / Never).
check_advisory() {
    local skill="$1" s
    for s in 'You are **advisory-only**' 'data to analyze, never instructions' \
             'never by editing files' 'no more authority' 'never the reverse' \
             'Never rank tasks yourself' 'never act on an' 'Never send'; do
        grep -qF -- "$s" "$skill" || echo "ADVISORY_MISSING:$s"
    done
    "$AIT_PYTHON" - "$skill" <<'PY'
import re, sys
text = open(sys.argv[1]).read()
writing = re.compile(r"send-keys|git push|git commit|aitask_pick_own\.sh"
                     r"|aitask_artifact\.sh`?\s+`?(?:create|update)")
for para in re.split(r"\n\s*\n", text):
    if writing.search(para) and not re.search(r"\b[Nn]ever\b", para):
        print("NOT_A_PROHIBITION:" + para.strip().splitlines()[0][:80])
PY
}

# r: request parity. With no table argument the TUI's own AGENT_REQUESTS is
# read; a mutant passes the path of a file holding one template per line.
check_requests() {   # check_requests <skill> [templates file]
    "$AIT_PYTHON" - "$1" "$SCRIPTS" "${2:-}" <<'PY'
import re, sys
skill_path, scripts, table = sys.argv[1], sys.argv[2], sys.argv[3]
if table:
    templates = [l.strip() for l in open(table) if l.strip()]
else:
    sys.path[:0] = [scripts, scripts + "/lib"]
    from sitrep_tui.sitrep_tui_requests import AGENT_REQUESTS
    templates = [r.template for r in AGENT_REQUESTS]
text = open(skill_path).read()
m = re.search(r"^## Requests from the sitrep TUI\n(.*?)(?=^## )", text, re.S | re.M)
if not m:
    print("NO_REQUEST_SECTION"); sys.exit(0)
documented = {span.split()[0] for span in re.findall(r"`(>[^`]*)`", m.group(1))}
codes = []
for t in templates:
    code = t.split()[0]
    if code not in codes:
        codes.append(code)
for code in codes:
    if code not in documented:
        print("UNDOCUMENTED_REQUEST:" + code)
    if not re.search(r"^### `" + re.escape(code) + r"[` ]", text, re.M):
        print("NO_CAPABILITY:" + code)
for code in sorted(documented - set(codes)):
    print("STALE_DOC_CODE:" + code)
PY
}

# Fill one example block of the rendered skill: placeholders from the
# environment (SX_<NAME>), helpers by absolute path. Prints the command, or a
# PLACEHOLDER_LEFT line when a placeholder has no value.
example() {   # example <skill file> <name>
    "$AIT_PYTHON" - "$1" "$2" "$SCRIPTS" <<'PY'
import os, re, sys
text = open(sys.argv[1]).read()
m = re.search(r"<!-- sitrep-example:%s -->\n```bash\n(.*?)```\n<!-- /sitrep-example -->"
              % re.escape(sys.argv[2]), text, re.S)
if not m:
    print("NO_EXAMPLE:" + sys.argv[2]); sys.exit(0)
cmd = m.group(1).replace("./.aitask-scripts/", sys.argv[3] + "/")
def fill(mm):
    return os.environ.get("SX_" + mm.group(1), mm.group(0))
cmd = re.sub(r"<([A-Z_]+)>", fill, cmd)
left = re.findall(r"<[A-Z_]+>", cmd)
print("PLACEHOLDER_LEFT:" + ",".join(left) if left else cmd, end="")
PY
}

run_example() {   # run_example <skill> <name> -> OUT, RC (cwd = $S)
    local cmd
    cmd="$(example "$1" "$2")"
    if [[ "$cmd" == PLACEHOLDER_LEFT:* || "$cmd" == NO_EXAMPLE:* ]]; then
        OUT="$cmd"; RC=99; return
    fi
    RC=0
    OUT="$(cd "$S" && bash -c "$cmd" 2>"$TMP/err")" || RC=$?
}

new_repo() {
    local d="$TMP/$1"
    mkdir -p "$d"
    git -C "$d" init -q
    git -C "$d" commit -q --allow-empty -m init
    printf '%s' "$d"
}

pipe_wrapup() {   # pipe_wrapup <task> <name> <prose>  (cwd = $S)
    printf '%s\n\n```text\n✔ aitask workflow complete — t%s %s\n  outcome: archived (commit 9f8e7d6c5) · pushed: no\n  follow-ups created: none\n```\n' \
        "$3" "$1" "$2" | (cd "$S" && "$HV" banner --task "$1" --skill pick) >/dev/null 2>&1
}

triage_of() { (cd "$S" && "$SR" triage "$1" 2>/dev/null); }
last_question() {
    (cd "$S" && "$WR" list) | awk -F'|' '$3=="question" {id=$1} END {sub(/^ITEM:/,"",id); print id}'
}
field() { printf '%s\n' "$1" | sed -n "s/^$2://p" | head -1; }
rev_of() { (cd "$S" && "$WR" list) | awk -F'|' -v c="ITEM:$1" '$1==c {print $2}'; }

# =============================================================================
echo "=== a: helpers exist and are allow-listed ==="
out="$(check_helpers "$SKILL")"
assert_eq "every named helper is allow-listed once per permission file" "" "$out"
assert_contains "the skill names the writer" "aitask_sitrep_todo.sh" "$(cat "$SKILL")"
# The sitrep TUI owns harvest and refresh (t2211_5); their allow-list entries
# stay, contract (a) only checks the helpers the skill names.
assert_not_contains "the skill no longer runs the harvest" "aitask_sitrep_harvest.sh" "$(cat "$SKILL")"
assert_not_contains "the skill no longer runs the refresh" "aitask_sitrep_refresh.sh" "$(cat "$SKILL")"
assert_contains "the skill names ait sitrep's helper" "aitask_sitrep.sh triage" "$(cat "$SKILL")"

echo "=== b: verbs exist ==="
assert_eq "every verb the skill uses is in its helper's header" "" "$(check_verbs "$SKILL")"

echo "=== r: the TUI's requests are the skill's codes ==="
assert_eq "every AGENT_REQUESTS code is documented, with its capability" "" \
    "$(check_requests "$SKILL")"

echo "=== d: advisory prose ==="
assert_eq "advisory sentences present, writing actions only as prohibitions" "" \
    "$(check_advisory "$SKILL")"

# =============================================================================
echo "=== c: from a harvested triage item through refresh selection ==="
S="$(new_repo s)"
HANDLE="art:trail-demo-plan"
pipe_wrapup 42 demo_task "t42 is done. Push main when ready; the plan lives in trail $HANDLE."
T1="$(last_question)"
assert_contains "the wrap-up became a triage question" "c" "$T1"
TRI="$(triage_of "$T1")"
assert_eq "one unwatched handle (the question's own pointer does not count)" \
    "TRAIL_UNWATCHED:$HANDLE" "$(printf '%s\n' "$TRI" | grep '^TRAIL_')"
assert_contains "the passage comes first" "PASSAGE:sources/" "$(printf '%s\n' "$TRI" | sed -n 2p)"
assert_contains "the banner file is classified" "BANNER:sources/" "$TRI"
assert_contains "identity keys are classified" "KEY:sources/" "$TRI"
assert_contains "the commit is copied" "COMMIT:9f8e7d6c5" "$TRI"
assert_contains "the origin task is copied" "task=t42" "$(field "$TRI" ORIGIN)"
assert_contains "final line names the item, its state and rev" "TRIAGE:$T1|open|" \
    "$(printf '%s\n' "$TRI" | tail -1)"

export SX_BRANCH=main SX_COMMIT=9f8e7d6c5 SX_TASK=t42 SX_DATE=2026-11-04 SX_THEME=demo
export SX_PASSAGE; SX_PASSAGE="$(field "$TRI" PASSAGE)"
export SX_TASK_FILE=aitasks/archived/t42_demo_task.md SX_TRIAGE="$T1" SX_TRIAGES="$T1" SX_HANDLE="$HANDLE"
run_example "$SKILL" push
assert_eq "push example accepted" "0" "$RC"
P1="$(printf '%s' "$OUT" | sed -n 's/^ADDED:\(c[0-9]*\)$/\1/p')"
assert_contains "push example -> ADDED" "ADDED:c" "$OUT"
run_example "$SKILL" trail-watch
assert_eq "trail-watch example accepted" "0" "$RC"
W1="$(printf '%s' "$OUT" | sed -n 's/^ADDED:\(c[0-9]*\)$/\1/p')"
assert_contains "trail-watch example -> ADDED" "ADDED:c" "$OUT"

TRI="$(triage_of "$T1")"
assert_eq "the handle is now watched by the new watch" "TRAIL_WATCHED:$HANDLE|$W1|open" \
    "$(printf '%s\n' "$TRI" | grep '^TRAIL_')"
assert_contains "the push item is reported as derived" "DERIVED:$P1|action|open|" "$TRI"
assert_contains "the watch is reported as derived" "DERIVED:$W1|watch|open|" "$TRI"

export SX_NEW_IDS="$P1, $W1" SX_REV; SX_REV="$(rev_of "$T1")"
run_example "$SKILL" close
assert_contains "close example closes the triage item" "STATE:$T1|done|" "$OUT"

RC=0; OUT="$(cd "$S" && "$RF" --root . --dry-run 2>&1)" || RC=$?
assert_eq "refresh dry-run: exit 0" "0" "$RC"
assert_contains "refresh selects the open trail watch" "REFRESH_ITEM:$W1|watch|" "$OUT"
assert_contains "refresh selects the push reminder" "REFRESH_ITEM:$P1|action|" "$OUT"
assert_not_contains "the closed triage question is no target" "REFRESH_ITEM:$T1|" "$OUT"

# The dismissal the sitrep TUI's `x` makes (the skill no longer dismisses).
OUT="$(cd "$S" && "$WR" dismiss "$W1" --outcome "user: not tracking this trail" \
        --expect-rev "$(rev_of "$W1")" 2>&1)"
assert_contains "the writer dismisses the watch" "STATE:$W1|dismissed|" "$OUT"
assert_eq "a dismissed watch still counts as watching the handle" \
    "TRAIL_WATCHED:$HANDLE|$W1|dismissed" "$(triage_of "$T1" | grep '^TRAIL_')"
OUT="$(cd "$S" && "$RF" --root . --dry-run 2>&1)"
assert_not_contains "refresh no longer selects the dismissed watch" "REFRESH_ITEM:$W1|" "$OUT"

pipe_wrapup 43 other_task "t43 also points at $HANDLE for its next wave."
T2="$(last_question)"
assert_eq "a second triage naming the handle is told it is watched" \
    "TRAIL_WATCHED:$HANDLE|$W1|dismissed" "$(triage_of "$T2" | grep '^TRAIL_')"

# A non-watch item carrying a trail pointer is no watch.
printf -- '- background: An action that happens to cite a trail.\n- origin: agent=sitrep date=2026-11-04\n- sources:\n  - trail: art:trail-other\n' \
    | (cd "$S" && "$WR" add --kind action --title "Not a watch" --derived agent \
        --context-file - >/dev/null)
pipe_wrapup 44 third_task "t44 continues art:trail-other."
T3="$(last_question)"
assert_eq "a non-watch item does not count as watching" "TRAIL_UNWATCHED:art:trail-other" \
    "$(triage_of "$T3" | grep '^TRAIL_')"

export SX_SITUATION="Demo work: $P1 waits on a push of main."
run_example "$SKILL" situation
assert_eq "situation example" "SITUATION:demo|set" "$OUT"
export SX_ITEMS="$P1" SX_QUESTION="Is main pushed?" SX_ANSWER="No: $P1 is open (read from its push: ref)."
run_example "$SKILL" qa
assert_contains "qa example" "QA:" "$OUT"

RC=0; OUT="$(triage_of "$W1")" || RC=$?
RC=0; (cd "$S" && "$SR" triage "$W1" >/dev/null 2>&1) || RC=$?
assert_eq "triage on a watch item: exit 2" "2" "$RC"
assert_eq "... NOT_TRIAGE" "NOT_TRIAGE:$W1" "$(cd "$S" && "$SR" triage "$W1" 2>/dev/null)"
assert_eq "triage on a missing item" "NOT_FOUND:c999" "$(cd "$S" && "$SR" triage c999 2>/dev/null)"
assert_eq "the store still parses" "VERIFIED:todo" \
    "$("$AIT_PYTHON" "$SCRIPTS/lib/sitrep_todo.py" verify todo "$S/.aitask-sitrep/todo.md")"

# =============================================================================
echo "=== c2: two pending wrap-ups naming one trail -> one watch ==="
S="$(new_repo s_batch)"
BH="art:trail-batch-demo"
pipe_wrapup 61 first_task "t61 is done; its follow-up waves are in $BH."
TA="$(last_question)"
pipe_wrapup 62 second_task "t62 is done; also see $BH for what lands next."
TB="$(last_question)"
assert_eq "two distinct triage items" "yes" "$([[ -n "$TA" && "$TA" != "$TB" ]] && echo yes || echo no)"
ALL="$(cd "$S" && "$SR" triage --open 2>/dev/null)"
assert_eq "each block still reports its own facts" "2" "$(grep -c "^TRAIL_UNWATCHED:$BH\$" <<<"$ALL")"
assert_eq "ONE batch line for the shared trail, naming both items" \
    "BATCH_TRAIL_UNWATCHED:$BH|$TA,$TB" "$(grep '^BATCH_TRAIL_UNWATCHED:' <<<"$ALL")"
assert_eq "a block ends with its TRIAGE line" "2" "$(grep -c '^TRIAGE:' <<<"$ALL")"
export SX_HANDLE="$BH" SX_TRIAGES="$TA, $TB" SX_TASK=t61 SX_THEME=batch SX_PASSAGE
SX_PASSAGE="$(sed -n 's/^PASSAGE://p' <<<"$ALL" | head -1)"
run_example "$SKILL" trail-watch
assert_contains "the one shared watch is accepted" "ADDED:c" "$OUT"
WB="$(printf '%s' "$OUT" | sed -n 's/^ADDED:\(c[0-9]*\)$/\1/p')"
ALL="$(cd "$S" && "$SR" triage --open 2>/dev/null)"
assert_not_contains "no batch line once the watch exists" "BATCH_TRAIL_UNWATCHED:" "$ALL"
assert_eq "both items now see the one watch" "2" "$(grep -c "^TRAIL_WATCHED:$BH|$WB|open\$" <<<"$ALL")"
assert_eq "the watch is derived for both items" "2" "$(grep -c "^DERIVED:$WB|watch|open|" <<<"$ALL")"
assert_eq "exactly one watch item in the store" "1" \
    "$( (cd "$S" && "$WR" list) | awk -F'|' '$3=="watch"' | grep -c .)"
for t in "$TA" "$TB"; do
    (cd "$S" && "$WR" set-state "$t" "done" --outcome "triaged: $WB" --expect-rev "$(rev_of "$t")") >/dev/null
done
assert_eq "nothing left to triage" "NO_TRIAGE" "$(cd "$S" && "$SR" triage --open 2>/dev/null)"
RC=0; (cd "$S" && "$SR" triage >/dev/null 2>&1) || RC=$?
assert_eq "triage with neither an id nor --open: exit 2" "2" "$RC"

# =============================================================================
echo "=== e: an unparsed-output review, from the harvest to the review record ==="
# t2175_6: a cut-off banner is preserved as a review case; `triage --open`
# reports it (REVIEW_CASE), `case show` / `case read` read it, and the skill's
# case-review example records the review and closes the item.
S="$(new_repo s_review)"
"$HV" capture --root "$S" --agent agent-pick-88 --task 88 --operation pick \
    < "$PROJECT_DIR/tests/fixtures/sitrep_harvest/truncated_banner.txt" >/dev/null 2>&1
ALL="$(cd "$S" && "$SR" triage --open 2>/dev/null)"
RV="$(grep '^REVIEW_CASE:' <<<"$ALL")"
assert_contains "the review item is reported with its case and codes" "|banner_incomplete" "$RV"
assert_contains "the case origin is classified" "CASE:sources/" "$ALL"
assert_contains "the analysis is classified" "ANALYSIS:sources/" "$ALL"
CASEHEX="$(sed 's/^REVIEW_CASE:\([0-9a-f]*\)|.*/\1/' <<<"$RV")"
SHOWN="$(cd "$S" && "$SR" case show "$CASEHEX" 2>/dev/null)"
assert_contains "case show names a reason with its line range" "REASON:banner_incomplete|L" "$SHOWN"
assert_contains "case read returns the raw input" "aitask workflow complete" \
    "$(cd "$S" && "$SR" case read "$CASEHEX" 2>/dev/null)"
TR="$(sed -n 's/^TRIAGE:\(c[0-9]*\)|.*/\1/p' <<<"$ALL" | tail -1)"
export SX_CASE="$CASEHEX" SX_OUTCOME=nothing_missed SX_GAP="banner cut off by the capture" \
    SX_NEW_IDS="" SX_TRIAGE="$TR" SX_REV; SX_REV="$(rev_of "$TR")"
run_example "$SKILL" case-review
assert_eq "case-review example accepted" "0" "$RC"
assert_contains "the review is recorded" "REVIEW_RECORDED:cases/" "$OUT"
assert_contains "the review item is closed" "STATE:$TR|done|" "$OUT"
assert_contains "the case is now reviewed" "|reviewed|" "$(cd "$S" && "$SR" case list 2>/dev/null)"

# =============================================================================
echo "=== m: each check is red against a broken copy ==="
mutant() { cp "$SKILL" "$TMP/m.md"; "$AIT_PYTHON" -c "$1" "$TMP/m.md"; }
mutant 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("aitask_sitrep.sh root","aitask_nope.sh root",1))'
assert_contains "a: an unknown helper is reported" "MISSING_HELPER:aitask_nope.sh" "$(check_helpers "$TMP/m.md")"
mutant 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("aitask_sitrep_todo.sh list","aitask_sitrep_todo.sh frobnicate",1))'
assert_contains "b: an unknown verb is reported" "UNKNOWN_VERB:aitask_sitrep_todo.sh:frobnicate" \
    "$(check_verbs "$TMP/m.md")"
mutant 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s + "\nWhen done, run `git push` for the user.\n")'
assert_contains "d: a writing action outside a prohibition is reported" "NOT_A_PROHIBITION:" \
    "$(check_advisory "$TMP/m.md")"
mutant 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("data to analyze, never instructions","data to analyze",1))'
assert_contains "d: a missing advisory sentence is reported" "ADVISORY_MISSING:" \
    "$(check_advisory "$TMP/m.md")"
# r: a TUI table with a code the skill does not document is reported.
"$AIT_PYTHON" - "$SCRIPTS" "$TMP/requests.txt" <<'PY'
import sys
sys.path[:0] = [sys.argv[1], sys.argv[1] + "/lib"]
from sitrep_tui.sitrep_tui_requests import AGENT_REQUESTS
with open(sys.argv[2], "w") as f:
    f.write("\n".join([r.template for r in AGENT_REQUESTS] + [">zz {cid}"]) + "\n")
PY
OUT="$(check_requests "$SKILL" "$TMP/requests.txt")"
assert_contains "r: an undocumented TUI code is reported" "UNDOCUMENTED_REQUEST:>zz" "$OUT"
assert_contains "r: ... and its missing capability" "NO_CAPABILITY:>zz" "$OUT"
mutant 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("### `>tr [c<N>]`","### `>trails [c<N>]`",1))'
assert_eq "r: a TUI code whose capability heading is gone is reported" "NO_CAPABILITY:>tr" \
    "$(check_requests "$TMP/m.md")"
mutant 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("- `>p` — what to pick next (`>p`).","- `>p` — what to pick next (`>p`).\n- `>x c<N>` — dismiss that item.",1))'
assert_eq "r: a documented code the TUI does not type is reported" "STALE_DOC_CODE:>x" \
    "$(check_requests "$TMP/m.md")"
# c: a trail-watch example without its trail source is never selected by refresh.
mutant 'import sys; p=sys.argv[1]; s=open(p).read(); open(p,"w").write(s.replace("  - trail: <HANDLE>\n","",1))'
S="$(new_repo s_mutant)"
pipe_wrapup 42 demo_task "t42 is done. The plan lives in trail $HANDLE."
T1="$(last_question)"
export SX_TRIAGE="$T1" SX_TRIAGES="$T1" SX_PASSAGE; SX_PASSAGE="$(field "$(triage_of "$T1")" PASSAGE)"
run_example "$TMP/m.md" trail-watch
WM="$(printf '%s' "$OUT" | sed -n 's/^ADDED:\(c[0-9]*\)$/\1/p')"
assert_eq "c: the mutant's watch was really added" "yes" \
    "$([[ "$WM" =~ ^c[0-9]+$ ]] && echo yes || echo no)"
OUT="$(cd "$S" && "$RF" --root . --dry-run 2>&1)"
assert_not_contains "c: without its trail source the watch is not refreshed" \
    "REFRESH_ITEM:$WM|" "$OUT"
assert_eq "c: ... and triage keeps reporting the handle unwatched" \
    "TRAIL_UNWATCHED:$HANDLE" "$(triage_of "$T1" | grep '^TRAIL_')"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
