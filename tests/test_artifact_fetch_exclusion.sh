#!/usr/bin/env bash
# test_artifact_fetch_exclusion.sh - the routine-fetch exclusion for the
# gitbranch artifact store (t2099): `ait artifact fetch-exclusion`, the store
# record's `retired` list, dedicated mode, the lock, and the CLI/setup/init_data
# call sites. The `ait sync` guard has its own file (test_sync_fetch_exclusion.sh).
#
# Every remote is reached through a file:// URL: a plain-path clone hard-links
# objects and would hide whether a fetch downloaded the store.
#
# Fault injection and pauses use a PATH `git` shim that lives only in this test
# (AFX_FAIL_MATCH: fail one exact invocation without running it; AFX_MUTATE_MATCH:
# run it, then eval AFX_MUTATE_CMD; AFX_PAUSE_MATCH:
# run it, then block on a FIFO). No test hook exists in production code.
#
# Fixtures are legacy-mode repos (task data on main), except the init_data case.
# Assertions run in the main shell, never in a subshell.
set -uo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/git_config_isolation.sh"
sync_isolate_git_config
PASS=0; FAIL=0; TOTAL=0

ART="$PROJECT_DIR/.aitask-scripts/aitask_artifact.sh"
REAL_GIT="$(command -v git)"
BR="aitask-artifacts"

TMP="$(mktemp -d)"
trap 'chmod -R u+w "$TMP" 2>/dev/null; rm -rf "$TMP"' EXIT

# ── The git shim ──────────────────────────────────────────────────────────────
mkdir -p "$TMP/shim"
cat > "$TMP/shim/git" <<EOF
#!/usr/bin/env bash
args="\$*"
if [[ -n "\${AFX_FAIL_MATCH:-}" && "\$args" == "\$AFX_FAIL_MATCH" ]]; then
    exit 1
fi
if [[ -n "\${AFX_VERSION:-}" && "\$args" == "--version" ]]; then
    echo "git version \$AFX_VERSION"; exit 0
fi
if [[ -n "\${AFX_MUTATE_MATCH:-}" && "\$args" == "\$AFX_MUTATE_MATCH" ]]; then
    rc=0; "$REAL_GIT" "\$@" || rc=\$?
    eval "\$AFX_MUTATE_CMD"
    exit \$rc
fi
if [[ -n "\${AFX_PAUSE_MATCH:-}" && "\$args" == "\$AFX_PAUSE_MATCH" ]]; then
    rc=0; "$REAL_GIT" "\$@" || rc=\$?
    : > "\$AFX_PAUSE_MARK"
    read -r _ < "\$AFX_PAUSE_FIFO"
    exit \$rc
fi
exec "$REAL_GIT" "\$@"
EOF
chmod +x "$TMP/shim/git"

# ── Fixture helpers ───────────────────────────────────────────────────────────

# cfg <repo> <branch> [extra gitbranch yaml lines...]
cfg() {
    local repo="$1" b="$2"; shift 2
    {
        printf 'artifacts:\n  default_backend: gitbranch\n  backends:\n    gitbranch:\n      branch: %s\n' "$b"
        local l; for l in "$@"; do printf '      %s\n' "$l"; done
    } > "$repo/aitasks/metadata/project_config.yaml"
}

mk_task() {
    printf -- '---\npriority: medium\nstatus: Implementing\nupdated_at: 2026-01-01 00:00\n---\n\nTask %s.\n' "$2" \
        > "$1/aitasks/$2.md"
}

# new_world <name> -- bare origin (file://) seeded with main; clones A and B.
new_world() {
    W="$TMP/$1"; mkdir -p "$W/seed/aitasks/metadata"
    git init -q --bare "$W/remote.git"
    git -C "$W/remote.git" symbolic-ref HEAD refs/heads/main
    git -C "$W/seed" init -q -b main
    git -C "$W/seed" config user.email t@t.t; git -C "$W/seed" config user.name tester
    mk_task "$W/seed" t5_demo; mk_task "$W/seed" t6_other
    cfg "$W/seed" "$BR"
    git -C "$W/seed" add -A; git -C "$W/seed" commit -q -m init
    git -C "$W/seed" push -q "file://$W/remote.git" main 2>/dev/null
    local c
    for c in A B; do clone_into "$c"; done
}

clone_into() {  # clone_into <name> [extra clone args...]
    local c="$1"; shift
    git clone -q "$@" "file://$W/remote.git" "$W/$c" 2>/dev/null
    git -C "$W/$c" config user.email t@t.t; git -C "$W/$c" config user.name tester
}

art() { local c="$1"; shift; ( cd "$W/$c" && XDG_CACHE_HOME="$W/xdg_$c" "$ART" "$@" ); }
afx() { local c="$1"; shift; ( cd "$W/$c" && "$ART" fetch-exclusion "$@" ); }
afx_shim() { local c="$1"; shift; ( cd "$W/$c" && PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion "$@" ); }

fetchvals() { git -C "$W/$1" config --get-all "remote.$2.fetch" 2>/dev/null || true; }
cfgval() { git -C "$W/$1" config --get "$2" 2>/dev/null || true; }
rtip() { git -C "$W/${2:-remote.git}" rev-parse -q --verify "refs/heads/$1" 2>/dev/null || true; }
has_obj() { git -C "$W/$1" cat-file -e "$2" 2>/dev/null && echo yes || echo no; }
tref() { git -C "$W/$1" rev-parse -q --verify "$2" 2>/dev/null || echo absent; }
objcount() { git -C "$W/$1" count-objects -v | awk '/^(count|in-pack):/ {s+=$2} END {print s}'; }
aitkeys() { git -C "$W/$1" config --get-regexp "^remote\\.$2\\.aitask(saved|dedicated)" 2>/dev/null || true; }
# release_pause -- unblock the paused shim. Bounded: when a regression stops the
# paused process from ever reaching its pause, nobody reads the FIFO, and an
# unbounded write would hang the suite instead of failing it.
release_pause() { timeout 5 bash -c 'echo go > "$1"' _ "$TMP/fifo" 2>/dev/null || true; }

# store_write <clone> <file> <handle> -- create or update an artifact on the store.
store_write() {
    local c="$1" f="$2" h="$3"
    printf 'payload %s %s\n' "$h" "$RANDOM$RANDOM" > "$W/$c/$f"
    if art "$c" versions "$h" >/dev/null 2>&1; then
        art "$c" update "$h" "$f" >/dev/null 2>&1
    else
        art "$c" create 5 "$f" --kind report --handle "$h" >/dev/null 2>&1
    fi
}

# ═════════════════════════════════════════════════════════════════════════════
echo "--- 1. Shared-mode mechanics ---"
new_world shared
git -C "$W/B" remote add upstream "file://$W/remote.git"
git -C "$W/B" config --add remote.upstream.fetch '+refs/tags/*:refs/tags/*'
git -C "$W/B" config --add remote.upstream.fetch '^refs/heads/aitask-artifacts'   # the user's own
before_origin="$(fetchvals B origin)"
before_up="$(fetchvals B upstream)"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_zero_rc "shared: apply succeeds" "$rc"
assert_contains "shared: origin excluded" "EXCLUDED:origin:$BR" "$out"
assert_not_contains "shared: a user's identical entry is not re-added" "EXCLUDED:upstream:$BR" "$out"
assert_eq "shared: origin's positive mapping is preserved byte for byte" "$before_origin" \
    "$(fetchvals B origin | grep -v '^\^')"
assert_eq "shared: origin gains exactly the negative refspec" "^refs/heads/$BR" "$(fetchvals B origin | grep '^\^')"
assert_eq "shared: upstream's values are untouched" "$before_up" "$(fetchvals B upstream)"
assert_eq "shared: ownership recorded on origin" "$BR" "$(cfgval B remote.origin.aitaskExclude)"
assert_eq "shared: the user's entry is never claimed" "" "$(cfgval B remote.upstream.aitaskExclude)"
cp "$W/B/.git/config" "$TMP/config.before"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_zero_rc "shared: re-run succeeds" "$rc"
assert_contains "shared: re-run is a no-op" "FETCH_EXCLUSION:UNCHANGED" "$out"
assert_eq "shared: re-run leaves .git/config byte-identical" "same" \
    "$(cmp -s "$TMP/config.before" "$W/B/.git/config" && echo same || echo differs)"

echo "--- 1b. Stale-config correction releases only what we added ---"
cfg "$W/B" typo-branch
afx B apply >/dev/null 2>&1
assert_contains "correction: the typo branch was excluded" "^refs/heads/typo-branch" "$(fetchvals B origin)"
git -C "$W/B" config --add remote.upstream.fetch '^refs/heads/typo-branch'   # user adds the same later
cfg "$W/B" "$BR"
out="$(afx B apply 2>&1)"
assert_contains "correction: the stale owned entry is RELEASED" "RELEASED:origin:typo-branch" "$out"
assert_not_contains "correction: origin no longer excludes it" "typo-branch" "$(fetchvals B origin)"
assert_contains "correction: the user's own identical entry on upstream survives" "^refs/heads/typo-branch" "$(fetchvals B upstream)"
assert_contains "correction: the current branch stays excluded" "^refs/heads/$BR" "$(fetchvals B origin)"

echo "--- 2. Not configured ---"
printf 'artifacts:\n  default_backend: local\n' > "$W/A/aitasks/metadata/project_config.yaml"
cp "$W/A/.git/config" "$TMP/config.a"
out="$(afx A apply 2>&1)"; rc=$?
assert_exit_zero_rc "not configured: exit 0" "$rc"
assert_contains "not configured: token" "FETCH_EXCLUSION:NOT_CONFIGURED" "$out"
assert_eq "not configured: config untouched" "same" "$(cmp -s "$TMP/config.a" "$W/A/.git/config" && echo same || echo differs)"
cfg "$W/A" "$BR"

echo "--- 3. Old git (< 2.29) ---"
cp "$W/A/.git/config" "$TMP/config.a"
out="$( cd "$W/A" && AFX_VERSION=2.28.0 PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply 2>"$TMP/err" )"; rc=$?
assert_exit_zero_rc "old git: exit 0" "$rc"
assert_contains "old git: token" "FETCH_EXCLUSION:UNSUPPORTED_GIT:2.28.0" "$out"
assert_eq "old git: exactly one warning" "1" "$(grep -c 'no negative refspecs' "$TMP/err")"
assert_eq "old git: config untouched" "same" "$(cmp -s "$TMP/config.a" "$W/A/.git/config" && echo same || echo differs)"

echo "--- 4. Full clone: routine fetches skip the store; artifact get still works ---"
new_world full
afx B apply >/dev/null 2>&1
store_write A a.txt art:t5-a
git -C "$W/A" push -q origin main 2>/dev/null
tip="$(rtip "$BR")"
assert_eq "full: the store exists on origin" "yes" "$([[ -n "$tip" ]] && echo yes || echo no)"
git -C "$W/B" fetch -q origin 2>/dev/null
git -C "$W/B" fetch -q --all --prune 2>/dev/null
assert_eq "full: no store tracking ref after fetch / fetch --all --prune" "absent" "$(tref B "refs/remotes/origin/$BR")"
assert_eq "full: no store objects fetched" "no" "$(has_obj B "$tip")"
git -C "$W/B" merge -q --ff-only origin/main 2>/dev/null
art B get art:t5-a --out "$W/B/got.txt" >/dev/null 2>&1; rc=$?
assert_exit_zero_rc "full: artifact get of an uncached version works (explicit refspec)" "$rc"
assert_eq "full: the bytes round-trip" "$(cat "$W/A/a.txt")" "$(cat "$W/B/got.txt" 2>/dev/null)"
c0="$(objcount B)"
store_write A a.txt art:t5-a
git -C "$W/B" fetch -q origin 2>/dev/null; git -C "$W/B" fetch -q --all --prune 2>/dev/null
assert_eq "full: count-objects unchanged when only the store advanced" "$c0" "$(objcount B)"
assert_eq "full: the new store tip was not fetched" "no" "$(has_obj B "$(rtip "$BR")")"

echo "--- 5. Old clone already holding the store ref ---"
new_world old
store_write A o.txt art:t5-o
git -C "$W/B" fetch -q origin 2>/dev/null
old="$(tref B "refs/remotes/origin/$BR")"
assert_eq "old clone: it downloaded the store before the exclusion" "$(rtip "$BR")" "$old"
afx B apply >/dev/null 2>&1
store_write A o.txt art:t5-o
new="$(rtip "$BR")"
git -C "$W/B" fetch -q origin 2>/dev/null; git -C "$W/B" fetch -q --all --prune 2>/dev/null
now="$(tref B "refs/remotes/origin/$BR")"
assert_eq "old clone: the stale ref is not advanced" "yes" "$([[ "$now" == "$old" || "$now" == absent ]] && echo yes || echo no)"
assert_eq "old clone: the new tip was not fetched" "no" "$(has_obj B "$new")"

echo "--- 6. Mixed code-and-artifact named remote ---"
new_world mixed
git init -q --bare "$W/up.git"
store_write A m.txt art:t5-m
git -C "$W/A" push -q "file://$W/up.git" main "$BR:$BR" 2>/dev/null
git -C "$W/B" remote add upstream "file://$W/up.git"
afx B apply >/dev/null 2>&1
git -C "$W/B" fetch -q --all --prune 2>/dev/null
up0="$(tref B refs/remotes/upstream/main)"
git -C "$W/A" commit -q --allow-empty -m "new code"
store_write A m.txt art:t5-m
git -C "$W/A" push -q "file://$W/up.git" main "$BR:$BR" 2>/dev/null
git -C "$W/B" fetch -q --all --prune 2>/dev/null
assert_eq "mixed: upstream/main advanced" "$(git -C "$W/up.git" rev-parse main)" "$(tref B refs/remotes/upstream/main)"
assert_eq "mixed: upstream/main really moved" "yes" "$([[ "$up0" != "$(tref B refs/remotes/upstream/main)" ]] && echo yes || echo no)"
assert_eq "mixed: no upstream store ref" "absent" "$(tref B "refs/remotes/upstream/$BR")"
assert_eq "mixed: no store objects" "no" "$(has_obj B "$(rtip "$BR" up.git)")"

echo "--- 7. Migration, rename, retired list, drop-retired ---"
new_world mig
store_write A x.txt art:t5-x
afx A apply >/dev/null 2>&1
out="$(art A gitbranch-migrate --from "$BR" --to store-b 2>&1)"; rc=$?
assert_exit_zero_rc "migrate: succeeds" "$rc"
assert_contains "migrate: names the migration" "MIGRATED:" "$out"
rec="$(cat "$W/A/artifacts/gitbranch_store.json")"
assert_contains "migrate: the record names the new branch" '"branch": "store-b"' "$rec"
assert_contains "migrate: the record lists the retired predecessor" '"retired": ["'"$BR"'"]' "$rec"
assert_contains "migrate: the new branch is excluded at once" "^refs/heads/store-b" "$(fetchvals A origin)"
assert_contains "migrate: the retired branch stays excluded" "^refs/heads/$BR" "$(fetchvals A origin)"
cfg "$W/A" store-b
git -C "$W/A" add -A; git -C "$W/A" commit -q -m "config to store-b"
out="$(afx A apply 2>&1)"
assert_not_contains "migrate: a config update after migration releases nothing" "RELEASED" "$out"
git -C "$W/A" push -q origin main 2>/dev/null

echo "--- 7b. Another clone and a fresh clone learn the retirement from the record ---"
git -C "$W/B" pull -q origin main 2>/dev/null
out="$(afx B apply 2>&1)"
assert_contains "cross-clone: B excludes the retired branch" "EXCLUDED:origin:$BR" "$out"
assert_contains "cross-clone: B excludes the new branch" "EXCLUDED:origin:store-b" "$out"
store_write A x.txt art:t5-x
git -C "$W/B" fetch -q --all --prune 2>/dev/null
assert_eq "cross-clone: B fetched no store-b objects" "no" "$(has_obj B "$(rtip store-b)")"
assert_eq "cross-clone: B fetched no retired-store objects" "no" "$(has_obj B "$(rtip "$BR")")"
clone_into Z --single-branch -b main
cp -r "$PROJECT_DIR/.aitask-scripts" "$W/Z/.aitask-scripts"
( source "$W/Z/.aitask-scripts/aitask_setup.sh" --source-only && setup_artifact_fetch_exclusion ) >/dev/null 2>&1
assert_contains "fresh clone + setup: retired branch excluded" "^refs/heads/$BR" "$(fetchvals Z origin)"
assert_contains "fresh clone + setup: store branch excluded" "^refs/heads/store-b" "$(fetchvals Z origin)"
assert_eq "fresh clone: the real repository's config was not touched" "" \
    "$(git -C "$PROJECT_DIR" config --get-all remote.origin.aitaskExclude 2>/dev/null)"
out="$( source "$W/Z/.aitask-scripts/aitask_setup.sh" --source-only && setup_artifact_fetch_exclusion 2>&1 )"
assert_contains "setup re-run is a no-op" "already in place" "$out"

echo "--- 7c. Config changed with no migration: the record term keeps the store ---"
cfg "$W/B" store-z
out="$(afx B apply 2>&1)"
assert_contains "no-migration: the new config branch is excluded" "EXCLUDED:origin:store-z" "$out"
assert_not_contains "no-migration: the recorded store is not released" "RELEASED:origin:store-b" "$out"
cfg "$W/B" store-b
afx B apply >/dev/null 2>&1

echo "--- 7d. drop-retired (t2104's release hook) ---"
out="$(afx A drop-retired store-b 2>&1)"; rc=$?
assert_exit_nonzero_rc "drop-retired: the current store branch refuses" "$rc"
out="$(afx A drop-retired "$BR" 2>&1)"; rc=$?
assert_exit_zero_rc "drop-retired: succeeds" "$rc"
assert_contains "drop-retired: releases the exclusion" "RELEASED:origin:$BR" "$out"
assert_not_contains "drop-retired: the record no longer lists it" "retired" "$(cat "$W/A/artifacts/gitbranch_store.json")"
assert_eq "drop-retired: committed" "" "$(git -C "$W/A" status --porcelain -- artifacts/gitbranch_store.json)"
assert_contains "drop-retired: store-b stays excluded" "^refs/heads/store-b" "$(fetchvals A origin)"

echo "--- 7e. Backfill and fail-closed record validation ---"
printf '{"store_id": "%s", "branch": "store-b"}\n' "$(sed -n 's/.*"store_id": "\([0-9a-f]*\)".*/\1/p' "$W/A/artifacts/gitbranch_store.json")" \
    > "$W/A/artifacts/gitbranch_store.json"
git -C "$W/A" commit -q -am "record without retired" 2>/dev/null
art A gitbranch-migrate --from "$BR" --to store-b >/dev/null 2>&1
assert_contains "backfill: re-running the migration re-adds the predecessor" '"retired": ["'"$BR"'"]' \
    "$(cat "$W/A/artifacts/gitbranch_store.json")"
sid="$(sed -n 's/.*"store_id": "\([0-9a-f]*\)".*/\1/p' "$W/A/artifacts/gitbranch_store.json")"
for bad in '"retired": "x"' '"retired": ["../evil"]'; do
    printf '{"store_id": "%s", "branch": "store-b", %s}\n' "$sid" "$bad" > "$W/A/artifacts/gitbranch_store.json"
    out="$(afx A apply 2>&1)"; rc=$?
    assert_exit_nonzero_rc "malformed retired ($bad): apply fails closed" "$rc"
    assert_contains "malformed retired ($bad): names the record" "malformed" "$out"
done
git -C "$W/A" checkout -q -- artifacts/gitbranch_store.json

echo "--- 8. Dedicated mode ---"
new_world ded
git init -q --bare "$W/s.git"
setup_store_remote() {  # setup_store_remote <clone> <name> <skip: unset|true|false>
    git -C "$W/$1" remote add "$2" "file://$W/s.git"
    git -C "$W/$1" config --add "remote.$2.fetch" '+refs/tags/*:refs/tags/*'
    [[ "$3" == unset ]] || git -C "$W/$1" config "remote.$2.skipFetchAll" "$3"
}
setup_store_remote B ait-store unset
orig="$(fetchvals B ait-store)"
cfg "$W/B" "$BR" "remote: ait-store" "remote_dedicated: true"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_zero_rc "dedicated: enter succeeds" "$rc"
assert_contains "dedicated: token" "DEDICATED:ait-store" "$out"
assert_eq "dedicated: skipFetchAll set" "true" "$(cfgval B remote.ait-store.skipFetchAll)"
assert_eq "dedicated: negative-only fetch set" "^refs/heads/$BR" "$(fetchvals B ait-store)"
assert_eq "dedicated: the backup holds the originals in order" "$orig" "$(git -C "$W/B" config --get-all remote.ait-store.aitaskSavedFetch)"
assert_eq "dedicated: origin is not dedicated" "" "$(cfgval B remote.origin.skipFetchAll)"
assert_contains "dedicated: origin gets shared mode" "^refs/heads/$BR" "$(fetchvals B origin)"
out="$(afx B apply 2>&1)"
assert_contains "dedicated: re-run is a no-op" "FETCH_EXCLUSION:UNCHANGED" "$out"
cfg "$W/B" "$BR" "remote: ait-store"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_zero_rc "dedicated->shared: succeeds" "$rc"
assert_contains "dedicated->shared: token" "RESTORED:ait-store" "$out"
assert_eq "dedicated->shared: originals restored in order" "$orig" "$(fetchvals B ait-store | grep -v '^\^')"
assert_eq "dedicated->shared: skipFetchAll back to unset" "" "$(cfgval B remote.ait-store.skipFetchAll)"
assert_eq "dedicated->shared: no state keys remain" "" "$(aitkeys B ait-store)"
assert_contains "dedicated->shared: the negative is re-added in shared mode" "^refs/heads/$BR" "$(fetchvals B ait-store)"

for skip in true false; do
    git -C "$W/A" remote remove "st-$skip" 2>/dev/null
    setup_store_remote A "st-$skip" "$skip"
    o="$(fetchvals A "st-$skip")"
    cfg "$W/A" "$BR" "remote: st-$skip" "remote_dedicated: true"; afx A apply >/dev/null 2>&1
    cfg "$W/A" "$BR" "remote: st-$skip"; afx A apply >/dev/null 2>&1
    assert_eq "dedicated->shared (skipFetchAll=$skip): restored" "$skip" "$(cfgval A "remote.st-$skip.skipFetchAll")"
    assert_eq "dedicated->shared (skipFetchAll=$skip): originals" "$o" "$(fetchvals A "st-$skip" | grep -v '^\^')"
done

echo "--- 8b. Without the flag, and declared on origin ---"
cfg "$W/B" "$BR" "remote: ait-store"
afx B apply >/dev/null 2>&1
assert_eq "no flag: no skipFetchAll anywhere" "" "$(git -C "$W/B" config --get-regexp 'skipfetchall' 2>/dev/null)"
cfg "$W/B" "$BR" "remote: origin" "remote_dedicated: true"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_zero_rc "origin declared: still succeeds" "$rc"
assert_contains "origin declared: warns" "carries the code and task data" "$out"
assert_eq "origin declared: origin is never dedicated" "" "$(cfgval B remote.origin.skipFetchAll)"
assert_contains "origin declared: origin keeps its positive mapping" "+refs/heads/*" "$(fetchvals B origin)"

echo "--- 8c. Reassignment ---"
git -C "$W/B" remote add ait-store2 "file://$W/s.git"
o1="$(fetchvals B ait-store | grep -v '^\^')"
cfg "$W/B" "$BR" "remote: ait-store" "remote_dedicated: true"; afx B apply >/dev/null 2>&1
cfg "$W/B" "$BR" "remote: ait-store2" "remote_dedicated: true"
out="$(afx B apply 2>&1)"
assert_contains "reassign: the first remote is restored" "RESTORED:ait-store" "$out"
assert_contains "reassign: the second is dedicated" "DEDICATED:ait-store2" "$out"
assert_eq "reassign: the first remote's originals are back" "$o1" "$(fetchvals B ait-store | grep -v '^\^')"
assert_eq "reassign: the second is negative-only" "^refs/heads/$BR" "$(fetchvals B ait-store2)"

echo "--- 8d. Drift and invalid state are refused, other remotes still processed ---"
git -C "$W/B" config --add remote.ait-store2.fetch '+refs/heads/hand:refs/remotes/ait-store2/hand'
# Leave ait-store2 (flag off) and, in the same run, force a shared-mode change
# on origin (a new branch name) to prove the other remotes are still processed.
cfg "$W/B" typo2 "remote: ait-store2"
snap="$(git -C "$W/B" config --get-regexp '^remote\.ait-store2\.')"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_nonzero_rc "drift: refused" "$rc"
assert_contains "drift: token" "FETCH_EXCLUSION:DEDICATED_DRIFT:ait-store2" "$out"
assert_contains "drift: recovery commands" "git config --unset-all remote.ait-store2.fetch" "$out"
assert_eq "drift: the remote is untouched" "$snap" "$(git -C "$W/B" config --get-regexp '^remote\.ait-store2\.')"
assert_contains "drift: other remotes still processed" "EXCLUDED:origin:typo2" "$out"
git -C "$W/B" config --unset-all remote.ait-store2.fetch '^\+refs/heads/hand'
afx B apply >/dev/null 2>&1
git -C "$W/B" config remote.ait-store.aitaskDedicatedState bogus
snap="$(git -C "$W/B" config --get-regexp '^remote\.ait-store\.')"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_nonzero_rc "invalid state: refused" "$rc"
assert_contains "invalid state: token" "DEDICATED_STATE_INVALID:ait-store" "$out"
assert_eq "invalid state: the remote is untouched" "$snap" "$(git -C "$W/B" config --get-regexp '^remote\.ait-store\.')"

echo "--- 9. Interrupted transitions resume without losing the backup ---"
# run_interrupt <label> <phase: enter|leave> <skip> <exact git args to fail>
run_interrupt() {
    local label="$1" phase="$2" skip="$3" match="$4" o s rc
    new_world "int-$label-$skip"
    setup_store_remote B st "$skip"
    o="$(fetchvals B st)"; s="$(cfgval B remote.st.skipFetchAll)"
    cfg "$W/B" "$BR" "remote: st" "remote_dedicated: true"
    if [[ "$phase" == leave ]]; then
        afx B apply >/dev/null 2>&1
        cfg "$W/B" "$BR" "remote: st"
    fi
    ( cd "$W/B" && AFX_FAIL_MATCH="$match" PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply ) >/dev/null 2>&1; rc=$?
    assert_exit_nonzero_rc "interrupt $label ($skip): the injected failure surfaces" "$rc"
    afx B apply >/dev/null 2>&1; rc=$?
    assert_exit_zero_rc "interrupt $label ($skip): the retry converges" "$rc"
    if [[ "$phase" == enter ]]; then
        assert_eq "interrupt $label ($skip): retry reaches active" "active" "$(cfgval B remote.st.aitaskDedicatedState)"
        assert_eq "interrupt $label ($skip): the backup still holds the originals" "$o" \
            "$(git -C "$W/B" config --get-all remote.st.aitaskSavedFetch)"
        cfg "$W/B" "$BR" "remote: st"
        afx B apply >/dev/null 2>&1
    fi
    assert_eq "interrupt $label ($skip): original fetch values survive, in order" "$o" "$(fetchvals B st | grep -v '^\^')"
    assert_eq "interrupt $label ($skip): original skipFetchAll survives" "$s" "$(cfgval B remote.st.skipFetchAll)"
    assert_eq "interrupt $label ($skip): no state keys remain" "" "$(aitkeys B st)"
}
for skip in unset false; do
    run_interrupt a enter "$skip" "config remote.st.aitaskDedicatedState active"
    run_interrupt b enter "$skip" "config remote.st.aitaskDedicatedState saved"
    run_interrupt c enter "$skip" "config --add remote.st.fetch ^refs/heads/$BR"
    run_interrupt d leave "$skip" "config --unset-all remote.st.aitaskSavedSkipFetchAll"
    run_interrupt e leave "$skip" "config --unset-all remote.st.aitaskSavedFetch"
    run_interrupt f leave "$skip" "config --unset-all remote.st.aitaskDedicatedState"
done

echo "--- 10. Concurrent applies are serialized ---"
new_world conc
setup_store_remote B st false
o="$(fetchvals B st)"
cfg "$W/B" "$BR" "remote: st" "remote_dedicated: true"
mkfifo "$TMP/fifo"; rm -f "$TMP/paused"
( cd "$W/B" && AFX_PAUSE_MATCH="config remote.st.aitaskDedicatedState saved" AFX_PAUSE_FIFO="$TMP/fifo" \
    AFX_PAUSE_MARK="$TMP/paused" PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply ) >"$TMP/outA" 2>&1 &
pa=$!
for _ in $(seq 1 100); do [[ -e "$TMP/paused" ]] && break; sleep 0.1; done
assert_file_exists "concurrency: A paused right after state=saved" "$TMP/paused"
snap="$(git -C "$W/B" config --get-regexp '^remote\.st\.')"
( cd "$W/B" && "$ART" fetch-exclusion apply ) >"$TMP/outB" 2>&1 &
pb=$!
sleep 1.5
assert_eq "concurrency: B is waiting" "running" "$(kill -0 "$pb" 2>/dev/null && echo running || echo exited)"
assert_dir_exists "concurrency: the lock is held" "$W/B/.git/ait-fetch-exclusion.lock"
assert_eq "concurrency: B wrote nothing while A holds the lock" "$snap" "$(git -C "$W/B" config --get-regexp '^remote\.st\.')"
release_pause
wait "$pa"; ra=$?; wait "$pb"; rb=$?
assert_exit_zero_rc "concurrency: A completes" "$ra"
assert_exit_zero_rc "concurrency: B completes after A" "$rb"
assert_contains "concurrency: B saw A's finished transition" "FETCH_EXCLUSION:UNCHANGED" "$(cat "$TMP/outB")"
assert_eq "concurrency: the backup holds the originals" "$o" "$(git -C "$W/B" config --get-all remote.st.aitaskSavedFetch)"
cfg "$W/B" "$BR" "remote: st"; afx B apply >/dev/null 2>&1
assert_eq "concurrency: leave restores the originals" "$o" "$(fetchvals B st | grep -v '^\^')"
assert_eq "concurrency: leave restores skipFetchAll=false" "false" "$(cfgval B remote.st.skipFetchAll)"

echo "--- 10b. Mirror: a re-declaration waits for an in-flight Leave ---"
cfg "$W/B" "$BR" "remote: st" "remote_dedicated: true"; afx B apply >/dev/null 2>&1
cfg "$W/B" "$BR" "remote: st"
rm -f "$TMP/paused"
( cd "$W/B" && AFX_PAUSE_MATCH="config remote.st.aitaskDedicatedState restoring" AFX_PAUSE_FIFO="$TMP/fifo" \
    AFX_PAUSE_MARK="$TMP/paused" PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply ) >"$TMP/outA" 2>&1 &
pa=$!
for _ in $(seq 1 100); do [[ -e "$TMP/paused" ]] && break; sleep 0.1; done
cfg "$W/B" "$BR" "remote: st" "remote_dedicated: true"
( cd "$W/B" && "$ART" fetch-exclusion apply ) >"$TMP/outB" 2>&1 &
pb=$!
sleep 1
release_pause
wait "$pa"; ra=$?; wait "$pb"; rb=$?
assert_exit_zero_rc "mirror: the Leave completes" "$ra"
assert_exit_zero_rc "mirror: the re-declaration completes" "$rb"
assert_eq "mirror: the final state is active" "active" "$(cfgval B remote.st.aitaskDedicatedState)"
assert_eq "mirror: the backup's positives are the originals" "$o" "$(git -C "$W/B" config --get-all remote.st.aitaskSavedFetch | grep -v '^\^')"

echo "--- 10c. A held lock times out as BUSY ---"
rm -f "$TMP/paused"
cfg "$W/B" "$BR" "remote: st"
( cd "$W/B" && AFX_PAUSE_MATCH="config remote.st.aitaskDedicatedState restoring" AFX_PAUSE_FIFO="$TMP/fifo" \
    AFX_PAUSE_MARK="$TMP/paused" PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply ) >/dev/null 2>&1 &
pa=$!
for _ in $(seq 1 100); do [[ -e "$TMP/paused" ]] && break; sleep 0.1; done
out="$( cd "$W/B" && AFX_LOCK_TIMEOUT=1 "$ART" fetch-exclusion apply 2>&1 )"; rc=$?
assert_exit_nonzero_rc "busy: refused" "$rc"
assert_contains "busy: token" "FETCH_EXCLUSION:BUSY" "$out"
release_pause; wait "$pa"

echo "--- 10d. No nested acquire ---"
out="$( cd "$W/B" && bash -c '
    L="$1/.aitask-scripts/lib"
    source "$L/terminal_compat.sh"; source "$L/artifact_fetch_exclusion.sh"
    registry_lock_acquire "$2/held.lock" 5 || exit 9
    afx_with_lock true' _ "$PROJECT_DIR" "$TMP" 2>&1 )"; rc=$?
assert_exit_nonzero_rc "nested: dies" "$rc"
assert_contains "nested: programming-error message" "programming error" "$out"

echo "--- 12. An input change during the apply is never certified ---"
new_world drift
cfg "$W/B" store-a
rm -f "$TMP/paused"
( cd "$W/B" && AFX_PAUSE_MATCH="config --add remote.origin.aitaskExclude store-a" AFX_PAUSE_FIFO="$TMP/fifo" \
    AFX_PAUSE_MARK="$TMP/paused" PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply --if-changed ) >"$TMP/outA" 2>&1 &
pa=$!
for _ in $(seq 1 100); do [[ -e "$TMP/paused" ]] && break; sleep 0.1; done
assert_file_exists "input change: the apply paused after reading store-a" "$TMP/paused"
cfg "$W/B" store-b                       # the config changes mid-apply
release_pause; wait "$pa"; ra=$?
assert_exit_zero_rc "input change: the apply converges" "$ra"
assert_contains "input change: it noticed and re-applied" "re-applying" "$(cat "$TMP/outA")"
assert_contains "input change: the NEW branch is excluded" "^refs/heads/store-b" "$(fetchvals B origin)"
assert_not_contains "input change: the stale branch was released" "^refs/heads/store-a" "$(fetchvals B origin)"
out="$(afx B apply --if-changed 2>&1)"
assert_contains "input change: the stored fingerprint matches what was applied" "FETCH_EXCLUSION:UNCHANGED" "$out"
# Inputs that never hold still: every attempt sees a new branch.
git -C "$W/B" config --unset aitask.fetchExclusionFingerprint
fp0="$(cfgval B aitask.fetchExclusionFingerprint)"
out="$( cd "$W/B" && AFX_MUTATE_MATCH="--version" \
    AFX_MUTATE_CMD="printf 'artifacts:\n  backends:\n    gitbranch:\n      branch: churn-%s\n' \"\$RANDOM\$RANDOM\" > aitasks/metadata/project_config.yaml" \
    PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply --if-changed 2>&1 )"; rc=$?
assert_exit_nonzero_rc "unstable inputs: the apply fails" "$rc"
assert_contains "unstable inputs: token" "FETCH_EXCLUSION:INPUTS_UNSTABLE" "$out"
assert_eq "unstable inputs: no fingerprint certifies them" "$fp0" "$(cfgval B aitask.fetchExclusionFingerprint)"
cfg "$W/B" "$BR"; afx B apply >/dev/null 2>&1

echo "--- 13. A release keeps the user's duplicate across every failure boundary ---"
# run_release_fault <label> <exact git args to fail>
run_release_fault() {
    local label="$1" match="$2" rc
    new_world "rel-$label"
    cfg "$W/B" rel-x; afx B apply >/dev/null 2>&1
    git -C "$W/B" config --add remote.origin.fetch '^refs/heads/rel-x'      # the user's own copy
    cfg "$W/B" rel-y
    ( cd "$W/B" && AFX_FAIL_MATCH="$match" PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply ) >/dev/null 2>&1; rc=$?
    assert_exit_nonzero_rc "release $label: the injected failure surfaces" "$rc"
    afx B apply >/dev/null 2>&1; rc=$?
    assert_exit_zero_rc "release $label: the retry converges" "$rc"
    assert_eq "release $label: exactly the user's copy remains" "1" "$(fetchvals B origin | grep -cxF '^refs/heads/rel-x')"
    assert_eq "release $label: ownership released" "" "$(git -C "$W/B" config --get-all remote.origin.aitaskExclude | grep -x rel-x)"
    assert_eq "release $label: no release marker left" "" "$(cfgval B remote.origin.aitaskReleasing)"
    assert_contains "release $label: the new branch is excluded" "^refs/heads/rel-y" "$(fetchvals B origin)"
}
run_release_fault ownership 'config --unset-all remote.origin.aitaskExclude ^rel-x$'
run_release_fault readd 'config --add remote.origin.fetch ^refs/heads/rel-x'
run_release_fault unsetall 'config --unset-all remote.origin.fetch ^\^refs/heads/rel-x$'
run_release_fault marker 'config --unset-all remote.origin.aitaskReleasing ^rel-x '
run_release_fault record 'config --add remote.origin.aitaskReleasing rel-x 1'

echo "--- 14. Dedicated drift: a negative refspec the user added is not ours ---"
new_world ddrift
git init -q --bare "$W/s.git"
setup_store_remote B st unset
cfg "$W/B" "$BR" "remote: st" "remote_dedicated: true"; afx B apply >/dev/null 2>&1
git -C "$W/B" config --add remote.st.fetch '^refs/heads/user-hidden'
snap="$(git -C "$W/B" config --get-regexp '^remote\.st\.')"
cfg "$W/B" other-branch "remote: st" "remote_dedicated: true"           # a Stay rewrite
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_nonzero_rc "user negative (stay): refused" "$rc"
assert_contains "user negative (stay): drift token" "FETCH_EXCLUSION:DEDICATED_DRIFT:st" "$out"
assert_eq "user negative (stay): the remote is untouched" "$snap" "$(git -C "$W/B" config --get-regexp '^remote\.st\.')"
cfg "$W/B" "$BR" "remote: st"                                          # a Leave
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_nonzero_rc "user negative (leave): refused" "$rc"
assert_contains "user negative (leave): drift token" "FETCH_EXCLUSION:DEDICATED_DRIFT:st" "$out"
assert_eq "user negative (leave): the remote is untouched" "$snap" "$(git -C "$W/B" config --get-regexp '^remote\.st\.')"
assert_contains "user negative (leave): the user's exclusion survives" "^refs/heads/user-hidden" "$(fetchvals B st)"

echo "--- 14b. An interrupted Stay rewrite never reads as drift ---"
new_world dstay
git init -q --bare "$W/s.git"
setup_store_remote B st unset
cfg "$W/B" old-store "remote: st" "remote_dedicated: true"; afx B apply >/dev/null 2>&1
cfg "$W/B" new-store "remote: st" "remote_dedicated: true"
( cd "$W/B" && AFX_FAIL_MATCH='config --unset-all remote.st.aitaskDedicatedSet ^old-store$' \
    PATH="$TMP/shim:$PATH" "$ART" fetch-exclusion apply ) >/dev/null 2>&1; rc=$?
assert_exit_nonzero_rc "interrupted stay: the injected failure surfaces" "$rc"
out="$(afx B apply 2>&1)"; rc=$?
assert_exit_zero_rc "interrupted stay: the retry is not mistaken for drift" "$rc"
assert_eq "interrupted stay: live is the new set" "^refs/heads/new-store" "$(fetchvals B st)"
assert_eq "interrupted stay: the record is the new set" "new-store" "$(git -C "$W/B" config --get-all remote.st.aitaskDedicatedSet)"

echo "--- 11. Call sites: init-store and init_data ---"
new_world callsites
out="$(art A init-store gitbranch 2>&1)"; rc=$?
assert_exit_zero_rc "init-store gitbranch: succeeds" "$rc"
assert_contains "init-store gitbranch: adds the exclusion" "^refs/heads/$BR" "$(fetchvals A origin)"

D="$TMP/initdata"; mkdir -p "$D"
git -C "$D" init -q -b main; git -C "$D" config user.email t@t.t; git -C "$D" config user.name tester
git -C "$D" commit -q --allow-empty -m code
git -C "$D" checkout -q --orphan aitask-data
git -C "$D" rm -rq --cached . 2>/dev/null || true
mkdir -p "$D/aitasks/metadata" "$D/aiplans"
printf 'artifacts:\n  backends:\n    gitbranch:\n      branch: %s\n' "$BR" > "$D/aitasks/metadata/project_config.yaml"
touch "$D/aiplans/.keep"
git -C "$D" add aitasks aiplans; git -C "$D" commit -q -m data
git -C "$D" checkout -q main; rm -rf "$D/aitasks" "$D/aiplans"
git -C "$D" remote add origin "file://$TMP/nowhere.git"
out="$( cd "$D" && "$PROJECT_DIR/.aitask-scripts/aitask_init_data.sh" 2>/dev/null )"; rc=$?
assert_exit_zero_rc "init_data: succeeds" "$rc"
assert_eq "init_data: stdout carries only its own token" "INITIALIZED" "$out"
assert_contains "init_data: adds the exclusion" "^refs/heads/$BR" "$(git -C "$D" config --get-all remote.origin.fetch 2>/dev/null)"

echo ""
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]]
