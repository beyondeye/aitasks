#!/usr/bin/env bash
# test_premise_baseline_field.sh - The `premise_baseline:` (t1663_2) field
# contract: writer, durability, rejection, write-site pins, and the round trip
# into the shipped reader (aitask_premise_stale.sh).
#
# The field is the commit at which a task's premise was last known valid. Two
# hazards make it worth pinning:
#   - aitask_update.sh parses frontmatter with an allowlist `case` and rebuilds
#     the block from a fixed positional list, so a half-threaded field is
#     silently dropped by any unrelated `ait update`, including the parent
#     child-completion write path that a batch test never exercises;
#   - the reader accepts only a full commit id, and reads anything else -- or a
#     full id that names no commit -- as SKIP. A value the writer accepted but
#     the reader skipped would leave the task silently never checked, so Part F
#     runs the writer's output through the real reader.
#
# Run: bash tests/test_premise_baseline_field.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
cd /

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/fixture_root.sh
. "$PROJECT_DIR/tests/lib/fixture_root.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

cleanup() {
    local d
    for d in "${CLEANUP_DIRS[@]:-}"; do
        [[ -n "$d" && -d "$d" ]] && rm -rf "$d"
    done
}
trap cleanup EXIT

UPD="$PROJECT_DIR/.aitask-scripts/aitask_update.sh"
CHECK="$PROJECT_DIR/.aitask-scripts/aitask_premise_stale.sh"
SCRIPTS="$PROJECT_DIR/.aitask-scripts"

TS="2026-11-01 09:00"

# Value of a frontmatter field, or "" when the key is absent.
field() { # field <file> <name>
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"
}

# PRESENT/ABSENT for the key itself: clearing means "the line is gone".
has_field() { # has_field <file> <name>
    if awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{found=1; exit} END{exit !found}' "$1"; then
        echo PRESENT
    else
        echo ABSENT
    fi
}

digest() { cksum < "$1"; }

seed_task() { # seed_task <path> <extra frontmatter line(s)>
    local path="$1" extra="${2:-}"
    {
        echo "---"
        echo "priority: high"
        echo "effort: medium"
        echo "depends: []"
        echo "issue_type: feature"
        echo "status: Ready"
        echo "labels: []"
        [[ -n "$extra" ]] && printf '%s\n' "$extra"
        echo "created_at: 2026-11-01 08:00"
        echo "updated_at: 2026-11-01 08:00"
        echo "---"
        echo ""
        echo "## Context"
        echo "Body."
    } > "$path"
}

# A git repository holding a task tree, with one commit.
init_repo() { # init_repo <dir> [git-init args...]
    local d="$1"
    shift
    git init --quiet "$@" "$d"
    git -C "$d" config user.email "test@test.com"
    git -C "$d" config user.name "Test"
    git -C "$d" config commit.gpgsign false
    mkdir -p "$d/aitasks/metadata" "$d/aitasks/t60" "$d/lib"
    : > "$d/aitasks/metadata/labels.txt"
    printf 'feature\nbug\nchore\ntest\nmanual_verification\n' \
        > "$d/aitasks/metadata/task_types.txt"
    echo "one" > "$d/lib/a.sh"
    git -C "$d" add -A
    git -C "$d" commit -q -m "chore: seed (t1)"
}

fixture_root_init
REPO="$(fixture_mktemp_d test_premise_baseline)"
init_repo "$REPO"
C1="$(git -C "$REPO" rev-parse HEAD)"
TREE="$(git -C "$REPO" rev-parse 'HEAD^{tree}')"
VALUE="$C1 @ $TS"

upd() { ( cd "$REPO" && TASK_DIR=aitasks "$UPD" "$@" ); }

# ============================================================
# Part A - durability
# ============================================================
echo "--- Part A: durability ---"

seed_task "$REPO/aitasks/t50_keep.md" "premise_baseline: $VALUE"
upd --batch 50 --status Editing --silent >/dev/null 2>&1
assert_eq "unrelated --status update preserves premise_baseline" "$VALUE" \
    "$(field "$REPO/aitasks/t50_keep.md" premise_baseline)"
upd --batch 50 --priority low --silent >/dev/null 2>&1
assert_eq "unrelated --priority update preserves premise_baseline" "$VALUE" \
    "$(field "$REPO/aitasks/t50_keep.md" premise_baseline)"
# ...and the guard is not vacuous: those updates really rewrote the file.
assert_eq "the unrelated update did rewrite the task" "low" \
    "$(field "$REPO/aitasks/t50_keep.md" priority)"

# The parent child-completion write path rewrites the PARENT through its own
# write_task_file call site, invisible to every batch assertion above.
seed_task "$REPO/aitasks/t60_parent.md" "children_to_implement: [t60_1, t60_2]
premise_baseline: $VALUE"
seed_task "$REPO/aitasks/t60/t60_1_child.md"
seed_task "$REPO/aitasks/t60/t60_2_child.md"
upd --batch 60_1 --status Done --silent >/dev/null 2>&1
assert_eq "parent's premise_baseline survives a child's --status Done" "$VALUE" \
    "$(field "$REPO/aitasks/t60_parent.md" premise_baseline)"
assert_eq "the child-completion path did rewrite the parent" "[t60_2]" \
    "$(field "$REPO/aitasks/t60_parent.md" children_to_implement)"

# ============================================================
# Part B - set, canonicalise, stamp, clear
# ============================================================
echo "--- Part B: set and clear ---"

seed_task "$REPO/aitasks/t51_set.md"
assert_eq "a task never given the flag has no premise_baseline key" "ABSENT" \
    "$(has_field "$REPO/aitasks/t51_set.md" premise_baseline)"

upd --batch 51 --premise-baseline "$VALUE" --silent >/dev/null 2>&1
assert_eq "--premise-baseline '<oid> @ <ts>' is written verbatim" "$VALUE" \
    "$(field "$REPO/aitasks/t51_set.md" premise_baseline)"

UPPER="$(printf '%s' "$C1" | tr 'a-f' 'A-F')"
upd --batch 51 --premise-baseline "$UPPER @ $TS" --silent >/dev/null 2>&1
assert_eq "an uppercase commit id is stored lowercase" "$VALUE" \
    "$(field "$REPO/aitasks/t51_set.md" premise_baseline)"

upd --batch 51 --premise-baseline "$C1" --silent >/dev/null 2>&1
stamped="$(field "$REPO/aitasks/t51_set.md" premise_baseline)"
assert_contains_re "a bare commit id is stamped with the current minute" \
    "^$C1 @ [0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}\$" "$stamped"

upd --batch 51 --premise-baseline "" --silent >/dev/null 2>&1
assert_eq "--premise-baseline '' removes the key entirely" "ABSENT" \
    "$(has_field "$REPO/aitasks/t51_set.md" premise_baseline)"
upd --batch 51 --premise-baseline "" --silent >/dev/null 2>&1
rc=$?
assert_exit_zero_rc "clearing an absent premise_baseline succeeds" "$rc"
assert_eq "clearing an absent premise_baseline stays ABSENT" "ABSENT" \
    "$(has_field "$REPO/aitasks/t51_set.md" premise_baseline)"

# ============================================================
# Part C - rejection, file byte-unchanged
# ============================================================
echo "--- Part C: rejection ---"

MISSING40="$(printf '0123456789abcdef%.0s' 1 2 3)"; MISSING40="${MISSING40:0:40}"
MISSING64="$(printf 'abcdef0123456789%.0s' 1 2 3 4)"
seed_task "$REPO/aitasks/t52_bad.md" "premise_baseline: $VALUE"
for bad in "HEAD" "main" "HEAD~1" "${C1:0:7}" "${C1}^" "$C1 @ 2026-11-01" \
           "$C1@$TS" "$C1 @ $TS trailing" " $C1 @ $TS" "$C1 @ 2026-11-01T09:00" \
           "$MISSING40 @ $TS" "$MISSING64 @ $TS" "$TREE @ $TS"; do
    before="$(digest "$REPO/aitasks/t52_bad.md")"
    err="$(upd --batch 52 --premise-baseline "$bad" --silent 2>&1 >/dev/null)"
    rc=$?
    assert_exit_nonzero_rc "--premise-baseline '$bad' is rejected" "$rc"
    assert_contains "'$bad' rejection names the flag" "--premise-baseline" "$err"
    assert_eq "'$bad' leaves the task file byte-unchanged" \
        "$before" "$(digest "$REPO/aitasks/t52_bad.md")"
done

# The rejection happens before ANY write: a label supplied in the same call is
# not registered in the vocabulary either.
upd --batch 52 --premise-baseline "HEAD" --add-label brandnew --silent >/dev/null 2>&1
assert_eq "a rejected value leaves labels.txt untouched" "" \
    "$(cat "$REPO/aitasks/metadata/labels.txt")"

# Outside a repository a commit id cannot be verified, so it is refused.
NOREPO="$(fixture_mktemp_d test_premise_baseline_norepo)"
mkdir -p "$NOREPO/aitasks/metadata"
: > "$NOREPO/aitasks/metadata/labels.txt"
cp "$REPO/aitasks/metadata/task_types.txt" "$NOREPO/aitasks/metadata/"
seed_task "$NOREPO/aitasks/t53_norepo.md"
before="$(digest "$NOREPO/aitasks/t53_norepo.md")"
( cd "$NOREPO" && GIT_CEILING_DIRECTORIES="$NOREPO" TASK_DIR=aitasks "$UPD" \
    --batch 53 --premise-baseline "$VALUE" --silent >/dev/null 2>&1 )
rc=$?
assert_exit_nonzero_rc "a commit id cannot be stored outside a git repository" "$rc"
assert_eq "...and the task file is byte-unchanged" \
    "$before" "$(digest "$NOREPO/aitasks/t53_norepo.md")"

# A SHA-256 repository accepts its own 64-hex commit ids.
SHA256_REPO="$(fixture_mktemp_d test_premise_baseline_sha256)"
if git init --quiet --object-format=sha256 "$SHA256_REPO/probe" >/dev/null 2>&1; then
    rm -rf "$SHA256_REPO/probe"
    init_repo "$SHA256_REPO/r" --object-format=sha256
    C256="$(git -C "$SHA256_REPO/r" rev-parse HEAD)"
    seed_task "$SHA256_REPO/r/aitasks/t54_sha256.md"
    ( cd "$SHA256_REPO/r" && TASK_DIR=aitasks "$UPD" \
        --batch 54 --premise-baseline "$C256 @ $TS" --silent >/dev/null 2>&1 )
    assert_eq "precondition: the SHA-256 commit id is 64 hex" "64" "${#C256}"
    assert_eq "a 64-hex commit id is accepted in a SHA-256 repository" \
        "$C256 @ $TS" "$(field "$SHA256_REPO/r/aitasks/t54_sha256.md" premise_baseline)"
else
    echo "SKIP: git cannot create a SHA-256 repository here"
fi

# ============================================================
# Part D - sites that must NOT write the field
# ============================================================
echo "--- Part D: must-not-write sites ---"

# Acquiring a scope after creation does not stamp a baseline (the design's
# lifecycle table): the task resolves a scope but stays SKIP until someone
# reviews its premise.
seed_task "$REPO/aitasks/t55_scope.md"
upd --batch 55 --file-ref lib/a.sh --silent >/dev/null 2>&1
upd --batch 55 --add-verifies 50 --silent >/dev/null 2>&1
assert_eq "precondition: --file-ref really wrote the scope" "[lib/a.sh]" \
    "$(field "$REPO/aitasks/t55_scope.md" file_references)"
assert_eq "--file-ref / --add-verifies do not create a premise_baseline" "ABSENT" \
    "$(has_field "$REPO/aitasks/t55_scope.md" premise_baseline)"

# The fold never writes one: aitask_fold_mark.sh carries only a comment.
assert_eq "aitask_fold_mark.sh emits no premise_baseline: line" "0" \
    "$(grep -cE '^[^#]*premise_baseline:' "$SCRIPTS/aitask_fold_mark.sh" || true)"

# ============================================================
# Part E - structural pins
# ============================================================
echo "--- Part E: structural pins ---"

call_sites="$(grep -cE '^[[:space:]]*write_task_file "' "$UPD")"
forwarded="$(grep -cE '^[[:space:]]*"\$(CURRENT_PREMISE_BASELINE|new_premise_baseline)"[[:space:]]*\\?$' "$UPD")"
assert_eq "write_task_file call-site count is unchanged" "3" "$call_sites"
assert_eq "every write_task_file call site forwards premise_baseline" \
    "$call_sites" "$forwarded"
assert_eq "aitask_update.sh has exactly one premise_baseline: emit" "1" \
    "$(grep -cF 'echo "premise_baseline: ' "$UPD")"

# The only shell writer of the field. A new write site (e.g. creation-time
# seeding) must be added here deliberately.
writers="$(grep -lE 'echo "premise_baseline: ' "$SCRIPTS"/*.sh "$SCRIPTS"/lib/*.sh 2>/dev/null \
    | sed "s|^$SCRIPTS/||" | sort | tr '\n' ' ')"
assert_eq "aitask_update.sh is the only shell writer of premise_baseline" \
    "aitask_update.sh " "$writers"

# ============================================================
# Part F - writer output through the shipped reader
# ============================================================
echo "--- Part F: writer -> aitask_premise_stale.sh ---"

check() { ( cd "$REPO" && bash "$CHECK" check "$1" 2>/dev/null ); }
line_of() { printf '%s\n' "$2" | grep "^$1:" | head -1; }

seed_task "$REPO/aitasks/t56_e2e.md" "file_references: [lib/a.sh]"
seed_task "$REPO/aitasks/t57_e2e_bare.md" "file_references: [lib/a.sh]"
upd --batch 56 --premise-baseline "$VALUE" --silent >/dev/null 2>&1
upd --batch 57 --premise-baseline "$C1" --silent >/dev/null 2>&1

for t in t56_e2e t57_e2e_bare; do
    out="$(check "aitasks/$t.md")"
    assert_contains "$t: the reader takes the written baseline" \
        "BASELINE:$C1|" "$(line_of BASELINE "$out")"
    assert_eq "$t: unchanged scope reads FRESH" "DECISION:FRESH" \
        "$(line_of DECISION "$out")"
done

echo "two" > "$REPO/lib/a.sh"
git -C "$REPO" add lib/a.sh
git -C "$REPO" commit -q -m "feature: change a (t9)"

for t in t56_e2e t57_e2e_bare; do
    out="$(check "aitasks/$t.md")"
    assert_eq "$t: a change after the baseline reads ASK_STALE" "DECISION:ASK_STALE" \
        "$(line_of DECISION "$out")"
    assert_contains "$t: the changed file is named" "CHANGED:lib/a.sh|" \
        "$(line_of CHANGED "$out")"
done

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failed: $FAIL"
    echo "===================="
    exit 1
fi
echo "===================="
