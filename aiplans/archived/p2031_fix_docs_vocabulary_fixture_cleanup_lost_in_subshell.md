---
Task: t2031_fix_docs_vocabulary_fixture_cleanup_lost_in_subshell.md
Base branch: main
Output branch: main
---

# t2031 — Docs-vocabulary fixture cleanup is lost in a subshell

## Context

`tests/test_docs_vocabulary_coverage.sh` `make_fixture` runs
`CLEANUP_DIRS+=("$dir")` and then echoes the dir. Every caller captures that echo
with `$(make_fixture)` (Test 2 at line 120, `assert_control` at line 137,
`assert_positive_control` at line 156). The array append therefore happens only
inside the command-substitution subshell, so the `trap cleanup EXIT` never sees
the fixtures.

**Red, measured before any change:** with
`TMPDIR=<scratch>/probe_red bash tests/test_docs_vocabulary_coverage.sh`
the result is `30/30 passed`, rc=0, and **12** `tmp.*` dirs are left behind (one
per `make_fixture` call: Test 2, 10 `assert_control`, and 1
`assert_positive_control`).

## Implementation (single file: `tests/test_docs_vocabulary_coverage.sh`)

1. **`make_fixture` returns through a result variable, not stdout.** Rename the
   local `dir` to write the global `_FIXTURE_DIR`. Update the header comment to
   say it sets `_FIXTURE_DIR` and registers it for cleanup. Also say why it must
   not be called inside `$( )`: the cleanup registration would die with the
   subshell (t2031).
   ```bash
   make_fixture() {
       local rel
       _FIXTURE_DIR="$(mktemp -d)"
       CLEANUP_DIRS+=("$_FIXTURE_DIR")
       while IFS= read -r rel; do
           ... "$_FIXTURE_DIR/..." ...
       done < <(python3 "$SCAN" --root "$PROJECT_DIR" --list-inputs)
       mkdir -p "$_FIXTURE_DIR/aitasks"
       cat > "$_FIXTURE_DIR/aitasks/t1_sample.md" <<'EOF' ... EOF
   }
   ```
   Drop the trailing `printf '%s\n' "$dir"`. Under `set -e`, a `mktemp`
   failure still aborts, just as the old failed `$( )` assignment did.

2. **Update the three callers:**
   - Test 2: `make_fixture; FIXTURE="$_FIXTURE_DIR"`
   - `assert_control` and `assert_positive_control`: `make_fixture; dir="$_FIXTURE_DIR"`

3. **Regression assertion in Test 2**, right after the call: assert that the
   fixture is registered in the parent shell's cleanup list:
   ```bash
   assert_contains "fixture is registered for EXIT cleanup in the parent shell" \
       " $FIXTURE " " ${CLEANUP_DIRS[*]} "
   ```
   (The space padding stops a prefix from matching.) The old code fails this
   assertion, because `CLEANUP_DIRS` is empty in the parent. That gives the
   red proof inside the suite itself, not only through the TMPDIR probe.

No other files change. The file's test bodies do not run in `( … )` subshells, so
the t1207 counters opt-in does not apply.

## Out-of-scope finding (surface at Step 8, do not fix here)

A heuristic grep finds the same `$( )` state-loss shape in many sibling suites.
The clearest is `new_fixture` in `tests/test_gate_*.sh`: it does
`CLEANUP_DIRS+=` and is called as `d="$(new_fixture)"`. Examples are
`test_gate_pass.sh`, `test_gate_orchestrator.sh`, `test_web_merge_materialize.sh`
and `test_run_project_command.sh`. No task owns this, so offer a follow-up task
for an audited sweep. That task re-checks each grep hit by reading the code;
the grep is only a heuristic.

## Verification

- `bash tests/test_docs_vocabulary_coverage.sh` → all pass (31/31, which includes
  the new assertion), rc=0.
- Probe: `TMPDIR=<scratch>/probe_green bash tests/test_docs_vocabulary_coverage.sh`,
  then confirm `find <probe> -mindepth 1 -maxdepth 1 | wc -l` is `0`, against
  12 before the fix.
- Red proof for the new assertion: temporarily wrap the call in a subshell in a
  **scratch copy** of the test (never by git-restoring or stashing the live
  file), e.g. `( make_fixture ); FIXTURE=...`. Confirm that the new assertion
  fails and that the suite exits nonzero.
- `shellcheck tests/test_docs_vocabulary_coverage.sh` → no new warnings.

## Step 9

Post-implementation: commit the code as `bug: … (t2031)`. Then archive through
the standard Step 9 flow, on the current branch (profile `fast`).

## Risk

### Code-health risk: low
None identified. The change is one test file and three call sites. The fixture
contents and the scanner it drives are unchanged.

### Goal-achievement risk: low
None identified. The TMPDIR probe measures the leak directly (12 before, 0
expected after), and the new in-suite assertion guards against a regression.

## Final Implementation Notes
- **Actual work done:** In `tests/test_docs_vocabulary_coverage.sh`, `make_fixture` now sets the global `_FIXTURE_DIR` and registers it in `CLEANUP_DIRS` in the caller's shell. It no longer echoes the path. All three callers (Test 2, `assert_control`, `assert_positive_control`) call it directly and then read `_FIXTURE_DIR`. The header comment forbids `$(make_fixture)` and cites t2031. Test 2 gains two regression assertions: `assert_dir_exists` on the fixture, then `assert_contains` checking that it is in `" ${CLEANUP_DIRS[*]} "`.
- **Deviations from plan:** One extra assertion beyond the plan, `assert_dir_exists` before the membership check. The first red proof (`( make_fixture )` in a scratch copy) still passed: `FIXTURE` was empty, and the needle `"  "` is a substring of an empty padded list. The non-empty check closes that vacuous case. The suite now has 32 assertions, not the 31 the plan expected.
- **Issues encountered:** The planned red proof was not faithful to the old bug. It was replaced by two scratch-copy proofs, kept out of the live file and never via stash or restore:
  - Red A, the exact pre-fix shape `FIXTURE="$( make_fixture; printf "%s" "$_FIXTURE_DIR" )"`: rc=1, `FAIL: fixture is registered for EXIT cleanup in the parent shell (… got '  ')`, 31/32.
  - Red B, `( make_fixture )` with an empty FIXTURE: rc=1, `FAIL: make_fixture set _FIXTURE_DIR in the parent shell (dir not found: )`.
- **Verification (durable evidence):**
  - Before the fix: `TMPDIR=<probe> bash tests/test_docs_vocabulary_coverage.sh` gave 30/30, rc=0, and **12** leftover `tmp.*` dirs.
  - After the fix: 32/32, rc=0, **0** leftovers.
  - `shellcheck`: identical findings before and after (2× SC1091, 5× SC2016, all info-level and pre-existing).
- **Key decisions:** Used a result variable rather than re-registering after each call, so the registration lives in one place and a future caller cannot forget it.
- **Upstream defects identified:**
  - `tests/test_gate_verifiers.sh` — `new_fixture` does `CLEANUP_DIRS+=` but is called as `$(new_fixture)` (41 sites), so its fixtures leak, the same `$( )` state-loss class as t2031.
  - Same shape in 19 more suites. The list is heuristic: helper bodies containing `CLEANUP_DIRS+=` that are called inside `$( )`. Each needs reading to confirm:
    - `new_fixture`: test_gate_active_gates, test_gate_cli_wiring, test_gate_declaration_backfill, test_gate_effective_gates, test_gate_no_double_record, test_gate_orchestrator, test_gate_pass, test_gate_procedure_docs, test_gate_risk_verifier, test_gates_sync_registry, test_gate_stale_witness_parity, test_run_project_command, test_web_merge_materialize
    - `fresh_tmpdir` / `make_repo`: test_atomic_task_file_writes
    - `bcrt`: test_followup_kind_roundtrip
    - `setup_repo`: test_issue_import_amend_guard
    - `new_dir`: test_skill_errexit_capture
    - `new_repo`: test_verification_stale
