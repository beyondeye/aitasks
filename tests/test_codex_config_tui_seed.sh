#!/usr/bin/env bash
# test_codex_config_tui_seed.sh - the Codex `[tui]` starfield seed (t1797, t1944).
#
# Codex animates a Braille "starfield" around the idle composer (Astra-family
# models), which keeps `ait monitor` / `ait minimonitor` from ever reading an
# idle Codex pane as idle. The seed switches off ONLY the starfield
# (`[tui] whimsy = false` for codex-cli 0.154, `[tui.effects] starfield = false`
# for 0.160) and never sets `animations`: that is Codex's master switch, and
# with it off the `Working (Ns …)` timer stops ticking, so a working pane reads
# idle (t1944). Framework launches carry the same keys as `-c` overrides
# (tests/test_codeagent.sh Test 11e); this file pins the per-project layer: the
# seed carries the keys, merge_codex_settings ADDS them when absent but never
# overrides an explicit project value, and it retires ONCE the
# `[tui] animations = false` the t1797 seed wrote.
#
# Drives the REAL merge via `aitask_setup.sh --source-only`, like Group D of
# tests/test_session_hook_install.sh. Assertions run in THIS shell (no `( … )`
# groups), so the in-process PASS/FAIL counters stay authoritative.
#
# Run: bash tests/test_codex_config_tui_seed.sh

set -uo pipefail

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

SEED="$PROJECT_DIR/seed/codex_config.seed.toml"
TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

# tui_get <file> <dotted key under [tui]> — repr of the value, or
# ABSENT / NO_TUI / INVALID:<why>.
tui_get() {
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
try:
    d = tomllib.load(open(sys.argv[1], "rb"))
except Exception as e:
    print("INVALID: %s" % e)
    raise SystemExit(0)
node = d.get("tui")
if not isinstance(node, dict):
    print("NO_TUI")
    raise SystemExit(0)
for part in sys.argv[2].split("."):
    if not isinstance(node, dict) or part not in node:
        print("ABSENT")
        raise SystemExit(0)
    node = node[part]
print(repr(node))
PY
}

# effective_starfield <file> <0154|0160> — the starfield preference Codex
# actually applies from the project file: 0.160 aliases tui.whimsy to
# tui.effects.starfield and the canonical key wins when both are set
# (codex-rs/config/src/key_aliases.rs, or_insert); 0.154 reads only whimsy.
# Prints True/False, or DEFAULT when neither spelling is set.
effective_starfield() {
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
tui = tomllib.load(open(sys.argv[1], "rb")).get("tui", {})
effects = tui.get("effects", {}) if isinstance(tui.get("effects"), dict) else {}
if sys.argv[2] == "0160" and "starfield" in effects:
    print(repr(effects["starfield"]))
elif "whimsy" in tui:
    print(repr(tui["whimsy"]))
else:
    print("DEFAULT")
PY
}

# toml_get <file> <dotted.key> — repr of a top-level/nested value.
toml_get() {
    python3 - "$1" "$2" <<'PY'
import sys, tomllib
d = tomllib.load(open(sys.argv[1], "rb"))
for part in sys.argv[2].split("."):
    d = d[part]
print(repr(d))
PY
}

# merge_fixture <name> <existing config content> — prints the merged file path;
# the merge's stderr is kept in <dir>/merge.err.
merge_fixture() {
    local dir="$TESTROOT/$1"
    mkdir -p "$dir/.aitask-scripts" "$dir/.codex"
    printf '%s' "$2" >"$dir/.codex/config.toml"
    merge_codex_settings "$SEED" "$dir/.codex/config.toml" >/dev/null 2>"$dir/merge.err"
    echo "$dir/.codex/config.toml"
}

# assert_starfield_off <label> <file> — both starfield keys present and false.
assert_starfield_off() {
    assert_eq "$1: [tui] whimsy = false" "False" "$(tui_get "$2" whimsy)"
    assert_eq "$1: [tui.effects] starfield = false" "False" "$(tui_get "$2" effects.starfield)"
}

echo "=== Codex [tui] starfield seed (t1797, t1944) ==="

echo ""
echo "--- Group 0: the seed and this repo's own config carry the starfield keys only ---"
assert_starfield_off "0 seed" "$SEED"
assert_eq "0: the seed never sets animations (master switch)" "ABSENT" "$(tui_get "$SEED" animations)"
assert_starfield_off "0 repo config" "$PROJECT_DIR/.codex/config.toml"
assert_eq "0: this repo's config never sets animations" "ABSENT" \
    "$(tui_get "$PROJECT_DIR/.codex/config.toml" animations)"

# shellcheck source=/dev/null
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
# Sourcing turns errexit/nounset ON in this shell; relax them as the sibling
# setup tests do, so a failing probe reports instead of aborting the suite.
set +eu

echo ""
echo "--- Group 1: an existing [tui] table gains the keys, keeping its own ---"
CFG1="$(merge_fixture g1_pet '[tui]
pet = "disabled"
')"
assert_starfield_off "1" "$CFG1"
assert_eq "1: the user's [tui] pet survives" "'disabled'" "$(tui_get "$CFG1" pet)"
assert_eq "1: no animations key is introduced" "ABSENT" "$(tui_get "$CFG1" animations)"

echo ""
echo "--- Group 2: explicit project values WIN, in EFFECT, across both spellings ---"
CFG2="$(merge_fixture g2_explicit '[tui]
animations = true
whimsy = true
')"
assert_eq "2: an explicit animations = true is kept" "True" "$(tui_get "$CFG2" animations)"
assert_eq "2: an explicit whimsy = true is kept" "True" "$(tui_get "$CFG2" whimsy)"
# The seed's own effects.starfield = false would win over whimsy on 0.160; the
# merge must carry the user's value into the missing spelling instead.
assert_eq "2: whimsy = true opt-in stays effective on 0.160" "True" "$(effective_starfield "$CFG2" 0160)"
assert_eq "2: whimsy = true opt-in stays effective on 0.154" "True" "$(effective_starfield "$CFG2" 0154)"

CFG2B="$(merge_fixture g2_canonical '[tui.effects]
starfield = true
')"
assert_eq "2: effects.starfield = true is kept" "True" "$(tui_get "$CFG2B" effects.starfield)"
assert_eq "2: canonical opt-in stays effective on 0.160" "True" "$(effective_starfield "$CFG2B" 0160)"
assert_eq "2: canonical opt-in is mirrored for 0.154" "True" "$(effective_starfield "$CFG2B" 0154)"

CFG2C="$(merge_fixture g2_optout '[tui]
whimsy = false
')"
assert_eq "2: an explicit opt-out stays off on 0.160" "False" "$(effective_starfield "$CFG2C" 0160)"
assert_eq "2: an explicit opt-out stays off on 0.154" "False" "$(effective_starfield "$CFG2C" 0154)"

echo ""
echo "--- Group 3: a config with no [tui] gets the tables ---"
CFG3="$(merge_fixture g3_absent 'model = "gpt-5.6"
')"
assert_starfield_off "3" "$CFG3"
assert_eq "3: the default is effective on 0.160" "False" "$(effective_starfield "$CFG3" 0160)"
assert_eq "3: the default is effective on 0.154" "False" "$(effective_starfield "$CFG3" 0154)"
assert_eq "3: the user's top-level key survives" "'gpt-5.6'" "$(toml_get "$CFG3" model)"

echo ""
echo "--- Group 4: repeated merges are idempotent ---"
merge_codex_settings "$SEED" "$CFG3" >/dev/null 2>&1
merge_codex_settings "$SEED" "$CFG3" >/dev/null 2>&1
assert_starfield_off "4" "$CFG3"
assert_eq "4: exactly one [tui] table header" "1" "$(grep -c '^\[tui\]$' "$CFG3")"
assert_eq "4: exactly one [tui.effects] table header" "1" "$(grep -c '^\[tui\.effects\]$' "$CFG3")"

echo ""
echo "--- Group 5: the t1797 [tui] animations = false is retired exactly once ---"
CFG5="$(merge_fixture g5_t1797 '[tui]
animations = false
')"
assert_eq "5: the t1797-seeded animations = false is removed" "ABSENT" "$(tui_get "$CFG5" animations)"
assert_starfield_off "5" "$CFG5"
assert_contains "5: the retirement is announced" "Removed [tui] animations = false" \
    "$(cat "$TESTROOT/g5_t1797/merge.err")"

CFG5B="$(merge_fixture g5_t1797_pet '[tui]
pet = "disabled"
animations = false
')"
assert_eq "5: retired next to the user's own [tui] key too" "ABSENT" "$(tui_get "$CFG5B" animations)"
assert_eq "5: the user's pet survives the retirement" "'disabled'" "$(tui_get "$CFG5B" pet)"

# A value re-added after the migration sits beside the t1944 keys, so the rule
# no longer matches: the second merge keeps it and says nothing. Each marker is
# checked ON ITS OWN, so a regression in either guard is caught.
for case in "whimsy|[tui]
animations = false
whimsy = false
" "effects|[tui]
animations = false

[tui.effects]
welcome = false
"; do
    name="${case%%|*}"
    CFG5C="$(merge_fixture "g5_readded_$name" "${case#*|}")"
    assert_eq "5: animations = false beside a $name marker is kept (one-shot)" "False" \
        "$(tui_get "$CFG5C" animations)"
    assert_not_contains "5: nothing is announced beside a $name marker" "Removed" \
        "$(cat "$TESTROOT/g5_readded_$name/merge.err")"
done
assert_eq "5: the unrelated effects.welcome survives" "False" \
    "$(tui_get "$TESTROOT/g5_readded_effects/.codex/config.toml" effects.welcome)"

# A project whose seed copy is still the t1797 one would re-add the key, so the
# rule stays out of the way instead of announcing a removal that does not stick.
OLD_SEED="$TESTROOT/old_seed.toml"
printf '[tui]\nanimations = false\n' >"$OLD_SEED"
mkdir -p "$TESTROOT/g5_oldseed/.codex"
printf '[tui]\nanimations = false\n' >"$TESTROOT/g5_oldseed/.codex/config.toml"
merge_codex_settings "$OLD_SEED" "$TESTROOT/g5_oldseed/.codex/config.toml" \
    >/dev/null 2>"$TESTROOT/g5_oldseed/merge.err"
assert_eq "5: an old t1797 seed copy leaves the value alone" "False" \
    "$(tui_get "$TESTROOT/g5_oldseed/.codex/config.toml" animations)"
assert_not_contains "5: and announces no removal" "Removed" \
    "$(cat "$TESTROOT/g5_oldseed/merge.err")"

# A seed that installs NO marker (neither whimsy nor effects) cannot make the
# retirement one-shot: a value re-added afterwards would be removed again on
# every merge. So nothing is retired, twice in a row.
NOMARK_SEED="$TESTROOT/nomarker_seed.toml"
printf 'sandbox_mode = "workspace-write"\n' >"$NOMARK_SEED"
mkdir -p "$TESTROOT/g5_nomark/.codex"
printf '[tui]\nanimations = false\n' >"$TESTROOT/g5_nomark/.codex/config.toml"
for pass in 1 2; do
    merge_codex_settings "$NOMARK_SEED" "$TESTROOT/g5_nomark/.codex/config.toml" \
        >/dev/null 2>"$TESTROOT/g5_nomark/merge$pass.err"
    assert_eq "5: a marker-less seed retires nothing (merge $pass)" "False" \
        "$(tui_get "$TESTROOT/g5_nomark/.codex/config.toml" animations)"
    assert_not_contains "5: a marker-less seed announces nothing (merge $pass)" "Removed" \
        "$(cat "$TESTROOT/g5_nomark/merge$pass.err")"
done

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
