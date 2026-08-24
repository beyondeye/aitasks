#!/usr/bin/env bash
# test_merge_broker_rendered_verdicts.sh - the Step 9 merge broker's rendered
# control flow must define a disposition for EVERY verdict the broker can emit
# (t1560_2).
#
# The unit of coverage is a **verb-qualified table row**, not a token. NOT_HELD
# appears under finish, abort AND cleanup, and RETAINED under begin, finish and
# abort, so a `grep -w` union over the rendered text passes with an entire
# verb's branch missing. Negative control 1 pins exactly that case.
#
# Coverage:
#   1. Every (verb, verdict) from `aitask_merge_task.sh --list-verdicts` has
#      exactly one row; no row exists for an undeclared token.
#   2. Closed column vocabularies + equal alternation arity.
#   3. The ABORT_UNSAFE branch echoes the broker-supplied remedy flag and
#      hardcodes neither --abort-merge nor --reset-hard.
#   4. The rendered merge-approval question still matches the real
#      workflow_phase.WORKFLOW_PROMPTS merge_approval regex.
#   5. Every handoff anchor exists in the procedure AND is referenced from
#      SKILL.md (bidirectional).
#   6. Handoff ORDERING on the rendered SKILL.md: the acquire-side anchor
#      precedes `ait gates run` and the release-side anchor follows it — the
#      structural proof that verification runs inside the held window.
#   7. Branch linkage: one `#### <verb> / <TOKEN>` per row, no orphans, and the
#      branch body names its row's terminal-release and continues-to values.
#   I1-I8 + the verification-outcome invariants (the executable form of the
#      held-lock invariant), and the verb drift guard.
#
# Run: bash tests/test_merge_broker_rendered_verdicts.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

PASS=0
FAIL=0
TOTAL=0

# shellcheck source=tests/lib/asserts.sh
. "$PROJECT_DIR/tests/lib/asserts.sh"

cd "$PROJECT_DIR"

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER="$PYTHON $PROJECT_DIR/.aitask-scripts/lib/skill_template.py"
WORKFLOW_DIR=".claude/skills/task-workflow"
PROFILES_DIR="aitasks/metadata/profiles"
BROKER="./.aitask-scripts/aitask_merge_task.sh"
PROFILES=(default fast remote)

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

# The vocabulary comes from the LIVE seam, never a transcription in this file.
"$BROKER" --list-verdicts > "$TMP/verdicts.txt"

CHECKER="$TMP/check.py"
cat > "$CHECKER" <<'PYEOF'
"""Parse the rendered merge-broker disposition tables and check them against
the broker's live verdict vocabulary. Prints one finding per line; prints
CHECK_OK and exits 0 when clean, exits 1 otherwise."""
import pathlib
import re
import sys

MB_PATH, SK_PATH, VOCAB_PATH = sys.argv[1], sys.argv[2], sys.argv[3]

LOCK = {"ours-held", "not-ours", "none"}
REL = {"finish", "abort", "ladder", "none"}
THRU = {"n/a", "immediate", "verification", "verification+cleanup"}
CONT = {"approval", "verification", "archival", "caller-path",
        "stop-in-flight", "stop", "recovery"}
TLOCK = {"released", "held-ladder", "n/a"}

# The verification-outcome table has its own vocabulary.
V_CLEAN = {"`--task-complete`", "no"}
V_CONT = {"archival", "re-run", "stop-in-flight"}

VERBS = ["begin", "finish", "abort", "cleanup", "status"]

ANCHORS = [
    "## Probe — report the queue holder",
    "## Entry — acquire the reservation and merge",
    "## Return to Step 9 — Verify implementation",
    "## Re-entry — release decision",
    "## Exit — cleanup and release",
]

findings = []


def bad(msg):
    findings.append(msg)


mb = pathlib.Path(MB_PATH).read_text(encoding="utf-8")
sk = pathlib.Path(SK_PATH).read_text(encoding="utf-8")

# ---------------------------------------------------------------- vocabulary
vocab = {}
for line in pathlib.Path(VOCAB_PATH).read_text(encoding="utf-8").splitlines():
    if ":" not in line:
        continue
    verb, rest = line.split(":", 1)
    vocab[verb.strip()] = rest.split()

# --- verb drift guard: a NEW broker verb must not escape coverage silently.
declared = set(vocab) - {"force-release"}
if declared != set(VERBS):
    bad("VERB_DRIFT:missing=%s:unexpected=%s" % (
        ",".join(sorted(set(VERBS) - declared)) or "-",
        ",".join(sorted(declared - set(VERBS))) or "-"))

# ------------------------------------------------------------- table parsing
SENTINEL = "\x00"


def split_row(line):
    tmp = line.strip().replace("\\|", SENTINEL)
    cells = [c.strip() for c in tmp.strip("|").split("|")]
    return [c.replace(SENTINEL, "|") for c in cells]


def table_after(text, heading):
    """Rows of the first markdown table following an exact heading line."""
    lines = text.splitlines()
    try:
        i = next(n for n, l in enumerate(lines) if l.strip() == heading)
    except StopIteration:
        return None
    j = i + 1
    while j < len(lines) and not lines[j].strip():
        j += 1
    if j >= len(lines) or not lines[j].lstrip().startswith("|"):
        return None
    j += 2  # header row + separator row
    rows = []
    while j < len(lines) and lines[j].lstrip().startswith("|"):
        rows.append(split_row(lines[j]))
        j += 1
    return rows


def token_of(cell):
    return cell.strip().strip("`").split(":", 1)[0]


def alts(cell):
    return [a.strip() for a in cell.split(";")]


# -------------------------------------------------------------- branch bodies
branch_re = re.compile(r"^####[ \t]+([a-z-]+)[ \t]*/[ \t]*([A-Z_]+)[ \t]*$", re.M)
branches = {}
for src in (mb, sk):
    lines = src.splitlines()
    for n, line in enumerate(lines):
        m = branch_re.match(line)
        if not m:
            continue
        key = (m.group(1), m.group(2))
        body = []
        for l in lines[n + 1:]:
            if l.startswith("#### ") or l.startswith("## "):
                break
            body.append(l)
        if key in branches:
            bad("DUPLICATE_BRANCH:%s:%s" % key)
        branches[key] = "\n".join(body)

# ------------------------------------------------------- per-verb disposition
seen_rows = set()
for verb in VERBS:
    heading = "### `%s` verdicts" % verb
    rows = table_after(mb, heading)
    if rows is None:
        bad("MISSING_TABLE:%s" % verb)
        continue
    by_token = {}
    for cells in rows:
        if len(cells) != 6:
            bad("BAD_ROW_SHAPE:%s:%s" % (verb, cells[0] if cells else "?"))
            continue
        tok = token_of(cells[0])
        by_token.setdefault(tok, []).append(cells)

    for tok, dupes in by_token.items():
        if len(dupes) > 1:
            bad("DUPLICATE_ROW:%s:%s" % (verb, tok))
        if tok not in vocab.get(verb, []):
            bad("UNKNOWN_ROW:%s:%s" % (verb, tok))

    for tok in vocab.get(verb, []):
        if tok not in by_token:
            bad("MISSING_ROW:%s:%s" % (verb, tok))
            continue
        seen_rows.add((verb, tok))
        cells = by_token[tok][0]
        cols = {
            "lock": alts(cells[1]),
            "terminal-release": alts(cells[2]),
            "lock-through": alts(cells[3]),
            "continues-to": alts(cells[4]),
            "terminal-lock": alts(cells[5]),
        }
        vocabs = {"lock": LOCK, "terminal-release": REL, "lock-through": THRU,
                  "continues-to": CONT, "terminal-lock": TLOCK}
        for name, vals in cols.items():
            for v in vals:
                if v not in vocabs[name]:
                    bad("BAD_VALUE:%s:%s:%s=%s" % (verb, tok, name, v))

        widths = {len(v) for v in cols.values() if len(v) > 1}
        if len(widths) > 1:
            bad("ARITY_MISMATCH:%s:%s" % (verb, tok))
            continue
        arity = max(widths) if widths else 1

        for i in range(arity):
            def g(name):
                vals = cols[name]
                return vals[i] if len(vals) > 1 else vals[0]

            lock, rel, thru = g("lock"), g("terminal-release"), g("lock-through")
            cont, tlock = g("continues-to"), g("terminal-lock")

            if lock == "ours-held" and rel not in {"finish", "abort", "ladder"}:
                bad("I1:%s:%s" % (verb, tok))
            if lock in {"none", "not-ours"} and not (
                    rel == "none" and thru == "n/a" and tlock == "n/a"):
                bad("I2:%s:%s" % (verb, tok))
            if cont in {"verification", "archival"} and lock != "ours-held":
                bad("I3:%s:%s" % (verb, tok))
            if cont == "archival" and rel != "finish":
                bad("I4:%s:%s" % (verb, tok))
            if cont == "verification" and thru not in {
                    "verification", "verification+cleanup"}:
                bad("I6:%s:%s" % (verb, tok))
            if not ((rel == "ladder") == (cont == "recovery") == (tlock == "held-ladder")):
                bad("I7:%s:%s" % (verb, tok))
            if rel in {"finish", "abort"} and tlock != "released":
                bad("I8:%s:%s" % (verb, tok))

        # --- branch linkage: the prose must exist and must not contradict.
        if (verb, tok) not in branches:
            bad("MISSING_BRANCH:%s:%s" % (verb, tok))
        else:
            body = branches[(verb, tok)]
            for name in ("terminal-release", "continues-to"):
                for v in cols[name]:
                    if "`%s`" % v not in body:
                        bad("BRANCH_CONTRADICTS_ROW:%s:%s:%s" % (verb, tok, name))

for key in branches:
    if key not in seen_rows:
        bad("ORPHAN_BRANCH:%s:%s" % key)

# --------------------------------------------- verification-outcome (§4a)
vrows = table_after(mb, "### Verification outcomes")
if vrows is None:
    bad("MISSING_TABLE:verification-outcomes")
else:
    for cells in vrows:
        if len(cells) != 5:
            bad("BAD_ROW_SHAPE:verification-outcomes")
            continue
        outcome, clean, rel, thru, cont = cells
        label = outcome[:28]
        if clean not in V_CLEAN:
            bad("BAD_VALUE:verification-outcomes:%s:cleanup=%s" % (label, clean))
        if rel not in REL:
            bad("BAD_VALUE:verification-outcomes:%s:terminal-release=%s" % (label, rel))
        if cont not in V_CONT:
            bad("BAD_VALUE:verification-outcomes:%s:continues-to=%s" % (label, cont))
        # I5: cleanup is a COMPLETION step - an in-flight row must never archive.
        if clean == "no" and cont == "archival":
            bad("I5:verification-outcomes:%s" % label)
        # I5b: the reservation spans the gates run on every outcome.
        if not thru.startswith("verification"):
            bad("I5b:verification-outcomes:%s" % label)

# ------------------------------------- injection safety at the broker call
# The git primitives moved out of SKILL.md Step 9 INTO the broker; the
# injection-safety property moved with them and is re-pinned here. The branch
# name is user-authored and git accepts refs containing shell metacharacters
# (`dev$(id)` is a valid ref and expands inside double quotes), so the call must
# consume the BOUND variable, never a substituted literal.
if '"$output_branch" "aitask/<task_name>"' not in mb:
    bad("BEGIN_CALL_NOT_BOUND")
for m in re.finditer(r"^[ \t]*\./\.aitask-scripts/aitask_merge_task\.sh .*$", mb, re.M):
    if "<output_branch>" in m.group(0):
        bad("BEGIN_CALL_SUBSTITUTES_LITERAL")

# ------------------------------------------------ ABORT_UNSAFE remedy echo
au = branches.get(("abort", "ABORT_UNSAFE"), "")
for lit in ("--abort-merge", "--reset-hard"):
    if lit in au:
        bad("HARDCODED_REMEDY:abort:ABORT_UNSAFE:%s" % lit)

# ----------------------------------------------------- handoff anchors (5)
for a in ANCHORS:
    if not re.search(r"^%s[ \t]*$" % re.escape(a), mb, re.M):
        bad("ANCHOR_MISSING_IN_PROCEDURE:%s" % a)
    if a not in sk:
        bad("ANCHOR_NOT_REFERENCED_IN_SKILL:%s" % a)

# ------------------------------------- handoff ORDERING on rendered SKILL.md
sk_lines = sk.splitlines()


def first_idx(sub):
    for n, l in enumerate(sk_lines):
        if sub in l:
            return n
    return -1


i_enter = first_idx("## Return to Step 9 — Verify implementation")
i_gates = first_idx('gates_out="$(./ait gates run')
i_exit = first_idx("## Re-entry — release decision")
if min(i_enter, i_gates, i_exit) < 0:
    bad("ORDER_ANCHOR_MISSING:enter=%d:gates=%d:exit=%d" % (i_enter, i_gates, i_exit))
elif not (i_enter < i_gates < i_exit):
    bad("ORDER_VIOLATION:enter=%d:gates=%d:exit=%d" % (i_enter, i_gates, i_exit))

# ------------------------------------------- merge-approval prompt contract
sys.path.insert(0, str(pathlib.Path(".aitask-scripts/lib").resolve()))
import workflow_phase as wp  # noqa: E402

merge_prompts = [p for p in wp.WORKFLOW_PROMPTS if p.name == "merge_approval"]
if not merge_prompts:
    bad("PROMPT_RULE_MISSING")

# Extract the ACTUAL rendered approval question and match THAT. Asserting a
# hardcoded copy of the question would keep passing while a rewrite broke the
# real phase anchor, which is the whole thing this check exists to catch.
qline = next((l for l in sk_lines
              if "Proceed with merge of code changes into" in l), None)
if qline is None:
    bad("PROMPT_ANCHOR_MISSING")
else:
    m = re.search(r'"([^"]*Proceed with merge of code changes into[^"]*)"', qline)
    if not m:
        bad("QUESTION_NOT_EXTRACTED")
    else:
        # Instantiate the placeholders the way Step 9 does at runtime.
        concrete = (m.group(1)
                    .replace("<output_branch>", "main")
                    .replace("\\<provenance\\>", "plan header")
                    .replace("<provenance>", "plan header"))
        # Both shapes must match: without the queued clause, and with it
        # appended - the clause is the only thing t1560_2 adds to the question.
        for variant, label in ((concrete, "plain"),
                               (concrete + " Queued behind t123.", "queued")):
            if not any(p.regex.search(variant) for p in merge_prompts):
                bad("PROMPT_NO_MATCH:%s" % label)
if "Queued behind t<N>." not in sk:
    bad("QUEUED_CLAUSE_MISSING")

for f in findings:
    print(f)
if findings:
    sys.exit(1)
print("CHECK_OK")
PYEOF

# ---------------------------------------------------------------------------
echo "=== Test 1: every verdict has a verb-qualified row + branch, per profile ==="
for profile in "${PROFILES[@]}"; do
    $RENDER "$WORKFLOW_DIR/merge-broker.md" "$PROFILES_DIR/$profile.yaml" claude \
        > "$TMP/mb-$profile.md"
    $RENDER "$WORKFLOW_DIR/SKILL.md" "$PROFILES_DIR/$profile.yaml" claude \
        > "$TMP/sk-$profile.md"
    set +e
    OUT="$("$PYTHON" "$CHECKER" "$TMP/mb-$profile.md" "$TMP/sk-$profile.md" "$TMP/verdicts.txt" 2>&1)"
    RC=$?
    set -e
    assert_exit_zero_rc "profile $profile: rendered dispositions are complete and consistent" "$RC"
    if [[ "$RC" -ne 0 ]]; then
        printf '%s\n' "$OUT" | sed 's/^/      /'
    else
        assert_contains "profile $profile: checker reports CHECK_OK" "CHECK_OK" "$OUT"
    fi
done

# ---------------------------------------------------------------------------
# Negative controls. Each is ONE mutation of the rendered procedure, and each
# must fail NAMING the specific row and check - not merely go red somewhere.
# ---------------------------------------------------------------------------
echo "=== Test 2: negative controls ==="

MB="$TMP/mb-default.md"
SK="$TMP/sk-default.md"

mutate() {   # mutate <out> <python-expr-file>
    "$PYTHON" - "$MB" "$1" <<PYEOF
import pathlib, re, sys
src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
$2
pathlib.Path(sys.argv[2]).write_text(src, encoding="utf-8")
PYEOF
}

run_checker() {   # run_checker <mutated_mb> -> sets NC_OUT / NC_RC
    set +e
    NC_OUT="$("$PYTHON" "$CHECKER" "$1" "$SK" "$TMP/verdicts.txt" 2>&1)"
    NC_RC=$?
    set -e
}

# --- Control A: delete the cleanup/NOT_HELD ROW while finish/ and abort/
# NOT_HELD rows remain. A token-union check passes here; a verb-qualified one
# must not. This is the control that proves the check is verb-qualified.
mutate "$TMP/nc_a.md" 'sec = src.split("### `cleanup` verdicts")
sec[1] = re.sub(r"^\| `NOT_HELD` \|.*\n", "", sec[1], count=1, flags=re.M)
src = "### `cleanup` verdicts".join(sec)'
run_checker "$TMP/nc_a.md"
assert_exit_nonzero_rc "control A: a deleted cleanup row fails the build" "$NC_RC"
assert_contains "control A: names cleanup:NOT_HELD specifically" \
    "MISSING_ROW:cleanup:NOT_HELD" "$NC_OUT"
assert_not_contains "control A: the finish/abort NOT_HELD rows still pass" \
    "MISSING_ROW:finish:NOT_HELD" "$NC_OUT"
assert_not_contains "control A: the abort NOT_HELD row still passes" \
    "MISSING_ROW:abort:NOT_HELD" "$NC_OUT"

# --- Control B: delete the begin/RETAINED row; finish/ and abort/ RETAINED stay.
mutate "$TMP/nc_b.md" 'sec = src.split("### `begin` verdicts")
sec[1] = re.sub(r"^\| `RETAINED:<inner>` \|.*\n", "", sec[1], count=1, flags=re.M)
src = "### `begin` verdicts".join(sec)'
run_checker "$TMP/nc_b.md"
assert_exit_nonzero_rc "control B: a deleted begin row fails the build" "$NC_RC"
assert_contains "control B: names begin:RETAINED specifically" \
    "MISSING_ROW:begin:RETAINED" "$NC_OUT"
assert_not_contains "control B: the finish RETAINED row still passes" \
    "MISSING_ROW:finish:RETAINED" "$NC_OUT"

# --- Control C: release BEFORE verification. Flip begin/MERGE_OK's lock-through
# from verification+cleanup to immediate. This is the merge race reopening: a
# check that only asks "is a release verb permitted" (I1) accepts it. The
# mutation must reach I6, not trip an earlier assertion.
mutate "$TMP/nc_c.md" 'src = src.replace(
    "| `MERGE_OK:<sha>` | ours-held | finish | verification+cleanup | verification | released |",
    "| `MERGE_OK:<sha>` | ours-held | finish | immediate | verification | released |", 1)'
run_checker "$TMP/nc_c.md"
assert_exit_nonzero_rc "control C: releasing before verification fails the build" "$NC_RC"
assert_contains "control C: names I6 on begin:MERGE_OK" "I6:begin:MERGE_OK" "$NC_OUT"
assert_not_contains "control C: it is NOT caught as a coverage miss" \
    "MISSING_ROW:begin:MERGE_OK" "$NC_OUT"
assert_not_contains "control C: I1 accepts it - only I6 rejects it" \
    "I1:begin:MERGE_OK" "$NC_OUT"

# --- Control D: a correct table beside contradicting prose. Rewrite the
# abort/ABORT_FAILED branch body to instruct `finish` where the row says
# `ladder`.
mutate "$TMP/nc_d.md" 'i = src.index("#### abort / ABORT_FAILED")
j = src.index("#### abort / ABORT_UNSAFE")
src = src[:i] + src[i:j].replace("`ladder`", "`finish`") + src[j:]'
run_checker "$TMP/nc_d.md"
assert_exit_nonzero_rc "control D: prose contradicting its row fails the build" "$NC_RC"
assert_contains "control D: names the row and the column" \
    "BRANCH_CONTRADICTS_ROW:abort:ABORT_FAILED:terminal-release" "$NC_OUT"

# --- Control E: a NEW broker verb must not escape coverage silently. Feed the
# checker a vocabulary declaring a verb the test does not cover.
cp "$TMP/verdicts.txt" "$TMP/verdicts_e.txt"
printf 'reserve: OK FAILED\n' >> "$TMP/verdicts_e.txt"
set +e
NC_OUT="$("$PYTHON" "$CHECKER" "$MB" "$SK" "$TMP/verdicts_e.txt" 2>&1)"
NC_RC=$?
set -e
assert_exit_nonzero_rc "control E: an uncovered broker verb fails the build" "$NC_RC"
assert_contains "control E: names the unexpected verb" "unexpected=reserve" "$NC_OUT"

# --- Control F: cleanup is a COMPLETION step. Let an in-flight verification
# outcome reach archival and I5 must catch it.
mutate "$TMP/nc_f.md" 'src = src.replace(
    "| `error` / `blocked:` / `pending` | no | finish | verification | stop-in-flight |",
    "| `error` / `blocked:` / `pending` | no | finish | verification | archival |", 1)'
run_checker "$TMP/nc_f.md"
assert_exit_nonzero_rc "control F: an in-flight row reaching archival fails the build" "$NC_RC"
assert_contains "control F: names I5 on the verification-outcome row" \
    "I5:verification-outcomes:" "$NC_OUT"

# --- Control G: the merge-approval question must be matched as RENDERED. A
# reworded prefix must break this test, or the phase-anchor contract with
# workflow_phase.WORKFLOW_PROMPTS is unguarded.
"$PYTHON" - "$SK" "$TMP/sk_g.md" <<'PYEOF'
import pathlib
import sys
t = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
t = t.replace("Proceed with merge of code changes into",
              "Shall we land these code changes on")
pathlib.Path(sys.argv[2]).write_text(t, encoding="utf-8")
PYEOF
set +e
NC_OUT="$("$PYTHON" "$CHECKER" "$MB" "$TMP/sk_g.md" "$TMP/verdicts.txt" 2>&1)"
NC_RC=$?
set -e
assert_exit_nonzero_rc "control G: a reworded approval prefix fails the build" "$NC_RC"
assert_contains "control G: names the broken phase anchor" \
    "PROMPT_ANCHOR_MISSING" "$NC_OUT"

# --- Summary ---
echo
echo "PASS: $PASS, FAIL: $FAIL, TOTAL: $TOTAL"
[[ "$FAIL" -eq 0 ]]
