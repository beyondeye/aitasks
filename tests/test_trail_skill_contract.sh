#!/usr/bin/env bash
# test_trail_skill_contract.sh — Contract guard for /aitask-trail (t1210_3).
#
# The trail skill carries load-bearing prose contracts (single confirmed
# write, stale-base guard, read-only --show, mandatory pre-write drift
# validation, no-metadata-mutation invariant, owner handoff, ad-hoc scope
# mapping). The skill is profile-aware, so the contracts are asserted in
# ALL THREE committed goldens (default / fast / remote) — no profile render
# may drop a required instruction. Dropping any marker fails the test.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

GOLDEN_DIR="tests/golden/skills/aitask-trail"
PROFILES=(default fast remote)

for profile in "${PROFILES[@]}"; do
    golden="$GOLDEN_DIR/SKILL-${profile}-claude.md"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$golden" ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: golden missing at $golden"
        echo ""
        echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
        exit 1
    fi

    skill="$(cat "$golden")"

    # (a) Both NON-SKIPPABLE confirmation banners (create + refresh). The
    # banner text appears once per flow; require two occurrences.
    banner_count="$(grep -c 'NON-SKIPPABLE' "$golden" || true)"
    TOTAL=$((TOTAL + 1))
    if [[ "$banner_count" -ge 2 ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $profile: expected >=2 NON-SKIPPABLE banners, found $banner_count"
    fi

    # (b) Stale-base re-read guard: versions re-run + current-line compare
    # immediately before update.
    assert_contains "$profile: stale-base guard names the re-read" \
        "Stale-base re-read guard" "$skill"
    assert_contains "$profile: guard compares the current-version line" \
        '`* sha256:` line against `<base_version>`' "$skill"

    # (c) --show is read-only.
    assert_contains "$profile: --show read-only contract" \
        "strictly read-only: zero writes, no confirmation" "$skill"

    # (d) Mandatory pre-write drift validation with its three branches.
    assert_contains "$profile: pre-write validation is mandatory" \
        "Pre-write validation (mandatory)" "$skill"
    assert_contains "$profile: invalid-trail branch present" \
        "ERROR:invalid_trail" "$skill"
    assert_contains "$profile: stale branch re-gathers" \
        "the repository changed under the analysis" "$skill"

    # (e) No task-metadata mutations invariant.
    assert_contains "$profile: no metadata mutation invariant" \
        "Never mutate task metadata" "$skill"

    # (f) HANDLE: parse + collision -> new slug (never overwrite).
    assert_contains "$profile: HANDLE line is parsed" \
        'Parse the `HANDLE:<handle>` stdout line' "$skill"
    assert_contains "$profile: collision re-prompts the slug" \
        "the slug is taken: re-prompt for a new slug" "$skill"

    # (g) OWNER:none requires an explicit owner before create.
    assert_contains "$profile: OWNER:none owner handoff" \
        "explicit owner choice is REQUIRED" "$skill"

    # (h) Ad-hoc scope maps to task scope with children disclosure and
    # records scope.kind ad_hoc.
    assert_contains "$profile: ad-hoc maps to task scope" \
        "map it to task" "$skill"
    assert_contains "$profile: ad-hoc children disclosure" \
        "parent id also pulls its active children" "$skill"
    assert_contains "$profile: ad-hoc scope.kind recorded" \
        'scope.kind: "ad_hoc"' "$skill"

    # (i) Single confirmed write per flow.
    assert_contains "$profile: single-write invariant" \
        "At most ONE artifact write per flow" "$skill"

    # (j) Refresh re-snapshot passes the stored owner and never re-opens
    # ownership (multi-topic/ad-hoc must not fall to OWNER:none).
    assert_contains "$profile: refresh passes the stored owner" \
        'Always pass `--owner <id>`' "$skill"
    assert_contains "$profile: refresh never re-opens ownership" \
        "refresh never" "$skill"

    # (k) Refresh replays the complete stored member set for task/ad_hoc
    # scopes (expansion-approved members must not vanish).
    assert_contains "$profile: refresh replays stored inputs" \
        "NEVER just the initiating task" "$skill"
    assert_contains "$profile: expansion members pinned by inputs" \
        "can never silently vanish on refresh" "$skill"
done

# --- Summary ----------------------------------------------------------------

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
