#!/usr/bin/env bash
# Contract test for the workflow-end banners (t1913).
#
# `task-workflow/workflow-end.md` defines the one closing message every run ends
# with: `## Complete` at Step 10, `## Stopped` at every early or alternate exit.
# Exit sites reference it instead of copying it. This test pins that every exit
# BRANCH carries the reference. A per-file check is not enough: a file holding
# one reference can still have several uncovered exits.
#
#   Guard 0  the procedure exists and carries both banner first-line keys.
#   Guard 1  per-branch scan. Every line in the task-workflow procedures and
#            the pickrem/pickweb templates that ends a run must sit in a list
#            item or paragraph that references workflow-end.md with an outcome,
#            or must be on the explicit allowlist below (descriptive or relayed
#            mentions). An allowlist entry that matches nothing fails, so the
#            allowlist cannot rot.
#   Guard 2  outcome accuracy. `outcome=unchanged` in SKILL.md is reserved for
#            exits before the Step 6 heading (pre-claim / pre-plan).
#   Guard 3  Step 10 and its NON-SKIPPABLE marker render under every profile.
#   Guard 4  negative controls. The scanner rejects a file whose other branches
#            are covered but one branch lost its reference, and it rejects a
#            stale allowlist entry.
#
# Every check asserts a hit count. A grep that silently matches nothing reads
# exactly like a clean result.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
# Start from an empty read-only dir, never the invoking one (t1826).
. "$PROJECT_DIR/tests/lib/scratch_cwd.sh"
enter_scratch_cwd
cd "$PROJECT_DIR" || exit 1

# shellcheck source=lib/asserts.sh
source "$SCRIPT_DIR/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0

TW=".claude/skills/task-workflow"
PROC="$TW/workflow-end.md"
PICKREM=".claude/skills/aitask-pickrem/SKILL.md.j2"
PICKWEB=".claude/skills/aitask-pickweb/SKILL.md.j2"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

check() {
    local name="$1" expected="$2" actual="$3"
    TOTAL=$((TOTAL + 1))
    if [[ "$expected" == "$actual" ]]; then
        PASS=$((PASS + 1)); echo "  PASS: $name"
    else
        FAIL=$((FAIL + 1)); echo "  FAIL: $name (expected $expected, got $actual)"
    fi
}

# --- the per-branch scanner -------------------------------------------------
cat > "$TMP/scan.py" <<'PY'
"""Report exit lines whose enclosing block lacks a workflow-end.md reference."""
import re
import sys

EXIT_RE = re.compile(
    r"(?i:\bend(?:s)? (?:(?:the|this) )?(?:workflow|session)\b)"
    r"|\bOtherwise: abort\b|\band abort\b|\*\*Abort\.\*\*"
    r"|(?<![\w`\"])Abort\.(?=\s|$)|\bthen stop\b")
# Option labels describe a choice; the branch that handles it is the exit.
DESC_RE = re.compile(r'\(description: "[^"]*("\)|$)')
ITEM_RE = re.compile(r"^(\s*)(?:[-*]|\d+\.)\s")
REF_RE = re.compile(r"workflow-end\.md")
OUT_RE = re.compile(
    r"outcome=(?:in-flight|ready|aborted|split|unchanged)\b|state-derived")


def indent(line):
    return len(line) - len(line.lstrip(" "))


def transparent(line):
    # Jinja tag lines are template plumbing, not document structure.
    s = line.strip()
    return s.startswith("{%") or s.startswith("{#")


def boundary(line):
    return not line.strip() or line.lstrip().startswith("#")


def block(lines, i):
    """(start, end) of the list item or paragraph enclosing line i."""
    li = indent(lines[i])
    start = None
    for j in range(i, -1, -1):
        line = lines[j]
        if transparent(line):
            continue
        if boundary(line):
            break
        m = ITEM_RE.match(line)
        if m and (j == i or len(m.group(1)) < li):
            start = j
            break
    if start is None:
        a = i
        while a > 0 and not boundary(lines[a - 1]):
            a -= 1
        b = i
        while b + 1 < len(lines) and lines[b + 1].strip():
            b += 1
        return a, b
    k = indent(lines[start])
    end = start
    for j in range(start + 1, len(lines)):
        line = lines[j]
        if not line.strip() or transparent(line):
            continue
        if indent(line) <= k or line.lstrip().startswith("#"):
            break
        end = j
    return start, end


def main():
    allow_path, files = sys.argv[1], sys.argv[2:]
    allow = []
    for raw in open(allow_path, encoding="utf-8").read().splitlines():
        if raw.strip() and not raw.startswith("#"):
            f, sub = raw.split("|", 1)
            allow.append((f, sub))
    used = set()
    covered = uncovered = 0
    for path in files:
        lines = open(path, encoding="utf-8").read().split("\n")
        fence = False
        for i, raw in enumerate(lines):
            if raw.lstrip().startswith("```"):
                fence = not fence
                continue
            if fence or not EXIT_RE.search(DESC_RE.sub("", raw)):
                continue
            hits = [n for n, (f, sub) in enumerate(allow)
                    if path.endswith(f) and sub in raw]
            if hits:
                used.update(hits)
                continue
            a, b = block(lines, i)
            text = "\n".join(lines[a:b + 1])
            if REF_RE.search(text) and OUT_RE.search(text):
                covered += 1
            else:
                uncovered += 1
                print(f"UNCOVERED:{path}:{i + 1}:{raw.strip()[:120]}")
    for n, (f, sub) in enumerate(allow):
        if n not in used:
            print(f"STALE_ALLOW:{f}|{sub}")
    print(f"COVERED:{covered}")
    print(f"UNCOVERED_COUNT:{uncovered}")


main()
PY

# Descriptive or relayed mentions: a line that talks ABOUT an exit owned by a
# procedure that shows its own banner, or an exit before any task number exists.
cat > "$TMP/allow.txt" <<'ALLOW'
# --- relays: the called procedure shows the banner itself ---
SKILL.md|If the procedure ends the workflow ("Stop and re-verify plan" or "Abort task")
SKILL.md|It never ends the workflow on its own
SKILL.md|If it ends the session ("Stop here")
SKILL.md|the procedure ends the workflow — do not archive
planning.md|If the procedure ends the workflow ("Stop and re-verify plan" or "Abort task")
planning.md|If it ends the workflow ("Stop and re-verify plan" or "Abort task")
remote-drift-check.md|The shared sequence ends the workflow
parallel-admission.md|sequence ends the workflow — do NOT proceed to Step 7
# --- descriptive prose ---
SKILL.md|This check never ends the workflow
SKILL.md|that *end the workflow* when they fire
SKILL.md|revert the task to `Ready` and end the session before any code is written
planning.md|That procedure records the approval (audit only
manual-verification.md|or ends the workflow early when the user chooses
parallel-admission.md|no verdict ever ends the workflow on its own
risk-mitigation-followup.md|release lock, end workflow) — see the Step 7 dispatch
# --- no task number yet: not a workflow run (workflow-end.md Rules) ---
aitask-pickrem/SKILL.md.j2|This skill will NOT work without a task ID argument
aitask-pickweb/SKILL.md.j2|This skill will NOT work without a task ID argument
ALLOW

scan_files=()
for f in "$TW"/*.md; do
    [[ "$f" == "$PROC" ]] && continue
    scan_files+=("$f")
done
scan_files+=("$PICKREM" "$PICKWEB")

echo "=== Guard 0: the procedure and its banner keys ==="
check "$PROC exists" "1" "$([[ -f "$PROC" ]] && echo 1 || echo 0)"
check "complete first-line key" "1" \
    "$(grep -cF '✔ aitask workflow complete — t<task_id> <task_name>' "$PROC")"
check "stopped first-line key" "1" \
    "$(grep -cF '■ aitask workflow stopped — t<task_id> <task_name>' "$PROC")"
for v in in-flight ready aborted split unchanged; do
    check "outcome '$v' defined in the vocabulary table" "1" \
        "$(grep -cE "^\| \`$v\` \|" "$PROC")"
done

echo
echo "=== Guard 1: every exit branch references the procedure ==="
check "scanned file count" "1" "$([[ "${#scan_files[@]}" -ge 30 ]] && echo 1 || echo 0)"
out="$(python3 "$TMP/scan.py" "$TMP/allow.txt" "${scan_files[@]}")"
echo "$out" | grep -E '^(UNCOVERED|STALE_ALLOW):' | sed 's/^/    /'
check "no uncovered exit branch" "0" "$(echo "$out" | grep -c '^UNCOVERED:')"
check "no stale allowlist entry" "0" "$(echo "$out" | grep -c '^STALE_ALLOW:')"
covered="$(echo "$out" | sed -n 's/^COVERED://p')"
check "covered branch count is substantial (>= 40)" "1" \
    "$([[ "${covered:-0}" -ge 40 ]] && echo 1 || echo 0)"

# The shared exit procedures and both remote templates each carry the reference.
for f in "$TW/SKILL.md" "$TW/plan-approved-stop.md" "$TW/task-abort.md" \
         "$TW/merge-broker.md" "$TW/merge-target-sync.md" \
         "$TW/manual-verification.md" "$TW/planning.md" \
         "$TW/cross-repo-child-assignment.md" "$TW/parallel-assessment.md" \
         "$TW/execution-profile-selection-auto.md" "$PICKREM" "$PICKWEB"; do
    check "$(basename "$(dirname "$f")")/$(basename "$f") references workflow-end.md" "1" \
        "$([[ "$(grep -c 'workflow-end\.md' "$f")" -ge 1 ]] && echo 1 || echo 0)"
done

echo
echo "=== Guard 2: outcome=unchanged only before Step 6 in SKILL.md ==="
step6="$(grep -n '^### Step 6:' "$TW/SKILL.md" | head -n1 | cut -d: -f1)"
check "Step 6 heading found" "1" "$([[ -n "$step6" ]] && echo 1 || echo 0)"
# The Step 7 line that FORBIDS reusing Step 4's outcome names the token too.
unchanged_lines="$(grep -n 'outcome=unchanged' "$TW/SKILL.md" | grep -v "reuse Step 4's" | cut -d: -f1)"
n_unchanged="$(printf '%s\n' "$unchanged_lines" | grep -c .)"
check "SKILL.md unchanged-outcome sites (Step 3 x3, Step 4 x5)" "8" "$n_unchanged"
late=0
for ln in $unchanged_lines; do
    [[ "$ln" -ge "${step6:-0}" ]] && late=$((late + 1))
done
check "no unchanged-outcome site at or after Step 6" "0" "$late"
# Step 7's guard runs after the claim and the plan commit: it derives its outcome.
check "Step 7 guard forbids reusing Step 4's unchanged" "1" \
    "$(grep -c "\*\*Never\*\* reuse Step 4's \`outcome=unchanged\` here" "$TW/SKILL.md")"

echo
echo "=== Guard 3: Step 10 renders under every profile ==="
PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for profile in default fast remote; do
    rendered="$("$PYTHON" .aitask-scripts/lib/skill_template.py \
        "$TW/SKILL.md" "aitasks/metadata/profiles/$profile.yaml" claude 2>/dev/null)"
    check "$profile: Step 10 heading" "1" \
        "$(printf '%s\n' "$rendered" | grep -c '^### Step 10: Workflow End$')"
    check "$profile: Step 10 NON-SKIPPABLE marker" "1" \
        "$(printf '%s\n' "$rendered" | grep -cF 'NON-SKIPPABLE — Auto mode and execution profiles do NOT bypass this step.')"
    check "$profile: Step 9b hands off to Step 10" "1" \
        "$(printf '%s\n' "$rendered" | grep -cF 'Then proceed to **Step 10**.')"
done

echo
echo "=== Guard 4: negative controls ==="
# (a) Drop ONE branch's reference in a file whose other branches stay covered.
cp "$TW/merge-target-sync.md" "$TMP/merge-target-sync.md"
python3 - "$TMP/merge-target-sync.md" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding="utf-8").read()
old = "Then show the **Stopped** banner (see `workflow-end.md`) with\n     `outcome=in-flight`"
assert s.count(old) == 1, "mutation anchor missing"
open(p, "w", encoding="utf-8").write(s.replace(old, "Then end the workflow with\n     `in-flight`"))
PY
base="$(python3 "$TMP/scan.py" "$TMP/allow.txt" "$TW/merge-target-sync.md")"
check "control (a) baseline: the unmutated file is fully covered" "0" \
    "$(echo "$base" | grep -c '^UNCOVERED:')"
check "control (a) baseline: the file has other covered branches" "1" \
    "$([[ "$(echo "$base" | sed -n 's/^COVERED://p')" -ge 2 ]] && echo 1 || echo 0)"
neg="$(python3 "$TMP/scan.py" "$TMP/allow.txt" "$TMP/merge-target-sync.md")"
# Every exit line of the mutated block is reported; none from elsewhere.
check "control (a): the stripped branch is reported" "1" \
    "$([[ "$(echo "$neg" | grep -c '^UNCOVERED:')" -ge 1 ]] && echo 1 || echo 0)"
# The "Stop here" branch block runs from its bullet to its closing sentence.
blk_a="$(grep -n '^   - \*\*"Stop here":\*\*' "$TMP/merge-target-sync.md" | head -n1 | cut -d: -f1)"
blk_b="$(grep -n 'and end the workflow\.$' "$TMP/merge-target-sync.md" | head -n1 | cut -d: -f1)"
check "control (a): mutated block located" "1" \
    "$([[ -n "$blk_a" && -n "$blk_b" && "$blk_a" -lt "$blk_b" ]] && echo 1 || echo 0)"
outside=0
while IFS=: read -r _ _ ln _; do
    [[ -z "$ln" ]] && continue
    if [[ "$ln" -lt "${blk_a:-0}" || "$ln" -gt "${blk_b:-0}" ]]; then outside=$((outside + 1)); fi
done < <(echo "$neg" | grep '^UNCOVERED:')
check "control (a): only the mutated block is reported" "0" "$outside"
# (b) A stale allowlist entry is reported.
{ cat "$TMP/allow.txt"; echo "SKILL.md|a phrase that no file contains"; } > "$TMP/allow_stale.txt"
neg_b="$(python3 "$TMP/scan.py" "$TMP/allow_stale.txt" "${scan_files[@]}")"
check "control (b): stale allowlist entry is reported" "1" \
    "$(echo "$neg_b" | grep -c '^STALE_ALLOW:SKILL.md|a phrase that no file contains$')"

echo
echo "Results: $PASS passed, $FAIL failed, $TOTAL total"
[[ "$FAIL" -eq 0 ]] || exit 1
