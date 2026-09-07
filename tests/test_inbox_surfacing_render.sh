#!/usr/bin/env bash
# test_inbox_surfacing_render.sh - Per-surface inbox-block assertions (t1657_3).
#
# WHY THIS EXISTS ALONGSIDE THE GOLDENS. A golden diff proves a render is
# byte-stable; it does not prove the block landed in the right STEP, under the
# right PROFILE, or that the surface which must never write a receipt still
# does not. Regenerating a golden makes any of those silently "correct".
#
# Four surfaces now carry near-identical inbox blocks and can drift apart:
#
#   aitask-pick          Step 0b, interactive vs headless acknowledgement
#   task-workflow        Step 3 Check 6, same split
#   aitask-pickrem       Step 2, unconditionally automatic
#   aitask-pickweb       Step 2, DISPLAY ONLY -- it makes no task-file writes
#                        at all, so a receipt there could never be durable
#
# Every assertion is paired with its negative control: "the auto branch is
# present" is worth little without "the interactive branch is absent", since a
# template that emitted both would satisfy the positive half alone.
#
# Run: bash tests/test_inbox_surfacing_render.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

cd "$PROJECT_DIR"

G="tests/golden"
PICK="$G/skills/aitask-pick"
WF="$G/procs/task-workflow"

# An INVOCATION, not a mention. The prohibition prose in aitask-pickweb says
# "Never run `ait note read` on this path", so a looser pattern would match the
# very file that must not carry a call and report a false failure.
INVOKE='\./\.aitask-scripts/aitask_note\.sh read'
# The read-only query. Safe anywhere, including a candidate listing.
QUERY='aitask_query_files\.sh inbox'

# has <label> <file> <extended-regex> <yes|no>
has() {
    local label="$1" file="$2" re="$3" want="$4" got
    TOTAL=$(( TOTAL + 1 ))
    if [[ ! -f "$file" ]]; then
        FAIL=$(( FAIL + 1 )); echo "FAIL: $label (missing golden: $file)"; return
    fi
    if grep -qE "$re" "$file"; then got=yes; else got=no; fi
    if [[ "$got" == "$want" ]]; then
        PASS=$(( PASS + 1 )); echo "PASS: $label"
    else
        FAIL=$(( FAIL + 1 ))
        echo "FAIL: $label (expected $want, got $got) [$file :: $re]"
    fi
}

echo "=== inbox surfacing, per surface and per profile (t1657_3) ==="

# --- 1. aitask-pick: the profile split -------------------------------------

has "1a. remote invokes the acknowledgement automatically" \
    "$PICK/SKILL-remote-claude.md" "$INVOKE.*--mode auto" yes
has "1b. remote asks NO acknowledgement question" \
    "$PICK/SKILL-remote-claude.md" 'Acknowledge these' no

for p in default fast; do
    has "1c[$p]. interactive profile asks before acknowledging" \
        "$PICK/SKILL-$p-claude.md" 'Acknowledge these' yes
    has "1d[$p]. ... and records mode=explicit" \
        "$PICK/SKILL-$p-claude.md" "$INVOKE.*--mode explicit" yes
    has "1e[$p]. ... and never auto-acknowledges" \
        "$PICK/SKILL-$p-claude.md" "$INVOKE.*--mode auto" no
done

# Both direct-selection formats get it: a parent picked by number and a child
# picked as <parent>_<child>.
has "1f. Step 0b Format 1 (parent) surfaces" \
    "$PICK/SKILL-fast-claude.md" "$QUERY <number>" yes
has "1g. Step 0b Format 2 (child) surfaces" \
    "$PICK/SKILL-fast-claude.md" "$QUERY <parent>_<child>" yes

# --- 2. The candidate listing stays read-only ------------------------------
#
# THE load-bearing one. If a listing acknowledged the notes of tasks the user
# did not choose, an agent that merely saw a task in a menu would hide that
# task's notes from the agent who later picks it.

for p in default fast remote; do
    has "2a[$p]. the listing rule is stated" \
        "$PICK/SKILL-$p-claude.md" 'THIS LISTING IS READ-ONLY' yes
    has "2b[$p]. the batched read-only query is used" \
        "$PICK/SKILL-$p-claude.md" "$QUERY <id1> <id2>" yes
    has "2c[$p]. unread count reaches the option descriptions" \
        "$PICK/SKILL-$p-claude.md" 'unread note' yes
done

# --- 3. task-workflow Step 3 Check 6 ---------------------------------------

has "3a. remote acknowledges automatically" \
    "$WF/SKILL-remote.md" "$INVOKE.*--mode auto" yes
has "3b. remote asks nothing" \
    "$WF/SKILL-remote.md" 'Acknowledge these' no
for p in default fast; do
    has "3c[$p]. interactive profile asks" "$WF/SKILL-$p.md" 'Acknowledge these' yes
    has "3d[$p]. ... and never auto-acknowledges" \
        "$WF/SKILL-$p.md" "$INVOKE.*--mode auto" no
done
has "3e. the check is numbered and named in every profile" \
    "$WF/SKILL-fast.md" 'Check 6 - Unread notes' yes
has "3f. it defers to the caller when already surfaced" \
    "$WF/SKILL-fast.md" 'inbox_surfaced' yes

# --- 4. aitask-pickrem: self-contained, writes receipts --------------------

PR="$G/skills/aitask-pickrem/SKILL-remote-claude.md"
has "4a. surfaces the inbox at all" "$PR" "$QUERY" yes
has "4b. acknowledges automatically" "$PR" "$INVOKE.*--mode auto" yes
has "4c. adds no interactive prompt" "$PR" 'Acknowledge these' no
# Position: the block belongs in Step 2 (right after the task is resolved), not
# somewhere later. A golden diff would not notice it moving.
has "4d. the block sits before Step 3" "$PR" \
    "$(printf '%s' 'Surface unread notes')" yes
if [[ -f "$PR" ]]; then
    n_surface=$(grep -n 'Surface unread notes' "$PR" | head -n1 | cut -d: -f1)
    n_step3=$(grep -n '^### Step 3' "$PR" | head -n1 | cut -d: -f1)
    TOTAL=$(( TOTAL + 1 ))
    if [[ -n "$n_surface" && -n "$n_step3" && "$n_surface" -lt "$n_step3" ]]; then
        PASS=$(( PASS + 1 )); echo "PASS: 4e. ... verified by line order ($n_surface < $n_step3)"
    else
        FAIL=$(( FAIL + 1 ))
        echo "FAIL: 4e. block is not inside Step 2 (surface=$n_surface step3=$n_step3)"
    fi
fi

# --- 5. aitask-pickweb: display only (the negative control) ----------------
#
# Web mode makes NO task-file writes (no aitask_update.sh, no ./ait git) and has
# no push access to the data branch, so a receipt could never become durable.
# Leaving the notes unread is the fail-safe direction.

PW="$G/skills/aitask-pickweb/SKILL-remote-claude.md"
has "5a. it DOES surface the notes" "$PW" 'INBOX_UNREAD' yes
has "5b. it NEVER invokes the receipt writer" "$PW" "$INVOKE" no
has "5c. ... and says so as a decision, not an omission" "$PW" 'Do NOT acknowledge' yes
has "5d. ... naming the fail-safe consequence" "$PW" 'next attended pick' yes

# --- 6. The trust posture survives rendering, on every surface -------------

for f in "$PICK/SKILL-fast-claude.md" "$WF/SKILL-fast.md" "$PR" "$PW"; do
    label="$(basename "$(dirname "$f")")/$(basename "$f")"
    has "6a[$label]. note is framed as untrusted advisory input" \
        "$f" 'untrusted advisory input' yes
    has "6b[$label]. sender is rendered as claimed" "$f" 'claimed' yes
    has "6c[$label]. dirty=yes is called out as a staleness warning" \
        "$f" 'dirty=yes' yes
done

echo
echo "Results: $PASS passed, $FAIL failed (of $TOTAL)"
[[ "$FAIL" -eq 0 ]]
