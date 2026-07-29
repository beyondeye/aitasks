#!/usr/bin/env bash
# tests/lib/codeagent_defaults.sh — shared helpers for tests that assert how
# `aitask_codeagent.sh resolve <op>` picks a per-operation default agent string.
#
# Source AFTER tests/lib/asserts.sh, via the absolute $PROJECT_DIR path:
#     . "$PROJECT_DIR/tests/lib/asserts.sh"
#     . "$PROJECT_DIR/tests/lib/codeagent_defaults.sh"
#
# WHY (t1318): three test files pinned literal model names as the expected
# per-operation default. t1241 promoted the shipped defaults to claudecode/opus5
# and left all three permanently red, so the suites they belong to carried no
# regression signal. Two rules follow from that:
#
#   1. DERIVE the expected value from the same config the resolver reads, so a
#      deliberate promotion cannot rot the assertion.
#   2. Never assert the real DEFAULT_AGENT_STRING. Inject a *sentinel* through
#      the env instead — that is what keeps "the config was read" distinguishable
#      from "we fell through to the hardcoded default". Without it the assertion
#      goes vacuous whenever the two happen to agree (they do today: both are
#      claudecode/opus5).
#
# The resolution chain under test lives in aitask_codeagent.sh
# resolve_agent_string(): --agent-string → codeagent_config.local.json →
# codeagent_config.json → $DEFAULT_AGENT_STRING. Both METADATA_DIR and
# DEFAULT_AGENT_STRING are `${VAR:-…}` in lib/agent_string.sh, so both are
# env-overridable — that is the seam these helpers drive.
#
# BSD-safe: jq + POSIX shell only, no GNU-only grep/sed. bash-3.2-safe (no
# mapfile, declare -A, or ${var^^}). See aidocs/framework/sed_macos_issues.md.

# Idempotent: guard against double-sourcing.
[[ -n "${_AIT_CODEAGENT_DEFAULTS_LOADED:-}" ]] && return 0
_AIT_CODEAGENT_DEFAULTS_LOADED=1

# codeagent_fixture_metadata <dest_dir> [<config_src>]
#
# Populate <dest_dir> as a hermetic METADATA_DIR for aitask_codeagent.sh:
# every models_<agent>.json registry (`resolve` needs them to emit its CLI_ID
# line — without them it prints AGENT_STRING: and then exits 1) plus
# project_config.yaml. When <config_src> is given it is installed as
# codeagent_config.json; omit it to build the no-config fallback fixture.
#
# codeagent_config.local.json is deliberately NEVER copied. It is a gitignored
# per-developer override that outranks the project config, so copying it would
# make every derived expectation depend on whose machine the suite runs on.
#
# $AIT_CODEAGENT_FIXTURE_OMIT_OPS (csv of operation names) drops those keys from
# the installed config. Two uses: building the "config present but this op is
# missing" fixture, and acting as the negative-control seam — a reviewer can
# prove the assertions still fail without editing any tracked file:
#     AIT_CODEAGENT_FIXTURE_OMIT_OPS=learn bash tests/test_shadow_spawn_learner.sh
codeagent_fixture_metadata() {
    local dest="$1" config_src="${2:-}"
    local src_meta="$PROJECT_DIR/aitasks/metadata"

    mkdir -p "$dest"
    cp "$src_meta"/models_*.json "$dest/"
    cp "$src_meta/project_config.yaml" "$dest/"

    [[ -n "$config_src" ]] || return 0

    if [[ -n "${AIT_CODEAGENT_FIXTURE_OMIT_OPS:-}" ]]; then
        jq --arg ops "$AIT_CODEAGENT_FIXTURE_OMIT_OPS" \
            'reduce ($ops | split(",")[]) as $op (.; del(.defaults[$op]))' \
            "$config_src" > "$dest/codeagent_config.json"
    else
        cp "$config_src" "$dest/codeagent_config.json"
    fi
}

# codeagent_config_default <op> <config_file>
#
# Print the configured default agent string for <op>, or nothing when the key
# (or the file) is absent. Uses the same jq expression as the resolver itself,
# so the test and production read the config identically.
codeagent_config_default() {
    local op="$1" config="$2"

    [[ -f "$config" ]] || return 0
    jq -r --arg op "$op" '.defaults[$op] // empty' "$config" 2>/dev/null || true
}

# codeagent_resolve_field <field> <resolve_output>
#
# Extract one `KEY:value` field from `aitask_codeagent.sh resolve` output (e.g.
# AGENT_STRING, MODEL, CLI_ID), so callers can assert_eq on the exact value.
#
# Exact extraction, not substring matching, is deliberate. assert_contains
# "AGENT_STRING:$expected" degrades into the always-true "AGENT_STRING:" when
# $expected is empty, and lets a prefix (opus5) match a longer registered name
# (opus5_1m). Appending a newline to anchor it does not work either: the assert
# helpers use `grep -F`, which reads an embedded newline as a SECOND, empty
# pattern that matches every line — making assert_not_contains unpassable.
codeagent_resolve_field() {
    local field="$1" out="$2"

    printf '%s\n' "$out" | sed -n "s/^$field://p" | head -n 1
}

# codeagent_sentinel_excluding <metadata_dir> [<agent_string>...]
#
# Print a registered agent string that is none of the excluded ones, for use as
# an injected DEFAULT_AGENT_STRING sentinel.
#
# Scanning <metadata_dir> instead of assuming an agent family keeps this
# agent-agnostic — a codex/ or opencode/ default (defaults.shadow is
# codex/gpt5_6_terra today) still gets a valid sentinel — and guarantees the
# model is registered in the very directory the `resolve` under test will read,
# so the sentinel always resolves cleanly instead of erroring on a missing
# model entry. Returns non-zero (fail-closed) if no candidate survives.
codeagent_sentinel_excluding() {
    local meta="$1"
    shift
    # Agent strings never contain spaces, so a space-delimited membership test
    # is sound and avoids an empty-array expansion under `set -u`.
    local excluded=" $* "
    local f agent name candidate

    for f in "$meta"/models_*.json; do
        [[ -f "$f" ]] || continue
        agent="$(basename "$f" .json)"
        agent="${agent#models_}"
        while IFS= read -r name; do
            [[ -n "$name" ]] || continue
            candidate="$agent/$name"
            case "$excluded" in
                *" $candidate "*) continue ;;
            esac
            printf '%s\n' "$candidate"
            return 0
        done < <(jq -r '.models[].name' "$f")
    done

    return 1
}
