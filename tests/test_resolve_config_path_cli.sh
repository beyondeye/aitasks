#!/usr/bin/env bash
# test_resolve_config_path_cli.sh - Tests for aitask_resolve_config_path.sh (t1071_6).
# Run: bash tests/test_resolve_config_path_cli.sh
#
# The CLI is the shell seam over config_utils.resolve_config_path that skills
# (aitask-learn-skill/generate.md) shell out to. These tests pin the parts the
# Python unit test can't reach — the shell contract itself:
#   1. Documented invocation (relative ./... from repo root) resolves a SET key
#      and, when unset, the seeded default — proving a non-empty success path.
#   2. cwd-independence: invoked by absolute path from a foreign cwd, it still
#      resolves the repo's own config (BASH_SOURCE repo-root discovery).
#   3. Always-exit-0 / single-empty-line contract when python3 is unavailable
#      (so a broken Python env can never abort the caller).
#   4. generate.md actually CONSUMES the resolver (not merely mentions a guide),
#      and the old hard-coded sole-source phrasing is gone.
#   5. Nested doc_update.guide with a quoted value + inline comment resolves
#      through the CLI (t1110 — the exact case the docs-gate's old grep failed).
#   6. The docs-updated gate skill consumes the resolver and no longer carries
#      the inline grep read (t1110).
#
# Runs inside throwaway temp repos (copies of the script + config_utils.py) so
# the real repo is never touched.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=tests/lib/asserts.sh disable=SC1091
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

REAL_HELPER="$PROJECT_DIR/.aitask-scripts/aitask_resolve_config_path.sh"
REAL_LIB="$PROJECT_DIR/.aitask-scripts/lib/config_utils.py"
GENERATE_MD="$PROJECT_DIR/.claude/skills/aitask-learn-skill/generate.md"
DOCS_GATE_MD="$PROJECT_DIR/.claude/skills/aitask-gate-docs-updated/SKILL.md"

TMPDIRS=()
cleanup() {
    local d
    for d in "${TMPDIRS[@]}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

# make_repo -> echoes a fresh temp repo skeleton path (script + lib copied in).
make_repo() {
    local d
    d="$(mktemp -d)"
    TMPDIRS+=("$d")
    mkdir -p "$d/.aitask-scripts/lib" "$d/aitasks/metadata"
    cp "$REAL_HELPER" "$d/.aitask-scripts/aitask_resolve_config_path.sh"
    cp "$REAL_LIB" "$d/.aitask-scripts/lib/config_utils.py"
    chmod +x "$d/.aitask-scripts/aitask_resolve_config_path.sh"
    printf '%s\n' "$d"
}

DEFAULT_REL="aireviewguides/aiagents/skill_authoring_best_practices.md"

# ============================================================
# Case 1 - documented invocation (relative from repo root): SET key + default
# ============================================================
repo="$(make_repo)"
mkdir -p "$repo/custom" "$repo/$(dirname "$DEFAULT_REL")"
echo guide > "$repo/custom/house.md"
echo guide > "$repo/$DEFAULT_REL"

# 1a: key SET to a readable file -> echoes the configured path.
printf 'learn_skill_authoring_guide: custom/house.md\n' > "$repo/aitasks/metadata/project_config.yaml"
out="$(cd "$repo" && ./.aitask-scripts/aitask_resolve_config_path.sh learn_skill_authoring_guide "$DEFAULT_REL")"
assert_eq "documented invocation, key set -> configured path" "custom/house.md" "$out"

# 1b: key UNSET, default present -> echoes the default path.
printf 'other: 1\n' > "$repo/aitasks/metadata/project_config.yaml"
out="$(cd "$repo" && ./.aitask-scripts/aitask_resolve_config_path.sh learn_skill_authoring_guide "$DEFAULT_REL")"
assert_eq "documented invocation, key unset -> default path" "$DEFAULT_REL" "$out"

# 1c: key unset, NO default arg -> empty line.
out="$(cd "$repo" && ./.aitask-scripts/aitask_resolve_config_path.sh learn_skill_authoring_guide)"
assert_eq "no default, unset -> empty" "" "$out"

# ============================================================
# Case 2 - cwd-independence (absolute path invocation from a foreign cwd)
# ============================================================
repo="$(make_repo)"
mkdir -p "$repo/custom"
echo guide > "$repo/custom/house.md"
printf 'learn_skill_authoring_guide: custom/house.md\n' > "$repo/aitasks/metadata/project_config.yaml"
foreign="$(mktemp -d)"; TMPDIRS+=("$foreign")
out="$(cd "$foreign" && "$repo/.aitask-scripts/aitask_resolve_config_path.sh" learn_skill_authoring_guide)"
assert_eq "absolute invocation from foreign cwd resolves repo config" "custom/house.md" "$out"

# ============================================================
# Case 3 - always-exit-0 / single-empty-line when python3 is unavailable
# ============================================================
repo="$(make_repo)"
mkdir -p "$repo/custom"
echo guide > "$repo/custom/house.md"
printf 'learn_skill_authoring_guide: custom/house.md\n' > "$repo/aitasks/metadata/project_config.yaml"
# Minimal PATH that keeps the one external the script needs (dirname) but hides
# python3, so `command -v python3` fails and the resolver must degrade to empty.
stubbin="$(mktemp -d)"; TMPDIRS+=("$stubbin")
ln -s "$(command -v dirname)" "$stubbin/dirname"
bash_bin="$(command -v bash)"
set +e
out="$(PATH="$stubbin" "$bash_bin" "$repo/.aitask-scripts/aitask_resolve_config_path.sh" learn_skill_authoring_guide "$DEFAULT_REL")"
rc=$?
set -e
assert_exit_zero_rc "no python3 -> exit 0" "$rc"
assert_eq "no python3 -> single empty line" "" "$out"

# ============================================================
# Case 4 - generate.md consumes the resolver (real file)
# ============================================================
assert_file_exists "generate.md present" "$GENERATE_MD"
gen="$(cat "$GENERATE_MD")"
assert_contains "generate.md invokes the resolver" "aitask_resolve_config_path.sh" "$gen"
assert_contains "generate.md names the config key" "learn_skill_authoring_guide" "$gen"
assert_not_contains "old hard-coded sole-source phrasing removed" \
    "By default, read the best-practices guide" "$gen"

# ============================================================
# Case 5 - nested doc_update.guide, quoted value + inline comment (t1110)
# ============================================================
repo="$(make_repo)"
mkdir -p "$repo/custom"
echo guide > "$repo/custom/guide.md"
printf 'doc_update:\n  guide: "custom/guide.md"  # note\n' > "$repo/aitasks/metadata/project_config.yaml"
out="$(cd "$repo" && ./.aitask-scripts/aitask_resolve_config_path.sh doc_update.guide aitasks/metadata/doc_update_guide.md)"
assert_eq "nested key, quoted + commented value -> configured path" "custom/guide.md" "$out"

# ============================================================
# Case 6 - docs-updated gate skill consumes the resolver (real file)
# ============================================================
assert_file_exists "docs-updated SKILL.md present" "$DOCS_GATE_MD"
gate="$(cat "$DOCS_GATE_MD")"
assert_contains "docs-updated skill invokes the resolver" "aitask_resolve_config_path.sh" "$gate"
assert_contains "docs-updated skill names the config key" "doc_update.guide" "$gate"
assert_not_contains "old inline grep read removed" \
    "grep -A3 '^doc_update:'" "$gate"

# ============================================================
# Summary
# ============================================================
echo ""
echo "=============================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
echo "=============================="

if [[ "$FAIL" -gt 0 ]]; then
    exit 1
fi
