#!/usr/bin/env bash
# End-to-end tests for aitask_sitrep_refresh.sh (t2175_3).
#
# Real refresh (parent + worker process group), real store writer, real git,
# real archive bundles -- under a scratch HOME / project registry, so nothing
# reaches the real ~/.config.
#
#   1   a follow-up lands: Ready -> Implementing -> archived Done; done is final
#   2   a harvest-unknown item whose task now exists -> open
#   3   fold: a live Folded file, then a deleted one found via folded_tasks
#   4   push: open "1 ahead", done after the push (no refresh-side fetch)
#   5   unreachable repos -> unknown, never done
#   6   concurrent refresh vs agent writes (dismiss / edit -> stale) and two refreshes
#   6b  a context swap during a paused refresh -> stale; unchanged -> applies
#   7   non-targets byte-identical; --dry-run writes nothing
#   8   no store, damaged store, '..' root
#   9   --budget 0 -> REFRESH_FAILED:deadline
#   10  slow checks + a slow writer finish inside the caller contract; lock busy
#   11  a stalled real archive (zstd) / git helper is killed with its group
#   12  progress across bounded runs: no starvation behind expensive items
#   13  interrupted before the first VERDICT, with concurrent edits
#   14  the worker dies with its parent (an external kill of the run)
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

RF="$PROJECT_DIR/.aitask-scripts/aitask_sitrep_refresh.sh"
WR="$PROJECT_DIR/.aitask-scripts/aitask_sitrep_todo.sh"
TRAIL_DOC="$PROJECT_DIR/aidocs/implementation_trail_examples/gate_framework.json"

TMP="$(mktemp -d "${TMPDIR:-/tmp}/ait_refresh_XXXXXX")"
TMP="$(cd "$TMP" && pwd -P)"
MARK="sitrep_refresh_test_$$"
BG_PIDS=()
cleanup() {
    local p
    for p in "${BG_PIDS[@]:-}"; do
        [[ -n "$p" ]] && kill -9 "$p" 2>/dev/null
    done
    pkill -9 -f "$MARK" 2>/dev/null
    exec 7>&- 2>/dev/null
    chmod -R u+w "$TMP" 2>/dev/null
    rm -rf "$TMP"
}
trap cleanup EXIT

AIT_PYTHON="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" && require_ait_python)"
export AIT_PYTHON
export HOME="$TMP/home"
mkdir -p "$HOME/.config/aitasks"
export AITASKS_PROJECTS_INDEX="$TMP/projects.yaml"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"
export AITASK_SITREP_NOW="2026-11-03T10:00:00Z"
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
export GIT_CONFIG_NOSYSTEM=1
unset TMUX TMUX_PANE AITASK_SITREP_DIR AITASK_SITREP_PAUSE_FIFO AITASK_SITREP_LOCK_TIMEOUT \
      AITASK_SITREP_REFRESH_PAUSE_FIFO AITASK_SITREP_REFRESH_ARTIFACT_SH \
      AITASK_SITREP_REFRESH_BATCH_LOG AITASK_SITREP_REFRESH_BUDGET TASK_DIR

FIFO="$TMP/pause.fifo"
REAL_GIT="$(command -v git)"
REAL_ZSTD="$(command -v zstd || true)"

# ONLY="1 6b 13" runs a subset (the mutant runs use it); Test 9 reuses Test 8's
# root, so asking for 9 also runs 8.
want() {
    [[ -z "${ONLY:-}" ]] && return 0
    [[ " $ONLY " == *" $1 "* ]] && return 0
    [[ "$1" == 8 && " $ONLY " == *" 9 "* ]]
}

# --- helpers -----------------------------------------------------------------

new_root() {   # new_root <name> [project name] -> a fresh git repo with aitasks/
    local d="$TMP/$1"
    mkdir -p "$d/aitasks/metadata" "$d/aitasks/archived"
    printf 'project:\n  name: %s\n' "${2:-fixproj}" > "$d/aitasks/metadata/project_config.yaml"
    printf '.aitask-sitrep/\n' > "$d/.gitignore"
    git -C "$d" init -q -b main
    git -C "$d" add -A
    git -C "$d" commit -q -m init
    printf '%s' "$d"
}

# task <root> <id> <status> [yaml lines...]  (active file; replaces any)
task() {
    local root="$1" id="$2" status="$3" dir="$1/aitasks" f
    shift 3
    [[ "$id" == *_* ]] && dir="$root/aitasks/t${id%%_*}"
    mkdir -p "$dir"
    f="$dir/t${id}_x.md"
    { printf -- '---\nstatus: %s\n' "$status"; local l; for l in "$@"; do printf '%s\n' "$l"; done
      printf -- '---\n\nbody\n'; } > "$f"
}

# archive <root> <id> <status> [yaml lines...]  (moves the task to archived/)
archive() {
    local root="$1" id="$2" status="$3"
    shift 3
    rm -f "$root/aitasks/t${id}_x.md"
    { printf -- '---\nstatus: %s\ncompleted_at: 2026-11-02 09:00\n' "$status"; local l
      for l in "$@"; do printf '%s\n' "$l"; done; printf -- '---\n\nbody\n'; } \
        > "$root/aitasks/archived/t${id}_x.md"
}

wr() {   # wr <root> <writer args...> (stdin passed through)
    local root="$1"; shift
    AITASK_SITREP_DIR="$root/.aitask-sitrep" "$WR" "$@"
}

ctx_of() {   # ctx_of <background> [extra lines...]
    printf -- '- background: %s\n- origin: agent=a1 date=2026-11-01\n' "$1"
    shift
    local l
    for l in "$@"; do printf '%s\n' "$l"; done
}

add_item() {   # add_item <root> <kind> <title> [writer add args...] -> echoes cN
    local root="$1" kind="$2" title="$3" out
    shift 3
    out="$(ctx_of "$title" | wr "$root" add --kind "$kind" --title "$title" --context-file - "$@")"
    printf '%s' "${out#*:}"
}

refresh() {   # refresh <root> [args...] -> OUT, RC
    local root="$1"; shift
    RC=0
    OUT="$("$RF" --root "$root" "$@" 2>"$TMP/err")" || RC=$?
}

line_of() { grep "^- $2 |" "$1/.aitask-sitrep/todo.md"; }
st_of() { line_of "$1" "$2" | sed -n 's/.* | state=\([a-z]*\) | .*/\1/p'; }
outc() { line_of "$1" "$2" | sed -n 's/.* | outcome=\([^|]*\) | .*/\1/p'; }
chk() { line_of "$1" "$2" | sed -n 's/.* | checked_at=\([^ ]*\) | .*/\1/p'; }
rev_of() { line_of "$1" "$2" | sed -n 's/^- c[0-9]* | rev=\([0-9]*\) | .*/\1/p'; }
item_res() { printf '%s\n' "$OUT" | grep "^REFRESH_ITEM:$1|" | cut -d'|' -f4; }

reset_fifo() {
    exec 7>&- 2>/dev/null
    rm -f "$FIFO" "$FIFO.reached"
    mkfifo "$FIFO"
    exec 7<>"$FIFO"
}
wait_reached() {   # wait_reached [point]
    local _
    for _ in $(seq 1 400); do
        if [[ -s "$FIFO.reached" ]] && { [[ -z "${1:-}" ]] || grep -qxF "$1" "$FIFO.reached"; }; then
            return 0
        fi
        sleep 0.05
    done
    return 1
}
wait_done() {
    local pid="$1" _
    for _ in $(seq 1 600); do
        kill -0 "$pid" 2>/dev/null || { wait "$pid" 2>/dev/null; return 0; }
        sleep 0.05
    done
    return 1
}

# A PATH-first shim dir: shim <name> <bash body> (the body may exec the real one).
# The marker is in the shim directory's PATH so every shim process's command
# line (`bash <dir>/git …`) carries it -- that is what survivors() counts.
SHIMS="$TMP/shims_$MARK"
mkdir -p "$SHIMS"
shim() {
    printf '#!/usr/bin/env bash\n%s\n' "$2" > "$SHIMS/$1"
    chmod +x "$SHIMS/$1"
}
unshim() { rm -f "$SHIMS/$1"; }

survivors() { pgrep -f "$MARK" | grep -vx "$$" | wc -l | tr -d ' '; }

# =============================================================================
if want 1; then
echo "=== Test 1: a follow-up lands ==="
R1="$(new_root r1)"
task "$R1" 10 Ready
C1="$(add_item "$R1" task "t10 follow-up" --ref t10 --group next)"
refresh "$R1"
assert_eq "refresh exits 0" "0" "$RC"
assert_contains "it reports the item" "REFRESH_ITEM:$C1|task|open->open|applied|status: Ready" "$OUT"
assert_contains "final line" "REFRESHED:checked=1|changed=1|stale=0|kept=0|unknown=0" "$OUT"
assert_eq "Ready -> open" "open" "$(st_of "$R1" "$C1")"
assert_eq "... showing the live status" "status: Ready" "$(outc "$R1" "$C1")"
assert_eq "... stamped" "2026-11-03T10:00:00Z" "$(chk "$R1" "$C1")"
task "$R1" 10 Implementing
AITASK_SITREP_NOW=2026-11-03T10:05:00Z refresh "$R1"
assert_eq "Implementing (picked) stays open" "open" "$(st_of "$R1" "$C1")"
assert_eq "... showing Implementing" "status: Implementing" "$(outc "$R1" "$C1")"
archive "$R1" 10 Done
AITASK_SITREP_NOW=2026-11-03T10:10:00Z refresh "$R1"
assert_eq "archived Done -> done" "done" "$(st_of "$R1" "$C1")"
assert_eq "... with a one-line outcome" "archived (completed 2026-11-02)" "$(outc "$R1" "$C1")"
done_line="$(line_of "$R1" "$C1")"
task "$R1" 10 Ready          # even if a task file reappears, done is final
AITASK_SITREP_NOW=2026-11-03T10:15:00Z refresh "$R1"
assert_eq "no targets left" "REFRESH_NONE:no_targets" "$OUT"
assert_eq "the done line is byte-identical (never re-checked)" "$done_line" "$(line_of "$R1" "$C1")"
fi

# =============================================================================
if want 2; then
echo "=== Test 2: a harvest-unknown item whose task now exists ==="
R2="$(new_root r2)"
C2="$(add_item "$R2" task "t20 created later" --ref t20 --state unknown)"
refresh "$R2"
assert_eq "still missing -> unknown" "unknown" "$(st_of "$R2" "$C2")"
assert_eq "... task file not found" "task file not found" "$(outc "$R2" "$C2")"
task "$R2" 20 Ready
refresh "$R2"
assert_eq "the task appeared -> open" "open" "$(st_of "$R2" "$C2")"
fi

# =============================================================================
if want 3; then
echo "=== Test 3: fold ==="
R3="$(new_root r3)"
task "$R3" 30 Ready
task "$R3" 31 Folded "folded_into: 30"
C3a="$(add_item "$R3" task "t31" --ref t31)"
C3b="$(add_item "$R3" task "t32" --ref t32)"
task "$R3" 32 Ready
refresh "$R3"
assert_eq "live Folded -> done" "done" "$(st_of "$R3" "$C3a")"
assert_eq "... naming where it went" "folded into t30 (t30: Ready)" "$(outc "$R3" "$C3a")"
# t32 is folded into t30, then t30 is archived and the folded file deleted.
rm -f "$R3/aitasks/t32_x.md"
archive "$R3" 30 Done "folded_tasks: [32]"
refresh "$R3"
assert_eq "deleted folded file found via folded_tasks -> done" "done" "$(st_of "$R3" "$C3b")"
assert_eq "... naming the archived receiver" "folded into t30 (t30: archived)" "$(outc "$R3" "$C3b")"
fi

# =============================================================================
if want 4; then
echo "=== Test 4: push ==="
R4="$(new_root r4)"
git init -q --bare -b main "$TMP/r4_origin.git"
git -C "$R4" remote add origin "$TMP/r4_origin.git"
git -C "$R4" push -q -u origin main
git -C "$R4" commit -q --allow-empty -m two
SHA4="$(git -C "$R4" rev-parse HEAD)"
C4="$(add_item "$R4" action "Push main" --ref "push:main@$SHA4" --derived agent)"
refresh "$R4"
assert_eq "not yet pushed -> open" "open" "$(st_of "$R4" "$C4")"
assert_contains "... 1 ahead" "not pushed: main 1 ahead / 0 behind origin/main" "$(outc "$R4" "$C4")"
git -C "$R4" push -q origin main
refresh "$R4"
assert_eq "after the push -> done" "done" "$(st_of "$R4" "$C4")"
assert_eq "... outcome" "pushed: ${SHA4:0:7} is on origin/main" "$(outc "$R4" "$C4")"
fi

# =============================================================================
if want 5; then
echo "=== Test 5: unreachable repos -> unknown ==="
R5="$(new_root r5)"
C5a="$(add_item "$R5" task "ghost" --ref ghostproj#7)"
printf 'projects:\n  - name: goneproj\n    path: %s\n    last_opened: 2026-11-01\n' "$TMP/deleted_dir" > "$AITASKS_PROJECTS_INDEX"
C5b="$(add_item "$R5" task "gone" --ref goneproj#8)"
NG="$TMP/nogit"; mkdir -p "$NG/aitasks/metadata"
C5c="$(add_item "$NG" action "Push main" --ref push:main@abcdef1)"
refresh "$R5"
assert_eq "unregistered project -> unknown" "unknown" "$(st_of "$R5" "$C5a")"
assert_eq "... cross-repo outcome" "cross-repo: project ghostproj not resolved" "$(outc "$R5" "$C5a")"
assert_eq "registered but deleted -> unknown" "unknown" "$(st_of "$R5" "$C5b")"
refresh "$NG"
assert_eq "push item in a non-git root -> unknown" "unknown" "$(st_of "$NG" "$C5c")"
assert_eq "... not a git repository" "not a git repository" "$(outc "$NG" "$C5c")"
XP="$(new_root xp xp)"
task "$XP" 8 Implementing
printf 'projects:\n  - name: xp\n    path: %s\n    last_opened: 2026-11-01\n' "$XP" > "$AITASKS_PROJECTS_INDEX"
C5d="$(add_item "$R5" task "resolvable" --ref xp#8)"
refresh "$R5"
assert_eq "a resolved cross-repo task -> open" "open" "$(st_of "$R5" "$C5d")"
assert_eq "... prefixed with the project" "xp: status: Implementing" "$(outc "$R5" "$C5d")"
printf 'projects:\n' > "$AITASKS_PROJECTS_INDEX"
fi

# =============================================================================
if want 6; then
echo "=== Test 6: concurrent refresh vs agent writes ==="
R6="$(new_root r6)"
for i in 61 62 63; do task "$R6" "$i" Ready; done
C61="$(add_item "$R6" task "t61" --ref t61)"
C62="$(add_item "$R6" task "t62" --ref t62)"
C63="$(add_item "$R6" task "t63" --ref t63)"
reset_fifo
AITASK_SITREP_REFRESH_PAUSE_FIFO="$FIFO" "$RF" --root "$R6" >"$TMP/bg.out" 2>"$TMP/bg.err" &
pid=$!; BG_PIDS+=("$pid")
wait_reached refresh:before_write
assert_eq "refresh parked before its write" "refresh:before_write" "$(cat "$FIFO.reached")"
wr "$R6" dismiss "$C61" --outcome "user: not needed" >/dev/null
wr "$R6" update "$C62" --title "t62 renamed by the agent" >/dev/null
echo go >&7
wait_done "$pid"
OUT="$(cat "$TMP/bg.out")"
# `dismiss` takes a fresh rev and the writer checks the rev first, so an item
# dismissed after the snapshot comes back STALE (KEPT needs the dismissed
# item's current rev, which a refresh never holds: dismissed items are not
# targets). Either way the dismissal is never overwritten.
assert_eq "dismissed meanwhile -> stale (rev checked first)" "stale" "$(item_res "$C61")"
assert_eq "changed meanwhile -> stale" "stale" "$(item_res "$C62")"
assert_eq "untouched -> applied" "applied" "$(item_res "$C63")"
assert_eq "c61 stays dismissed" "dismissed" "$(st_of "$R6" "$C61")"
assert_contains "c62 keeps the agent's title" "| t62 renamed by the agent" "$(line_of "$R6" "$C62")"
assert_eq "c62 not stamped" "never" "$(chk "$R6" "$C62")"
assert_contains "final counts" "stale=2|kept=0" "$OUT"
"$RF" --root "$R6" >"$TMP/c1.out" 2>&1 & p1=$!
"$RF" --root "$R6" >"$TMP/c2.out" 2>&1 & p2=$!
wait "$p1"; r1=$?; wait "$p2"; r2=$?
assert_eq "two concurrent refreshes both exit 0" "0 0" "$r1 $r2"
assert_eq "the store still parses" "VERIFIED:todo" \
    "$("$AIT_PYTHON" "$PROJECT_DIR/.aitask-scripts/lib/sitrep_todo.py" verify todo "$R6/.aitask-sitrep/todo.md")"
assert_eq "every item is present" "3" "$(wr "$R6" list | grep -c '^ITEM:')"
fi

# =============================================================================
if want 6b; then
echo "=== Test 6b: a context swap during a paused refresh ==="
R6B="$(new_root r6b fixproj)"
TRAILS="$TMP/trails"; mkdir -p "$TRAILS"
# Trail A: every entry archived Done. Trail B: the same shape, one entry Ready.
sed 's/"aitasks#/"fixproj#/g' "$TRAIL_DOC" > "$TRAILS/art:trail-a.json"
sed 's/"aitasks#/"fixproj#/g; s/"fixproj#1147"/"fixproj#1200"/g' "$TRAIL_DOC" > "$TRAILS/art:trail-b.json"
for id in 1147 1183 635_29 635_33 1181 635_30; do
    if [[ "$id" == *_* ]]; then
        mkdir -p "$R6B/aitasks/archived/t${id%%_*}"
        printf -- '---\nstatus: Done\ncompleted_at: 2026-10-01 09:00\n---\n' > "$R6B/aitasks/archived/t${id%%_*}/t${id}_x.md"
    else
        archive "$R6B" "$id" Done
    fi
done
task "$R6B" 1200 Ready
task "$R6B" 635 Implementing
cat > "$TMP/fake_artifact.sh" <<EOF
#!/usr/bin/env bash
# fake artifact CLI: get <handle> --out <path> serves $TRAILS/<handle>.json
[[ "\$1" == get && -f "$TRAILS/\$2.json" ]] || exit 1
cp "$TRAILS/\$2.json" "\$4"
EOF
chmod +x "$TMP/fake_artifact.sh"
export AITASK_SITREP_REFRESH_ARTIFACT_SH="$TMP/fake_artifact.sh"
C6B="$(add_item "$R6B" watch "Trail to watch" "--group" waiting)"
ctx_of "Trail to watch" "- sources:" "  - trail: art:trail-a" | wr "$R6B" upsert-context "$C6B" >/dev/null
refresh "$R6B" --dry-run
assert_contains "trail A alone would be done" "REFRESH_ITEM:$C6B|watch|open->done|dry_run|all 5 waves landed" "$OUT"
reset_fifo
AITASK_SITREP_REFRESH_PAUSE_FIFO="$FIFO" "$RF" --root "$R6B" >"$TMP/bg.out" 2>"$TMP/bg.err" &
pid=$!; BG_PIDS+=("$pid")
wait_reached refresh:before_write
ctx_of "Trail to watch" "- sources:" "  - trail: art:trail-b" | wr "$R6B" upsert-context "$C6B" >/dev/null
echo go >&7
wait_done "$pid"
OUT="$(cat "$TMP/bg.out")"
assert_eq "the swapped source makes the line stale" "stale" "$(item_res "$C6B")"
assert_eq "... the item stays open" "open" "$(st_of "$R6B" "$C6B")"
refresh "$R6B"
assert_eq "the next refresh reads trail B -> open" "open" "$(st_of "$R6B" "$C6B")"
assert_contains "... with B's next wave" "next wave 1/5 Clear dirty and in-flight conflicts: 1 pending (t1200)" "$(outc "$R6B" "$C6B")"
assert_contains "... and the owner's live state" "owner t635 Implementing" "$(outc "$R6B" "$C6B")"
reset_fifo
AITASK_SITREP_NOW=2026-11-03T11:00:00Z AITASK_SITREP_REFRESH_PAUSE_FIFO="$FIFO" "$RF" --root "$R6B" >"$TMP/bg.out" 2>"$TMP/bg.err" &
pid=$!; BG_PIDS+=("$pid")
wait_reached refresh:before_write
ctx_of "Trail to watch" "- sources:" "  - trail: art:trail-b" | wr "$R6B" upsert-context "$C6B" >"$TMP/up.out"
echo go >&7
wait_done "$pid"
OUT="$(cat "$TMP/bg.out")"
assert_eq "an unchanged upsert is a no-op" "CONTEXT:$C6B|unchanged" "$(cat "$TMP/up.out")"
assert_eq "... and the line still applies" "applied" "$(item_res "$C6B")"
unset AITASK_SITREP_REFRESH_ARTIFACT_SH
fi

# =============================================================================
if want 7; then
echo "=== Test 7: non-targets and --dry-run ==="
R7="$(new_root r7)"
task "$R7" 70 Done
C7q="$(add_item "$R7" question "Triage wrap-up of t1")"
C7a="$(add_item "$R7" action "Deploy dev" --derived agent)"
C7d="$(add_item "$R7" task "t71" --ref t71)"; wr "$R7" set-state "$C7d" "done" --outcome "by hand" >/dev/null
C7x="$(add_item "$R7" task "t72" --ref t72)"; wr "$R7" dismiss "$C7x" >/dev/null
C7t="$(add_item "$R7" task "t70" --ref t70)"
before="$(cat "$R7/.aitask-sitrep/todo.md")"
lines_before="$(grep -E "^- ($C7q|$C7a|$C7d|$C7x) \|" "$R7/.aitask-sitrep/todo.md")"
refresh "$R7" --dry-run
assert_eq "--dry-run exits 0" "0" "$RC"
assert_contains "--dry-run reports the target" "REFRESH_ITEM:$C7t|task|open->done|dry_run|status: Done (not yet archived)" "$OUT"
assert_eq "--dry-run writes nothing" "$before" "$(cat "$R7/.aitask-sitrep/todo.md")"
refresh "$R7"
assert_eq "only the target was reported" "1" "$(printf '%s\n' "$OUT" | grep -c '^REFRESH_ITEM:')"
assert_eq "question / agent action / done / dismissed lines byte-identical" "$lines_before" \
    "$(grep -E "^- ($C7q|$C7a|$C7d|$C7x) \|" "$R7/.aitask-sitrep/todo.md")"
fi

# =============================================================================
if want 8; then
echo "=== Test 8: no store, damaged store, '..' root ==="
R8="$(new_root r8)"
refresh "$R8"
assert_eq "no store -> REFRESH_NONE:no_store" "REFRESH_NONE:no_store" "$OUT"
assert_eq "... exit 0" "0" "$RC"
assert_dir_not_exists "... and no store was created" "$R8/.aitask-sitrep"
task "$R8" 80 Ready
add_item "$R8" task "t80" --ref t80 >/dev/null
cp "$R8/.aitask-sitrep/todo.md" "$TMP/r8.todo"
printf 'hand edit\n' >> "$R8/.aitask-sitrep/todo.md"
cp "$R8/.aitask-sitrep/todo.md" "$TMP/r8.damaged"
refresh "$R8"
assert_eq "damaged store -> exit 1" "1" "$RC"
assert_contains "... REFRESH_FAILED:store_unusable" "REFRESH_FAILED:store_unusable" "$OUT"
assert_eq "... nothing changed" "$(cat "$TMP/r8.damaged")" "$(cat "$R8/.aitask-sitrep/todo.md")"
cp "$TMP/r8.todo" "$R8/.aitask-sitrep/todo.md"
RC=0; OUT="$("$RF" --root "$TMP/r8/../r8" 2>&1)" || RC=$?
assert_eq "'..' root -> exit 2" "2" "$RC"
RC=0; OUT="$("$RF" --budget abc 2>&1)" || RC=$?
assert_eq "bad --budget -> exit 2" "2" "$RC"
for bad in inf 1e400 nan; do
    RC=0; OUT="$(AITASK_SITREP_REFRESH_BUDGET=$bad "$RF" --root "$R8" 2>&1)" || RC=$?
    assert_eq "AITASK_SITREP_REFRESH_BUDGET=$bad -> exit 2" "2" "$RC"
    assert_not_contains "... no traceback" "Traceback" "$OUT"
done
RC=0; OUT="$("$RF" --root "$R8" --budget 99999999999999999999999 2>&1)" || RC=$?
assert_eq "an overflowing --budget -> exit 2" "2" "$RC"
fi

# =============================================================================
if want 9; then
echo "=== Test 9: --budget 0 ==="
before="$(cat "$R8/.aitask-sitrep/todo.md")"
refresh "$R8" --budget 0
assert_eq "--budget 0 -> exit 1" "1" "$RC"
assert_eq "... REFRESH_FAILED:deadline" "REFRESH_FAILED:deadline" "$OUT"
assert_eq "... nothing written" "$before" "$(cat "$R8/.aitask-sitrep/todo.md")"
fi

# =============================================================================
if want 10; then
echo "=== Test 10: slow checks + slow writer inside the caller contract ==="
R10="$(new_root r10)"
git init -q --bare -b main "$TMP/r10_origin.git"
git -C "$R10" remote add origin "$TMP/r10_origin.git"
git -C "$R10" push -q -u origin main
S10="$(git -C "$R10" rev-parse HEAD)"
git -C "$R10" branch b2
git -C "$R10" push -q -u origin b2
C10a="$(add_item "$R10" action "Push main" --ref "push:main@$S10")"
C10b="$(add_item "$R10" action "Push b2" --ref "push:b2@$S10")"
# Every push-check git subcommand sleeps 2 s (~8 slowed calls per item), so
# the first item outlives the 15 s check deadline of --budget 20 (reserve 5).
shim git "case \" \$* \" in *' merge-base '*|*' rev-list '*|*' remote '*|*' config '*) sleep 2;; esac
exec \"$REAL_GIT\" \"\$@\""
# A writer holds the store lock until 16 s after the refresh starts: the
# refresh's writer starts at ~15 s and must wait for it (lock timeout 2 s).
reset_fifo
AITASK_SITREP_DIR="$R10/.aitask-sitrep" AITASK_SITREP_PAUSE_FIFO="$FIFO" \
    "$WR" situation r10 <<<"held" >/dev/null 2>&1 &
wpid=$!; BG_PIDS+=("$wpid")
wait_reached
before_b="$(line_of "$R10" "$C10b")"
( sleep 16; for _ in 1 2 3 4; do echo go >&7; sleep 0.1; done ) & BG_PIDS+=("$!")
t0=$SECONDS
RC=0
OUT="$(PATH="$SHIMS:$PATH" timeout 35 "$RF" --root "$R10" --budget 20 2>"$TMP/err")" || RC=$?
elapsed=$((SECONDS - t0))
assert_eq "exit 0 inside timeout 35 (budget + 15)" "0" "$RC"
assert_contains "REFRESHED reported" "REFRESHED:" "$OUT"
assert_contains "the interrupted target is unknown with the budget reason" \
    "check did not finish within the 20s budget" "$(outc "$R10" "$C10a")"
assert_eq "the not-reached target is byte-identical" "$before_b" "$(line_of "$R10" "$C10b")"
assert_contains "... and reported as not reached" "REFRESH_WARN:budget_exhausted|1 not reached" "$OUT"
[[ $elapsed -lt 35 && $elapsed -ge 15 ]] && ok=yes || ok=no
assert_eq "it waited for the lock and finished inside the contract (${elapsed}s)" "yes" "$ok"
assert_contains "the held writer's change survived" "held" "$(sed -n '/^#### r10/,/^###/p' "$R10/.aitask-sitrep/todo.md")"
wait_done "$wpid"
unshim git
# Lock held past the whole budget, after slow checks used up the check window:
# the writer's lock wait comes from what is left (1 s), so the run ends within
# budget + 2 s -- not after the writer's default 10 s lock wait.
shim git "case \" \$* \" in *' merge-base '*|*' rev-list '*|*' remote '*|*' config '*) sleep 2;; esac
exec \"$REAL_GIT\" \"\$@\""
reset_fifo
AITASK_SITREP_DIR="$R10/.aitask-sitrep" AITASK_SITREP_PAUSE_FIFO="$FIFO" \
    "$WR" situation r10 <<<"held again" >/dev/null 2>&1 &
wpid=$!; BG_PIDS+=("$wpid")
wait_reached
before="$(cat "$R10/.aitask-sitrep/todo.md")"
t0=$SECONDS
RC=0
OUT="$(PATH="$SHIMS:$PATH" timeout 27 "$RF" --root "$R10" --budget 12 2>"$TMP/err")" || RC=$?
elapsed=$((SECONDS - t0))
unshim git
assert_eq "lock held -> exit 1" "1" "$RC"
assert_eq "... REFRESH_FAILED:lock_busy" "REFRESH_FAILED:lock_busy" "$(printf '%s\n' "$OUT" | tail -1)"
assert_eq "... nothing written" "$before" "$(cat "$R10/.aitask-sitrep/todo.md")"
[[ $elapsed -le 14 ]] && ok=yes || ok=no
assert_eq "... within budget + 2 s (${elapsed}s)" "yes" "$ok"
for _ in 1 2 3 4; do echo go >&7; done
wait_done "$wpid"
fi

# =============================================================================
if want 11; then
echo "=== Test 11: a stalled real archive / git helper is killed with its group ==="
if [[ -z "$REAL_ZSTD" ]]; then
    echo "SKIP: zstd is not installed"
else
    R11="$(new_root r11)"
    task "$R11" 110 Ready
    # A real numbered bundle: t1xx ids live in _b0/old1.tar.zst.
    mkdir -p "$TMP/b11" "$R11/aitasks/archived/_b0"
    printf -- '---\nstatus: Done\n---\n' > "$TMP/b11/t150_x.md"
    tar -C "$TMP/b11" -cf - t150_x.md | "$REAL_ZSTD" -q -c > "$R11/aitasks/archived/_b0/old1.tar.zst"
    AITASK_SITREP_NOW=2026-11-03T09:00:00Z
    C11a="$(add_item "$R11" task "t110" --ref t110)"
    C11b="$(add_item "$R11" task "t199 missing" --ref t199)"
    C11c="$(add_item "$R11" task "t110 again" --ref t110_1)"
    AITASK_SITREP_NOW=2026-11-03T10:00:00Z
    before_c="$(line_of "$R11" "$C11c")"
    shim zstd "sleep 600"
    t0=$SECONDS
    RC=0
    OUT="$(PATH="$SHIMS:$PATH" timeout 25 "$RF" --root "$R11" --budget 10 2>"$TMP/err")" || RC=$?
    elapsed=$((SECONDS - t0))
    assert_eq "exit 0 before timeout 25" "0" "$RC"
    assert_eq "the target before the stall was written" "open" "$(st_of "$R11" "$C11a")"
    assert_eq "the stalled target (fold scan through zstd) is unknown" "unknown" "$(st_of "$R11" "$C11b")"
    assert_contains "... with the budget reason" "check did not finish within the 10s budget" "$(outc "$R11" "$C11b")"
    assert_eq "the target after it is unwritten" "$before_c" "$(line_of "$R11" "$C11c")"
    [[ $elapsed -lt 25 ]] && ok=yes || ok=no
    assert_eq "elapsed < 25 s (was ${elapsed}s)" "yes" "$ok"
    sleep 0.5
    assert_eq "no zstd shim survives" "0" "$(survivors)"
    unshim zstd
fi
R11G="$(new_root r11g)"
task "$R11G" 1 Ready
add_item "$R11G" task "t1" --ref t1 >/dev/null
before="$(cat "$R11G/.aitask-sitrep/todo.md")"
shim git "case \" \$* \" in *' worktree list '*) sleep 600;; esac
exec \"$REAL_GIT\" \"\$@\""
t0=$SECONDS
RC=0
OUT="$(PATH="$SHIMS:$PATH" timeout 25 "$RF" --root "$R11G" --budget 8 2>"$TMP/err")" || RC=$?
elapsed=$((SECONDS - t0))
unshim git
assert_eq "a stalled canonical_root -> REFRESH_FAILED:deadline" "REFRESH_FAILED:deadline" "$OUT"
assert_eq "... exit 1" "1" "$RC"
assert_eq "... nothing written" "$before" "$(cat "$R11G/.aitask-sitrep/todo.md")"
[[ $elapsed -lt 25 ]] && ok=yes || ok=no
assert_eq "... before timeout 25 (${elapsed}s)" "yes" "$ok"
sleep 0.5
assert_eq "... no git shim survives" "0" "$(survivors)"
fi

# =============================================================================
if want 12; then
echo "=== Test 12: progress across bounded runs ==="
R12="$(new_root r12)"
git init -q --bare -b main "$TMP/r12_origin.git"
git -C "$R12" remote add origin "$TMP/r12_origin.git"
git -C "$R12" push -q -u origin main
git -C "$R12" branch b1
git -C "$R12" push -q -u origin b1 2>/dev/null
git -C "$R12" commit -q --allow-empty -m unpushed     # on main only: never on b1
S12="$(git -C "$R12" rev-parse HEAD)"
for i in 124 125 126; do task "$R12" "$i" Ready; done
# c1 sorts first (id) and its check never finishes; c2..c4 are cheap.
P1="$(add_item "$R12" action "Push b1" --ref "push:b1@$S12")"
T4="$(add_item "$R12" task "t124" --ref t124)"
T5="$(add_item "$R12" task "t125" --ref t125)"
T6="$(add_item "$R12" task "t126" --ref t126)"
shim git "case \" \$* \" in *' merge-base '*origin/b1*) sleep 600;; esac
exec \"$REAL_GIT\" \"\$@\""
maxel=0
for run in 1 2 3; do
    t0=$SECONDS
    RC=0
    OUT="$(AITASK_SITREP_NOW="2026-11-03T12:0${run}:00Z" PATH="$SHIMS:$PATH" timeout 23 "$RF" --root "$R12" --budget 8 2>"$TMP/err")" || RC=$?
    el=$((SECONDS - t0)); [[ $el -gt $maxel ]] && maxel=$el
done
unshim git
for c in "$T4" "$T5" "$T6"; do
    assert_eq "cheap $c was checked within 3 runs" "open" "$(st_of "$R12" "$c")"
    [[ "$(chk "$R12" "$c")" != never ]] && ok=yes || ok=no
    assert_eq "... and stamped" "yes" "$ok"
done
s="$(st_of "$R12" "$P1")"
[[ "$s" == open || "$s" == unknown ]] && ok=yes || ok=no
assert_eq "the never-finishing $P1 is open/unknown (never wrongly done)" "yes" "$ok"
assert_contains "... and rotated behind the others with the budget reason" \
    "check did not finish within the 8s budget" "$(outc "$R12" "$P1")"
[[ $maxel -lt 23 ]] && ok=yes || ok=no
assert_eq "no run lasted past budget + 15 (max ${maxel}s)" "yes" "$ok"
sleep 0.5
assert_eq "no stalled git survives" "0" "$(survivors)"
fi

# =============================================================================
if want 13; then
echo "=== Test 13: interrupted before the first VERDICT, with concurrent edits ==="
R13="$(new_root r13)"
git init -q --bare -b main "$TMP/r13_origin.git"
git -C "$R13" remote add origin "$TMP/r13_origin.git"
git -C "$R13" push -q -u origin main
S13="$(git -C "$R13" rev-parse HEAD)"
task "$R13" 131 Ready
P13="$(add_item "$R13" action "Push main" --ref "push:main@$S13")"
T13="$(add_item "$R13" task "t131" --ref t131)"
# A stamp later than any run's, so t131 always sorts after the push item.
wr "$R13" set-state "$T13" open --checked-at 2026-12-01T00:00:00Z >/dev/null
shim git "case \" \$* \" in *' merge-base '*) sleep 600;; esac
exec \"$REAL_GIT\" \"\$@\""
for variant in a b c; do
    rev0="$(rev_of "$R13" "$P13")"
    before_t="$(line_of "$R13" "$T13")"
    export AITASK_SITREP_REFRESH_BATCH_LOG="$TMP/batch13$variant"
    rm -f "$AITASK_SITREP_REFRESH_BATCH_LOG"
    PATH="$SHIMS:$PATH" "$RF" --root "$R13" --budget 8 >"$TMP/bg.out" 2>"$TMP/bg.err" &
    pid=$!; BG_PIDS+=("$pid")
    sleep 2.5                                  # the worker is stalled in c$P13's check
    case "$variant" in
        b) wr "$R13" update "$P13" --title "Push main (edited)" >/dev/null ;;
        c) ctx_of "Push main" "- theme: edited" | wr "$R13" upsert-context "$P13" >/dev/null ;;
    esac
    wait_done "$pid"
    OUT="$(cat "$TMP/bg.out")"
    assert_contains "($variant) the batch carries the START's snapshot rev" \
        "$P13|$rev0|unknown|" "$(cat "$AITASK_SITREP_REFRESH_BATCH_LOG")"
    assert_eq "($variant) the never-started target is unwritten" "$before_t" "$(line_of "$R13" "$T13")"
    case "$variant" in
        a)  assert_eq "(a) no edit -> applied" "applied" "$(item_res "$P13")"
            assert_contains "(a) ... unknown with the budget reason" "check did not finish" "$(outc "$R13" "$P13")" ;;
        b)  assert_eq "(b) title edit -> stale" "stale" "$(item_res "$P13")"
            assert_contains "(b) ... the edit is kept" "| Push main (edited)" "$(line_of "$R13" "$P13")" ;;
        c)  assert_eq "(c) context edit -> stale" "stale" "$(item_res "$P13")"
            assert_contains "(c) ... the new context is kept" "theme: edited" "$(wr "$R13" context "$P13")" ;;
    esac
done
unset AITASK_SITREP_REFRESH_BATCH_LOG
unshim git
sleep 0.5
assert_eq "no stalled git survives" "0" "$(survivors)"
fi

# =============================================================================
if want 14; then
echo "=== Test 14: the worker dies with its parent ==="
R14="$(new_root r14)"
git init -q --bare -b main "$TMP/r14_origin.git"
git -C "$R14" remote add origin "$TMP/r14_origin.git"
git -C "$R14" push -q -u origin main
add_item "$R14" action "Push main" --ref "push:main@$(git -C "$R14" rev-parse HEAD)" >/dev/null
shim git "case \" \$* \" in *' merge-base '*) sleep 600;; esac
exec \"$REAL_GIT\" \"\$@\""
before="$(cat "$R14/.aitask-sitrep/todo.md")"
PATH="$SHIMS:$PATH" "$RF" --root "$R14" --budget 60 >/dev/null 2>&1 &
pid=$!; BG_PIDS+=("$pid")
sleep 2.5
kill -9 "$pid"                      # what the monitor runner's proc.kill() does
wait "$pid" 2>/dev/null
gone=no
for _ in $(seq 1 40); do
    [[ "$(survivors)" == 0 ]] && { gone=yes; break; }
    sleep 0.1
done
unshim git
assert_eq "the orphaned worker group is gone within 4 s" "yes" "$gone"
assert_eq "... nothing written" "$before" "$(cat "$R14/.aitask-sitrep/todo.md")"
fi

echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ "$FAIL" -eq 0 ]]; then
    echo "ALL TESTS PASSED"
fi
[[ "$FAIL" -eq 0 ]]
