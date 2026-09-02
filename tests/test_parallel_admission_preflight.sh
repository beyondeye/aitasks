#!/usr/bin/env bash
#
# test_parallel_admission_preflight.sh - the task-workflow preflight contract
# (t1569_4).
#
# `tests/test_parallel_admission_cli.sh` pins the CHECKER's exit-status split
# against the live corpus. This file pins the seam between that checker and the
# `parallel-admission.md` procedure that consumes it:
#
#   1. Every verdict the real helper can emit is PRODUCED from a synthetic repo
#      and has a disposition in the rendered procedure. Driven end-to-end
#      through the shell wrapper -- no injected probes, unlike
#      tests/test_parallel_admission_collect.py, whose CollectIntegrationTests
#      replace _LOCK_PROBE / _STATUS_PROBE / _TRACKED_SETS with lambdas.
#   2. SELF-EXCLUSION through the REAL claim path: `aitask_pick_own.sh` (what
#      task-workflow Step 4 runs) writes the status AND the lock, and the
#      checker must then NOT see the candidate. The Python test's
#      `test_the_candidate_is_excluded_from_its_own_comparison` injects replica
#      probe dicts and so cannot see a regression in the WRITER. This can.
#      Without the exclusion every pick conflicts with its own plan.
#   3. The procedure's verdict table is COMPLETE against
#      lib/parallel_admission_vocab.py's closed VERDICTS tuple -- derived, not
#      restated -- and its invalid-output table covers the misuse states the
#      helper really produces.
#
# Every fixture is built fresh per invocation: `aitask_pick_own.sh` mutates the
# repo it runs in, so a shared root would make test 2 pass on the first run and
# mean something different on the second.
#
# Assertions run at top level / in functions, never in `( … )` subshells, so the
# in-process counters are correct without the file-backed opt-in.
#
# Run: bash tests/test_parallel_admission_preflight.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# shellcheck source=lib/asserts.sh
source "$SCRIPT_DIR/lib/asserts.sh"

PASS=0; FAIL=0; TOTAL=0

CHECKER="$PROJECT_DIR/.aitask-scripts/aitask_parallel_admission.sh"
WF="$PROJECT_DIR/.claude/skills/task-workflow"
PROC="$WF/parallel-admission.md"

TMPROOT="$(mktemp -d "${TMPDIR:-/tmp}/pa_preflight_XXXXXX")"
cleanup() { rm -rf "$TMPROOT"; }
trap cleanup EXIT

cd "$PROJECT_DIR" || exit 1

# ---------------------------------------------------------------------------
# Fixture: a real git repo the real CLI can probe.
#
# The checker reads a code corpus (`git ls-files`), a data corpus
# (`aitask-data`), a locks ref (`aitask-locks`, fetched from `origin` under
# --lock-freshness require-fresh), and task/plan files. All of those are real
# here; nothing is stubbed. `origin` points at the fixture itself so a
# require-fresh fetch genuinely succeeds -- that is the exact freshness mode the
# procedure mandates, so it is the one the test must exercise.
# ---------------------------------------------------------------------------
make_root() {
    local d="$1"
    mkdir -p "$d"/{aitasks,aiplans,src}
    git -C "$d" init -q -b main .
    git -C "$d" config user.email t@example.com
    git -C "$d" config user.name "T"
    echo alpha > "$d/src/alpha.py"
    echo beta  > "$d/src/beta.py"
    echo gamma > "$d/src/gamma.py"
    printf -- '---\nstatus: Implementing\npriority: high\nupdated_at: 2026-09-02 09:00\n---\n\ncandidate\n' \
        > "$d/aitasks/t100_me.md"
    printf '# plan\n\nEdit `src/alpha.py`.\n' > "$d/aiplans/p100_me.md"
    git -C "$d" add -A
    git -C "$d" commit -qm init
    git -C "$d" branch aitask-data HEAD
    git -C "$d" branch aitask-locks HEAD
    git -C "$d" remote add origin "$d"
    git -C "$d" fetch -q origin
}

# Add a SECOND in-flight task. $2 = plan body, or "" for no plan file at all.
add_inflight() {
    local d="$1" body="$2"
    printf -- '---\nstatus: Implementing\npriority: high\nupdated_at: 2026-09-02 09:00\n---\n\nother\n' \
        > "$d/aitasks/t200_other.md"
    [[ -n "$body" ]] && printf '%s\n' "$body" > "$d/aiplans/p200_other.md"
    git -C "$d" add -A
    git -C "$d" commit -qm inflight
    git -C "$d" branch -f aitask-data HEAD
    git -C "$d" fetch -q origin
}

verdict_of() { printf '%s\n' "$1" | sed -n 's/^VERDICT://p' | head -n1; }

run_check() {  # <root> [extra args…]
    local d="$1"; shift
    "$CHECKER" check --root "$d" --candidate 100 --from plan \
        --lock-freshness require-fresh "$@" 2>/dev/null
}

echo "=== 1. Every producible verdict has a disposition in the procedure ==="

proc_default="$(cat "$PROC")"

# --- CLEAR: a lone candidate, fresh locks, both corpora present -------------
d="$TMPROOT/clear"; make_root "$d"
out_clear="$(run_check "$d")"
assert_eq "CLEAR: a lone candidate with fresh locks" "CLEAR" "$(verdict_of "$out_clear")"
assert_not_contains "CLEAR: the candidate is not in its own comparison set" \
    "INFLIGHT:100" "$out_clear"

# --- CLEAR_CAVEATED: same repo, but the lock ref is only cached -------------
d="$TMPROOT/caveated"; make_root "$d"
out_cav="$("$CHECKER" check --root "$d" --candidate 100 --from plan \
    --lock-freshness allow-cached 2>/dev/null)"
assert_eq "CLEAR_CAVEATED: allow-cached downgrades rather than certifying" \
    "CLEAR_CAVEATED" "$(verdict_of "$out_cav")"
assert_contains "CLEAR_CAVEATED: names the unverified evidence" \
    "CAVEAT:locks|locks_cached" "$out_cav"
# The whole point of the third verdict: unverified evidence must not collapse
# into CLEAR. The assert_eq above already pins that exactly -- this pins the
# other half, that the caveat is CARRIED rather than dropped on the floor.
assert_contains "CLEAR_CAVEATED: the display names the unverified evidence" \
    "but evidence was unverified" "$out_cav"

# --- CONFLICT: a second in-flight task declaring the same file --------------
d="$TMPROOT/conflict"; make_root "$d"
add_inflight "$d" '# other

Edit `src/alpha.py`.'
out_conf="$(run_check "$d")"
assert_eq "CONFLICT: an in-flight task declares the candidate's file" \
    "CONFLICT" "$(verdict_of "$out_conf")"
assert_contains "CONFLICT: names the overlapping task and file" \
    "OVERLAP:200|specific" "$out_conf"

# --- UNCHECKABLE: an in-flight task with no plan at all ---------------------
d="$TMPROOT/unchk"; make_root "$d"
add_inflight "$d" ""
out_unchk="$(run_check "$d")"
assert_eq "UNCHECKABLE: an in-flight task with no declared surface" \
    "UNCHECKABLE" "$(verdict_of "$out_unchk")"
assert_contains "UNCHECKABLE: names the cause per source" \
    "UNCHECKABLE_CAUSE:inflight:200|no_plan" "$out_unchk"
# Missing evidence is never silently CLEAR -- the failure this verdict exists
# to prevent.
assert_not_contains "UNCHECKABLE: missing evidence never reads as CLEAR" \
    "VERDICT:CLEAR" "$out_unchk"

# Each produced verdict must have a row in the procedure's disposition table.
for v in CLEAR CLEAR_CAVEATED CONFLICT UNCHECKABLE; do
    assert_contains "procedure has a disposition row for $v" \
        "| \`$v\` |" "$proc_default"
done

# …and the table is COMPLETE against the checker's own closed vocabulary,
# derived rather than restated, so a fifth verdict cannot be added upstream
# without this failing.
PY_BIN="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; require_ait_python )"
vocab_verdicts="$("$PY_BIN" -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
import parallel_admission_vocab as v
print(' '.join(v.VERDICTS))")"
missing_rows=""
for v in $vocab_verdicts; do
    printf '%s' "$proc_default" | grep -qF "| \`$v\` |" || missing_rows+="$v "
done
assert_eq "the procedure covers every member of vocab.VERDICTS" "" "$missing_rows"

echo "=== 2. Self-exclusion through the REAL Step-4 claim path ==="

# task-workflow Step 4 runs exactly this. It sets status Implementing AND takes
# the lock, both long before a plan exists -- so without the checker's exclusion
# the candidate overlaps 100% of its own plan and EVERY pick is a CONFLICT.
d="$TMPROOT/selfexcl"; make_root "$d"
mkdir -p "$d/.aitask-scripts/lib"
cp "$PROJECT_DIR/.aitask-scripts/aitask_pick_own.sh" \
   "$PROJECT_DIR/.aitask-scripts/aitask_lock.sh" \
   "$PROJECT_DIR/.aitask-scripts/aitask_update.sh" "$d/.aitask-scripts/"
cp "$PROJECT_DIR"/.aitask-scripts/lib/*.sh "$PROJECT_DIR"/.aitask-scripts/lib/*.py \
   "$d/.aitask-scripts/lib/" 2>/dev/null

own_out="$(cd "$d" && timeout 120 ./.aitask-scripts/aitask_pick_own.sh 100 \
    --email "t@example.com" 2>/dev/null)"
assert_contains "the real claim path reports ownership" "OWNED:100" "$own_out"

# Prove the claim actually landed on BOTH surfaces the checker probes. Without
# this the assertion below could pass because nothing was claimed at all.
assert_contains "the claim set status Implementing" "status: Implementing" \
    "$(cat "$d/aitasks/t100_me.md")"
assert_contains "the claim wrote a real lock on the locks ref" "t100_lock.yaml" \
    "$(git -C "$d" ls-tree -r --name-only aitask-locks)"

git -C "$d" fetch -q origin
out_self="$(run_check "$d")"
assert_eq "a really-claimed candidate is still CLEAR, not a self-conflict" \
    "CLEAR" "$(verdict_of "$out_self")"
assert_not_contains "…and emits no INFLIGHT row for itself" "INFLIGHT:100" "$out_self"
assert_not_contains "…and no OVERLAP against its own plan" "OVERLAP:" "$out_self"

# DISCRIMINATING CONTROL. A CLEAR proves self-exclusion only if this fixture is
# capable of conflicting at all -- otherwise the assertion above would pass just
# as happily against a checker that never reports anything. Add a SECOND task
# declaring the very same file and require the verdict to flip.
add_inflight "$d" '# other

Edit `src/alpha.py`.'
out_self_ctl="$(run_check "$d")"
assert_eq "control: the same fixture DOES conflict when a real second task overlaps" \
    "CONFLICT" "$(verdict_of "$out_self_ctl")"
# Not pinning the third field: it is a distinct-task touch count derived from
# commit history, which differs between fixtures. The CLASS and the PATH are the
# claim.
assert_contains "control: reported as a specific (not hub) overlap" \
    "OVERLAP:200|specific" "$out_self_ctl"
assert_contains "control: and it is the file the candidate's own plan declares" \
    "|src/alpha.py" "$out_self_ctl"
# The candidate is STILL excluded even while a genuine conflict is reported --
# the exclusion is not "report nothing".
assert_not_contains "control: the candidate is still absent from the comparison set" \
    "INFLIGHT:100" "$out_self_ctl"

echo "=== 3. Unusable checker output is UNCHECKABLE, never a pass ==="

# The two misuse states the real helper produces. Both must exit 2 and emit no
# verdict -- a silent verdict for a typo is the hazard the wrapper documents.
d="$TMPROOT/misuse"; make_root "$d"

"$CHECKER" check --root "$d" --from plan >/dev/null 2>&1
assert_eq "a missing --candidate exits 2" "2" "$?"
misuse_out="$("$CHECKER" check --root "$d" --from plan 2>/dev/null)"
assert_not_contains "…and emits no verdict for the procedure to act on" \
    "VERDICT:" "$misuse_out"

"$CHECKER" check --root "$d" --candidate 100 --plan /no/such/plan.md >/dev/null 2>&1
assert_eq "a nonexistent --plan target exits 2" "2" "$?"

# The procedure must route BOTH of those, and the states the helper cannot
# produce, to UNCHECKABLE rather than to a proceed.
assert_contains "procedure routes CLI misuse to UNCHECKABLE" \
    "| exit 2 (CLI misuse) | UNCHECKABLE" "$proc_default"
assert_contains "procedure routes any other non-zero exit to UNCHECKABLE" \
    "| any other non-zero exit, or a crash | UNCHECKABLE" "$proc_default"
assert_contains "procedure routes a missing VERDICT line to UNCHECKABLE" \
    "| empty stdout, or no \`VERDICT:\` line | UNCHECKABLE |" "$proc_default"
assert_contains "procedure refuses to pick one of two VERDICT lines" \
    "never pick one" "$proc_default"
assert_contains "procedure routes an out-of-vocabulary token to UNCHECKABLE" \
    "| a \`VERDICT:\` token outside the closed set | UNCHECKABLE" "$proc_default"
assert_contains "procedure prints an unlisted cause verbatim rather than swallowing it" \
    "print the raw reason field verbatim" "$proc_default"
assert_contains "procedure states the direction of the failure mode" \
    "fail-safe, not fail-open" "$proc_default"

# A malformed stream is only meaningful if the procedure's accept-condition is
# strict enough to reject it. Pin the condition itself.
assert_contains "procedure accepts exactly one VERDICT line" \
    'one** `VERDICT:` line whose' "$proc_default"
assert_contains "procedure names the closed verdict set at the accept-condition" \
    'token is one of `CLEAR`, `CLEAR_CAVEATED`,' "$proc_default"

# The cause vocabulary the recovery table keys on must be the checker's own.
vocab_causes="$("$PY_BIN" -c "
import sys; sys.path.insert(0, '$PROJECT_DIR/.aitask-scripts/lib')
import parallel_admission_vocab as v
print(' '.join(sorted(v.UNCHECKABLE_REASONS)))")"
# A parameterised code appears as `code:<param>` in the table, a bare one as
# `code`, so accept either terminator -- but nothing looser, or `no_plan` would
# match a hypothetical `no_planning` and the check would go quiet.
uncovered=""
for c in $vocab_causes; do
    printf '%s' "$proc_default" | grep -qE "\`${c}[\`:]" || uncovered+="$c "
done
assert_eq "the recovery table names every UNCHECKABLE_REASONS code" "" "$uncovered"

echo ""
echo "===================="
echo "Passed: $PASS / $TOTAL"
echo "===================="
[[ "$FAIL" -eq 0 ]]
