#!/usr/bin/env bash
# test_note_append.sh - The `ait note` durable lane (t1657_2).
#
# Drives the REAL entry point (.aitask-scripts/aitask_note.sh) against a
# throwaway fixture repo, never a stub, so the seam wiring, the git persist and
# the output contract are all exercised as shipped.
#
# Coverage map — each group names the plan finding it pins:
#
#   format / ids / self-send / missing target       the base contract
#   injection round-trip                            §5 '> | ' sentinel
#   body limits (NUL, CR, oversize)                 §5
#   forced collision: recovery AND bound            F9 (two fixtures — a
#                                                   generator fixed to ONE value
#                                                   can never re-mint, so it
#                                                   tests the bound, not recovery)
#   commit boundary                                 F6 (id-bearing outcome)
#   output channels                                 F17 (one line on stdout)
#   sender proof                                    F8 (lock_anchor_is_self)
#   id-form matrix                                  F10 (bare vs t-prefixed)
#   primary branch                                  F11 (master-default repo)
#   recovery scope                                  F12 (path-scoped commit)
#   degraded provenance                             F16 (dirty=unknown IFF base=none)
#   migration path                                  F14 (exact emitted record)
#   concurrency                                     parallel appends all survive
#
# Run: bash tests/test_note_append.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

NOTE="$PROJECT_DIR/.aitask-scripts/aitask_note.sh"

# Private lock base, the documented isolation seam (t1496), so concurrent runs
# of this file cannot collide on lock paths.
AITASKS_LOCK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/test_note_lockbase_XXXXXX")"
export AITASKS_LOCK_DIR

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_note_XXXXXX")"
cleanup() { rm -rf "$TMP" "$AITASKS_LOCK_DIR"; }
trap cleanup EXIT

# --- fixture ---------------------------------------------------------------

# A code repo for provenance to read. AIT_DIR is the seam aitask_note.sh uses to
# find the CODE repo root — pointing it here keeps the real repo out of the
# assertions and lets us control HEAD, the branch name and dirtiness.
CODE="$TMP/code"
mkdir -p "$CODE"
git -C "$CODE" init -q -b main
git -C "$CODE" config user.email t@example.com
git -C "$CODE" config user.name Test
echo one > "$CODE/f.txt"
git -C "$CODE" add -A && git -C "$CODE" commit -qm first
CODE_HEAD="$(git -C "$CODE" rev-parse HEAD)"

# The task-data repo. `ait note` commits the task file path-scoped through
# task_git, which in legacy mode (no .aitask-data worktree) is plain git.
#
# It is a CLONE of a bare remote, not a bare `git init`: aitask_lock.sh keeps
# locks on an 'aitask-locks' orphan branch and refuses to operate without an
# 'origin'. Without that the sender-proof group below cannot fire at all — and a
# suite that only ever sees "no lock record" would pass while `from_verified`
# was unreachable, which is exactly the dead-feature hazard F10 describes.
REMOTE="$TMP/remote.git"
git init -q --bare -b main "$REMOTE"
DATA="$TMP/data"
git clone -q "$REMOTE" "$DATA" 2>/dev/null
mkdir -p "$DATA/aitasks"
git -C "$DATA" config user.email t@example.com
git -C "$DATA" config user.name Test

make_task() {
    local id="$1"
    cat > "$DATA/aitasks/t${id}_x.md" <<EOF
---
status: Ready
---
Body for t${id}.
EOF
}
for id in 700 701 702 703 704 705 706; do make_task "$id"; done
git -C "$DATA" add -A && git -C "$DATA" commit -qm "tasks"
git -C "$DATA" push -q origin main 2>/dev/null || true
# Create the lock branch so aitask_lock.sh has infrastructure to work with.
( cd "$DATA" && "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" --init ) >/dev/null 2>&1 || true

# Run the real script inside the data repo with provenance pointed at $CODE.
run_note() { ( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" "$@" ); }

task_body() { cat "$DATA/aitasks/t${1}_x.md"; }

echo "=== ait note: durable lane (t1657_2) ==="

# --- 1. The base contract --------------------------------------------------

out="$(run_note 700 --from 701 --text "hello inbox" 2>/dev/null)"
assert_contains_re "1a. NOTE_APPENDED with an id and a path" \
    '^NOTE_APPENDED:[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:]+Z\.[0-9a-f]{24}\|aitasks/t700_x\.md$' "$out"

body="$(task_body 700)"
assert_contains "1b. section header created"  "## Inbox" "$body"
assert_contains "1c. marker names the sender" "**✉ note:t701**" "$body"
assert_contains "1d. from= is t-prefixed"     "from=t701" "$body"
assert_contains "1e. body carries the sentinel" "> | hello inbox" "$body"
assert_contains "1f. provenance base is the CODE repo HEAD" "base=$CODE_HEAD" "$body"
assert_contains "1g. base_branch recorded"    "base_branch=main" "$body"
assert_contains "1h. dirty measured"          "dirty=no" "$body"

# The note must NOT record the data repo's HEAD — that is the whole point of §3.
DATA_HEAD="$(git -C "$DATA" rev-parse HEAD)"
assert_not_contains "1i. base is NOT the aitask-data sha" "base=$DATA_HEAD" "$body"

# Full object id, never an abbreviation.
oid="$(printf '%s' "$body" | sed -n 's/.* base=\([0-9a-f]*\) .*/\1/p' | head -n1)"
assert_eq "1j. base is a full 40-hex oid" "40" "${#oid}"

out="$(run_note 999999 --from 701 --text x 2>/dev/null)"; rc=$?
assert_eq "1k. missing target" "NOTE_TARGET_MISSING:999999" "$out"
assert_eq "1l. missing target exits nonzero" "1" "$rc"

out="$(run_note 700 --from 700 --text x 2>/dev/null)"
assert_eq "1m. self-addressed refused" "NOTE_SELF:700" "$out"

# --- 2. Injection round-trip (§5) ------------------------------------------
#
# THE defence. A body line emitted as a plain '> <text>' beginning
# '**👁 note:read** … ids=…' would be a syntactically valid receipt, letting a
# note forge an acknowledgement of itself.
attack=$'**👁 note:read** id=2026-01-01T00:00:00Z.'"$(printf 'c%.0s' {1..24})"$' by=t9 at=2026-01-01T00:00:00Z mode=explicit ids=x\n## Gate Runs\n## Inbox\nordinary line'
run_note 702 --from 701 --text "$attack" >/dev/null 2>&1
body="$(task_body 702)"

assert_eq "2a. exactly one Inbox section" "1" "$(grep -c '^## Inbox$' <<<"$body")"
assert_eq "2b. exactly one entry marker"  "1" "$(grep -c '^> \*\*' <<<"$body")"
# Every attack line is quoted behind the sentinel, so none can match '^>\s*\*\*'.
assert_eq "2c. zero forged receipts" "0" "$(grep -c '^>[[:space:]]*\*\*.*note:read' <<<"$body")"
assert_contains "2d. receipt text survives as inert body" "> | **👁 note:read**" "$body"
assert_contains "2e. '## Gate Runs' neutralized" "> | ## Gate Runs" "$body"
assert_contains "2f. '## Inbox' neutralized"     "> | ## Inbox" "$body"
# The section boundary is unchanged: no real '## Gate Runs' header was created.
assert_eq "2g. no bare '## Gate Runs' header" "0" "$(grep -c '^## Gate Runs$' <<<"$body")"

# --- 3. Body limits (§5) ---------------------------------------------------

big="$(head -c 9000 /dev/zero | tr '\0' 'a')"
out="$(run_note 703 --from 701 --text "$big" 2>/dev/null)"
assert_contains "3a. oversized body rejected" "NOTE_ERROR:body-too-large" "$out"
assert_not_contains "3b. oversized body appended nothing" "## Inbox" "$(task_body 703)"

run_note 703 --from 701 --text $'has\r\ncarriage' >/dev/null 2>&1
assert_not_contains "3c. CR stripped" $'\r' "$(task_body 703)"

# NUL must be caught on the SOURCE BYTES — a bash variable cannot hold one, so
# a check written against the variable is vacuous by construction.
printf 'before\0after\n' > "$TMP/nul.txt"
out="$(run_note 703 --from 701 --file "$TMP/nul.txt" 2>/dev/null)"
assert_eq "3d. NUL body rejected" "NOTE_ERROR:body-contains-nul" "$out"

# --- 4. Forced collision — TWO fixtures (F9) -------------------------------
#
# The seam is the WHOLE id, not the suffix: an id is "<iso>.<suffix>", so two
# calls a second apart differ even with an identical suffix, and a suffix-only
# collision test would pass without ever exercising the re-mint.

FIXED_A="2030-01-01T00:00:00Z.$(printf 'a%.0s' {1..24})"
FIXED_B="2030-01-01T00:00:01Z.$(printf 'b%.0s' {1..24})"

# 4a-c. RECOVERY: a scripted collide-then-unique sequence.
run_note_id() { ( cd "$DATA" && AIT_DIR="$CODE" AIT_NOTE_ID_CMD="$1" "$NOTE" "${@:2}" ); }

run_note_id "printf '%s' '$FIXED_A'" 705 --from 701 --text "first" >/dev/null 2>&1
assert_contains "4a. seeded note carries the pinned id" "id=$FIXED_A" "$(task_body 705)"

seq="$TMP/idseq"; printf '1' > "$seq"
out="$(run_note_id 'n=$(cat '"$seq"'); if [ "$n" = 1 ]; then printf 2 > '"$seq"'; printf %s "'"$FIXED_A"'"; else printf %s "'"$FIXED_B"'"; fi' \
      705 --from 701 --text "second" 2>/dev/null)"
assert_eq "4b. re-mints past the collision to the second value" \
    "NOTE_APPENDED:$FIXED_B|aitasks/t705_x.md" "$out"
body="$(task_body 705)"
assert_eq "4c. the colliding id appears exactly once" "1" \
    "$(grep -c "id=$FIXED_A" <<<"$body")"
assert_eq "4d. two entries total" "2" "$(grep -c '^> \*\*' <<<"$body")"

# 4e-g. BOUND: a permanently-fixed generator must TERMINATE, not spin.
# This is the fixture a suffix-only seam could never build.
before="$(grep -c '^> \*\*' "$DATA/aitasks/t705_x.md")"
out="$(run_note_id "printf '%s' '$FIXED_A'" 705 --from 701 --text "dup" 2>/dev/null)"; rc=$?
assert_eq "4e. exhausts the retry bound" \
    "NOTE_ERROR:id-collision-retries-exhausted" "$out"
assert_eq "4f. and exits nonzero" "1" "$rc"
assert_eq "4g. having appended nothing" "$before" \
    "$(grep -c '^> \*\*' "$DATA/aitasks/t705_x.md")"

# --- 5. Commit boundary + output channels (F6, F17) ------------------------
#
# The note is committed path-scoped. When that commit fails the note is STILL on
# disk and owns an id, so reporting NOTE_ERROR would read as "nothing happened"
# and the caller's retry would append a SECOND note.

# Force the commit to fail by making the git index unwritable.
chmod -w "$DATA/.git" 2>/dev/null || true
stdout_f="$TMP/o"; stderr_f="$TMP/e"
( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" 706 --from 701 --text "uncommitted" ) \
    > "$stdout_f" 2> "$stderr_f"; rc=$?
chmod +w "$DATA/.git" 2>/dev/null || true

out="$(cat "$stdout_f")"; err="$(cat "$stderr_f")"
assert_contains "5a. id-bearing uncommitted outcome" "NOTE_APPENDED_UNCOMMITTED:" "$out"
assert_eq "5b. and exits nonzero" "1" "$rc"
assert_not_contains "5c. NOTE_ERROR is NEVER emitted once the append landed" \
    "NOTE_ERROR" "$out"
assert_contains "5d. the note is on disk exactly once" "> | uncommitted" "$(task_body 706)"
assert_eq "5e. appended exactly one entry" "1" \
    "$(grep -c '^> \*\*' "$DATA/aitasks/t706_x.md")"

# F17 — stdout is the machine channel: exactly one line, always.
assert_eq "5f. stdout is exactly one line" "1" "$(grep -c . "$stdout_f")"
assert_contains_re "5g. and matches the contract" \
    '^NOTE_APPENDED_UNCOMMITTED:[^|]+\|[^|]+\|[^|]+$' "$out"
# The path-scoped recovery hint is guidance, not data — it belongs on stderr.
assert_contains "5h. recovery hint is on stderr" "./ait git add --" "$err"
assert_not_contains "5i. and never on stdout" "./ait git add" "$out"
# It must name the ONE file, never a blanket 'aitasks/' path: task data is a
# shared multi-writer branch and a blanket add would sweep up another session's
# uncommitted work.
assert_contains "5j. hint is scoped to the note's own path" \
    "aitasks/t706_x.md" "$err"
assert_not_contains "5k. hint never says 'add aitasks/'" "add aitasks/ " "$err"

# stdout survives discarding stderr as a complete parseable record.
piped="$( ( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" 706 --from 701 --text "clean" ) 2>/dev/null )"
assert_eq "5l. stdout survives 2>/dev/null as one line" "1" \
    "$(printf '%s\n' "$piped" | grep -c .)"

# --- 6. Sender proof (F8) --------------------------------------------------
#
# `from=` is a CLAIM. The append lock is keyed on the TARGET, so it proves
# nothing about the sender: without a separate check any caller could present an
# arbitrary --from as verified.
#
# The positive case is the one that matters most. A suite covering only the
# negatives would pass on a feature that never writes the field at all — which
# is exactly what the t-prefix id bug (F10) would have caused.

body="$(task_body 700)"
assert_not_contains "6a. unlocked sender is NOT verified" "from_verified" "$body"

# Positive: hold the sender's lock as THIS session, then send.
LOCK="$PROJECT_DIR/.aitask-scripts/aitask_lock.sh"
if ( cd "$DATA" && "$LOCK" 701 --email t@example.com ) >/dev/null 2>&1; then
    run_note 702 --from 701 --text "verified send" >/dev/null 2>&1
    assert_contains "6b. sender locked by THIS session IS verified" \
        "from_verified=yes" "$(task_body 702)"
    ( cd "$DATA" && "$LOCK" 701 --unlock ) >/dev/null 2>&1 || true
else
    echo "SKIP 6b: could not acquire a sender lock in the fixture"
fi

# The field is never written as 'no' — absence and disproof must stay distinct,
# so a reader can tell "not proven" from "proven false".
assert_eq "6c. from_verified is never written as 'no'" "0" \
    "$(grep -rl 'from_verified=no' "$DATA/aitasks/" 2>/dev/null | grep -c . )"

# --- 7. Id-form matrix (F10) -----------------------------------------------
#
# Measured on the real helpers: `aitask_lock.sh --check t1669` prints NOTHING
# while `--check 1669` works, and resolve_task_file ERRORS on a 't' prefix. Both
# spellings must therefore reach the same task, and the STORED form must be
# t-prefixed regardless of which was typed.

for target in 704 t704; do
    for sender in 701 t701; do
        out="$(run_note "$target" --from "$sender" --text "m $target $sender" 2>/dev/null)"
        assert_contains "7. ${target}/${sender} resolves to t704" \
            "|aitasks/t704_x.md" "$out"
    done
done
body="$(task_body 704)"
assert_eq "7e. every stored sender is t-prefixed" "0" \
    "$(grep -c 'from=701' <<<"$body")"
assert_eq "7f. four entries landed" "4" "$(grep -c '^> \*\*' <<<"$body")"

out="$(run_note 'bogus!' --from 701 --text x 2>/dev/null)"
assert_eq "7g. malformed target is a typed error, not an empty answer" \
    "NOTE_ERROR:bad-task-id:bogus!" "$out"
out="$(run_note 700 --from 'nope' --text x 2>/dev/null)"
assert_eq "7h. malformed sender likewise" "NOTE_ERROR:bad-task-id:nope" "$out"

# --- 8. Primary branch (F11) -----------------------------------------------
#
# `detect_primary_branch()` resolves origin/HEAD, then main, then master. This
# is framework code shipped into other people's repos, so a hardcoded 'main'
# would compute the wrong merge base — or none — in a master-default repo.

MASTER="$TMP/master_repo"
mkdir -p "$MASTER"
git -C "$MASTER" init -q -b master
git -C "$MASTER" config user.email t@example.com
git -C "$MASTER" config user.name Test
echo a > "$MASTER/f.txt"
git -C "$MASTER" add -A && git -C "$MASTER" commit -qm base
MASTER_BASE="$(git -C "$MASTER" rev-parse HEAD)"
git -C "$MASTER" checkout -q -b feature
echo b > "$MASTER/g.txt"
git -C "$MASTER" add -A && git -C "$MASTER" commit -qm feat

( cd "$DATA" && AIT_DIR="$MASTER" "$NOTE" 706 --from 701 --text "off master" ) >/dev/null 2>&1
body="$(task_body 706)"
assert_contains "8a. off-primary HEAD emits base_mergebase" "base_mergebase=" "$body"
assert_contains "8b. merge base is against master, not a hardcoded main" \
    "base_mergebase=$MASTER_BASE" "$body"
assert_contains "8c. base_branch is the feature branch" "base_branch=feature" "$body"

# --- 9. Degraded provenance (F16) ------------------------------------------
#
# `dirty=unknown` IFF `base=none`. Requiring yes/no unconditionally would be
# unsatisfiable with no repository: 'no' fabricates a clean-state claim and
# 'yes' is equally unsupported.

NOREPO="$TMP/norepo"; mkdir -p "$NOREPO"
( cd "$DATA" && AIT_DIR="$NOREPO" "$NOTE" 703 --from 701 --text "no repo" ) >/dev/null 2>&1
# Assert on the LAST marker, not the whole file: t703 already carries entries
# from earlier groups, and a whole-file assertion would read their provenance.
last="$(grep '^> \*\*' "$DATA/aitasks/t703_x.md" | tail -n1)"
assert_contains "9a. no repository emits base=none" "base=none" "$last"
assert_contains "9b. and dirty=unknown"             "dirty=unknown" "$last"
assert_not_contains "9c. never dirty=no with no repository" "dirty=no" "$last"
assert_not_contains "9d. and no base_branch (no repo => no branch)" \
    "base_branch=" "$last"

# The trigger is base=none ALONE. On an unborn branch `git rev-parse HEAD` fails
# but `git status` still reports, so dirty is MEASURED there — 'unknown' would
# be a false disclaimer.
UNBORN="$TMP/unborn"; mkdir -p "$UNBORN"
git -C "$UNBORN" init -q -b main
echo x > "$UNBORN/untracked.txt"
( cd "$DATA" && AIT_DIR="$UNBORN" "$NOTE" 705 --from 701 --text "unborn" ) >/dev/null 2>&1
last="$(grep '^> \*\*' "$DATA/aitasks/t705_x.md" | tail -n1)"
assert_contains "9e. unborn branch emits base=unknown" "base=unknown" "$last"
assert_contains "9f. with a MEASURED dirty, not the sentinel" "dirty=yes" "$last"
assert_not_contains "9g. dirty is not 'unknown' where it is measurable" \
    "dirty=unknown" "$last"

# --- 10. Migration path (F14) ----------------------------------------------
#
# The only writer of an external sender. `from_verified` is omitted
# STRUCTURALLY — this path never calls the proof — and no dirty/host is written,
# because neither was ever observed.

out="$(run_note 706 --migrate --claimed-from "thinking_app#357" \
        --claimed-at "2026-09-01" --base "$CODE_HEAD" --base-branch main \
        --text "historical note" 2>/dev/null)"
assert_contains "10a. migration appends" "NOTE_APPENDED:" "$out"
last="$(grep '^> \*\*' "$DATA/aitasks/t706_x.md" | tail -n1)"
assert_contains "10b. marker name is the LOCAL part" "note:t357" "$last"
assert_contains "10c. from= keeps the cross-repo reference" \
    "from=thinking_app#357" "$last"
assert_contains "10d. migrated=yes"    "migrated=yes" "$last"
assert_contains "10e. claimed_at recorded" "claimed_at=2026-09-01" "$last"
assert_not_contains "10f. from_verified absent"  "from_verified" "$last"
assert_not_contains "10g. dirty absent (never observed)" "dirty=" "$last"
assert_not_contains "10h. host absent (never observed)"  "host=" "$last"

out="$(run_note 706 --migrate --claimed-from "BAD REF" --claimed-at 2026-09-01 \
        --base "$CODE_HEAD" --text x 2>/dev/null)"
assert_contains "10i. malformed claimed-from rejected" "NOTE_ERROR:bad-claimed-from" "$out"
# The narrow scope holds: plain --from still refuses a cross-repo value.
out="$(run_note 706 --from "thinking_app#357" --text x 2>/dev/null)"
assert_contains "10j. plain --from rejects a cross-repo sender" \
    "NOTE_ERROR:bad-task-id" "$out"

# --- 12. Argument matrix + migration validation (F18, F19) -----------------
#
# What the writer COMMITS, the merger re-validates on every other PC. A value
# accepted here and rejected there turns a local migration into a cross-PC
# conflict source, and by then the block is already in git — so the writer must
# refuse the same things the merger does, BEFORE the append.

FULL_OID="$(printf 'a%.0s' {1..40})"

out="$(run_note 706 --migrate --claimed-from "thinking_app#357" \
        --claimed-at 2026-09-01 --base "451dd3af7" --base-branch main \
        --text x 2>/dev/null)"
assert_eq "12a. an abbreviated base is refused before the append" \
    "NOTE_ERROR:base-not-a-full-oid:451dd3af7" "$out"

out="$(run_note 706 --migrate --claimed-from "thinking_app#357" \
        --claimed-at "not-a-date" --base "$FULL_OID" --base-branch main \
        --text x 2>/dev/null)"
assert_eq "12b. a free-text claimed-at is refused" \
    "NOTE_ERROR:bad-claimed-at:not-a-date" "$out"

out="$(run_note 706 --migrate --claimed-from "thinking_app#357" \
        --claimed-at 2026-09-01 --base none --base-branch main --text x 2>/dev/null)"
assert_eq "12c. a branch beside a sentinel base is refused" \
    "NOTE_ERROR:base-branch-with-sentinel-base:none" "$out"

out="$(run_note 706 --migrate --claimed-from "thinking_app#357" \
        --claimed-at 2026-09-01 --base "$FULL_OID" --text x 2>/dev/null)"
assert_eq "12d. a real base REQUIRES a branch" \
    "NOTE_ERROR:migrate-requires-base-branch" "$out"

# A refusal must leave nothing behind — these run before the lock and the append.
assert_eq "12e. every refusal above appended nothing" "0" \
    "$(grep -c 'base=451dd3af7' "$DATA/aitasks/t706_x.md")"

# Body sources: exactly one, no repeats. Silently preferring --file would drop
# the caller's inline text with no error.
echo "from file" > "$TMP/b.txt"
out="$(run_note 706 --from 701 --text "from text" --file "$TMP/b.txt" 2>/dev/null)"
assert_contains "12f. --text with --file is refused, not silently resolved" \
    "NOTE_ERROR:need-exactly-one-body-source" "$out"
out="$(run_note 706 --from 701 2>/dev/null)"
assert_contains "12g. no body source at all is refused" \
    "NOTE_ERROR:need-exactly-one-body-source" "$out"
out="$(run_note 706 --from 701 --text a --text b 2>/dev/null)"
assert_eq "12h. a duplicate flag names ITSELF, not the arity rule" \
    "NOTE_ERROR:duplicate-option:--text" "$out"
out="$(run_note 706 --from 701 --from 702 --text a 2>/dev/null)"
assert_eq "12i. duplicate --from" "NOTE_ERROR:duplicate-option:--from" "$out"

# The two modes are mutually exclusive: a flag that would be IGNORED must be
# refused, or the caller believes something the note does not say.
out="$(run_note 706 --migrate --from 701 --claimed-from "x#1" \
        --claimed-at 2026-09-01 --base "$FULL_OID" --base-branch main \
        --text x 2>/dev/null)"
assert_eq "12j. --from is refused with --migrate (the proof never runs)" \
    "NOTE_ERROR:from-not-valid-with-migrate" "$out"
out="$(run_note 706 --from 701 --base "$FULL_OID" --text x 2>/dev/null)"
assert_eq "12k. migration provenance is refused without --migrate" \
    "NOTE_ERROR:migration-options-require-migrate" "$out"

# Every error line stays a single parseable record even though the messages
# carry a '/' where a '|' would have split the field.
out="$(run_note 706 --from 701 --text a --file "$TMP/b.txt" 2>/dev/null)"
assert_eq "12l. a refusal is still exactly one stdout line" "1" \
    "$(printf '%s\n' "$out" | grep -c .)"

# --- 13. Never exit silently (F21) -----------------------------------------
#
# The contract is "exactly ONE line on stdout, ALWAYS". Two paths violated it by
# dying instead of reporting, and both left the caller unable to tell malformed
# input from a died process:
#
#   * a value-taking flag with no value -> `shift 2` fails under `set -e`
#   * lock exhaustion                   -> the seam's `die` exits past us
#
# Every value-taking flag, so a future flag added without its guard is caught.
for flag in --from --text --file --claimed-from --claimed-at --base --base-branch; do
    out="$(run_note 700 "$flag" 2>/dev/null)"
    assert_eq "13. ${flag} with no value is typed, not silent" \
        "NOTE_ERROR:missing-value:${flag}" "$out"
done

# ...and the same in the middle of an otherwise valid command line.
out="$(run_note 700 --from 701 --text 2>/dev/null)"
assert_eq "13h. a trailing valueless flag is typed" \
    "NOTE_ERROR:missing-value:--text" "$out"

# Lock exhaustion: pre-hold the target's note lock so acquisition cannot win.
mkdir -p "$AITASKS_LOCK_DIR/note_802"
make_task 802
out="$(run_note 802 --from 701 --text "blocked" 2>/dev/null)"; rc=$?
assert_eq "13i. lock exhaustion is a typed outcome, not a silent death" \
    "NOTE_ERROR:lock-unavailable:802" "$out"
assert_eq "13j. and exits nonzero" "1" "$rc"
# The seam's own wording still reaches stderr — converting the death must not
# swallow the diagnostic that says WHICH lock and where.
err="$(run_note 802 --from 701 --text "blocked" 2>&1 >/dev/null)"
assert_contains "13k. the seam's lock diagnostic survives on stderr" \
    "note append lock" "$err"
rm -rf "$AITASKS_LOCK_DIR/note_802"

# Whatever the outcome, stdout is one line. This is the invariant the whole
# group exists to protect.
for args in "--from" "--from 701 --text a --file /dev/null" "--from 701"; do
    # shellcheck disable=SC2086  # intentional: $args IS the argument list.
    out="$(run_note 700 $args 2>/dev/null)"
    assert_eq "13l. one stdout line for: $args" "1" \
        "$(printf '%s\n' "$out" | grep -c .)"
done

# --- 11. Concurrency -------------------------------------------------------
#
# Two senders appending to one inbox WILL race. Every entry must survive.

make_task 800; ( cd "$DATA" && git add -A && git commit -qm t800 ) >/dev/null 2>&1
for i in 1 2 3 4 5; do
    ( cd "$DATA" && AIT_DIR="$CODE" "$NOTE" 800 --from 701 --text "concurrent $i" ) \
        >/dev/null 2>&1 &
done
wait
assert_eq "11a. all five concurrent appends survive" "5" \
    "$(grep -c '^> \*\*' "$DATA/aitasks/t800_x.md")"
assert_eq "11b. and every id is unique" "5" \
    "$(grep -o 'id=[^ ]*' "$DATA/aitasks/t800_x.md" | sort -u | wc -l | tr -d ' ')"

# --- summary ---------------------------------------------------------------
echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
