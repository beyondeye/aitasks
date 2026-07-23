#!/usr/bin/env bash
# test_gate_active_gates.sh - Tests for the t635_33 active-gates tuple:
#   materialize-active / active / active-gates-status (aitask_gate.sh) and the
#   enforcement fallback semantics (archive-ready / deps-unblock) plus tuple
#   atomicity + durability through aitask_update.sh.
#
# Exercises the REAL entry points (aitask_gate.sh / aitask_update.sh) from a
# fixture cwd with TASK_DIR=aitasks. The materialize path writes its digest via
# the python compute (gate_ledger.py) while the bash `active` verb re-validates
# the profileless digest halves in bash — so every exit-0 `active` assertion on
# a materialized tuple is also a cross-language hash-agreement check.
#
# Run: bash tests/test_gate_active_gates.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
UPDATE="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"

# --- fixture helpers -------------------------------------------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_gateact_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata/profiles" "$tmp/aiplans"
    printf 'name: fast\ndefault_gates: [risk_evaluated]\n' \
        > "$tmp/aitasks/metadata/profiles/fast.yaml"
    printf 'name: default\n' > "$tmp/aitasks/metadata/profiles/default.yaml"
    # Explicit render-nothing override: rendered_gates PRESENT and empty must
    # NOT fall back to the nonempty default_gates (key-presence semantics).
    printf 'name: rnone\ndefault_gates: [risk_evaluated]\nrendered_gates: []\n' \
        > "$tmp/aitasks/metadata/profiles/rnone.yaml"
    cat > "$tmp/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  risk_evaluated:
    type: machine
    blocks_dependents: true
  merge_approved:
    type: human
    blocks_dependents: true
EOF
    echo "$tmp"
}

# write_task <dir> <id> <gates-literal | __absent__> [extra frontmatter lines...]
write_task() {
    local dir="$1" id="$2" gates="$3"
    shift 3
    local path="$dir/aitasks/t${id}_x.md"
    {
        echo "---"
        echo "status: Ready"
        [[ "$gates" != "__absent__" ]] && echo "gates: ${gates}"
        local extra
        for extra in "$@"; do echo "$extra"; done
        echo "---"
        echo "Body."
    } > "$path"
}

run_gate() {
    local dir="$1"; shift
    ( cd "$dir" && TASK_DIR=aitasks "$GATE" "$@" )
}

run_update() {
    local dir="$1"; shift
    ( cd "$dir" && TASK_DIR=aitasks "$UPDATE" "$@" )
}

task_field() {  # <dir> <id> <field> -> raw line or empty
    grep -E "^${3}:" "$1/aitasks/t${2}_x.md" || true
}

# --- materialize-active ----------------------------------------------------

test_materialize_basic() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"

    # Declared gate under fast (rendered = default_gates = [risk_evaluated]).
    # Captured stdout must be EXACTLY the one status line (git/persist output
    # is quieted — the caller contract).
    write_task "$d" 1 "[risk_evaluated]"
    assert_eq "materialize: declared gate under fast (single stdout line)" \
        "MATERIALIZED:risk_evaluated" \
        "$(run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml" 2>/dev/null)"
    assert_eq "materialize: active_gates persisted" "active_gates: [risk_evaluated]" \
        "$(task_field "$d" 1 active_gates)"
    assert_eq "materialize: filtered empty" "active_gates_filtered: []" \
        "$(task_field "$d" 1 active_gates_filtered)"
    assert_eq "materialize: profile stamp" "active_gates_profile: fast" \
        "$(task_field "$d" 1 active_gates_profile)"
    assert_contains "materialize: 3-part digest" \
        "active_gates_digest: " "$(task_field "$d" 1 active_gates_digest)"
    local digest
    digest="$(task_field "$d" 1 active_gates_digest | sed 's/^active_gates_digest: //')"
    if [[ "$digest" =~ ^[0-9a-f]{12}\.[0-9a-f]{12}\.[0-9a-f]{12}$ ]]; then
        assert_eq "materialize: digest shape g.p.o" "ok" "ok"
    else
        assert_eq "materialize: digest shape g.p.o" "12hex.12hex.12hex" "$digest"
    fi

    # SAME declared task under default (no default_gates → rendered []) →
    # the filtered safety valve: active [], filtered carries the declaration.
    write_task "$d" 2 "[risk_evaluated]"
    assert_eq "materialize: declared gate filtered under default" "MATERIALIZED:(empty)" \
        "$(run_gate "$d" materialize-active 2 --profile "$prof/default.yaml")"
    assert_eq "materialize: empty active persisted (load-bearing [])" "active_gates: []" \
        "$(task_field "$d" 2 active_gates)"
    assert_eq "materialize: filtered records the removal" "active_gates_filtered: [risk_evaluated]" \
        "$(task_field "$d" 2 active_gates_filtered)"

    # Opt-out gates: [] under fast → empty active, nothing filtered — and the
    # explicit `gates: []` key itself SURVIVES the tuple write (presence-
    # tracked; dropping it would both revoke the opt-out at the next resolve
    # and instantly stale the fresh tuple's gates-half digest).
    write_task "$d" 3 "[]"
    assert_eq "materialize: [] opt-out under fast" "MATERIALIZED:(empty)" \
        "$(run_gate "$d" materialize-active 3 --profile "$prof/fast.yaml" 2>/dev/null)"
    assert_eq "materialize: opt-out filtered empty" "active_gates_filtered: []" \
        "$(task_field "$d" 3 active_gates_filtered)"
    assert_eq "opt-out: gates [] key survives the tuple write" "gates: []" \
        "$(task_field "$d" 3 gates)"
    assert_eq "opt-out: fresh tuple immediately FRESH" "FRESH" \
        "$(run_gate "$d" active-gates-status 3 --profile "$prof/fast.yaml" | head -1)"
    assert_eq "opt-out: re-pick under same profile is a NOOP" "NOOP:unchanged" \
        "$(run_gate "$d" materialize-active 3 --profile "$prof/fast.yaml" 2>/dev/null)"
    # ...and an unrelated update keeps the opt-out too (the pre-existing
    # never-emit-[] writer would have silently dropped it).
    run_update "$d" --batch 3 --priority high --silent >/dev/null
    assert_eq "opt-out: gates [] survives unrelated update" "gates: []" \
        "$(task_field "$d" 3 gates)"
    assert_eq "opt-out: post-update re-pick still NOOP (no default_gates resurrection)" \
        "NOOP:unchanged" \
        "$(run_gate "$d" materialize-active 3 --profile "$prof/fast.yaml" 2>/dev/null)"

    # Absent gates + fast → profile default flows into active; raw gates STAYS
    # absent (no backfill — this replaced the Step-7 backfill).
    write_task "$d" 4 "__absent__"
    assert_eq "materialize: profile-default gate under fast" "MATERIALIZED:risk_evaluated" \
        "$(run_gate "$d" materialize-active 4 --profile "$prof/fast.yaml")"
    local rc
    run_gate "$d" has-gates-field 4; rc=$?
    assert_eq "materialize: raw gates: NOT backfilled (still absent)" "1" "$rc"

    # Absent gates + default (no default_gates) → empty.
    write_task "$d" 5 "__absent__"
    assert_eq "materialize: absent + no defaults" "MATERIALIZED:(empty)" \
        "$(run_gate "$d" materialize-active 5 --profile "$prof/default.yaml")"

    # Key-presence: rendered_gates: [] + default_gates: [risk_evaluated] →
    # renders/enforces NOTHING (no truthiness fallback).
    write_task "$d" 6 "[risk_evaluated]"
    assert_eq "materialize: explicit rendered_gates [] override" "MATERIALIZED:(empty)" \
        "$(run_gate "$d" materialize-active 6 --profile "$prof/rnone.yaml")"
}

test_materialize_error_paths() {
    local d; d="$(new_fixture)"
    local rc out
    write_task "$d" 1 "[risk_evaluated]"

    # No profile → hard fail, NOTHING written.
    out="$(run_gate "$d" materialize-active 1 2>&1)"; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "materialize: no profile → nonzero" "ok" "ok" \
        || assert_eq "materialize: no profile → nonzero" "nonzero" "$rc"
    assert_contains "materialize: no-profile message is clear" "no profile" "$out"
    assert_eq "materialize: no-profile wrote nothing" "" "$(task_field "$d" 1 active_gates)"

    # Unreadable profile → hard fail, NOTHING written (and the failure report
    # is honest: no tuple existed, so none was "cleared").
    out="$(run_gate "$d" materialize-active 1 --profile aitasks/metadata/profiles/nope.yaml 2>&1)"; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "materialize: unreadable profile → nonzero" "ok" "ok" \
        || assert_eq "materialize: unreadable profile → nonzero" "nonzero" "$rc"
    assert_contains "materialize: honest no-tuple report" "no prior tuple present" "$out"
    assert_eq "materialize: unreadable-profile wrote nothing" "" "$(task_field "$d" 1 active_gates)"

    # A failed re-derivation must CLEAR a previously persisted tuple — its
    # profileless digest halves would still validate, so leaving it would keep
    # the PREVIOUS profile's enforcement authoritative under the new one.
    local prof="aitasks/metadata/profiles"
    write_task "$d" 2 "__absent__"
    run_gate "$d" materialize-active 2 --profile "$prof/fast.yaml" >/dev/null
    assert_eq "clear-on-fail: tuple present before failure" "active_gates: [risk_evaluated]" \
        "$(task_field "$d" 2 active_gates)"
    assert_eq "clear-on-fail: stale tuple enforced pre-failure" "BLOCKED:risk_evaluated" \
        "$(run_gate "$d" archive-ready 2)"
    out="$(run_gate "$d" materialize-active 2 --profile "$prof/nope.yaml" 2>&1)"; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "clear-on-fail: failed re-pick → nonzero" "ok" "ok" \
        || assert_eq "clear-on-fail: failed re-pick → nonzero" "nonzero" "$rc"
    assert_contains "clear-on-fail: honest clear report" "stale tuple cleared" "$out"
    assert_eq "clear-on-fail: stale tuple removed" "" "$(task_field "$d" 2 active_gates)"
    # NOTE: this is the transient CLI-level state — raw declared intent (here:
    # absent) governs, NOT the profile's defaults. That is exactly why the
    # task-workflow ABORTS the pick on a materialize failure instead of
    # continuing (SKILL.md Step 4): continuing here would under-enforce fast.
    assert_eq "clear-on-fail: raw gates (absent) now governs" "NO_GATES" \
        "$(run_gate "$d" archive-ready 2)"

    # Strict profile validation: a directory path or a file without a
    # top-level name: key must fail — never resolve to an empty ceiling that
    # would silently persist active_gates: [].
    write_task "$d" 3 "[risk_evaluated]"
    mkdir -p "$d/aitasks/metadata/profiles/dirprof.yaml"
    run_gate "$d" materialize-active 3 --profile "$prof/dirprof.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: directory path → nonzero" "ok" "ok" \
        || assert_eq "strict profile: directory path → nonzero" "nonzero" "$rc"
    assert_eq "strict profile: directory path wrote nothing" "" "$(task_field "$d" 3 active_gates)"
    printf 'not: a profile\n' > "$d/aitasks/metadata/profiles/garbage.yaml"
    run_gate "$d" materialize-active 3 --profile "$prof/garbage.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: no name: key → nonzero" "ok" "ok" \
        || assert_eq "strict profile: no name: key → nonzero" "nonzero" "$rc"
    assert_eq "strict profile: garbage profile wrote nothing" "" "$(task_field "$d" 3 active_gates)"

    # A present-but-malformed gate list must be rejected, never read as an
    # empty ceiling (which would persist active_gates: [] and disable gates).
    printf 'name: fast\ndefault_gates: [unclosed\n' > "$d/aitasks/metadata/profiles/badlist.yaml"
    run_gate "$d" materialize-active 3 --profile "$prof/badlist.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: malformed default_gates → nonzero" "ok" "ok" \
        || assert_eq "strict profile: malformed default_gates → nonzero" "nonzero" "$rc"
    printf 'name: fast\ndefault_gates: [risk_evaluated]\nrendered_gates: not_a_list\n' \
        > "$d/aitasks/metadata/profiles/badlist2.yaml"
    run_gate "$d" materialize-active 3 --profile "$prof/badlist2.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: scalar rendered_gates → nonzero" "ok" "ok" \
        || assert_eq "strict profile: scalar rendered_gates → nonzero" "nonzero" "$rc"
    printf 'name: fast\ndefault_gates: [risk_evaluated,,plan_approved]\n' \
        > "$d/aitasks/metadata/profiles/badlist3.yaml"
    run_gate "$d" materialize-active 3 --profile "$prof/badlist3.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: double-comma inline → nonzero" "ok" "ok" \
        || assert_eq "strict profile: double-comma inline → nonzero" "nonzero" "$rc"
    assert_eq "strict profile: malformed profiles wrote nothing" "" "$(task_field "$d" 3 active_gates)"

    # ...while the readers' supported BLOCK forms must still be accepted (the
    # value match is anchored to the key's own line — a `- item` block is not
    # a scalar; sequence items are valid at ANY indentation, including none).
    printf 'name: fast\ndefault_gates:\n  - risk_evaluated\n' \
        > "$d/aitasks/metadata/profiles/blockform.yaml"
    write_task "$d" 4 "__absent__"
    assert_eq "strict profile: block-form list accepted" "MATERIALIZED:risk_evaluated" \
        "$(run_gate "$d" materialize-active 4 --profile "$prof/blockform.yaml" 2>/dev/null)"
    printf 'name: fast\ndefault_gates:\n- risk_evaluated\n' \
        > "$d/aitasks/metadata/profiles/blockform0.yaml"
    write_task "$d" 5 "__absent__"
    assert_eq "strict profile: indentless block items accepted" "MATERIALIZED:risk_evaluated" \
        "$(run_gate "$d" materialize-active 5 --profile "$prof/blockform0.yaml" 2>/dev/null)"
    # A bare dash item reads as [] and would silently empty the ceiling.
    printf 'name: fast\ndefault_gates:\n-\n' > "$d/aitasks/metadata/profiles/baredash.yaml"
    run_gate "$d" materialize-active 5 --profile "$prof/baredash.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: bare-dash item → nonzero" "ok" "ok" \
        || assert_eq "strict profile: bare-dash item → nonzero" "nonzero" "$rc"
    # A blank line splitting an already-started block would make the reader
    # silently DROP every item after it — reject loudly instead of half-parsing.
    printf 'name: fast\ndefault_gates:\n  - risk_evaluated\n\n  - plan_approved\n' \
        > "$d/aitasks/metadata/profiles/blanksplit.yaml"
    run_gate "$d" materialize-active 5 --profile "$prof/blanksplit.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: blank-split block → nonzero (no silent drop)" "ok" "ok" \
        || assert_eq "strict profile: blank-split block → nonzero (no silent drop)" "nonzero" "$rc"
    # ...but a LEADING blank (key line, blank, then items) is a form the
    # authoritative reader consumes whole — it must stay accepted.
    printf 'name: fast\ndefault_gates:\n\n  - risk_evaluated\n' \
        > "$d/aitasks/metadata/profiles/leadblank.yaml"
    write_task "$d" 6 "__absent__"
    assert_eq "strict profile: leading-blank block accepted" "MATERIALIZED:risk_evaluated" \
        "$(run_gate "$d" materialize-active 6 --profile "$prof/leadblank.yaml" 2>/dev/null)"
    # Mismatched quote pairs are rejected (the readers would silently strip).
    printf 'name: fast\ndefault_gates: [%s]\n' "'risk_evaluated\"" \
        > "$d/aitasks/metadata/profiles/badquote.yaml"
    run_gate "$d" materialize-active 5 --profile "$prof/badquote.yaml" >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "strict profile: mismatched quotes → nonzero" "ok" "ok" \
        || assert_eq "strict profile: mismatched quotes → nonzero" "nonzero" "$rc"
}

test_materialize_persist_status() {
    # In a REAL git context a failed path-scoped commit must not report plain
    # success: the structured MATERIALIZED_UNCOMMITTED status distinguishes
    # "enforced locally" from "durable/cross-PC visible". Non-git fixtures
    # (every other test here) skip persistence silently via the rev-parse seam.
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"
    ( cd "$d" && git init -q . && git add -A && git -c user.email=t@t -c user.name=t commit -qm init ) || true
    write_task "$d" 1 "[risk_evaluated]"
    # A held index lock makes git add/commit fail while the tuple write succeeds.
    touch "$d/.git/index.lock"
    assert_eq "persist: real-repo commit failure → MATERIALIZED_UNCOMMITTED" \
        "MATERIALIZED_UNCOMMITTED:risk_evaluated" \
        "$(run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml" 2>/dev/null)"
    # Unchanged retry while the lock persists: the identical-tuple path must
    # NOT report a plain NOOP while the file is still uncommitted.
    assert_eq "persist: unchanged retry under lock → NOOP_UNCOMMITTED" \
        "NOOP_UNCOMMITTED:pending-persist" \
        "$(run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml" 2>/dev/null)"
    rm -f "$d/.git/index.lock"
    # With the transient lock gone, the unchanged re-pick HEALS the pending
    # persistence (commits the file) before reporting NOOP.
    assert_eq "persist: unchanged after unlock → NOOP (healed)" "NOOP:unchanged" \
        "$(run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml" 2>/dev/null)"
    assert_eq "persist: heal actually committed the task file" "" \
        "$(cd "$d" && git status --porcelain -- aitasks/t1_x.md)"
    write_task "$d" 2 "[risk_evaluated]"
    assert_eq "persist: healthy repo → plain MATERIALIZED" "MATERIALIZED:risk_evaluated" \
        "$(run_gate "$d" materialize-active 2 --profile "$prof/fast.yaml" 2>/dev/null)"

    # A BROKEN repo (git markers present but rev-parse failing) is an
    # operational failure, not the fixture seam — persistence must report
    # unverified, never plain success.
    local b; b="$(new_fixture)"
    printf 'gitdir: /nonexistent/broken\n' > "$b/.git"
    write_task "$b" 1 "[risk_evaluated]"
    assert_eq "persist: broken repo → MATERIALIZED_UNCOMMITTED" \
        "MATERIALIZED_UNCOMMITTED:risk_evaluated" \
        "$(run_gate "$b" materialize-active 1 --profile "$prof/fast.yaml" 2>/dev/null)"
    assert_eq "persist: broken repo unchanged retry → NOOP_UNCOMMITTED" \
        "NOOP_UNCOMMITTED:pending-persist" \
        "$(run_gate "$b" materialize-active 1 --profile "$prof/fast.yaml" 2>/dev/null)"
}

test_materialize_noop_and_concurrency() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"
    write_task "$d" 1 "[risk_evaluated]"
    run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml" >/dev/null

    # Unchanged re-pick → NOOP:unchanged, ZERO file diff (no updated_at bump).
    local before after
    before="$(cat "$d/aitasks/t1_x.md")"
    assert_eq "materialize: unchanged re-pick is a NOOP" "NOOP:unchanged" \
        "$(run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml")"
    after="$(cat "$d/aitasks/t1_x.md")"
    assert_eq "materialize: NOOP leaves file byte-identical" "$before" "$after"

    # Concurrent ledger append during materialize: both effects land (shared
    # per-task gate lock serializes the two writers; neither is lost).
    write_task "$d" 2 "[risk_evaluated]"
    ( run_gate "$d" materialize-active 2 --profile "$prof/fast.yaml" >/dev/null 2>&1 ) &
    local m_pid=$!
    ( run_gate "$d" append 2 risk_evaluated pass type=machine >/dev/null 2>&1 ) &
    local a_pid=$!
    wait "$m_pid" "$a_pid"
    assert_eq "concurrency: tuple landed" "active_gates: [risk_evaluated]" \
        "$(task_field "$d" 2 active_gates)"
    assert_contains "concurrency: ledger append landed" \
        "gate:risk_evaluated" "$(cat "$d/aitasks/t2_x.md")"
}

test_materialize_manual_verification_carveout() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"
    # MV task, gates absent → resolve would pull default_gates [risk_evaluated],
    # but the t1156 reachable-gates allowlist strips it at the materialize sink
    # (MV tasks skip Steps 6-8, so the gate could never be satisfied).
    write_task "$d" 1 "__absent__" "issue_type: manual_verification"
    assert_eq "MV carve-out: risk_evaluated stripped under fast" "MATERIALIZED:(empty)" \
        "$(run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml")"
    assert_eq "MV carve-out: stays archivable" "NO_GATES" \
        "$(run_gate "$d" archive-ready 1)"
}

# --- active (decision verb) + python parity --------------------------------

test_active_verb() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"
    local rc

    # Pre-claim fallback: no tuple → raw gates: field governs.
    write_task "$d" 1 "[risk_evaluated]"
    run_gate "$d" active 1 risk_evaluated; rc=$?
    assert_eq "active: pre-claim raw-gates fallback → 0" "0" "$rc"
    run_gate "$d" active 1 build_verified; rc=$?
    assert_eq "active: not in set → 1" "1" "$rc"

    # Materialized tuple governs (also the bash↔python hash-agreement check:
    # the digest was written by python; bash validates it before trusting).
    write_task "$d" 2 "__absent__"
    run_gate "$d" materialize-active 2 --profile "$prof/fast.yaml" >/dev/null
    run_gate "$d" active 2 risk_evaluated; rc=$?
    assert_eq "active: materialized profile-default gate → 0" "0" "$rc"

    # Filtered tuple: declared gate, empty active set → NOT active.
    write_task "$d" 3 "[risk_evaluated]"
    run_gate "$d" materialize-active 3 --profile "$prof/default.yaml" >/dev/null
    run_gate "$d" active 3 risk_evaluated; rc=$?
    assert_eq "active: filtered gate → 1 (tuple wins over raw gates)" "1" "$rc"

    # Stale tuple (raw gates edited after materialize) → fallback to raw.
    write_task "$d" 4 "__absent__"
    run_gate "$d" materialize-active 4 --profile "$prof/default.yaml" >/dev/null
    python3 - "$d/aitasks/t4_x.md" <<'EOF'
import sys
p = sys.argv[1]
text = open(p).read()
open(p, "w").write(text.replace("status: Ready", "status: Ready\ngates: [build_verified]"))
EOF
    run_gate "$d" active 4 build_verified; rc=$?
    assert_eq "active: stale tuple → raw-gates fallback → 0" "0" "$rc"
    # Python twin agrees on the same stale-tuple decision.
    ( cd "$d" && TASK_DIR=aitasks AIT_GATES_BACKEND=python "$GATE" active 4 build_verified ); rc=$?
    assert_eq "active: python backend agrees on stale case" "0" "$rc"
    ( cd "$d" && TASK_DIR=aitasks AIT_GATES_BACKEND=python "$GATE" active 3 risk_evaluated ); rc=$?
    assert_eq "active: python backend agrees on filtered case" "1" "$rc"
}

test_should_self_record_active_set() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"
    local rc

    # THE P0 double-record case: profile-default gate, raw gates: absent.
    # Pre-claim (no tuple): not enforced anywhere → self-record (exit 0).
    write_task "$d" 1 "__absent__"
    run_gate "$d" should-self-record 1 risk_evaluated; rc=$?
    assert_eq "self-record: pre-claim absent → record (0)" "0" "$rc"
    # Post-materialize: gate is in active_gates → the orchestrator records it;
    # a self-record here too would double-record (the negative control is the
    # pre-claim assertion above — a literal-declared read would return 0 here).
    run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml" >/dev/null
    run_gate "$d" should-self-record 1 risk_evaluated; rc=$?
    assert_eq "self-record: active via tuple → skip (1) [P0 no-double-record]" "1" "$rc"

    # Filtered gate: declared but not enforced → self-record path applies.
    write_task "$d" 2 "[risk_evaluated]"
    run_gate "$d" materialize-active 2 --profile "$prof/default.yaml" >/dev/null
    run_gate "$d" should-self-record 2 risk_evaluated; rc=$?
    assert_eq "self-record: filtered gate → record (0)" "0" "$rc"
}

# --- active-gates-status ---------------------------------------------------

test_active_gates_status() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"

    write_task "$d" 1 "[risk_evaluated]"
    assert_eq "status: no tuple → ABSENT" "ABSENT" \
        "$(run_gate "$d" active-gates-status 1 --profile "$prof/fast.yaml" | head -1)"

    run_gate "$d" materialize-active 1 --profile "$prof/fast.yaml" >/dev/null
    assert_eq "status: fresh after materialize" "FRESH" \
        "$(run_gate "$d" active-gates-status 1 --profile "$prof/fast.yaml" | head -1)"
    assert_contains "status: tuple displayed" \
        "ACTIVE:risk_evaluated" \
        "$(run_gate "$d" active-gates-status 1 --profile "$prof/fast.yaml")"

    # Profile switch → STALE:<stamped>-><current>.
    assert_eq "status: profile switch → STALE" "STALE:fast->default" \
        "$(run_gate "$d" active-gates-status 1 --profile "$prof/default.yaml" | head -1)"

    # Manual gates: edit under the SAME profile name → gates-half mismatch.
    python3 - "$d/aitasks/t1_x.md" <<'EOF'
import sys
p = sys.argv[1]
text = open(p).read()
open(p, "w").write(text.replace("gates: [risk_evaluated]", "gates: [risk_evaluated, build_verified]"))
EOF
    assert_eq "status: same-profile gates edit → STALE" "STALE:fast->fast" \
        "$(run_gate "$d" active-gates-status 1 --profile "$prof/fast.yaml" | head -1)"
    # ...and enforcement falls back to the (new) raw declared intent.
    assert_eq "status: stale tuple → archive-ready reads raw gates" \
        "BLOCKED:risk_evaluated,build_verified" \
        "$(run_gate "$d" archive-ready 1)"

    # Profile default_gates edit under an unchanged profile name and no task
    # gates: field → profile-half digest mismatch → STALE (concern-3 case).
    write_task "$d" 2 "__absent__"
    run_gate "$d" materialize-active 2 --profile "$prof/fast.yaml" >/dev/null
    printf 'name: fast\ndefault_gates: [risk_evaluated, build_verified]\n' \
        > "$d/aitasks/metadata/profiles/fast.yaml"
    assert_eq "status: default_gates edit → STALE" "STALE:fast->fast" \
        "$(run_gate "$d" active-gates-status 2 --profile "$prof/fast.yaml" | head -1)"
}

# --- tuple integrity + atomicity -------------------------------------------

test_tuple_atomicity_and_corruption() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"
    local rc before after

    # Strict subset of the four flags → rejected, zero diff.
    write_task "$d" 1 "[risk_evaluated]"
    before="$(cat "$d/aitasks/t1_x.md")"
    run_update "$d" --batch 1 --active-gates "risk_evaluated" --silent >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "atomicity: 1-of-4 flags rejected" "ok" "ok" \
        || assert_eq "atomicity: 1-of-4 flags rejected" "nonzero" "$rc"
    run_update "$d" --batch 1 --active-gates "risk_evaluated" \
        --active-gates-profile fast --silent >/dev/null 2>&1; rc=$?
    [[ $rc -ne 0 ]] && assert_eq "atomicity: 2-of-4 flags rejected" "ok" "ok" \
        || assert_eq "atomicity: 2-of-4 flags rejected" "nonzero" "$rc"
    after="$(cat "$d/aitasks/t1_x.md")"
    assert_eq "atomicity: rejected invocation left zero diff" "$before" "$after"

    # Hand-edited active_gates value (bypassing the CLI) → outputs-half digest
    # mismatch → readers fall back to raw gates: conservatively.
    write_task "$d" 2 "[risk_evaluated]"
    run_gate "$d" materialize-active 2 --profile "$prof/default.yaml" >/dev/null
    assert_eq "corruption: filtered task archives before edit" "NO_GATES" \
        "$(run_gate "$d" archive-ready 2)"
    python3 - "$d/aitasks/t2_x.md" <<'EOF'
import sys
p = sys.argv[1]
text = open(p).read()
open(p, "w").write(text.replace("active_gates: []", "active_gates: [build_verified]"))
EOF
    assert_eq "corruption: hand-edited set NOT trusted (raw fallback)" \
        "BLOCKED:risk_evaluated" "$(run_gate "$d" archive-ready 2)"
}

test_tuple_durability() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"

    # An explicit EMPTY tuple (fully filtered task) must survive unrelated
    # writes — the `gates:` never-emit-[] pattern would silently drop it and
    # convert the filtered task back into a gated one.
    write_task "$d" 1 "[risk_evaluated]"
    run_gate "$d" materialize-active 1 --profile "$prof/default.yaml" >/dev/null

    run_update "$d" --batch 1 --priority high --silent >/dev/null
    assert_eq "durability: [] tuple survives unrelated update" "active_gates: []" \
        "$(task_field "$d" 1 active_gates)"
    assert_eq "durability: digest survives unrelated update" \
        "$(run_gate "$d" archive-ready 1)" "NO_GATES"

    # Rename (aitask_update --name) — same writer path, new filename.
    run_update "$d" --batch 1 --name renamed --silent >/dev/null
    assert_contains "durability: [] tuple survives rename" \
        "active_gates: []" "$(cat "$d/aitasks/t1_renamed.md")"

    # The fold write path (aitask_fold_mark.sh persists via aitask_update.sh
    # --folded-tasks): same preserve-by-default plumbing.
    run_update "$d" --batch 1 --folded-tasks "99" --silent >/dev/null 2>&1 || true
    assert_contains "durability: [] tuple survives folded-tasks write" \
        "active_gates: []" "$(cat "$d/aitasks/t1_renamed.md")"
}

# --- negative control: filtered gate invisible at EVERY enforcer -----------

test_negative_control_enforcers() {
    local d; d="$(new_fixture)"
    local prof="aitasks/metadata/profiles"

    # Task declares risk_evaluated; profile (default) renders nothing.
    write_task "$d" 1 "[risk_evaluated]" "also_blocks_dependents: [risk_evaluated]"
    run_gate "$d" materialize-active 1 --profile "$prof/default.yaml" >/dev/null

    # (b) archives without blocking on the filtered gate.
    assert_eq "negctl: archive-ready NO_GATES" "NO_GATES" \
        "$(run_gate "$d" archive-ready 1)"
    # (c)+(d-i) dependents unblock: the declared-but-filtered also-entry is
    # dropped via active_gates_filtered (no profile needed at read time).
    assert_eq "negctl: deps-unblock NO_GATES (filtered also dropped)" "NO_GATES" \
        "$(run_gate "$d" deps-unblock 1)"

    # (d-ii) an INDEPENDENT also-blocker (not declared, not filtered) still
    # blocks until it passes.
    write_task "$d" 2 "[risk_evaluated]" "also_blocks_dependents: [merge_approved]"
    run_gate "$d" materialize-active 2 --profile "$prof/default.yaml" >/dev/null
    assert_eq "negctl: independent also-blocker still blocks" "BLOCKED:merge_approved" \
        "$(run_gate "$d" deps-unblock 2)"
    run_gate "$d" append 2 merge_approved pass type=human >/dev/null
    assert_eq "negctl: independent blocker passes → satisfied" "SATISFIED" \
        "$(run_gate "$d" deps-unblock 2)"

    # Staleness lockstep: after a raw gates: edit adds a blocker ALSO named in
    # also_blocks_dependents, the STALE tuple's filtered list must be ignored
    # in the SAME decision — the newly declared blocker blocks again.
    python3 - "$d/aitasks/t1_x.md" <<'EOF'
import sys
p = sys.argv[1]
text = open(p).read()
open(p, "w").write(text.replace("gates: [risk_evaluated]", "gates: [risk_evaluated, build_verified]"))
EOF
    assert_eq "negctl: stale filtered list ignored — blocker returns" \
        "BLOCKED:risk_evaluated" "$(run_gate "$d" deps-unblock 1)"

    # SAME declared task under fast → ENFORCED (the filter is load-bearing,
    # not a constant): archive blocked until the gate passes.
    write_task "$d" 3 "[risk_evaluated]"
    run_gate "$d" materialize-active 3 --profile "$prof/fast.yaml" >/dev/null
    assert_eq "negctl: enforced under fast" "BLOCKED:risk_evaluated" \
        "$(run_gate "$d" archive-ready 3)"
    run_gate "$d" append 3 risk_evaluated pass type=machine >/dev/null
    assert_eq "negctl: passes → ALL_PASS" "ALL_PASS" \
        "$(run_gate "$d" archive-ready 3)"

    # (e) TUI decision surfaces: a FAILED historical run of a now-filtered gate
    # never drives a classification (audit-only). compact_gate_summary and
    # TaskGateState.filtered_gates are the shared seams the board/monitor use.
    write_task "$d" 4 "[risk_evaluated]"
    run_gate "$d" append 4 risk_evaluated fail type=machine >/dev/null
    run_gate "$d" materialize-active 4 --profile "$prof/default.yaml" >/dev/null
    local pyout
    pyout="$( cd "$d" && python3 - "$PROJECT_DIR" <<'EOF'
import sys, os
sys.path.insert(0, os.path.join(sys.argv[1], ".aitask-scripts", "lib"))
import glob
import gate_ledger
state = gate_ledger.read_task_gate_state(glob.glob("aitasks/t4_*.md")[0])
print("filtered=" + ",".join(state.filtered_gates))
print("active=" + ",".join(state.active_gates))
print("compact=" + (gate_ledger.compact_gate_summary(state) or "(none)"))
print("archive=" + state.archive_decision)
failed_drives = any(
    r.status in ("fail", "error")
    for r in state.current.values()
    if r.name not in state.filtered_gates
)
print("failed_drives=" + str(failed_drives))
EOF
)"
    assert_contains "negctl(e): filtered surfaced on state" "filtered=risk_evaluated" "$pyout"
    assert_contains "negctl(e): failed filtered run excluded from counts" "compact=(none)" "$pyout"
    assert_contains "negctl(e): failed filtered run drives no classification" "failed_drives=False" "$pyout"
    assert_contains "negctl(e): archive decision unaffected" "archive=NO_GATES" "$pyout"
}

# --- remote-lane negative control against the REAL shipped profile ---------

test_remote_lane_real_profile() {
    # t635_35: the shipped remote.yaml declares an explicit rendered_gates: []
    # ceiling. A task with a literal gates: declaration materialized under the
    # REAL profile (not a fixture) gets the load-bearing empty tuple and
    # archives with no manual gate append — the t635_33 negative control
    # exercised through the remote lane's actual configuration.
    local d; d="$(new_fixture)"
    cp "$PROJECT_DIR/aitasks/metadata/profiles/remote.yaml" \
        "$d/aitasks/metadata/profiles/remote.yaml"
    write_task "$d" 9 "[risk_evaluated]"
    assert_eq "remote lane: real remote.yaml filters to empty" "MATERIALIZED:(empty)" \
        "$(run_gate "$d" materialize-active 9 --profile aitasks/metadata/profiles/remote.yaml 2>/dev/null)"
    assert_eq "remote lane: empty tuple persisted" "active_gates: []" \
        "$(task_field "$d" 9 active_gates)"
    assert_eq "remote lane: archive-ready NO_GATES (no manual append)" "NO_GATES" \
        "$(run_gate "$d" archive-ready 9)"
}

# --- Run ---
test_materialize_basic
test_materialize_error_paths
test_materialize_persist_status
test_materialize_noop_and_concurrency
test_materialize_manual_verification_carveout
test_active_verb
test_should_self_record_active_set
test_active_gates_status
test_tuple_atomicity_and_corruption
test_tuple_durability
test_negative_control_enforcers
test_remote_lane_real_profile

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
