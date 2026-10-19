#!/usr/bin/env bash
# test_artifact_gitbranch_backend.sh - the `gitbranch` artifact backend (t1231_1):
# blobs on a dedicated orphan branch written with git plumbing only.
#
# Covers the adapter contract (put/head/get/list/delete/init), the R1 push-gated
# publish (a write never succeeds without reaching origin, including an
# unchanged local-only store), the R2 probe (an unmarked existing branch is
# refused, never adopted), the R3 project identity (racing first writers
# converge on ONE store id), the R4 guard (renamed branch, missing record,
# store mismatch), `gitbranch-migrate` (fence + catch-up cutover, idempotent
# rerun, truthful failure reporting) and the registry/manifest verbs.
#
# Contention is injected with FIXTURE git hooks only (pre-push / pre-commit),
# never a production test hook: an interloping write runs from inside the
# hook, so the adapter's lease is genuinely rejected.
#
# Every fixture is a legacy-mode repo (task data on main) so `task_git` is
# plain git. Assertions run in the main shell; library calls run in a child
# process (gb.sh) so a `die` there cannot end the test.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
PASS=0; FAIL=0; TOTAL=0

ART="$PROJECT_DIR/.aitask-scripts/aitask_artifact.sh"
REG_PY="$PROJECT_DIR/.aitask-scripts/lib/artifact_registry.py"
PY="$(source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; resolve_python)"
BR="aitask-artifacts"

TMP="$(mktemp -d)"
trap 'chmod -R u+w "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT
export AIT_TEST_PROJECT_DIR="$PROJECT_DIR"

# ── Fixture helpers ───────────────────────────────────────────────────────────

# gb.sh <op> [args] -- run one adapter op in the cwd's repo, activated through
# the registry like the CLI does. GB_EXPECT pins ARTIFACT_GITBRANCH_STORE_ID.
cat > "$TMP/gb.sh" <<'EOF'
#!/usr/bin/env bash
set -uo pipefail
L="$AIT_TEST_PROJECT_DIR/.aitask-scripts/lib"
SCRIPT_DIR="$AIT_TEST_PROJECT_DIR/.aitask-scripts"
source "$L/terminal_compat.sh"; source "$L/task_utils.sh"; source "$L/python_resolve.sh"
source "$L/artifact_utils.sh"; source "$L/artifact_backend.sh"; source "$L/artifact_cache.sh"
source "$L/artifact_registry.sh"
artifact_registry_activate gitbranch
export ARTIFACT_GITBRANCH_STORE_ID="${GB_EXPECT:-}"
op="$1"; shift
case "$op" in
    put|head|get|delete|list|init) "artifact_backend_$op" "$@" ;;
    store-id) artifact_gitbranch_store_id ;;
    *) echo "gb.sh: unknown op $op" >&2; exit 2 ;;
esac
EOF

# The interloper/hook scripts run inside a git hook: drop every GIT_* variable
# the parent git may have exported before touching another repository.
HOOK_PRELUDE='unset GIT_DIR GIT_WORK_TREE GIT_INDEX_FILE GIT_PREFIX GIT_COMMON_DIR GIT_OBJECT_DIRECTORY GIT_QUARANTINE_PATH'

write_config() {  # write_config <repo> <branch>
    printf 'artifacts:\n  default_backend: gitbranch\n  backends:\n    gitbranch:\n      branch: %s\n' "$2" \
        > "$1/aitasks/metadata/project_config.yaml"
}

mk_task() {  # mk_task <repo> <stem>
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s.\n' "$2" \
        > "$1/aitasks/$2.md"
}

seed_repo() {  # seed_repo <dir> -- a repo on main with tasks t5/t6 + config
    mkdir -p "$1/aitasks/metadata"
    git -C "$1" init -q -b main
    git -C "$1" config user.email t@t.t; git -C "$1" config user.name tester
    mk_task "$1" t5_demo; mk_task "$1" t6_other
    write_config "$1" "$BR"
    git -C "$1" add -A; git -C "$1" commit -q -m init
}

# new_world <name> -- bare remote + clones A and B of an initial main.
new_world() {
    W="$TMP/$1"; mkdir -p "$W"
    git init -q --bare "$W/remote.git"
    git -C "$W/remote.git" symbolic-ref HEAD refs/heads/main
    seed_repo "$W/seed"
    git -C "$W/seed" remote add origin "$W/remote.git"
    git -C "$W/seed" push -q origin main 2>/dev/null
    local c
    for c in A B; do
        git clone -q "$W/remote.git" "$W/$c" 2>/dev/null
        git -C "$W/$c" config user.email t@t.t; git -C "$W/$c" config user.name tester
    done
}

# new_solo <name> -- one repo N with NO remote.
new_solo() {
    W="$TMP/$1"; mkdir -p "$W"
    seed_repo "$W/N"
}

add_origin() {  # add_origin -- give $W/N a fresh bare origin
    git init -q --bare "$W/remote.git"
    git -C "$W/remote.git" symbolic-ref HEAD refs/heads/main
    git -C "$W/N" remote add origin "$W/remote.git"
}

# art <clone> <args...> -- run the CLI in a clone with its OWN resolver cache.
art()  { local c="$1"; shift; ( cd "$W/$c" && XDG_CACHE_HOME="$W/xdg_$c" "$ART" "$@" ); }
# gb <clone> <op> <args...> -- one adapter op in a clone.
gb()   { local c="$1"; shift; ( cd "$W/$c" && XDG_CACHE_HOME="$W/xdg_$c" bash "$TMP/gb.sh" "$@" ); }
cold() { rm -rf "$W/xdg_$1"; }

rtip()  { git -C "$W/remote.git" rev-parse -q --verify "refs/heads/$1" 2>/dev/null || true; }
rblobs() { git -C "$W/remote.git" ls-tree -r --name-only "refs/heads/$1" -- blobs/ 2>/dev/null || true; }
rmarker_id() { git -C "$W/remote.git" cat-file blob "refs/heads/$1:.ait-artifact-store" 2>/dev/null | sed -n 's/^store_id: //p'; }
record_id() { sed -n 's/.*"store_id": "\([0-9a-f]*\)".*/\1/p' "$W/$1/artifacts/gitbranch_store.json" 2>/dev/null; }
record_branch() { sed -n 's/.*"branch": "\([^"]*\)".*/\1/p' "$W/$1/artifacts/gitbranch_store.json" 2>/dev/null; }
blobpath() { local h="${1#sha256:}"; printf 'blobs/%s/%s' "${h:0:2}" "${h:2}"; }
sha() { printf 'sha256:%s' "$(sha256sum "$1" 2>/dev/null | cut -d' ' -f1 || shasum -a 256 "$1" | cut -d' ' -f1)"; }
commits() { git -C "$W/$1" rev-list --count HEAD; }

# mk_marked_branch <clone> <branch> <store_id> -- push a branch whose tip carries
# a valid store marker with the given id (a foreign store / adoptable store).
mk_marked_branch() {
    local d="$W/$1" m t c
    m="$(printf 'store_id: %s\nbranch: %s\ncreated_at: 2026-01-01 00:00\n' "$3" "$2" | git -C "$d" hash-object -w --stdin)"
    t="$(printf '100644 blob %s\t.ait-artifact-store\n' "$m" | git -C "$d" mktree)"
    c="$(echo "foreign store" | git -C "$d" commit-tree "$t")"
    git -C "$d" push -q origin "$c:refs/heads/$2" 2>/dev/null
}

# hook <clone> <name> <body> -- install an executable fixture hook.
hook() {
    printf '#!/usr/bin/env bash\n%s\n%s\n' "$HOOK_PRELUDE" "$3" > "$W/$1/.git/hooks/$2"
    chmod +x "$W/$1/.git/hooks/$2"
}
unhook() { rm -f "$W/$1/.git/hooks/$2"; }

# ── 1. Registry: ref_name validator, validate-ref, adapters, activation ──────
echo "=== 1. registry ==="
new_world reg
for bad in main master aitask-data aitask-locks aitask-ids; do
    out="$("$PY" "$REG_PY" --config "$W/A/aitasks/metadata/project_config.yaml" validate-ref "$bad" 2>&1)"; rc=$?
    assert_exit_nonzero_rc "validate-ref rejects reserved '$bad'" "$rc"
    assert_contains "validate-ref '$bad' names the key" "artifacts.backends.gitbranch.branch" "$out"
    write_config "$W/A" "$bad"
    out="$(gb A list 2>&1)"; rc=$?
    assert_exit_nonzero_rc "activation rejects reserved '$bad' (single-sourced rule)" "$rc"
    assert_contains "activation error for '$bad' names the key" "artifacts.backends.gitbranch.branch" "$out"
done
for bad in "-lead" "a..b" "a//b" "trail/" "/lead" "x.lock" "a/b.lock/c" "dot." "a/.hidden" "sp ace" "a@{b" "HEAD" "q?x"; do
    "$PY" "$REG_PY" --config "$W/A/aitasks/metadata/project_config.yaml" validate-ref "$bad" >/dev/null 2>&1; rc=$?
    assert_exit_nonzero_rc "validate-ref rejects malformed '$bad'" "$rc"
    write_config "$W/A" "$bad"
    gb A list >/dev/null 2>&1; rc=$?
    assert_exit_nonzero_rc "activation rejects malformed '$bad'" "$rc"
done
# validate-ref and activation judge the SAME raw string: a trailing newline or
# padding is rejected by both (re.match's `$` would accept "main\n").
for raw in $'main\n' $'aitask-artifacts\n' ' pad' 'pad '; do
    "$PY" "$REG_PY" --config "$W/A/aitasks/metadata/project_config.yaml" validate-ref "$raw" >/dev/null 2>&1; rc=$?
    assert_exit_nonzero_rc "validate-ref rejects $(printf '%q' "$raw")" "$rc"
done
printf 'artifacts:\n  backends:\n    gitbranch:\n      branch: " pad"\n' > "$W/A/aitasks/metadata/project_config.yaml"
gb A list >/dev/null 2>&1; rc=$?
assert_exit_nonzero_rc "activation rejects a padded branch, agreeing with validate-ref" "$rc"
printf 'artifacts:\n  backends:\n    gitbranch:\n      branch: "main\\n"\n' > "$W/A/aitasks/metadata/project_config.yaml"
gb A list >/dev/null 2>&1; rc=$?
assert_exit_nonzero_rc "activation rejects a trailing-newline branch" "$rc"
for good in aitask-artifacts store/blobs v1.2_x; do
    "$PY" "$REG_PY" --config "$W/A/aitasks/metadata/project_config.yaml" validate-ref "$good"; rc=$?
    assert_exit_zero_rc "validate-ref accepts '$good'" "$rc"
done
write_config "$W/A" "$BR"
assert_eq "adapters lists every shipped adapter, config-independent" "local
dir
gitbranch" "$("$PY" "$REG_PY" --config "$W/A/aitasks/metadata/project_config.yaml" adapters)"
printf 'artifacts:\n  backends: {}\n' > "$W/A/aitasks/metadata/project_config.yaml"
assert_contains "adapters ignores what is registered" "gitbranch" \
    "$("$PY" "$REG_PY" --config "$W/A/aitasks/metadata/project_config.yaml" adapters)"
out="$(gb A list 2>&1)"; rc=$?
assert_exit_nonzero_rc "unregistered gitbranch dies" "$rc"
assert_contains "unregistered error names the key" "artifacts.backends.gitbranch" "$out"
printf 'artifacts:\n  backends:\n    gitbranch: {}\n' > "$W/A/aitasks/metadata/project_config.yaml"
out="$(gb A list 2>&1)"; rc=$?
assert_exit_nonzero_rc "missing branch key dies" "$rc"
assert_contains "missing-key error names 'branch'" "'branch'" "$out"
write_config "$W/A" "$BR"
# Cross-activation leakage: activating local / dir clears the gitbranch params.
leak="$( cd "$W/A" && L="$PROJECT_DIR/.aitask-scripts/lib" && SCRIPT_DIR="$PROJECT_DIR/.aitask-scripts" \
    && source "$L/terminal_compat.sh" && source "$L/task_utils.sh" && source "$L/artifact_registry.sh" \
    && artifact_registry_activate gitbranch && export ARTIFACT_GITBRANCH_STORE_ID=abc \
    && artifact_registry_activate local \
    && printf '%s|%s' "${ARTIFACT_GITBRANCH_BRANCH:-unset}" "${ARTIFACT_GITBRANCH_STORE_ID:-unset}" )"
assert_eq "activating local clears ARTIFACT_GITBRANCH_BRANCH and _STORE_ID" "unset|unset" "$leak"

# ── 2. Adapter round trip, bootstrap, idempotence, user index ────────────────
echo "=== 2. round trip ==="
new_world rt
printf 'blob one\n' > "$W/A/f1"; H1="$(sha "$W/A/f1")"
printf 'blob two\n' > "$W/A/f2"; H2="$(sha "$W/A/f2")"
gb A put "$H1" f1 >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "first put bootstraps the store" "$rc"
assert_eq "bootstrap: exactly one (root) commit on origin" "1" "$(git -C "$W/remote.git" rev-list --count "$BR")"
assert_eq "bootstrap: the root is parentless" "1" "$(git -C "$W/remote.git" rev-list --max-parents=0 --count "$BR")"
assert_contains "bootstrap root carries the blob" "$(blobpath "$H1")" "$(rblobs "$BR")"
assert_contains_re "bootstrap root carries a valid marker" '^[0-9a-f]{32}$' "$(rmarker_id "$BR")"
root="$(rtip "$BR")"; marker_oid="$(git -C "$W/remote.git" rev-parse "$BR:.ait-artifact-store")"
assert_exit_zero "head finds the blob" gb A head "$H1"
assert_exit_nonzero "head answers absent for another hash" gb A head "$H2"
gb A get "$H1" "$W/A/out1" >/dev/null 2>&1
assert_eq "get to a file returns identical bytes" "$(cat "$W/A/f1")" "$(cat "$W/A/out1")"
assert_eq "get - streams to stdout" "$(cat "$W/A/f1")" "$(gb A get "$H1" - 2>/dev/null)"
assert_eq "list prints the stored hash" "$H1" "$(gb A list 2>/dev/null)"
gb A put "$H1" f1 >/dev/null 2>&1
assert_eq "double put adds no commit" "$root" "$(rtip "$BR")"
# The user's index is never touched by put/delete.
printf 'x\n' > "$W/A/unrelated.txt"; git -C "$W/A" add unrelated.txt
idx_before="$(git -C "$W/A" diff --cached --name-only)"
gb A put "$H2" f2 >/dev/null 2>&1
assert_eq "second put extends the root (parent = root)" "$root" "$(git -C "$W/remote.git" rev-parse "$BR^")"
assert_eq "second put leaves the marker blob untouched" "$marker_oid" "$(git -C "$W/remote.git" rev-parse "$BR:.ait-artifact-store")"
gb A delete "$H2" >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "delete succeeds" "$rc"
assert_not_contains "delete removed the blob from origin" "$(blobpath "$H2")" "$(rblobs "$BR")"
assert_eq "user index unchanged across put/delete" "$idx_before" "$(git -C "$W/A" diff --cached --name-only)"
gb A delete "$H2" >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "delete of an absent blob is a no-op success" "$rc"
assert_eq "local mirror follows the published tip" "$(rtip "$BR")" "$(git -C "$W/A" rev-parse "refs/heads/$BR")"

# ── 3. Two concurrent first writers converge on one root ─────────────────────
echo "=== 3. racing bootstraps ==="
new_world race
printf 'from A\n' > "$W/A/fa"; HA="$(sha "$W/A/fa")"
printf 'from B\n' > "$W/B/fb"; HB="$(sha "$W/B/fb")"
hook A pre-push "[ -e '$W/hooked' ] && exit 0; touch '$W/hooked'
while read -r _l lsha _r _rs; do echo \"\$lsha\" > '$W/a_pushed'; done
( cd '$W/B' && XDG_CACHE_HOME='$W/xdg_B' bash '$TMP/gb.sh' put '$HB' fb ) >/dev/null 2>&1
exit 0"
gb A put "$HA" fa >/dev/null 2>"$W/err"; rc=$?
assert_exit_zero_rc "the loser of the root race retries and succeeds" "$rc"
assert_eq "one root after the race" "1" "$(git -C "$W/remote.git" rev-list --max-parents=0 --count "$BR")"
assert_eq "history is linear: B's root, then A's commit" "2" "$(git -C "$W/remote.git" rev-list --count "$BR")"
assert_contains "B's blob survived" "$(blobpath "$HB")" "$(rblobs "$BR")"
assert_contains "A's blob landed" "$(blobpath "$HA")" "$(rblobs "$BR")"
assert_eq "A's commit sits on B's root" "$(git -C "$W/remote.git" rev-list --max-parents=0 "$BR")" \
    "$(git -C "$W/remote.git" rev-parse "$BR^")"
assert_not_contains "A's own candidate root was NOT published" "$(cat "$W/a_pushed")" \
    "$(git -C "$W/remote.git" rev-list "$BR")"
unhook A pre-push

# ── 4. CAS on an existing branch: the retry builds on the interloper ─────────
echo "=== 4. CAS interloper ==="
new_world cas
printf 'c1\n' > "$W/A/c1"; HC1="$(sha "$W/A/c1")"
printf 'c2\n' > "$W/B/c2"; HC2="$(sha "$W/B/c2")"
printf 'c3\n' > "$W/A/c3"; HC3="$(sha "$W/A/c3")"
gb A put "$HC1" c1 >/dev/null 2>&1
hook A pre-push "[ -e '$W/hooked' ] && exit 0; touch '$W/hooked'
( cd '$W/B' && XDG_CACHE_HOME='$W/xdg_B' bash '$TMP/gb.sh' put '$HC2' c2 ) >/dev/null 2>&1
git -C '$W/remote.git' rev-parse refs/heads/$BR > '$W/interloper'
exit 0"
gb A put "$HC3" c3 >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "put retries after a lease rejection" "$rc"
assert_contains "the interloper's blob is on origin" "$(blobpath "$HC2")" "$(rblobs "$BR")"
assert_contains "the retried blob is on origin" "$(blobpath "$HC3")" "$(rblobs "$BR")"
assert_eq "the retry's parent IS the interloper (fresh refresh, no memo)" \
    "$(cat "$W/interloper")" "$(git -C "$W/remote.git" rev-parse "$BR^")"
unhook A pre-push

# ── 5. Two clones racing a full create converge on ONE store id (R3) ─────────
echo "=== 5. R3 identity ==="
new_world r3
printf 'A artifact\n' > "$W/A/a.txt"; printf 'B artifact\n' > "$W/B/b.txt"
hook A pre-push "[ -e '$W/hooked' ] && exit 0; touch '$W/hooked'
while read -r _l lsha _r _rs; do echo \"\$lsha\" > '$W/a_pushed'; done
( cd '$W/B' && XDG_CACHE_HOME='$W/xdg_B' '$ART' create 6 b.txt --kind report --handle art:t6-b ) >/dev/null 2>&1
exit 0"
art A create 5 a.txt --kind report --handle art:t5-a >/dev/null 2>"$W/err"; rc=$?
assert_exit_zero_rc "A's create succeeds after losing the root race" "$rc"
unhook A pre-push
assert_eq "exactly one store root on the branch" "1" "$(git -C "$W/remote.git" rev-list --max-parents=0 --count "$BR")"
mid="$(rmarker_id "$BR")"
assert_eq "B's record holds the marker's id" "$mid" "$(record_id B)"
assert_eq "A's record holds the SAME id (derived from the winning tip)" "$mid" "$(record_id A)"
a_candidate="$(git -C "$W/A" cat-file blob "$(cat "$W/a_pushed"):.ait-artifact-store" 2>/dev/null | sed -n 's/^store_id: //p')"
assert_contains_re "negative control: A did mint its own candidate id" '^[0-9a-f]{32}$' "$a_candidate"
assert_eq "negative control: A's record is not its own minted candidate" "1" "$([[ "$a_candidate" != "$(record_id A)" ]] && echo 1 || echo 0)"
assert_contains "the record is committed with A's first manifest" "artifacts/gitbranch_store.json" \
    "$(git -C "$W/A" show --name-only --pretty=format: HEAD)"

# ── 6. Publish: a second clone gets the bytes; unwritable remote → no manifest ─
echo "=== 6. publish ==="
new_world pub
printf 'published bytes\n' > "$W/A/p.txt"
art A create 5 p.txt --kind report --handle art:t5-p >/dev/null 2>&1
git -C "$W/A" push -q origin main 2>/dev/null
git -C "$W/B" pull -q --no-rebase 2>/dev/null
art B get art:t5-p --out "$W/B/got.txt" >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "clone B resolves A's handle" "$rc"
assert_eq "clone B gets A's bytes (cold cache, from the branch)" "$(cat "$W/A/p.txt")" "$(cat "$W/B/got.txt" 2>/dev/null)"
new_world pubro
printf 'never published\n' > "$W/A/n.txt"
before="$(commits A)"
chmod -R a-w "$W/remote.git"
art A create 5 n.txt --kind report --handle art:t5-n >/dev/null 2>"$W/err"; rc=$?
chmod -R u+w "$W/remote.git"
assert_exit_nonzero_rc "create fails when origin refuses the push" "$rc"
assert_eq "no data commit when publication failed" "$before" "$(commits A)"
assert_file_not_exists "no manifest left behind" "$W/A/artifacts/manifests/t5-n.json"
assert_file_not_exists "no store record left behind" "$W/A/artifacts/gitbranch_store.json"
assert_eq "origin has no store branch" "" "$(rtip "$BR")"

# ── 7. Guard matrix (R4) ──────────────────────────────────────────────────────
echo "=== 7. guard ==="
new_world guard
printf 'g1\n' > "$W/A/g1.txt"; printf 'g2\n' > "$W/A/g2.txt"
art A create 5 g1.txt --kind report --handle art:t5-g1 >/dev/null 2>&1
art A create 6 g2.txt --kind report --handle art:t6-g2 >/dev/null 2>&1
S="$(record_id A)"
assert_contains_re "first create wrote the record" '^[0-9a-f]{32}$' "$S"
assert_eq "record names the configured branch" "$BR" "$(record_branch A)"
# (a) renamed branch: local check, no network needed.
write_config "$W/A" other-br
out="$(art A create 5 g1.txt --kind mockup --handle art:t5-g3 2>&1)"; rc=$?
assert_exit_nonzero_rc "renamed branch: create dies" "$rc"
assert_contains "renamed branch: names the migrate verb" "ait artifact gitbranch-migrate --from $BR --to other-br" "$out"
assert_contains "renamed branch: names the store id" "$S" "$out"
git -C "$W/A" remote set-url origin /nonexistent/remote.git
cold A
out="$(art A get art:t5-g1 --out "$W/A/x" 2>&1)"; rc=$?
assert_exit_nonzero_rc "renamed branch: get dies" "$rc"
assert_contains "renamed branch: get dies on the LOCAL check (remote unreachable)" "gitbranch-migrate" "$out"
out="$(art A ls 2>&1)"; rc=$?
assert_exit_zero_rc "ls never touches the store (works under a renamed config)" "$rc"
art A rm 6 art:t6-g2 >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "rm never touches the store (works under a renamed config)" "$rc"
git -C "$W/A" remote set-url origin "$W/remote.git"
write_config "$W/A" "$BR"
# (g) warm-cache get with origin unreachable succeeds (no network on a hit).
art A get art:t5-g1 --out "$W/A/warm0" >/dev/null 2>&1   # warm the cache
git -C "$W/A" remote set-url origin /nonexistent/remote.git
art A get art:t5-g1 --out "$W/A/warm" >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "warm-cache get works with origin unreachable" "$rc"
git -C "$W/A" remote set-url origin "$W/remote.git"
# (b) record missing while gitbranch manifests exist.
mv "$W/A/artifacts/gitbranch_store.json" "$W/rec.bak"
cold A
out="$(art A get art:t5-g1 --out "$W/A/x" 2>&1)"; rc=$?
assert_exit_nonzero_rc "missing record + gitbranch manifests: get dies" "$rc"
assert_contains "missing record: names the record path" "gitbranch_store.json" "$out"
mv "$W/rec.bak" "$W/A/artifacts/gitbranch_store.json"
# (c) record present, branch ABSENT (deleted on origin, no local mirror).
saved="$(rtip "$BR")"
git -C "$W/remote.git" update-ref -d "refs/heads/$BR"
git -C "$W/A" update-ref -d "refs/heads/$BR"
cold A
out="$(art A get art:t5-g1 --out "$W/A/x" 2>&1)"; rc=$?
assert_exit_nonzero_rc "present record + ABSENT branch: get dies" "$rc"
assert_contains "ABSENT: says the store is missing" "missing" "$out"
printf 'g4\n' > "$W/A/g4.txt"
out="$(art A create 5 g4.txt --kind mockup --handle art:t5-g4 2>&1)"; rc=$?
assert_exit_nonzero_rc "present record + ABSENT branch: create dies" "$rc"
assert_eq "ABSENT: the store is never re-created empty" "" "$(rtip "$BR")"
# (d) record present, branch holds ANOTHER store.
OTHER="ffffffffffffffffffffffffffffffff"
mk_marked_branch A "$BR" "$OTHER"
git -C "$W/A" update-ref -d "refs/heads/$BR" 2>/dev/null
cold A
out="$(art A get art:t5-g1 --out "$W/A/x" 2>&1)"; rc=$?
assert_exit_nonzero_rc "present record + STORE:other: get dies" "$rc"
assert_contains "STORE:other names the branch's id" "$OTHER" "$out"
assert_contains "STORE:other names the record's id" "$S" "$out"
out="$(art A create 5 g4.txt --kind mockup --handle art:t5-g4 2>&1)"; rc=$?
assert_exit_nonzero_rc "present record + STORE:other: create dies" "$rc"
git -C "$W/remote.git" update-ref "refs/heads/$BR" "$saved"
# (f) a fresh clone with no record adopts the existing store at its first write.
printf 'b1\n' > "$W/B/b1.txt"
art B create 6 b1.txt --kind report --handle art:t6-b1 >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "fresh clone writes to the existing store" "$rc"
assert_eq "fresh clone adopted the existing store id" "$S" "$(record_id B)"

# ── 8. Unmarked existing branch is refused, never adopted (R2) ───────────────
echo "=== 8. occupied ==="
new_world occ
git -C "$W/A" checkout -q -b feature-x
printf 'real work\n' > "$W/A/work.txt"; git -C "$W/A" add work.txt; git -C "$W/A" commit -q -m work
git -C "$W/A" push -q origin feature-x 2>/dev/null
git -C "$W/A" checkout -q main
feat_before="$(rtip feature-x)"
write_config "$W/A" feature-x
printf 'o1\n' > "$W/A/o1.txt"
out="$(art A create 5 o1.txt --kind report --handle art:t5-o1 2>&1)"; rc=$?
assert_exit_nonzero_rc "create onto an unmarked branch dies" "$rc"
assert_contains "OCCUPIED names the branch" "branch 'feature-x' already exists and is not an aitask artifact store" "$out"
assert_eq "the unmarked branch is byte-unchanged" "$feat_before" "$(rtip feature-x)"
write_config "$W/A" "$BR"
art A create 5 o1.txt --kind report --handle art:t5-o1 >/dev/null 2>&1
out="$(art A gitbranch-migrate --from "$BR" --to feature-x 2>&1)"; rc=$?
assert_exit_nonzero_rc "migrate onto an unmarked branch dies" "$rc"
assert_contains "migrate OCCUPIED names the branch" "feature-x" "$out"
assert_eq "migrate left the unmarked branch unchanged" "$feat_before" "$(rtip feature-x)"
assert_exit_nonzero "migrate refusal did not retire the source" \
    git -C "$W/remote.git" cat-file -e "refs/heads/$BR:.ait-artifact-retired"
# Negative control: the same kind of existing branch WITH a valid marker is accepted.
new_world occ2
MARKED="0123456789abcdef0123456789abcdef"
mk_marked_branch A marked-x "$MARKED"
write_config "$W/A" marked-x
printf 'm1\n' > "$W/A/m1.txt"
art A create 5 m1.txt --kind report --handle art:t5-m1 >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "negative control: a marked existing branch is accepted" "$rc"
assert_eq "negative control: its id is adopted into the record" "$MARKED" "$(record_id A)"

# ── 9. No remote: the local ref is the store of record ────────────────────────
echo "=== 9. no remote ==="
new_solo solo
printf '#!/usr/bin/env bash\ntouch "%s/pushed"\nexit 1\n' "$W" > "$W/N/.git/hooks/pre-push"; chmod +x "$W/N/.git/hooks/pre-push"
printf 'solo\n' > "$W/N/s.txt"
art N create 5 s.txt --kind report --handle art:t5-s >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "create works without a remote" "$rc"
assert_eq "the local branch holds the store" "$(git -C "$W/N" rev-parse -q --verify "refs/heads/$BR^{commit}" >/dev/null && echo yes)" "yes"
assert_file_not_exists "no push was attempted" "$W/pushed"
cold N
art N get art:t5-s --out "$W/N/got" >/dev/null 2>&1
assert_eq "round trip without a remote" "solo" "$(cat "$W/N/got" 2>/dev/null)"
rm -f "$W/N/.git/hooks/pre-push"

# ── 10. Local-only store is published by the next write (unchanged tip) ──────
echo "=== 10. local-only publish ==="
new_solo lop
printf 'same bytes\n' > "$W/N/x1.txt"; cp "$W/N/x1.txt" "$W/N/x2.txt"; HX="$(sha "$W/N/x1.txt")"
art N create 5 x1.txt --kind report --handle art:t5-x1 >/dev/null 2>&1
add_origin
art N create 6 x2.txt --kind report --handle art:t6-x2 >/dev/null 2>"$W/err"; rc=$?
assert_exit_zero_rc "write with already-present bytes succeeds" "$rc"
assert_contains "the unchanged local store reached origin" "$(blobpath "$HX")" "$(rblobs "$BR")"
git -C "$W/N" push -q origin main 2>/dev/null
git clone -q "$W/remote.git" "$W/B" 2>/dev/null
git -C "$W/B" config user.email t@t.t; git -C "$W/B" config user.name tester
art B get art:t5-x1 --out "$W/B/g1" >/dev/null 2>&1
art B get art:t6-x2 --out "$W/B/g2" >/dev/null 2>&1
assert_eq "second clone gets the first artifact" "same bytes" "$(cat "$W/B/g1" 2>/dev/null)"
assert_eq "second clone gets the second artifact" "same bytes" "$(cat "$W/B/g2" 2>/dev/null)"
new_solo lopro
printf 'same bytes\n' > "$W/N/x1.txt"; cp "$W/N/x1.txt" "$W/N/x2.txt"
art N create 5 x1.txt --kind report --handle art:t5-x1 >/dev/null 2>&1
add_origin
before="$(commits N)"
chmod -R a-w "$W/remote.git"
art N create 6 x2.txt --kind report --handle art:t6-x2 >/dev/null 2>&1; rc=$?
chmod -R u+w "$W/remote.git"
assert_exit_nonzero_rc "negative control: unpublishable local store fails the write" "$rc"
assert_eq "negative control: no manifest commit" "$before" "$(commits N)"
assert_eq "negative control: origin still has no store" "" "$(rtip "$BR")"
new_solo lopinit
printf 'i1\n' > "$W/N/i1.txt"
art N create 5 i1.txt --kind report --handle art:t5-i1 >/dev/null 2>&1
add_origin
out="$(art N init-store gitbranch 2>&1)"; rc=$?
assert_exit_zero_rc "init-store publishes an unchanged local store" "$rc"
assert_eq "init-store: origin tip == the local store tip" "$(git -C "$W/N" rev-parse "refs/heads/$BR")" "$(rtip "$BR")"

# ── 11. Rollback of a failed create; init-store ───────────────────────────────
echo "=== 11. rollback + init ==="
new_world rb
hook A pre-commit 'git diff --cached --name-only | grep -q "^artifacts/manifests/" && exit 1; exit 0'
printf 'rolled back\n' > "$W/A/r.txt"; HR="$(sha "$W/A/r.txt")"
out="$(art A create 5 r.txt --kind report --handle art:t5-r 2>&1)"; rc=$?
assert_exit_nonzero_rc "create fails when its commit fails" "$rc"
assert_contains "the failure says it rolled back" "rolled back" "$out"
assert_not_contains "rollback removed the txn's blob from the branch" "$(blobpath "$HR")" "$(rblobs "$BR")"
assert_file_not_exists "rollback removed the new record" "$W/A/artifacts/gitbranch_store.json"
assert_not_contains "an ordinary abort reports no retained effects" "RETAINED" "$out"
assert_not_contains "an ordinary abort prints no resume hint" "Resume with:" "$out"
unhook A pre-commit
new_world init
out="$(art A init-store gitbranch 2>&1)"; rc=$?
assert_exit_zero_rc "init-store creates the store" "$rc"
assert_contains "init-store reports Initialized" "Initialized" "$out"
assert_eq "init-store root carries only the marker" ".ait-artifact-store" \
    "$(git -C "$W/remote.git" ls-tree -r --name-only "$BR")"
out="$(art A init-store gitbranch 2>&1)"
assert_contains "init-store is idempotent" "already initialized" "$out"
printf 'after init\n' > "$W/A/ai.txt"
art A create 5 ai.txt --kind report --handle art:t5-ai >/dev/null 2>&1
assert_eq "a later create adopts the initialized store id" "$(rmarker_id "$BR")" "$(record_id A)"

# ── 12. gitbranch-migrate: copy, fence, record, idempotent rerun ──────────────
echo "=== 12. migrate ==="
new_world mig
printf 'm1\n' > "$W/A/m1.txt"; printf 'm2\n' > "$W/A/m2.txt"; printf 'm1b\n' > "$W/A/m1b.txt"
art A create 5 m1.txt --kind report --handle art:t5-m1 >/dev/null 2>&1
art A create 6 m2.txt --kind report --handle art:t6-m2 >/dev/null 2>&1
art A update art:t5-m1 m1b.txt >/dev/null 2>&1
git -C "$W/A" push -q origin main 2>/dev/null
git -C "$W/B" pull -q --no-rebase 2>/dev/null     # B: a clone that will NOT resync
S="$(record_id A)"; old_before="$(rtip "$BR")"; old_blobs="$(rblobs "$BR")"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "migrate succeeds" "$rc"
assert_contains "migrate reports MIGRATED" "MIGRATED:" "$out"
assert_eq "every blob is on the new branch" "$old_blobs" "$(rblobs new-art)"
assert_eq "the new branch carries the SAME store id" "$S" "$(rmarker_id new-art)"
assert_eq "the old branch gained exactly one commit (the fence)" "$old_before" "$(git -C "$W/remote.git" rev-parse "$BR^")"
assert_exit_zero "the old branch is fenced" git -C "$W/remote.git" cat-file -e "refs/heads/$BR:.ait-artifact-retired"
assert_eq "the old branch still holds every blob (readable)" "$old_blobs" "$(rblobs "$BR")"
assert_exit_nonzero "the fence is not copied to the new branch" git -C "$W/remote.git" cat-file -e "refs/heads/new-art:.ait-artifact-retired"
assert_eq "the record now names the new branch" "new-art" "$(record_branch A)"
assert_eq "the record keeps the store id" "$S" "$(record_id A)"
out="$(art A ls 2>&1)"
out="$(art A get art:t5-m1 --out "$W/A/x" 2>&1)"; rc=$?
assert_exit_nonzero_rc "with the config still naming the old branch, the guard refuses" "$rc"
assert_contains "the refusal names the new branch" "new-art" "$out"
write_config "$W/A" new-art
cold A
art A get art:t5-m1 --out "$W/A/gm" >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "after the config change the guard is lifted" "$rc"
assert_eq "migrated bytes resolve from the new branch" "m1b" "$(cat "$W/A/gm" 2>/dev/null)"
o1="$(rtip "$BR")"; n1="$(rtip new-art)"; h1="$(git -C "$W/A" rev-parse HEAD)"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "an identical second invocation succeeds" "$rc"
assert_contains "the second invocation reports ALREADY_MIGRATED" "ALREADY_MIGRATED:" "$out"
assert_eq "second run: old branch unchanged" "$o1" "$(rtip "$BR")"
assert_eq "second run: new branch unchanged" "$n1" "$(rtip new-art)"
assert_eq "second run: no data commit" "$h1" "$(git -C "$W/A" rev-parse HEAD)"
# A clone that never resynced (record + config still on the old branch) is
# refused at the fence when it writes.
printf 'late\n' > "$W/B/late.txt"
out="$(art B create 5 late.txt --kind mockup --handle art:t5-late 2>&1)"; rc=$?
assert_exit_nonzero_rc "a write to the retired branch dies" "$rc"
assert_contains "the fence names the new branch" "new-art" "$out"

# ── 13. migrate target holding another store dies before any write ────────────
echo "=== 13. migrate foreign target ==="
new_world migx
printf 'x\n' > "$W/A/x.txt"
art A create 5 x.txt --kind report --handle art:t5-x >/dev/null 2>&1
S="$(record_id A)"; FOREIGN="eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
mk_marked_branch A other-store "$FOREIGN"
t_before="$(rtip other-store)"; s_before="$(rtip "$BR")"
out="$(art A gitbranch-migrate --from "$BR" --to other-store 2>&1)"; rc=$?
assert_exit_nonzero_rc "migrate onto a foreign store dies" "$rc"
assert_contains "the error names the target's id" "$FOREIGN" "$out"
assert_contains "the error names our id" "$S" "$out"
assert_eq "the target is byte-unchanged" "$t_before" "$(rtip other-store)"
assert_eq "the source is not fenced" "$s_before" "$(rtip "$BR")"

# ── 14. Migration cutover across clones ───────────────────────────────────────
echo "=== 14. cutover ==="
new_world cut
printf 'a1\n' > "$W/A/a1.txt"
art A create 5 a1.txt --kind report --handle art:t5-a1 >/dev/null 2>&1
git -C "$W/A" push -q origin main 2>/dev/null
git -C "$W/B" pull -q --no-rebase 2>/dev/null
printf 'late one\n' > "$W/B/l1.txt"; HL1="$(sha "$W/B/l1.txt")"
hook A pre-push "[ -e '$W/hooked' ] && exit 0; touch '$W/hooked'
( cd '$W/B' && XDG_CACHE_HOME='$W/xdg_B' '$ART' create 6 l1.txt --kind mockup --handle art:t6-l1 ) >/dev/null 2>&1
exit 0"
art A gitbranch-migrate --from "$BR" --to new-art >/dev/null 2>"$W/err"; rc=$?
unhook A pre-push
assert_exit_zero_rc "migrate succeeds with a writer racing the bulk copy" "$rc"
assert_contains "B's racing blob landed on the old branch first" "$(blobpath "$HL1")" "$(rblobs "$BR")"
assert_contains "the catch-up copied B's racing blob to the new branch" "$(blobpath "$HL1")" "$(rblobs new-art)"
fence="$(rtip "$BR")"
printf 'late two\n' > "$W/B/l2.txt"
before="$(commits B)"
out="$(art B create 6 l2.txt --kind mockup --handle art:t6-l2 2>&1)"; rc=$?
assert_exit_nonzero_rc "a late writer still on the old branch dies" "$rc"
assert_contains "the late writer is told where the store went" "new-art" "$out"
assert_eq "the late writer committed no manifest" "$before" "$(commits B)"
assert_eq "the fenced branch did not move" "$fence" "$(rtip "$BR")"
git -C "$W/A" push -q origin main 2>/dev/null
git -C "$W/B" pull -q --no-rebase 2>/dev/null
write_config "$W/B" new-art
cold B
art B get art:t6-l1 --out "$W/B/gl1" >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "after syncing, B reads its racing artifact from the new branch" "$rc"
assert_eq "B's racing artifact bytes" "late one" "$(cat "$W/B/gl1" 2>/dev/null)"
# Negative control: without the fence, the late write lands on X only.
new_world cutneg
printf 'a1\n' > "$W/A/a1.txt"
art A create 5 a1.txt --kind report --handle art:t5-a1 >/dev/null 2>&1
git -C "$W/A" push -q origin main 2>/dev/null
git -C "$W/B" pull -q --no-rebase 2>/dev/null
art A gitbranch-migrate --from "$BR" --to new-art >/dev/null 2>&1
git -C "$W/A" fetch -q origin "+refs/heads/$BR:refs/remotes/origin/$BR" 2>/dev/null
unfence_tree="$( cd "$W/A" && GIT_INDEX_FILE="$W/idx" && export GIT_INDEX_FILE \
    && git read-tree "origin/$BR" && git update-index --force-remove -- .ait-artifact-retired && git write-tree )"
unfence="$(echo unfence | git -C "$W/A" commit-tree "$unfence_tree" -p "origin/$BR")"
git -C "$W/A" push -q origin "$unfence:refs/heads/$BR" 2>/dev/null
printf 'stranded\n' > "$W/B/st.txt"; HST="$(sha "$W/B/st.txt")"
art B create 6 st.txt --kind mockup --handle art:t6-st >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "negative control: with the fence removed the late write succeeds" "$rc"
assert_contains "negative control: the blob is on the old branch" "$(blobpath "$HST")" "$(rblobs "$BR")"
assert_not_contains "negative control: ...and stranded off the new one" "$(blobpath "$HST")" "$(rblobs new-art)"

# ── 15. Migrate preflight: a dirty record refuses before any store mutation ──
echo "=== 15. migrate preflight ==="
new_world pre
printf 'p\n' > "$W/A/p.txt"
art A create 5 p.txt --kind report --handle art:t5-p >/dev/null 2>&1
printf ' \n' >> "$W/A/artifacts/gitbranch_store.json"
s_before="$(rtip "$BR")"; sl_before="$(git -C "$W/A" rev-parse "refs/heads/$BR")"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_nonzero_rc "migrate refuses a dirty record" "$rc"
assert_contains "the refusal names the record" "gitbranch_store.json" "$out"
assert_eq "remote source unchanged" "$s_before" "$(rtip "$BR")"
assert_eq "local source unchanged" "$sl_before" "$(git -C "$W/A" rev-parse "refs/heads/$BR")"
assert_eq "remote target never created" "" "$(rtip new-art)"
assert_exit_nonzero "local target never created" git -C "$W/A" rev-parse -q --verify refs/heads/new-art
assert_exit_nonzero "source not fenced" git -C "$W/remote.git" cat-file -e "refs/heads/$BR:.ait-artifact-retired"

# ── 16. Migrate failure reporting + convergence ───────────────────────────────
echo "=== 16. migrate failures ==="
RESUME="Resume with: ait artifact gitbranch-migrate --from $BR --to new-art"
# (a) the catch-up push fails after the fence landed.
new_world fail_a
printf 'a1\n' > "$W/A/a1.txt"
art A create 5 a1.txt --kind report --handle art:t5-a1 >/dev/null 2>&1
git -C "$W/A" push -q origin main 2>/dev/null
git -C "$W/B" pull -q --no-rebase 2>/dev/null
printf 'racer\n' > "$W/B/rc.txt"; HRC="$(sha "$W/B/rc.txt")"
rec_before="$(cat "$W/A/artifacts/gitbranch_store.json")"
hook A pre-push "n=\$(cat '$W/pushes' 2>/dev/null || echo 0); n=\$((n+1)); echo \$n > '$W/pushes'
if [ \$n -eq 1 ]; then ( cd '$W/B' && XDG_CACHE_HOME='$W/xdg_B' '$ART' create 6 rc.txt --kind mockup --handle art:t6-rc ) >/dev/null 2>&1; fi
[ \$n -eq 3 ] && exit 1
exit 0"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
unhook A pre-push
assert_exit_nonzero_rc "(a) a failed catch-up push fails the migration" "$rc"
assert_contains "(a) report: the new branch advanced" "advanced" "$out"
assert_contains "(a) report: the new branch is INCOMPLETE" "INCOMPLETE" "$out"
assert_contains "(a) report: the old branch is RETIRED" "RETIRED" "$out"
assert_contains "(a) report: exact resume command" "$RESUME" "$out"
assert_not_contains "(a) report never claims a clean rollback" "rolled back every mutation; nothing was committed" "$out"
assert_eq "(a) the record was restored" "$rec_before" "$(cat "$W/A/artifacts/gitbranch_store.json")"
art A ls >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "(a) the attach lock was released" "$rc"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "(a) rerun converges" "$rc"
assert_contains "(a) rerun reports MIGRATED" "MIGRATED:" "$out"
assert_contains "(a) the racer's blob is on the new branch" "$(blobpath "$HRC")" "$(rblobs new-art)"
assert_eq "(a) the record names the new branch" "new-art" "$(record_branch A)"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"
assert_contains "(a) third run is ALREADY_MIGRATED" "ALREADY_MIGRATED:" "$out"
# (b) the final record commit fails (the explicit txn_abort path).
new_world fail_b
printf 'b1\n' > "$W/A/b1.txt"
art A create 5 b1.txt --kind report --handle art:t5-b1 >/dev/null 2>&1
cp "$W/A/artifacts/gitbranch_store.json" "$W/rec.before"
hook A pre-commit 'git diff --cached --name-only | grep -q "gitbranch_store.json" && exit 1; exit 0'
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
unhook A pre-commit
assert_exit_nonzero_rc "(b) a failed record commit fails the migration" "$rc"
assert_contains "(b) report lists the advanced new branch" "branch 'new-art' advanced" "$out"
assert_contains "(b) report lists the retired old branch" "branch '$BR' RETIRED" "$out"
assert_contains "(b) report: exact resume command" "$RESUME" "$out"
assert_eq "(b) the record is restored to its pre-run bytes" "$(cat "$W/rec.before")" "$(cat "$W/A/artifacts/gitbranch_store.json")"
art A ls >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "(b) the attach lock was released" "$rc"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "(b) rerun converges" "$rc"
assert_contains "(b) rerun reports MIGRATED" "MIGRATED:" "$out"
assert_eq "(b) the record names the new branch" "new-art" "$(record_branch A)"
h_b="$(git -C "$W/A" rev-parse HEAD)"; o_b="$(rtip "$BR")"; n_b="$(rtip new-art)"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"
assert_contains "(b) third run is ALREADY_MIGRATED" "ALREADY_MIGRATED:" "$out"
assert_eq "(b) third run: no commit anywhere" "$h_b|$o_b|$n_b" "$(git -C "$W/A" rev-parse HEAD)|$(rtip "$BR")|$(rtip new-art)"

# ── 18. Migrating a store larger than the per-string exec limit ──────────────
echo "=== 18. large store migration ==="
new_world big
printf 'seed\n' > "$W/A/seed.txt"
art A create 5 seed.txt --kind report --handle art:t5-seed >/dev/null 2>&1
mkdir -p "$W/bulk"
for i in $(seq 1 2500); do printf 'bulk blob %d\n' "$i" > "$W/bulk/$i"; done
big_tip="$( cd "$W/A" || exit 1
    git fetch -q origin "+refs/heads/$BR:refs/remotes/origin/$BR" 2>/dev/null
    find "$W/bulk" -type f > "$W/bulk.paths"
    git hash-object -w --stdin-paths < "$W/bulk.paths" > "$W/bulk.oids"
    "$PY" -c 'import hashlib,sys
for p in open(sys.argv[1]).read().split("\n"):
    if p: print(hashlib.sha256(open(p,"rb").read()).hexdigest())' "$W/bulk.paths" > "$W/bulk.hashes"
    paste "$W/bulk.oids" "$W/bulk.hashes" \
        | awk '{ printf "100644 blob %s\tblobs/%s/%s\n", $1, substr($2, 1, 2), substr($2, 3) }' > "$W/bulk.idx"
    export GIT_INDEX_FILE="$W/bigidx"
    git read-tree "origin/$BR" && git update-index --add --index-info < "$W/bulk.idx" \
        && t="$(git write-tree)" && echo bulk | git commit-tree "$t" -p "origin/$BR" )"
git -C "$W/A" push -q origin "$big_tip:refs/heads/$BR" 2>/dev/null
nbig="$(rblobs "$BR" | wc -l | tr -d ' ')"
assert_eq "fixture: 2501 blobs on the store" "2501" "$nbig"
assert_eq "fixture: the name list exceeds the 128 KiB per-string exec limit" "1" \
    "$(( $(rblobs "$BR" | wc -c) > 131072 ? 1 : 0 ))"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "a large store migrates" "$rc"
assert_not_contains "no exec-limit failure" "Argument list too long" "$out"
assert_eq "every blob of the large store is on the new branch" "2501" "$(rblobs new-art | wc -l | tr -d ' ')"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "a large store's rerun succeeds (store-to-store compare)" "$rc"
assert_contains "large store rerun is ALREADY_MIGRATED" "ALREADY_MIGRATED:" "$out"

# ── 19. Confirmed remote absence is never overridden by a stale tracking ref ──
echo "=== 19. stale tracking ref ==="
new_world stale
printf 'same\n' > "$W/A/s1.txt"; cp "$W/A/s1.txt" "$W/A/s2.txt"; HS="$(sha "$W/A/s1.txt")"
art A create 5 s1.txt --kind report --handle art:t5-s1 >/dev/null 2>&1
git -C "$W/remote.git" update-ref -d "refs/heads/$BR"
git -C "$W/A" update-ref -d "refs/heads/$BR"                     # no local mirror
: > "$W/A/.git/refs/remotes/origin/$BR.lock"                       # prune cannot delete
assert_exit_zero "fixture: the stale tracking ref is still readable" \
    git -C "$W/A" rev-parse -q --verify "refs/remotes/origin/$BR"
before="$(commits A)"
out="$(art A create 6 s2.txt --kind report --handle art:t6-s2 2>&1)"; rc=$?
assert_exit_nonzero_rc "absent remote + stale tracking ref: create dies" "$rc"
assert_eq "absent remote + stale tracking ref: no manifest commit" "$before" "$(commits A)"
assert_eq "absent remote + stale tracking ref: origin still has no store" "" "$(rtip "$BR")"
rm -f "$W/A/.git/refs/remotes/origin/$BR.lock"
new_world stale2
printf 'same\n' > "$W/A/s1.txt"; cp "$W/A/s1.txt" "$W/A/s2.txt"; HS="$(sha "$W/A/s1.txt")"
art A create 5 s1.txt --kind report --handle art:t5-s1 >/dev/null 2>&1
git -C "$W/remote.git" update-ref -d "refs/heads/$BR"             # local mirror kept
: > "$W/A/.git/refs/remotes/origin/$BR.lock"
art A create 6 s2.txt --kind report --handle art:t6-s2 >/dev/null 2>&1; rc=$?
rm -f "$W/A/.git/refs/remotes/origin/$BR.lock"
if (( rc == 0 )); then
    assert_contains "a write that succeeds re-published the store with the blob" "$(blobpath "$HS")" "$(rblobs "$BR")"
else
    assert_eq "a write that fails left origin without a store" "" "$(rtip "$BR")"
fi

# ── 20. A wrong-bytes entry is repaired, never accepted on presence ───────────
echo "=== 20. corrupt entry ==="
new_world corrupt
printf 'good bytes\n' > "$W/A/c1.txt"; cp "$W/A/c1.txt" "$W/A/c2.txt"; HG="$(sha "$W/A/c1.txt")"
art A create 5 c1.txt --kind report --handle art:t5-c1 >/dev/null 2>&1
bad_tip="$( cd "$W/A" || exit 1
    git fetch -q origin "+refs/heads/$BR:refs/remotes/origin/$BR" 2>/dev/null
    bad="$(printf 'WRONG\n' | git hash-object -w --stdin)"
    export GIT_INDEX_FILE="$W/badidx"
    git read-tree "origin/$BR" && printf '100644 blob %s\t%s\n' "$bad" "$(blobpath "$HG")" | git update-index --index-info \
        && t="$(git write-tree)" && echo corrupt | git commit-tree "$t" -p "origin/$BR" )"
git -C "$W/A" push -q origin "$bad_tip:refs/heads/$BR" 2>/dev/null
cold A
art A get art:t5-c1 --out "$W/A/pre" >/dev/null 2>&1; rc=$?
assert_exit_nonzero_rc "fixture: the corrupt entry is unreadable before repair" "$rc"
art A create 6 c2.txt --kind report --handle art:t6-c2 >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "a write of the correct bytes succeeds" "$rc"
assert_eq "the write repaired the entry to the correct object" \
    "$(git -C "$W/A" hash-object "$W/A/c1.txt")" "$(git -C "$W/remote.git" rev-parse "$BR:$(blobpath "$HG")")"
cold A
art A get art:t5-c1 --out "$W/A/post" >/dev/null 2>&1
assert_eq "after repair a cold get returns the right bytes" "good bytes" "$(cat "$W/A/post" 2>/dev/null)"

# ── 21. A push applied by origin whose acknowledgement is lost: UNKNOWN ───────
echo "=== 21. unknown push outcome ==="
new_world unknown
printf 'u1\n' > "$W/A/u1.txt"
art A create 5 u1.txt --kind report --handle art:t5-u1 >/dev/null 2>&1
rec_before="$(cat "$W/A/artifacts/gitbranch_store.json")"
cat > "$W/remote.git/hooks/reference-transaction" <<EOF
#!/usr/bin/env bash
[ "\$1" = committed ] || exit 0
[ -e "$W/rt_fired" ] && exit 0
while read -r _old new ref; do
    if [ "\$ref" = "refs/heads/$BR" ] && git cat-file -e "\$new:.ait-artifact-retired" 2>/dev/null; then
        touch "$W/rt_fired"; mv "$W/remote.git" "$W/remote.away"; kill -9 \$PPID; exit 0
    fi
done
exit 0
EOF
chmod +x "$W/remote.git/hooks/reference-transaction"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
[[ -d "$W/remote.away" ]] && mv "$W/remote.away" "$W/remote.git"
rm -f "$W/remote.git/hooks/reference-transaction"
assert_file_exists "fixture: the fence push reached origin before the fault" "$W/rt_fired"
assert_exit_zero "fixture: origin really applied the fence" \
    git -C "$W/remote.git" cat-file -e "refs/heads/$BR:.ait-artifact-retired"
assert_exit_nonzero_rc "an unacknowledged fence push fails the run" "$rc"
assert_contains "the outcome is reported as UNKNOWN" "UNKNOWN" "$out"
assert_contains "the report retains the possibly-applied fence" "MAY have been RETIRED" "$out"
assert_not_contains "never claims nothing was published for the unknown push" "nothing was published" "$out"
assert_contains "the report keeps the resume command" "Resume with: ait artifact gitbranch-migrate --from $BR --to new-art" "$out"
assert_eq "the record was restored" "$rec_before" "$(cat "$W/A/artifacts/gitbranch_store.json")"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "rerun after an unknown outcome converges" "$rc"
assert_contains "rerun after an unknown outcome reports MIGRATED" "MIGRATED:" "$out"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"
assert_contains "third run after an unknown outcome is ALREADY_MIGRATED" "ALREADY_MIGRATED:" "$out"

# ── 22. A verification that cannot complete never moves the record ───────────
echo "=== 22. verify failure ==="
new_world vfail
printf 'v1\n' > "$W/A/v1.txt"
art A create 5 v1.txt --kind report --handle art:t5-v1 >/dev/null 2>&1
mkdir -p "$W/fakebin"; printf '#!/usr/bin/env bash\nexit 2\n' > "$W/fakebin/comm"; chmod +x "$W/fakebin/comm"
h_before="$(git -C "$W/A" rev-parse HEAD)"
out="$( cd "$W/A" && PATH="$W/fakebin:$PATH" XDG_CACHE_HOME="$W/xdg_A" "$ART" gitbranch-migrate --from "$BR" --to new-art 2>&1 )"; rc=$?
assert_exit_nonzero_rc "a failed completeness comparison fails the migration" "$rc"
assert_not_contains "a failed comparison never reports MIGRATED" "MIGRATED:" "$out"
assert_contains "the failure says verification could not complete" "could not verify" "$out"
assert_eq "the record still names the old branch" "$BR" "$(record_branch A)"
assert_eq "no record commit" "$h_before" "$(git -C "$W/A" rev-parse HEAD)"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "with a working comparison the rerun converges" "$rc"
assert_eq "the record now names the new branch" "new-art" "$(record_branch A)"

# ── 23. Lost ack + another writer on top: the applied copy is still reported ─
echo "=== 23. lost ack, descendant tip ==="
new_world desc
printf 'd1\n' > "$W/A/d1.txt"
art A create 5 d1.txt --kind report --handle art:t5-d1 >/dev/null 2>&1
printf 'B appended\n' > "$W/bapp"; HBA="$(sha "$W/bapp")"; HBAP="$(blobpath "$HBA")"
# Origin applies A's bulk copy, lets clone B append on top of it, then kills
# A's receive-pack: A sees a failed push while origin has moved PAST its commit.
{
    printf '#!/usr/bin/env bash\n%s\nunset GIT_ALTERNATE_OBJECT_DIRECTORIES\n' "$HOOK_PRELUDE"
    printf '[ "$1" = committed ] || exit 0\n'
    printf '[ -e %q ] && exit 0\n' "$W/dt_fired"
    printf 'while read -r _old _new ref; do\n'
    printf '  if [ "$ref" = refs/heads/new-art ]; then\n'
    printf '    touch %q\n' "$W/dt_fired"
    printf '    ( cd %q || exit 1\n' "$W/B"
    printf '      git fetch -q origin +refs/heads/new-art:refs/remotes/origin/new-art || exit 1\n'
    printf '      o="$(git hash-object -w %q)" || exit 1\n' "$W/bapp"
    printf '      export GIT_INDEX_FILE=%q\n' "$W/dtidx"
    printf '      git read-tree origin/new-art || exit 1\n'
    printf '      printf "100644 blob %%s\\t%%s\\n" "$o" %q | git update-index --index-info || exit 1\n' "$HBAP"
    printf '      t="$(git write-tree)" || exit 1\n'
    printf '      c="$(echo appended | git commit-tree "$t" -p origin/new-art)" || exit 1\n'
    printf '      git push -q origin "$c:refs/heads/new-art" ) >/dev/null 2>&1\n'
    printf '    kill -9 $PPID; exit 0\n'
    printf '  fi\n'
    printf 'done\nexit 0\n'
} > "$W/remote.git/hooks/reference-transaction"
chmod +x "$W/remote.git/hooks/reference-transaction"
hook A pre-push "n=\$(cat '$W/pushes' 2>/dev/null || echo 0); n=\$((n+1)); echo \$n > '$W/pushes'
[ \$n -eq 2 ] && exit 1
exit 0"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
rm -f "$W/remote.git/hooks/reference-transaction"; unhook A pre-push
assert_file_exists "fixture: the bulk copy reached origin before the fault" "$W/dt_fired"
assert_eq "fixture: another writer's commit sits on top of the copy" "2" \
    "$(git -C "$W/remote.git" rev-list --count new-art 2>/dev/null)"
assert_contains "fixture: the other writer's blob is on the destination" "$HBAP" "$(rblobs new-art)"
assert_exit_nonzero_rc "a failed fence after an applied-but-unacknowledged copy fails the run" "$rc"
assert_contains "the applied copy is reported as retained" "branch 'new-art' advanced" "$out"
assert_not_contains "never claims a clean rollback" "rolled back every mutation; nothing was committed" "$out"
assert_contains "the resume command is printed" "Resume with: ait artifact gitbranch-migrate --from $BR --to new-art" "$out"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "rerun converges" "$rc"
assert_contains "rerun reports MIGRATED" "MIGRATED:" "$out"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"
assert_contains "third run is ALREADY_MIGRATED" "ALREADY_MIGRATED:" "$out"

# write_lost_ack_hook -- origin hook for $W: when A's push to new-art commits,
# clone B appends a blob on top and A's receive-pack is killed, so A sees a
# failed push while origin has moved PAST its commit.
write_lost_ack_hook() {
    {
        printf '#!/usr/bin/env bash\n%s\nunset GIT_ALTERNATE_OBJECT_DIRECTORIES\n' "$HOOK_PRELUDE"
        printf '[ "$1" = committed ] || exit 0\n'
        printf '[ -e %q ] && exit 0\n' "$W/dt_fired"
        printf 'while read -r _old _new ref; do\n'
        printf '  if [ "$ref" = refs/heads/new-art ]; then\n'
        printf '    touch %q\n' "$W/dt_fired"
        printf '    ( cd %q || exit 1\n' "$W/B"
        printf '      git fetch -q origin +refs/heads/new-art:refs/remotes/origin/new-art || exit 1\n'
        printf '      o="$(git hash-object -w %q)" || exit 1\n' "$W/bapp"
        printf '      export GIT_INDEX_FILE=%q\n' "$W/dtidx"
        printf '      git read-tree origin/new-art || exit 1\n'
        printf '      printf "100644 blob %%s\\t%%s\\n" "$o" %q | git update-index --index-info || exit 1\n' "$HBAP"
        printf '      t="$(git write-tree)" || exit 1\n'
        printf '      c="$(echo appended | git commit-tree "$t" -p origin/new-art)" || exit 1\n'
        printf '      git push -q origin "$c:refs/heads/new-art" ) >/dev/null 2>&1\n'
        printf '    kill -9 $PPID; exit 0\n'
        printf '  fi\n'
        printf 'done\nexit 0\n'
    } > "$W/remote.git/hooks/reference-transaction"
    chmod +x "$W/remote.git/hooks/reference-transaction"
}

# mk_lost_ack_world <name> -- a world armed with that fault; A's pre-push also
# rejects A's 2nd push (the fence), as in section 23.
mk_lost_ack_world() {
    new_world "$1"
    printf 'd1\n' > "$W/A/d1.txt"
    art A create 5 d1.txt --kind report --handle art:t5-d1 >/dev/null 2>&1
    printf 'B appended\n' > "$W/bapp"; HBAP="$(blobpath "$(sha "$W/bapp")")"
    write_lost_ack_hook
    hook A pre-push "n=\$(cat '$W/pushes' 2>/dev/null || echo 0); n=\$((n+1)); echo \$n > '$W/pushes'
[ \$n -eq 2 ] && exit 1
exit 0"
}

# ── 24. Lost ack, then the RETRY's refresh fails: still UNKNOWN, still retained ─
echo "=== 24. lost ack + failed retry refresh ==="
mk_lost_ack_world lost_refresh
# A client-side hook aborts A's tracking-ref update for new-art once origin has
# been faulted, so the retry's fetch fails while ls-remote keeps working.
{
    printf '#!/usr/bin/env bash\n[ "$1" = prepared ] || exit 0\n'
    printf '[ -e %q ] || exit 0\n' "$W/dt_fired"
    printf 'while read -r _o _n ref; do [ "$ref" = refs/remotes/origin/new-art ] && exit 1; done\nexit 0\n'
} > "$W/A/.git/hooks/reference-transaction"
chmod +x "$W/A/.git/hooks/reference-transaction"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
rm -f "$W/remote.git/hooks/reference-transaction" "$W/A/.git/hooks/reference-transaction"; unhook A pre-push
assert_file_exists "fixture: the copy landed and the retry ran" "$W/dt_fired"
assert_contains "fixture: the destination holds the other writer's blob" "$HBAP" "$(rblobs new-art)"
assert_exit_nonzero_rc "a failed retry refresh fails the run" "$rc"
assert_contains "the failed retry is reported as UNKNOWN" "UNKNOWN" "$out"
assert_contains "the possibly-applied copy is retained" "branch 'new-art' MAY have advanced" "$out"
assert_not_contains "never a clean-rollback claim" "rolled back every mutation; nothing was committed" "$out"
assert_contains "resume guidance survives" "Resume with: ait artifact gitbranch-migrate --from $BR --to new-art" "$out"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "rerun converges after a failed retry refresh" "$rc"
assert_contains "rerun reports MIGRATED" "MIGRATED:" "$out"

# ── 25. Lost ack, then the ancestry probe ERRORS: never read as "not landed" ──
echo "=== 25. lost ack + ancestry probe error ==="
mk_lost_ack_world lost_ancestry
REAL_GIT="$(command -v git)"
mkdir -p "$W/gitshim"
printf '#!/usr/bin/env bash\n[ "$1" = merge-base ] && exit 128\nexec %q "$@"\n' "$REAL_GIT" > "$W/gitshim/git"
chmod +x "$W/gitshim/git"
out="$( cd "$W/A" && PATH="$W/gitshim:$PATH" XDG_CACHE_HOME="$W/xdg_A" "$ART" gitbranch-migrate --from "$BR" --to new-art 2>&1 )"; rc=$?
rm -f "$W/remote.git/hooks/reference-transaction"; unhook A pre-push
assert_file_exists "fixture: the copy landed before the probe" "$W/dt_fired"
assert_exit_nonzero_rc "an ancestry probe error fails the run" "$rc"
assert_contains "the probe error is reported as UNKNOWN" "UNKNOWN" "$out"
assert_contains "the possibly-applied copy is retained" "branch 'new-art' MAY have advanced" "$out"
assert_not_contains "never a clean-rollback claim" "rolled back every mutation; nothing was committed" "$out"
out="$(art A gitbranch-migrate --from "$BR" --to new-art 2>&1)"; rc=$?
assert_exit_zero_rc "rerun converges after an ancestry probe error" "$rc"
assert_contains "rerun reports MIGRATED" "MIGRATED:" "$out"

# ── 17. txn report: defaults unchanged, retained effects worded truthfully ───
echo "=== 17. txn report ==="
rep="$( L="$PROJECT_DIR/.aitask-scripts/lib"; source "$L/terminal_compat.sh"; source "$L/txn_snapshot.sh"
        txn_rollback_report 1 "ctx" 2>&1 )"
exp="$( L="$PROJECT_DIR/.aitask-scripts/lib"; source "$L/terminal_compat.sh"
        warn "ctx — rolled back every mutation; nothing was committed" 2>&1 )"
assert_eq "empty retained set: the report is byte-identical to before" "$exp" "$rep"
rep="$( L="$PROJECT_DIR/.aitask-scripts/lib"; source "$L/terminal_compat.sh"; source "$L/txn_snapshot.sh"
        txn_retain "branch 'y' advanced"; txn_set_resume_hint "do it again"
        txn_rollback_report 1 "ctx" 2>&1 )"
assert_contains "retained: lists the effect" "branch 'y' advanced" "$rep"
assert_contains "retained: says RETAINED" "RETAINED" "$rep"
assert_contains "retained: prints the resume hint" "Resume with: do it again" "$rep"
assert_not_contains "retained: no unqualified clean-rollback claim" "rolled back every mutation; nothing was committed" "$rep"

echo ""
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
