#!/usr/bin/env bash
set -euo pipefail

# Test ensure_agent_config_seeds() — the populate-missing pass that copies the
# agent config seeds from seed/ into aitasks/metadata/ (t1185).
#
# Regression context: setup_codex_cli() reads ONLY
# aitasks/metadata/codex_config.seed.toml and codex_rules.default.rules, both
# behind `if [[ -f ]]` guards, so a missing seed is a silent no-op — setup
# reports success while leaving .codex/config.toml without the
# default_mode_request_user_input feature that t1171 depends on. The clean
# data-branch initializer never copied those two files (codex_instructions.seed.md
# only survived by riding the incidental `*_instructions.seed.md` glob).
#
# Tests 5 and 6 are the end-to-end pair that existing coverage cannot provide:
# tests/test_agent_instructions.sh hand-writes codex_config.seed.toml into the
# fixture's metadata dir, which masks exactly this gap.

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

# assert_file_contains is single-use here and stays inline (see asserts.sh header).
assert_file_contains() {
    local desc="$1" needle="$2" file="$3"
    TOTAL=$((TOTAL + 1))
    if [[ -f "$file" ]] && grep -qF -- "$needle" "$file"; then
        echo "  PASS: $desc"
        PASS=$((PASS + 1))
    else
        echo "  FAIL: $desc"
        echo "    expected file '$file' to contain: $needle"
        FAIL=$((FAIL + 1))
    fi
}

TESTROOT="$(mktemp -d)"
trap 'rm -rf "$TESTROOT"' EXIT

# Build a fixture project dir. Args after the first are the seed/ basenames to
# populate from the real repo seed/ dir; with none, seed/ is created empty.
make_fixture() {
    local name="$1"; shift
    local dir="$TESTROOT/$name"
    mkdir -p "$dir/.aitask-scripts" "$dir/aitasks/metadata" "$dir/seed"
    local f
    for f in "$@"; do
        cp "$PROJECT_DIR/seed/$f" "$dir/seed/$f"
    done
    echo "$dir"
}

ALL_SEEDS=(
    codex_config.seed.toml
    codex_rules.default.rules
    opencode_config.seed.json
    claude_settings.local.json
)

# Source the setup script to get access to its functions.
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

echo "=== ensure_agent_config_seeds() Tests ==="
echo ""

# --- Test 1: populate-missing ---
echo "--- Test 1: populates every missing seed ---"
DIR1="$(make_fixture t1 "${ALL_SEEDS[@]}")"
(
    SCRIPT_DIR="$DIR1/.aitask-scripts"
    ensure_agent_config_seeds
) > /dev/null
assert_file_exists "T1: codex config seed populated" "$DIR1/aitasks/metadata/codex_config.seed.toml"
assert_file_exists "T1: codex rules seed populated" "$DIR1/aitasks/metadata/codex_rules.default.rules"
assert_file_exists "T1: opencode config seed populated" "$DIR1/aitasks/metadata/opencode_config.seed.json"
# The Claude settings seed is renamed on copy (install.sh applies the same rename).
assert_file_exists "T1: claude settings seed populated under its metadata name" \
    "$DIR1/aitasks/metadata/claude_settings.seed.json"
assert_file_not_exists "T1: claude seed is NOT copied under its seed/ name" \
    "$DIR1/aitasks/metadata/claude_settings.local.json"
# The populated codex config must actually carry the t1171 feature flag.
assert_file_contains "T1: populated codex config carries the t1171 feature" \
    "default_mode_request_user_input = true" "$DIR1/aitasks/metadata/codex_config.seed.toml"

echo ""

# --- Test 2: no-clobber ---
echo "--- Test 2: never overwrites an existing metadata copy ---"
DIR2="$(make_fixture t2 "${ALL_SEEDS[@]}")"
printf 'sentinel = "user customization"\n' > "$DIR2/aitasks/metadata/codex_config.seed.toml"
(
    SCRIPT_DIR="$DIR2/.aitask-scripts"
    ensure_agent_config_seeds
) > /dev/null
assert_eq "T2: existing file left byte-identical" \
    'sentinel = "user customization"' \
    "$(cat "$DIR2/aitasks/metadata/codex_config.seed.toml")"
assert_file_exists "T2: the other seeds still populated alongside it" \
    "$DIR2/aitasks/metadata/codex_rules.default.rules"

echo ""

# --- Test 3: partial seed dir ---
echo "--- Test 3: partial seed/ copies what is there, skips the rest ---"
DIR3="$(make_fixture t3 codex_config.seed.toml)"
(
    SCRIPT_DIR="$DIR3/.aitask-scripts"
    ensure_agent_config_seeds
) > /dev/null
rc3=$?
assert_eq "T3: exits 0 on a partial seed dir" "0" "$rc3"
assert_file_exists "T3: present seed copied" "$DIR3/aitasks/metadata/codex_config.seed.toml"
assert_file_not_exists "T3: absent seed not fabricated" \
    "$DIR3/aitasks/metadata/codex_rules.default.rules"

echo ""

# --- Test 4: no seed/ dir (the tarball-install path) ---
echo "--- Test 4: missing seed/ is a clean no-op ---"
DIR4="$TESTROOT/t4"
mkdir -p "$DIR4/.aitask-scripts" "$DIR4/aitasks/metadata"
(
    SCRIPT_DIR="$DIR4/.aitask-scripts"
    ensure_agent_config_seeds
) > /dev/null
rc4=$?
assert_eq "T4: exits 0 when seed/ is absent" "0" "$rc4"
assert_file_not_exists "T4: no seed fabricated" \
    "$DIR4/aitasks/metadata/codex_config.seed.toml"

echo ""

# --- Tests 5 & 6: end-to-end through setup_codex_cli ---
# Build a codex fixture whose aitasks/metadata/ is deliberately NOT hand-seeded
# with the config/rules — only the skill staging exists. seed/ carries the real
# seeds. This is the shape a clean clone actually has.
make_codex_fixture() {
    local name="$1"
    local dir
    dir="$(make_fixture "$name" \
        codex_config.seed.toml \
        codex_rules.default.rules \
        codex_instructions.seed.md \
        aitasks_agent_instructions.seed.md)"
    mkdir -p "$dir/aitasks/metadata/codex_skills/aitask-pick"
    echo "# Pick skill" > "$dir/aitasks/metadata/codex_skills/aitask-pick/SKILL.md"
    echo "$dir"
}

echo "--- Test 5: end-to-end — clean fixture reaches a configured .codex/config.toml ---"
DIR5="$(make_codex_fixture t5)"
(
    SCRIPT_DIR="$DIR5/.aitask-scripts"
    ensure_agent_config_seeds
    setup_codex_cli < /dev/null
) > /dev/null 2>&1
assert_file_contains "T5: config.toml has the features table" \
    "[features]" "$DIR5/.codex/config.toml"
assert_file_contains "T5: config.toml enables default-mode request_user_input" \
    "default_mode_request_user_input = true" "$DIR5/.codex/config.toml"
assert_file_exists "T5: rules merged from the populated seed" \
    "$DIR5/.codex/rules/default.rules"

echo ""

# Negative control: the SAME fixture without the populate pass must NOT produce
# a configured config.toml. Without this, T5 could pass on incidental fixture
# state rather than on the fix — which is precisely how this bug survived the
# existing suite.
echo "--- Test 6: negative control — skipping the populate pass leaves it unconfigured ---"
DIR6="$(make_codex_fixture t6)"
(
    # shellcheck disable=SC2034  # read by the sourced setup_codex_cli.
    SCRIPT_DIR="$DIR6/.aitask-scripts"
    setup_codex_cli < /dev/null
) > /dev/null 2>&1
TOTAL=$((TOTAL + 1))
if [[ ! -f "$DIR6/.codex/config.toml" ]] || \
   ! grep -qF -- "default_mode_request_user_input" "$DIR6/.codex/config.toml"; then
    echo "  PASS: T6: without the populate pass, the feature flag is absent"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T6: feature flag present without the populate pass"
    echo "    the T5 assertion is not attributable to ensure_agent_config_seeds"
    FAIL=$((FAIL + 1))
fi
# The skill staging still installs — proving the fixture is otherwise viable and
# T6's failure is specific to the missing config seed.
assert_file_exists "T6: skill wrapper still installed (fixture is viable)" \
    "$DIR6/.agents/skills/aitask-pick/SKILL.md"

echo ""

# --- Test 7: data-branch layout (aitasks/ is a symlink into .aitask-data/) ---
# The production layout symlinks aitasks/ -> .aitask-data/aitasks, so the seeds
# must land on the data branch rather than beside the symlink.
echo "--- Test 7: populates through the aitasks/ -> .aitask-data symlink ---"
DIR7="$TESTROOT/t7"
mkdir -p "$DIR7/.aitask-scripts" "$DIR7/seed" "$DIR7/.aitask-data/aitasks/metadata"
ln -s ".aitask-data/aitasks" "$DIR7/aitasks"
cp "$PROJECT_DIR/seed/codex_config.seed.toml" "$DIR7/seed/"
(
    # shellcheck disable=SC2034  # read by the sourced ensure_agent_config_seeds.
    SCRIPT_DIR="$DIR7/.aitask-scripts"
    ensure_agent_config_seeds
) > /dev/null
assert_file_exists "T7: seed landed on the data branch, not beside the symlink" \
    "$DIR7/.aitask-data/aitasks/metadata/codex_config.seed.toml"
assert_file_contains "T7: the populated seed carries the t1171 feature" \
    "default_mode_request_user_input = true" \
    "$DIR7/.aitask-data/aitasks/metadata/codex_config.seed.toml"
TOTAL=$((TOTAL + 1))
if [[ -L "$DIR7/aitasks" ]]; then
    echo "  PASS: T7: aitasks/ is still a symlink after the populate pass"
    PASS=$((PASS + 1))
else
    echo "  FAIL: T7: populate pass replaced the symlink with a real directory"
    FAIL=$((FAIL + 1))
fi

echo ""

# --- Test 8: dangling aitasks/ symlink must not take setup down ---
# `mkdir -p` through a dangling symlink fails; under `set -e` an unguarded
# mkdir would abort the entire `ait setup` run.
echo "--- Test 8: dangling aitasks/ symlink degrades to a warning ---"
DIR8="$TESTROOT/t8"
mkdir -p "$DIR8/.aitask-scripts" "$DIR8/seed"
ln -s ".aitask-data/aitasks" "$DIR8/aitasks"   # target deliberately absent
cp "$PROJECT_DIR/seed/codex_config.seed.toml" "$DIR8/seed/"
(
    # shellcheck disable=SC2034  # read by the sourced ensure_agent_config_seeds.
    SCRIPT_DIR="$DIR8/.aitask-scripts"
    ensure_agent_config_seeds
) > /dev/null 2>&1
rc8=$?
assert_eq "T8: returns 0 instead of aborting setup" "0" "$rc8"

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed"
echo "========================================="
[[ $FAIL -eq 0 ]]
