---
Task: t2324_fix_codex_approval_guard_registration_spelling.md
Base branch: main
Output branch: main
---

# t2324 — Codex approval guard: recognise every registration spelling, fail closed when it cannot tell (+ two stale tests)

## Context

t2297 made `ait setup`'s `questions_server_registered` (`.aitask-scripts/aitask_setup.sh:859`)
parse `.codex/config.toml` when its literal-header grep misses. Codex starts the `aitask_questions`
server for every valid TOML spelling (`[mcp_servers."aitask_questions"]`, a top-level dotted
`mcp_servers.aitask_questions.command = …`). `aitask_gate.sh`'s `codex_attended_approvals` (`:238`)
still runs only the literal grep. With a hand-written registration in one of those spellings, the
server runs and asks the questions, but the approval/receipt guard stays **off**.

**Review finding (accepted, blocking).** Simply reusing setup's check would be wrong. That check
folds "could not inspect" into "not registered", and every gate caller (`append` `:477`,
`resume-point` `:909`, `merge-guard` `:948`, `approvals-settled` `:977`) reads any non-zero result
as *unguarded*. Interpreter selection makes this worse. `resolve_python` (`lib/python_resolve.sh:53`)
returns the first *executable* candidate (`AIT_PYTHON` first) without testing it, while the server
launcher (`aitask_questions_mcp.sh:39`) tests each candidate and falls back. So a broken `AIT_PYTHON`
override can sit beside a working server while detection fails, and enforcement disappears. Also,
1 is Python's own failure code: an interpreter that crashes exits 1, which looks exactly like a
"parsed: absent" verdict carried in the exit code. The fix has three parts. The helper returns a
**three-way** answer (registered / confirmed absent / inspection failed). It takes a verdict only
from a printed token, never from an exit status, and falls back across candidates. The gate
enforces on an inspection failure. Setup keeps its own policy.

The other two defects recorded on the task, re-checked at HEAD:
- **`/aitask-note` "exactly once"** (`tests/test_note_with_live_composition.sh` test 7). The second
  mention in task-workflow (default/fast) is the relation-derived Step 8e D.3 push offer. t1981_5
  (f87d4ef27) added it on purpose, not t1912_3. The test means to pin the *judgement* offer, so its
  expectation is out of date. Fix the test.
- **`tests/test_install_engine_binary.sh`.** E7 copies `goengines/ci/preflight.sh`, which the
  export (6405506d1) removed. That is a real fixture defect. S2/E4 fail for a different reason:
  `compile: version "go1.27.4" does not match go tool version "go1.27.4-X:nodwarf5"`, because `PATH`
  finds `/usr/bin/go` while `GOROOT` points at mise. That is a local toolchain mismatch, out of
  scope, and I'll report it.

## Implementation

### 1. New helper — `.aitask-scripts/lib/codex_questions_registration.sh`

`codex_questions_registration <config> [<python-candidate>...]` — return **0** registered, **1**
confirmed absent, **2** inspection failed. On 2 it sets `CODEX_QUESTIONS_REG_REASON`. The function
runs in the caller's shell, so the variable is visible to the caller.

Decision order:
1. `[[ -e "$config" ]]` false → **1** (no project config: Codex starts nothing from it). The path
   exists but is not a readable regular file → **2** (`unreadable`).
2. The literal-header grep `^\[mcp_servers\.aitask_questions\]` → **0**. If grep itself errors
   (exit ≥ 2) → **2** (`unreadable`).
3. **Sound no-parser prefilter.** If the file contains neither the substring `aitask_questions` nor
   any `\u` / `\U` escape → **1**. Why this is sound: a TOML key is a single atom (a bare, basic-
   or literal-quoted segment of a dotted key). A basic-string key can spell letters only literally
   or through `\u`/`\U` escapes, and a literal-string key only literally. So a key equal to
   `aitask_questions` must leave one of those two byte patterns in the file. Because of this step, a
   project that does not register the server never needs Python, so a broken interpreter cannot
   wrongly turn the guard on there.
4. Parse. For each candidate (skip empty and non-`command -v` ones), run the embedded Python. It
   prints exactly one token on stdout: `REG:yes`, `REG:no`, `REG:invalid` (not valid TOML), or
   `REG:noparser` (neither tomllib nor tomli). Only the token counts. The exit status is ignored, so
   a crashing interpreter (exit 1, 126, 127, a traceback) can never produce a verdict.
   `yes` → **0**. `no` / `invalid` → **1**: Codex refuses a config it cannot parse, so nothing is
   registered. `noparser` / no token → try the next candidate.
5. No candidate produced a verdict → **2** (`no_working_toml_parser: tried <list>`).

The file has a double-source guard and no startup sources of its own.

### 2. `aitask_setup.sh` — `questions_server_registered` is a thin wrapper, setup policy kept

```bash
questions_server_registered() {
    local config="${1:-$SCRIPT_DIR/../.codex/config.toml}"
    declare -F codex_questions_registration >/dev/null ||
        source "$SETUP_LIB_DIR/codex_questions_registration.sh"
    codex_questions_registration "$config" "$VENV_DIR/bin/python" python3
    # setup policy: only a positive detection counts; 1 and 2 both read "not registered"
}
```

The function returns 0 only on 0, which is today's behaviour, now with candidate fallback as a bonus.
The source is lazy, indented, and goes through `SETUP_LIB_DIR`: Group 3 of
`test_setup_questions_server.sh` re-points `SCRIPT_DIR` at a lib-less fixture, and this is the same
pattern `atomic_write.sh` uses. `_codex_toml_python` stays for its other callers. Trim the comment
and point it at the lib.

### 3. `aitask_gate.sh` — `codex_attended_approvals` fails closed

```bash
codex_attended_approvals() {
    [[ -n "${CODEX_THREAD_ID:-}" ]] || return 1
    local project config rc=0
    project="$(_questions_project_dir)" || return 1
    config="$project/.codex/config.toml"
    [[ -e "$config" ]] || return 1
    declare -F codex_questions_registration >/dev/null ||
        source "$SCRIPT_DIR/lib/codex_questions_registration.sh"
    codex_questions_registration "$config" "${AIT_PYTHON:-}" \
        "$HOME/.aitask/venv/bin/python" "$HOME/.aitask/bin/python3" python3 || rc=$?
    case "$rc" in
        0) return 0 ;;
        1) return 1 ;;
        *) warn "approval guard: could not tell whether $config registers the aitask_questions server (${CODEX_QUESTIONS_REG_REASON:-unknown}) — enforcing receipts; fix the interpreter (AIT_PYTHON / ait setup) to clear this"
           return 0 ;;
    esac
}
```

An inspection failure maps to **guarded**, so every caller refuses without valid evidence. A receipt
claim then also needs a working interpreter (`delegate_python_approval`), so with a broken
interpreter only `approval=profile:<name>` (a pure-bash check) passes. That is the fail-closed
direction. `resume-point` demotes to PLAN, `merge-guard` takes its guarded path, and
`approvals-settled` checks evidence. No caller needs to change, because the one shared predicate now
only says "unguarded" on positive evidence of absence. The candidate list mirrors `resolve_python`'s
plus `python3`, and each candidate is *tested*, as the launcher tests its own. The source is lazy and
runs after the Codex check and the config-exists check, so there is no new startup lib and no change
to `test_scaffold.sh`. Update the comment above the function and the guard summary at `:224`.

### 4. Tests

**`tests/test_gate_codex_approvals.sh`**, in a new section "1b. registration spellings and
inspection failure", ending with `register` so later sections are unchanged. FAIL stubs: an
executable `exit 1` script, and a "python" that prints a traceback and exits 1.
- quoted `[mcp_servers."aitask_questions"]` → `codex append … plan_approved pass type=human`:
  exit 3, nothing written.
- dotted top-level `mcp_servers.aitask_questions.command = "x"` → same refusal.
- **quoted + `AIT_PYTHON=<failing stub>`** (other candidates still work) → still refused. This
  checks that fallback across candidates works.
- **quoted + every candidate failing** (`AIT_PYTHON` = stub, scratch `HOME` without a venv, `PATH`
  prefixed with a failing `python3` stub) → refused (exit 3, nothing written), and stderr carries the
  "could not tell … enforcing receipts" warning. `approvals-settled` does not print
  `APPROVALS:unguarded` and `merge-guard` does not print `MERGE:unguarded`. This checks that
  enforcement cannot silently disappear.
- negative controls, all of which must stay unguarded (append succeeds): a commented-out quoted
  table, an invalid TOML file, and **a config without the name + every candidate failing** (the
  prefilter confirms absence without a parser).
- Pre-fix control: run the quoted, dotted and all-candidates-failing cases against the unmodified
  gate first, and confirm they fail there.

**Helper unit cases**, a new `tests/test_codex_questions_registration.sh`, sourcing the lib
directly: one row per decision step. Cover missing file → 1; unreadable file → 2; literal → 0;
`\u`-escaped quoted key (the table header `mcp_servers."aitask_question<ESC>"` where `<ESC>` is backslash, `u`, `0073` — the escape for `s` — so the literal substring `aitask_questions` is absent) with a working parser → 0;
no-name-no-escape with no candidates → 1; name present with no candidates → 2, reason set;
`REG:noparser` stub then working python → 0; and a stub that exits 0 printing nothing → it is
skipped, not taken as a verdict. Use the file-backed counters if any body runs in a subshell
(CLAUDE.md t1207).

The existing groups 3 and 13 of `test_setup_questions_server.sh` already pin the setup wrapper
(literal, quoted, dotted, commented, broken), so they act as the refactor's regression suite.

**`tests/test_note_with_live_composition.sh` test 7**: count the judgement offer's own phrase,
`to send it there with \`/aitask-note\``, which renders exactly once in all 9 site×profile cells
(verified). Update the comment to say that the profile-dependent Step 8e relation push offer is
deliberately left out. Leave 7z unchanged.

**`tests/test_install_engine_binary.sh` E7**: replace the `cp` of the removed
`goengines/ci/preflight.sh` with an inline executable fixture that runs the same tripwire
(`go test -count=1 -run '^TestIsolationTripwire(Catches|Imports)?$' ./internal/testsupport/hangguard/`).
`want` stays the same. E7 pins `ait engine test`'s ordering contract (vet → preflight alone → suite,
and a failing preflight stops the suite). The preflight's content now lives in aitasks_go, and the
comment will say so.

### 5. Docs — `aidocs/codeagents/codex_questions.md`, "Gate enforcement → Scope" (~line 306)

Say that the registration is "the `aitask_questions` server in `.codex/config.toml`, in any valid
TOML spelling (`lib/codex_questions_registration.sh`)". Add the fail-closed rule: when the config
names the server but cannot be inspected (no working TOML-capable interpreter, unreadable file), the
guard **is enforced** and warns, so a broken interpreter can block approvals but never drop them.
Setup's own check stays positive-only. No website page mentions this.

## Verification

- `bash tests/test_codex_questions_registration.sh` and `bash tests/test_gate_codex_approvals.sh`:
  all pass. The pre-fix control shows the new gate cases failing on the old code.
- `bash tests/test_setup_questions_server.sh`: same results as before.
- `bash tests/test_note_with_live_composition.sh`: test 7 passes.
- `bash tests/test_install_engine_binary.sh`: E7 passes. S2/E4 are expected to keep failing on this
  machine (Go toolchain mismatch, reported).
- Spot-check that tests that drive gate/archive/merge under scaffolds still pass:
  `tests/test_gate_*.sh` and the archive/merge approval tests that set `CODEX_THREAD_ID`.
- `shellcheck` on the new lib, `aitask_gate.sh`, `aitask_setup.sh` and the new test.
- `tests/test_shell_startup_closure.py`: the format contract still holds (only lazy, indented
  sources were added).

## Step 9

Post-implementation: commit on the current branch (main), then archive t2324 and its plan through
the standard Step 9 flow.

## Risk

### Code-health risk: low
- The guard now turns on in more cases: quoted/dotted registrations, and an inspection failure when
  the config names the server. A machine with a broken interpreter, in a project that registers the
  server, now gets approval refusals with a warning that names the fix, where before approvals went
  through unguarded. That is intended fail-closed behaviour, and projects that don't register the
  server are unaffected because the prefilter needs no parser. · severity: low · → mitigation: none
  needed (section-4 tests pin both directions)
- Lazy-source placement could break a fixture that re-points `SCRIPT_DIR` or carries a partial
  `lib/`. Handled by design: setup uses `SETUP_LIB_DIR`, and gate sources only after the Codex check
  and the config-exists check. · severity: low · → mitigation: built into steps 2–3

### Goal-achievement risk: low
- The prefilter's soundness argument (a key named `aitask_questions` must leave the literal bytes or a
  `\u`/`\U` escape in the file) is checked by the escaped-key helper case. If it were wrong, the
  failure would be the old one (guard off), not a new one. · severity: low · → mitigation: helper
  test row in section 4
