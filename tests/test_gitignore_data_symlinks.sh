#!/usr/bin/env bash
# test_gitignore_data_symlinks.sh - the data names stay ignored as SYMLINKS at
# the root, and ONLY at the root (t1711, t2184).
# Run: bash tests/test_gitignore_data_symlinks.sh
#
# In a linked task worktree, .aitask-data, aitasks and aiplans are symlinks
# (ait_link_worktree_data). A trailing-slash .gitignore pattern matches
# directories only, so `.aitask-data/` left every worktree reporting
# `?? .aitask-data`; `git worktree remove` then refused and the task could not
# archive. The primary checkout never shows it, because there .aitask-data is a
# real directory. The bare form that fixed it matches at ANY depth, so it also
# silently ignored every nested `docs/aitasks/` (t2184); the rules are therefore
# root-anchored: `/aitasks`.
#
# So this asks GIT, never a hand-rolled matcher: directory-only and any-depth
# matching are the exact semantics a re-implementation gets wrong. Each check
# builds a throwaway repo, creates a real symlink per data name at the root and
# a real file under ait_t2184_nested/<name>/, and asserts git ignores the
# symlinks but REPORTS the nested files — plus a control symlink no pattern
# matches, which MUST be reported, so a harness that stopped observing fails
# instead of passing vacuously.
#
# Inputs read at runtime (declare them to any test-selection tooling, or an
# edit to them will not re-run this test):
#   .gitignore                              (Case A — the repo's own file)
#   .aitask-scripts/lib/data_symlinks.sh    (the names under test)
#   .aitask-scripts/aitask_setup.sh         (the rewriter, Cases C-E)
#   .aitask-scripts/lib/atomic_write.sh     (the rewriter's file replacement)
#
# The .gitignore setup writes for NEW installs is covered in
# tests/test_data_branch_setup.sh, which owns the setup_data_branch fixture.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

# The rewriter lives in aitask_setup.sh; sourcing it also pulls in
# data_symlinks.sh (the names) and sets -euo pipefail, which a test must undo.
# shellcheck source=../.aitask-scripts/aitask_setup.sh
source "$PROJECT_DIR/.aitask-scripts/aitask_setup.sh" --source-only
set +euo pipefail

NAMES=("$AIT_DATA_DIR_NAME" "${AIT_DATA_LINKS[@]}")
CONTROL="ait_t1711_control"
NESTED="ait_t2184_nested"

WORK="$(mktemp -d "${TMPDIR:-/tmp}/t1711test.XXXXXX")"
cleanup() {
    [[ -n "${WORK:-}" && -d "$WORK" ]] || return 0
    chmod -R u+w "$WORK" 2>/dev/null
    rm -rf "$WORK"
}
trap cleanup EXIT

# The names must be derived, not empty: an empty list would make every
# "not reported" assertion below pass without checking anything. No fixed count
# and no literals: the gate follows data_symlinks.sh, so a new data link is
# covered (and must be ignored) without editing this file.
TOTAL=$((TOTAL + 1))
if [[ ${#NAMES[@]} -ge 2 && -n "$AIT_DATA_DIR_NAME" ]]; then
    PASS=$((PASS + 1))
else
    FAIL=$((FAIL + 1))
    echo "FAIL: data_symlinks.sh yields the data dir plus at least one link (got: ${NAMES[*]})"
fi
for name in "${NAMES[@]}"; do
    assert_not_contains "derived name '$name' is a bare name" "/" "$name"
done

# porcelain_for <gitignore-file> -> `git status --porcelain` of a fresh repo
# holding that .gitignore, one real symlink per data name, the control, and a
# real file under $NESTED/<name>/ per data name.
# Called inside $( ), so a fresh dir per call comes from mktemp, not a counter.
porcelain_for() {
    local src="$1" repo name
    repo="$(mktemp -d "$WORK/repo.XXXXXX")" || return 1
    git -C "$repo" init -q
    cp -- "$src" "$repo/.gitignore"
    for name in "${NAMES[@]}" "$CONTROL"; do
        ln -s target "$repo/$name"
    done
    for name in "${NAMES[@]}"; do
        mkdir -p "$repo/$NESTED/$name"
        echo nested > "$repo/$NESTED/$name/f"
    done
    git -C "$repo" status --porcelain --untracked-files=all
}

# check_gitignore <label> <gitignore-file>: every data name ignored as a root
# symlink, and NOT ignored as a nested directory.
check_gitignore() {
    local label="$1" src="$2" out name
    out="$(porcelain_for "$src")"
    # Positive control first: the harness still sees untracked symlinks.
    assert_contains "$label: control symlink IS reported" "?? $CONTROL" "$out"
    for name in "${NAMES[@]}"; do
        assert_not_contains "$label: symlink '$name' not reported" "?? $name" "$out"
        assert_contains "$label: nested '$NESTED/$name/f' IS reported" \
            "?? $NESTED/$name/f" "$out"
    done
}

# --- Case A: this repo's tracked .gitignore -----------------------------------
# Catches the slash coming back, the line being deleted, and a later `!`
# negation re-including the name — any of them shows up as `?? <name>`.
echo "--- Case A: repo .gitignore ignores the data names as symlinks ---"
check_gitignore "A" "$PROJECT_DIR/.gitignore"

# --- Negative control: the pre-fix block really leaves the symlink exposed ----
# Proves the check above can fail: the exact block setup used to write.
echo "--- Negative control: pre-fix .gitignore exposes .aitask-data ---"
printf '.aitask-data/\naitasks\naiplans\n' > "$WORK/prefix.gitignore"
out="$(porcelain_for "$WORK/prefix.gitignore")"
assert_contains "neg: pre-fix '.aitask-data/' leaves the symlink untracked" \
    "?? .aitask-data" "$out"
assert_contains "neg: control symlink is reported" "?? $CONTROL" "$out"

# --- Negative control: the bare block hides nested directories (t2184) -------
# Proves the nested half of check_gitignore can fail: the block setup wrote
# from t1711 until t2184 ignores the root symlinks AND every nested namesake.
echo "--- Negative control: bare .gitignore hides nested data-name dirs ---"
printf '%s\n' "${NAMES[@]}" > "$WORK/bare.gitignore"
out="$(porcelain_for "$WORK/bare.gitignore")"
assert_contains "neg-bare: control symlink is reported" "?? $CONTROL" "$out"
for name in "${NAMES[@]}"; do
    assert_not_contains "neg-bare: bare '$name' hides the nested file" \
        "?? $NESTED/$name/f" "$out"
done

# --- Case C: the rewriter repairs legacy lines, and only those ----------------
echo "--- Case C: rewrite legacy lines to the symlink-safe form ---"
C="$WORK/c.gitignore"
# Built from NAMES, so every derived name gets a legacy line to repair.
{ echo "foo/"; for name in "${NAMES[@]}"; do echo "$name/"; done; echo "bar"; } > "$C"
rc=0; _ait_rewrite_data_gitignore_lines "$C" || rc=$?
assert_eq "C: rewrite reports a change (0)" "0" "$rc"
assert_eq "C: exact rewritten content (unrelated lines untouched)" \
    "$(echo "foo/"; printf '/%s\n' "${NAMES[@]}"; echo "bar")" "$(cat "$C")"
check_gitignore "C" "$C"
rc=0; _ait_rewrite_data_gitignore_lines "$C" || rc=$?
assert_eq "C: second run reports nothing to do (1)" "1" "$rc"
rc=0; _ait_rewrite_data_gitignore_lines "$WORK/does-not-exist" || rc=$?
assert_eq "C: missing .gitignore reports nothing to do (1)" "1" "$rc"

# --- Case C2: the bare form is legacy too, and only exact lines change (t2184) --
echo "--- Case C2: rewrite bare lines; lookalikes pass through ---"
C2="$WORK/c2.gitignore"
# Lookalikes built from every name: each contains the name but is not the
# exact bare line, so each must pass through byte for byte.
lookalikes() {
    local name
    for name in "${NAMES[@]}"; do
        printf '%s\n' "$name/new/" "docs/$name" "!$name" "# $name" "${name}x" " $name"
    done
}
{ echo "foo/"; printf '%s\n' "${NAMES[@]}"; lookalikes; echo "bar"; } > "$C2"
rc=0; _ait_rewrite_data_gitignore_lines "$C2" || rc=$?
assert_eq "C2: bare lines report a change (0)" "0" "$rc"
{ echo "foo/"; printf '/%s\n' "${NAMES[@]}"; lookalikes; echo "bar"; } > "$WORK/c2.expected"
assert_exit_zero "C2: bytes exact — bare lines anchored, lookalikes untouched" \
    cmp -s "$WORK/c2.expected" "$C2"
rc=0; _ait_rewrite_data_gitignore_lines "$C2" || rc=$?
assert_eq "C2: second run reports nothing to do (1)" "1" "$rc"
# An already-anchored file is not legacy: untouched and reported as such.
C3="$WORK/c3.gitignore"
{ echo "node_modules/"; printf '/%s\n' "${NAMES[@]}"; } > "$C3"
cp "$C3" "$WORK/c3.before"
rc=0; _ait_rewrite_data_gitignore_lines "$C3" || rc=$?
assert_eq "C2: anchored file reports nothing to do (1)" "1" "$rc"
assert_exit_zero "C2: anchored file byte-identical" cmp -s "$WORK/c3.before" "$C3"
check_gitignore "C3" "$C3"

# --- Case D: a failed repair is reported as a failure, never as "unchanged" ---
echo "--- Case D: failure is distinct from 'unchanged' ---"
LEGACY_BODY="$(printf '.aitask-data/\naitasks\naiplans')"

# setup_data_gitignore_symlink_safe reads $SCRIPT_DIR/../.gitignore.
D_PROJ="$WORK/dproj"
mkdir -p "$D_PROJ/.aitask-scripts"
SETUP_SCRIPT_DIR_SAVED="$SCRIPT_DIR"
SCRIPT_DIR="$D_PROJ/.aitask-scripts"

# run_repair -> REPAIR_RC / REPAIR_OUT from the user-facing re-run step.
run_repair() {
    REPAIR_RC=0
    REPAIR_OUT="$(setup_data_gitignore_symlink_safe 2>&1)" || REPAIR_RC=$?
}

# D1: the write itself fails. atomic_write.sh's load guard keeps the
# rewriter's lazy `source` from restoring the real ait_atomic_render.
printf '%s\n' "$LEGACY_BODY" > "$D_PROJ/.gitignore"
cp "$D_PROJ/.gitignore" "$WORK/d.before"
# shellcheck source=../.aitask-scripts/lib/atomic_write.sh
source "$PROJECT_DIR/.aitask-scripts/lib/atomic_write.sh"
eval "$(declare -f ait_atomic_render | sed '1s/ait_atomic_render/_real_ait_atomic_render/')"
ait_atomic_render() { return 1; }
rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
assert_eq "D1: write failure reports 2 (not 1)" "2" "$rc"
assert_exit_zero "D1: file byte-identical after failed write" \
    cmp -s "$WORK/d.before" "$D_PROJ/.gitignore"
run_repair
assert_eq "D1: repair step stays non-fatal" "0" "$REPAIR_RC"
assert_contains "D1: repair step warns it could not rewrite" "Could not rewrite" "$REPAIR_OUT"
assert_not_contains "D1: repair step does not claim already-safe" "already symlink-safe" "$REPAIR_OUT"
eval "$(declare -f _real_ait_atomic_render | sed '1s/_real_ait_atomic_render/ait_atomic_render/')"
rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
assert_eq "D1 control: real render succeeds (0)" "0" "$rc"

# D2: the .gitignore cannot be inspected (a directory: grep exits 2). Holds
# under root too, unlike a permission fault.
rm -f "$D_PROJ/.gitignore"
mkdir "$D_PROJ/.gitignore"
rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
assert_eq "D2: uninspectable .gitignore reports 2 (not 1)" "2" "$rc"
run_repair
assert_contains "D2: repair step warns it could not rewrite" "Could not rewrite" "$REPAIR_OUT"
assert_not_contains "D2: repair step does not claim already-safe" "already symlink-safe" "$REPAIR_OUT"
rmdir "$D_PROJ/.gitignore"

# D3: a read-only .gitignore is refused, not replaced.
printf '%s\n' "$LEGACY_BODY" > "$D_PROJ/.gitignore"
chmod 444 "$D_PROJ/.gitignore"
if [[ -w "$D_PROJ/.gitignore" ]]; then
    echo "NOTE: D3 skipped — running as a user that can write a mode-444 file (root)"
else
    cp "$D_PROJ/.gitignore" "$WORK/d.before"
    rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
    assert_eq "D3: read-only .gitignore reports 2 (not 1)" "2" "$rc"
    assert_exit_zero "D3: read-only file byte-identical" \
        cmp -s "$WORK/d.before" "$D_PROJ/.gitignore"
    run_repair
    assert_contains "D3: repair step warns it could not rewrite" "Could not rewrite" "$REPAIR_OUT"
    chmod 644 "$D_PROJ/.gitignore"
    rc=0; _ait_rewrite_data_gitignore_lines "$D_PROJ/.gitignore" || rc=$?
    assert_eq "D3 control: writable again, rewrite succeeds (0)" "0" "$rc"
fi

# Unchanged is reported as unchanged.
run_repair
assert_contains "D: clean file reports already symlink-safe" "already symlink-safe" "$REPAIR_OUT"
SCRIPT_DIR="$SETUP_SCRIPT_DIR_SAVED"

# --- Case E: the repair keeps the file's mode and writes through a symlink ----
echo "--- Case E: mode and symlinked .gitignore preserved ---"
E="$WORK/e.gitignore"
printf '%s\n' "$LEGACY_BODY" > "$E"
# 664 differs from mktemp's 0600 and from the umask-022 default 0644, so a
# replacement that drops the mode cannot pass by accident.
chmod 664 "$E"
rc=0; (umask 022; _ait_rewrite_data_gitignore_lines "$E") || rc=$?
assert_eq "E: rewrite succeeds (0)" "0" "$rc"
assert_eq "E: mode 664 preserved" "664" "$(ait_file_mode "$E")"
assert_exit_zero "E: legacy line rewritten" grep -qxF "/.aitask-data" "$E"

mkdir -p "$WORK/elink"
printf '%s\n' "$LEGACY_BODY" > "$WORK/elink/shared.gitignore"
ln -s shared.gitignore "$WORK/elink/.gitignore"
rc=0; _ait_rewrite_data_gitignore_lines "$WORK/elink/.gitignore" || rc=$?
assert_eq "E: symlinked .gitignore rewrite succeeds (0)" "0" "$rc"
assert_eq "E: the .gitignore symlink survives" "link" \
    "$([[ -L "$WORK/elink/.gitignore" ]] && echo link || echo notlink)"
assert_exit_zero "E: rewrite landed in the link target" \
    grep -qxF "/.aitask-data" "$WORK/elink/shared.gitignore"
assert_eq "E: no staging temp left beside the target" "" \
    "$(find "$WORK/elink" -name '.shared.gitignore.*' -print)"

# --- Case F: CRLF .gitignore (core.autocrlf=true checkouts) -------------------
# Git strips a trailing CR before matching, so CRLF `.aitask-data/` is still
# directory-only and leaves the symlink untracked — but grep -x and a plain awk
# record both see the CR, so a naive rewriter reports "nothing to do".
echo "--- Case F: CRLF legacy lines are detected and rewritten ---"
F="$WORK/f.gitignore"
legacy_crlf=""
for name in "${NAMES[@]}"; do legacy_crlf+="$name/"$'\r\n'; done
printf 'foo/\r\n%s# keep\r\n' "$legacy_crlf" > "$F"
# Precondition, asked of git: the CRLF legacy file really exposes the symlinks.
out="$(porcelain_for "$F")"
assert_contains "F: precondition: CRLF '.aitask-data/' leaves the symlink untracked" \
    "?? $AIT_DATA_DIR_NAME" "$out"

rc=0; _ait_rewrite_data_gitignore_lines "$F" || rc=$?
assert_eq "F: CRLF legacy lines detected and rewritten (0)" "0" "$rc"
expected_crlf="foo/"$'\r\n'
for name in "${NAMES[@]}"; do expected_crlf+="/$name"$'\r\n'; done
expected_crlf+="# keep"$'\r\n'
printf '%s' "$expected_crlf" > "$WORK/f.expected"
assert_exit_zero "F: bytes exact — CRLF kept on every line, unrelated lines untouched" \
    cmp -s "$WORK/f.expected" "$F"
check_gitignore "F" "$F"
rc=0; _ait_rewrite_data_gitignore_lines "$F" || rc=$?
assert_eq "F: second run on CRLF is a no-op (1)" "1" "$rc"

# F2: the bare form in a CRLF file (t2184).
F2="$WORK/f2.gitignore"
bare_crlf="" anchored_crlf=""
for name in "${NAMES[@]}"; do
    bare_crlf+="$name"$'\r\n'
    anchored_crlf+="/$name"$'\r\n'
done
printf 'foo/\r\n%s# keep\r\n' "$bare_crlf" > "$F2"
rc=0; _ait_rewrite_data_gitignore_lines "$F2" || rc=$?
assert_eq "F2: CRLF bare lines detected and rewritten (0)" "0" "$rc"
printf 'foo/\r\n%s# keep\r\n' "$anchored_crlf" > "$WORK/f2.expected"
assert_exit_zero "F2: bytes exact — CRLF kept, bare lines anchored" \
    cmp -s "$WORK/f2.expected" "$F2"
check_gitignore "F2" "$F2"
rc=0; _ait_rewrite_data_gitignore_lines "$F2" || rc=$?
assert_eq "F2: second run on CRLF is a no-op (1)" "1" "$rc"

# --- Case G: the repair lists nested data-name paths, claiming no provenance --
# setup_data_gitignore_symlink_safe reads $SCRIPT_DIR/../.gitignore; after a
# successful rewrite it lists the untracked paths under NESTED data-name dirs
# (_ait_report_unhidden_nested_data_paths, t2184). It scans after the rewrite
# only, so its wording must not claim the paths were hidden before: G2 is a
# file whose rewrite (rc 0) never touched the line that matters.
echo "--- Case G: repair lists nested data-name paths (neutral wording) ---"
G_LINK_A="${AIT_DATA_LINKS[0]}"
G_LINK_B="${AIT_DATA_LINKS[${#AIT_DATA_LINKS[@]}-1]}"
assert_not_contains "G: precondition: two data links to nest" "$G_LINK_A" "$G_LINK_B"

# g_repo <dir> <gitignore-body>: a git repo with that .gitignore, the root data
# symlinks, files under nested data-name dirs, and a control file.
g_repo() {
    local repo="$1" name
    mkdir -p "$repo/.aitask-scripts" "$repo/docs/$G_LINK_A" "$repo/x/y/$G_LINK_B" "$repo/notdata"
    git -C "$repo" init -q
    printf '%s' "$2" > "$repo/.gitignore"
    for name in "${NAMES[@]}"; do ln -s target "$repo/$name"; done
    echo t > "$repo/docs/$G_LINK_A/t1.md"
    echo p > "$repo/x/y/$G_LINK_B/p.md"
    echo n > "$repo/notdata/f"
}
# listed_lines <output>: the indented path lines of the listing, verbatim.
listed_lines() { printf '%s\n' "$1" | grep -E '^    [^ ]' | sed 's/^    //'; }

G_SAVED_SCRIPT_DIR="$SCRIPT_DIR"

# G1: the bare block (setup's form until t2184).
G1="$WORK/g1"
g_repo "$G1" "$(printf '%s\n' "${NAMES[@]}")"$'\n'
SCRIPT_DIR="$G1/.aitask-scripts"
out="$(setup_data_gitignore_symlink_safe 2>&1)"
assert_contains "G1: repair rewrote the bare block" "Rewrote legacy data entries" "$out"
listed="$(listed_lines "$out")"
assert_eq "G1: exactly the two nested dirs are listed" \
    "$(printf '%s\n' "docs/$G_LINK_A/" "x/y/$G_LINK_B/" | sort)" "$(printf '%s\n' "$listed" | sort)"
assert_not_contains "G1: never names the control" "notdata" "$out"
out="$(setup_data_gitignore_symlink_safe 2>&1)"
assert_contains "G1: second run reports already safe" "already symlink-safe" "$out"
assert_eq "G1: second run lists nothing" "" "$(listed_lines "$out")"

# G2: mixed rules — only `.aitask-data/` is legacy, and docs/<link>/ was never
# hidden. The rewrite still returns 0, so the listing must not claim otherwise.
G2="$WORK/g2"
g_body="$AIT_DATA_DIR_NAME/"$'\n'
for name in "${AIT_DATA_LINKS[@]}"; do g_body+="/$name"$'\n'; done
g_repo "$G2" "$g_body"
assert_contains "G2: precondition: docs/$G_LINK_A/t1.md already untracked before the repair" \
    "?? docs/$G_LINK_A/t1.md" "$(git -C "$G2" status --porcelain --untracked-files=all)"
SCRIPT_DIR="$G2/.aitask-scripts"
out="$(setup_data_gitignore_symlink_safe 2>&1)"
assert_contains "G2: the mixed file is rewritten (rc 0 path)" "Rewrote legacy data entries" "$out"
assert_contains "G2: docs/$G_LINK_A/ is listed" "    docs/$G_LINK_A/" "$out"
assert_contains "G2: neutral wording" "show as untracked" "$out"
assert_not_contains "G2: no 'hidden' provenance claim" "hidden" "$out"
assert_not_contains "G2: no 'old unanchored' provenance claim" "old unanchored" "$out"

# G3: the listing is capped at 10 with a remainder line.
G3="$WORK/g3"
g_repo "$G3" "$(printf '%s\n' "${NAMES[@]}")"$'\n'
for i in $(seq 1 11); do mkdir -p "$G3/extra$i/$G_LINK_A"; echo e > "$G3/extra$i/$G_LINK_A/f"; done
SCRIPT_DIR="$G3/.aitask-scripts"
out="$(setup_data_gitignore_symlink_safe 2>&1)"
assert_eq "G3: ten paths shown" "10" "$(listed_lines "$out" | grep -cv '^… and ')"
assert_contains "G3: remainder line (13 nested dirs, 10 shown)" "… and 3 more" "$out"

# G4: outside a git work tree the repair still succeeds and lists nothing.
G4="$WORK/g4"
mkdir -p "$G4/.aitask-scripts" "$G4/docs/$G_LINK_A"
printf '%s\n' "${NAMES[@]}" > "$G4/.gitignore"
SCRIPT_DIR="$G4/.aitask-scripts"
rc=0; out="$(setup_data_gitignore_symlink_safe 2>&1)" || rc=$?
assert_eq "G4: not a repo: repair stays non-fatal" "0" "$rc"
assert_contains "G4: not a repo: rewrite still reported" "Rewrote legacy data entries" "$out"
assert_eq "G4: not a repo: nothing listed" "" "$(listed_lines "$out")"

# G5: names git would C-quote. Without -z, `quote"name.txt` comes back as
# `"docs/<link>/quote\"name.txt"`, which split the one directory into
# `docs/<link>/` and `"docs/<link>/` (t2184 review). Raw NUL-separated paths
# give one entry per directory; a directory whose own name needs escaping is
# shown once, escaped, on a single line.
G5="$WORK/g5"
mkdir -p "$G5/.aitask-scripts" "$G5/docs/$G_LINK_A" "$G5/odd"$'\n'"dir/$G_LINK_B"
git -C "$G5" init -q
printf '%s\n' "${NAMES[@]}" > "$G5/.gitignore"
echo a > "$G5/docs/$G_LINK_A/normal.txt"
echo b > "$G5/docs/$G_LINK_A/quote\"name.txt"
echo c > "$G5/docs/$G_LINK_A/back\\slash.txt"
echo d > "$G5/odd"$'\n'"dir/$G_LINK_B/f"
assert_contains "G5: precondition: git C-quotes the quote-name path without -z" \
    "\"docs/$G_LINK_A/quote\\\"name.txt\"" "$(git -C "$G5" ls-files -o)"
SCRIPT_DIR="$G5/.aitask-scripts"
out="$(setup_data_gitignore_symlink_safe 2>&1)"
assert_eq "G5: one entry per directory, the odd one escaped on one line" \
    "$(printf '%s\n' "docs/$G_LINK_A/" "\$'odd\\ndir/$G_LINK_B/'" | sort)" \
    "$(listed_lines "$out" | sort)"
SCRIPT_DIR="$G_SAVED_SCRIPT_DIR"

# G6 / G7 drive the helper itself through a `git` function shim, which shadows
# the binary for its `-C <dir> ls-files` call only (the pipeline stage is a
# subshell, which inherits functions). G6_GIT_RC is the shim's exit status.
G6="$WORK/g6"
mkdir -p "$G6"
G6_GIT_RC=0
G6_PRODUCER=g6_one_path
g6_one_path() { printf 'docs/%s/f\0' "$G_LINK_A"; }
g6_many_paths() {
    local i
    for i in $(seq 1 1200); do printf 'd%s/%s/f\0' "$i" "$G_LINK_A"; done
    # A repeat that is NOT adjacent to its first occurrence.
    printf 'd1/%s/g\0' "$G_LINK_A"
}
git() {
    if [[ "${1:-}" == "-C" && "${3:-}" == "ls-files" ]]; then
        "$G6_PRODUCER"
        return "$G6_GIT_RC"
    fi
    command git "$@"
}

# G6: a scan that fails AFTER printing paths must show nothing — a partial list
# presented as the list would be wrong (t2184 review). The control proves the
# shim's output is consumed, so the negative is not vacuous.
out="$(_ait_report_unhidden_nested_data_paths "$G6" 2>&1)"
assert_eq "G6 control: a succeeding producer's path is listed" "docs/$G_LINK_A/" "$(listed_lines "$out")"
G6_GIT_RC=128
out="$(_ait_report_unhidden_nested_data_paths "$G6" 2>&1)"
assert_eq "G6: a producer failing after output lists nothing" "" "$(listed_lines "$out")"
assert_not_contains "G6: ... and prints no header" "show as untracked" "$out"

# G7: 1200 distinct directories plus a non-adjacent repeat: dedupe is exact
# (sort -u, not a per-entry scan of everything collected so far).
G6_GIT_RC=0
G6_PRODUCER=g6_many_paths
out="$(_ait_report_unhidden_nested_data_paths "$G6" 2>&1)"
assert_eq "G7: ten paths shown" "10" "$(listed_lines "$out" | grep -cv '^… and ')"
assert_contains "G7: remainder counts distinct directories only" "… and 1190 more" "$out"
unset -f git

echo
echo "=== Results ==="
echo "Total:  $TOTAL"
echo "Pass:   $PASS"
echo "Fail:   $FAIL"
[[ "$FAIL" -eq 0 ]] && { echo "PASS"; exit 0; }
echo "FAIL"
exit 1
