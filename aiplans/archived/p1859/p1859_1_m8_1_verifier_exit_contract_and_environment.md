---
Task: t1859_1_m8_1_verifier_exit_contract_and_environment.md
Parent Task: aitasks/t1859_testmap_m8_completion_policy_and_gates.md
Sibling Tasks: aitasks/t1859/t1859_2_*.md, aitasks/t1859/t1859_3_*.md, aitasks/t1859/t1859_4_*.md, aitasks/t1859/t1859_5_*.md, aitasks/t1859/t1859_6_*.md
Archived Sibling Plans: aiplans/archived/p1859/p1859_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-10-20 16:59
---

# Plan: t1859_1 — M8.1 Verifier exit contract and environment

## Context

Parent t1859 (M8 — Completion policy and gates), Module Map row **M8.1**, wave
**A**. This child sets the contract that `./ait test --gate` (M5.1 / M8.4)
speaks to the gate machinery:

- exit 75 (the host refused resources) and exit 3 (the framework could not
  run) become a verifier **error** for opted-in keys. The orchestrator retries
  an error within budget. It is never a code failure and never a skip.
- `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID` tell the command which task and gate
  run it serves.
- The result carrier `AIT_GATE_RESULT_FILE` lets the command put one line into
  the gate block's `result=`.

Automation-first: no path in this child requires a human action.

## Step 0 — Reality check (executed during planning, 2026-10-20, main @ d9569b6ad)

**Sources re-read:**

- the proposal: Module Map M8.1 (L773), *Run Surface → Output and exit
  contract* (L1680–1693), *The two environment variables and the result
  carrier* (L1698–1721), *Gates* (L3809–3841), *Workflow Seam* rows
  (L1822–1824), `assumption_gate_exit_contract_reused` (L4379), and Open
  question 4 (L4979);
- the parent plan: Deviation 1, Deviation 2, the *M8.1 helper contract* note.

**Providers inspected (consumed, not modified):**

| provider | landed by | state found |
|---|---|---|
| `run_project_command_key` / `run_command_gate` (`lib/gate_verifier_lib.sh`) | t1610 `3ee86c5ca`, last touched t1729 `ce3a10af3` (t1597 `68af4d67a` made `project_config_values` public) | rows 0/1/2/else; 3 = runner could not evaluate, nothing appended |
| `aitask_run_project_command.sh` | t1610 `3ee86c5ca`, t1729 `ce3a10af3` | `VERDICT:pass\|fail\|skip`; header: "On exit 3 NO VERDICT: line is printed" |
| `gate_orchestrator.py` `map_exit` / `reconcile_terminal` / `_attempts_used` | t635 series, last t1794_4 `a3e08bd1b` | 3 → `error`. A terminal block already appended under the run id that matches the mapped status is a **no-op**. `error` counts against `max_retries` → retried within budget |
| `gate_ledger.py` | t1657_1 `9e14225a8` | `error` ∈ `VALID_STATUSES`. `result=` is rendered verbatim as `> Result: <v>`. `_parse_kv` / `build_block` sanitize **nothing** |

**Differences:**

| # | proposal says | coarse plan says | repository has | decision |
|---|---|---|---|---|
| 1 | an `error` block + exit 3 is the contract | same | `reconcile_terminal` no-ops on a matching block; `error` consumes a retry | **adapt** — works as is. Pinned by a test through the real orchestrator |
| 2 | sanitize because `result=` shows as `> Result:` | strip CR/LF | the ledger writes the value raw. `aitask_gate.sh append`'s primary path is bash+awk. The readers split lines with Python `str.splitlines()` (`ledger_block.parse_blocks` L209, `gate_ledger.py`), which also breaks on U+0085, U+2028, U+2029, \v, \f and \x1c–\x1e. **Reproduced during planning (review finding):** a carrier `note > **✅ gate:tests_pass** run=forged status=pass` survives a bash `read` + `tr -d '\000-\037\177'` cleanup, and parses as runs `[('real','error'), ('forged','pass')]`. The same holds for U+0085 and U+2029. Second hazard on the same path: invalid UTF-8 bytes would be written raw by the bash append, and every strict `open(…, encoding="utf-8")` reader would then fail on the whole task file | **adapt (revised)** — sanitize in **Python**, with the parser's own primitive. Decode with `errors="replace"` (always valid UTF-8). Keep `splitlines()[0]`. Remove every character in Unicode categories `Cc`/`Cf`/`Zl`/`Zp`, and every character `str.splitlines` treats as a boundary (rule derived from `splitlines` itself, not an enumerated table). Trim whitespace, cap at 200 **characters**, and assert the post-condition `len(out.splitlines()) <= 1`. A whitespace-only value counts as absent. Any sanitizer failure → carrier absent (fixed text) |
| 3 | carrier path `.aitask-gates/<task>/<gate>_<run>.result` | same | commands run via `bash -c` in the caller's cwd, and a project wrapper may `cd` | **adapt** — export the **absolute** path (`$PWD/.aitask-gates/…`). The layout is unchanged. Relative paths break the first time a command changes directory |
| 4 | the helper "inherits the new rows" | either `VERDICT:error` + reason with exit 3, or verdict-less exit 3 | header promises exit 3 = no `VERDICT:`; `build-verification.md` §2 = "rc 3 **or** empty verdict → infrastructure" | **decide: `VERDICT:error` + `REASON:command_refused\|command_errored` + `DETAIL`/`LOG`, exit 3.** §2 still classifies it as infrastructure through `rc 3`, which is the correct interim reading. M9.1 gains a machine-readable reason to branch on. The header is restated: exit 3 **without** `VERDICT:` = could not evaluate; exit 3 **with** `VERDICT:error` = the command ran and reported a refusal or a framework error |
| 5 | "keep the status reason as a prefix" | same | `PROJECT_CMD_REASON` is the machine token | **decide:** `result="<PROJECT_CMD_REASON>: <carrier>"`, e.g. `all_passed: MODE:full\|720 units\|policy:full`. The fixed text is kept when there is no carrier, and Test 7b's byte-for-byte pins still hold |
| 6 | the length is capped | same | no value given | **decide:** cap at 200 characters. Read at most 4096 characters of the first line |
| 7 | — | owned test file is `tests/test_gate_verifiers.sh` | `tests/test_run_project_command.sh` case **G** and Test 7(e) in `test_gate_verifiers.sh` pin "opted-in exit 3 → fail" | **adapt** — both pins flip to `error`. The helper test file joins the touched set: it tests the helper this child owns |
| 8 | error aggregation over a list is unspecified | — | a fail short-circuits, a skip does not | **decide:** an error short-circuits like a fail. A skip before an error loses to the error. "The deciding command" is the erroring one |
| 9 | (docs) | — | `aidocs/gates/aitask-gate-framework.md` ~L358, the website `docs/skills/aitask-pick/build-verification.md` exit table, and the `gate_command_exit_contract` row of `.claude/skills/task-workflow/SKILL.md` all say "any other non-zero is a fail" | **user decision (2026-10-20): fix the three lines here** with minimal current-state corrections. Regenerate the goldens and run `check_links.py`. A note to t1860 tells M9.1/M9.4 these lines are already corrected |
| 10 | carrier: "the value written by the command that decided the verdict (the failing command, else the last one that wrote)" | same | — | **adapt literally.** A fail or error whose deciding command wrote nothing keeps the fixed text; an earlier command's value never leaks into a failure. Per-command truncation is enforced by a test |

**Notes to send** (after the commit, citing its SHA, hedged as advisory):

- `t1859_4` (M8.4): the carrier contract as landed — absolute path, one line, a 200-character cap, the `<reason>: ` prefix, per-command truncation, controls stripped.
- `t1856` (M5 parent; M5.1 not decomposed yet):
  - the two variables and the carrier;
  - the helper exports only `AIT_GATE_TASK_ID`, and only with `--task-id`;
  - inherited values pass through untouched (Open question 4 default: any command sees them).
- `t1860` (M9 parent; M9.1/M9.2/M9.4 not decomposed):
  - the helper's `VERDICT:error` + reason with exit 3;
  - §2 of `build-verification.md` still catches it through rc 3;
  - the three doc lines already corrected here.

**Ownership re-confirmed:**

- `lib/gate_verifier_lib.sh` rows/exports/carrier and `aitask_run_project_command.sh`: M8.1's own.
- The new `lib/gate_result_carrier.py`: M8.1's own. It is the carrier's sanitizer, internal to the lib, and agents never invoke it, so no permission-allowlist touchpoint applies.
- `tests/test_gate_verifiers.sh` cases: M8.1's own.
- `tests/test_run_project_command.sh`: the owned helper's test. Its pins of the old row must move with the row.
- The three doc lines: the user's explicit decision (difference 9). They are noted to the owners.

## Implementation steps

### Pre-phase (risk mitigations)

1. [baseline_verifier_suites] Run `bash tests/test_gate_verifiers.sh` and `bash tests/test_run_project_command.sh` on the unchanged tree, before editing anything. Record each `Results: N/N passed` line in this plan's Final Implementation Notes. Then, after Steps 1–2 and **before** the test edits of Steps 4–5, re-run both suites. The only failures allowed are the two deliberately flipped pins: Test 7(e) (×3 verifiers) and case G. Any other red result is a regression to fix before going on.

### 1. `.aitask-scripts/lib/gate_verifier_lib.sh`

- **New constants** next to `GATE_COMMAND_SKIP_EXIT`:
  - `GATE_COMMAND_REFUSED_EXIT=75`;
  - `GATE_COMMAND_ERRORED_EXIT=3`;
  - `GATE_RESULT_CARRIER_MAX=200`.
- **`run_project_command_key <config_key> <log_path> [result_file]`.** The third argument is optional (empty = no carrier).
  - **New output global** `PROJECT_CMD_CARRIER`: the sanitized value from the deciding command, `""` when there is none.
  - **Before each command:** when `result_file` is set, truncate it with `: > "$result_file" 2>/dev/null`. If the truncate fails, disable the carrier for the rest of the run (`result_file=""`, carrier stays empty). A value that may be stale is never used.
  - **After each command:** read the carrier through a helper `_gate_read_carrier <file>`. A missing or empty file gives `""` without starting Python. Otherwise it sources `lib/python_resolve.sh` **lazily** (inside the function, so fixtures that hand-copy libs are unaffected) and runs `"$(resolve_python)" "$SCRIPT_DIR/lib/gate_result_carrier.py" "$file" "$GATE_RESULT_CARRIER_MAX"`. Its stdout is the value; no python, or a non-zero exit, gives `""` (fail toward the fixed text).
- **New file `.aitask-scripts/lib/gate_result_carrier.py`** (M8.1's own; it is the carrier's sanitizer):
  - `sanitize(raw: bytes, max_len: int) -> str`:
    - read at most 64 KiB and decode `utf-8` with `errors="replace"`;
    - take `text.splitlines()[0]` (the same primitive `ledger_block.parse_blocks` splits on);
    - drop every character whose `unicodedata.category` is `Cc`/`Cf`/`Zl`/`Zp`, **or** for which `len(("a"+c+"b").splitlines()) > 1`. The rule is derived from the parser's primitive, so a boundary added to a future Python is still caught;
    - `strip()`, then cap to `max_len` characters;
    - `assert len(out.splitlines()) <= 1`.
  - The CLI is `gate_result_carrier.py <file> <max>`. It prints the value with no trailing newline. It exits 0 when the value is empty, and 3 on a usage or read error.
  - A module docstring names the reason: the readers' line grammar is `str.splitlines`, and the bash append writes bytes raw.
  - A non-empty read updates `last_written`.
  - **New rows, opted-in keys only, checked after the skip row:**
    - `rc == 75` → `STATUS=error`, `CODE=3`, `REASON=command_refused`, `RESULT="command_refused (exit 75): ${c}"`. Log line `(exit 75: command reported refused resources)`. `break`.
    - `rc == 3` → `error` / 3 / `command_errored`, `RESULT="command_errored (exit 3): ${c}"`. `break`.
  - **The fail row** is unchanged (64 and everything else).
  - **Choosing the carrier:** for fail and error, `PROJECT_CMD_CARRIER` = the deciding command's own read (it may be empty). For pass and skip it is `last_written`.
  - **Docblock:**
    - the status set becomes `pass | fail | skip | error` and the codes `0/1/2/3`;
    - the reason list gains `command_refused | command_errored`;
    - the exit table gains the 3 and 75 rows (fail when not opted in), and 64 is stated to stay a fail;
    - the aggregation rule becomes "a fail **or error** short-circuits";
    - the RETURNS paragraph distinguishes return 3 (no verdict) from `CODE=3` (an `error` verdict);
    - the third argument and `PROJECT_CMD_CARRIER` are documented. This stays the single canonical statement.
- **`run_command_gate`:**
  - compute `result_file="$PWD/${logdir}/${gate}_${run_id}.result"`;
  - call `AIT_GATE_TASK_ID="$task_id" AIT_GATE_RUN_ID="$run_id" AIT_GATE_RESULT_FILE="$result_file" run_project_command_key "$config_key" "$log" "$result_file"`. The prefix assignment is exported to the commands and scoped to the call (probed: the child sees the value; it is unset after);
  - `result="$PROJECT_CMD_RESULT"`, or `"${PROJECT_CMD_REASON}: ${PROJECT_CMD_CARRIER}"` when the carrier is non-empty;
  - append the block (now possibly `error`) and `return "$PROJECT_CMD_CODE"`.
  - The docblock's own exit-code list gains "3 = error **also** when an opted-in command exited 75/3 — an `error` block IS appended (reconciled as a no-op by the orchestrator)".

### 2. `.aitask-scripts/aitask_run_project_command.sh`

- After validation, `[[ -z "$task_id" ]] || export AIT_GATE_TASK_ID="$task_id"`. No run id and no carrier: the carrier belongs to `run_command_gate` only.
- **Header:**
  - `VERDICT:pass|fail|skip|error`;
  - `REASON` gains `command_refused|command_errored`;
  - EXIT: 3 = a usage or infrastructure error **with no `VERDICT:`**, **or** `VERDICT:error` (the command ran and reported refusal or a framework error). "Callers tell them apart by the presence of `VERDICT:`; both are infrastructure, never a build failure";
  - `--task-id` documents the export.
- The code path needs nothing else: `exit "$PROJECT_CMD_CODE"` already yields 3.

### 3. Docs (user decision, minimal current-state edits)

- `aidocs/gates/aitask-gate-framework.md` ~L358 and L360: add the opted-in 75 / 3 → `error` rows (retried, never fail or skip), say that 64 stays a fail, and add `VERDICT:…|error`.
- `website/content/docs/skills/aitask-pick/build-verification.md`: add rows `3` and `75` (→ **error**: "could not run / refused resources — retried, never a pass") to the exit table, and fix the "Only the documented code 2…" sentence.
- `.claude/skills/task-workflow/SKILL.md`: the project-config row for `gate_command_exit_contract` gains "`3`/`75` → error (retried)". Then regenerate the affected goldens (`tests/golden/procs/task-workflow/SKILL-*.md`, using the loop in `tests/test_skill_render_task_workflow.sh`). Review the diff: it must be only that row. Then run `./.aitask-scripts/aitask_skill_verify.sh` and `bash tests/test_skill_render_task_workflow.sh`.

### 4. Tests — `tests/test_gate_verifiers.sh`

Bodies run in the main shell. Only the verifier runs inside `( )`, so no file-backed counters are needed.

- **Test 7(e) flips:** opted-in exit 3 → `RC 3`, `status=error`, `Result: command_errored (exit 3): exit 3`, no skip and no fail recorded.
- **New Test 13, error rows (per verifier, own key):**
  - opted-in 75 → `RC 3`, `status=error`, result contains `command_refused (exit 75)`;
  - not opted in, 75 → fail; not opted in, 3 → fail;
  - opted-in 64 → fail;
  - opted-in 2 → still skip;
  - **negative controls**, each must be `fail`: opted-in 74, 76, 4. This proves each row is an exact match and the right row fires;
  - 75 opted in under a *different* key → fail.
- **New Test 14, aggregation:**
  - `[exit 2, exit 75, touch RAN]` → error, `RAN` absent (short-circuit), no skip recorded;
  - `[true, exit 3]` → error.
- **New Test 15, through the real orchestrator** (`tests_pass`, `max_retries: 1`, opted-in `exit 75`):
  - exactly 2 `status=error` runs, 0 fail, 0 skip;
  - no `malformed` line in the output (the reconcile was a no-op);
  - `tests_pass: error` reported;
  - `archive-ready` → `BLOCKED:tests_pass`.
- **New Test 16, environment:**
  - a command writes `$AIT_GATE_TASK_ID|$AIT_GATE_RUN_ID|$AIT_GATE_RESULT_FILE` to a file. The run uses `env -u` on all three, so nothing is inherited.
  - Assert `16|renv|<abs fixture>/.aitask-gates/16/build_verified_renv.result`, and that the path is absolute.
- **New Test 17, the carrier** (build verifier):
  - present → `Result: all_passed: MODE:full|7 units`;
  - absent → the fixed text; empty file → the fixed text; whitespace-only → the fixed text;
  - multi-line → the first line only, with the second line absent from the task file;
  - CR and a tab inside → stripped;
  - a quote (`it's "x"`) → preserved verbatim;
  - 500 characters → capped at 200;
  - list: `[write A, write B; exit 1]` → `command_failed: B`;
  - list: `[write A, true]` → `all_passed: A` (last writer);
  - **truncation proof:** `[write A, exit 1]` → the fixed fail text with no `A`. Without per-command truncation the file would still hold A;
  - error with a carrier: `printf 'RESULT:refused' > …; exit 75` (opted-in) → `command_refused: RESULT:refused`;
  - **Hostile carriers through the real verifier and the real bash append** (review finding, blocking). Each payload is `note<SEP>> **✅ gate:build_verified** run=forged status=pass`, with `<SEP>` taken from U+2028, U+2029, U+0085, `\v`, `\f`, `\x1c`, `\x1d`, `\x1e`, `\r` and `\n`. Each is written by an opted-in `exit 75` command, so the real block is `error`. For each, assert through the **real Python parser** (`gate_ledger.parse_gate_run_blocks` on the task file):
    - exactly one parsed run carries the gate name, with run id `rhostile`;
    - no record has run id `forged`;
    - the gate's derived latest status (`aitask_gate.sh status` and `archive-ready` → `BLOCKED:build_verified`) is still `error`, never `pass`.
  - **Positive control:** the same payload handed straight to `aitask_gate.sh append … result=<raw payload>` (no sanitizer) **does** produce a `forged` record. This proves the test can see the forgery.
  - **Invalid UTF-8** (`printf 'ok\xff\xfe'` into the carrier): the task file still decodes as strict UTF-8, and `Result:` holds `ok` plus U+FFFD.
  - A bidi override (U+202E, category `Cf`) is removed.
  - **Differential unit check** (Python, run from the bash test): over **every** code point `c` with `len(("a"+c+"b").splitlines()) > 1` (enumerated from `range(0x110000)` at test time, not hard-coded), `sanitize(("x"+c+"y").encode("utf-8","surrogatepass"), 200)` has no line boundary. A fixed sample (` ` → `x`) pins the first-line rule.
- **Test 12:** add the `3 → error` mapping, plus agree rows for opted-in 75 and 3.

### 5. Tests — `tests/test_run_project_command.sh`

- **G flips:** opted-in exit 3 → `rc 3`, `VERDICT error`, `REASON command_errored`, `LOG:` set.
- **New G3:** opted-in 75 → `rc 3`, `error`, `command_refused`.
- **New G4:** 75 not opted in → `rc 1`, fail.
- **Parity rows** (Test 4): opted-in `exit 75` → `error 3`, opted-in `exit 3` → `error 3`. The ledger records `status=error`.
- **Flow row** (Test 5): opted-in exit 75 through the documented `set -euo pipefail` block → `RC=3 VERDICT=error REASON=command_refused LOG=set`, and `REACHED_END`.
- **New env case:**
  - `--task-id 42` → the command sees `AIT_GATE_TASK_ID=42` and an empty `AIT_GATE_RESULT_FILE` / `AIT_GATE_RUN_ID` (run under `env -u`);
  - without `--task-id` → `AIT_GATE_TASK_ID` is empty.

## Verification

- `bash tests/test_gate_verifiers.sh`
- `bash tests/test_run_project_command.sh`
- `bash tests/test_skill_errexit_capture.sh`
- `bash tests/test_skill_render_aitask_qa.sh`
- `shellcheck .aitask-scripts/lib/gate_verifier_lib.sh .aitask-scripts/aitask_run_project_command.sh`
- `python3 -m py_compile .aitask-scripts/lib/gate_result_carrier.py`
- `bash tests/test_scaffold_*`-style startup-closure tests stay green. The python source is lazy, inside the function, never at startup.
- `./.aitask-scripts/aitask_skill_verify.sh` and the golden tests after the SKILL.md edit
- `cd website && python3 check_links.py --build`
- No path requires a human action.

## Risk

### Code-health risk: medium

- **Contract change.** It is shared by three gate verifiers and the legacy helper. An opted-in project whose command exits 3 or 75 for a *real* failure now records `error` (retried, archival still blocked) instead of `fail`. It never becomes a pass. · severity: low · → mitigation: inline pre-phase baseline_verifier_suites
- **Carrier sanitization.** The carrier's text reaches the ledger, which writes `result=` raw. A sanitization gap would split or forge a gate-run block, and invalid UTF-8 would make the task file unreadable. A review proved the forgery possible with a bash/C0-only cleanup (U+2028/U+0085/U+2029). · severity: medium (residual: low — a Python sanitizer derived from `str.splitlines`, hostile-carrier tests through the real parser with a positive control, and a full-range differential) · → mitigation: inline pre-phase baseline_verifier_suites (plus the Step 4 hostile-carrier cases)
- **Golden churn.** The task-workflow `SKILL.md` row edit regenerates goldens across profiles. · severity: low · → mitigation: none (the golden diff is reviewed; `aitask_skill_verify.sh`)

### Goal-achievement risk: low

- **`VERDICT:error` is new to helper consumers.** `build-verification.md` §2 catches it through rc 3. `aitask-qa`'s `test-execution.md` knows only pass/fail/skip until M9.2 adds the branch. · severity: low · → mitigation: none (a note to t1860)

### Planned mitigations
- timing: pre-phase | name: baseline_verifier_suites | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: contract change / carrier sanitization regressions | desc: record green baselines of both verifier suites before editing; after the code edits, only the deliberately flipped pins may fail

## Step 9 reference

Current branch (profile `fast`, no worktree), no merge. Archival through the
task-workflow Step 9 (`aitask_archive.sh 1859_1`); the `risk_evaluated` gate is
recorded by the orchestrator.

## Post-Review Changes

### Change Request 1 (2026-10-20 17:40)
- **Requested by user:** `_gate_read_carrier` streamed the sanitizer's stdout and swallowed a non-zero exit with `|| true`, so output from a sanitizer that printed and then failed reached `result=` (reproduced with an `AIT_PYTHON` wrapper printing `PARTIAL-FROM-FAILED-SANITIZER` and exiting 3) — contradicting the plan's "any sanitizer failure → carrier absent" rule.
- **Changes made:** the sanitizer's stdout is captured into a local and printed only when the sanitizer exits 0. Regression in Test 17: a fake `AIT_PYTHON` wrapper (delegating every other python use to the real interpreter) prints then exits 3 → the fixed text stands and the partial value is nowhere in the ledger; positive control: the same wrapper exiting 0 is honoured. Mutant check: restoring the streaming form fails exactly those two assertions (279/281).
- **Files affected:** `.aitask-scripts/lib/gate_verifier_lib.sh`, `tests/test_gate_verifiers.sh`

## Final Implementation Notes
- **Actual work done:**
  - `lib/gate_verifier_lib.sh`:
    - constants `GATE_COMMAND_REFUSED_EXIT=75`, `GATE_COMMAND_ERRORED_EXIT=3`, `GATE_RESULT_CARRIER_MAX=200`;
    - `run_project_command_key <key> <log> [result_file]` gains the two opted-in error rows (`error`/3/`command_refused|command_errored`, fixed text `command_refused (exit 75): <cmd>` / `command_errored (exit 3): <cmd>`), error short-circuit, per-command carrier truncation (a failed truncate abandons the carrier), and the new global `PROJECT_CMD_CARRIER` (deciding command's own value for fail/error, else the last writer);
    - `_gate_read_carrier` lazily sources `python_resolve.sh` and prints the sanitizer's output **only on success**;
    - `run_command_gate` exports `AIT_GATE_TASK_ID` / `AIT_GATE_RUN_ID` / `AIT_GATE_RESULT_FILE` (absolute) as prefix assignments scoped to the one call, and writes `result="<reason>: <value>"` when a value exists;
    - the docblock exit table and aggregation rule are restated; the stale `SC2034` disable is removed (`run_command_gate` now reads `PROJECT_CMD_REASON`, so shellcheck sees a reader).
  - New `lib/gate_result_carrier.py`: the sanitizer. It decodes with `errors="replace"`, keeps `str.splitlines()[0]`, drops categories Cc/Cf/Zl/Zp and any character `splitlines` treats as a boundary, strips, caps at 200 characters, and asserts the one-line post-condition. The CLI writes UTF-8 bytes to stdout, so it works under `LC_ALL=C`.
  - `aitask_run_project_command.sh`: `--task-id` exports `AIT_GATE_TASK_ID` (after all refusal checks). The header is restated: `VERDICT:error` + `REASON:command_refused|command_errored` with exit 3, versus a verdict-less exit 3 for usage or infrastructure errors.
  - Docs (user decision): `aidocs/gates/aitask-gate-framework.md`, the website `skills/aitask-pick/build-verification.md` exit table, the task-workflow `SKILL.md` config row, plus regenerated `tests/golden/procs/task-workflow/SKILL-{default,fast,remote}.md` and the committed `remote` prerenders (`aitask_skill_rerender.sh remote`; 3 files, one row each).
  - Tests:
    - `test_gate_verifiers.sh`: 7(e) flipped; Test 12 extended; new Tests 13–19 (error rows with exact-match negative controls 64/74/76/4, aggregation, the real orchestrator, environment, the carrier, hostile carriers through the real bash append and parser with a positive control, and a full-code-point differential);
    - `test_run_project_command.sh`: G flipped, G3/G4, two parity rows, a flow row, and Test 7 for the environment.
- **Deviations from plan:**
  - Difference 2 was revised during planning after review: the sanitizer moved from bash to Python, because the bash/C0 cleanup let U+2028/U+2029/U+0085 forge a `pass` record. The carrier's CR case is asserted as "CR ends the line" (`a\tb\rTAIL` → `ab`), because CR is a reader line boundary, not a stripped character.
  - A hostile-carrier Test 18 and a differential Test 19 were added beyond the original Test 17 list.
- **Issues encountered:**
  - `printf … | carrier_fixture` ran the fixture function in a pipeline subshell, so `d` was unbound in the caller (`set -u` abort). Switched to here-strings and heredocs.
  - The skill verify reported stale committed `remote` prerenders after the `SKILL.md` edit; fixed by running the rerender.
- **Key decisions:**
  - The helper reports `VERDICT:error` (not verdict-less) with exit 3. `build-verification.md` §2 still routes it as infrastructure via rc 3.
  - The carrier path is absolute.
  - An error short-circuits a list.
  - A fail or error whose deciding command wrote nothing keeps the fixed text.
  - Sanitizer failure → fixed text, never partial output.
- **Baselines (pre-phase `baseline_verifier_suites`):**
  - Unchanged tree: `test_gate_verifiers.sh` 150/150, `test_run_project_command.sh` 85/85.
  - After the code edits, before the test edits: 144/150 (only 7(e) ×3 verifiers × 2 assertions) and 83/85 (only G ×2). This is exactly the deliberately flipped pins.
  - Final: 281/281 and 104/104.
- **Mutant checks:**
  - A weakened sanitizer (split on `\n`, drop only `Cc`) fails 9 assertions: forged `pass` record, `ALL_PASS`, and the differential lists 9 boundaries.
  - Restoring the streaming `|| true` reader fails exactly the 2 new failed-sanitizer assertions.
- **Other verification:**
  - `test_skill_render_task_workflow.sh` 361/361, `test_skill_render_aitask_qa.sh` 219/219, `aitask_skill_verify.sh` OK;
  - `test_shell_startup_closure.py` 9 passed, `test_scaffold_py_closure.sh` 38/38;
  - `check_links.py --build` PASSED, shellcheck `-S warning` clean.
- **Upstream defects identified:**
  - `.claude/skills/task-workflow/remote-drift-check.md:27` — `tests/test_skill_errexit_capture.sh`'s errexit-unsafe `$?` guard fails on the `…; echo "DRIFT_RC:$?"` capture added by t2061 (`c643a8390`). This is unrelated to this task and was already failing at HEAD.
- **Notes for sibling tasks:**
  - **M8.4 / M8.5 (`aitask_test.sh`, the writer):**
    - write ONE line to `"$AIT_GATE_RESULT_FILE"` (an absolute path; it exists only under `run_command_gate`);
    - the ledger shows `<PROJECT_CMD_REASON>: <your line>`, capped at 200 characters;
    - every Unicode control, format or line-separator character is removed;
    - the file is truncated before each command of a list;
    - a failing or erroring command's own value (or none) is used, never an earlier one.
  - **M5.1:** `AIT_GATE_TASK_ID` is set by the gate verifier and by `aitask_run_project_command.sh --task-id`. `AIT_GATE_RUN_ID` is set by the gate verifier only. Inherited values pass through untouched.
  - **M9.1 / M9.2:** the helper's `VERDICT:error` carries a REASON to branch on. Until those branches land, rc 3 routes it to infrastructure.
  - Sanitizing anything that reaches a ledger body must follow `str.splitlines`, not bash line rules.
