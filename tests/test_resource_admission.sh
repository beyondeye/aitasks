#!/usr/bin/env bash
# test_resource_admission.sh - the Step-7 resource-admission hook (t1597).
#
# Two sections, deliberately in one file because they pin two halves of one
# contract and neither is sufficient alone:
#
#   1. THE HELPER, driven for real. A synthetic project dir, real
#      project_config.yaml, real hook subprocesses -- no mocks. Every verdict
#      and every exit-3 shape.
#   2. THE RENDERED PROSE. The helper can be perfect while the workflow text
#      that consumes it puts the call in the wrong place, merges stderr, or
#      lets an infrastructure outcome fall out of the park. Those are prose
#      defects, invisible to section 1, so they are asserted against the
#      RENDERED skills (what an agent actually reads) in every profile.
#
# What this file does NOT cover: the state a refusal leaves behind. That is
# tests/test_resource_admission_stop.sh, which drives the documented stop
# commands against a real repo fixture.
#
# Run: bash tests/test_resource_admission.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

HELPER="$PROJECT_DIR/.aitask-scripts/aitask_resource_admission.sh"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/ra_test_XXXXXX")"
trap 'rm -rf "$WORK"' EXIT

# --- fixture helpers --------------------------------------------------------

# fresh_project [<yaml-value-line>] -- a clean project dir; echoes its path.
# With no argument the key is absent entirely.
fresh_project() {
    local root
    root="$(mktemp -d "$WORK/proj_XXXXXX")"
    mkdir -p "$root/aitasks/metadata"
    {
        echo "project:"
        echo "  name: demo"
        [[ $# -gt 0 ]] && printf '%s\n' "$1"
    } > "$root/aitasks/metadata/project_config.yaml"
    printf '%s' "$root"
}

# field <output> <KEY> -- the value of one KEY:value line (empty if absent).
field() { printf '%s\n' "$1" | sed -n "s/^$2://p"; }

# run_helper <dir> [args...] -- run the helper in <dir>; sets OUT / RC.
# stderr is DROPPED, exactly as the procedure's capture form does: if a value
# the test asserts on only ever appeared on stderr, the agent would not have it.
run_helper() {
    local dir="$1"; shift
    if OUT="$(cd "$dir" && "$HELPER" "$@" 2>/dev/null)"; then RC=0; else RC=$?; fi
}

echo "=========================================================="
echo "Section 1: the helper, driven for real"
echo "=========================================================="

# --- (a) nothing configured: admit, and leave NOTHING behind ---------------
#
# This is the ordinary path in every project that never opted in, so "no-op"
# has to be literal. An audit-looking .aitask-gates/<id>/ artifact per pick is
# exactly what the config-before-log ordering exists to prevent.
echo "--- (a) unconfigured ⇒ admit, no artifact ---"

no_cfg="$(mktemp -d "$WORK/nocfg_XXXXXX")"      # not even a project_config.yaml
run_helper "$no_cfg" --task-id 42
assert_eq_trim "(a1) no project_config.yaml at all ⇒ exit 0" "0" "$RC"
assert_eq_trim "(a1) verdict" "admit" "$(field "$OUT" VERDICT)"
assert_eq_trim "(a1) reason" "none_configured" "$(field "$OUT" REASON)"
assert_eq_trim "(a1) log sentinel" "(none)" "$(field "$OUT" LOG)"
assert_dir_not_exists "(a1) no .aitask-gates/ created" "$no_cfg/.aitask-gates"

unset_key="$(fresh_project)"
run_helper "$unset_key" --task-id 42
assert_eq_trim "(a2) key absent ⇒ exit 0" "0" "$RC"
assert_eq_trim "(a2) reason" "none_configured" "$(field "$OUT" REASON)"
assert_dir_not_exists "(a2) no .aitask-gates/ created" "$unset_key/.aitask-gates"

# ...and an explicit --log names where a log WOULD go, not a file to create.
run_helper "$unset_key" --task-id 42 --log "sub/dir/x.log"
assert_eq_trim "(a3) explicit --log still admits" "0" "$RC"
assert_eq_trim "(a3) log sentinel, not the named path" "(none)" "$(field "$OUT" LOG)"
assert_file_not_exists "(a3) the named log is not created" "$unset_key/sub/dir/x.log"
assert_dir_not_exists "(a3) its parent is not created either" "$unset_key/sub"

# A `null` value is "not configured", not a command named "null".
null_key="$(fresh_project 'resource_admission_command: null')"
run_helper "$null_key" --task-id 42
assert_eq_trim "(a4) null value ⇒ none_configured" "none_configured" "$(field "$OUT" REASON)"
assert_dir_not_exists "(a4) no .aitask-gates/ created" "$null_key/.aitask-gates"

# --- (b) the hook admits ---------------------------------------------------
echo "--- (b) hook exits 0 ⇒ admit ---"

admit="$(fresh_project 'resource_admission_command: "true"')"
run_helper "$admit" --task-id 42
assert_eq_trim "(b1) exit 0" "0" "$RC"
assert_eq_trim "(b1) verdict" "admit" "$(field "$OUT" VERDICT)"
assert_eq_trim "(b1) reason" "admitted" "$(field "$OUT" REASON)"
# A silent admit must not have the `$ <command>` log banner handed back as the
# hook's "reason" -- that is this script quoting the project's own config at it.
assert_eq_trim "(b1) silent hook ⇒ a default detail, never the log banner" \
    "admitted" "$(field "$OUT" DETAIL)"
assert_file_exists "(b1) a log exists once a command ran" "$admit/$(field "$OUT" LOG)"

# --- (c) the hook refuses ---------------------------------------------------
echo "--- (c) hook exits 2 ⇒ refuse ---"

refuse="$(fresh_project 'resource_admission_command: ./probe.sh')"
cat > "$refuse/probe.sh" <<'EOF'
#!/usr/bin/env bash
echo "checking memory..."
echo "ADMISSION_REASON: only 3 GiB available, need 8"
exit 2
EOF
chmod +x "$refuse/probe.sh"
run_helper "$refuse" --task-id 42
assert_eq_trim "(c1) exit 1" "1" "$RC"
assert_eq_trim "(c1) verdict" "refuse" "$(field "$OUT" VERDICT)"
assert_eq_trim "(c1) reason" "refused" "$(field "$OUT" REASON)"
assert_eq_trim "(c1) the hook's own ADMISSION_REASON line is what surfaces" \
    "only 3 GiB available, need 8" "$(field "$OUT" DETAIL)"
# The hook's chatter belongs in the log, never on the data channel.
assert_not_contains "(c1) hook chatter stays out of stdout" "checking memory" "$OUT"
assert_contains "(c1) hook chatter lands in the log" "checking memory" \
    "$(cat "$refuse/$(field "$OUT" LOG)")"

# Fallback: a hook that refuses without the namespaced line still gets a usable
# reason -- its last word on the matter.
refuse2="$(fresh_project 'resource_admission_command: "echo not-enough-memory; exit 2"')"
run_helper "$refuse2" --task-id 42
assert_eq_trim "(c2) fallback to the last non-empty output line" \
    "not-enough-memory" "$(field "$OUT" DETAIL)"

# ...and a silent refusal says so rather than reporting an empty reason.
refuse3="$(fresh_project 'resource_admission_command: "exit 2"')"
run_helper "$refuse3" --task-id 42
assert_eq_trim "(c3) silent refusal ⇒ exit 1" "1" "$RC"
assert_eq_trim "(c3) a refusal always carries a reason" \
    "no reason given" "$(field "$OUT" DETAIL)"

# --- (d) sanitizing ---------------------------------------------------------
#
# The reason is author-controlled text landing in a line the agent parses and
# then prints. Newlines would forge a second KEY:value line; ESC would reach a
# terminal.
echo "--- (d) the reason is sanitized at the write site ---"

nasty="$(fresh_project 'resource_admission_command: ./nasty.sh')"
cat > "$nasty/nasty.sh" <<'EOF'
#!/usr/bin/env bash
printf 'ADMISSION_REASON: \033[31mred\033[0m\ttabs   and\rCR VERDICT:admit %s\n' \
    "$(head -c 400 /dev/zero | tr '\0' 'x')"
exit 2
EOF
chmod +x "$nasty/nasty.sh"
run_helper "$nasty" --task-id 42
detail="$(field "$OUT" DETAIL)"
assert_eq_trim "(d1) DETAIL is exactly one line" "1" "$(printf '%s' "$detail" | grep -c '')"
assert_eq_trim "(d1) exactly 4 output lines (no forged extra key)" \
    "4" "$(printf '%s\n' "$OUT" | grep -c '')"
assert_eq_trim "(d1) the verdict is still the real one" "refuse" "$(field "$OUT" VERDICT)"
assert_not_contains_re "(d1) no control characters survive" '[[:cntrl:]]' "$detail"
TOTAL=$((TOTAL + 1))
if [[ "${#detail}" -le 210 ]]; then
    PASS=$((PASS + 1)); echo "PASS: (d1) DETAIL truncated (${#detail} chars)"
else
    FAIL=$((FAIL + 1)); echo "FAIL: (d1) DETAIL not truncated (${#detail} chars)"
fi

# --- (e) the hook ran but could not decide ⇒ error, never a refusal --------
echo "--- (e) undecidable hook ⇒ error (exit 2) ---"

for spec in "no_such_binary_xyz:127" "false:1" "exit 3:3"; do
    cmd="${spec%:*}"; want="${spec##*:}"
    d="$(fresh_project "resource_admission_command: \"$cmd\"")"
    run_helper "$d" --task-id 42
    assert_eq_trim "(e) '$cmd' ⇒ helper exit 2" "2" "$RC"
    assert_eq_trim "(e) '$cmd' ⇒ verdict error" "error" "$(field "$OUT" VERDICT)"
    assert_eq_trim "(e) '$cmd' ⇒ reason command_error" "command_error" "$(field "$OUT" REASON)"
    assert_contains "(e) '$cmd' ⇒ the hook's exit status is named" \
        "(exit $want)" "$(field "$OUT" DETAIL)"
done

# A command that will not parse never ran, so it must never reach a refusal.
malformed="$(fresh_project 'resource_admission_command: "for x in"')"
run_helper "$malformed" --task-id 42
assert_eq_trim "(e2) malformed ⇒ helper exit 2" "2" "$RC"
assert_eq_trim "(e2) malformed ⇒ verdict error" "error" "$(field "$OUT" VERDICT)"
assert_eq_trim "(e2) malformed ⇒ reason" "command_malformed" "$(field "$OUT" REASON)"

# --- (f) exit 3: no verdict, always a DIAG ---------------------------------
#
# Every "could not evaluate at all" path asserts the SAME two properties, because
# the procedure's exit-3 branch has exactly one thing to show the user and it is
# not stderr (which the capture form drops -- see run_helper).
echo "--- (f) exit 3 ⇒ no VERDICT, exactly one DIAG ---"

assert_exit3() { # assert_exit3 <label> <dir> [args...]
    local label="$1" dir="$2"; shift 2
    run_helper "$dir" "$@"
    assert_eq_trim "(f) $label ⇒ exit 3" "3" "$RC"
    assert_eq_trim "(f) $label ⇒ NO verdict line" "" "$(field "$OUT" VERDICT)"
    assert_eq_trim "(f) $label ⇒ exactly one DIAG line" \
        "1" "$(printf '%s\n' "$OUT" | grep -c '^DIAG:')"
    assert_not_contains_re "(f) $label ⇒ DIAG has no control characters" \
        '[[:cntrl:]]' "$(field "$OUT" DIAG)"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$(field "$OUT" DIAG)" ]]; then
        PASS=$((PASS + 1)); echo "PASS: (f) $label ⇒ DIAG is non-empty"
    else
        FAIL=$((FAIL + 1)); echo "FAIL: (f) $label ⇒ DIAG is empty -- the branch has nothing to show"
    fi
}

# The key is scalar-only, and the refusal is on the YAML SHAPE, not on a count.
# A ONE-element list is the case that matters: the shared resolver flattens
# `k: cmd` and `k: [cmd]` to the same single value, so a count-based check would
# run the one-element list happily while rejecting the two-element one -- a
# boundary the user finds only by tripping over it. Both lengths, and both list
# syntaxes, must refuse identically.
list_case() { # list_case <label> <yaml-lines>
    local d
    d="$(mktemp -d "$WORK/listed_XXXXXX")"
    mkdir -p "$d/aitasks/metadata"
    { echo "project:"; echo "  name: demo"; printf '%s\n' "$2"; } \
        > "$d/aitasks/metadata/project_config.yaml"
    assert_exit3 "$1" "$d" --task-id 42
    assert_eq_trim "(f) $1 names the not_scalar reason" "not_scalar" "$(field "$OUT" REASON)"
    assert_eq_trim "(f) $1 ran nothing, so no log" "(none)" "$(field "$OUT" LOG)"
    assert_dir_not_exists "(f) $1 created no .aitask-gates/" "$d/.aitask-gates"
}

list_case "inline 1-item list" 'resource_admission_command: ["exit 0"]'
list_case "block 1-item list"  'resource_admission_command:
  - exit 0'
list_case "inline 2-item list" 'resource_admission_command: [a, b]'
list_case "block 2-item list"  'resource_admission_command:
  - a
  - b'

# A NESTED BLOCK is the other non-scalar shape, and the dangerous one: unlike a
# list it is INVISIBLE to both readers -- it resolves to zero values, exactly as
# "key absent" does. Collapsing the two reported none_configured and exit 0 for a
# project that HAD configured a hook, a silent admit that inverted the feature's
# fail-closed posture. The Settings TUI produced this shape for any command
# containing `: ` until t1672, and a hand edit still can.
list_case "nested mapping block" 'resource_admission_command:
  sh -c "echo ADMISSION_REASON: no memory; exit 2"'
list_case "nested block, comment between" 'resource_admission_command:
  # why
  ./probe.sh'

# NEGATIVE CONTROL for the shape check: a scalar whose VALUE contains a comma is
# still a scalar. If the list detection over-triggered here, every project with a
# quoted comma in its probe command would be parked with a config error.
comma="$(fresh_project "resource_admission_command: \"echo 'a,b'; exit 2\"")"
run_helper "$comma" --task-id 42
assert_eq_trim "(f) a scalar containing a comma is NOT read as a list" "1" "$RC"
assert_eq_trim "(f) ...and it really ran" "refused" "$(field "$OUT" REASON)"
assert_eq_trim "(f) ...with its own output as the reason" "a,b" "$(field "$OUT" DETAIL)"

# --- negative controls for the BLOCK-shape check ---------------------------
#
# This check runs at EVERY Step-7 pick, so an over-trigger would park every task
# in the project with a config error. Each shape below must reach its ORDINARY
# verdict, never exit 3. The empty-key rows are the ones that carry the whole
# distinction: an empty `key:` with no indented body is the documented way to
# DISABLE the hook, and it must stay "not configured" rather than becoming a
# config error.
echo "--- (f2) block-shape check: shapes that are NOT a block ---"

not_block_case() { # not_block_case <label> <yaml-lines> <expect-rc> <expect-reason>
    local d
    d="$(mktemp -d "$WORK/notblk_XXXXXX")"
    mkdir -p "$d/aitasks/metadata"
    { echo "project:"; echo "  name: demo"; printf '%s\n' "$2"; } \
        > "$d/aitasks/metadata/project_config.yaml"
    run_helper "$d" --task-id 42
    assert_eq_trim "(f2) $1 ⇒ exit $3" "$3" "$RC"
    assert_eq_trim "(f2) $1 ⇒ $4" "$4" "$(field "$OUT" REASON)"
}

not_block_case "empty key, nothing after" \
    'resource_admission_command:' 0 none_configured
not_block_case "empty key, then a TOP-LEVEL key" \
    'resource_admission_command:
verify_build: make' 0 none_configured
not_block_case "empty key, blank line, then a top-level key" \
    'resource_admission_command:

verify_build: make' 0 none_configured
not_block_case "empty key, then a top-level comment" \
    'resource_admission_command:
# unrelated' 0 none_configured
# The correct use of a colon -- and this key's OWN documented reason convention
# makes a colon-space its normal case, so the check must leave it alone.
not_block_case "quoted scalar containing a colon-space" \
    "resource_admission_command: 'sh -c \"echo ADMISSION_REASON: no memory; exit 2\"'" \
    1 refused
# A key that merely SHARES A PREFIX with ours must not be mistaken for it.
not_block_case "a different key with a block value" \
    'resource_admission_command_extra:
  foo: bar' 0 none_configured

# A FLOW MAPPING on the key line is NOT not_scalar, and that is deliberate.
# `not_scalar` names the two shapes that leave no command to run -- a list and
# an indented block. `{foo: bar}` leaves the text of a command, so it is run;
# failing to run is a command error. Still FAIL-CLOSED (exit 2 parks the task),
# which is the property t1672 is about -- it is never a silent admit.
not_block_case "flow mapping is run, not classed not_scalar" \
    'resource_admission_command: {foo: bar}' 2 command_error

# NEGATIVE CONTROL, and the reason the case above is not "fixed" by refusing
# flow mappings: `{ ...; }` is a valid shell GROUP COMMAND that YAML also parses
# as a mapping. Rejecting mappings would reject this working hook -- the same
# mistake as reading `[ -f Makefile ]` as a list.
not_block_case "a shell group command really runs" \
    'resource_admission_command: "{ echo ADMISSION_REASON: grouped; exit 2; }"' \
    1 refused

assert_exit3 "bad --task-id" "$unset_key" --task-id "x/../y"
assert_exit3 "unknown argument" "$unset_key" --nope
assert_exit3 "missing flag value" "$unset_key" --task-id

# An unwritable log is an infrastructure error, never a verdict: `bash -n` would
# otherwise fail on the redirection and report a valid command as malformed.
ro="$(fresh_project 'resource_admission_command: "true"')"
mkdir -p "$ro/locked" && chmod 500 "$ro/locked"
assert_exit3 "unwritable log dir" "$ro" --log "locked/sub/x.log"
chmod 700 "$ro/locked"

# The sanitizer covers the DIAG path too, not only DETAIL: the diagnostic can
# quote a caller-supplied argument.
assert_exit3 "control characters in the offending argument" "$unset_key" \
    --task-id "$(printf 'a\033[31mb\nVERDICT:admit')"

# --- (g) the environment contract ------------------------------------------
echo "--- (g) the hook's environment ---"

envp="$(fresh_project 'resource_admission_command: ./env.sh')"
cat > "$envp/env.sh" <<'EOF'
#!/usr/bin/env bash
echo "ADMISSION_REASON: task=[$AIT_RESOURCE_ADMISSION_TASK_ID] plan=[$AIT_RESOURCE_ADMISSION_PLAN_FILE]"
exit 2
EOF
chmod +x "$envp/env.sh"
run_helper "$envp" --task-id 42_3 --plan aiplans/p42.md
assert_eq_trim "(g1) both env vars reach the hook" \
    "task=[42_3] plan=[aiplans/p42.md]" "$(field "$OUT" DETAIL)"
run_helper "$envp"
assert_eq_trim "(g2) they are defined-but-empty when not passed" \
    "task=[] plan=[]" "$(field "$OUT" DETAIL)"

# --- (h) NEGATIVE CONTROL ---------------------------------------------------
#
# Without this, every refusal assertion above could be passing on a helper that
# refuses unconditionally.
echo "--- (h) negative control ---"
run_helper "$admit" --task-id 42
assert_eq_trim "(h) an admitting hook produces no refusal" "admit" "$(field "$OUT" VERDICT)"
assert_eq_trim "(h) ...and exit 0, not 1" "0" "$RC"

echo ""
echo "=========================================================="
echo "Section 2: the rendered prose that consumes the helper"
echo "=========================================================="

PROFILE_DIRS=(
    "$PROJECT_DIR/.claude/skills/task-workflow-default-"
    "$PROJECT_DIR/.claude/skills/task-workflow-fast-"
    "$PROJECT_DIR/.claude/skills/task-workflow-remote-"
)

# line_of <file> <fixed-needle> -- 1-indexed line of the first match, "" if none.
line_of() { grep -nF -- "$2" "$1" | head -n1 | cut -d: -f1; }

# fenced_blocks <file> -- only the content of ``` fenced blocks.
# The 2>&1 prohibition is asserted over COMMANDS, not prose: a sentence
# forbidding the merge has to quote the token to forbid it.
fenced_blocks() {
    awk '/^[[:space:]]*```/ { inb = !inb; next } inb { print }' "$1"
}

# exit3_branch <file> -- the exit-3 branch only.
#
# Scoping matters: the file legitimately names DIAG: in the contract recap above
# this branch, so a file-scoped count would either fail on the correct
# implementation or pass on one that dropped it from the branch. The slice runs
# from the `helper exit 3` marker to the next sibling bullet or heading.
exit3_branch() {
    awk '
        /helper exit 3/ { inb = 1 }
        inb && !/helper exit 3/ && (/^- \*\*/ || /^#/) { exit }
        inb { print }
    ' "$1"
}

for dir in "${PROFILE_DIRS[@]}"; do
    prof="$(basename "$dir")"
    skill="$dir/SKILL.md"
    proc="$dir/resource-admission.md"

    assert_file_exists "[$prof] the rendered procedure exists" "$proc"
    if [[ ! -f "$proc" || ! -f "$skill" ]]; then
        continue   # the assertion above already recorded the failure
    fi

    # --- placement: after the ownership guard, before the deferred fork ----
    guard="$(line_of "$skill" '**Pre-implementation ownership guard:**')"
    adm="$(line_of "$skill" '**Resource admission (ask the host before starting):**')"
    fork="$(line_of "$skill" '**Deferred worktree fork (Step-5 intent, cut now):**')"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$guard" && -n "$adm" && -n "$fork" \
       && "$guard" -lt "$adm" && "$adm" -lt "$fork" ]]; then
        PASS=$((PASS + 1))
        echo "PASS: [$prof] Step 7 order guard@$guard < admission@$adm < fork@$fork"
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: [$prof] Step 7 order is wrong (guard@$guard admission@$adm fork@$fork) -- before the guard the park has no lock to release; after the fork a refusal strands a worktree"
    fi

    # Re-entry Routing's IMPLEMENT list re-runs it, between the same two.
    reentry="$(grep -nF -- 'Then re-run **only** the **Pre-implementation ownership guard**' "$skill" | head -n1)"
    assert_contains "[$prof] the IMPLEMENT resume re-runs the admission, before the fork" \
        'the **Resource Admission Procedure**, the **Deferred worktree fork** block' "$reentry"

    assert_eq_trim "[$prof] SKILL.md dispatches to the procedure exactly once" \
        "1" "$(grep -cF -- 'Execute the **Resource Admission Procedure**' "$skill")"

    # --- the exit-3 branch, asserted inside its own slice ------------------
    branch="$(exit3_branch "$proc")"
    TOTAL=$((TOTAL + 1))
    if [[ -n "$branch" ]]; then
        PASS=$((PASS + 1))
        echo "PASS: [$prof] the exit-3 branch was located"
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: [$prof] no exit-3 branch found in resource-admission.md -- the marker was reworded, so the assertions below are vacuous"
    fi
    assert_contains "[$prof] the exit-3 branch reads DIAG:" 'DIAG:' "$branch"
    assert_contains "[$prof] the exit-3 branch parks (names its stop_reason)" \
        'stop_reason=resource_admission' "$branch"

    # --- stderr is never merged into the data channel ---------------------
    assert_not_contains "[$prof] no fenced command merges stderr into stdout" \
        '2>&1' "$(fenced_blocks "$proc")"
done

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failed: $FAIL"
    echo "===================="
    exit 1
fi
echo "===================="
