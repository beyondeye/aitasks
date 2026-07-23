#!/usr/bin/env bash
# test_web_merge_materialize.sh - Tests for the t635_35 web-lane handoff:
#   aitask_web_merge.sh materialize <task_id> <marker_json>
#
# Covers the full completion-marker → provenance validation → profile
# resolution → tuple persistence → archival-readiness chain against the REAL
# helpers (aitask_web_merge.sh delegating to aitask_gate.sh) from a fixture
# cwd with TASK_DIR=aitasks. The marker's provenance fields are an authority
# input for gate selection, so the invalid-marker matrix is the load-bearing
# part: no malformed marker may select another profile or silently skip.
#
# Run: bash tests/test_web_merge_materialize.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

WM="$PROJECT_DIR/.aitask-scripts/aitask_web_merge.sh"
GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"

# --- fixture helpers -------------------------------------------------------

new_fixture() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_webmat_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    mkdir -p "$tmp/aitasks/metadata/profiles/local" "$tmp/aiplans" "$tmp/markers"
    # Mirrors the shipped remote profile's gate posture: explicit
    # render-nothing ceiling.
    printf 'name: remote\nrendered_gates: []\n' \
        > "$tmp/aitasks/metadata/profiles/remote.yaml"
    printf 'name: fast\ndefault_gates: [risk_evaluated]\n' \
        > "$tmp/aitasks/metadata/profiles/fast.yaml"
    # Local-override variant (scanner-style local/ filename).
    printf 'name: loc\nrendered_gates: []\n' \
        > "$tmp/aitasks/metadata/profiles/local/loc.yaml"
    # Malformed profile: scalar rendered_gates → materialize-active hard-fails.
    printf 'name: broken\nrendered_gates: nope\n' \
        > "$tmp/aitasks/metadata/profiles/broken.yaml"
    cat > "$tmp/aitasks/metadata/gates.yaml" <<'EOF'
gates:
  risk_evaluated:
    type: machine
    blocks_dependents: true
EOF
    echo "$tmp"
}

# write_task <dir> <id> <gates-literal | __absent__>
write_task() {
    local dir="$1" id="$2" gates="$3"
    local path="$dir/aitasks/t${id}_x.md"
    {
        echo "---"
        echo "status: Ready"
        [[ "$gates" != "__absent__" ]] && echo "gates: ${gates}"
        echo "---"
        echo "Body."
    } > "$path"
}

# write_marker <dir> <name> <json-content> -> echoes marker path (fixture-relative)
write_marker() {
    local dir="$1" name="$2" content="$3"
    printf '%s' "$content" > "$dir/markers/$name"
    echo "markers/$name"
}

run_wm() {
    local dir="$1"; shift
    ( cd "$dir" && TASK_DIR=aitasks "$WM" "$@" )
}

run_gate() {
    local dir="$1"; shift
    ( cd "$dir" && TASK_DIR=aitasks "$GATE" "$@" )
}

task_field() {  # <dir> <id> <field> -> raw line or empty
    grep -E "^${3}:" "$1/aitasks/t${2}_x.md" || true
}

# --- Test 1: valid marker → materialized empty set + archivable -------------

test_valid_marker() {
    echo "=== Test 1: valid marker materializes under the recorded profile ==="
    local d; d="$(new_fixture)"
    write_task "$d" 1 "[risk_evaluated]"
    local m
    m="$(write_marker "$d" ok.json \
        '{"task_id":"1","profile":"remote","profile_filename":"remote.yaml"}')"

    local out rc
    out="$(run_wm "$d" materialize 1 "$m" 2>/dev/null)"; rc=$?
    assert_eq "valid marker: exit 0" "0" "$rc"
    assert_eq "valid marker: WEBMAT_OK with filtered-empty status" \
        "WEBMAT_OK:MATERIALIZED:(empty)" "$out"
    assert_eq "valid marker: load-bearing empty tuple persisted" \
        "active_gates: []" "$(task_field "$d" 1 active_gates)"
    assert_eq "valid marker: provenance stamp is the marker profile" \
        "active_gates_profile: remote" "$(task_field "$d" 1 active_gates_profile)"
    # The remote-lane negative control: literal gates:, archives with no
    # manual gate append.
    assert_eq "valid marker: archive-ready NO_GATES" "NO_GATES" \
        "$(run_gate "$d" archive-ready 1)"
}

# --- Test 2: pre-existing tuple is superseded, not preserved ----------------

test_supersedes_prior_tuple() {
    echo "=== Test 2: prior fast-stamped tuple is re-materialized under the marker profile ==="
    local d; d="$(new_fixture)"
    write_task "$d" 2 "[risk_evaluated]"
    # First stamp under fast (enforced set nonempty)...
    run_gate "$d" materialize-active 2 --profile aitasks/metadata/profiles/fast.yaml >/dev/null 2>&1
    assert_eq "precondition: fast tuple present" "active_gates: [risk_evaluated]" \
        "$(task_field "$d" 2 active_gates)"
    # ...then the web handoff under remote supersedes it.
    local m
    m="$(write_marker "$d" ok2.json \
        '{"profile":"remote","profile_filename":"remote.yaml"}')"
    local out
    out="$(run_wm "$d" materialize 2 "$m" 2>/dev/null)"
    assert_eq "supersede: WEBMAT_OK" "WEBMAT_OK:MATERIALIZED:(empty)" "$out"
    assert_eq "supersede: tuple now empty under remote" "active_gates: []" \
        "$(task_field "$d" 2 active_gates)"
    assert_eq "supersede: provenance restamped" "active_gates_profile: remote" \
        "$(task_field "$d" 2 active_gates_profile)"
}

# --- Test 3: legacy marker skips (raw gates govern) -------------------------

test_legacy_marker_skips() {
    echo "=== Test 3: legacy marker (no provenance) skips — raw gates govern ==="
    local d; d="$(new_fixture)"
    write_task "$d" 3 "[risk_evaluated]"
    local m
    m="$(write_marker "$d" legacy.json \
        '{"task_id":"3","implemented_with":"claudecode/opus4_6"}')"
    local out rc
    out="$(run_wm "$d" materialize 3 "$m" 2>/dev/null)"; rc=$?
    assert_eq "legacy marker: exit 0 (skip is not a failure)" "0" "$rc"
    assert_eq "legacy marker: WEBMAT_SKIP" "WEBMAT_SKIP:no-profile" "$out"
    assert_eq "legacy marker: task file untouched (no tuple)" "" \
        "$(task_field "$d" 3 active_gates)"
    assert_eq "legacy marker: raw gates still govern archival" \
        "BLOCKED:risk_evaluated" "$(run_gate "$d" archive-ready 3)"
}

# --- Test 4: invalid-marker matrix (fail-closed, nothing written) -----------

# assert_invalid <dir> <task_id> <marker_rel> <label> [expected_reason]
assert_invalid() {
    local d="$1" id="$2" m="$3" label="$4" reason="${5:-}"
    local out rc
    out="$(run_wm "$d" materialize "$id" "$m" 2>/dev/null)"; rc=$?
    if [[ $rc -ne 0 ]]; then
        assert_eq "$label: nonzero exit" "ok" "ok"
    else
        assert_eq "$label: nonzero exit" "nonzero" "0"
    fi
    assert_contains "$label: WEBMAT_INVALID" "WEBMAT_INVALID:" "$out"
    if [[ -n "$reason" ]]; then
        assert_eq "$label: reason" "WEBMAT_INVALID:$reason" "$out"
    fi
    assert_eq "$label: task file untouched" "" "$(task_field "$d" "$id" active_gates)"
}

test_invalid_markers() {
    echo "=== Test 4: invalid markers are rejected fail-closed ==="
    local d; d="$(new_fixture)"
    write_task "$d" 4 "[risk_evaluated]"
    local m

    m="$(write_marker "$d" trav.json \
        '{"profile":"remote","profile_filename":"../evil.yaml"}')"
    assert_invalid "$d" 4 "$m" "path traversal" "bad-profile-filename"

    m="$(write_marker "$d" abs.json \
        '{"profile":"remote","profile_filename":"/etc/evil.yaml"}')"
    assert_invalid "$d" 4 "$m" "absolute path" "bad-profile-filename"

    m="$(write_marker "$d" deep.json \
        '{"profile":"remote","profile_filename":"local/../../evil.yaml"}')"
    assert_invalid "$d" 4 "$m" "local/ traversal" "bad-profile-filename"

    m="$(write_marker "$d" ghost.json \
        '{"profile":"ghost","profile_filename":"ghost.yaml"}')"
    assert_invalid "$d" 4 "$m" "nonexistent profile file" "profile-not-found"

    # File exists but its declared name is not the marker's profile —
    # repointed provenance must not govern.
    m="$(write_marker "$d" mismatch.json \
        '{"profile":"fast","profile_filename":"remote.yaml"}')"
    assert_invalid "$d" 4 "$m" "name mismatch" "name-mismatch"

    m="$(write_marker "$d" partial1.json '{"profile":"remote"}')"
    assert_invalid "$d" 4 "$m" "profile without filename" "partial-provenance"

    m="$(write_marker "$d" partial2.json '{"profile_filename":"remote.yaml"}')"
    assert_invalid "$d" 4 "$m" "filename without profile" "partial-provenance"

    m="$(write_marker "$d" nonstring.json \
        '{"profile":42,"profile_filename":"remote.yaml"}')"
    assert_invalid "$d" 4 "$m" "non-string profile" "non-string-provenance"

    m="$(write_marker "$d" notjson.json 'this is not json {')"
    assert_invalid "$d" 4 "$m" "non-JSON marker" "bad-marker"

    m="markers/does_not_exist.json"
    assert_invalid "$d" 4 "$m" "missing marker file" "bad-marker"
}

# --- Test 5: local/ profile filename accepted -------------------------------

test_local_profile_accepted() {
    echo "=== Test 5: local/ profile filename resolves and materializes ==="
    local d; d="$(new_fixture)"
    write_task "$d" 5 "[risk_evaluated]"
    local m
    m="$(write_marker "$d" loc.json \
        '{"profile":"loc","profile_filename":"local/loc.yaml"}')"
    local out
    out="$(run_wm "$d" materialize 5 "$m" 2>/dev/null)"
    assert_eq "local profile: WEBMAT_OK" "WEBMAT_OK:MATERIALIZED:(empty)" "$out"
    # The canonical stamp is path-derived (scanner-style, t635_33
    # _profile_stamp_name): a local/ override stamps `local/<stem>`, keeping
    # file identity in the provenance — distinct from the YAML `name:` the
    # marker cross-check validates.
    assert_eq "local profile: provenance stamp keeps local/ file identity" \
        "active_gates_profile: local/loc" \
        "$(task_field "$d" 5 active_gates_profile)"
}

# --- Test 6: materialization failure → WEBMAT_FAIL, no trusted stale tuple --

test_materialize_failure() {
    echo "=== Test 6: materialize failure surfaces WEBMAT_FAIL and clears stale state ==="
    local d; d="$(new_fixture)"
    write_task "$d" 6 "[risk_evaluated]"
    # Seed a valid fast tuple first — the failure path must not leave it
    # silently authoritative.
    run_gate "$d" materialize-active 6 --profile aitasks/metadata/profiles/fast.yaml >/dev/null 2>&1
    assert_eq "precondition: fast tuple present" "active_gates: [risk_evaluated]" \
        "$(task_field "$d" 6 active_gates)"

    local m out rc
    m="$(write_marker "$d" broken.json \
        '{"profile":"broken","profile_filename":"broken.yaml"}')"
    out="$(run_wm "$d" materialize 6 "$m" 2>/dev/null)"; rc=$?
    if [[ $rc -ne 0 ]]; then
        assert_eq "materialize failure: nonzero exit" "ok" "ok"
    else
        assert_eq "materialize failure: nonzero exit" "nonzero" "0"
    fi
    assert_contains "materialize failure: WEBMAT_FAIL forwarded" "WEBMAT_FAIL:" "$out"
    # The status line must carry the actual diagnostic (materialize-active
    # reports errors on stderr; a stdout-only capture would leave the reason
    # empty and the interactive retry prompt unable to say what failed).
    if [[ "$out" =~ ^WEBMAT_FAIL:[0-9]+:[[:space:]]*$ || "$out" =~ ^WEBMAT_FAIL:[0-9]+:$ ]]; then
        assert_eq "materialize failure: reason is non-empty" "non-empty reason" "$out"
    else
        assert_eq "materialize failure: reason is non-empty" "ok" "ok"
    fi
    # materialize-active's clear-on-fail removed the stale fast tuple, so the
    # raw-`gates:` fallback genuinely governs (fail-closed toward enforcement).
    assert_eq "materialize failure: stale tuple cleared" "" \
        "$(task_field "$d" 6 active_gates)"
    assert_eq "materialize failure: raw gates govern archival" \
        "BLOCKED:risk_evaluated" "$(run_gate "$d" archive-ready 6)"
}

# --- run -------------------------------------------------------------------

test_valid_marker
test_supersedes_prior_tuple
test_legacy_marker_skips
test_invalid_markers
test_local_profile_accepted
test_materialize_failure

for dirx in "${CLEANUP_DIRS[@]}"; do
    rm -rf "$dirx"
done

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
