#!/usr/bin/env bash
# test_yaml_utils.sh - Tests for the shared YAML reader lib (t815).
#
# read_yaml_field was once defined independently in BOTH task_utils.sh and
# agentcrew_utils.sh; whichever lib was sourced last silently won. t815
# extracted the canonical readers (join_yaml_flow_lists, read_yaml_field,
# read_yaml_list) into lib/yaml_utils.sh, sourced by both libs behind a
# double-source guard.
#
# These tests cover the canonical read_yaml_field on both file shapes it must
# support — markdown frontmatter files and plain YAML files with no
# frontmatter (crew *_status.yaml) — read_yaml_list, and a regression guard
# against a second copy of read_yaml_field being re-introduced.
#
# Run: bash tests/test_yaml_utils.sh

set -u

TEST_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$TEST_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
LIB_DIR="$PROJECT_DIR/.aitask-scripts/lib"

# Source both libs, in the same order aitask_archive.sh does. Both source
# yaml_utils.sh; the double-source guard must make the second a no-op.
# shellcheck source=../.aitask-scripts/lib/task_utils.sh
source "$LIB_DIR/task_utils.sh"
# shellcheck source=../.aitask-scripts/lib/agentcrew_utils.sh
source "$LIB_DIR/agentcrew_utils.sh"

PASS=0
FAIL=0
TOTAL=0

# Count comma-separated entries after stripping brackets/spaces.
count_entries() {
    local csv
    csv=$(parse_yaml_list "$1")
    [[ -z "$csv" ]] && { echo 0; return; }
    echo "$csv" | tr ',' '\n' | grep -c .
}

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_t815_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT

# --- Test 1: read_yaml_field on a markdown frontmatter file ----------------

cat > "$TMP/task.md" <<'EOF'
---
priority: high
issue_type: bug
status: Ready
labels: [ui, backend]
---

## Body

status: this-body-line-must-not-match
EOF

assert_eq "read_yaml_field: scalar frontmatter field" \
    "high" "$(read_yaml_field "$TMP/task.md" "priority")"
assert_eq "read_yaml_field: issue_type field" \
    "bug" "$(read_yaml_field "$TMP/task.md" "issue_type")"
assert_eq "read_yaml_field: missing field yields empty string" \
    "" "$(read_yaml_field "$TMP/task.md" "no_such_field")"

# Frontmatter restriction: a body line that looks like a field must NOT win.
assert_eq "read_yaml_field: body line is not matched (frontmatter wins)" \
    "Ready" "$(read_yaml_field "$TMP/task.md" "status")"

# --- Test 2: read_yaml_field on a wrapped multi-line flow list -------------

cat > "$TMP/verifies.md" <<'EOF'
---
issue_type: manual_verification
verifies: [t900_1, t900_2, t900_3, t900_4, t900_5, t900_6, t900_7, t900_8,
  t900_9, t900_10]
status: Ready
---
EOF
rf_value=$(read_yaml_field "$TMP/verifies.md" "verifies")
assert_eq "read_yaml_field: wrapped flow list returns all 10 entries" \
    "10" "$(count_entries "$rf_value")"
assert_contains "read_yaml_field: continuation-line entry present" \
    "t900_10" "$rf_value"

# --- Test 3: read_yaml_field on a plain YAML file (no frontmatter) ----------
# Crew *_status.yaml files are plain YAML with no `---` delimiters. The
# canonical reader must scan the whole file for these — the behaviour the
# agentcrew_utils.sh copy used to provide.

cat > "$TMP/crew_status.yaml" <<'EOF'
status: Running
progress: 42
agent_name: planner
started_at: '2026-03-24 09:38:55'
EOF

assert_eq "read_yaml_field: plain YAML (no frontmatter) scalar field" \
    "Running" "$(read_yaml_field "$TMP/crew_status.yaml" "status")"
assert_eq "read_yaml_field: plain YAML numeric field" \
    "42" "$(read_yaml_field "$TMP/crew_status.yaml" "progress")"
assert_eq "read_yaml_field: plain YAML agent_name field" \
    "planner" "$(read_yaml_field "$TMP/crew_status.yaml" "agent_name")"
assert_eq "read_yaml_field: plain YAML missing field yields empty string" \
    "" "$(read_yaml_field "$TMP/crew_status.yaml" "no_such_field")"

# --- Test 4: read_yaml_list on inline / wrapped / block lists --------------

cat > "$TMP/inline_list.md" <<'EOF'
---
depends: [1, 2, 3]
status: Ready
---
EOF
assert_eq "read_yaml_list: inline list yields 3 entries" \
    "3" "$(read_yaml_list "$TMP/inline_list.md" "depends" | grep -c .)"

cat > "$TMP/wrapped_list.md" <<'EOF'
---
children_to_implement: [t900_1, t900_2, t900_3, t900_4, t900_5, t900_6,
  t900_7, t900_8, t900_9, t900_10]
status: Ready
---
EOF
assert_eq "read_yaml_list: wrapped inline list yields all 10 entries" \
    "10" "$(read_yaml_list "$TMP/wrapped_list.md" "children_to_implement" | grep -c .)"
assert_eq "read_yaml_list: wrapped continuation entry parsed" \
    "t900_10" "$(read_yaml_list "$TMP/wrapped_list.md" "children_to_implement" | tail -1)"

cat > "$TMP/block_list.md" <<'EOF'
---
labels:
  - ui
  - backend
status: Ready
---
EOF
assert_eq "read_yaml_list: block-style list yields 2 entries" \
    "2" "$(read_yaml_list "$TMP/block_list.md" "labels" | grep -c .)"

# --- Test 5: join_yaml_flow_lists is reachable via both libs ---------------

joined=$(printf '%s\n' \
    'children_to_implement: [t1, t2,' \
    '  t3]' | join_yaml_flow_lists)
assert_eq "join_yaml_flow_lists: wrapped list collapses to one line" \
    "children_to_implement: [t1, t2,   t3]" "$joined"

# --- Test 6: collision regression guard ------------------------------------
# read_yaml_field must be defined exactly once, in yaml_utils.sh — never again
# in task_utils.sh or agentcrew_utils.sh (the t815 footgun).

count_def() { grep -cE "^${2}\(\)" "$1" || true; }

assert_eq "no read_yaml_field definition in task_utils.sh" \
    "0" "$(count_def "$LIB_DIR/task_utils.sh" read_yaml_field)"
assert_eq "no read_yaml_field definition in agentcrew_utils.sh" \
    "0" "$(count_def "$LIB_DIR/agentcrew_utils.sh" read_yaml_field)"
assert_eq "read_yaml_field defined exactly once in yaml_utils.sh" \
    "1" "$(count_def "$LIB_DIR/yaml_utils.sh" read_yaml_field)"
assert_eq "no read_yaml_list definition in agentcrew_utils.sh" \
    "0" "$(count_def "$LIB_DIR/agentcrew_utils.sh" read_yaml_list)"
assert_eq "read_yaml_list defined exactly once in yaml_utils.sh" \
    "1" "$(count_def "$LIB_DIR/yaml_utils.sh" read_yaml_list)"
assert_eq "no join_yaml_flow_lists definition in task_utils.sh" \
    "0" "$(count_def "$LIB_DIR/task_utils.sh" join_yaml_flow_lists)"
assert_eq "join_yaml_flow_lists defined exactly once in yaml_utils.sh" \
    "1" "$(count_def "$LIB_DIR/yaml_utils.sh" join_yaml_flow_lists)"

# --- Test 7: double-source guard -------------------------------------------

assert_eq "yaml_utils.sh double-source guard variable is set" \
    "1" "${_AIT_YAML_UTILS_LOADED:-unset}"
# Re-sourcing must short-circuit (return 0) without redefining.
source "$LIB_DIR/yaml_utils.sh"
assert_eq "re-sourcing yaml_utils.sh is a no-op (exit 0)" "0" "$?"

# --- read_yaml_mappings: artifacts: block (t1076_2) ------------------------
# The mapping reader serves both attachments: (t1030 §3) and artifacts:
# (unified artifact design §4). handle/kind must be emitted, handle/kind
# FIRST, records blank-line separated, quoted names round-tripped, and
# field-scoping must hold when both blocks coexist on one task.

cat > "$TMP/artifacts.md" <<'EOF'
---
priority: low
artifacts:
  - handle: art:t774-htmlplan
    kind: html_plan
    name: "Login flow mockups"
  - handle: art:t774-report
    kind: report
attachments:
  - hash: sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08
    name: shot.png
---
EOF

art_out="$(read_yaml_mappings "$TMP/artifacts.md" artifacts)"
expected_art="$(printf 'handle=art:t774-htmlplan\nkind=html_plan\nname=Login flow mockups\n\nhandle=art:t774-report\nkind=report')"
assert_eq "artifacts records emit handle/kind/name in schema order, blank-line separated" \
    "$expected_art" "$art_out"

attach_out="$(read_yaml_mappings "$TMP/artifacts.md" attachments)"
expected_attach="$(printf 'hash=sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08\nname=shot.png')"
assert_eq "field-scoping: reading attachments from a mixed task yields only attachment records" \
    "$expected_attach" "$attach_out"

art_scoped="$(read_yaml_mappings "$TMP/artifacts.md" artifacts | grep -c '^hash=' || true)"
assert_eq "field-scoping: artifacts records carry no attachment keys" "0" "$art_scoped"

# === t1444: broken-pipe storm suppression ==================================
#
# Every streaming emitter here writes into consumers that legitimately stop
# early (read_yaml_field returns mid-stream; `| head -1` / `| grep -q` callers).
# Under a DEFAULT SIGPIPE disposition the producer is killed silently. Agent
# harnesses built on Node/Python leave SIGPIPE as SIG_IGN and children inherit
# it, so the producer is NOT killed: every remaining write returns EPIPE and
# bash (or sed/tr/grep) reports it, burying the real output.
#
# Two kinds of coverage below:
#   1. CHARACTERIZATION — pins read_yaml_list's output across every supported
#      block and inline shape. These must hold across the fork-removing
#      rewrites; they are the ground truth those rewrites may not move.
#   2. SIGPIPE cases — assert stdout / empty stderr / exit 0 under inherited
#      SIG_IGN, guarded by a positive control that proves EPIPE is reachable.

# --- t1444 characterization: read_yaml_list block-item shapes ---------------
# The block emitter's `sed 's/^[[:space:]]*-[[:space:]]*//'` is replaced by the
# regex capture the loop already computes. Both must accept the same line set
# and produce byte-identical values, including the terminator case (`-a` is not
# a list item, so it ends the list).

printf '%s\n' \
    '---' \
    'blk:' \
    '  - a' \
    '  -   b' \
    '  - ' \
    '  -  ' \
    '  - d  ' \
    "  -$(printf '\t')e" \
    '  - - nested' \
    'status: Ready' \
    '---' > "$TMP/block_shapes.md"

blk_out="$(read_yaml_list "$TMP/block_shapes.md" blk)"
expected_blk="$(printf 'a\nb\n\n\nd  \ne\n- nested')"
assert_eq "block shapes: multi-space, empty, trailing-ws, tab and nested items" \
    "$expected_blk" "$blk_out"

printf '%s\n' '---' 'blk:' '  - a' '  -notanitem' '  - c' '---' \
    > "$TMP/block_terminator.md"
assert_eq "block shapes: '-a' (no space) is not a list item and ends the list" \
    "a" "$(read_yaml_list "$TMP/block_terminator.md" blk)"

# --- t1444 characterization: read_yaml_list inline-list shapes --------------
# The inline branch's five-process pipeline
#   echo | tr -d "[]'\"" | tr ',' '\n' | sed | sed | grep -v '^$'
# is replaced by a pure-bash loop. Each of these inputs must round-trip
# identically through the replacement.

inline_case() {
    # $1 = description, $2 = raw inline value, $3 = expected newline-joined
    printf '%s\n' '---' "il: $2" 'status: Ready' '---' > "$TMP/inline_case.md"
    assert_eq "inline shape: $1" "$3" "$(read_yaml_list "$TMP/inline_case.md" il)"
}

inline_case "plain numbers"            '[1, 2, 3]'                "$(printf '1\n2\n3')"
inline_case "no spaces"                '[a,b,c]'                  "$(printf 'a\nb\nc')"
inline_case "padded separators"        '[ a , b ]'                "$(printf 'a\nb')"
inline_case "empty list"               '[]'                       ""
inline_case "whitespace-only list"     '[ ]'                      ""
inline_case "single-quoted items"      "['x', 'y']"               "$(printf 'x\ny')"
inline_case "double-quoted items"      '["p", "q"]'               "$(printf 'p\nq')"
inline_case "consecutive commas"       '[a,,b]'                   "$(printf 'a\nb')"
inline_case "trailing comma"           '[a, b,]'                  "$(printf 'a\nb')"
inline_case "leading comma"            '[,a]'                     "a"
inline_case "task ids, ragged spacing" '[t900_1, t900_2,   t900_3]' "$(printf 't900_1\nt900_2\nt900_3')"
inline_case "items containing spaces"  '[foo bar, baz qux]'       "$(printf 'foo bar\nbaz qux')"
inline_case "inner brackets stripped"  '[a[1], b]'                "$(printf 'a1\nb')"
inline_case "apostrophe in item"       "[it's, fine]"             "$(printf 'its\nfine')"
inline_case "heavily padded items"     '[  spaced  ,  out  ]'     "$(printf 'spaced\nout')"
inline_case "single item"              '[single]'                 "single"

# --- t1444 SIGPIPE harness --------------------------------------------------
# Skips (never fails) when python3 is absent: it is the only way to hand a child
# an inherited SIG_IGN disposition. Everything above still runs.

if command -v python3 >/dev/null 2>&1; then

    cat > "$TMP/sigpipe_run.py" <<'PYEOF'
import signal, subprocess, sys
sys.exit(subprocess.call(["bash", sys.argv[1]],
    preexec_fn=lambda: signal.signal(signal.SIGPIPE, signal.SIG_IGN)))
PYEOF

    # Pipe capacity drives fixture sizing: EPIPE is only DETERMINISTIC once the
    # producer has more pending output than the pipe can buffer, so that it is
    # blocked in write() when the reader exits. Below that threshold it is a
    # race (measured: a ~1.6KB producer storms in only 24 of 25 runs).
    # F_GETPIPE_SZ is Linux-only -> fall back to a fixed target and let the
    # positive control below carry the proof. Never fail on a missing constant.
    PIPE_CAP="$(python3 - <<'PYEOF'
import fcntl, os
try:
    r, w = os.pipe()
    print(fcntl.fcntl(w, fcntl.F_GETPIPE_SZ))
except (AttributeError, OSError, ValueError):
    print(0)
PYEOF
)"
    if [[ "$PIPE_CAP" -gt 0 ]]; then
        BULK_BYTES=$(( PIPE_CAP * 2 ))          # linear cases: comfortable margin
        INLINE_BYTES=$(( PIPE_CAP + PIPE_CAP / 10 ))
    else
        BULK_BYTES=131072                        # unmeasurable: fixed 128 KB
        INLINE_BYTES=73728                       #               fixed  72 KB
    fi
    # The inline fixture is sized tighter on purpose: read_yaml_list's flow-list
    # bracket counting is quadratic in the value's length (2.1s at 70KB, 8.3s at
    # 140KB, 34.5s at 324KB), and anything above pipe capacity is already
    # deterministic, so a larger fixture buys runtime rather than confidence.

    python3 - "$TMP" "$BULK_BYTES" "$INLINE_BYTES" <<'PYEOF'
import os, sys
tmp, bulk, inline = sys.argv[1], int(sys.argv[2]), int(sys.argv[3])
pad = "y" * 60

def upto(n, per):
    return max(4, n // per + 1)

# 1. frontmatter, `priority` first so the reader returns almost immediately
n = upto(bulk, 80)
with open(os.path.join(tmp, "sp_big.md"), "w") as f:
    f.write("---\npriority: high\n")
    for i in range(n):
        f.write("key_%06d: value_%06d_%s\n" % (i, i, pad))
    f.write("---\n")

# 2. block list
n = upto(bulk, 80)
with open(os.path.join(tmp, "sp_list.md"), "w") as f:
    f.write("---\nlabels:\n")
    for i in range(n):
        f.write("  - item_%06d_%s\n" % (i, pad))
    f.write("status: Ready\n---\n")

# 3. attachment records
n = upto(bulk, 160)
with open(os.path.join(tmp, "sp_attach.md"), "w") as f:
    f.write("---\nattachments:\n")
    for i in range(n):
        f.write("  - hash: sha256:%064d\n    name: shot_%06d_%s.png\n" % (i, i, pad))
    f.write("---\n")

# 4. one inline flow list
n = upto(inline, 70)
items = ", ".join("entry_%06d_%s" % (i, pad) for i in range(n))
with open(os.path.join(tmp, "sp_inline.md"), "w") as f:
    f.write("---\ndepends: [%s]\nstatus: Ready\n---\n" % items)
PYEOF

    # run_ignoring_sigpipe <snippet-file> -> sets SP_OUT / SP_ERR / SP_RC
    run_ignoring_sigpipe() {
        local snippet="$1" errfile="$TMP/sp_stderr.txt"
        SP_OUT="$(python3 "$TMP/sigpipe_run.py" "$snippet" 2>"$errfile")"
        SP_RC=$?
        SP_ERR="$(cat "$errfile")"
    }

    sp_snippet() {
        # $1 = snippet name, $2... = body lines
        local name="$1"; shift
        {
            printf '%s\n' "cd '$TMP'"
            printf '%s\n' "source '$LIB_DIR/yaml_utils.sh'"
            printf '%s\n' "$@"
        } > "$TMP/$name.sh"
        printf '%s' "$TMP/$name.sh"
    }

    # --- POSITIVE CONTROL (t1444 mitigation: epipe_trigger_positive_control) ---
    # An empty-stderr assertion cannot distinguish "the guard suppressed the
    # storm" from "EPIPE never happened". Prove the trigger is live first, with
    # a deliberately UNGUARDED producer at the same volume. If this does not
    # storm, every empty-stderr assertion below is unproven.
    {
        printf '%s\n' "pad=\"$(printf 'y%.0s' $(seq 1 60))\""
        printf '%s\n' "for ((i = 0; i < $(( BULK_BYTES / 80 + 1 )); i++)); do printf 'item_%06d_%s\\n' \"\$i\" \"\$pad\"; done | head -1"
    } > "$TMP/sp_control.sh"
    run_ignoring_sigpipe "$TMP/sp_control.sh"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$SP_ERR" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: positive control — harness cannot trigger EPIPE (fixture too small or SIGPIPE not ignored); the empty-stderr assertions below are unproven"
    fi

    # --- the four guarded cases ---------------------------------------------
    sp_assert() {
        # $1 = label, $2 = snippet path, $3 = expected stdout
        local label="$1" snippet="$2" want="$3"
        run_ignoring_sigpipe "$snippet"
        assert_eq "SIGPIPE/$label: stdout unchanged" "$want" "$SP_OUT"
        assert_eq "SIGPIPE/$label: stderr is empty" "" "$SP_ERR"
        assert_eq "SIGPIPE/$label: exit 0" "0" "$SP_RC"
    }

    sp_assert "read_yaml_field (join_yaml_flow_lists)" \
        "$(sp_snippet sp_case_field 'read_yaml_field sp_big.md priority')" \
        "high"

    sp_assert "read_yaml_list block | head -1" \
        "$(sp_snippet sp_case_block 'read_yaml_list sp_list.md labels | head -1')" \
        "item_000000_$(printf 'y%.0s' $(seq 1 60))"

    sp_assert "read_yaml_mappings | head -1" \
        "$(sp_snippet sp_case_map 'read_yaml_mappings sp_attach.md attachments | head -1')" \
        "hash=sha256:$(printf '0%.0s' $(seq 1 64))"

    sp_assert "read_yaml_list inline | head -1" \
        "$(sp_snippet sp_case_inline 'read_yaml_list sp_inline.md depends | head -1')" \
        "entry_000000_$(printf 'y%.0s' $(seq 1 60))"

    # --- non-truncation guard (t1444 mitigation: non_truncation_guard) -------
    # The guards must stop ONLY on a genuinely closed pipe. An UNPIPED read of
    # the same fixtures must still yield every item.
    full_block=$(read_yaml_list "$TMP/sp_list.md" labels | grep -c .)
    full_inline=$(read_yaml_list "$TMP/sp_inline.md" depends | grep -c .)
    full_map=$(read_yaml_mappings "$TMP/sp_attach.md" attachments | grep -c '^hash=')
    expect_block=$(grep -c '^  - item_' "$TMP/sp_list.md")
    expect_map=$(grep -c '^  - hash:' "$TMP/sp_attach.md")
    assert_eq_trim "non-truncation: unpiped block list yields every item" \
        "$expect_block" "$full_block"
    assert_eq_trim "non-truncation: unpiped mappings yield every record" \
        "$expect_map" "$full_map"
    TOTAL=$((TOTAL + 1))
    if [[ "$full_inline" -gt 100 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: non-truncation: unpiped inline list truncated (got $full_inline items)"
    fi

    # --- enforced write-guard boundary (t1444: enforce_pipe_contract) -------
    # The closed-pipe guard must apply ONLY where stdout can be closed by a
    # reader. With a REGULAR FILE as stdout a failed write is a genuine error
    # (ENOSPC/quota) and must stay loud, never become silent truncation.
    # Pin both directions of the discriminator this relies on.
    guard_probe='if [[ -f /dev/fd/1 ]]; then echo REGULAR_FILE; else echo NOT_REGULAR; fi'
    assert_eq "write-guard boundary: pipe stdout is not a regular file (guard active)" \
        "NOT_REGULAR" "$(bash -c "$guard_probe" | cat)"
    bash -c "$guard_probe" > "$TMP/guard_probe.out"
    assert_eq "write-guard boundary: file stdout is a regular file (guard inactive)" \
        "REGULAR_FILE" "$(cat "$TMP/guard_probe.out")"

    # Redirected to a regular file, output must still be complete.
    read_yaml_list "$TMP/sp_list.md" labels > "$TMP/redirected.txt"
    assert_eq_trim "write-guard boundary: file-redirected read is complete" \
        "$expect_block" "$(grep -c . "$TMP/redirected.txt")"
else
    echo "SKIP: python3 absent — SIGPIPE cases not run"
fi

# --- t1444: forcing SIGPIPE to DEFAULT for the pins that require it ---------
# The pins below are meaningless unless SIGPIPE has its DEFAULT disposition,
# and this suite may itself be launched from a harness that ignores SIGPIPE
# (Node/Python parents do), which children inherit:
#   * a bash process that inherited SIG_IGN CANNOT install a PIPE trap at all —
#     `trap 'handler' PIPE` is silently a no-op and `trap -p PIPE` reports
#     `trap -- '' SIGPIPE` — so the trap-restoration pins would compare against
#     a disposition the test never managed to set (observed: 73/76, red purely
#     from the environment);
#   * and an emitter under SIG_IGN is never killed, so the not-killed pins would
#     pass against the UNFIXED library (verified: they do) — vacuously green.
# Force the disposition instead of branching the assertions on it.

SIGDFL_AVAILABLE=false
if command -v python3 >/dev/null 2>&1; then
    cat > "$TMP/sigdfl_run.py" <<'PYEOF'
import signal, subprocess, sys
sys.exit(subprocess.call(["bash", sys.argv[1]],
    preexec_fn=lambda: signal.signal(signal.SIGPIPE, signal.SIG_DFL)))
PYEOF
    SIGDFL_AVAILABLE=true
fi

# Emit the script's stdout with SIGPIPE guaranteed to be at its default.
run_with_default_sigpipe() {
    if [[ "$SIGDFL_AVAILABLE" == true ]]; then
        python3 "$TMP/sigdfl_run.py" "$1"
    else
        bash "$1"
    fi
}

# Without python3 we cannot reset an inherited SIG_IGN from inside bash. Detect
# that case and skip rather than report a false failure. An empty `trap -p PIPE`
# here means the default disposition; `trap -- '' SIGPIPE` means we inherited
# the ignore.
SIGPIPE_DISPOSITION_PINS=true
if [[ "$SIGDFL_AVAILABLE" == false && -n "$(trap -p PIPE)" ]]; then
    SIGPIPE_DISPOSITION_PINS=false
    echo "SKIP: python3 absent and SIGPIPE inherited as ignored — kill/trap pins not run"
fi

if [[ "$SIGPIPE_DISPOSITION_PINS" == true ]]; then

# --- t1444: the emitter must not be KILLED by a reader that stops early -----
# Guarding the write only helps if the write is reached. Under the DEFAULT
# SIGPIPE disposition the producer is killed (exit 141) before any `||` runs,
# and under `set -o pipefail` that 141 becomes the pipeline's status even though
# the reader succeeded — so `read_yaml_mappings … | grep -q '^handle='` reports
# "no artifacts" whenever the producer outlives grep -q. That silently skipped
# aitask_fold_mark.sh's attachment/artifact transfer (aitask_fold_mark.sh:536,
# 539). Pre-fix measurement: 60/60 correct at 1 record, 0/60 at 12.
#
# Sized at 12 records deliberately — 1 record was inside the race window and
# passed by luck.

cat > "$TMP/kill_probe.md" <<'EOF'
---
priority: medium
artifacts:
EOF
i=0
while [[ $i -lt 12 ]]; do
    printf '  - handle: art:kp-%s\n    kind: report\n    name: rep %s\n' "$i" "$i" \
        >> "$TMP/kill_probe.md"
    i=$((i + 1))
done
printf 'status: Implementing\n---\n' >> "$TMP/kill_probe.md"

# Run the real caller idiom under the real caller's shell options.
cat > "$TMP/kill_probe.sh" <<EOF
set -euo pipefail
source '$LIB_DIR/yaml_utils.sh'
det=0
for n in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    if read_yaml_mappings '$TMP/kill_probe.md' artifacts 2>/dev/null | grep -q '^handle='; then
        det=\$((det + 1))
    fi
done
echo "\$det"
EOF
assert_eq "early-exiting reader (| grep -q under pipefail) never kills the emitter" \
    "20" "$(run_with_default_sigpipe "$TMP/kill_probe.sh")"

# The same must hold for the list reader with a `| head -1` consumer.
{
    printf -- '---\nlabels:\n'
    i=0; while [[ $i -lt 40 ]]; do printf -- '  - label_%s\n' "$i"; i=$((i + 1)); done
    printf -- 'status: Ready\n---\n'
} > "$TMP/sp_list_small.md"
cat > "$TMP/kill_probe_list.sh" <<EOF
set -euo pipefail
source '$LIB_DIR/yaml_utils.sh'
ok=0
for n in 1 2 3 4 5 6 7 8 9 10; do
    if read_yaml_list '$TMP/sp_list_small.md' labels | head -1 > /dev/null; then
        ok=\$((ok + 1))
    fi
done
echo "\$ok"
EOF
assert_eq "early-exiting reader (| head -1 under pipefail) never kills the list emitter" \
    "10" "$(run_with_default_sigpipe "$TMP/kill_probe_list.sh")"

# The SIGPIPE ignore must never reach the caller's shell — leaking SIG_IGN into
# a caller would spread the very condition this file exists to prevent. The
# readers only touch the disposition inside a subshell (BASH_SUBSHELL > 0),
# where the change is discarded on exit, so a caller's own trap is untouched by
# construction.
#
# Pinned EXACTLY, on a dedicated last line: asserting merely that the output
# CONTAINS the handler's text would also pass if the trap simply FIRED during a
# reader call, which is a different (and undesired) event.
cat > "$TMP/trap_leak.sh" <<EOF
set -uo pipefail
source '$LIB_DIR/yaml_utils.sh'
trap 'echo CALLER_HANDLER' PIPE
read_yaml_field '$TMP/task.md' priority > /dev/null
read_yaml_list '$TMP/block_list.md' labels > /dev/null
read_yaml_list '$TMP/inline_list.md' depends > /dev/null
read_yaml_mappings '$TMP/artifacts.md' artifacts > /dev/null
printf '%s\n' 'k: [1]' | join_yaml_flow_lists > /dev/null
printf 'FINAL:%s\n' "\$(trap -p PIPE)"
EOF
leak_out="$(run_with_default_sigpipe "$TMP/trap_leak.sh")"
assert_eq "caller's own PIPE trap is byte-identical after every reader call" \
    "FINAL:trap -- 'echo CALLER_HANDLER' SIGPIPE" \
    "$(printf '%s' "$leak_out" | grep '^FINAL:')"
assert_not_contains "no reader call fires the caller's PIPE trap" \
    "CALLER_HANDLER
" "$(printf '%s' "$leak_out" | grep -v '^FINAL:')"

cat > "$TMP/trap_none.sh" <<EOF
set -uo pipefail
source '$LIB_DIR/yaml_utils.sh'
read_yaml_field '$TMP/task.md' priority > /dev/null
read_yaml_list '$TMP/block_list.md' labels > /dev/null
read_yaml_mappings '$TMP/artifacts.md' artifacts > /dev/null
printf 'FINAL:[%s]' "\$(trap -p PIPE)"
EOF
assert_eq "no PIPE trap is left behind when the caller had none" \
    "FINAL:[]" "$(run_with_default_sigpipe "$TMP/trap_none.sh")"

# And the caller's disposition must be untouched even when a reader was used in
# the subshell contexts that DO flip it internally.
cat > "$TMP/trap_after_pipe.sh" <<EOF
set -uo pipefail
source '$LIB_DIR/yaml_utils.sh'
trap 'echo CALLER_HANDLER' PIPE
read_yaml_mappings '$TMP/kill_probe.md' artifacts | grep -q '^handle=' || true
read_yaml_list '$TMP/sp_list_small.md' labels | head -1 > /dev/null
v="\$(read_yaml_field '$TMP/task.md' priority)"
printf 'FINAL:%s\n' "\$(trap -p PIPE)"
EOF
assert_eq "caller's PIPE trap survives pipeline / command-substitution reader use" \
    "FINAL:trap -- 'echo CALLER_HANDLER' SIGPIPE" \
    "$(run_with_default_sigpipe "$TMP/trap_after_pipe.sh" | grep '^FINAL:')"

fi   # SIGPIPE_DISPOSITION_PINS

# --- t1444 set -e smoke (mitigation: set_e_source_smoke) -------------------
# The new guards add branching to functions sourced into ~40 `set -euo pipefail`
# scripts. An idiom that trips set -e must fail HERE, not in a production run.

cat > "$TMP/set_e_smoke.sh" <<EOF
set -euo pipefail
source '$LIB_DIR/yaml_utils.sh'
read_yaml_field '$TMP/task.md' priority          > /dev/null
read_yaml_field '$TMP/task.md' no_such_field     > /dev/null
read_yaml_field '$TMP/crew_status.yaml' status   > /dev/null
read_yaml_list  '$TMP/inline_list.md' depends    > /dev/null
read_yaml_list  '$TMP/block_list.md'  labels     > /dev/null
read_yaml_list  '$TMP/block_list.md'  no_such    > /dev/null
read_yaml_mappings '$TMP/artifacts.md' artifacts > /dev/null
read_yaml_mappings '$TMP/artifacts.md' no_such   > /dev/null
read_yaml_mappings '$TMP/task.md' attachments    > /dev/null
printf '%s\n' 'depends: [1, 2]' | join_yaml_flow_lists > /dev/null
echo SMOKE_OK
EOF
smoke_out="$(bash "$TMP/set_e_smoke.sh" 2>&1)"; smoke_rc=$?
assert_eq "set -e smoke: all readers survive set -euo pipefail on hit and miss paths" \
    "SMOKE_OK" "$smoke_out"
assert_eq "set -e smoke: exit 0" "0" "$smoke_rc"

# --- Syntax checks for the touched libraries -------------------------------

for f in lib/yaml_utils.sh lib/task_utils.sh lib/agentcrew_utils.sh aitask_archive.sh; do
    TOTAL=$((TOTAL + 1))
    if bash -n "$PROJECT_DIR/.aitask-scripts/$f"; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: syntax check $f"
    fi
done

echo ""
echo "=========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=========================="
[[ "$FAIL" -eq 0 ]] || exit 1
