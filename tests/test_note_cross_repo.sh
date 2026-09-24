#!/usr/bin/env bash
# test_note_cross_repo.sh - `ait note --project` / `ait note read --project`
# (t1869): cross-repository notes and read receipts.
#
# Drives the REAL entry point in isolated repositories built in the PRODUCTION
# topology (tests/lib/sync_fixture.sh::setup_repo): a bare remote, a clone with
# a real `.aitask-data` worktree on the orphan `aitask-data` branch, `aitasks/`
# symlinks, an initialized lock branch and each repository's OWN copy of
# `.aitask-scripts`. So `task_git` runs in branch mode, and the target's own
# helper does the write — which is the whole point of the feature. One
# legacy-mode repository is kept for a single smoke case.
#
# Coverage map:
#   placement           the write lands only in the target, on its aitask-data
#                       branch, pushed; the source and the target's main never move
#   identity            from=<src>#t<id>, marker t<id>, same number in both repos
#   proof               from_verified=yes only when this session holds the
#                       source task's lock in the SOURCE repository; never 'no'
#   provenance          base is the TARGET checkout; an inherited AIT_DIR never leaks
#   routing boundary    literal "--project"/"--from-project" VALUES never route
#   write failures      every refusal leaves every branch of every repo untouched
#   read                receipts in the target, rollback, READ_* family only
#   compatibility       per-verb capability probe; a pre-t1869 read helper works
#   live lane           durable first; LIVE_* passed through verbatim
#
# Run: bash tests/test_note_cross_repo.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
. "$PROJECT_DIR/tests/lib/asserts.sh"
# Also exports AITASKS_TMUX_SOCKET at a socket nothing serves: the resolver's
# tmux tier therefore sees a DEFINITE "no server", never the user's sessions.
. "$PROJECT_DIR/tests/lib/sync_fixture.sh"

PASS=0
FAIL=0
TOTAL=0

BASE="$(mktemp -d "${TMPDIR:-/tmp}/test_note_xrepo_XXXXXX")"
AITASKS_LOCK_DIR="$BASE/locks"; mkdir -p "$AITASKS_LOCK_DIR"
export AITASKS_LOCK_DIR
cleanup() { rm -rf "$BASE"; _sync_fixture_cleanup; }
trap cleanup EXIT

# The caller's own AITASKS_PROJECT_* variables would add env-tier candidates.
while IFS= read -r v; do unset "$v"; done < <(compgen -e | grep '^AITASKS_PROJECT_' || true)
unset AIT_PROJECT_RESOLVE_ENUM_FAIL AIT_DIR 2>/dev/null || true
# A deterministic session anchor for the lock proof (must name a live process).
export AIT_AGENT_PID=$$

# --- fixture ---------------------------------------------------------------

task_md() { printf -- '---\nstatus: Ready\n---\nBody for %s.\n' "$1"; }

# seed_branch_repo <local-root>: project marker + t700/t701 on the data branch.
seed_branch_repo() {
    local r="$1"
    (
        cd "$r" || exit 1
        : > .aitask-data/aitasks/metadata/project_config.yaml
        task_md t700 > .aitask-data/aitasks/t700_x.md
        task_md t701 > .aitask-data/aitasks/t701_x.md
        git -C .aitask-data add -A
        git -C .aitask-data commit -q -m "seed"
        git -C .aitask-data push -q 2>/dev/null
    ) >/dev/null 2>&1
}

SRC="$(setup_repo)/local"; seed_branch_repo "$SRC"
TGT="$(setup_repo)/local"; seed_branch_repo "$TGT"
SRC="$(cd "$SRC" && pwd -P)"; TGT="$(cd "$TGT" && pwd -P)"

# Legacy mode: plain clone, task data on the code branch.
LEG="$BASE/leg"
git init -q --bare "$BASE/leg.git"
git clone -q "$BASE/leg.git" "$LEG" 2>/dev/null
(
    cd "$LEG" || exit 1
    git config user.email t@t; git config user.name T; git config commit.gpgsign false
    mkdir -p aitasks/metadata; : > aitasks/metadata/project_config.yaml
    task_md t700 > aitasks/t700_x.md
    cp -r "$PROJECT_DIR/.aitask-scripts" ./.aitask-scripts
    git add -A; git commit -q -m init; git branch -M main; git push -q -u origin main
    ./.aitask-scripts/aitask_lock.sh --init
) >/dev/null 2>&1
LEG="$(cd "$LEG" && pwd -P)"

# Stubs: a target whose helper advertises NEITHER capability, and one that is
# pre-t1869 (has the receipt verb, lacks --from-project) and records its argv.
make_stub() {   # <dir> <help-text>
    local d="$1" help="$2"
    mkdir -p "$d/aitasks/metadata" "$d/.aitask-scripts"
    : > "$d/aitasks/metadata/project_config.yaml"
    cat > "$d/.aitask-scripts/aitask_note.sh" <<EOF
#!/usr/bin/env bash
if [[ "\${1:-}" == "--help" ]]; then printf '%s\n' "$help"; exit 0; fi
printf '%s\n' "\$*" > "$d/argv"
printf 'READ_RECORDED:2026-01-01T00:00:00Z.aaaaaaaaaaaaaaaaaaaaaaaa|aitasks/t700_x.md|1\n'
EOF
    chmod +x "$d/.aitask-scripts/aitask_note.sh"
}
STUBW="$BASE/stubw"; make_stub "$STUBW" "Usage: aitask_note.sh <target-task-id> --from <id>"
STUBR="$BASE/stubr"; make_stub "$STUBR" "       aitask_note.sh read <task-id> --by <id> --ids <csv>"

REG="$BASE/projects.yaml"
write_registry() {   # extra entries appended from stdin
    {
        echo "projects:"
        printf '  - name: srcfx\n    path: %s\n' "$SRC"
        printf '  - name: tgtfx\n    path: %s\n' "$TGT"
        printf '  - name: legfx\n    path: %s\n' "$LEG"
        printf '  - name: stubw\n    path: %s\n' "$STUBW"
        printf '  - name: stubr\n    path: %s\n' "$STUBR"
        printf '  - name: stalefx\n    path: %s\n' "$BASE/nowhere"
        cat
    } > "$REG"
}
write_registry </dev/null
export AITASKS_PROJECTS_INDEX="$REG"

ERR="$BASE/stderr"
# run_in <repo> <args...> — the note helper of <repo>, from inside it.
run_in() { local r="$1"; shift; ( cd "$r" && ./.aitask-scripts/aitask_note.sh "$@" ) 2>"$ERR"; }
run_src() { run_in "$SRC" "$@"; }

tgt_body() { cat "$TGT/aitasks/t${1}_x.md"; }
# Every ref that could move, in every repository, plus the task files' bytes.
state() {
    local r
    for r in "$SRC" "$TGT"; do
        git -C "$r" rev-parse HEAD
        git -C "$r/.aitask-data" rev-parse HEAD
        git -C "$r/.aitask-data" status --porcelain
        cat "$r"/aitasks/t70*_x.md | cksum
    done
    git -C "$LEG" rev-parse HEAD
}
# expect_refused <desc> <expected-line> <args...> — one line, rc!=0, no mutation.
expect_refused() {
    local desc="$1" want="$2"; shift 2
    local before after out rc=0
    before="$(state)"
    out="$(run_src "$@")" || rc=$?
    after="$(state)"
    assert_eq "$desc: outcome" "$want" "$out"
    assert_eq "$desc: non-zero exit" "1" "$(( rc != 0 ))"
    assert_eq "$desc: nothing mutated anywhere" "$before" "$after"
}

echo "=== ait note --project: cross-repository notes (t1869) ==="

# The help text is the capability probe AND an unquoted heredoc: a backtick or
# $( ) in it would EXECUTE while --help runs. Pin the literal survivors.
help_out="$( cd "$SRC" && ./.aitask-scripts/aitask_note.sh --help 2>/dev/null )"
assert_contains "0a. help advertises --from-project (the write capability)" "--from-project" "$help_out"
assert_contains "0b. help advertises the receipt verb (the read capability)" "read <task-id> --by" "$help_out"
assert_contains "0c. help text is literal (no command substitution ran)" \
    '"ait projects resolve" supports' "$help_out"

# --- 1. Placement, identity, provenance ------------------------------------

tgt_data_before="$(git -C "$TGT/.aitask-data" rev-parse HEAD)"
tgt_main_before="$(git -C "$TGT" rev-parse HEAD)"
src_state_before="$(git -C "$SRC" rev-parse HEAD; git -C "$SRC/.aitask-data" rev-parse HEAD; cat "$SRC/aitasks/t700_x.md")"

# Same numeric id on both sides (t700 -> t700), with a caller AIT_DIR pointing
# at the SOURCE: provenance must still describe the TARGET checkout.
rc=0
out="$( cd "$SRC" && AIT_DIR="$SRC" ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text "first cross-repo note" 2>"$ERR" )" || rc=$?
assert_contains_re "1a. NOTE_APPENDED with an ABSOLUTE target path" \
    "^NOTE_APPENDED:[0-9T:Z.-]+\.[0-9a-f]{24}\|$TGT/aitasks/t700_x\.md$" "$out"
assert_eq "1b. exit 0" "0" "$rc"
NOTE1="$(printf '%s' "$out" | sed -n 's/^NOTE_APPENDED:\([^|]*\)|.*/\1/p')"
body="$(tgt_body 700)"
assert_contains "1c. qualified sender stored" "from=srcfx#t700" "$body"
assert_contains "1d. marker name is the local t<id> part" "**✉ note:t700**" "$body"
assert_contains "1e. body landed" "> | first cross-repo note" "$body"
assert_not_contains "1f. unlocked sender is not verified" "from_verified" "$body"
assert_contains "1g. base is the TARGET checkout, not the inherited AIT_DIR" \
    "base=$(git -C "$TGT" rev-parse HEAD)" "$body"
assert_eq "1h. commit on the TARGET's aitask-data branch" \
    "ait: Record note $NOTE1 for t700" \
    "$(git -C "$TGT/.aitask-data" log -1 --format=%s -- aitasks/t700_x.md)"
assert_eq "1i. pushed to the target's remote aitask-data" \
    "$(git -C "$TGT/.aitask-data" rev-parse HEAD)" \
    "$(git -C "$TGT/.aitask-data" ls-remote origin refs/heads/aitask-data | cut -f1)"
assert_eq "1j. target data branch advanced by exactly one commit" "1" \
    "$(git -C "$TGT/.aitask-data" rev-list --count "$tgt_data_before"..HEAD)"
assert_eq "1k. target main did not move" "$tgt_main_before" "$(git -C "$TGT" rev-parse HEAD)"
assert_eq "1l. source untouched (both branches, same-numbered task)" "$src_state_before" \
    "$(git -C "$SRC" rev-parse HEAD; git -C "$SRC/.aitask-data" rev-parse HEAD; cat "$SRC/aitasks/t700_x.md")"

inbox="$( cd "$TGT" && ./.aitask-scripts/aitask_query_files.sh inbox 700 2>/dev/null )"
assert_contains "1m. surfaced in the target with the qualified sender" \
    "INBOX_UNREAD:700|$NOTE1|srcfx#t700|" "$inbox"
assert_not_contains "1n. the block validates (not malformed)" "INBOX_MALFORMED" "$inbox"

# --- 2. The sender proof across the boundary -------------------------------

if ( cd "$SRC" && ./.aitask-scripts/aitask_lock.sh 701 --email t@t ) >/dev/null 2>&1; then
    run_src 701 --project tgtfx --from 701 --text "verified send" >/dev/null
    assert_contains "2a. source lock held by THIS session => verified" \
        "from_verified=yes" "$(tgt_body 701)"
    ( cd "$SRC" && ./.aitask-scripts/aitask_lock.sh --unlock 701 ) >/dev/null 2>&1 || true
else
    echo "SKIP 2a: could not acquire a source lock in the fixture"
fi
# A lock on the SAME number in the TARGET proves nothing about the source.
if ( cd "$TGT" && ./.aitask-scripts/aitask_lock.sh 700 --email t@t ) >/dev/null 2>&1; then
    run_src 701 --project tgtfx --from 700 --text "target-side lock is not proof" >/dev/null
    last_marker="$(grep '^> \*\*✉ note:t700\*\*' "$TGT/aitasks/t701_x.md" | tail -1)"
    assert_not_contains "2b. a same-numbered TARGET lock does not verify" \
        "from_verified" "$last_marker"
    ( cd "$TGT" && ./.aitask-scripts/aitask_lock.sh --unlock 700 ) >/dev/null 2>&1 || true
fi
assert_eq "2c. from_verified is never written as 'no'" "0" \
    "$(cat "$TGT"/aitasks/t70*_x.md | grep -c 'from_verified=no')"

# --- 3. Bodies from files ---------------------------------------------------

printf 'from a relative file\n' > "$SRC/body.txt"
run_src 700 --project tgtfx --from 700 --file body.txt >/dev/null
assert_contains "3a. --file <relative> resolves against the CALLER's cwd" \
    "> | from a relative file" "$(tgt_body 700)"
rm -f "$SRC/body.txt"
printf 'from stdin\n' | run_src 700 --project tgtfx --from 700 --file - >/dev/null
assert_contains "3b. --file - passes stdin through" "> | from stdin" "$(tgt_body 700)"

# --- 4. The routing boundary: literal option tokens as VALUES --------------

out="$(run_src 701 --from 700 --text --project)"
assert_contains_re "4a. '--text --project' is a local note (relative path)" \
    '^NOTE_APPENDED:[^|]+\|aitasks/t701_x\.md$' "$out"
assert_contains "4b. ... whose body is the literal token" "> | --project" "$(cat "$SRC/aitasks/t701_x.md")"
assert_contains "4c. ... from the LOCAL sender" "from=t700" "$(cat "$SRC/aitasks/t701_x.md")"
printf 'a file literally named --project\n' > "$SRC/--project"
out="$(run_src 701 --from 700 --file --project)"
assert_contains_re "4d. '--file --project' reads that file locally" '^NOTE_APPENDED:[^|]+\|aitasks/t701_x\.md$' "$out"
assert_contains "4e. ... its content" "> | a file literally named --project" "$(cat "$SRC/aitasks/t701_x.md")"
rm -f -- "$SRC/--project"
out="$(run_src 701 --from 700 --text --from-project)"
assert_contains_re "4f. '--text --from-project' stays local" '^NOTE_APPENDED:[^|]+\|aitasks/t701_x\.md$' "$out"
out="$(run_src 700 --project tgtfx --from 700 --text --project)"
assert_contains "4g. routed: a '--project' body is forwarded as a value" \
    "|$TGT/aitasks/t700_x.md" "$out"
assert_contains "4h. ... and lands verbatim" "> | --project" "$(tgt_body 700)"
out="$(run_src read 700 --by 700 --ids --project)"
assert_eq "4i. 'read --ids --project' stays on the local path, unchanged" \
    "READ_ERROR:bad-note-id:--project" "$out"
out="$(run_src 700 --bogus --project tgtfx --from 700 --text x)"
assert_eq "4j. an unknown option before --project: the unchanged local error" \
    "NOTE_ERROR:unknown-option:--bogus" "$out"

# --- 5. Write refusals: typed, one line, nothing mutated anywhere ----------

expect_refused "5a. unknown project" "NOTE_ERROR:project-not-found:nosuch" \
    700 --project nosuch --from 700 --text x
expect_refused "5b. stale project" "NOTE_ERROR:project-stale:stalefx" \
    700 --project stalefx --from 700 --text x
expect_refused "5c. bad project name" "NOTE_ERROR:bad-project-name:Bad/Name" \
    700 --project Bad/Name --from 700 --text x
before="$(state)"
out="$( cd "$SRC" && AITASKS_PROJECT_tgtfx="$SRC" ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text x 2>"$ERR" )"
assert_eq "5d. registry and env disagree => ambiguous" "NOTE_ERROR:project-ambiguous:tgtfx" "$out"
assert_contains "5e. ... and the roots are named on stderr" "$TGT" "$(cat "$ERR")"
assert_eq "5f. ... nothing mutated" "$before" "$(state)"
printf '  - name: tgtfx\n    path: %s\n' "$LEG" | write_registry
expect_refused "5g. duplicate registry name, two roots" "NOTE_ERROR:project-ambiguous:tgtfx" \
    700 --project tgtfx --from 700 --text x
write_registry </dev/null
before="$(state)"
out="$( cd "$SRC" && AIT_PROJECT_RESOLVE_ENUM_FAIL=registry ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text x 2>/dev/null )"
assert_eq "5h. registry tier unreadable => fails closed" \
    "NOTE_ERROR:project-resolution-incomplete:registry" "$out"
out="$( cd "$SRC" && AIT_PROJECT_RESOLVE_ENUM_FAIL=tmux ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text x 2>/dev/null )"
assert_eq "5i. tmux tier unreadable => fails closed" \
    "NOTE_ERROR:project-resolution-incomplete:tmux" "$out"
assert_eq "5j. ... nothing mutated" "$before" "$(state)"
expect_refused "5k. target is this repository" "NOTE_ERROR:project-is-local:srcfx" \
    700 --project srcfx --from 700 --text x
expect_refused "5l. --project with --migrate" "NOTE_ERROR:project-not-valid-with-migrate" \
    700 --project tgtfx --migrate --claimed-from 1 --claimed-at 2026-01-01 --base none --text x
expect_refused "5m. --project A --project B" "NOTE_ERROR:duplicate-option:--project" \
    700 --project tgtfx --project legfx --from 700 --text x
expect_refused "5n. repeated --from-project" "NOTE_ERROR:duplicate-option:--from-project" \
    700 --project tgtfx --from-project srcfx --from-project srcfx --from 700 --text x
expect_refused "5o. --project with no value" "NOTE_ERROR:missing-value:--project" \
    700 --from 700 --text x --project
expect_refused "5p. missing --from" "NOTE_ERROR:missing-from" \
    700 --project tgtfx --text x
expect_refused "5q. --from-project is not this repository" \
    "NOTE_ERROR:from-project-mismatch:tgtfx" \
    700 --project legfx --from-project tgtfx --from 700 --text x
expect_refused "5r. source task missing (checked in the SOURCE repo)" \
    "NOTE_ERROR:source-task-missing:srcfx#t999" \
    700 --project tgtfx --from 999 --text x
expect_refused "5s. target task missing" "NOTE_TARGET_MISSING:999" \
    999 --project tgtfx --from 700 --text x
expect_refused "5t. incompatible target helper" "NOTE_ERROR:project-incompatible:stubw" \
    700 --project stubw --from 700 --text x
expect_refused "5u. pre-t1869 helper cannot take a WRITE" "NOTE_ERROR:project-incompatible:stubr" \
    700 --project stubr --from 700 --text x

# Source identity from the registry: unregistered, then registered twice.
{ echo "projects:"; printf '  - name: tgtfx\n    path: %s\n' "$TGT"; } > "$BASE/nosrc.yaml"
before="$(state)"
out="$( cd "$SRC" && AITASKS_PROJECTS_INDEX="$BASE/nosrc.yaml" ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text x 2>/dev/null )"
assert_eq "5v. unregistered source is refused, never invented" "NOTE_ERROR:source-unregistered" "$out"
assert_eq "5w. ... nothing mutated" "$before" "$(state)"
printf '  - name: srcalias\n    path: %s\n' "$SRC" | write_registry
expect_refused "5x. source registered under two names" \
    "NOTE_ERROR:source-ambiguous:srcfx,srcalias" \
    700 --project tgtfx --from 700 --text x
out="$(run_src 700 --project tgtfx --from-project srcalias --from 700 --text "chosen alias")"
assert_contains "5y. --from-project picks one of them" "|$TGT/aitasks/t700_x.md" "$out"
assert_contains "5z. ... and it is the stored sender" "from=srcalias#t700" "$(tgt_body 700)"
write_registry </dev/null

# A REAL unreadable registry (not the forced seam) fails closed end to end.
if [[ "$(id -u)" != 0 ]]; then
    cp "$REG" "$BASE/unreadable.yaml"; chmod 000 "$BASE/unreadable.yaml"
    before="$(state)"
    out="$( cd "$SRC" && AITASKS_PROJECTS_INDEX="$BASE/unreadable.yaml" AITASKS_PROJECT_tgtfx="$TGT" \
        ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text x 2>/dev/null )"
    assert_eq "5za. unreadable registry fails closed despite an env binding" \
        "NOTE_ERROR:project-resolution-incomplete:registry" "$out"
    assert_eq "5zb. ... nothing mutated" "$before" "$(state)"
    chmod 644 "$BASE/unreadable.yaml"
fi

# A registry in an unsearchable directory is "could not look", not "absent".
if [[ "$(id -u)" != 0 ]]; then
    mkdir -p "$BASE/locked"; cp "$REG" "$BASE/locked/projects.yaml"; chmod 000 "$BASE/locked"
    before="$(state)"
    out="$( cd "$SRC" && AITASKS_PROJECTS_INDEX="$BASE/locked/projects.yaml" AITASKS_PROJECT_tgtfx="$TGT" \
        ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text x 2>/dev/null )"
    assert_eq "5ze. unsearchable registry dir fails closed despite an env binding" \
        "NOTE_ERROR:project-resolution-incomplete:registry" "$out"
    assert_eq "5zf. ... nothing mutated" "$before" "$(state)"
    chmod 755 "$BASE/locked"
fi

# --from-project is only the target half of a ROUTED call. Used standalone, the
# calling repository is the one the command runs in, so no foreign project can
# be claimed as the sender — even one that exists and holds that task.
before="$(state)"
out="$(run_in "$TGT" 700 --from 700 --from-project srcfx --text "standalone claim")"
assert_eq "5zg. standalone --from-project is refused" \
    "NOTE_ERROR:from-project-requires-project" "$out"
assert_eq "5zh. ... nothing mutated" "$before" "$(state)"
# A handoff naming a different repository than the claimed sender is refused.
out="$( cd "$TGT" && AIT_NOTE_XREPO_CALLER="$LEG" ./.aitask-scripts/aitask_note.sh 700 --from 700 --from-project srcfx --text x 2>/dev/null )"
assert_eq "5zi. handoff and claimed sender must be the same repository" \
    "NOTE_ERROR:from-project-mismatch:srcfx" "$out"
assert_eq "5zj. ... nothing mutated" "$before" "$(state)"

# The sender's only declared name reaches two checkouts: report THAT, not
# "unregistered" — the fix is repairing a registration, not adding one.
before="$(state)"
out="$( cd "$SRC" && AITASKS_PROJECT_srcfx="$LEG" ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --text x 2>/dev/null )"
assert_eq "5zc. conflicting sender name keeps its real reason" \
    "NOTE_ERROR:project-ambiguous:srcfx" "$out"
assert_eq "5zd. ... nothing mutated" "$before" "$(state)"

# --- 6. Read receipts --------------------------------------------------------

rc=0
out="$(run_src read 700 --project tgtfx --by 700 --ids "$NOTE1" --mode explicit)" || rc=$?
assert_contains_re "6a. READ_RECORDED with an absolute target path" \
    "^READ_RECORDED(_UNPUSHED)?:[^|]+\|$TGT/aitasks/t700_x\.md\|1$" "$out"
assert_eq "6b. exit 0" "0" "$rc"
assert_eq "6c. receipt committed on the target's aitask-data branch" \
    "ait: Record note read receipt for t700" \
    "$(git -C "$TGT/.aitask-data" log -1 --format=%s -- aitasks/t700_x.md)"
inbox="$( cd "$TGT" && ./.aitask-scripts/aitask_query_files.sh inbox 700 2>/dev/null )"
assert_not_contains "6d. the note is no longer unread in the target" "|$NOTE1|" "$inbox"

out="$(run_src 700 --project tgtfx --from 700 --text "to be read with a failing commit")"
NOTE2="$(printf '%s' "$out" | sed -n 's/^NOTE_APPENDED:\([^|]*\)|.*/\1/p')"
receipts_before="$(grep -c 'note:read' "$TGT/aitasks/t700_x.md")"
out="$( cd "$SRC" && AIT_NOTE_READ_FAIL_COMMIT=1 ./.aitask-scripts/aitask_note.sh read 700 --project tgtfx --by 700 --ids "$NOTE2" --mode explicit 2>/dev/null )"
assert_eq "6e. commit failure => READ_ERROR (rolled back)" "READ_ERROR:git-commit-failed" "$out"
assert_eq "6f. ... no receipt left behind" "$receipts_before" "$(grep -c 'note:read' "$TGT/aitasks/t700_x.md")"
assert_eq "6g. ... target data worktree clean" "" "$(git -C "$TGT/.aitask-data" status --porcelain)"

expect_read_refused() {   # <desc> <expected> <args...>
    local desc="$1" want="$2"; shift 2
    local before out
    before="$(state)"
    out="$(run_src read "$@")"
    assert_eq "$desc" "$want" "$out"
    assert_eq "$desc: nothing mutated" "$before" "$(state)"
}
expect_read_refused "6h. --by must be the target task" "READ_ERROR:by-must-be-target:701" \
    700 --project tgtfx --by 701 --ids "$NOTE2"
expect_read_refused "6i. read: duplicate --project" "READ_ERROR:duplicate-option:--project" \
    700 --project tgtfx --project legfx --by 700 --ids "$NOTE2"
expect_read_refused "6j. read: unknown project (READ_* family, never NOTE_*)" \
    "READ_ERROR:project-not-found:nosuch" 700 --project nosuch --by 700 --ids "$NOTE2"
expect_read_refused "6k. read: incompatible target" "READ_ERROR:project-incompatible:stubw" \
    700 --project stubw --by 700 --ids "$NOTE2"
out="$( cd "$SRC" && AIT_PROJECT_RESOLVE_ENUM_FAIL=registry ./.aitask-scripts/aitask_note.sh read 700 --project tgtfx --by 700 --ids "$NOTE2" 2>/dev/null )"
assert_eq "6l. read: unreadable tier fails closed" \
    "READ_ERROR:project-resolution-incomplete:registry" "$out"

# A target that predates t1869 but has the receipt verb is fully usable.
out="$(run_src read 700 --project stubr --by 700 --ids "$NOTE2" --mode explicit)"
assert_eq "6m. pre-t1869 read helper: routed, path made absolute" \
    "READ_RECORDED:2026-01-01T00:00:00Z.aaaaaaaaaaaaaaaaaaaaaaaa|$STUBR/aitasks/t700_x.md|1" "$out"
assert_eq "6n. ... given only the existing receipt grammar" \
    "read 700 --by 700 --ids $NOTE2 --mode explicit" "$(cat "$STUBR/argv")"

# --- 7. Live lane: durable first, passed through verbatim -------------------

rc=0
out="$(run_src 700 --project tgtfx --from 700 --with-live --text "live probe")" || rc=$?
assert_contains_re "7a. durable line first" "^NOTE_APPENDED:[^|]+\|$TGT/" "$(head -n1 <<<"$out")"
assert_eq "7b. no holder => LIVE_NONE:unlocked" "LIVE_NONE:unlocked" "$(sed -n 2p <<<"$out")"
assert_eq "7c. exit 0 (durable result is authoritative)" "0" "$rc"
cat > "$BASE/live_stub.sh" <<'EOF'
#!/usr/bin/env bash
echo "LIVE_PANE:%9|s:@1.%9|123|agent=claudecode"
EOF
chmod +x "$BASE/live_stub.sh"
out="$( cd "$SRC" && AIT_LIVE_ENDPOINT_SH="$BASE/live_stub.sh" ./.aitask-scripts/aitask_note.sh 700 --project tgtfx --from 700 --with-live --text "stubbed live" 2>/dev/null )"
assert_eq "7d. LIVE_* passes through verbatim, after the append" \
    "LIVE_PANE:%9|s:@1.%9|123|agent=claudecode" "$(sed -n 2p <<<"$out")"

# --- 8. Local invocation unchanged -----------------------------------------

out="$(run_src 700 --from 701 --text "plain local")"
assert_contains_re "8a. no --project: one local line, relative path" \
    '^NOTE_APPENDED:[^|]+\|aitasks/t700_x\.md$' "$out"
assert_eq "8b. exactly one stdout line" "1" "$(printf '%s\n' "$out" | grep -c .)"
assert_contains "8c. local bare sender" "from=t701" "$(cat "$SRC/aitasks/t700_x.md")"

# --- 9. Legacy-mode target smoke --------------------------------------------

leg_before="$(git -C "$LEG" rev-parse HEAD)"
out="$(run_src 700 --project legfx --from 700 --text "legacy target")"
assert_contains "9a. legacy target: absolute path" "|$LEG/aitasks/t700_x.md" "$out"
assert_eq "9b. legacy target: committed on its code branch" "1" \
    "$(git -C "$LEG" rev-list --count "$leg_before"..HEAD)"
assert_contains "9c. legacy target: qualified sender" "from=srcfx#t700" "$(cat "$LEG/aitasks/t700_x.md")"

# --- 10. Commit failure on the target: id-bearing, terminal, absolute --------
# Last: it leaves an uncommitted note in the target, as the contract says.

wt_gitdir="$(git -C "$TGT/.aitask-data" rev-parse --absolute-git-dir)"
touch "$wt_gitdir/index.lock"
rc=0
out="$(run_src 701 --project tgtfx --from 700 --text "uncommitted")" || rc=$?
rm -f "$wt_gitdir/index.lock"
assert_contains_re "10a. NOTE_APPENDED_UNCOMMITTED with an absolute path" \
    "^NOTE_APPENDED_UNCOMMITTED:[^|]+\|$TGT/aitasks/t701_x\.md\|git-(add|commit)-failed$" "$out"
assert_eq "10b. non-zero exit" "1" "$(( rc != 0 ))"
assert_contains "10c. the note IS on disk (do not retry)" "> | uncommitted" "$(tgt_body 701)"

echo ""
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
