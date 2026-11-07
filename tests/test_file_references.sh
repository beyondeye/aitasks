#!/usr/bin/env bash
# test_file_references.sh - Tests for file_references frontmatter field
# Run: bash tests/test_file_references.sh
#
# Covers: create/update/draft round-trip, compact multi-range entries,
# exact-string dedup semantics, aitask_find_by_file.sh path-only match
# and status filter, and malformed-input rejection.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

# shellcheck source=lib/test_scaffold.sh
. "$PROJECT_DIR/tests/lib/test_scaffold.sh"

PASS=0
FAIL=0
TOTAL=0

# --- Test helpers ---

# Shared core helpers (assert_eq, assert_contains, …) live in tests/lib/asserts.sh.
. "$PROJECT_DIR/tests/lib/asserts.sh"

# --- Project setup ---

setup_project() {
    local tmpdir
    tmpdir="$(mktemp -d)"

    local remote_dir="$tmpdir/remote.git"
    git init --bare --quiet "$remote_dir"

    local local_dir="$tmpdir/local"
    git clone --quiet "$remote_dir" "$local_dir"
    (
        cd "$local_dir" || exit 1
        git config user.email "test@test.com"
        git config user.name "Test"

        mkdir -p aitasks/archived aitasks/metadata aitasks/new
        setup_fake_aitask_repo "$PWD"

        cp "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_claim_id.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/aitask_find_by_file.sh" .aitask-scripts/
        cp "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh" .aitask-scripts/lib/
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" .aitask-scripts/lib/ 2>/dev/null || true
        cp "$PROJECT_DIR/.aitask-scripts/lib/archive_scan.sh" .aitask-scripts/lib/ 2>/dev/null || true
        chmod +x .aitask-scripts/aitask_create.sh .aitask-scripts/aitask_claim_id.sh \
            .aitask-scripts/aitask_update.sh .aitask-scripts/aitask_find_by_file.sh

        printf 'bug\nchore\ndocumentation\nenhancement\nfeature\nperformance\nrefactor\nstyle\ntest\n' \
            > aitasks/metadata/task_types.txt

        echo "aitasks/new/" > .gitignore

        git add -A
        git commit -m "Initial setup" --quiet
        git push --quiet 2>/dev/null

        ./.aitask-scripts/aitask_claim_id.sh --init >/dev/null 2>&1
    )

    echo "$tmpdir"
}

# Helper: extract the single draft file from aitasks/new/
draft_path() {
    local repo="$1" name="$2"
    ls "$repo/aitasks/new/"draft_*_"$name".md 2>/dev/null | head -1
}

# Helper: read file_references line from a task/draft file frontmatter
read_file_refs_line() {
    local file="$1"
    grep '^file_references:' "$file" 2>/dev/null || true
}

set +e

echo "=== file_references Tests ==="
echo ""

# --- Test 1: Single --file-ref in batch create ---
echo "--- Test 1: Single --file-ref ---"
TMPDIR_1="$(setup_project)"
(cd "$TMPDIR_1/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t1" --desc "one ref" \
        --file-ref "foo.py" >/dev/null 2>&1)
draft1=$(draft_path "$TMPDIR_1/local" t1)
refs_line1=$(read_file_refs_line "$draft1")
assert_eq_trim "Single ref in frontmatter" "file_references: [foo.py]" "$refs_line1"
rm -rf "$TMPDIR_1"

# --- Test 2: Multiple --file-ref mixed flags ---
echo "--- Test 2: Multiple --file-ref mixed flags ---"
TMPDIR_2="$(setup_project)"
(cd "$TMPDIR_2/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t2" --desc "mixed" \
        --file-ref "a.py" --file-ref "b.py:10-20" >/dev/null 2>&1)
draft2=$(draft_path "$TMPDIR_2/local" t2)
refs_line2=$(read_file_refs_line "$draft2")
assert_eq_trim "Mixed refs preserve order" "file_references: [a.py, b.py:10-20]" "$refs_line2"
rm -rf "$TMPDIR_2"

# --- Test 3: Compact multi-range preserved verbatim ---
echo "--- Test 3: Compact multi-range preserved verbatim ---"
TMPDIR_3="$(setup_project)"
(cd "$TMPDIR_3/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t3" --desc "compact" \
        --file-ref "foo.py:10-20^30-40^89-100" >/dev/null 2>&1)
draft3=$(draft_path "$TMPDIR_3/local" t3)
refs_line3=$(read_file_refs_line "$draft3")
assert_eq_trim "Compact multi-range kept as single entry" \
    "file_references: [foo.py:10-20^30-40^89-100]" "$refs_line3"
rm -rf "$TMPDIR_3"

# --- Test 4: Same ref twice dedups to single entry ---
echo "--- Test 4: Exact-string dedup on create ---"
TMPDIR_4="$(setup_project)"
(cd "$TMPDIR_4/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t4" --desc "dup" \
        --file-ref "foo.py:10-20" --file-ref "foo.py:10-20" >/dev/null 2>&1)
draft4=$(draft_path "$TMPDIR_4/local" t4)
refs_line4=$(read_file_refs_line "$draft4")
assert_eq_trim "Duplicate exact-string ref deduped" \
    "file_references: [foo.py:10-20]" "$refs_line4"
rm -rf "$TMPDIR_4"

# --- Test 5: Order-sensitive dedup keeps two entries ---
echo "--- Test 5: Order-sensitive dedup keeps two entries ---"
TMPDIR_5="$(setup_project)"
(cd "$TMPDIR_5/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --name "t5" --desc "order" \
        --file-ref "foo.py:10-20^30-40" \
        --file-ref "foo.py:30-40^10-20" >/dev/null 2>&1)
draft5=$(draft_path "$TMPDIR_5/local" t5)
refs_line5=$(read_file_refs_line "$draft5")
assert_eq_trim "Reordered ranges are NOT deduped" \
    "file_references: [foo.py:10-20^30-40, foo.py:30-40^10-20]" "$refs_line5"
rm -rf "$TMPDIR_5"

# --- Test 6: Batch update --file-ref appends ---
echo "--- Test 6: Batch update --file-ref appends ---"
TMPDIR_6="$(setup_project)"
(cd "$TMPDIR_6/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "upd1" \
        --desc "initial" --file-ref "a.py" >/dev/null 2>&1)
task6=$(ls "$TMPDIR_6/local/aitasks"/t*_upd1.md 2>/dev/null | head -1)
task6_num=$(basename "$task6" | grep -oE '^t[0-9]+' | sed 's/t//')
(cd "$TMPDIR_6/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$task6_num" \
        --file-ref "c.py" >/dev/null 2>&1)
refs_line6=$(read_file_refs_line "$task6")
assert_eq_trim "Update appends new ref" \
    "file_references: [a.py, c.py]" "$refs_line6"
rm -rf "$TMPDIR_6"

# --- Test 7: Batch update --remove-file-ref removes existing ---
echo "--- Test 7: Batch update --remove-file-ref removes ---"
TMPDIR_7="$(setup_project)"
(cd "$TMPDIR_7/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "upd2" \
        --desc "initial" --file-ref "a.py" --file-ref "b.py:10" >/dev/null 2>&1)
task7=$(ls "$TMPDIR_7/local/aitasks"/t*_upd2.md 2>/dev/null | head -1)
task7_num=$(basename "$task7" | grep -oE '^t[0-9]+' | sed 's/t//')
(cd "$TMPDIR_7/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$task7_num" \
        --remove-file-ref "a.py" >/dev/null 2>&1)
refs_line7=$(read_file_refs_line "$task7")
assert_eq_trim "Update removes named ref" \
    "file_references: [b.py:10]" "$refs_line7"
rm -rf "$TMPDIR_7"

# --- Test 8: get_file_references round-trip ---
echo "--- Test 8: get_file_references round-trip ---"
TMPDIR_8="$(setup_project)"
(cd "$TMPDIR_8/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "rt" \
        --desc "round-trip" \
        --file-ref "a.py" --file-ref "b.py:10-20" \
        --file-ref "c.py:5^15-25" >/dev/null 2>&1)
task8=$(ls "$TMPDIR_8/local/aitasks"/t*_rt.md 2>/dev/null | head -1)
helper_out=$(cd "$TMPDIR_8/local" && \
    bash -c 'source .aitask-scripts/lib/task_utils.sh && get_file_references "'"$task8"'"')
assert_contains "Round-trip includes a.py" "a.py" "$helper_out"
assert_contains "Round-trip includes b.py:10-20" "b.py:10-20" "$helper_out"
assert_contains "Round-trip includes c.py:5^15-25" "c.py:5^15-25" "$helper_out"
line_count8=$(echo "$helper_out" | grep -c .)
assert_eq_trim "Three entries parsed back" "3" "$line_count8"
rm -rf "$TMPDIR_8"

# --- Test 9: aitask_find_by_file.sh path-only match ---
echo "--- Test 9: aitask_find_by_file.sh path-only match ---"
TMPDIR_9="$(setup_project)"
(cd "$TMPDIR_9/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "find1" \
        --desc "ready task" --file-ref "a.py:10-20^30-40" >/dev/null 2>&1)
(cd "$TMPDIR_9/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "find2" \
        --desc "exact path" --file-ref "a.py" >/dev/null 2>&1)
(cd "$TMPDIR_9/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "find3" \
        --desc "unrelated" --file-ref "other.py" >/dev/null 2>&1)
find_out9=$(cd "$TMPDIR_9/local" && ./.aitask-scripts/aitask_find_by_file.sh a.py 2>&1)
assert_contains "find1 matched (compact range)" "find1.md" "$find_out9"
assert_contains "find2 matched (bare path)" "find2.md" "$find_out9"
assert_not_contains "find3 not matched" "find3.md" "$find_out9"
match_count9=$(echo "$find_out9" | grep -c '^TASK:')
assert_eq_trim "Exactly 2 matches for a.py" "2" "$match_count9"
rm -rf "$TMPDIR_9"

# --- Test 10: aitask_find_by_file.sh excludes non-Ready/Editing ---
echo "--- Test 10: Status filter in find helper ---"
TMPDIR_10="$(setup_project)"
(cd "$TMPDIR_10/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "stat1" \
        --desc "ready" --file-ref "filt.py" >/dev/null 2>&1)
(cd "$TMPDIR_10/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "stat2" \
        --desc "will be impl" --file-ref "filt.py" >/dev/null 2>&1)
task10_impl=$(ls "$TMPDIR_10/local/aitasks"/t*_stat2.md 2>/dev/null | head -1)
task10_impl_num=$(basename "$task10_impl" | grep -oE '^t[0-9]+' | sed 's/t//')
(cd "$TMPDIR_10/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$task10_impl_num" \
        --status "Implementing" >/dev/null 2>&1)

find_out10=$(cd "$TMPDIR_10/local" && ./.aitask-scripts/aitask_find_by_file.sh filt.py 2>&1)
assert_contains "Ready task still matched" "stat1.md" "$find_out10"
assert_not_contains "Implementing task excluded" "stat2.md" "$find_out10"
rm -rf "$TMPDIR_10"

# --- Test 11: Malformed --file-ref rejected ---
echo "--- Test 11: Malformed refs rejected ---"
TMPDIR_11="$(setup_project)"
assert_exit_nonzero "Reject non-numeric range in create" \
    bash -c "cd '$TMPDIR_11/local' && ./.aitask-scripts/aitask_create.sh --batch --name bad1 --desc x --file-ref 'foo.py:abc'"
assert_exit_nonzero "Reject bad tail range in create" \
    bash -c "cd '$TMPDIR_11/local' && ./.aitask-scripts/aitask_create.sh --batch --name bad2 --desc x --file-ref 'foo.py:10-20^bad'"
# Also test update path validation
(cd "$TMPDIR_11/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "okv" \
        --desc "ok" >/dev/null 2>&1)
task11=$(ls "$TMPDIR_11/local/aitasks"/t*_okv.md 2>/dev/null | head -1)
task11_num=$(basename "$task11" | grep -oE '^t[0-9]+' | sed 's/t//')
assert_exit_nonzero "Reject non-numeric range in update" \
    bash -c "cd '$TMPDIR_11/local' && ./.aitask-scripts/aitask_update.sh --batch $task11_num --file-ref 'foo.py:xyz'"
rm -rf "$TMPDIR_11"

# --- Test 12: Interactive mode seeds all_file_refs from BATCH_FILE_REFS ---
echo "--- Test 12: Interactive seed from BATCH_FILE_REFS ---"
TMPDIR_12="$(setup_project)"
seed_out=$(cd "$TMPDIR_12/local" && bash -c '
set +e
fzf() { :; }
info() { :; }
success() { :; }
warn() { :; }
die() { :; }
func_src=$(sed -n "/^get_task_definition() {/,/^}\$/p" .aitask-scripts/aitask_create.sh)
eval "$func_src"
BATCH_FILE_REFS=("foo.py:10-20" "bar.py")
get_task_definition </dev/null
' 2>/dev/null)
seed_refs=$(echo "$seed_out" | awk '/__FILE_REFS_MARKER__/{flag=1;next} flag')
assert_contains "Pre-seeded foo.py:10-20 flows through interactive path" "foo.py:10-20" "$seed_refs"
assert_contains "Pre-seeded bar.py flows through interactive path" "bar.py" "$seed_refs"
rm -rf "$TMPDIR_12"

# --- Test 14: unrelated updates leave file_references byte-identical ---
# Characterization (t2209 pre-phase): green on the pre-t2209 tree and must stay
# green. aitask_update.sh rewrites the whole frontmatter on every update, so a
# change to how it carries file_references must not perturb the plain form.
echo "--- Test 14: unrelated updates keep file_references byte-identical ---"
TMPDIR_14="$(setup_project)"
(cd "$TMPDIR_14/local" && \
    ./.aitask-scripts/aitask_create.sh --batch --commit --name "keep" \
        --desc "keep refs" --file-ref "a.py" --file-ref "b.py:10-20" >/dev/null 2>&1)
task14=$(ls "$TMPDIR_14/local/aitasks"/t*_keep.md 2>/dev/null | head -1)
task14_num=$(basename "$task14" | grep -oE '^t[0-9]+' | sed 's/t//')
for upd14 in "--status Implementing" "--priority high" "--add-label x"; do
    # shellcheck disable=SC2086  # word-split the flag/value pair on purpose
    (cd "$TMPDIR_14/local" && \
        ./.aitask-scripts/aitask_update.sh --batch "$task14_num" $upd14 >/dev/null 2>&1)
    assert_eq "After $upd14: file_references line unchanged" \
        "file_references: [a.py, b.py:10-20]" "$(read_file_refs_line "$task14")"
done
(cd "$TMPDIR_14/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$task14_num" --remove-file-ref "a.py" >/dev/null 2>&1 && \
    ./.aitask-scripts/aitask_update.sh --batch "$task14_num" --remove-file-ref "b.py:10-20" >/dev/null 2>&1)
assert_eq "Removing every ref drops the field" "" "$(read_file_refs_line "$task14")"
rm -rf "$TMPDIR_14"

# --- t2209: the field is YAML end to end ---------------------------------
# Helpers: make a committed task, then hand-write its file_references line
# (and optionally extra frontmatter) the way a person or another tool might.
mk_task_t2209() {   # <repo> <name> -> prints "<num> <path>"
    local repo="$1" name="$2" f n
    (cd "$repo" && ./.aitask-scripts/aitask_create.sh --batch --commit --name "$name" \
        --desc "t2209 fixture" --file-ref "seed.py" >/dev/null 2>&1)
    f=$(ls "$repo/aitasks"/t*_"$name".md 2>/dev/null | head -1)
    n=$(basename "$f" | grep -oE '^t[0-9]+' | sed 's/t//')
    printf '%s %s' "$n" "$f"
}
set_refs_block() {   # <file> <replacement lines for the file_references: line>
    # Any other frontmatter line whose key the block redefines is dropped, so
    # the result never carries a duplicate key.
    local f="$1" block="$2"
    python3 - "$f" "$block" <<'PY'
import re, sys
path, block = sys.argv[1], sys.argv[2]
new = block.split("\n")
keys = {m.group(1) for m in (re.match(r"([a-z_]+):", l) for l in new) if m}
lines = open(path, encoding="utf-8").read().split("\n")
end = lines.index("---", 1)
i = next(k for k, l in enumerate(lines) if l.startswith("file_references:"))
out = []
for k, l in enumerate(lines):
    if k == i:
        out.extend(new)
    elif 0 < k < end and (m := re.match(r"([a-z_]+):", l)) and m.group(1) in keys:
        continue
    else:
        out.append(l)
open(path, "w", encoding="utf-8").write("\n".join(out))
PY
}
fm_of() {   # <file> -> the frontmatter text between the --- lines
    awk 'NR==1 && $0=="---" {f=1; next} f && $0=="---" {exit} f' "$1"
}
yaml_fields_minus() {   # <file> -> sorted key=repr lines of the frontmatter, minus status/updated_at/assigned_to
    local py
    py="$(bash -c 'source "$1/.aitask-scripts/lib/python_resolve.sh"; resolve_python' _ "$PROJECT_DIR")"
    fm_of "$1" | "$py" -c '
import sys, yaml
d = yaml.safe_load(sys.stdin.read())
for k in sorted(d):
    if k not in ("status", "updated_at", "assigned_to"):
        print("%s=%r" % (k, d[k]))'
}

echo "--- Test 15: --file-ref with a comma writes one quoted entry ---"
TMPDIR_15="$(setup_project)"
(cd "$TMPDIR_15/local" && ./.aitask-scripts/aitask_create.sh --batch --name "comma" \
    --desc "comma" --file-ref "a,b.py" --file-ref "lib/x.py:3-5" >/dev/null 2>&1)
assert_eq "comma entry is quoted, plain entry stays plain" \
    'file_references: ["a,b.py", lib/x.py:3-5]' \
    "$(read_file_refs_line "$(draft_path "$TMPDIR_15/local" comma)")"
rej_rc=0
(cd "$TMPDIR_15/local" && ./.aitask-scripts/aitask_create.sh --batch --name "nl" \
    --desc "nl" --file-ref $'a\nb' >/dev/null 2>&1) || rej_rc=$?
assert_eq "--file-ref holding a newline is rejected" "1" "$([[ $rej_rc -ne 0 ]] && echo 1 || echo 0)"
rm -rf "$TMPDIR_15"

echo "--- Test 16: unrelated update keeps a quoted list byte-identical; ops read it as YAML ---"
TMPDIR_16="$(setup_project)"
read -r n16 f16 <<< "$(mk_task_t2209 "$TMPDIR_16/local" quoted)"
set_refs_block "$f16" 'file_references: ["a,b.py", "my file.py"]'
(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_update.sh --batch "$n16" --status Implementing >/dev/null 2>&1)
assert_eq "--status leaves the quoted list byte-identical" \
    'file_references: ["a,b.py", "my file.py"]' "$(read_file_refs_line "$f16")"
(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_update.sh --batch "$n16" --file-ref "x.py" >/dev/null 2>&1)
assert_eq "--file-ref appends and keeps both quoted entries whole" \
    'file_references: ["a,b.py", "my file.py", x.py]' "$(read_file_refs_line "$f16")"
# find_by_file only reports Ready/Editing tasks.
(cd "$TMPDIR_16/local" && \
    ./.aitask-scripts/aitask_update.sh --batch "$n16" --status Ready >/dev/null 2>&1) || true
find16="$(cd "$TMPDIR_16/local" && ./.aitask-scripts/aitask_find_by_file.sh "a,b.py" 2>&1)"
assert_contains "find_by_file matches the quoted comma path" "TASK:${n16}:" "$find16"
rm -rf "$TMPDIR_16"

echo "--- Test 17: an unreadable field refuses file-ref ops and is left untouched ---"
TMPDIR_17="$(setup_project)"
read -r n17 f17 <<< "$(mk_task_t2209 "$TMPDIR_17/local" bad)"
set_refs_block "$f17" 'file_references: [on, 010]'
before17="$(cat "$f17")"
ops_rc=0
(cd "$TMPDIR_17/local" && ./.aitask-scripts/aitask_update.sh --batch "$n17" --file-ref "y.py" >/dev/null 2>&1) || ops_rc=$?
assert_eq "--file-ref on a non-path list dies" "1" "$([[ $ops_rc -ne 0 ]] && echo 1 || echo 0)"
assert_eq "...and the task file is untouched" "$before17" "$(cat "$f17")"
rm -rf "$TMPDIR_17"

echo "--- Test 18: a quoted bracket does not swallow the following fields (review finding 1) ---"
TMPDIR_18="$(setup_project)"
read -r n18 f18 <<< "$(mk_task_t2209 "$TMPDIR_18/local" brk)"
set_refs_block "$f18" $'file_references: ["a[.py"]\nverification_baseline: 0123456789abcdef0123456789abcdef01234567 @ 2026-01-01 10:00\nlabels: [ui]'
fields18_before="$(yaml_fields_minus "$f18")"
(cd "$TMPDIR_18/local" && ./.aitask-scripts/aitask_update.sh --batch "$n18" --status Implementing >/dev/null 2>&1)
assert_eq "file_references line byte-identical after --status" 'file_references: ["a[.py"]' "$(read_file_refs_line "$f18")"
assert_eq "verification_baseline still its own line" \
    "verification_baseline: 0123456789abcdef0123456789abcdef01234567 @ 2026-01-01 10:00" \
    "$(grep '^verification_baseline:' "$f18")"
assert_eq "labels still its own line" "labels: [ui]" "$(grep '^labels:' "$f18")"
assert_eq "every other key parses to the same value" "$fields18_before" "$(yaml_fields_minus "$f18")"
(cd "$TMPDIR_18/local" && ./.aitask-scripts/aitask_update.sh --batch "$n18" --file-ref "b.py" >/dev/null 2>&1)
assert_eq "ops path: appended and still quoted" 'file_references: ["a[.py", b.py]' "$(read_file_refs_line "$f18")"
assert_eq "ops path: following fields intact" "labels: [ui]" "$(grep '^labels:' "$f18")"
rm -rf "$TMPDIR_18"

echo "--- Test 19: U+0085 under LC_ALL=C is escaped and round-trips (review finding 2) ---"
TMPDIR_19="$(setup_project)"
(cd "$TMPDIR_19/local" && LC_ALL=C ./.aitask-scripts/aitask_create.sh --batch --commit --name "nel" \
    --desc "nel" --file-ref $'a\xc2\x85b.py' >/dev/null 2>&1)
f19=$(ls "$TMPDIR_19/local/aitasks"/t*_nel.md 2>/dev/null | head -1)
assert_eq "written as an escape, never the literal byte pair" 'file_references: ["a\x85b.py"]' "$(read_file_refs_line "$f19")"
got19="$(cd "$TMPDIR_19/local" && bash -c 'source .aitask-scripts/lib/task_utils.sh && get_file_references "$1"' _ "$f19" | od -An -tx1 | tr -d ' \n')"
assert_eq "reader returns the original bytes" "61c28562 2e7079" "${got19:0:8} ${got19:8:6}"
rm -rf "$TMPDIR_19"

echo "--- Test 20: a quoted entry continued on a key-like / ---suffix line survives an update ---"
# Valid YAML: PyYAML reads each as ONE path ("a ---suffix.py", "a name: part.py").
for cont20 in 'name: part.py' '---suffix.py'; do
    TMPDIR_20="$(setup_project)"
    read -r n20 f20 <<< "$(mk_task_t2209 "$TMPDIR_20/local" cont)"
    set_refs_block "$f20" $'file_references: ["a\n'"$cont20"$'"]\nlabels: [ui]'
    block20_before="$(sed -n '/^file_references:/,/"\]$/p' "$f20")"
    fields20_before="$(yaml_fields_minus "$f20")"
    upd20_rc=0
    (cd "$TMPDIR_20/local" && ./.aitask-scripts/aitask_update.sh --batch "$n20" --status Implementing >/dev/null 2>&1) || upd20_rc=$?
    assert_eq "[$cont20] update succeeds" "0" "$upd20_rc"
    assert_eq "[$cont20] both physical lines of the entry kept verbatim" "$block20_before" \
        "$(sed -n '/^file_references:/,/"\]$/p' "$f20")"
    assert_eq "[$cont20] every other key parses to the same value" "$fields20_before" "$(yaml_fields_minus "$f20")"
    got20="$(cd "$TMPDIR_20/local" && bash -c 'source .aitask-scripts/lib/task_utils.sh && get_file_references "$1"' _ "$f20")"
    assert_eq "[$cont20] reader sees the one folded path" "a $cont20" "$got20"
    rm -rf "$TMPDIR_20"
done

# --- Test 13: Syntax check on all touched scripts ---
echo "--- Test 13: Syntax check ---"
TOTAL=$((TOTAL + 1))
if bash -n "$PROJECT_DIR/.aitask-scripts/aitask_create.sh" && \
   bash -n "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" && \
   bash -n "$PROJECT_DIR/.aitask-scripts/aitask_find_by_file.sh" && \
   bash -n "$PROJECT_DIR/.aitask-scripts/lib/task_utils.sh"; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: Syntax check on touched scripts"
fi

# --- Summary ---
echo ""
echo "==============================="
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
if [[ $FAIL -eq 0 ]]; then
    echo "ALL TESTS PASSED"
else
    echo "SOME TESTS FAILED"
    exit 1
fi
