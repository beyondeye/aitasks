#!/usr/bin/env bash
# test_skill_errexit_capture.sh - Exit-status captures in the skill surface must
# survive `set -euo pipefail` (t1621).
#
# The defect class: `x="$(cmd)"; rc=$?` (and its newline-separated twin) are two
# separate simple commands. The assignment inherits the substitution's status,
# so errexit fires there and the shell dies BEFORE `rc=$?` runs -- the branch
# written to diagnose that status is unreachable. Same for a bare `case $?`
# after a simple command whose non-zero exit is an ordinary outcome.
#
# t1610 fixed this class in aitask_run_project_command.sh and documented the
# working form in .claude/skills/task-workflow/build-verification.md. This file
# covers the remaining skill-surface sites:
#
#   1.  The rendered `ait gates run` dispatch block runs to completion under a
#       strict shell, with the real status AND the real output in hand.
#   1b. That block is still WIRED to the surrounding diagnostic branch -- a
#       snippet can survive errexit and still hand the user a bare failure if a
#       rename or a dropped branch left the prose talking about other names.
#   2.  Negative controls: both rejected spellings really do die. Without them
#       the if-form proves nothing.
#   3.  The aitask-trail incoming-`verifies` sweep classifies grep's status
#       instead of dying on the expected no-match.
#   4.  A structural drift guard over the whole authoring surface, so the next
#       editor cannot reintroduce the shape in either spelling.
#
# Run: bash tests/test_skill_errexit_capture.sh

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
. "$PROJECT_DIR/tests/lib/asserts.sh"

PASS=0
FAIL=0
TOTAL=0
CLEANUP_DIRS=()

cd "$PROJECT_DIR" || exit 1

# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PYTHON="$(require_ait_python)"
if ! "$PYTHON" -c 'import minijinja' 2>/dev/null; then
    echo "SKIP: minijinja not installed in framework venv ($PYTHON). Run 'ait setup' first."
    exit 0
fi

RENDER=(.aitask-scripts/lib/skill_template.py)
PROFILES_DIR="aitasks/metadata/profiles"

# The scanner rule, shared by Test 4 and its own controls. Reads bash fenced
# blocks only -- prose that QUOTES the bad shape in backticks (build-verification
# .md says "Do not write `bv_out=...`; bv_rc=$?`") must not be a hit.
#
# shellcheck disable=SC2016  # awk program text: $0/$? are awk/target-shell, not ours
SCANNER='
/^[[:space:]]*```bash[[:space:]]*$/ { inb=1; prev=""; next }
inb && /^[[:space:]]*```[[:space:]]*$/ { inb=0; next }
!inb { next }
{
  line=$0
  t=line; sub(/^[[:space:]]+/,"",t); sub(/[[:space:]]+$/,"",t)
  if (t=="" || t ~ /^#/) next
  if (index(line,"$?")>0) {
    safe=0
    o=index(line,"||"); q=index(line,"$?")
    # (a) right operand of `||` -- errexit is suspended for the left side.
    if (o>0 && o<q) safe=1
    # (b) the documented if/else form: a lone `x=$?` directly under `else`.
    else if (t ~ /^[A-Za-z_][A-Za-z0-9_]*=\$\?$/ && prev=="else") safe=1
    if (!safe) printf "%s:%d: %s\n", FILENAME, FNR, t
  }
  prev=t
}
'

# --- helpers ---------------------------------------------------------------

new_dir() {
    local tmp
    tmp="$(mktemp -d "${TMPDIR:-/tmp}/test_errexit_capture_XXXXXX")"
    CLEANUP_DIRS+=("$tmp")
    printf '%s' "$tmp"
}

# Extract the fenced ```bash block whose body contains `ait gates run`, dedented
# by the fence's own indentation (task-workflow indents it 2 spaces, pickrem 0).
extract_gates_block() {  # <file>
    awk '
      /^[[:space:]]*```bash[[:space:]]*$/ { inb=1; buf=""; ind=match($0,/[^ ]/)-1; next }
      inb && /^[[:space:]]*```[[:space:]]*$/ {
          if (buf ~ /ait gates run/) { printf "%s", buf; exit }
          inb=0; next
      }
      inb {
          line=$0
          if (ind>0 && substr(line,1,ind)==sprintf("%*s",ind,"")) line=substr(line,ind+1)
          buf=buf line "\n"
      }
    ' "$1"
}

# Everything after the gates block -- the branch prose Test 1b inspects.
text_after_gates_block() {  # <file>
    awk '
      done_ { print; next }
      /^[[:space:]]*```bash[[:space:]]*$/ { inb=1; buf=""; next }
      inb && /^[[:space:]]*```[[:space:]]*$/ {
          inb=0
          if (buf ~ /ait gates run/) done_=1
          next
      }
      inb { buf=buf $0 "\n" }
    ' "$1"
}

# Build a fixture holding a stub `./ait` and run <block> under a strict shell.
# Echoes the driver's stdout; the driver's own exit status is discarded on
# purpose -- the assertions read REACHED_END, which is the observable that
# distinguishes "ran to the end" from "errexit killed it".
run_block_with_stub() {  # <block> <stub_exit> <stub_stderr_msg>
    local block="$1" stub_exit="$2" msg="$3" d
    d="$(new_dir)"
    cat > "$d/ait" <<STUB
#!/usr/bin/env bash
echo "stub stdout: gates run \$*"
echo "$msg" >&2
exit $stub_exit
STUB
    chmod +x "$d/ait"
    {
        echo '#!/usr/bin/env bash'
        echo 'set -euo pipefail'
        # <task_id> unsubstituted is a shell REDIRECTION, not an argument.
        printf '%s\n' "${block//<task_id>/42}"
        # shellcheck disable=SC2016  # driver source text: expands in the driver, not here
        echo 'echo "RC=$gates_rc"'
        # shellcheck disable=SC2016  # driver source text: expands in the driver, not here
        echo 'echo "OUT<<$gates_out>>"'
        echo 'echo REACHED_END'
    } > "$d/driver.sh"
    chmod +x "$d/driver.sh"
    ( cd "$d" && ./driver.sh 2>/dev/null ) || true
}

# ============================================================
# Test 1: the rendered dispatch block survives a strict shell
# ============================================================
test_rendered_block_survives() {
    echo "=== Test 1: rendered gate-dispatch block under set -euo pipefail ==="
    local label src profile rendered block out

    _one() {  # <label> <source> <profile>
        label="$1"; src="$2"; profile="$3"
        rendered="$(new_dir)/rendered.md"
        "$PYTHON" "${RENDER[@]}" "$src" "$PROFILES_DIR/$profile.yaml" claude > "$rendered"
        block="$(extract_gates_block "$rendered")"

        # Extractor positive control -- without it every assertion below can
        # pass vacuously on an extraction miss (an empty driver reaches its end).
        assert_contains "$label: extractor found the dispatch block" \
            "ait gates run" "$block"

        # (a) failure path: the status AND the diagnostic payload survive.
        out="$(run_block_with_stub "$block" 2 'ait: fatal: gate registry unreadable')"
        assert_contains "$label: block survives a nonzero dispatch" "REACHED_END" "$out"
        assert_contains "$label: captured status is the dispatch's real status" "RC=2" "$out"
        assert_contains "$label: gates_out carries the diagnosis (2>&1 is load-bearing)" \
            "ait: fatal: gate registry unreadable" "$out"

        # (b) success path: `set -u` would abort on $gates_rc if the zero branch
        # forgot to bind it.
        out="$(run_block_with_stub "$block" 0 'noise')"
        assert_contains "$label: block survives a clean dispatch" "REACHED_END" "$out"
        assert_contains "$label: clean dispatch binds gates_rc=0" "RC=0" "$out"
    }

    for profile in default fast remote; do
        _one "task-workflow/$profile" ".claude/skills/task-workflow/SKILL.md" "$profile"
    done
    _one "aitask-pickrem/remote" ".claude/skills/aitask-pickrem/SKILL.md.j2" remote
}

# ============================================================
# Test 1b: the block is still wired to its diagnostic branch
# ============================================================
# Running the snippet cannot see a rename or a deleted branch in the prose
# around it: a perfectly errexit-safe capture whose branch names other variables
# hands the user a bare failure again.
test_branch_wiring() {
    echo "=== Test 1b: the dispatch block is wired to the surrounding branch ==="
    local label src profile rendered block after ids id nonzero_bullet

    _wiring() {  # <label> <source> <profile>
        label="$1"; src="$2"; profile="$3"
        rendered="$(new_dir)/rendered.md"
        "$PYTHON" "${RENDER[@]}" "$src" "$PROFILES_DIR/$profile.yaml" claude > "$rendered"
        block="$(extract_gates_block "$rendered")"
        after="$(text_after_gates_block "$rendered")"

        # Identifiers the block BINDS -- both `if var=...` and bare `var=...`.
        ids="$(printf '%s\n' "$block" |
            sed -n 's/^[[:space:]]*\(if[[:space:]]\+\)\?\([A-Za-z_][A-Za-z0-9_]*\)=.*/\2/p' |
            sort -u)"
        assert_contains "$label: block binds an output variable" "gates_out" "$ids"
        assert_contains "$label: block binds a status variable" "gates_rc" "$ids"

        # Every bound identifier must be consumed after the block. A rename that
        # never propagated leaves an orphan binding and a dangling branch.
        for id in $ids; do
            assert_contains "$label: $id is consumed after the block" "$id" "$after"
        done

        # The nonzero-status branch itself must still exist.
        nonzero_bullet="$(printf '%s\n' "$after" |
            grep -n 'gates_rc' | grep -i 'nonzero' | head -n1)"
        assert_contains "$label: a nonzero-gates_rc branch still exists" \
            "gates_rc" "$nonzero_bullet"
    }

    for profile in default fast remote; do
        _wiring "task-workflow/$profile" ".claude/skills/task-workflow/SKILL.md" "$profile"
    done
    _wiring "aitask-pickrem/remote" ".claude/skills/aitask-pickrem/SKILL.md.j2" remote

    # File-specific diagnosis pins. The two paths have deliberately DIFFERENT
    # contracts, so one shared assertion would be wrong for one of them.
    #
    #   task-workflow (attended) : "STOP and diagnose using `gates_out`"
    #   aitask-pickrem (headless): "Trigger the Abort Procedure"
    local tw_after pr_after tw_branch pr_branch
    rendered="$(new_dir)/tw.md"
    "$PYTHON" "${RENDER[@]}" ".claude/skills/task-workflow/SKILL.md" \
        "$PROFILES_DIR/default.yaml" claude > "$rendered"
    tw_after="$(text_after_gates_block "$rendered")"
    # The bullet plus its wrapped continuation lines, up to the next bullet.
    tw_branch="$(printf '%s\n' "$tw_after" | awk '/gates_rc` is nonzero/{f=1} f{print} f&&/^  - \*\*Else/{exit}')"
    assert_contains "task-workflow: nonzero branch diagnoses with gates_out" \
        "gates_out" "$tw_branch"
    assert_contains "task-workflow: nonzero branch says diagnose" \
        "diagnose" "$tw_branch"

    rendered="$(new_dir)/pr.md"
    "$PYTHON" "${RENDER[@]}" ".claude/skills/aitask-pickrem/SKILL.md.j2" \
        "$PROFILES_DIR/remote.yaml" claude > "$rendered"
    pr_after="$(text_after_gates_block "$rendered")"
    pr_branch="$(printf '%s\n' "$pr_after" | awk '/`gates_rc` nonzero/{f=1} f{print} f&&/^- \*\*`gates_out`/{exit}')"
    assert_contains "aitask-pickrem: nonzero branch routes to the Abort Procedure" \
        "Abort Procedure" "$pr_branch"
    assert_contains "aitask-pickrem: gates_out is consumed by the next branch" \
        'gates_out' "$pr_after"
}

# ============================================================
# Test 2: negative controls -- both rejected spellings do die
# ============================================================
test_negative_controls() {
    echo "=== Test 2: negative controls (the rejected shapes really break) ==="
    local out

    # The three blocks below are verbatim SHELL SOURCE handed to the driver --
    # single quotes are what keeps them unexpanded here, which is the point.
    # shellcheck disable=SC2016
    out="$(run_block_with_stub 'gates_out="$(./ait gates run <task_id> 2>&1)"; gates_rc=$?' \
            2 'boom')"
    assert_not_contains "negative control: the one-line shape dies on a nonzero dispatch" \
        "REACHED_END" "$out"

    # The newline-separated twin. A drift guard that only rejects the one-line
    # spelling would report clean on this while the defect is identical.
    # shellcheck disable=SC2016
    out="$(run_block_with_stub 'gates_out="$(./ait gates run <task_id> 2>&1)"
gates_rc=$?' 2 'boom')"
    assert_not_contains "negative control: the newline-separated shape dies too" \
        "REACHED_END" "$out"

    # Positive control for the controls: the documented form survives the very
    # same fixture, so the two rows above measure the SHAPE, not the fixture.
    # shellcheck disable=SC2016
    out="$(run_block_with_stub 'if gates_out="$(./ait gates run <task_id> 2>&1)"; then
  gates_rc=0
else
  gates_rc=$?
fi' 2 'boom')"
    assert_contains "negative control: the documented form survives the same fixture" \
        "REACHED_END" "$out"
}

# ============================================================
# Test 3: the aitask-trail incoming-`verifies` sweep loop
# ============================================================
test_trail_sweep_loop() {
    echo "=== Test 3: aitask-trail sweep classifies grep's status ==="
    local d out rc

    _sweep_fixture() {
        d="$(new_dir)"
        echo "nothing here" > "$d/nomatch.md"
        echo "verifies: [1039]" > "$d/match.md"
    }

    # The FIXED shape: no-match is classified, the read failure propagates, and
    # the loop reaches its end.
    _sweep_fixture
    cat > "$d/sweep.sh" <<'SWEEP'
#!/usr/bin/env bash
set -euo pipefail
printf 'nomatch.md\nmatch.md\nvanished.md\n' | { rc=0
  while IFS= read -r f; do
    grep_rc=0
    grep -q -- '1039' "$f" || grep_rc=$?
    case "$grep_rc" in
      0) printf '%s\n' "$f" ;;
      1) ;;
      *) printf 'sweep: cannot read %s\n' "$f" >&2; rc=2 ;;
    esac
  done
  echo "LOOP_END"
  exit "$rc"; }
SWEEP
    chmod +x "$d/sweep.sh"
    out="$( cd "$d" && ./sweep.sh 2>"$d/err.txt" )" && rc=0 || rc=$?
    assert_contains "trail sweep: the loop reaches its end" "LOOP_END" "$out"
    assert_contains "trail sweep: the matching candidate is emitted" "match.md" "$out"
    assert_not_contains "trail sweep: a non-matching file is not a candidate" \
        "nomatch.md" "$out"
    assert_contains "trail sweep: an unreadable file is reported on stderr" \
        "cannot read vanished.md" "$(cat "$d/err.txt")"
    assert_eq "trail sweep: a read failure propagates as exit 2" "2" "$rc"

    # Negative control: the shape this task replaces dies before LOOP_END on the
    # FIRST expected no-match, so the `1)` arm above is unreachable.
    _sweep_fixture
    cat > "$d/bad_sweep.sh" <<'SWEEP'
#!/usr/bin/env bash
set -euo pipefail
printf 'nomatch.md\nmatch.md\n' | { rc=0
  while IFS= read -r f; do
    grep -q -- '1039' "$f"
    case $? in
      0) printf '%s\n' "$f" ;;
      1) ;;
      *) printf 'sweep: cannot read %s\n' "$f" >&2; rc=2 ;;
    esac
  done
  echo "LOOP_END"
  exit "$rc"; }
SWEEP
    chmod +x "$d/bad_sweep.sh"
    out="$( cd "$d" && ./bad_sweep.sh 2>/dev/null )" || true
    assert_not_contains "trail sweep(negative control): the bare \$? shape dies on a no-match" \
        "LOOP_END" "$out"
}

# ============================================================
# Test 4: surface-wide structural drift guard
# ============================================================
# A regex for the one-line spelling is not enough (Test 2 row 2 proves the
# newline form is the same defect), so the guard classifies every `$?` READ by
# position instead of matching one spelling.
test_surface_drift_guard() {
    echo "=== Test 4: surface-wide drift guard over authoring skill files ==="
    local d hits sources root sub

    # -- controls first: an unproven guard is decoration ---------------------
    d="$(new_dir)"
    cat > "$d/bad_oneline.md" <<'CTL'
```bash
out="$(cmd)"; rc=$?
```
CTL
    cat > "$d/bad_multiline.md" <<'CTL'
```bash
out="$(cmd)"
rc=$?
```
CTL
    cat > "$d/bad_case.md" <<'CTL'
```bash
grep -q x "$f"
case $? in
  0) : ;;
esac
```
CTL
    cat > "$d/safe_or.md" <<'CTL'
```bash
rc=0
out="$(cmd)" || rc=$?
{ grep -rl x . || [ "$?" = 1 ]; } | cat
```
CTL
    cat > "$d/safe_ifelse.md" <<'CTL'
```bash
if out="$(cmd)"; then
  rc=0
else
  rc=$?
fi
```
CTL
    cat > "$d/safe_prose.md" <<'CTL'
Do not write `out="$(cmd)"; rc=$?` -- it dies under `set -e`.
CTL

    assert_contains "guard control(+): flags the one-line shape" \
        "bad_oneline.md" "$(awk "$SCANNER" "$d/bad_oneline.md")"
    assert_contains "guard control(+): flags the newline-separated shape" \
        "bad_multiline.md" "$(awk "$SCANNER" "$d/bad_multiline.md")"
    assert_contains "guard control(+): flags a bare case \$? after a simple command" \
        "bad_case.md" "$(awk "$SCANNER" "$d/bad_case.md")"
    assert_eq "guard control(-): does not flag the || forms" \
        "" "$(awk "$SCANNER" "$d/safe_or.md")"
    assert_eq "guard control(-): does not flag the if/else form" \
        "" "$(awk "$SCANNER" "$d/safe_ifelse.md")"
    assert_eq "guard control(-): does not flag prose quoting the bad shape" \
        "" "$(awk "$SCANNER" "$d/safe_prose.md")"

    # -- the surface itself --------------------------------------------------
    # Authoring sources only: rendered variants (trailing-hyphen dirs) are
    # generated, so flagging them would double-report the same defect.
    sources=()
    for root in .claude/skills .agents/skills .opencode/skills .opencode/commands; do
        [ -d "$root" ] || continue
        for sub in "$root"/*/; do
            [ -d "$sub" ] || continue
            case "$(basename "$sub")" in *-) continue ;; esac
            while IFS= read -r f; do sources+=("$f"); done < <(
                find "$sub" -type f \( -name '*.md' -o -name '*.j2' \)
            )
        done
        while IFS= read -r f; do sources+=("$f"); done < <(
            find "$root" -maxdepth 1 -type f \( -name '*.md' -o -name '*.j2' \)
        )
    done

    assert_exit_zero "guard: the authoring surface was actually enumerated" \
        test "${#sources[@]}" -gt 50

    hits="$(awk "$SCANNER" "${sources[@]}")"
    assert_eq "guard: no errexit-unsafe \$? read in any authoring skill file" "" "$hits"
}

# --- Run ---
echo "=== test_skill_errexit_capture.sh ==="
echo ""

test_rendered_block_survives
test_branch_wiring
test_negative_controls
test_trail_sweep_loop
test_surface_drift_guard

for dir in "${CLEANUP_DIRS[@]}"; do rm -rf "$dir"; done

echo ""
echo "========================="
echo "Results: $PASS/$TOTAL passed, $FAIL failed"
[[ "$FAIL" -gt 0 ]] && exit 1
echo "All tests PASSED"
