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

    # (b2) t1569_1 gatherer contract additions. These are PROSE contracts, and
    # this is where the claim actually lives: "the status reports probe health,
    # not completeness" has no executable form against gatherer output, so it is
    # pinned here as contract text instead of as a pseudo-assertion that would
    # be silently weakened.
    assert_contains "$profile: MEMBER_EXT is in the pinned line set" \
        "MEMBER_EXT:<ref>" "$skill"
    assert_contains "$profile: the four INFLIGHT prefixes are pinned" \
        "INFLIGHT_SCAN:<n_tasks>" "$skill"
    assert_contains "$profile: the fourth INFLIGHT field is named for what it carries" \
        "is the **archive status**, republished from the" "$skill"
    assert_contains "$profile: absent git evidence is never synthesised away" \
        "Never synthesise a classification from absent git evidence" "$skill"
    assert_contains "$profile: the conflation pair is named, not positional" \
        'and `unclassifiable` are opposites and must never be' "$skill"
    # The closed <reason> vocabulary the plan's Step 5 required. Every value the
    # code can emit must be declared, or t1569_3 branches on undocumented text.
    assert_contains "$profile: <reason> is declared closed" \
        "is a **closed vocabulary**" "$skill"
    for reason in no_local_ref unreadable_tree no_reflog clock_skew timeout scan_error no_tasks; do
        assert_contains "$profile: reason '"'"'$reason'"'"' is declared" \
            "\`$reason\`" "$skill"
    done
    assert_contains "$profile: source_status declares its own scope" \
        "covers **only the two enumeration probes**" "$skill"
    assert_contains "$profile: the tracked line is always emitted" \
        "and is **always emitted**" "$skill"
    assert_contains "$profile: new prefixes are declared digest-excluded" \
        "All five new prefixes are digest-excluded" "$skill"
    assert_contains "$profile: the guarantee is digest identity, not whole-output" \
        "*digest* identity" "$skill"
    assert_contains "$profile: probe health is not completeness" \
        "A healthy probe is not a complete one" "$skill"
    assert_contains "$profile: the enumeration status must not be read as safe" \
        'Never read `both_enumeration_ok` as' "$skill"
    assert_contains "$profile: the extension scope limit is stated" \
        "Path evidence covers only" "$skill"
    assert_contains "$profile: absence of overlap is not safety" \
        "**not** evidence of safety" "$skill"
    assert_contains "$profile: the age unit and its only sentinel are stated" \
        "An unknown age is never rendered as \`0\`" "$skill"
    assert_contains "$profile: planned_new limitation (moved file)" \
        "A file that MOVED away lands there too" "$skill"
    assert_contains "$profile: planned_new limitation (top-level file)" \
        "classifies \`phantom\` rather than \`planned_new\`" "$skill"

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

    # (l) The snapshot PRODUCER for `followup_kind` (t1468_5). The schema
    # property, the enum drift guard and the gatherer's MEMBER field all pass
    # against a writer that never populates anything — this prose IS the
    # producer, so it is the only place the instruction can be pinned.
    assert_contains "$profile: writer populates followup_kind" \
        "followup_kind\`
  from the MEMBER line" "$skill"

    # And the other half: the sentinels must be OMITTED, not stored. This
    # guards the COMMON path — a task with no followup_kind emits \`unknown\`,
    # which is not in the schema enum, so storing it would invalidate every
    # ordinary trail.
    assert_contains "$profile: writer omits the transport sentinels" \
        "OMIT any optional \`snapshot\` field whose MEMBER value is \`unknown\` or" "$skill"
    assert_contains "$profile: sentinels are named as non-values" \
        "transport sentinels, not values" "$skill"

    # (m) The writer emits the bumped schema version.
    assert_contains "$profile: writer emits the current schema_version" \
        '`schema_version`: `"1.1.0"`' "$skill"

    # (n) Depth axis (t1505_4): lite is the DEFAULT and --deep is the opt-out.
    assert_contains "$profile: absence of a depth flag means lite" \
        "**Absence means lite**" "$skill"
    assert_contains "$profile: --deep restores the full analysis" \
        '`--deep` → the full analysis' "$skill"

    # The deep-REFRESH form specifically. `--deep` on create can keep working
    # while a template edit silently breaks the refresh path, and refresh is
    # the escape hatch from the new lite default — so pin the accepted form,
    # not just the flag.
    assert_contains "$profile: deep refresh form is spelled out" \
        '`--refresh <handle> --deep`' "$skill"
    assert_contains "$profile: depth flags are position-independent" \
        "Recognize anywhere in the argument list, before or after" "$skill"

    # Conflicting depth flags fail closed rather than picking one.
    assert_contains "$profile: --deep with --lite is an error" \
        "together is an error" "$skill"

    # (o) Depth never weakens the write gate. The >=2 NON-SKIPPABLE count in
    # (a) proves both banners exist; this pins that depth does not bypass them.
    assert_contains "$profile: depth does not bypass confirmation" \
        "Depth changes how much is analyzed, never whether the write is" "$skill"

    # (p) The lite contract keeps the COMPLETE snapshot. This is the pin that
    # fails if the followup_kind instruction is ever moved into a deep-only
    # block: (l) would still pass from the shared authoring section.
    assert_contains "$profile: lite entries carry a complete snapshot" \
        '**complete `snapshot`** (including `followup_kind` whenever the MEMBER' "$skill"

    # (q) "Omits" means the key is ABSENT — an empty container is not omission.
    # Producer prose must match the validator's lite_shape rule and the board's
    # canonical lite fixture, all three of which test key presence.
    assert_contains "$profile: omission is key-absence, not an empty list" \
        "Omit means the key is absent" "$skill"

    # (r) Recorded depth values are exactly the two the board's label reads.
    assert_contains "$profile: depth marker values are pinned" \
        'exactly those two lowercase' "$skill"

    # (s) End-of-run print: it exists, states the depth, and resolves the
    # summary the same way the By-Trail pane does (same field order, same
    # whitespace handling) so the two surfaces cannot disagree.
    assert_contains "$profile: run summary print is defined" \
        "## Run summary print" "$skill"
    assert_contains "$profile: summary falls back like the board pane" \
        'falling back to' "$skill"
    assert_contains "$profile: summary is stripped, not raw" \
        "surrounding whitespace stripped" "$skill"

    # (t) The deep->lite refresh downgrade names EVERY discarded dimension.
    # A bare "sections will be dropped" hides the two largest losses (the
    # evidence records and their citations), so each is pinned by name.
    assert_contains "$profile: downgrade preflight exists" \
        "Downgrade preflight" "$skill"
    assert_contains "$profile: downgrade names the evidence reduction" \
        "records reduced to 1" "$skill"
    assert_contains "$profile: downgrade names the removed citations" \
        "citations across" "$skill"
    assert_contains "$profile: downgrade names the recovery route" \
        "get --version sha256:<hash>\` retrieves it" "$skill"

    # (u) The belt-and-braces sweep is deep-only — one of the two costs the
    # lite contract removes.
    assert_contains "$profile: sweep is gated to --deep" \
        'Belt-and-braces follow-up sweep — `--deep` only' "$skill"

    # (v) The run must ASSERT its own depth at pre-write validation. This is
    # the pin that matters most of the depth set: `rendering_hints.depth` is
    # authored by the same agent the lite_shape rule constrains, so a check
    # keyed only on the marker is one the writer can opt out of by omitting
    # it. `--expect-depth` comes from parsed arguments instead. Drop this
    # instruction and the lite contract silently becomes advisory again.
    assert_contains "$profile: pre-write validation asserts the depth" \
        "--expect-depth lite|deep" "$skill"
    # Through the WRAPPER, never lib/trail_schema.py directly: skills invoke
    # `.sh` wrappers, bare `python3` is not the framework's interpreter, and
    # only wrapper paths are on the agents' permission allowlists (Codex and
    # OpenCode carry no python allowance at all, so a direct lib call prompts
    # on every single trail write).
    assert_contains "$profile: validation goes through the wrapper" \
        "aitask_trail_depth.sh validate <tmpfile>" "$skill"
    TOTAL=$((TOTAL + 1))
    if grep -q 'python3 .aitask-scripts/lib/' "$golden"; then
        FAIL=$((FAIL + 1))
        echo "FAIL: $profile: skill invokes a lib .py directly instead of a .sh wrapper"
    else
        PASS=$((PASS + 1))
    fi
    assert_contains "$profile: the depth flag is named non-optional" \
        "not optional and not a formality" "$skill"
    assert_contains "$profile: the marker cannot police itself" \
        "silently opt out of by omitting it" "$skill"
    assert_contains "$profile: depth_marker rule is named" \
        "depth_marker" "$skill"

    # Refresh must run the assertion too — it is the flow whose default
    # downgrades an existing trail, so its depth claim is the one to prove.
    assert_contains "$profile: refresh validates with both commands" \
        "Validate with **both** commands of Step 2e.3" "$skill"

    # (w) The grammar is RESOLVED by a deterministic helper, not applied by
    # the model. Without this the model both decides the depth and asserts it,
    # so a wrong-but-self-consistent depth validates cleanly — the resolver is
    # what removes the interpretation step that produces one.
    assert_contains "$profile: depth is resolved by the helper" \
        "aitask_trail_depth.sh resolve --" "$skill"
    assert_contains "$profile: the model must not apply the grammar by hand" \
        "Do not apply the grammar below by hand" "$skill"
    assert_contains "$profile: resolved depth feeds BOTH sinks" \
        "write it into \`rendering_hints.depth\` and pass the same value to" "$skill"
    assert_contains "$profile: the resolved depth is not re-derived" \
        "Do not re-derive it" "$skill"

    # Show has no authoring depth: the resolver says n/a and the flow reports
    # the artifact's STORED depth. Echoing a caller-supplied flag back here
    # would label a lite or unmarked artifact "deep".
    assert_contains "$profile: show reports stored depth, not the flag" \
        "the resolver emits **\`DEPTH:n/a\`**" "$skill"

    # An ambiguous bare handle is not a runnable mode: the skill must RE-RESOLVE
    # after the show-or-refresh choice. Reusing the first call's values is how a
    # supplied --deep reaches a --show chosen afterwards.
    assert_contains "$profile: ambiguous handle is not runnable" \
        "is not a runnable mode" "$skill"
    assert_contains "$profile: ambiguous handle forces a re-resolve" \
        "**re-run the resolver** on a rewritten argument" "$skill"
    assert_contains "$profile: the second run's values are the ones used" \
        "Do not carry the first run's values forward" "$skill"
    # The rewrite REPLACES the bare token. "Keep every original argument" would
    # produce `--show trail-x trail-x --deep`, a mode conflict — so the template
    # must say replace, and show the wrong form explicitly.
    assert_contains "$profile: the bare token is replaced, not kept" \
        "the bare token is *consumed* by the rewrite" "$skill"
    assert_contains "$profile: the wrong rewrite is shown by name" \
        "ERROR:conflicting_modes:--show,trail-x" "$skill"
done

# --- Summary ----------------------------------------------------------------

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
