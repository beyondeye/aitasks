#!/usr/bin/env bash
# test_codex_entrypoints_tool_mapping.sh - every Codex entry point loads
# .agents/skills/codex_tool_mapping.md (t2297).
#
# Pins:
#   A. every Codex skill wrapper/stub under .agents/skills/ points at the
#      mapping, and every profile-aware stub carries the shared fragment right
#      after its frontmatter (the scan count is tied to the SKILL.md.j2 count,
#      so a stub silently dropped from the scan fails);
#   B. the stub generator emits that fragment before the stub steps;
#   C. the renderer gives every rendered Codex SKILL.md — entry point and
#      closure skill — the fragment, never a procedure file and never another
#      agent; the committed -remote-codex- prerenders carry it on disk;
#   D. the mapping still carries the plain-prose fallback and names the opt-in;
#   E. negative controls: the same checkers flag a stub / rendered entry with
#      the fragment stripped;
#   F. one source: generator, renderer and the awk fallback all emit the
#      fragment file verbatim, and the awk fallback equals the renderer's
#      inject_entry_prereq byte for byte;
#   R. refresh_codex_rendered_entries (ait setup + install.sh, the ait upgrade
#      route): render path, fallback path, scope, an upgrade fixture with a
#      pre-change rendered variant that is never entered through its stub, and
#      the wiring of both callers.
#
# Run: bash tests/test_codex_entrypoints_tool_mapping.sh

set -uo pipefail

PASS=0
FAIL=0
# shellcheck disable=SC2034  # TOTAL is mutated by the sourced asserts.sh helpers.
TOTAL=0

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/framework_copy.sh
. "$PROJECT_DIR/tests/lib/framework_copy.sh"

MARK='.agents/skills/codex_tool_mapping.md'
FRAG="$PROJECT_DIR/.aitask-scripts/skill_templates/_codex_entry_prereq.md"
MAPPING="$PROJECT_DIR/.agents/skills/codex_tool_mapping.md"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# A python that can render (minijinja + yaml). Probed by import only — never by
# running the code under test.
PY=""
for cand in "$HOME/.aitask/venv/bin/python" "${AITASKS_HOME:-$HOME/.aitasks}/venv/bin/python"; do
    if [[ -x "$cand" ]] && "$cand" -c 'import minijinja, yaml' 2>/dev/null; then PY="$cand"; break; fi
done

# --- checkers (shared by the positive checks and the negative controls) ------
has_pointer() { grep -qF "$MARK" "$1"; }

# 0 iff the fragment's lines follow the frontmatter's closing `---` after one
# blank line — the position both the generator and the renderer promise.
fragment_after_frontmatter() {
    local file="$1" n got
    n="$(wc -l < "$FRAG" | tr -d ' ')"
    got="$(awk -v n="$n" '
        NR == 1 && $0 == "---" { fm = 1; next }
        fm && $0 == "---" { fm = 0; after = 1; next }
        after == 1 { if ($0 != "") exit; after = 2; next }
        after == 2 && taken < n { print; taken++ }
    ' "$file")"
    [[ "$got" == "$(cat "$FRAG")" ]]
}

echo "=== Codex entry points load codex_tool_mapping.md (t2297) ==="

echo ""
echo "--- A: wrappers and stubs ---"
assert_file_exists "A mapping file exists" "$MAPPING"
assert_file_exists "A fragment file exists" "$FRAG"
assert_contains "A fragment names the mapping path" "$MARK" "$(cat "$FRAG")"

checked=0 stubs=0 missing=""
for d in "$PROJECT_DIR"/.agents/skills/*/; do
    name="$(basename "$d")"
    [[ "$name" == *- ]] && continue                       # rendered variant
    [[ -f "$d/SKILL.md" ]] || continue
    [[ -d "$PROJECT_DIR/.claude/skills/$name" ]] || continue
    checked=$((checked + 1))
    has_pointer "$d/SKILL.md" || missing+=" $name"
    if grep -q 'profile-aware skill stub' "$d/SKILL.md"; then
        stubs=$((stubs + 1))
        fragment_after_frontmatter "$d/SKILL.md" || missing+=" $name(position)"
    fi
done
assert_eq "A every Codex wrapper/stub points at the mapping" "" "$missing"
templated_with_stub=0
for t in "$PROJECT_DIR"/.claude/skills/*/SKILL.md.j2; do
    s="$(basename "$(dirname "$t")")"
    [[ -f "$PROJECT_DIR/.agents/skills/$s/SKILL.md" ]] && templated_with_stub=$((templated_with_stub + 1))
done
assert_eq "A profile-aware stub count == templated skills with a Codex stub" "$templated_with_stub" "$stubs"
if (( checked > stubs && stubs > 0 )); then assert_eq "A scan covered wrappers and stubs" ok ok
else assert_eq "A scan covered wrappers and stubs" "checked>stubs>0" "checked=$checked stubs=$stubs"; fi

echo ""
echo "--- B: the stub generator ---"
gen="$("$PROJECT_DIR/.aitask-scripts/aitask_audit_wrappers.sh" render-wrapper agents aitask-pick 2>&1)"
printf '%s\n' "$gen" > "$TMP/gen.md"
assert_contains "B generator output carries the fragment verbatim" "$(cat "$FRAG")" "$gen"
frag_line="$(grep -nF "$MARK" "$TMP/gen.md" | head -1 | cut -d: -f1)"
stub_line="$(grep -n 'This is a profile-aware skill stub' "$TMP/gen.md" | head -1 | cut -d: -f1)"
if [[ -n "$frag_line" && -n "$stub_line" ]] && (( frag_line < stub_line )); then
    assert_eq "B fragment precedes the stub steps" ok ok
else
    assert_eq "B fragment precedes the stub steps" "frag<stub" "frag=$frag_line stub=$stub_line"
fi
if fragment_after_frontmatter "$TMP/gen.md"; then assert_eq "B fragment right after frontmatter" ok ok
else assert_eq "B fragment right after frontmatter" ok no; fi

echo ""
echo "--- C: rendered skills ---"
if [[ -z "$PY" ]]; then
    echo "SKIP C: no python with minijinja + yaml (run ait setup)"
else
    out="$(cd "$PROJECT_DIR" && "$PY" - "$FRAG" <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, ".aitask-scripts/lib")
import skill_template as st
frag = Path(sys.argv[1]).read_text().strip("\n")
root = Path(".").resolve()
prof = Path("aitasks/metadata/profiles/fast.yaml").resolve()
bad, entries, closure_skills = [], 0, 0
for j2 in sorted(Path(".claude/skills").glob("*/SKILL.md.j2")):
    for agent in ("codex", "claude", "opencode"):
        plan = st.walk_closure(j2.resolve(), st._load_profile(prof), agent, "fast",
                               prof, root, write=False, force=False)
        for i, (src, tgt, content) in enumerate(plan):
            has = frag in content
            if agent != "codex":
                if has:
                    bad.append(f"{agent}:{tgt.relative_to(root)} carries the codex fragment")
                continue
            if tgt.name == "SKILL.md":
                if i == 0:
                    entries += 1
                else:
                    closure_skills += 1
                head_end = content.find("\n---\n", 3) + len("\n---\n")
                if not content[head_end:].startswith("\n" + frag + "\n"):
                    bad.append(f"codex:{tgt.relative_to(root)} lacks the fragment after its frontmatter")
            elif has:
                bad.append(f"codex:{tgt.relative_to(root)} (procedure file) carries the fragment")
print(f"ENTRIES:{entries}")
print(f"CLOSURE_SKILLS:{closure_skills}")
for b in bad:
    print("BAD:" + b)
PY
)"
    assert_eq "C no misplaced or missing fragments" "" "$(printf '%s\n' "$out" | grep '^BAD:')"
    assert_eq "C one rendered Codex entry per templated skill" "ENTRIES:$templated_with_stub" \
        "$(printf '%s\n' "$out" | grep '^ENTRIES:')"
    closure_n="$(printf '%s\n' "$out" | sed -n 's/^CLOSURE_SKILLS://p')"
    if [[ "$closure_n" =~ ^[0-9]+$ ]] && (( closure_n > 0 )); then
        assert_eq "C closure skills (task-workflow, …) are covered too" ok ok
    else
        assert_eq "C closure skills (task-workflow, …) are covered too" ">0" "$closure_n"
    fi
fi
committed_missing=""
while IFS= read -r f; do
    [[ -n "$f" ]] || continue
    fragment_after_frontmatter "$PROJECT_DIR/$f" || committed_missing+=" $f"
done < <(git -C "$PROJECT_DIR" ls-files -- '.agents/skills/*-codex-/SKILL.md')
assert_eq "C committed Codex prerenders carry the fragment" "" "$committed_missing"

echo ""
echo "--- D: the mapping's fallback ---"
assert_contains "D plain-prose fallback passage present" "If the server is not available" "$(cat "$MAPPING")"
assert_contains "D fallback names the opt-in flag" "--with-codex-questions" "$(cat "$MAPPING")"
assert_contains "D fallback covers a declined server" "declined the server" "$(cat "$MAPPING")"

echo ""
echo "--- E: negative controls ---"
strip_fragment() {   # strip_fragment <in> <out>
    python3 - "$1" "$2" "$FRAG" <<'PY'
import sys
t = open(sys.argv[1]).read()
frag = open(sys.argv[3]).read().strip("\n") + "\n\n"
assert frag in t, "fragment not present to strip"
open(sys.argv[2], "w").write(t.replace(frag, "", 1))
PY
}
strip_fragment "$PROJECT_DIR/.agents/skills/aitask-pick/SKILL.md" "$TMP/stub_stripped.md"
if has_pointer "$TMP/stub_stripped.md"; then assert_eq "E stripped stub is flagged (pointer)" flagged missed
else assert_eq "E stripped stub is flagged (pointer)" flagged flagged; fi
if fragment_after_frontmatter "$TMP/stub_stripped.md"; then assert_eq "E stripped stub is flagged (position)" flagged missed
else assert_eq "E stripped stub is flagged (position)" flagged flagged; fi
strip_fragment "$PROJECT_DIR/.agents/skills/aitask-pickrem-remote-codex-/SKILL.md" "$TMP/rendered_stripped.md"
if fragment_after_frontmatter "$TMP/rendered_stripped.md"; then assert_eq "E stripped rendered entry is flagged" flagged missed
else assert_eq "E stripped rendered entry is flagged" flagged flagged; fi

# --- R fixture: a scratch copy of the framework --------------------------------
FX="$TMP/fx"
mkdir -p "$FX/aitasks/metadata" "$FX/.agents/skills"
copy_framework_tree "$PROJECT_DIR/.aitask-scripts" "$FX/.aitask-scripts"
copy_framework_tree "$PROJECT_DIR/.claude/skills" "$FX/.claude/skills"
cp -rL "$PROJECT_DIR/aitasks/metadata/profiles" "$FX/aitasks/metadata/"
git -C "$FX" init -q
STALE=$'---\nname: aitask-pick-fast\ndescription: old\n---\n\n## Workflow\nold body\n'
plant() { mkdir -p "$FX/.agents/skills/$1"; printf '%s' "$2" > "$FX/.agents/skills/$1/SKILL.md"; }
run_refresh() {
    (cd "$FX" && bash -c 'source .aitask-scripts/aitask_setup.sh --source-only; set +e; refresh_codex_rendered_entries "$1"' _ "$FX") 2>&1
}
sha() { sha256sum "$1" | cut -d' ' -f1; }

echo ""
echo "--- F/R2: fallback insertion (render fails: unknown profile) ---"
GHOST=$'---\nname: aitask-pick-zzghost\ndescription: ghost profile\n---\n\n## Workflow\nbody\n'
plant aitask-pick-zzghost-codex- "$GHOST"
NOFM=$'## No frontmatter\nbody\n'
plant aitask-explore-zzghost-codex- "$NOFM"
out="$(run_refresh)"
g="$FX/.agents/skills/aitask-pick-zzghost-codex-/SKILL.md"
assert_contains "R2 summary reports a patch" "patched=" "$out"
if fragment_after_frontmatter "$g"; then assert_eq "R2 fragment inserted after frontmatter" ok ok
else assert_eq "R2 fragment inserted after frontmatter" ok no; fi
assert_eq "R2 frontmatter byte-identical" "$(printf '%s' "$GHOST" | head -4)" "$(head -4 "$g")"
assert_eq "R2 body kept" "body" "$(tail -1 "$g")"
# The renderer's own injection over the same input, for a byte comparison.
py_inject() {   # py_inject <input-file> -> stdout
    python3 - "$PROJECT_DIR/.aitask-scripts/lib" "$1" "$FRAG" <<'PY'
import sys
sys.path.insert(0, sys.argv[1])
import skill_template as st
sys.stdout.write(st.inject_entry_prereq(open(sys.argv[2]).read(), open(sys.argv[3]).read()))
PY
}
printf '%s' "$GHOST" > "$TMP/ghost.in"
printf '%s' "$NOFM" > "$TMP/nofm.in"
py_inject "$TMP/ghost.in" > "$TMP/ghost.expected"
py_inject "$TMP/nofm.in" > "$TMP/nofm.expected"
if cmp -s "$TMP/ghost.expected" "$g"; then assert_eq "F awk fallback == renderer inject_entry_prereq (frontmatter)" same same
else assert_eq "F awk fallback == renderer inject_entry_prereq (frontmatter)" same "$(diff "$TMP/ghost.expected" "$g")"; fi
if cmp -s "$TMP/nofm.expected" "$FX/.agents/skills/aitask-explore-zzghost-codex-/SKILL.md"; then
    assert_eq "F awk fallback == renderer inject_entry_prereq (no frontmatter)" same same
else
    assert_eq "F awk fallback == renderer inject_entry_prereq (no frontmatter)" same \
        "$(diff "$TMP/nofm.expected" "$FX/.agents/skills/aitask-explore-zzghost-codex-/SKILL.md")"
fi
before="$(sha "$g")"
run_refresh >/dev/null
assert_eq "R2 second run leaves exactly one pointer" "1" "$(grep -cF "$MARK" "$g")"
assert_eq "R2 second run is a no-op" "$before" "$(sha "$g")"

echo ""
echo "--- R3: scope ---"
plant nosuchskill-fast-codex- $'---\nname: x\n---\n\nbody\n'
plant aitask-pick-fast-agy- $'---\nname: x\n---\n\nbody\n'
mkdir -p "$FX/.claude/skills/aitask-pick-fast-"
printf -- '---\nname: aitask-pick-fast\n---\n\nclaude body\n' > "$FX/.claude/skills/aitask-pick-fast-/SKILL.md"
s_orphan="$(sha "$FX/.agents/skills/nosuchskill-fast-codex-/SKILL.md")"
s_agy="$(sha "$FX/.agents/skills/aitask-pick-fast-agy-/SKILL.md")"
s_claude="$(sha "$FX/.claude/skills/aitask-pick-fast-/SKILL.md")"
out="$(run_refresh)"
assert_eq "R3 orphan -codex- dir untouched" "$s_orphan" "$(sha "$FX/.agents/skills/nosuchskill-fast-codex-/SKILL.md")"
assert_eq "R3 non-codex rendered dir untouched" "$s_agy" "$(sha "$FX/.agents/skills/aitask-pick-fast-agy-/SKILL.md")"
assert_eq "R3 claude rendered dir untouched" "$s_claude" "$(sha "$FX/.claude/skills/aitask-pick-fast-/SKILL.md")"
assert_contains "R3 orphan counted as skipped" "skipped=1" "$out"
res="$(bash -c 'source "$1/.aitask-scripts/aitask_setup.sh" --source-only; set +e
    printf "%s|" "$(_codex_rendered_skill_of aitask-pickrem-zzghost-codex- aitask-pick aitask-pickrem)"
    printf "%s|" "$(_codex_rendered_skill_of aitask-pick-remote-codex- aitask-pick aitask-pickrem)"
    printf "%s" "$(_codex_rendered_skill_of aitask-pick-codex- aitask-pick)"' _ "$PROJECT_DIR")"
assert_eq "R3 longest-prefix skill resolution" "aitask-pickrem|aitask-pick|" "$res"

echo ""
echo "--- R1: render path (pre-change variant, stub never entered) ---"
if [[ -z "$PY" ]]; then
    echo "SKIP R1: no python with minijinja + yaml (run ait setup)"
else
    plant aitask-pick-fast-codex- "$STALE"
    out="$(run_refresh)"
    e="$FX/.agents/skills/aitask-pick-fast-codex-/SKILL.md"
    assert_contains "R1 summary reports a refresh" "refreshed=1" "$out"
    if fragment_after_frontmatter "$e"; then assert_eq "R1 refreshed variant carries the fragment" ok ok
    else assert_eq "R1 refreshed variant carries the fragment" ok no; fi
    fresh="$(cd "$FX" && "$PY" - <<'PY'
import sys
from pathlib import Path
sys.path.insert(0, ".aitask-scripts/lib")
import skill_template as st
root = Path(".").resolve()
prof = Path("aitasks/metadata/profiles/fast.yaml").resolve()
plan = st.walk_closure(Path(".claude/skills/aitask-pick/SKILL.md.j2").resolve(),
                       st._load_profile(prof), "codex", "fast", prof, root,
                       write=False, force=False)
sys.stdout.write(plan[0][2])
PY
)"
    assert_eq "R1 refreshed variant equals a fresh render" "$fresh" "$(cat "$e")"
    assert_not_contains "R1 stale body is gone" "old body" "$(cat "$e")"
fi

echo ""
echo "--- R4: upgrade fixture (install.sh --force, the ait upgrade route) ---"
STAGE="$TMP/stage"; LIST="$TMP/list"; TARBALL="$TMP/aitasks-test.tar.gz"
mkdir -p "$STAGE"
(cd "$PROJECT_DIR" && git ls-files -co --exclude-standard -- \
    ait CHANGELOG.md .aitask-scripts packaging seed .claude/skills \
    | while IFS= read -r f; do [[ -f "$f" ]] && printf '%s\n' "$f"; done) > "$LIST"
(cd "$PROJECT_DIR" && tar -cf - -T "$LIST") | tar -xf - -C "$STAGE"
mv "$STAGE/.claude/skills" "$STAGE/skills"; rmdir "$STAGE/.claude"
(cd "$STAGE" && tar -czf "$TARBALL" ait CHANGELOG.md .aitask-scripts packaging seed skills)
UP="$TMP/up"; FAKE_HOME="$TMP/home"
mkdir -p "$UP" "$FAKE_HOME"
git -C "$UP" init -q -b main
git -C "$UP" config user.email test@example.com
git -C "$UP" config user.name test
git -C "$UP" config commit.gpgsign false
run_install() {
    env -u AITASKS_HOME HOME="$FAKE_HOME" AIT_TESTMAP_FETCH=0 AIT_STATS_MIGRATE=0 \
        bash "$PROJECT_DIR/install.sh" "$@" --dir "$UP" --local-tarball "$TARBALL" --no-testmap </dev/null 2>&1
}
first="$(run_install)"; rc1=$?
assert_eq "R4 fresh install succeeds" "0" "$rc1"
[[ "$rc1" == 0 ]] || printf '%s\n' "$first" | tail -20
mkdir -p "$UP/.agents/skills/aitask-pick-fast-codex-"
printf '%s' "$STALE" > "$UP/.agents/skills/aitask-pick-fast-codex-/SKILL.md"
second="$(run_install --force)"; rc2=$?
assert_eq "R4 upgrade (install --force) succeeds" "0" "$rc2"
[[ "$rc2" == 0 ]] || printf '%s\n' "$second" | tail -20
assert_contains "R4 upgrade runs the refresh" "Checking rendered Codex skills" "$second"
if fragment_after_frontmatter "$UP/.agents/skills/aitask-pick-fast-codex-/SKILL.md"; then
    assert_eq "R4 pre-change variant carries the fragment after upgrade" ok ok
else
    assert_eq "R4 pre-change variant carries the fragment after upgrade" ok no
fi

echo ""
echo "--- R5: wiring ---"
wiring="$(bash -c 'source "$1/.aitask-scripts/aitask_setup.sh" --source-only
    declare -f setup_code_agents; echo "=====";  declare -f setup_codex_agent' _ "$PROJECT_DIR")"
assert_contains "R5 setup_code_agents runs the Codex block" "setup_codex_agent" "${wiring%%=====*}"
assert_contains "R5 the Codex block refreshes rendered skills" "refresh_codex_rendered_entries" "${wiring#*=====}"
src_line="$(grep -n 'source "\$INSTALL_DIR/.aitask-scripts/aitask_setup.sh" --source-only' "$PROJECT_DIR/install.sh" | head -1 | cut -d: -f1)"
call_line="$(grep -n 'refresh_codex_rendered_entries "\$INSTALL_DIR"' "$PROJECT_DIR/install.sh" | head -1 | cut -d: -f1)"
guard_line="$(grep -n 'declare -F refresh_codex_rendered_entries' "$PROJECT_DIR/install.sh" | head -1 | cut -d: -f1)"
if [[ -n "$src_line" && -n "$guard_line" && -n "$call_line" ]] && (( src_line < guard_line && guard_line < call_line )); then
    assert_eq "R5 install.sh calls the refresh, guarded, after sourcing setup" ok ok
else
    assert_eq "R5 install.sh calls the refresh, guarded, after sourcing setup" "src<guard<call" \
        "src=$src_line guard=$guard_line call=$call_line"
fi

echo ""
echo "========================================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
echo "========================================="
[[ "$FAIL" -eq 0 ]] || exit 1
echo "ALL TESTS PASSED"
