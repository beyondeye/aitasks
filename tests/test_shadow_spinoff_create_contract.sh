#!/usr/bin/env bash
# test_shadow_spinoff_create_contract.sh - Pins the REAL aitask_create.sh
# contract behind the picker's spin-off triage arm (t1159_3).
#
# Why this exists as a shell test. Every Python test of the spin-off flow
# overrides `_run_create_cmd`, the subprocess seam -- deliberately, so no bash
# runs in the Python suites. The consequence is that *nothing* would execute
# the real script with the argv the picker actually emits: a flag rename, a
# dropped frontmatter line, or a change to the `--silent` stdout shape would
# leave the whole Python suite green while the feature is dead on disk. This
# test is the one place the composite invocation is exercised end to end.
#
# Scope note -- deliberately NOT re-tested here:
#   `--followup-of` anchor resolution (root / flatten / legacy-parent fallback)
#   and its rejection of a nonexistent id are already covered per-flag by
#   tests/test_anchor_create.sh (test_followup_flatten). This file pins the
#   COMPOSITE invocation and the flags that file does not exercise together.
#
# Covers:
#   - the picker's exact argv -> a draft carrying anchor + followup_kind +
#     draft:true + priority + the shadow-concern label
#   - `--silent` in DRAFT mode prints EXACTLY one line, the draft path
#     (test_create_silent_stdout.sh covers the --commit path)
#   - the canonical `- [priority | region] body` marker line survives the
#     `--desc-file -` stdin round trip verbatim, brackets and pipe included
#   - an invalid --followup-kind is rejected BEFORE any file is written
#
# Run: bash tests/test_shadow_spinoff_create_contract.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

# The exact marker line `concern_marker_line()` renders (concern_parser.py).
# Brackets and the pipe are the point: this text travels through stdin, and a
# regression that routed it through argv or a shell expansion would corrupt it.
MARKER_LINE='- [high | monitor_shared.py:2048] Row mark budget is unverified.'

read_frontmatter_field() {
    local file="$1" field="$2"
    awk -v f="$field" '
        NR == 1 && $0 == "---" { infm = 1; next }
        infm && $0 == "---" { exit }
        infm && index($0, f ": ") == 1 { print substr($0, length(f) + 3); exit }
    ' "$file"
}

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"
    CLEANUP_DIRS+=("$tmpdir")

    pushd "$tmpdir" > /dev/null
    git init --quiet .
    git config user.email "test@test.com"
    git config user.name "Test"

    mkdir -p aitasks/metadata aitasks/new aitasks/archived
    setup_fake_aitask_repo "$PWD"
    cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/aitask_query_files.sh" .aitask-scripts/
    cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
    cp "$PROJECT_DIR/.aitask-scripts/lib/agentcrew_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
    chmod +x .aitask-scripts/*.sh

    printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
        > aitasks/metadata/task_types.txt
    : > aitasks/metadata/labels.txt
    echo "aitasks/new/" > .gitignore

    # The REVIEWED task the picker anchors the spin-off to: a child, so the
    # anchor resolution exercised here is the one the picker really produces
    # (a followed agent is usually working a child task).
    mkdir -p aitasks/t42
    seed_task aitasks/t42_parent_topic.md
    seed_task aitasks/t42/t42_1_reviewed_child.md "anchor: 42"

    git add -A
    git commit -m "Initial setup" --quiet
}

seed_task() {
    local path="$1"; shift
    mkdir -p "$(dirname "$path")"
    {
        printf '%s\n' "---"
        printf '%s\n' "priority: medium"
        printf '%s\n' "effort: low"
        printf '%s\n' "depends: []"
        printf '%s\n' "issue_type: chore"
        printf '%s\n' "status: Ready"
        printf '%s\n' "labels: []"
        for extra in "$@"; do printf '%s\n' "$extra"; done
        printf '%s\n' "created_at: 2026-01-01 10:00"
        printf '%s\n' "updated_at: 2026-01-01 10:00"
        printf '%s\n' "---"
        printf '\nBody\n'
    } > "$path"
}

teardown() {
    popd > /dev/null 2>&1 || true
}

# The picker's invocation, verbatim. Description arrives on stdin exactly as
# `_spawn_concern_tasks` composes it.
spinoff_create() {
    local name="$1" kind="${2:-review_finding}"
    printf 'Spun off from a shadow review concern on t42_1.\n\n%s\n' "$MARKER_LINE" |
        bash .aitask-scripts/aitask_create.sh \
            --batch --silent \
            --name "$name" \
            --desc-file - \
            --priority high \
            --labels shadow-concern \
            --followup-of 42_1 \
            --followup-kind "$kind"
}

test_composite_argv_writes_a_complete_draft() {
    echo "=== Test: the picker's exact argv produces a complete draft ==="
    setup_project

    local out rc=0
    out="$(spinoff_create shadow_monitorsharedpy2048_a1b2c3d4_1)" || rc=$?
    assert_eq "spin-off create exits 0" "0" "$rc"

    # --silent promises exactly one stdout line; the whole feature parses it
    # as a path, so a second line (a warning, a git blurb) breaks the caller.
    assert_eq "stdout is exactly one line" "1" "$(printf '%s' "$out" | grep -c '' || true)"

    local draft="$out"
    assert_contains "stdout line is a draft path" "aitasks/new/" "$draft"
    assert_file_exists "draft file exists on disk" "$draft"

    # Provenance -- the two flags whose draft-path flow this task depends on.
    assert_eq "anchor resolved from the reviewed child" \
        "42" "$(read_frontmatter_field "$draft" anchor)"
    assert_eq "followup_kind recorded" \
        "review_finding" "$(read_frontmatter_field "$draft" followup_kind)"
    assert_eq "draft marker present" \
        "true" "$(read_frontmatter_field "$draft" draft)"
    assert_eq "priority carried from the concern" \
        "high" "$(read_frontmatter_field "$draft" priority)"
    # The hyphen SURVIVES label normalization (unlike `sanitize_name`, which
    # deletes it) -- pinned literally so a future normalizer change that
    # silently rewrote it to `shadow_concern` is caught here.
    assert_eq "shadow-concern label recorded verbatim" \
        "[shadow-concern]" "$(read_frontmatter_field "$draft" labels)"

    # The canonical marker line must survive stdin byte for byte: the picker's
    # store matching and the receiving agent both depend on that exact text.
    assert_contains "canonical marker line survives the stdin round trip" \
        "$MARKER_LINE" "$(cat "$draft")"

    teardown
}

test_invalid_followup_kind_is_rejected_before_any_write() {
    echo "=== Test: an invalid --followup-kind writes nothing ==="
    setup_project

    local rc=0
    spinoff_create shadow_bad_kind_a1b2c3d4_1 not_a_real_kind >/dev/null 2>&1 || rc=$?
    assert_exit_nonzero_rc "invalid --followup-kind rejected" "$rc"

    # Pre-write rejection, not a cleanup: no draft may exist at all.
    local count
    count="$(find aitasks/new -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
    assert_eq "no draft written for an invalid kind" "0" "$count"

    teardown
}

test_unresolvable_followup_of_fails_the_whole_creation() {
    echo "=== Test: an unresolvable --followup-of fails the create ==="
    setup_project

    local rc=0
    printf 'body\n' | bash .aitask-scripts/aitask_create.sh \
        --batch --silent --name shadow_orphan_a1b2c3d4_1 --desc-file - \
        --priority high --labels shadow-concern \
        --followup-of 999999 --followup-kind review_finding \
        >/dev/null 2>&1 || rc=$?

    # This nonzero is the contract `_spawn_concern_tasks` relies on: the ONE
    # reachable way the composite invocation fails (an id matching no task,
    # active or archived). It must surface as a per-concern failure -- which
    # means NOT writing the rejection store, so the concern returns next round
    # instead of being silently suppressed with nothing on disk.
    assert_exit_nonzero_rc "unresolvable --followup-of rejected" "$rc"

    local count
    count="$(find aitasks/new -name '*.md' 2>/dev/null | wc -l | tr -d ' ')"
    assert_eq "no draft written when the anchor cannot resolve" "0" "$count"

    teardown
}

echo "Running shadow spin-off create-contract tests..."
echo

test_composite_argv_writes_a_complete_draft
echo
test_invalid_followup_kind_is_rejected_before_any_write
echo
test_unresolvable_followup_of_fails_the_whole_creation
echo

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo "================================"
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
echo "================================"
[[ "$FAIL" -eq 0 ]]
