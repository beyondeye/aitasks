#!/usr/bin/env bash
# test_gate_codex_approvals.sh - receipt guard on human approval gates (t2281).
#
# In an attended Codex session of a project that registers the aitask_questions
# server, a `pass` for plan_approved / review_approved / merge_approved needs a
# completion receipt this task may claim, and resume-point does not resume
# implementation on an approval that no longer covers the plan file.
#
# Coverage:
#   1. Scope: no CODEX_THREAD_ID, or no registration -> unguarded, as before.
#   2. append: refused without evidence, with a receipt for another task /
#      checkpoint / non-approving answer / unbound plan / changed plan; nothing
#      is written on refusal. Accepted with a valid receipt, exactly one claim.
#   3. Profile evidence is checked against the profile file.
#   4. aitask_gate_record.sh surfaces the refusal as exit 3.
#   5. resume-point: FRESH and BOOKKEEPING resume, STALE and UNBOUND demote to
#      PLAN under Codex only; approval-check reports the evidence.
#      A review_approved pass needs a commit made by commit-approved.
#   6. fail records and machine gates are never guarded.
#   7. Standing is not history: asking again, or a change seen once and then
#      reverted, ends an approval for good; the old receipt records nothing.
#   8. plan-bookkeeping/v2: only checkbox state is tolerated; any added text,
#      under whatever heading, needs approval again.
#   9. task-requirements/v2: a changed task body, dependency or declared gate
#      is stale; a ledger append or a status/priority write is not. A claim
#      saved without that binding, or under an older rule, is retired.
#  10. Reviewed deletions and renames are bound and committed; a path that
#      exists, or has no committed original, is refused.
#  11. A profile-recorded approval resumes while the profile still pre-answers.
#  12. The commit boundary: commit-approved commits the approved bytes whatever
#      the working tree holds by then, only the bound paths, onto the bound
#      branch and base; it is refused when either moved under the approval.
#
# Hermetic: scratch project, scratch question state. Never touches the real
# ~/.local/state or the checkout's .codex/config.toml.
#
# Run: bash tests/test_gate_codex_approvals.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd

PASS=0
FAIL=0
TOTAL=0

GATE="$PROJECT_DIR/.aitask-scripts/aitask_gate.sh"
RECORD="$PROJECT_DIR/.aitask-scripts/aitask_gate_record.sh"
PY="$( . "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh" 2>/dev/null; resolve_python 2>/dev/null || true)"
if [[ -z "$PY" ]]; then
    echo "SKIP: no python interpreter"
    exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/test_codex_approvals_XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
PROJ="$(cd "$TMP" && pwd -P)/proj"
mkdir -p "$PROJ/aitasks/metadata/profiles" "$PROJ/aiplans" "$PROJ/.codex" "$PROJ/src"
export TASK_DIR="$PROJ/aitasks" PLAN_DIR="$PROJ/aiplans"
export AIT_QUESTIONS_STATE_DIR="$TMP/state"
# The state directory is pinned explicitly; XDG is redirected as a second
# fence so a regression in that pinning lands in scratch, not in the real one.
# HOME stays: the framework's python shim resolves its venv through it.
export XDG_STATE_HOME="$TMP/xdg"
unset CODEX_THREAD_ID
# The scratch project is a git work tree: a review approval binds its branch.
# Signing and hooks are pinned locally so the user's global git config (a
# signing key, a hooks path) cannot reach these commits.
git -C "$PROJ" init -q -b main
git -C "$PROJ" config user.name t
git -C "$PROJ" config user.email t@example.invalid
git -C "$PROJ" config commit.gpgsign false
git -C "$PROJ" config core.hooksPath .git/hooks
printf 'fixture\n' > "$PROJ/README"
git -C "$PROJ" add README
git -C "$PROJ" commit -q -m fixture

register() { printf '[mcp_servers.aitask_questions]\ncommand = "x"\n' > "$PROJ/.codex/config.toml"; }
unregister() { : > "$PROJ/.codex/config.toml"; }

make_task() {
    printf -- '---\npriority: high\nstatus: Implementing\n---\n\nBody for t%s.\n' "$1" > "$TASK_DIR/t$1_demo.md"
    printf 'Plan for t%s: do the thing.\n' "$1" > "$PLAN_DIR/p$1_demo.md"
}
runs() { grep -c "gate:$2\*\*" "$TASK_DIR/t$1_demo.md" 2>/dev/null || true; }

# ask <task> <checkpoint> <opening> <answer-id> <artifact>... -> "<session>:<receipt>"
# answer-id "-" leaves it unanswered, "cancel" declines it; both print the session.
ask() {
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts" "$PY" - "$PROJ" "$AIT_QUESTIONS_STATE_DIR" "$@" <<'PYEOF'
import sys
from pathlib import Path
from aitask_questions.store import Store
proj, state, task, checkpoint, opening, answer, *artifacts = sys.argv[1:]
# "merge:<source>:<destination>" names what a merge approval merges, and where.
action = next(({"source": a.split(":")[1], "destination": a.split(":")[2]}
               for a in artifacts if a.startswith("merge:")), None)
artifacts = [a for a in artifacts if not a.startswith("merge:")]
store = Store(Path(state), Path(proj))
q = [{"id": "decision", "text": "Approve?", "kind": "choice", "options": [
    {"id": "approve_start", "label": "Start", "description": ""},
    {"id": "revise", "label": "Revise", "description": ""}]}]
# "del:<relative path>" names a path the reviewed change removes.
gone = [a[4:] for a in artifacts if a.startswith("del:")]
rel = [str(Path(a).resolve().relative_to(Path(proj).resolve())) for a in artifacts if not a.startswith("del:")]
sid = store.open(task, checkpoint, opening, q, rel, gone, action=action)["session_id"]
if answer in ("-", "cancel"):  # asked, not answered / declined
    if answer == "cancel":
        store.cancel(sid)
    print(sid)
    raise SystemExit
done = store.submit(sid, "decision", answer, "codex_prompt_model_forwarded")
print(f"{sid}:{done['receipt']['id']}")
PYEOF
}

codex() { CODEX_THREAD_ID=thread-1 "$@"; }

# consume <session>:<receipt> <consumer> -> outcome (the MCP tool's claim)
consume() {
    PYTHONPATH="$PROJECT_DIR/.aitask-scripts" "$PY" -c '
import sys
from pathlib import Path
from aitask_questions.store import Store
sid, rid = sys.argv[3].split(":")
print(Store(Path(sys.argv[2]), Path(sys.argv[1])).consume(sid, rid, sys.argv[4])["outcome"])
' "$PROJ" "$AIT_QUESTIONS_STATE_DIR" "$1" "$2"
}
# approve <task> <opening> -> records plan_approved from a fresh receipt
approve() {
    local r
    r="$(ask "t$1" plan_approved "$2" approve_start "$PLAN_DIR/p$1_demo.md")" || return 1
    codex "$GATE" append "$1" plan_approved pass type=human "approval=$r" >/dev/null 2>&1 || return 1
    echo "$r"
}
resume() { codex "$GATE" resume-point "$1" 2>/dev/null; }
# commit_approved <task> <session>:<receipt> -> COMMIT:... line; exit 3 on refusal
commit_approved() { printf 'feature: Approved change (t%s)\n' "$1" | "$GATE" commit-approved "$1" "$2" - 2>&1; }
head_of() { git -C "$PROJ" rev-parse HEAD; }
verdict() { "$GATE" approval-check "$1" "${2:-plan_approved}"; }

# ---------------------------------------------------------------------------
echo "--- 1. scope ---"
make_task 10
register
"$GATE" append 10 plan_approved pass type=human >/dev/null 2>&1
assert_eq "no CODEX_THREAD_ID: unguarded append succeeds" "0" "$?"
assert_eq "no CODEX_THREAD_ID: block written" "1" "$(runs 10 plan_approved)"
unregister
make_task 11
codex "$GATE" append 11 plan_approved pass type=human >/dev/null 2>&1
assert_eq "Codex without registration: unguarded append succeeds" "0" "$?"
assert_eq "Codex without registration: block written" "1" "$(runs 11 plan_approved)"
[[ ! -e "$AIT_QUESTIONS_STATE_DIR" ]]
assert_eq "unguarded paths never create question state" "0" "$?"
[[ ! -e "$TMP/xdg" ]]
assert_eq "nothing written under the XDG fallback" "0" "$?"

# ---------------------------------------------------------------------------
echo "--- 2. append under attended Codex ---"
register
make_task 20
out="$(codex "$GATE" append 20 plan_approved pass type=human 2>&1)"; rc=$?
assert_eq "no evidence: exit 3" "3" "$rc"
assert_contains "no evidence: says what to pass" "approval=<session_id>:<receipt_id>" "$out"
assert_eq "no evidence: nothing written" "0" "$(runs 20 plan_approved)"

codex "$GATE" append 20 plan_approved pass approval=nonsense >/dev/null 2>&1
assert_eq "malformed evidence: exit 3" "3" "$?"
codex "$GATE" append 20 plan_approved pass approval=aaaa:bbbb >/dev/null 2>&1
assert_eq "unknown session: exit 3" "3" "$?"

make_task 21
other="$(ask t21 plan_approved o1 approve_start "$PLAN_DIR/p21_demo.md")"
codex "$GATE" append 20 plan_approved pass "approval=$other" >/dev/null 2>&1
assert_eq "receipt of another task: exit 3" "3" "$?"

wrong_cp="$(ask t20 label_filter o1 approve_start "$PLAN_DIR/p20_demo.md")"
codex "$GATE" append 20 plan_approved pass "approval=$wrong_cp" >/dev/null 2>&1
assert_eq "receipt of another checkpoint: exit 3" "3" "$?"

revise="$(ask t20 plan_approved o1 revise "$PLAN_DIR/p20_demo.md")"
out="$(codex "$GATE" append 20 plan_approved pass "approval=$revise" 2>&1)"; rc=$?
assert_eq "non-approving answer: exit 3" "3" "$rc"
assert_contains "non-approving answer: reason" "answer_is_not_an_approval" "$out"

echo x > "$PROJ/src/a.txt"
unbound="$(ask t20 plan_approved o2 approve_start "$PROJ/src/a.txt")"
out="$(codex "$GATE" append 20 plan_approved pass "approval=$unbound" 2>&1)"; rc=$?
assert_eq "plan file not bound: exit 3" "3" "$rc"
assert_contains "plan file not bound: reason" "plan_file_not_bound" "$out"

nothing="$(ask t20 review_approved o1 approve_start)"
out="$(codex "$GATE" append 20 review_approved pass "approval=$nothing" 2>&1)"; rc=$?
assert_eq "review approval binding no files: exit 3" "3" "$rc"
assert_contains "review approval binding no files: reason" "nothing_bound" "$out"

changed="$(ask t20 plan_approved o3 approve_start "$PLAN_DIR/p20_demo.md")"
echo "Now do something else." >> "$PLAN_DIR/p20_demo.md"
out="$(codex "$GATE" append 20 plan_approved pass "approval=$changed" 2>&1)"; rc=$?
assert_eq "plan changed after the answer: exit 3" "3" "$rc"
assert_eq "every refusal left the ledger untouched" "0" "$(runs 20 plan_approved)"

good="$(ask t20 plan_approved o4 approve_start "$PLAN_DIR/p20_demo.md")"
out="$(codex "$GATE" append 20 plan_approved pass type=human "approval=$good" 2>&1)"; rc=$?
assert_eq "valid receipt: exit 0" "0" "$rc"
assert_eq "valid receipt: one block" "1" "$(runs 20 plan_approved)"
assert_contains "block carries the occurrence" "approval:${good%%:*}:" "$(cat "$TASK_DIR/t20_demo.md")"
grep -q 'approval=' "$TASK_DIR/t20_demo.md"
assert_eq "raw approval= key never reaches the ledger" "1" "$?"
assert_contains "claim acknowledged" "APPROVAL:FRESH|${good%%:*}" "$("$GATE" approval-check 20 plan_approved)"

codex "$GATE" append 20 review_approved pass "approval=$good" >/dev/null 2>&1
assert_eq "plan receipt cannot record the review gate: exit 3" "3" "$?"
assert_eq "review gate not written" "0" "$(runs 20 review_approved)"

# A review approval is recorded only for a commit made from its approved bytes.
review="$(ask t20 review_approved o2 approve_start "$PROJ/src/a.txt")"
out="$(codex "$GATE" append 20 review_approved pass type=human "approval=$review" 2>&1)"; rc=$?
assert_eq "review receipt without the guarded commit: exit 3" "3" "$rc"
assert_contains "review receipt without the guarded commit: reason" "review_commit_missing" "$out"
out="$(commit_approved 20 "$review")"
assert_contains "guarded commit of the change set" "COMMIT:committed|" "$out"
assert_eq "the commit holds the approved file" "x" "$(git -C "$PROJ" show HEAD:src/a.txt)"
codex "$GATE" append 20 review_approved pass type=human "approval=$review" >/dev/null 2>&1
assert_eq "review record after the guarded commit: exit 0" "0" "$?"
assert_eq "review record after the guarded commit: one block" "1" "$(runs 20 review_approved)"

# A claim through the MCP tool followed by the agent's own `git commit` is not
# that: nothing shows the committed bytes are the approved ones.
make_task 22
echo y > "$PROJ/src/b.txt"
pre="$(ask t22 review_approved o1 approve_start "$PROJ/src/b.txt")"
assert_eq "claim through the tool" "claimed" "$(consume "$pre" t22:review_approved)"
echo unapproved >> "$PROJ/src/b.txt"
git -C "$PROJ" add src/b.txt && git -C "$PROJ" commit -q -m "raw commit" -- src/b.txt
out="$(codex "$GATE" append 22 review_approved pass "approval=$pre" 2>&1)"; rc=$?
assert_eq "raw commit after a tool claim: record refused" "3" "$rc"
assert_contains "raw commit after a tool claim: reason" "review_commit_missing" "$out"
assert_eq "raw commit after a tool claim: nothing written" "0" "$(runs 22 review_approved)"
out="$(commit_approved 22 "$pre")"
assert_contains "and the claim cannot be turned into a guarded commit afterwards" "COMMIT_REFUSED:" "$out"
# Once committed through the guard, the approval is of that commit: editing the
# files again is new work and does not unmake the record.
make_task 23
echo y > "$PROJ/src/c.txt"
late="$(ask t23 review_approved o1 approve_start "$PROJ/src/c.txt")"
commit_approved 23 "$late" >/dev/null
echo z >> "$PROJ/src/c.txt"
codex "$GATE" append 23 review_approved pass "approval=$late" >/dev/null 2>&1
assert_eq "record after the commit, files edited since: exit 0" "0" "$?"
assert_contains "the approval names its commit" "APPROVAL:FRESH|${late%%:*}|committed as" "$(verdict 23 review_approved)"
other_claim="$(ask t22 merge_approved o1 approve_start merge:main:main)"
consume "$other_claim" something-else >/dev/null
out="$(codex "$GATE" append 22 merge_approved pass "approval=$other_claim" 2>&1)"; rc=$?
assert_eq "receipt already claimed by another action: exit 3" "3" "$rc"
assert_contains "receipt already claimed by another action: reason" "conflict" "$out"

# ---------------------------------------------------------------------------
echo "--- 3. profile evidence ---"
make_task 30
printf 'name: auto\npost_plan_action: start_implementation\nreview_action: commit\n' > "$TASK_DIR/metadata/profiles/auto.yaml"
printf 'name: fast\npost_plan_action: ask\n' > "$TASK_DIR/metadata/profiles/fast.yaml"
codex "$GATE" append 30 plan_approved pass approval=profile:auto >/dev/null 2>&1
assert_eq "profile that pre-answers the step: exit 0" "0" "$?"
assert_contains "block names the profile" "approval:profile:auto" "$(cat "$TASK_DIR/t30_demo.md")"
codex "$GATE" append 30 plan_approved pass approval=profile:fast >/dev/null 2>&1
assert_eq "profile that asks: exit 3" "3" "$?"
codex "$GATE" append 30 plan_approved pass approval=profile:missing >/dev/null 2>&1
assert_eq "unknown profile: exit 3" "3" "$?"
codex "$GATE" append 30 plan_approved pass 'approval=profile:../../x' >/dev/null 2>&1
assert_eq "profile name with a path: exit 3" "3" "$?"
codex "$GATE" append 30 merge_approved pass approval=profile:auto >/dev/null 2>&1
assert_eq "no profile covers the merge approval: exit 3" "3" "$?"
assert_eq "only the valid profile record was written" "1" "$(runs 30 plan_approved)"

# ---------------------------------------------------------------------------
echo "--- 4. aitask_gate_record.sh ---"
make_task 40
out="$(cd "$PROJ" && codex "$RECORD" 40 plan_approved pass type=human 2>/dev/null)"; rc=$?
assert_eq "record helper: refusal is exit 3" "3" "$rc"
assert_contains "record helper: refusal token" "GATE_RECORD_REFUSED:plan_approved" "$out"
assert_eq "record helper: nothing written" "0" "$(runs 40 plan_approved)"

# ---------------------------------------------------------------------------
echo "--- 5. resume-point and approval-check ---"
make_task 50
printf 'Plan for t50: do the thing.\n\n- [ ] step 1\n' > "$PLAN_DIR/p50_demo.md"
r50="$(ask t50 plan_approved o1 approve_start "$PLAN_DIR/p50_demo.md")"
codex "$GATE" append 50 plan_approved pass type=human "approval=$r50" >/dev/null 2>&1
assert_eq "fresh approval resumes at IMPLEMENT" "IMPLEMENT" "$(codex "$GATE" resume-point 50 2>/dev/null)"
printf 'Plan for t50: do the thing.\n\n- [x] step 1\n' > "$PLAN_DIR/p50_demo.md"
assert_contains "a ticked step is bookkeeping" "APPROVAL:BOOKKEEPING|${r50%%:*}|" "$(verdict 50)"
assert_eq "bookkeeping still resumes at IMPLEMENT" "IMPLEMENT" "$(resume 50)"
printf 'Plan for t50: do a different thing.\n' > "$PLAN_DIR/p50_demo.md"
assert_eq "rewritten plan resumes at PLAN under Codex" "PLAN" "$(resume 50)"
assert_contains "rewritten plan is stale" "APPROVAL:STALE|${r50%%:*}|" "$(verdict 50)"
assert_contains "the demotion is explained on stderr" "approved again" "$(codex "$GATE" resume-point 50 2>&1 >/dev/null)"
assert_eq "other agents still resume at IMPLEMENT" "IMPLEMENT" "$("$GATE" resume-point 50 2>/dev/null)"
rm "$PLAN_DIR/p50_demo.md"
assert_eq "missing plan file resumes at PLAN under Codex" "PLAN" "$(resume 50)"
make_task 52
approve 52 o1 >/dev/null
rm "$PLAN_DIR/p52_demo.md"
assert_eq "plan removed after approval resumes at PLAN" "PLAN" "$(resume 52)"

# A pass recorded without a receipt (another agent, or before this guard).
assert_contains "legacy pass is unbound" "APPROVAL:UNBOUND" "$("$GATE" approval-check 10 plan_approved)"
assert_eq "legacy pass resumes at PLAN under Codex" "PLAN" "$(codex "$GATE" resume-point 10 2>/dev/null)"
assert_eq "legacy pass resumes at IMPLEMENT elsewhere" "IMPLEMENT" "$("$GATE" resume-point 10 2>/dev/null)"
unregister
assert_eq "legacy pass, Codex without the server: IMPLEMENT" "IMPLEMENT" "$(codex "$GATE" resume-point 10 2>/dev/null)"
register

# Review already recorded: the completed action stays historical evidence.
make_task 51
r51="$(ask t51 plan_approved o1 approve_start "$PLAN_DIR/p51_demo.md")"
codex "$GATE" append 51 plan_approved pass "approval=$r51" >/dev/null 2>&1
echo r > "$PROJ/src/r51.txt"
v51="$(ask t51 review_approved o1 approve_start "$PROJ/src/r51.txt")"
commit_approved 51 "$v51" >/dev/null
codex "$GATE" append 51 review_approved pass "approval=$v51" >/dev/null 2>&1
echo "Final notes rewrite." > "$PLAN_DIR/p51_demo.md"
assert_eq "POSTIMPL is not demoted by a later plan change" "POSTIMPL" "$(codex "$GATE" resume-point 51 2>/dev/null)"

# ---------------------------------------------------------------------------
echo "--- 6. never guarded ---"
make_task 60
codex "$GATE" append 60 plan_approved fail type=human note=aborted >/dev/null 2>&1
assert_eq "a fail record needs no evidence" "0" "$?"
codex "$GATE" append 60 risk_evaluated pass type=machine >/dev/null 2>&1
assert_eq "a machine gate needs no evidence" "0" "$?"
codex "$GATE" append 60 build_verified pass type=machine approval=whatever >/dev/null 2>&1
assert_eq "a stray approval= on a machine gate is dropped" "0" "$?"
grep -q 'approval=' "$TASK_DIR/t60_demo.md"
assert_eq "and never written" "1" "$?"

# ---------------------------------------------------------------------------
echo "--- 7. standing is not history ---"
make_task 70
r70="$(approve 70 o1)"
assert_eq "approved: IMPLEMENT" "IMPLEMENT" "$(resume 70)"
ask t70 plan_approved o2 - "$PLAN_DIR/p70_demo.md" >/dev/null
assert_eq "asked again, unanswered: PLAN" "PLAN" "$(resume 70)"
assert_contains "asked again: the old approval is revoked" "APPROVAL:STALE|${r70%%:*}|revoked: checkpoint_reopened" "$(verdict 70)"
out="$(codex "$GATE" append 70 plan_approved pass type=human "approval=$r70" 2>&1)"; rc=$?
assert_eq "old receipt after asking again: exit 3" "3" "$rc"
assert_contains "old receipt after asking again: reason" "stale_approval" "$out"
assert_eq "old receipt after asking again: no second block" "1" "$(runs 70 plan_approved)"
approve 70 o3 >/dev/null
assert_eq "a new approval of the same bytes resumes" "IMPLEMENT" "$(resume 70)"

make_task 71
r71="$(approve 71 o1)"
printf 'Plan for t71: do a different thing.\n' > "$PLAN_DIR/p71_demo.md"
assert_eq "rewritten: PLAN" "PLAN" "$(resume 71)"
printf 'Plan for t71: do the thing.\n' > "$PLAN_DIR/p71_demo.md"
assert_eq "rewritten then reverted: still PLAN" "PLAN" "$(resume 71)"
assert_contains "the revocation is persisted" "APPROVAL:STALE|${r71%%:*}|revoked:" "$(verdict 71)"
out="$(codex "$GATE" append 71 plan_approved pass "approval=$r71" 2>&1)"
assert_eq "reverted bytes do not revive the receipt" "3" "$?"

# The change is seen by the question server (any status/recovery call), not by
# a gate check, and reverted before the workflow resumes.
make_task 72
approve 72 o1 >/dev/null
printf 'Plan for t72: do a different thing.\n' > "$PLAN_DIR/p72_demo.md"
PYTHONPATH="$PROJECT_DIR/.aitask-scripts" "$PY" -c '
import sys
from pathlib import Path
from aitask_questions.store import Store
Store(Path(sys.argv[2]), Path(sys.argv[1])).outstanding()
' "$PROJ" "$AIT_QUESTIONS_STATE_DIR"
printf 'Plan for t72: do the thing.\n' > "$PLAN_DIR/p72_demo.md"
assert_eq "change seen by the server, then reverted: PLAN" "PLAN" "$(resume 72)"

# ---------------------------------------------------------------------------
echo "--- 8. plan-bookkeeping/v2 ---"
make_task 80
approve 80 o1 >/dev/null
printf 'Also delete the database.\n' >> "$PLAN_DIR/p80_demo.md"
assert_contains "appended requirement is stale" "APPROVAL:STALE" "$(verdict 80)"
assert_eq "appended requirement: PLAN" "PLAN" "$(resume 80)"

make_task 81
printf '# Plan\n\n- [ ] step one\n- [ ] step two\n' > "$PLAN_DIR/p81_demo.md"
approve 81 o1 >/dev/null
printf '# Plan\n\n- [x] step one\n- [ ] step two\n' > "$PLAN_DIR/p81_demo.md"
assert_contains "ticked checkboxes are bookkeeping" "APPROVAL:BOOKKEEPING" "$(verdict 81)"
assert_eq "ticked checkboxes: IMPLEMENT" "IMPLEMENT" "$(resume 81)"

# Text is text whatever heading it sits under: a section the workflow itself
# appends can carry a requirement nobody approved.
make_task 85
approve 85 o1 >/dev/null
printf '\n## Implementation Progress\n- New requirement: delete the database.\n' >> "$PLAN_DIR/p85_demo.md"
assert_contains "a requirement under a workflow heading is stale" "APPROVAL:STALE" "$(verdict 85)"
assert_eq "a requirement under a workflow heading: PLAN" "PLAN" "$(resume 85)"
make_task 86
r86="$(approve 86 o1)"
approve_receipt() { echo "$r86"; }
printf '\n## Final Implementation Notes\n- done\n' >> "$PLAN_DIR/p86_demo.md"
assert_contains "closing notes after the approved plan: NOTES, not revoked" "APPROVAL:NOTES" "$(verdict 86)"
assert_eq "even harmless appended notes ask again on re-entry: PLAN" "PLAN" "$(resume 86)"
codex "$GATE" append 86 plan_approved pass type=human "approval=$(approve_receipt 86)" >/dev/null 2>&1
assert_eq "NOTES does not re-record the plan gate" "3" "$?"

make_task 82
approve 82 o1 >/dev/null
printf '\n## Implementation Progress\n- step 1\n\n## Additional Requirements\n- delete the database\n' >> "$PLAN_DIR/p82_demo.md"
assert_eq "a section the workflow does not write: PLAN" "PLAN" "$(resume 82)"

make_task 83
printf 'Plan for t83: do the thing' > "$PLAN_DIR/p83_demo.md"
approve 83 o1 >/dev/null
printf ' and delete the database\n\n## Implementation Progress\n' >> "$PLAN_DIR/p83_demo.md"
assert_eq "text continuing the last approved line: PLAN" "PLAN" "$(resume 83)"

make_task 84
printf '# Plan\n\n- [ ] step one\n' > "$PLAN_DIR/p84_demo.md"
approve 84 o1 >/dev/null
printf '# Plan\n\n- [x] step one, and delete the database\n' > "$PLAN_DIR/p84_demo.md"
assert_eq "an edited step is not a ticked step: PLAN" "PLAN" "$(resume 84)"

# ---------------------------------------------------------------------------
echo "--- 9. task-requirements/v2 ---"
make_task 90
approve 90 o1 >/dev/null
codex "$GATE" append 90 risk_evaluated pass type=machine >/dev/null 2>&1
sed -i.bak -e 's/^priority: high$/priority: low/' -e 's/^status: Implementing$/status: Postponed\nassigned_to: someone/' \
    "$TASK_DIR/t90_demo.md" && rm -f "$TASK_DIR/t90_demo.md.bak"
assert_contains "ledger appends and workflow-state fields are not requirements" "APPROVAL:FRESH" "$(verdict 90)"
assert_eq "ledger appends and workflow-state fields: IMPLEMENT" "IMPLEMENT" "$(resume 90)"
sed -i.bak 's/^Body for t90\.$/Body for t90: also delete the database./' "$TASK_DIR/t90_demo.md" && rm -f "$TASK_DIR/t90_demo.md.bak"
assert_contains "changed task body is stale" "task requirements changed" "$(verdict 90)"
assert_eq "changed task body: PLAN" "PLAN" "$(resume 90)"

# Frontmatter that states a requirement is bound; its formatting is not.
edit_frontmatter() {  # <task> <python expression over text s>
    "$PY" - "$TASK_DIR/t$1_demo.md" "$2" <<'PYEOF'
import sys
from pathlib import Path
path = Path(sys.argv[1])
s = path.read_text()
path.write_text(eval(sys.argv[2]))
PYEOF
}
make_task 93
edit_frontmatter 93 's.replace("priority: high\n", "priority: high\ndepends: []\n")'
approve 93 o1 >/dev/null
edit_frontmatter 93 's.replace("depends: []", "depends: [ ]")'
assert_contains "an empty dependency list respelled is the same requirement" "APPROVAL:FRESH" "$(verdict 93)"
edit_frontmatter 93 's.replace("depends: [ ]", "depends: [7]")'
assert_contains "a dependency added after approval is stale" "task requirements changed" "$(verdict 93)"
assert_eq "a dependency added after approval: PLAN" "PLAN" "$(resume 93)"
make_task 94
approve 94 o1 >/dev/null
edit_frontmatter 94 's.replace("priority: high\n", "priority: high\ngates:\n  - risk_evaluated\n")'
assert_contains "a gate declared after approval is stale" "task requirements changed" "$(verdict 94)"
assert_eq "a gate declared after approval: PLAN" "PLAN" "$(resume 94)"
make_task 96
edit_frontmatter 96 's.replace("priority: high\n", "priority: high\ndepends: [3, 4]\n")'
approve 96 o1 >/dev/null
edit_frontmatter 96 's.replace("depends: [3, 4]", "depends:\n  - 3\n  - 4")'
assert_contains "the same dependencies in block form are the same requirement" "APPROVAL:FRESH" "$(verdict 96)"

make_task 91
r91="$(ask t91 plan_approved o1 approve_start "$PLAN_DIR/p91_demo.md")"
printf '\nOne more requirement.\n' >> "$TASK_DIR/t91_demo.md"
codex "$GATE" append 91 plan_approved pass "approval=$r91" >/dev/null 2>&1
assert_eq "task body changed between answer and record: exit 3" "3" "$?"
assert_eq "task body changed between answer and record: nothing written" "0" "$(runs 91 plan_approved)"

# An occurrence that binds no requirements (state written before they were
# bound) cannot record a plan approval.
make_task 92
r92="$(ask t92 plan_approved o1 approve_start "$PLAN_DIR/p92_demo.md")"
"$PY" - "$AIT_QUESTIONS_STATE_DIR/questions.sqlite3" "${r92%%:*}" <<'PYEOF'
import json, sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
body = json.loads(conn.execute("SELECT body FROM sessions WHERE id=?", (sys.argv[2],)).fetchone()[0])
body["manifest"] = [e for e in body["manifest"] if "projection" not in e]
conn.execute("UPDATE sessions SET body=? WHERE id=?", (json.dumps(body), sys.argv[2]))
conn.commit()
PYEOF
out="$(codex "$GATE" append 92 plan_approved pass "approval=$r92" 2>&1)"; rc=$?
assert_eq "no requirements bound: exit 3" "3" "$rc"
assert_contains "no requirements bound: reason" "task_requirements_not_bound" "$out"

# The same for a claim that was SAVED without it: a pass recorded before the
# binding existed must not resume implementation, however fresh its plan file.
strip_binding() {  # <session> <mode: drop|v1>
    "$PY" - "$AIT_QUESTIONS_STATE_DIR/questions.sqlite3" "$1" "$2" <<'PYEOF'
import json, sqlite3, sys
conn = sqlite3.connect(sys.argv[1])
body = json.loads(conn.execute("SELECT body FROM sessions WHERE id=?", (sys.argv[2],)).fetchone()[0])
for holder in (body, body["consumption"]):
    if sys.argv[3] == "drop":
        holder["manifest"] = [e for e in holder["manifest"] if "projection" not in e]
    else:
        for e in holder["manifest"]:
            if "projection" in e:
                e["projection"] = "task-requirements/v1"
conn.execute("UPDATE sessions SET body=? WHERE id=?", (json.dumps(body), sys.argv[2]))
conn.commit()
PYEOF
}
make_task 97
r97="$(approve 97 o1)"
assert_eq "bound claim: IMPLEMENT" "IMPLEMENT" "$(resume 97)"
strip_binding "${r97%%:*}" drop
assert_contains "saved claim without the binding is stale" "APPROVAL:STALE|${r97%%:*}|" "$(verdict 97)"
assert_contains "saved claim without the binding: says why" "not bound under task-requirements/v2" \
    "$("$PY" - "$AIT_QUESTIONS_STATE_DIR/questions.sqlite3" "${r97%%:*}" <<'PYEOF'
import json, sqlite3, sys
body = json.loads(sqlite3.connect(sys.argv[1]).execute("SELECT body FROM sessions WHERE id=?", (sys.argv[2],)).fetchone()[0])
print(body["consumption"].get("revoked", {}).get("reason", "not revoked"))
PYEOF
)"
assert_eq "saved claim without the binding: PLAN" "PLAN" "$(resume 97)"
out="$(codex "$GATE" append 97 plan_approved pass "approval=$r97" 2>&1)"
assert_eq "saved claim without the binding records nothing again" "3" "$?"
make_task 98
r98="$(approve 98 o1)"
strip_binding "${r98%%:*}" v1
assert_contains "claim bound under the superseded rule is stale" "APPROVAL:STALE|${r98%%:*}|" "$(verdict 98)"
assert_eq "claim bound under the superseded rule: PLAN" "PLAN" "$(resume 98)"

rm "$TASK_DIR/t92_demo.md"
ask t92 plan_approved o2 approve_start "$PLAN_DIR/p92_demo.md" >/dev/null 2>&1
assert_eq "no task file: the plan approval cannot be asked" "1" "$?"

# ---------------------------------------------------------------------------
echo "--- 10. reviewed deletions and renames ---"
printf 'old\n' > "$PROJ/src/old.txt"; printf 'gone\n' > "$PROJ/src/gone.txt"; printf 'back\n' > "$PROJ/src/back.txt"
git -C "$PROJ" add src/old.txt src/gone.txt src/back.txt
git -C "$PROJ" commit -q -m "fixture files" -- src/old.txt src/gone.txt src/back.txt
make_task 100
git -C "$PROJ" mv src/old.txt src/new.txt
rename="$(ask t100 review_approved o1 approve_start "$PROJ/src/new.txt" del:src/old.txt)"
assert_contains "rename: committed" "COMMIT:committed|" "$(commit_approved 100 "$rename")"
assert_eq "rename: new path is in the commit" "old" "$(git -C "$PROJ" show HEAD:src/new.txt)"
assert_eq "rename: old path is gone from the commit" "" "$(git -C "$PROJ" ls-tree HEAD src/old.txt)"
assert_eq "rename: index and tree agree afterwards" "" "$(git -C "$PROJ" status --porcelain -- src/new.txt src/old.txt)"
codex "$GATE" append 100 review_approved pass type=human "approval=$rename" >/dev/null 2>&1
assert_eq "rename (old path removed, new path bound): record exit 0" "0" "$?"

make_task 101
rm "$PROJ/src/gone.txt"
only="$(ask t101 review_approved o1 approve_start del:src/gone.txt)"
assert_contains "deletion-only change: stands before the commit" "APPROVAL:UNBOUND" "$(verdict 101 review_approved)"
assert_contains "deletion-only change: committed" "COMMIT:committed|" "$(commit_approved 101 "$only")"
assert_eq "deletion-only change: path removed by the commit" "" "$(git -C "$PROJ" ls-tree HEAD src/gone.txt)"
codex "$GATE" append 101 review_approved pass type=human "approval=$only" >/dev/null 2>&1
assert_eq "deletion-only change: record exit 0" "0" "$?"
assert_contains "deletion-only change: stands" "APPROVAL:FRESH" "$(verdict 101 review_approved)"

make_task 102
ask t102 review_approved o1 approve_start del:src/new.txt >/dev/null 2>&1
assert_eq "a path that exists cannot be bound as removed" "1" "$?"
ask t102 review_approved o2 approve_start del:src/never.txt >/dev/null 2>&1
assert_eq "a path with no committed original cannot be bound as removed" "1" "$?"
ask t102 review_approved o3 approve_start "$PROJ/src/missing.txt" >/dev/null 2>&1
assert_eq "a missing file is still not an artifact" "1" "$?"
rm "$PROJ/src/back.txt"
back="$(ask t102 review_approved o4 approve_start del:src/back.txt)"
before="$(head_of)"
printf 'back\n' > "$PROJ/src/back.txt"
out="$(commit_approved 102 "$back")"; rc=$?
assert_eq "removed path restored before the commit: exit 3" "3" "$rc"
assert_contains "removed path restored before the commit: reason" "COMMIT_REFUSED:stale_approval" "$out"
assert_eq "removed path restored before the commit: no commit" "$before" "$(head_of)"
codex "$GATE" append 102 review_approved pass "approval=$back" >/dev/null 2>&1
assert_eq "removed path restored: record exit 3" "3" "$?"

# ---------------------------------------------------------------------------
echo "--- 11. profile-recorded approval on re-entry ---"
make_task 110
codex "$GATE" append 110 plan_approved pass type=human approval=profile:auto >/dev/null 2>&1
assert_contains "profile approval is reported as such" "APPROVAL:PROFILE|auto|" "$(verdict 110)"
assert_eq "profile approval resumes at IMPLEMENT" "IMPLEMENT" "$(resume 110)"
printf 'Plan for t110: revised by the agent.\n' > "$PLAN_DIR/p110_demo.md"
assert_eq "the profile skips the question, so a plan edit does not ask" "IMPLEMENT" "$(resume 110)"
printf 'name: auto\npost_plan_action: ask\n' > "$TASK_DIR/metadata/profiles/auto.yaml"
assert_eq "profile no longer pre-answers: PLAN" "PLAN" "$(resume 110)"
printf 'name: auto\npost_plan_action: start_implementation\nreview_action: commit\n' > "$TASK_DIR/metadata/profiles/auto.yaml"
# A later receipt-backed record replaces the profile one as the evidence.
codex "$GATE" append 110 plan_approved fail type=human note=revise >/dev/null 2>&1
printf 'Plan for t110: revised again.\n' > "$PLAN_DIR/p110_demo.md"
r110="$(approve 110 o1)"
assert_contains "the current record is the receipt" "APPROVAL:FRESH|${r110%%:*}|" "$(verdict 110)"

# ---------------------------------------------------------------------------
echo "--- 12. the commit boundary ---"
# A writer that changes the reviewed file after the claim, before the branch
# moves. git runs the reference-transaction hook inside update-ref, which is
# exactly that window.
make_task 120
printf 'approved\n' > "$PROJ/src/race.txt"; printf 'bystander\n' > "$PROJ/src/bystander.txt"
git -C "$PROJ" add src/bystander.txt && git -C "$PROJ" commit -q -m bystander -- src/bystander.txt
printf 'edited, never reviewed\n' > "$PROJ/src/bystander.txt"
race="$(ask t120 review_approved o1 approve_start "$PROJ/src/race.txt")"
cat > "$PROJ/.git/hooks/reference-transaction" <<HOOK
#!/bin/sh
[ "\$1" = prepared ] && printf 'unapproved\n' > "$PROJ/src/race.txt"
exit 0
HOOK
chmod +x "$PROJ/.git/hooks/reference-transaction"
out="$(commit_approved 120 "$race")"
rm -f "$PROJ/.git/hooks/reference-transaction"
assert_contains "writer racing the commit: committed" "COMMIT:committed|" "$out"
assert_eq "the racing writer did run" "unapproved" "$(cat "$PROJ/src/race.txt")"
assert_eq "the commit holds the approved bytes, not the writer's" "approved" "$(git -C "$PROJ" show HEAD:src/race.txt)"
assert_eq "the commit holds the bound path only" "src/race.txt" "$(git -C "$PROJ" show --name-only --format= HEAD)"
assert_eq "the unreviewed edit of another file stays uncommitted" "bystander" "$(git -C "$PROJ" show HEAD:src/bystander.txt)"
assert_contains "the writer's bytes are an uncommitted modification" " M src/race.txt" "$(git -C "$PROJ" status --porcelain -- src/race.txt)"
assert_contains "the message is the caller's" "feature: Approved change (t120)" "$(git -C "$PROJ" log -1 --format=%s)"
codex "$GATE" append 120 review_approved pass type=human "approval=$race" >/dev/null 2>&1
assert_eq "writer racing the commit: the approved commit is recordable" "0" "$?"
tip="$(head_of)"
assert_contains "repeating the commit is a no-op" "COMMIT:duplicate|$tip" "$(commit_approved 120 "$race")"
assert_eq "repeating the commit moves nothing" "$tip" "$(head_of)"
git -C "$PROJ" checkout -q -- src/race.txt src/bystander.txt

# A hook that rejects stops the commit before anything is claimed.
make_task 126
printf 'approved\n' > "$PROJ/src/hooked.txt"
hooked="$(ask t126 review_approved o1 approve_start "$PROJ/src/hooked.txt")"
printf '#!/bin/sh\nexit 1\n' > "$PROJ/.git/hooks/commit-msg"; chmod +x "$PROJ/.git/hooks/commit-msg"
before="$(head_of)"
out="$(commit_approved 126 "$hooked")"; rc=$?
rm -f "$PROJ/.git/hooks/commit-msg"
assert_eq "commit-msg hook rejects: exit 3" "3" "$rc"
assert_contains "commit-msg hook rejects: reason" "COMMIT_REFUSED:hook_rejected:commit-msg" "$out"
assert_eq "commit-msg hook rejects: no commit" "$before" "$(head_of)"
assert_contains "commit-msg hook rejects: the receipt is still usable" "COMMIT:committed|" "$(commit_approved 126 "$hooked")"

# The same writer, before the claim: refused, nothing committed.
make_task 121
printf 'approved\n' > "$PROJ/src/early.txt"
early="$(ask t121 review_approved o1 approve_start "$PROJ/src/early.txt")"
printf 'unapproved\n' > "$PROJ/src/early.txt"
before="$(head_of)"
out="$(commit_approved 121 "$early")"; rc=$?
assert_eq "file changed before the commit: exit 3" "3" "$rc"
assert_contains "file changed before the commit: reason" "COMMIT_REFUSED:stale_approval" "$out"
assert_eq "file changed before the commit: branch untouched" "$before" "$(head_of)"
rm -f "$PROJ/src/early.txt"

# Target: the branch gained a different version of an approved path.
make_task 122
printf 'v1\n' > "$PROJ/src/target.txt"
git -C "$PROJ" add src/target.txt && git -C "$PROJ" commit -q -m v1 -- src/target.txt
printf 'reviewed v2\n' > "$PROJ/src/target.txt"
moved="$(ask t122 review_approved o1 approve_start "$PROJ/src/target.txt")"
printf 'someone else\n' > "$PROJ/src/target.txt"
git -C "$PROJ" commit -q -m "concurrent" -- src/target.txt
printf 'reviewed v2\n' > "$PROJ/src/target.txt"
before="$(head_of)"
out="$(commit_approved 122 "$moved")"; rc=$?
assert_eq "branch changed under an approved path: exit 3" "3" "$rc"
assert_contains "branch changed under an approved path: reason" "COMMIT_REFUSED:target_changed:src/target.txt" "$out"
assert_eq "branch changed under an approved path: no commit" "$before" "$(head_of)"
git -C "$PROJ" checkout -q -- src/target.txt

# ...while a commit elsewhere on the branch is not a change of target.
make_task 123
printf 'reviewed\n' > "$PROJ/src/side.txt"; chmod +x "$PROJ/src/side.txt"
side="$(ask t123 review_approved o1 approve_start "$PROJ/src/side.txt")"
printf 'unrelated\n' > "$PROJ/src/unrelated.txt"
git -C "$PROJ" add src/unrelated.txt && git -C "$PROJ" commit -q -m unrelated -- src/unrelated.txt
assert_contains "branch advanced elsewhere: committed" "COMMIT:committed|" "$(commit_approved 123 "$side")"
assert_eq "branch advanced elsewhere: the other commit is kept" "unrelated" "$(git -C "$PROJ" show HEAD:src/unrelated.txt)"
assert_contains "the file mode is the approved one" "100755" "$(git -C "$PROJ" ls-tree HEAD src/side.txt)"

# ...and a different branch is a different target.
make_task 124
printf 'reviewed\n' > "$PROJ/src/branch.txt"
onmain="$(ask t124 review_approved o1 approve_start "$PROJ/src/branch.txt")"
git -C "$PROJ" checkout -q -b elsewhere
out="$(commit_approved 124 "$onmain")"; rc=$?
assert_eq "approved for another branch: exit 3" "3" "$rc"
assert_eq "approved for another branch: nothing on main" "$(git -C "$PROJ" rev-parse main)" "$(git -C "$PROJ" rev-parse elsewhere)"
git -C "$PROJ" checkout -q main

# Not a review approval: a plan receipt commits nothing.
before="$(head_of)"
out="$(commit_approved 20 "$good")"; rc=$?
assert_eq "plan receipt at the commit boundary: exit 3" "3" "$rc"
assert_contains "plan receipt at the commit boundary: reason" "COMMIT_REFUSED:wrong_checkpoint" "$out"
assert_eq "plan receipt at the commit boundary: no commit" "$before" "$(head_of)"

# ---------------------------------------------------------------------------
echo "--- 13. what is committed is what git would store, onto what was there ---"
# A clean filter: the object committed is the filtered form bound at the ask,
# not the working-tree bytes.
git -C "$PROJ" config filter.canon.clean "sed s/WORKTREE/CANONICAL/"
printf '*.flt filter=canon\n' > "$PROJ/.gitattributes"
git -C "$PROJ" add .gitattributes && git -C "$PROJ" commit -q -m attributes -- .gitattributes
make_task 130
printf 'WORKTREE\n' > "$PROJ/src/code.flt"
flt="$(ask t130 review_approved o1 approve_start "$PROJ/src/code.flt")"
assert_contains "filtered path: committed" "COMMIT:committed|" "$(commit_approved 130 "$flt")"
assert_eq "filtered path: the stored object is the clean-filtered form" "CANONICAL" \
    "$(git -C "$PROJ" show HEAD:src/code.flt)"
assert_eq "filtered path: git sees no pending change" "" "$(git -C "$PROJ" status --porcelain -- src/code.flt)"

# The filter changes between the question and the commit: another
# representation than the one bound is not committed.
make_task 131
printf 'WORKTREE again\n' > "$PROJ/src/code2.flt"
flt2="$(ask t131 review_approved o1 approve_start "$PROJ/src/code2.flt")"
git -C "$PROJ" config filter.canon.clean "sed s/WORKTREE/OTHER/"
before="$(head_of)"
out="$(commit_approved 131 "$flt2")"; rc=$?
assert_eq "filter changed since the ask: exit 3" "3" "$rc"
assert_eq "filter changed since the ask: no commit" "$before" "$(head_of)"
git -C "$PROJ" config filter.canon.clean "sed s/WORKTREE/CANONICAL/"

# A pre-commit hook that edits the index: what it drops or adds was not approved.
make_task 132
printf 'one\n' > "$PROJ/src/keep.txt"; printf 'two\n' > "$PROJ/src/code.txt"
hooked="$(ask t132 review_approved o1 approve_start "$PROJ/src/keep.txt" "$PROJ/src/code.txt")"
printf '#!/bin/sh\ngit rm -q --cached src/code.txt\n' > "$PROJ/.git/hooks/pre-commit"
chmod +x "$PROJ/.git/hooks/pre-commit"
before="$(head_of)"
out="$(commit_approved 132 "$hooked")"; rc=$?
assert_eq "pre-commit hook changed the index: exit 3" "3" "$rc"
assert_contains "pre-commit hook changed the index: reason" "COMMIT_REFUSED:hook_changed_index:pre-commit" "$out"
assert_eq "pre-commit hook changed the index: no commit" "$before" "$(head_of)"
# A hook that only inspects still passes.
printf '#!/bin/sh\ngit diff --cached --quiet HEAD && exit 1\nexit 0\n' > "$PROJ/.git/hooks/pre-commit"
assert_contains "pre-commit hook that only inspects: committed" "COMMIT:committed|" "$(commit_approved 132 "$hooked")"
rm -f "$PROJ/.git/hooks/pre-commit"

# The branch changes only the MODE of an approved path (same content).
make_task 133
printf 'v1\n' > "$PROJ/src/mode.txt"
git -C "$PROJ" add src/mode.txt && git -C "$PROJ" commit -q -m mode -- src/mode.txt
printf 'v2\n' > "$PROJ/src/mode.txt"
modal="$(ask t133 review_approved o1 approve_start "$PROJ/src/mode.txt")"
git -C "$PROJ" update-index --chmod=+x --cacheinfo "100755,$(git -C "$PROJ" rev-parse HEAD:src/mode.txt),src/mode.txt"
git -C "$PROJ" commit -q -m "executable now"
git -C "$PROJ" reset -q
before="$(head_of)"
out="$(commit_approved 133 "$modal")"; rc=$?
assert_eq "branch changed the mode of an approved path: exit 3" "3" "$rc"
assert_contains "branch changed the mode of an approved path: reason" "target_changed:src/mode.txt" "$out"
assert_eq "branch changed the mode of an approved path: no commit" "$before" "$(head_of)"
assert_contains "the concurrent mode change is kept" "100755" "$(git -C "$PROJ" ls-tree HEAD src/mode.txt)"

# ---------------------------------------------------------------------------
echo "--- 14. the merge boundary ---"
BROKER="$PROJECT_DIR/.aitask-scripts/aitask_merge_task.sh"
export AITASKS_LOCK_DIR="$TMP/locks"; mkdir -p "$AITASKS_LOCK_DIR"
sleep 600 >/dev/null 2>&1 &
ANCHOR=$!
# shellcheck disable=SC2064
trap "kill $ANCHOR 2>/dev/null || true; $(trap -p EXIT | sed "s/^trap -- '//; s/' EXIT\$//")" EXIT
git -C "$PROJ" checkout -q -- . 2>/dev/null; git -C "$PROJ" clean -qfd -- src >/dev/null 2>&1
git -C "$PROJ" add -A >/dev/null 2>&1; git -C "$PROJ" commit -q -m "settle fixture" >/dev/null 2>&1 || true
branch_with() {  # <branch> <file> <content>: a task branch one commit ahead of main
    git -C "$PROJ" checkout -q -b "$1" main
    printf '%s\n' "$3" > "$PROJ/$2"; git -C "$PROJ" add "$2"; git -C "$PROJ" commit -q -m "$1"
    git -C "$PROJ" checkout -q main
}
guard() { codex "$GATE" merge-guard "$@" 2>/dev/null; }
broker() { ( cd "$PROJ" && unset TASK_DIR PLAN_DIR && AIT_AGENT_PID="$ANCHOR" "$BROKER" "$@" ); }

assert_eq "outside Codex the guard does not apply" "MERGE:unguarded" "$("$GATE" merge-guard 140 main aitask/t140 2>/dev/null)"

make_task 140
branch_with aitask/t140 merged140.txt approved
# An approval that names nothing to merge is not a merge approval.
( ask t140 merge_approved o0 approve_start >/dev/null 2>&1 )
assert_eq "merge approval without source and destination: refused at the ask" "1" "$?"
out="$(guard 140 main aitask/t140)"; rc=$?
assert_eq "no merge approval: exit 3" "3" "$rc"
assert_contains "no merge approval: reason" "MERGE_REFUSED:merge_approval_missing" "$out"

m140="$(ask t140 merge_approved o1 approve_start merge:aitask/t140:main)"
rev140="$(git -C "$PROJ" rev-parse aitask/t140)"
codex "$GATE" append 140 merge_approved pass type=human "approval=$m140" >/dev/null 2>&1
assert_eq "bound merge approval: recorded" "0" "$?"
assert_eq "recorded approval: the guard names the approved revision" "MERGE:approved|$rev140|main" "$(guard 140 main aitask/t140)"
out="$(guard 140 elsewhere aitask/t140)"; rc=$?
assert_eq "another destination: exit 3" "3" "$rc"
assert_contains "another destination: reason" "merge_destination_differs" "$out"
out="$(guard 140 main aitask/t123x)"; rc=$?
assert_eq "another source: exit 3" "3" "$rc"
# The finding: a receipt claimed, then the branch switched - the approval is
# of a revision into a branch, so the checked-out branch is irrelevant...
git -C "$PROJ" checkout -q -b other-view
assert_eq "checked-out branch does not matter" "MERGE:approved|$rev140|main" "$(guard 140 main aitask/t140)"
git -C "$PROJ" checkout -q main
# ...and a source that moved after the approval is refused, for good.
git -C "$PROJ" checkout -q aitask/t140
printf 'unreviewed\n' >> "$PROJ/merged140.txt"; git -C "$PROJ" commit -q -am "after approval"
git -C "$PROJ" checkout -q main
out="$(guard 140 main aitask/t140)"; rc=$?
assert_eq "source moved after the approval: exit 3" "3" "$rc"
assert_contains "source moved after the approval: reason" "merge_source_differs" "$out"
assert_contains "source moved: the approval is stale" "APPROVAL:STALE|" "$(verdict 140 merge_approved)"
git -C "$PROJ" branch -q -f aitask/t140 "$rev140"
out="$(guard 140 main aitask/t140)"; rc=$?
assert_eq "source moved back: still refused" "3" "$rc"

# The broker, in a Codex tool shell, merges only on a standing approval...
make_task 141
branch_with aitask/t141 merged141.txt approved
before="$(git -C "$PROJ" rev-parse main)"
out="$(CODEX_THREAD_ID=thread-1 broker begin 141 main aitask/t141 2>&1)"; rc=$?
assert_eq "broker without a merge approval: exit 2" "2" "$rc"
assert_contains "broker without a merge approval: reason" "APPROVAL_REFUSED:merge_approval_missing" "$out"
assert_eq "broker without a merge approval: main untouched" "$before" "$(git -C "$PROJ" rev-parse main)"
assert_eq "broker without a merge approval: no reservation taken" "FREE" "$(broker status 2>/dev/null | cut -d: -f1)"
# ...and merges the approved revision, not what the name resolves to later.
m141="$(ask t141 merge_approved o1 approve_start merge:aitask/t141:main)"
rev141="$(git -C "$PROJ" rev-parse aitask/t141)"
out="$(CODEX_THREAD_ID=thread-1 broker begin 141 main aitask/t141 --approval "$m141" 2>/dev/null)"
assert_contains "broker with the receipt: merged" "MERGE_OK:" "$out"
assert_eq "broker with the receipt: main holds the approved revision" "0" \
    "$(git -C "$PROJ" merge-base --is-ancestor "$rev141" main; echo $?)"
broker finish 141 >/dev/null 2>&1
assert_contains "after the merge the approval stands by the merge" "is merged into main" "$(verdict 141 merge_approved)"
codex "$GATE" append 141 merge_approved pass type=human "approval=$m141" >/dev/null 2>&1
assert_eq "gate record after the merge reuses the claim" "0" "$?"
git -C "$PROJ" branch -q -D aitask/t141
assert_contains "task branch removed after the merge: still stands" "APPROVAL:FRESH|" "$(verdict 141 merge_approved)"
# The source branch moves between the approval check and the merge (driven
# through the broker's test seam): what lands is the approved revision.
make_task 143
branch_with aitask/t143 merged143.txt approved
m143="$(ask t143 merge_approved o1 approve_start merge:aitask/t143:main)"
rev143="$(git -C "$PROJ" rev-parse aitask/t143)"
: > "$AITASKS_LOCK_DIR/.ait_merge_test_seams"
late="$(git -C "$PROJ" commit-tree -p "$rev143" -m late "$(git -C "$PROJ" rev-parse "$rev143^{tree}")")"
out="$(CODEX_THREAD_ID=thread-1 AIT_MERGE_BROKER_HOOK="git update-ref refs/heads/aitask/t143 $late" \
    broker begin 143 main aitask/t143 --approval "$m143" 2>/dev/null)"
rm -f "$AITASKS_LOCK_DIR/.ait_merge_test_seams"
assert_contains "source moved inside the broker: the merge still runs" "MERGE_OK:" "$out"
assert_eq "source moved inside the broker: the approved revision landed" "0" \
    "$(git -C "$PROJ" merge-base --is-ancestor "$rev143" main; echo $?)"
assert_eq "source moved inside the broker: the later commit did not" "1" \
    "$(git -C "$PROJ" merge-base --is-ancestor "$late" main; echo $?)"
broker finish 143 >/dev/null 2>&1

# Outside Codex the broker is unchanged.
make_task 142
branch_with aitask/t142 merged142.txt plain
out="$(broker begin 142 main aitask/t142 2>/dev/null)"
assert_contains "broker outside Codex: merges without an approval" "MERGE_OK:" "$out"
broker finish 142 >/dev/null 2>&1

# ---------------------------------------------------------------------------
echo "--- 15. the archive boundary ---"
settled() { codex "$GATE" approvals-settled "$1" 2>/dev/null; }
make_task 150
assert_eq "outside Codex the guard does not apply" "APPROVALS:unguarded" "$("$GATE" approvals-settled 150 2>/dev/null)"
assert_contains "nothing asked: settled" "APPROVALS:settled" "$(settled 150)"
printf 'reviewed\n' > "$PROJ/src/r150.txt"
ask t150 review_approved o1 - "$PROJ/src/r150.txt" >/dev/null
out="$(settled 150)"; rc=$?
assert_eq "unanswered review: exit 3" "3" "$rc"
assert_eq "unanswered review: reason" "APPROVALS:blocked|review_approved:unanswered" "$out"
# The archive script itself refuses, and --ignore-gates does not override it.
ARCHIVE="$PROJECT_DIR/.aitask-scripts/aitask_archive.sh"
out="$(cd "$PROJ" && CODEX_THREAD_ID=thread-1 "$ARCHIVE" --dry-run --ignore-gates 150 2>&1)"; rc=$?
assert_eq "archive with an unanswered review: exit 2" "2" "$rc"
assert_contains "archive with an unanswered review: reason" "APPROVAL_PENDING:review_approved:unanswered" "$out"
out="$(cd "$PROJ" && "$ARCHIVE" --dry-run 150 2>&1)"
case "$out" in *APPROVAL_BLOCKED*) other=blocked ;; *) other=unblocked ;; esac
assert_eq "archive outside Codex: not blocked by the question" "unblocked" "$other"

r150="$(ask t150 review_approved o2 revise "$PROJ/src/r150.txt")"
assert_eq "answered 'revise': blocked" "APPROVALS:blocked|review_approved:not_approved" "$(settled 150)"
r150="$(ask t150 review_approved o3 approve_start "$PROJ/src/r150.txt")"
assert_eq "approved, never committed or recorded: blocked" "APPROVALS:blocked|review_approved:not_recorded" "$(settled 150)"
commit_approved 150 "$r150" >/dev/null
assert_contains "approved and committed: settled" "APPROVALS:settled" "$(settled 150)"
printf 'later edit\n' >> "$PROJ/src/r150.txt"
assert_contains "a later edit is new work, not a stale approval" "APPROVALS:settled" "$(settled 150)"
git -C "$PROJ" checkout -q -- src/r150.txt

make_task 151
printf 'reviewed\n' > "$PROJ/src/r151.txt"
ask t151 review_approved o1 cancel "$PROJ/src/r151.txt" >/dev/null
assert_eq "declined review: blocked" "APPROVALS:blocked|review_approved:declined" "$(settled 151)"
make_task 152
printf 'reviewed\n' > "$PROJ/src/r152.txt"
ask t152 review_approved o1 - "$PROJ/src/r152.txt" >/dev/null
printf 'changed\n' > "$PROJ/src/r152.txt"
assert_eq "review voided by a later edit: blocked" "APPROVALS:blocked|review_approved:voided" "$(settled 152)"
# The workflow's closing sections after the approved plan are the one change
# a claimed plan approval is settled under. Nothing else is.
make_task 153
approve 153 o1 >/dev/null
printf '\n## Post-Review Changes\n\n- [x] renamed a flag\n\n## Final Implementation Notes\n\nDone.\n' >> "$PLAN_DIR/p153_demo.md"
assert_contains "claimed plan approval with closing notes: settled" "APPROVALS:settled" "$(settled 153)"
make_task 156
approve 156 o1 >/dev/null
printf -- '---\npriority: high\nstatus: Implementing\n---\n\nBody for t156, and also drop the table.\n' > "$TASK_DIR/t156_demo.md"
assert_contains "requirements changed after approval: revoked" "APPROVAL:STALE" "$(verdict 156)"
assert_eq "requirements changed after approval: blocked" "APPROVALS:blocked|plan_approved:stale" "$(settled 156)"
out="$(cd "$PROJ" && CODEX_THREAD_ID=thread-1 "$ARCHIVE" --dry-run 156 2>&1)"; rc=$?
assert_eq "archive on a revoked plan approval: exit 2" "2" "$rc"
assert_contains "archive on a revoked plan approval: reason" "APPROVAL_PENDING:plan_approved:stale" "$out"
make_task 157
approve 157 o1 >/dev/null
printf 'Plan for t157: do another thing.\n\n## Final Implementation Notes\n\nDone.\n' > "$PLAN_DIR/p157_demo.md"
assert_eq "plan body rewritten under closing notes: blocked" "APPROVALS:blocked|plan_approved:stale" "$(settled 157)"
make_task 158
approve 158 o1 >/dev/null
printf '\n## Final Implementation Notes\n\nDone.\n\n## Extra Step\n\nAlso delete the database.\n' >> "$PLAN_DIR/p158_demo.md"
assert_eq "a new plan section among the closing notes: blocked" "APPROVALS:blocked|plan_approved:stale" "$(settled 158)"
make_task 159
approve 159 o1 >/dev/null
printf 'Also delete the database.\n' >> "$PLAN_DIR/p159_demo.md"
verdict 159 >/dev/null   # observed: revoked for good
printf 'Plan for t159: do the thing.\n\n## Final Implementation Notes\n\nDone.\n' > "$PLAN_DIR/p159_demo.md"
assert_eq "revoked, then dressed as closing notes: still blocked" "APPROVALS:blocked|plan_approved:stale" "$(settled 159)"
ask t153 plan_approved o2 - "$PLAN_DIR/p153_demo.md" >/dev/null
assert_eq "plan asked again and left open: blocked" "APPROVALS:blocked|plan_approved:unanswered" "$(settled 153)"
# A step the profile pre-answers is settled by the profile record.
make_task 154
printf 'reviewed\n' > "$PROJ/src/r154.txt"
ask t154 review_approved o1 - "$PROJ/src/r154.txt" >/dev/null
codex "$GATE" append 154 review_approved pass type=human approval=profile:auto >/dev/null 2>&1
assert_contains "profile-recorded review: settled by the profile" "APPROVALS:settled" "$(settled 154)"
# A review whose commit was removed from the branch no longer stands.
make_task 155
printf 'reviewed\n' > "$PROJ/src/r155.txt"
r155="$(ask t155 review_approved o1 approve_start "$PROJ/src/r155.txt")"
commit_approved 155 "$r155" >/dev/null
git -C "$PROJ" reset -q --soft HEAD~1
assert_eq "reviewed commit dropped from the branch: blocked" "APPROVALS:blocked|review_approved:stale" "$(settled 155)"

# A parent archived together with its last child is checked too, before
# either file is touched.
make_child() {  # <parent> <child> <children_to_implement csv>
    printf -- '---\npriority: high\nstatus: Implementing\nchildren_to_implement: [%s]\n---\n\nParent t%s.\n' "$3" "$1" > "$TASK_DIR/t$1_demo.md"
    mkdir -p "$TASK_DIR/t$1"
    printf -- '---\npriority: high\nstatus: Implementing\n---\n\nChild.\n' > "$TASK_DIR/t$1/t$1_$2_part.md"
}
make_child 160 1 "t160_1"
printf 'reviewed\n' > "$PROJ/src/r160.txt"
ask t160 review_approved o1 - "$PROJ/src/r160.txt" >/dev/null
before="$(cd "$PROJ" && find "$TASK_DIR" -path '*160*' -type f -exec cksum {} + | sort)"
out="$(cd "$PROJ" && CODEX_THREAD_ID=thread-1 "$ARCHIVE" --no-commit 160_1 2>&1)"; rc=$?
assert_eq "last child with an open parent review: exit 2" "2" "$rc"
assert_contains "last child with an open parent review: names the parent" "of t160 is open" "$out"
assert_contains "last child with an open parent review: reason" "APPROVAL_PENDING:review_approved:unanswered" "$out"
assert_eq "last child with an open parent review: nothing written" "$before" \
    "$(cd "$PROJ" && find "$TASK_DIR" -path '*160*' -type f -exec cksum {} + | sort)"
make_child 161 1 "t161_1, t161_2"
printf 'reviewed\n' > "$PROJ/src/r161.txt"
ask t161 review_approved o1 - "$PROJ/src/r161.txt" >/dev/null
out="$(cd "$PROJ" && CODEX_THREAD_ID=thread-1 "$ARCHIVE" --dry-run 161_1 2>&1)"
case "$out" in *APPROVAL_BLOCKED*) other=blocked ;; *) other=unblocked ;; esac
assert_eq "a child whose parent stays open is not held by the parent's review" "unblocked" "$other"
out="$(cd "$PROJ" && "$ARCHIVE" --dry-run 160_1 2>&1)"
case "$out" in *APPROVAL_BLOCKED*) other=blocked ;; *) other=unblocked ;; esac
assert_eq "last child outside Codex: not blocked by the parent's question" "unblocked" "$other"

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
if [[ "$FAIL" -gt 0 ]]; then
    exit 1
else
    echo "All tests PASSED"
fi
