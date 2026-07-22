#!/usr/bin/env bash
# Tests for aitask_prune_retired_skills.sh — the retired-skill upgrade migration.
# Run: bash tests/test_prune_retired_skills.sh
#
# This is an UPGRADE fixture, not a fresh checkout: the temp project is
# populated the way an already-installed project looks after it upgraded past
# the retirement — every wrapper location the release tarball fans out to, a
# mix of git-tracked and untracked, plus live neighbours whose names sit one
# character away from the retired ones.
#
# The two guards under test:
#   Rule 1 — exact-name matching (never prefix-glob): `aitask-pickn` must not
#            catch `aitask-pick`, `task-workflown` must not catch
#            `task-workflow`.
#   Rule 2 — content-hash ownership: a user-modified or user-authored file at a
#            retired path is preserved, never deleted.
# Both have an explicit negative control that runs a deliberately broken copy of
# the helper and asserts it DOES cause the damage — so a regression that
# weakens either guard cannot pass silently.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

cd "$PROJECT_DIR"

PRUNER="$PROJECT_DIR/.aitask-scripts/aitask_prune_retired_skills.sh"
MANIFEST="$PROJECT_DIR/.aitask-scripts/retired_skills_manifest.txt"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
PROJ="$TMP/proj"

# Two DIFFERENT framework-owned blobs from the manifest. The SHA set is flat by
# design (it must also match the staging copies, which are byte-for-byte cp's of
# the agent-tree wrappers), so any manifest SHA placed at any retired path is
# framework-owned. Using two distinct ones also covers "content from an older
# shipped release" without hard-coding a version.
SHA_A="$(grep '^SHA'"$(printf '\t')" "$MANIFEST" | sed -n '1p' | cut -f2)"
SHA_B="$(grep '^SHA'"$(printf '\t')" "$MANIFEST" | sed -n '2p' | cut -f2)"

if [[ -z "$SHA_A" || -z "$SHA_B" || "$SHA_A" == "$SHA_B" ]]; then
    echo "FAIL: could not read two distinct SHA records from $MANIFEST"
    exit 1
fi

# Write framework-owned content (a real shipped blob) to a fixture path.
shipped() {
    local sha="$1" dest="$2"
    mkdir -p "$(dirname "$dest")"
    git cat-file blob "$sha" > "$dest"
}

# Write user content (never a shipped blob) to a fixture path.
mine() {
    local dest="$1" body="$2"
    mkdir -p "$(dirname "$dest")"
    printf '%s\n' "$body" > "$dest"
}

build_fixture() {
    rm -rf "$PROJ"
    mkdir -p "$PROJ"

    # --- retired: fully framework-owned (must be PRUNED) ---
    shipped "$SHA_A" "$PROJ/.claude/skills/aitask-pickn/SKILL.md"
    shipped "$SHA_B" "$PROJ/.claude/skills/aitask-pickn/SKILL.md.j2"   # older shipped version
    shipped "$SHA_A" "$PROJ/.agents/skills/aitask-pickn/SKILL.md"
    shipped "$SHA_A" "$PROJ/.opencode/commands/aitask-pickn.md"
    shipped "$SHA_A" "$PROJ/aitasks/metadata/codex_skills/aitask-pickn/SKILL.md"
    shipped "$SHA_A" "$PROJ/aitasks/metadata/opencode_commands/aitask-pickn.md"

    # --- retired: user-touched (must be KEPT) ---
    # a) directory where ONE file among shipped ones was modified
    shipped "$SHA_A" "$PROJ/.claude/skills/task-workflown/SKILL.md"
    mine "$PROJ/.claude/skills/task-workflown/planning.md" "# my local tweak"
    # b) a user's own unrelated skill parked at a retired name (untracked)
    mine "$PROJ/.opencode/skills/aitask-pickn/SKILL.md" "# my own pickn skill"
    # c) a hand-edited untracked staging wrapper
    mine "$PROJ/aitasks/metadata/opencode_skills/aitask-pickn/SKILL.md" "# edited staging"

    # --- retired rendered closures (normal shape: only .md, SKILL.md present) ---
    mine "$PROJ/.claude/skills/aitask-pickn-fast-/SKILL.md" "# hand-edited render"
    mine "$PROJ/.claude/skills/task-workflown-default-/SKILL.md" "# generated"
    mine "$PROJ/.claude/skills/task-workflown-default-/planning.md" "# generated"
    mine "$PROJ/.agents/skills/aitask-pickn-fast-codex-/SKILL.md" "# generated"

    # --- LIVE NEIGHBOURS: names one character from the retired ones ---
    mine "$PROJ/.claude/skills/aitask-pick/SKILL.md" "# live pick stub"
    mine "$PROJ/.claude/skills/task-workflow/SKILL.md" "# live workflow"
    mine "$PROJ/.claude/skills/aitask-pick-fast-/SKILL.md" "# live pick render"
    mine "$PROJ/.claude/skills/task-workflow-remote-/SKILL.md" "# live workflow render"
    mine "$PROJ/.agents/skills/task-workflow-fast-codex-/SKILL.md" "# live codex render"
    mine "$PROJ/.opencode/commands/aitask-pick.md" "# live pick command"

    # Track a subset, leaving the rest untracked (an installed project has both).
    git -C "$PROJ" init -q .
    git -C "$PROJ" config user.email test@example.com
    git -C "$PROJ" config user.name test
    git -C "$PROJ" add .claude .opencode/commands >/dev/null 2>&1
    git -C "$PROJ" commit -qm fixture >/dev/null 2>&1
}

# Snapshot every file's path+hash, so "byte-identical afterwards" is provable.
snapshot() {
    (cd "$PROJ" && find . -path ./.git -prune -o -type f -print0 \
        | sort -z | xargs -0 -r shasum 2>/dev/null)
}

echo "=== Test 1: default mode — prune framework-owned, preserve everything else ==="
build_fixture
BEFORE="$(snapshot)"
set +e
OUT="$("$PRUNER" --dir "$PROJ" 2>"$TMP/err1")"
RC=$?
set -e
ERR="$(cat "$TMP/err1")"

assert_eq "exit 0 even when paths were kept" "0" "$RC"

for p in \
    ".claude/skills/aitask-pickn" \
    ".agents/skills/aitask-pickn" \
    ".opencode/commands/aitask-pickn.md" \
    "aitasks/metadata/codex_skills/aitask-pickn" \
    "aitasks/metadata/opencode_commands/aitask-pickn.md" ; do
    assert_contains "PRUNED: $p" "PRUNED:$p" "$OUT"
    assert_file_not_exists "removed from disk: $p" "$PROJ/$p"
done

echo "--- Rule 2: user-touched retired paths are preserved ---"
assert_contains "KEPT dir with one modified file" \
    "KEPT:.claude/skills/task-workflown:unrecognized-content" "$OUT"
assert_contains "KEPT user's own skill at a retired name" \
    "KEPT:.opencode/skills/aitask-pickn:unrecognized-content" "$OUT"
assert_contains "KEPT hand-edited staging wrapper" \
    "KEPT:aitasks/metadata/opencode_skills/aitask-pickn:unrecognized-content" "$OUT"

# ALL-OR-NOTHING: the unmodified sibling inside the kept dir survives too.
assert_file_exists "no partial delete: modified file survives" \
    "$PROJ/.claude/skills/task-workflown/planning.md"
assert_file_exists "no partial delete: unmodified sibling survives" \
    "$PROJ/.claude/skills/task-workflown/SKILL.md"

echo "--- rendered closures are never deleted by an upgrade ---"
for p in \
    ".claude/skills/aitask-pickn-fast-" \
    ".claude/skills/task-workflown-default-" \
    ".agents/skills/aitask-pickn-fast-codex-" ; do
    assert_contains "KEPT closure $p" "KEPT:$p:rendered-closure-not-verifiable" "$OUT"
    assert_dir_exists "closure still on disk: $p" "$PROJ/$p"
done
# The case a shape check would have destroyed: normal shape, hand-edited body.
assert_eq "hand-edited closure SKILL.md is byte-identical" \
    "# hand-edited render" "$(cat "$PROJ/.claude/skills/aitask-pickn-fast-/SKILL.md")"

echo "--- Rule 1 negative control: live neighbours untouched ---"
for p in \
    ".claude/skills/aitask-pick/SKILL.md" \
    ".claude/skills/task-workflow/SKILL.md" \
    ".claude/skills/aitask-pick-fast-/SKILL.md" \
    ".claude/skills/task-workflow-remote-/SKILL.md" \
    ".agents/skills/task-workflow-fast-codex-/SKILL.md" \
    ".opencode/commands/aitask-pick.md" ; do
    assert_file_exists "live neighbour survives: $p" "$PROJ/$p"
    assert_not_contains "no PRUNED for live neighbour: $p" "PRUNED:$p" "$OUT"
done

echo "--- the closing warning is actionable ---"
assert_contains "warning names a kept path" ".opencode/skills/aitask-pickn" "$ERR"
assert_contains "warning gives the cleanup command" "rm -rf .claude/skills/task-workflown" "$ERR"

echo "--- tracked deletions are visible to the installer's commit machinery ---"
# install.sh / aitask_setup.sh stage via `git ls-files --modified`, which
# reports deletions; this is why the helper itself never touches the index.
MOD="$(git -C "$PROJ" ls-files --modified)"
assert_contains "deletion of tracked retired file is reported by ls-files -m" \
    ".claude/skills/aitask-pickn/SKILL.md" "$MOD"
assert_not_contains "live neighbour not reported as modified" \
    ".claude/skills/aitask-pick/SKILL.md" "$MOD"

echo "=== Test 2: idempotence — no further removals, same KEPT set ==="
AFTER1="$(snapshot)"
set +e
OUT2="$("$PRUNER" --dir "$PROJ" 2>/dev/null)"
RC2=$?
set -e
AFTER2="$(snapshot)"

assert_eq "second run exits 0" "0" "$RC2"
assert_not_contains "second run removes nothing" "PRUNED:" "$OUT2"
assert_eq "second run leaves the tree byte-identical" "$AFTER1" "$AFTER2"
assert_eq "KEPT set repeats identically (it is a standing report)" \
    "$(printf '%s\n' "$OUT" | grep '^KEPT:' | sort)" \
    "$(printf '%s\n' "$OUT2" | grep '^KEPT:' | sort)"

echo "=== Test 3: --prune-rendered removes closures, still exact-name ==="
build_fixture
set +e
OUT3="$("$PRUNER" --dir "$PROJ" --prune-rendered 2>/dev/null)"
set -e
assert_contains "closure pruned under the flag" \
    "PRUNED:.claude/skills/aitask-pickn-fast-" "$OUT3"
assert_dir_not_exists "closure gone" "$PROJ/.claude/skills/aitask-pickn-fast-"
assert_dir_not_exists "codex closure gone" "$PROJ/.agents/skills/aitask-pickn-fast-codex-"
assert_dir_exists "live render survives --prune-rendered" \
    "$PROJ/.claude/skills/aitask-pick-fast-"
assert_dir_exists "live workflow render survives --prune-rendered" \
    "$PROJ/.claude/skills/task-workflow-remote-"
assert_dir_exists "live codex render survives --prune-rendered" \
    "$PROJ/.agents/skills/task-workflow-fast-codex-"

echo "=== Test 4: negative controls — the guards are load-bearing ==="
# A passing suite proves nothing unless a weakened guard actually breaks it.
# Each control is a deliberately broken copy of the helper; the assertion is
# that it DOES cause the damage the real helper avoids.

# A control must run to completion — it resolves lib/ and the manifest relative
# to its own dir, so give it a staging dir that mirrors .aitask-scripts/.
CTRL_DIR="$TMP/ctrl"
mkdir -p "$CTRL_DIR"
ln -s "$PROJECT_DIR/.aitask-scripts/lib" "$CTRL_DIR/lib"
ln -s "$MANIFEST" "$CTRL_DIR/retired_skills_manifest.txt"

BROKEN_GLOB="$CTRL_DIR/broken_glob.sh"
# shellcheck disable=SC2016  # the sed patterns are literal shell source, not expansions
sed -e 's/\[\[ "\$base" == "\${stem}-"\*"-" \]\]/[[ "$base" == "${stem}"*"-" ]]/' \
    -e 's/-name "\${stem}-\*-"/-name "${stem}*-"/' \
    "$PRUNER" > "$BROKEN_GLOB"
chmod +x "$BROKEN_GLOB"
assert_eq "glob control is actually a mutation" "differ" \
    "$(cmp -s "$PRUNER" "$BROKEN_GLOB" && echo same || echo differ)"

# Rule 1's hazard is a retired stem that is a PREFIX of a LIVE one. The shipped
# manifest has no such pair (`aitask-pickn` is LONGER than `aitask-pick`, and a
# longer prefix cannot swallow a shorter name), so the control inverts them with
# a synthetic manifest: retire `aitask-pick` while `aitask-pickn` is live. This
# is the situation the next retirement can easily land in.
INV_MANIFEST="$CTRL_DIR/inverted_manifest.txt"
grep -v '^STEM'"$(printf '\t')" "$MANIFEST" > "$INV_MANIFEST"
printf 'STEM\taitask-pick\n' >> "$INV_MANIFEST"

build_fixture
set +e
"$PRUNER" --dir "$PROJ" --manifest "$INV_MANIFEST" --prune-rendered >/dev/null 2>&1
RC_G_OK=$?
set -e
assert_eq "real helper ran with the inverted manifest" "0" "$RC_G_OK"
assert_dir_not_exists "real helper removes the retired stem's render" \
    "$PROJ/.claude/skills/aitask-pick-fast-"
assert_dir_exists "real helper SPARES the live longer-named render (Rule 1)" \
    "$PROJ/.claude/skills/aitask-pickn-fast-"

build_fixture
set +e
"$BROKEN_GLOB" --dir "$PROJ" --manifest "$INV_MANIFEST" --prune-rendered \
    >/dev/null 2>"$TMP/ctrl_glob.err"
RC_G=$?
set -e
# Assert it RAN — a control that dies on startup proves nothing.
assert_eq "glob control ran to completion" "0" "$RC_G"
assert_dir_not_exists "prefix-glob control DOES swallow the live render (Rule 1 is load-bearing)" \
    "$PROJ/.claude/skills/aitask-pickn-fast-"

BROKEN_HASH="$CTRL_DIR/broken_hash.sh"
sed 's/^is_known_blob() {$/is_known_blob() { return 0/' "$PRUNER" > "$BROKEN_HASH"
chmod +x "$BROKEN_HASH"
assert_eq "hash control is actually a mutation" "differ" \
    "$(cmp -s "$PRUNER" "$BROKEN_HASH" && echo same || echo differ)"

build_fixture
set +e
"$BROKEN_HASH" --dir "$PROJ" >/dev/null 2>"$TMP/ctrl_hash.err"
RC_H=$?
set -e
assert_eq "hash control ran to completion" "0" "$RC_H"
assert_dir_not_exists "hash-less control DOES destroy the user's own skill (Rule 2 is load-bearing)" \
    "$PROJ/.opencode/skills/aitask-pickn"
assert_dir_not_exists "hash-less control DOES destroy the modified directory" \
    "$PROJ/.claude/skills/task-workflown"

echo "=== Test 5: missing manifest is a no-op, not a failure ==="
build_fixture
set +e
OUT5="$("$PRUNER" --dir "$PROJ" --manifest "$TMP/does-not-exist.txt" 2>/dev/null)"
RC5=$?
set -e
assert_eq "missing manifest exits 0" "0" "$RC5"
assert_eq "missing manifest prunes nothing" "" "$OUT5"
assert_dir_exists "retired path untouched without a manifest" \
    "$PROJ/.claude/skills/aitask-pickn"

# Unused-variable guard for the initial snapshot (kept for readability above).
: "$BEFORE"

echo ""
echo "Tests: $TOTAL, Passed: $PASS, Failed: $FAIL"
[[ "$FAIL" -eq 0 ]] || exit 1
