#!/usr/bin/env bash
# test_premise_baseline_seeding.sh - creation-time seeding of `premise_baseline:`
# (t1663_3). Design: aidocs/framework/task_premise_staleness.md ("Seeding",
# "Tier B reachability", "Baseline lifecycle").
#
# The rule: a task that leaves creation with a derivable scope -- a
# `file_references:` list (Tier A) or a `verifies:` list (Tier B, the only input
# that yields an `exact` origin) -- is stamped with HEAD at its commit point. A
# task without one is not, and `--followup-of` alone is NOT a trigger (it writes
# only `anchor:`, which Tier B refuses by contract). Drafts are never seeded;
# finalizing one is a commit point and seeds it.
#
# The parts:
#   A  --batch --commit (parent + child), the trigger set and its negatives
#   B  the internal --premise-baseline creation flag (carry-over's route)
#   C  draft -> finalize, including hand-edited block-style lists
#   D  read_premise_seed_fields / premise_baseline_canonical units
#   E  no HEAD commit: created, not seeded, warned
#   F  the seeded value read back through the shipped reader
#   G  structural pins
#
# RED PROOFS: AIT_SEED_SRC=<dir> copies the scripts under test from <dir>
# instead of the repository, so a mutated scratch copy can be shown to fail.
#
# Run: bash tests/test_premise_baseline_seeding.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/scratch_cwd.sh
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"
# shellcheck source=lib/fixture_root.sh
. "$PROJECT_DIR/tests/lib/fixture_root.sh"
# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

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

SRC="${AIT_SEED_SRC:-$PROJECT_DIR/.aitask-scripts}"
CHECK="$PROJECT_DIR/.aitask-scripts/aitask_premise_stale.sh"
TS_RE='^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}$'

# Value of a frontmatter field, or "" when the key is absent.
field() { # field <file> <name>
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{sub("^"f":[[:space:]]*",""); print; exit}' "$1"
}

# Number of frontmatter lines carrying the key.
key_count() { # key_count <file> <name>
    awk -v f="$2" '$0=="---"{n++; next} n==1 && $0 ~ "^"f":"{c++} END{print c+0}' "$1"
}

has_field() { # PRESENT / ABSENT
    if [[ "$(key_count "$1" "$2")" -gt 0 ]]; then echo PRESENT; else echo ABSENT; fi
}

# A clone of a bare remote with the create toolchain copied in (the
# tests/test_file_references.sh shape), one commit, claim-id counter seeded.
new_project() {
    local tmp
    tmp="$(fixture_mktemp_d test_premise_seed)" || return 1
    git init --bare --quiet "$tmp/remote.git"
    git clone --quiet "$tmp/remote.git" "$tmp/local" 2>/dev/null
    (
        cd "$tmp/local" || exit 1
        git config user.email "test@test.com"
        git config user.name "Test"
        git config commit.gpgsign false
        mkdir -p aitasks/archived aitasks/metadata aitasks/new lib
        setup_fake_aitask_repo "$PWD"
        local s
        for s in aitask_create.sh aitask_claim_id.sh aitask_update.sh aitask_find_by_file.sh aitask_query_files.sh; do
            cp "$SRC/$s" .aitask-scripts/
        done
        cp "$SRC/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
        chmod +x .aitask-scripts/*.sh
        printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\nmanual_verification\n' \
            > aitasks/metadata/task_types.txt
        : > aitasks/metadata/labels.txt
        echo "aitasks/new/" > .gitignore
        echo "one" > lib/a.sh
        git add -A
        git commit -m "chore: seed (t1)" --quiet
        git push --quiet 2>/dev/null
        ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1
    ) || return 1
    echo "$tmp/local"
}

ERRF=""
# create <repo> <args...> -> prints the created path; stderr kept in $ERRF.
create() {
    local repo="$1"
    shift
    ( cd "$repo" && ./.aitask-scripts/aitask_create.sh --batch "$@" --silent 2>"$ERRF" )
}

# Assert <file> is seeded with exactly <sha> plus a well-formed timestamp.
assert_seeded() { # assert_seeded <label> <file> <sha>
    local label="$1" f="$2" sha="$3" v
    v="$(field "$f" premise_baseline)"
    assert_eq "$label: seeded sha is HEAD at the commit point" "$sha" "${v%% @ *}"
    TOTAL=$((TOTAL + 1))
    if [[ "$v" == *" @ "* && "${v#* @ }" =~ $TS_RE ]]; then
        PASS=$((PASS + 1))
    else
        FAIL=$((FAIL + 1))
        echo "FAIL: $label: timestamp half is malformed: '$v'"
    fi
}

fixture_root_init
ERRF="$(fixture_mktemp_d test_premise_seed_err)/stderr"

P="$(new_project)"
HEAD0="$(git -C "$P" rev-parse HEAD)"
MAIN_BRANCH="$(git -C "$P" rev-parse --abbrev-ref HEAD)"

# ============================================================
# Part A - --batch --commit
# ============================================================
echo "--- Part A: --batch --commit ---"

pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(create "$P" --name a_fileref --desc d --file-ref lib/a.sh --commit)"
assert_seeded "--file-ref" "$f" "$pre"
assert_eq "--file-ref: scope really written" "[lib/a.sh]" "$(field "$f" file_references)"

pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(create "$P" --name a_verifies --desc d --verifies 1 --commit)"
assert_seeded "--verifies" "$f" "$pre"

# The contract fixture (t1673): --verifies is type-agnostic, and Tier-B
# eligibility is having an exact origin, not being a follow-up. A type-gate on
# --verifies, or a follow-up gate on seeding, fails here.
pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(create "$P" --name a_contract --desc d --verifies 1 --type test --commit)"
assert_seeded "--verifies + --type test, no follow-up relation" "$f" "$pre"
assert_eq "contract fixture: issue_type really is test" "test" "$(field "$f" issue_type)"
assert_eq "contract fixture: no anchor" "ABSENT" "$(has_field "$f" anchor)"
assert_eq "contract fixture: no followup_kind" "ABSENT" "$(has_field "$f" followup_kind)"

src_id="$(basename "$f" .md | sed -E 's/^t([0-9]+)_.*/\1/')"
f="$P/$(create "$P" --name a_followup --desc d --followup-of "$src_id" --commit)"
assert_eq "--followup-of alone: not seeded" "ABSENT" "$(has_field "$f" premise_baseline)"
# Non-vacuity: the trigger the record used to name really ran.
assert_eq "--followup-of alone: anchor really written" "$src_id" "$(field "$f" anchor)"

f="$P/$(create "$P" --name a_plain --desc d --commit)"
assert_eq "no scope: not seeded" "ABSENT" "$(has_field "$f" premise_baseline)"
PARENT_FILE="$f"
PARENT_ID="$(basename "$f" .md | sed -E 's/^t([0-9]+)_.*/\1/')"

pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(create "$P" --name a_child --desc d --parent "$PARENT_ID" --file-ref lib/a.sh --commit)"
assert_seeded "--parent child with --file-ref" "$f" "$pre"
assert_contains "--parent: child creation still updates the parent" \
    "$(basename "$f" .md | sed -E 's/^(t[0-9]+_[0-9]+)_.*/\1/')" \
    "$(field "$PARENT_FILE" children_to_implement)"

f="$P/$(create "$P" --name a_child_plain --desc d --parent "$PARENT_ID" --commit)"
assert_eq "--parent child without scope: not seeded" "ABSENT" "$(has_field "$f" premise_baseline)"

# ============================================================
# Part B - the internal --premise-baseline creation flag
# ============================================================
echo "--- Part B: --premise-baseline at creation ---"

explicit="$HEAD0 @ 2026-01-02 03:04"
f="$P/$(create "$P" --name b_explicit --desc d --verifies 1 --premise-baseline "$explicit" --commit)"
assert_eq "explicit value is written verbatim (not re-stamped to HEAD)" \
    "$explicit" "$(field "$f" premise_baseline)"

f="$P/$(create "$P" --name b_empty --desc d --verifies 1 --premise-baseline "" --commit)"
assert_eq "explicit \"\" suppresses the --verifies seed" "ABSENT" "$(has_field "$f" premise_baseline)"
assert_eq "explicit \"\": the scope is still written" "[1]" "$(field "$f" verifies)"

upper="$(printf '%s' "$HEAD0" | tr 'a-f' 'A-F') @ 2026-01-02 03:04"
f="$P/$(create "$P" --name b_upper --desc d --file-ref lib/a.sh --premise-baseline "$upper" --commit)"
assert_eq "an uppercase oid is stored lowercase" "$explicit" "$(field "$f" premise_baseline)"

# A history-rewritten origin names a commit that is gone: the creation flag is
# grammar-only on purpose, so the inherited state carries forward.
gone="0123456789abcdef0123456789abcdef01234567 @ 2026-01-02 03:04"
f="$P/$(create "$P" --name b_gone --desc d --verifies 1 --premise-baseline "$gone" --commit)"
assert_eq "a well-formed oid naming no commit is accepted (grammar only)" \
    "$gone" "$(field "$f" premise_baseline)"

reject() { # reject <label> <value> [extra args...]
    local label="$1" value="$2" rc=0 before_head before_count
    shift 2
    before_head="$(git -C "$P" rev-parse HEAD)"
    before_count="$(find "$P/aitasks" -maxdepth 2 -name 't*.md' | wc -l)"
    ( cd "$P" && ./.aitask-scripts/aitask_create.sh --batch --name rej --desc d \
        --verifies 1 --premise-baseline "$value" "$@" --silent >/dev/null 2>"$ERRF" ) || rc=$?
    TOTAL=$((TOTAL + 1))
    if [[ $rc -ne 0 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: $label: accepted (rc=0)"; fi
    assert_eq "$label: no new commit" "$before_head" "$(git -C "$P" rev-parse HEAD)"
    assert_eq "$label: no task file created" "$before_count" \
        "$(find "$P/aitasks" -maxdepth 2 -name 't*.md' | wc -l)"
}
reject "symbolic HEAD" "HEAD @ 2026-01-02 03:04" --commit
reject "abbreviated oid" "${HEAD0:0:12} @ 2026-01-02 03:04" --commit
reject "no spaces around @" "$HEAD0@2026-01-02 03:04" --commit
reject "missing timestamp" "$HEAD0" --commit
reject "date without time" "$HEAD0 @ 2026-01-02" --commit
reject "trailing garbage" "$HEAD0 @ 2026-01-02 03:04 x" --commit
reject "without --commit (drafts are never seeded)" "$explicit"
draft_left="$(find "$P/aitasks/new" -name 'draft_*_rej.md' | wc -l)"
assert_eq "without --commit: no draft written either" "0" "$draft_left"

# The INTERACTIVE route (no --batch) never reaches run_batch_mode's validation,
# and its finalize used to commit the unvalidated override verbatim (a symbolic
# HEAD the reader rejects). main() must refuse the flag before the mode split.
# Asserting the specific message keeps this from passing vacuously on a box
# without fzf (where the interactive flow would also exit non-zero).
before_head="$(git -C "$P" rev-parse HEAD)"
before_drafts="$(find "$P/aitasks/new" -name 'draft_*.md' | wc -l)"
irc=0
( cd "$P" && ./.aitask-scripts/aitask_create.sh --premise-baseline HEAD </dev/null >/dev/null 2>"$ERRF" ) || irc=$?
TOTAL=$((TOTAL + 1))
if [[ $irc -ne 0 ]]; then PASS=$((PASS + 1)); else FAIL=$((FAIL + 1)); echo "FAIL: interactive --premise-baseline accepted (rc=0)"; fi
assert_contains "interactive --premise-baseline: refused before the mode split" \
    "--premise-baseline requires --batch --commit" "$(cat "$ERRF")"
assert_eq "interactive --premise-baseline: no new commit" "$before_head" "$(git -C "$P" rev-parse HEAD)"
assert_eq "interactive --premise-baseline: no draft written" "$before_drafts" \
    "$(find "$P/aitasks/new" -name 'draft_*.md' | wc -l)"

# Defence in depth: the finalize path's resolver ignores any override, so even a
# route that skipped both refusals seeds HEAD, never the flag's value. The
# function is lifted out of the script (which runs main on load) and driven
# directly in the fixture repo.
resolver_out="$( (
    cd "$P" || exit 1
    warn() { :; }
    get_timestamp() { echo "2026-01-02 03:04"; }
    eval "$(awk '/^resolve_premise_seed\(\) \{/{on=1} on{print} on && /^}/{exit}' "$SRC/aitask_create.sh")"
    BATCH_PREMISE_BASELINE_SET=true
    BATCH_PREMISE_BASELINE="HEAD"
    resolve_premise_seed true ignore_override
    printf '%s|' "$PREMISE_SEED"
    resolve_premise_seed true
    printf '%s' "$PREMISE_SEED"
) )"
assert_eq "finalize resolver ignores an override; the batch resolver honours it" \
    "$(git -C "$P" rev-parse HEAD) @ 2026-01-02 03:04|HEAD" "$resolver_out"

# ============================================================
# Part C - draft -> finalize
# ============================================================
echo "--- Part C: drafts and finalize ---"

finalize() { # finalize <repo> <draft path relative to repo>
    ( cd "$1" && ./.aitask-scripts/aitask_create.sh --batch --finalize "$2" --silent 2>"$ERRF" )
}

d="$(create "$P" --name c_draft --desc d --file-ref lib/a.sh)"
assert_eq "a draft carries no premise_baseline" "ABSENT" "$(has_field "$P/$d" premise_baseline)"
pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(finalize "$P" "$d")"
assert_seeded "finalized --file-ref draft" "$f" "$pre"
assert_eq "finalize: committed (the seed rides in the creation commit)" "" \
    "$(git -C "$P" status --porcelain -- "$f")"

d="$(create "$P" --name c_child_draft --desc d --parent "$PARENT_ID" --verifies 1)"
pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(finalize "$P" "$d")"
assert_seeded "finalized child --verifies draft" "$f" "$pre"

d="$(create "$P" --name c_plain_draft --desc d)"
f="$P/$(finalize "$P" "$d")"
assert_eq "finalized draft without scope: not seeded" "ABSENT" "$(has_field "$f" premise_baseline)"

# Hand-edited drafts: write the draft file directly (the shapes create never
# emits but a person may).
hand_draft() { # hand_draft <name> <frontmatter lines...>
    local name="$1" path
    shift
    path="aitasks/new/draft_20260101_0000_${name}.md"
    {
        echo "---"
        echo "priority: medium"
        echo "effort: low"
        echo "depends: []"
        echo "issue_type: feature"
        echo "status: Ready"
        echo "labels: []"
        printf '%s\n' "$@"
        echo "draft: true"
        echo "created_at: 2026-01-01 00:00"
        echo "updated_at: 2026-01-01 00:00"
        echo "---"
        echo ""
        echo "Body."
    } > "$P/$path"
    echo "$path"
}

d="$(hand_draft c_block_verifies "verifies:" "  - 1")"
# Non-vacuity: the line-oriented reader really misses this list, so a pass here
# proves the YAML path.
assert_eq "block verifies: read_yaml_field sees nothing (fixture is the hard case)" "" \
    "$( ( cd "$P" && SCRIPT_DIR="$P/.aitask-scripts" && . .aitask-scripts/lib/task_utils.sh && read_yaml_field "$d" verifies ) )"
pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(finalize "$P" "$d")"
assert_seeded "finalized hand-edited block-style verifies (no file_references)" "$f" "$pre"

d="$(hand_draft c_block_refs "file_references:" "  - lib/a.sh")"
pre="$(git -C "$P" rev-parse HEAD)"
f="$P/$(finalize "$P" "$d")"
assert_seeded "finalized hand-edited block-style file_references" "$f" "$pre"

d="$(hand_draft c_has_value "file_references: [lib/a.sh]" "premise_baseline: $explicit")"
f="$P/$(finalize "$P" "$d")"
assert_eq "a draft's own value is kept verbatim" "$explicit" "$(field "$f" premise_baseline)"
assert_eq "a draft's own value: still exactly one key" "1" "$(key_count "$f" premise_baseline)"

d="$(hand_draft c_null_value "file_references: [lib/a.sh]" "premise_baseline:")"
f="$P/$(finalize "$P" "$d")"
assert_eq "a null key is never duplicated" "1" "$(key_count "$f" premise_baseline)"

d="$(hand_draft c_bad_yaml "file_references: [lib/a.sh" )"
f="$P/$(finalize "$P" "$d")"
assert_eq "unparseable frontmatter: not seeded" "ABSENT" "$(has_field "$f" premise_baseline)"
assert_contains "unparseable frontmatter: warned" "premise_baseline not seeded" "$(cat "$ERRF")"

# ============================================================
# Part D - helper units
# ============================================================
echo "--- Part D: read_premise_seed_fields / premise_baseline_canonical ---"

U="$(fixture_mktemp_d test_premise_seed_units)"
unit_file() { # unit_file <name> <frontmatter lines...>
    local name="$1"
    shift
    { echo "---"; printf '%s\n' "$@"; echo "---"; echo ""; echo "Body."; } > "$U/$name.md"
    echo "$U/$name.md"
}
# task_utils.sh sources its siblings through $SCRIPT_DIR, so point it at the
# fixture's scripts directory in each sourcing subshell.
src_utils() { SCRIPT_DIR="$P/.aitask-scripts"; . "$P/.aitask-scripts/lib/task_utils.sh"; }
rpsf() { ( src_utils && read_premise_seed_fields "$1" ) 2>/dev/null; }
canon() { ( src_utils && premise_baseline_canonical "$1" ); }

nl=$'\n'
assert_eq "absent key, no scope" \
    "BASELINE_ABSENT${nl}REFS:0${nl}VERIFIES:0${nl}END:3" \
    "$(rpsf "$(unit_file absent "status: Ready")")"
assert_eq "double-quoted value is YAML-decoded" \
    "BASELINE:$explicit${nl}REFS:0${nl}VERIFIES:0${nl}END:3" \
    "$(rpsf "$(unit_file dq "premise_baseline: \"$explicit\"")")"
assert_eq "single-quoted value is YAML-decoded" \
    "BASELINE:$explicit${nl}REFS:0${nl}VERIFIES:0${nl}END:3" \
    "$(rpsf "$(unit_file sq "premise_baseline: '$explicit'")")"
assert_eq "null key is present-but-empty" \
    "BASELINE:${nl}REFS:0${nl}VERIFIES:0${nl}END:3" \
    "$(rpsf "$(unit_file null "premise_baseline:")")"
assert_eq "non-string value is BASELINE_INVALID" \
    "BASELINE_INVALID${nl}REFS:0${nl}VERIFIES:0${nl}END:3" \
    "$(rpsf "$(unit_file int "premise_baseline: 12345")")"
assert_eq "flow lists count their entries" \
    "BASELINE_ABSENT${nl}REFS:2${nl}VERIFIES:3${nl}END:3" \
    "$(rpsf "$(unit_file flow "file_references: [a.sh, b.sh:1-2]" "verifies: [1, 2, t3]")")"
assert_eq "block lists count their entries" \
    "BASELINE_ABSENT${nl}REFS:1${nl}VERIFIES:2${nl}END:3" \
    "$(rpsf "$(unit_file block "file_references:" "  - a.sh" "verifies:" "  - 1" "  - 2")")"
assert_eq "a non-string file reference still counts as scope" \
    "BASELINE_ABSENT${nl}REFS:1${nl}VERIFIES:0${nl}END:3" \
    "$(rpsf "$(unit_file badref "file_references: [null]")")"
assert_eq "a scalar verifies counts as one" \
    "BASELINE_ABSENT${nl}REFS:0${nl}VERIFIES:1${nl}END:3" \
    "$(rpsf "$(unit_file scalarv "verifies: 7")")"
assert_eq "empty verifies list counts as none" \
    "BASELINE_ABSENT${nl}REFS:0${nl}VERIFIES:0${nl}END:3" \
    "$(rpsf "$(unit_file emptyv "verifies: []")")"
assert_eq "unparseable frontmatter" "INVALID:frontmatter" \
    "$(rpsf "$(unit_file broken "verifies: [1")")"

# No usable Python: exit 3 and nothing on stdout (never a partial answer).
nopy_out="" nopy_rc=0
nopy_out="$( ( src_utils && resolve_python() { echo ""; } \
    && read_premise_seed_fields "$U/flow.md" ) 2>/dev/null)" || nopy_rc=$?
assert_eq "no python: exit 3" "3" "$nopy_rc"
assert_eq "no python: empty stdout" "" "$nopy_out"

assert_eq "canonical: well-formed value passes through" "$explicit" "$(canon "$explicit")"
assert_eq "canonical: uppercase is lowercased" "$explicit" "$(canon "$upper")"
canon_rc=0; canon "HEAD @ 2026-01-02 03:04" >/dev/null || canon_rc=$?
assert_eq "canonical: a symbol is rejected" "1" "$canon_rc"
canon_rc=0; canon "$HEAD0" >/dev/null || canon_rc=$?
assert_eq "canonical: a bare oid is rejected (no stamping here)" "1" "$canon_rc"
canon_rc=0; canon_out="$(canon "${HEAD0}0 @ 2026-01-02 03:04")" || canon_rc=$?
assert_eq "canonical: 41 hex is rejected" "1" "$canon_rc"
assert_eq "canonical: a rejection prints nothing" "" "$canon_out"

# ============================================================
# Part E - no HEAD commit
# ============================================================
echo "--- Part E: unborn HEAD ---"

git -C "$P" checkout --quiet --orphan unborn
f="$P/$(create "$P" --name e_unborn --desc d --file-ref lib/a.sh --commit)"
assert_eq "unborn HEAD: the task is still created" "[lib/a.sh]" "$(field "$f" file_references)"
assert_eq "unborn HEAD: not seeded" "ABSENT" "$(has_field "$f" premise_baseline)"
assert_contains "unborn HEAD: warned" "premise_baseline not seeded: no HEAD commit" "$(cat "$ERRF")"
git -C "$P" checkout --quiet -f "$MAIN_BRANCH"

# ============================================================
# Part F - through the shipped reader
# ============================================================
echo "--- Part F: seeded task -> aitask_premise_stale.sh ---"

line_of() { printf '%s\n' "$2" | grep "^$1:" | head -1; }
pre="$(git -C "$P" rev-parse HEAD)"
rel="$(create "$P" --name f_e2e --desc d --file-ref lib/a.sh --commit)"
out="$( (cd "$P" && bash "$CHECK" check "$rel") 2>/dev/null)"
assert_contains "the reader takes the seeded baseline" "BASELINE:$pre|" "$(line_of BASELINE "$out")"
assert_eq "unchanged scope reads FRESH" "DECISION:FRESH" "$(line_of DECISION "$out")"
echo "two" > "$P/lib/a.sh"
git -C "$P" add lib/a.sh
git -C "$P" commit -q -m "feature: change a (t9)"
out="$( (cd "$P" && bash "$CHECK" check "$rel") 2>/dev/null)"
assert_eq "a later change to the scope reads ASK_STALE" "DECISION:ASK_STALE" "$(line_of DECISION "$out")"
assert_contains "the changed file is named" "CHANGED:lib/a.sh|" "$(line_of CHANGED "$out")"

# ============================================================
# Part G - structural pins
# ============================================================
echo "--- Part G: structural pins ---"

CREATE="$SRC/aitask_create.sh"
assert_eq "aitask_create.sh emits premise_baseline: in exactly two serializers" "2" \
    "$(grep -cF 'echo "premise_baseline: ' "$CREATE")"
assert_eq "create_draft_file emits no premise_baseline:" "0" \
    "$(awk '/^create_draft_file\(\)/{on=1} on && /^}/{on=0} on' "$CREATE" | grep -cF 'premise_baseline:')"
assert_eq "both --commit serializer call sites forward the seed" "2" \
    "$(grep -cE '^[[:space:]]*"\$deduped_file_refs" "\$BATCH_VERIFIES" "\$PREMISE_SEED"\)' "$CREATE")"
assert_eq "finalize_draft seeds in both branches" "2" \
    "$(awk '/^finalize_draft\(\)/{on=1} on && /^}/{on=0} on' "$CREATE" | grep -c 'seed_finalized_premise_baseline "\$filepath"')"
assert_eq "the finalize seeder ignores any --premise-baseline override" "1" \
    "$(awk '/^seed_finalized_premise_baseline\(\)/{on=1} on && /^}/{on=0} on' "$CREATE" \
        | grep -c 'resolve_premise_seed "\$has_scope" ignore_override')"

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
if [[ "$FAIL" -ne 0 ]]; then
    echo "Failed: $FAIL"
    echo "===================="
    exit 1
fi
echo "===================="
