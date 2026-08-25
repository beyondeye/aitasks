---
Task: t1605_gate_verifier_collapses_command_skip_to_fail.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1605 — `run_command_gate` records a project command's exit 2 (skip) as `fail`

## Context

`.aitask-scripts/lib/gate_verifier_lib.sh` → `run_command_gate()` is the shared core
behind three machine gates — `build_verified` (`verify_build`), `tests_pass`
(`test_command`), `lint` (`lint_command`). Its command loop maps **every** non-zero
exit to `status=fail`. The only `skip` it can emit is the "no `<config_key>`
configured" branch. So a project command that deliberately reports **"I did not
run"** is recorded as **"I ran and failed"**.

`tests_pass` is `blocks_dependents: true` with `max_retries: 1`, so a downstream
project whose test command legitimately reports "did not run" records a `fail` and
**blocks its dependents** for a run that never executed — with one retry against a
condition retrying cannot clear. Concretely: thinking_app's `test_command`
(`tools/verification/screenshot-tests.sh verify-active`) exits **2** since its t280
when another worktree's agent holds the host-global capacity-one heavy-run lock. With
several agents on sibling worktrees that is the normal case, not an edge one.

Intended outcome: a command can report "did not run" and have it recorded as `skip`
— which `gate_ledger.SATISFIED_STATUSES = {pass, skip}` already treats as
terminal-satisfied, so dependents unblock and archival is not held — **without**
letting any other non-zero exit be laundered into a skip.

### The two decisions this plan settles

**Opt-in, per config key.** Reserving exit 2 universally is unsafe: GNU **make**
exits 2 on a build error, **pytest** exits 2 on interrupt, `grep`/`diff` exit 2 on
trouble. A universal mapping would turn `verify_build: "make"` failures into a green
`blocks_dependents` gate — a worse bug than the one being fixed. Opt-in is **per
config key**, not global, because a project can legitimately want it on for
`test_command` and off for `verify_build`.

**The verifier's own exit code is unchanged.** `run_command_gate` still returns
`0/1/2/3`; a command-driven skip returns `2` exactly like the "no command configured"
skip. The two are distinguished in the appended `result=` line, never by the code —
the orchestrator's `map_exit` needs no change, and its status↔exit-code match check
still holds.

---

## Implementation

### Pre-phase (risk mitigations)

1. `[pin_command_resolution]` Do step 1a **alone first**: extract
   `_gate_config_values` and have `run_command_gate` call it, leaving the command
   loop, the docblock and everything else untouched. Run
   `bash tests/test_gate_verifiers.sh` — Test 1 (pass / fail / skip-absent /
   skip-null, ×3 verifiers), Test 2 (list stops at first failure) and Test 3
   (sidecar capture) must be green **before** any behavior change lands, proving the
   extraction is semantics-preserving on the code path all three gates share.
2. `[pin_command_resolution]` Add two rows to that run pinning the forms the
   extraction could silently drop: a **quoted scalar** (`verify_build: "true"`) and a
   **block list** (`verify_build:` / `  - "true"` / `  - "true"`) each still resolve
   and pass. Only then proceed to steps 1b–1d.

### 1. `.aitask-scripts/lib/gate_verifier_lib.sh` — the fix

**1a. Extract the config-value resolver.** Lift `run_command_gate`'s current inline
resolution into a helper, semantics **byte-identical** to today (list form via
`read_yaml_list`, scalar fallback via `read_yaml_field` with one layer of surrounding
quotes stripped, drop empties and the literal `null`), so the command path does not
change and the new opt-in list reuses it:

```bash
# _gate_config_values <config-file> <key>  -> zero or more values, one per line
_gate_config_values() {
    local config="$1" key="$2"
    [[ -f "$config" ]] || return 0
    local -a raw=()
    mapfile -t raw < <(read_yaml_list "$config" "$key" 2>/dev/null || true)
    if [[ ${#raw[@]} -eq 0 ]]; then
        local scalar
        scalar="$(read_yaml_field "$config" "$key" 2>/dev/null || true)"
        if [[ "$scalar" == \"*\" || "$scalar" == \'*\' ]]; then
            scalar="${scalar:1:${#scalar}-2}"
        fi
        [[ -n "$scalar" ]] && raw=("$scalar")
    fi
    local v
    for v in "${raw[@]}"; do
        [[ -n "$v" && "$v" != "null" ]] && printf '%s\n' "$v"
    done
    return 0
}
```

**1b. Three named constants** (plain globals — no `readonly`, the lib must stay
re-source-safe). One canonical spelling each; the seed config, the registry comments
and the docs quote these names:

```bash
GATE_COMMAND_EXIT_CONTRACT_KEY="gate_command_exit_contract"
GATE_COMMAND_SKIP_EXIT=2
# Every project_config.yaml command key this lib can be invoked for — one entry
# per aitask_gate_*.sh wrapper's <config_key> argument. Canonical set; a
# gate_command_exit_contract entry outside it is a typo, not an opt-in.
GATE_COMMAND_KEYS="verify_build test_command lint_command"
```

**1c. Resolve the per-key opt-in, and diagnose unrecognized entries**, inside
`run_command_gate` after the command resolution. Block-list items keep their quotes
(`read_yaml_list` strips them only on the inline `[a, b]` form), so normalize each
item before comparing:

```bash
local exit_contract=0 k unknown_keys=""
while IFS= read -r k; do
    if [[ "$k" == \"*\" || "$k" == \'*\' ]]; then k="${k:1:${#k}-2}"; fi
    if [[ " $GATE_COMMAND_KEYS " != *" $k "* ]]; then
        unknown_keys="${unknown_keys:+$unknown_keys,}$k"
        continue
    fi
    [[ "$k" == "$config_key" ]] && exit_contract=1
done < <(_gate_config_values "$config" "$GATE_COMMAND_EXIT_CONTRACT_KEY")
```

**Unrecognized entries are ignored, never fatal — but they are surfaced, not
swallowed.** A typo such as `tests_command` must not silently look identical to "not
opted in": under contention that is precisely the state that is hardest to diagnose.
Every verifier validates the *whole* list against `GATE_COMMAND_KEYS` (not just its
own `config_key`), so any of the three reports the typo. When `unknown_keys` is
non-empty, write the same message to **stderr**, to the **sidecar log**, and — the
part that is durable and actually read — as a `note=` body field on the appended
gate-run block:

```
note=gate_command_exit_contract: unrecognized key(s): tests_command (expected one of: verify_build, test_command, lint_command)
```

The gate's `status`, `result` and exit code are unaffected: a bad opt-in entry never
changes a verdict, it only explains why an expected skip did not happen.

**1d. Rewrite the command loop** — capture each command's real exit code; a
declared-skip exit is remembered but does **not** short-circuit, a fail still does:

```bash
status=pass; code=0; result="all ${config_key} command(s) passed"
: > "$log"
local c rc skipped_cmd=""
for c in "${cmds[@]}"; do
    printf '$ %s\n' "$c" >> "$log"
    rc=0
    bash -c "$c" >> "$log" 2>&1 || rc=$?
    if [[ $rc -eq 0 ]]; then continue; fi
    if [[ $exit_contract -eq 1 && $rc -eq $GATE_COMMAND_SKIP_EXIT ]]; then
        # Declared "I did not run". Not a failure — and NOT a short-circuit:
        # a later command may still fail, and a fail beside a skip stays a fail.
        printf '(exit %s: command reported skip — did not run)\n' "$rc" >> "$log"
        [[ -n "$skipped_cmd" ]] || skipped_cmd="$c"
        continue
    fi
    status=fail; code=1; result="command failed (exit ${rc}): ${c}"
    break
done
if [[ "$status" == pass && -n "$skipped_cmd" ]]; then
    status=skip; code=2
    result="command reported skip (exit ${GATE_COMMAND_SKIP_EXIT}): ${skipped_cmd}"
fi
```

The "no command configured" branch is untouched, keeping `result="no ${config_key}
configured"` — that is what keeps the two skips distinguishable.

**Aggregation rule** (stated in the docblock and asserted by tests): any fail → fail
(short-circuits); else any skip → skip; else pass.

**1e. Rewrite the `run_command_gate` docblock** so it cannot be misread as a claim
about the *command's* exit code. It gains: an explicit "THIS FUNCTION'S OWN exit
codes (what the orchestrator reads) — NOT a claim about what the project command
returned" heading; a command-exit table (`0`→pass, `1`→fail, `2`→skip *only* when the
key opted in, else fail, `*`→fail); the rule "only the documented skip code is a
skip; any other non-zero is a failure"; the aggregation rule; and the accepted
opt-in key set with the ignored-but-reported behavior for anything else.

### 2. The three wrapper headers

`aitask_gate_tests_pass.sh`, `aitask_gate_lint.sh`, `aitask_gate_build.sh` each carry
`exit 0=pass 1=fail 2=skip(no command) 3=error`. Change `2=skip(no command)` → `2=skip`
and add one line: a skip is either "no `<key>` configured" **or** a command that
declared it did not run (opt-in via `gate_command_exit_contract`) — see
`lib/gate_verifier_lib.sh`.

### 3. Tests — `tests/test_gate_verifiers.sh`

**3a. `test_command_exit_contract()` — parametrized over all three verifiers.** Reuse
the file's existing `new_fixture` / `write_task` / `write_config` / `run_verifier`
helpers and the Test-1 `rows` pattern (`build|$BUILD|verify_build|build_verified`,
`tests|$TESTS|test_command|tests_pass`, `lint|$LINT|lint_command|lint`). Rows a–e run
**per verifier with its own `<key>`**, because each wrapper passes its own
`config_key` into `run_command_gate` and the opt-in match is against that argument —
a wrapper-specific key or invocation slip would otherwise leave `test_command`
recording `fail` while the shared build path passes:

| # | fixture (per row's `<key>`) | expect |
|---|---|---|
| a | `<key>: "exit 2"`, **no** opt-in | `RC=1`, `status=fail` — today's behavior preserved |
| b | `<key>: "exit 2"` + `gate_command_exit_contract: [<key>]` | `RC=2`, `status=skip`; `result=` contains `exit 2` and the command |
| c | `<key>: "exit 2"` + opt-in listing **a different valid key** | `RC=1`, `status=fail` — discriminates the per-key dimension |
| d | `<key>: "exit 1"` + opt-in | `RC=1`, `status=fail` — reachable rejection probe |
| e | `<key>: "exit 3"` + opt-in | `RC=1`, `status=fail`, ledger contains **no** `status=skip` |

Aggregation and form rows, representative on `$BUILD`:

| # | fixture | expect |
|---|---|---|
| f | opt-in, list `["true", "exit 2", "touch RAN_THIRD"]` | `RC=2`, `status=skip`, `RAN_THIRD` **exists** — a skip does not short-circuit |
| g | opt-in, list `["exit 2", "false"]` | `RC=1`, `status=fail`, no `status=skip` — a fail beside a skip stays a fail |
| h | opt-in, list `["false", "exit 2"]` | `RC=1`, `status=fail` — a fail still short-circuits |
| i | key absent entirely (no config file) | `result=` contains `no verify_build configured` — pins that the two skips stay distinguishable |
| j | block-list opt-in form (`gate_command_exit_contract:` / `  - "verify_build"`) | `RC=2`, `status=skip` — pins the quote normalization in 1c |

**3b. `test_exit_contract_unknown_key()` — the typo is diagnosable.**

| # | fixture | expect |
|---|---|---|
| k | `verify_build: "exit 2"` + opt-in `[tests_command, verify_build]` (one typo, one valid) | `RC=2`, `status=skip` — a bad entry never changes a verdict — **and** the appended block carries `note=` naming `tests_command` |
| l | `verify_build: "exit 2"` + opt-in `[tests_command]` only | `RC=1`, `status=fail` (unrecognized ⇒ no opt-in) **and** the block carries the `note=` naming `tests_command` — the diagnostic is present exactly in the state that is otherwise indistinguishable from "not opted in" |
| m | `$TESTS` with opt-in `[verify_build]`, `test_command: "exit 2"` | the `note=` is **absent** — a valid key another verifier owns is not reported as unknown |

**3c. `test_gate_command_keys_no_drift()`** — the `GATE_COMMAND_KEYS` constant must
equal the set of `<config_key>` arguments in the wrappers, so adding a fourth
verifier without extending the constant fails here instead of silently rejecting a
legitimate opt-in:

```bash
declared=$(grep -ho 'run_command_gate [^ ]* [^ ]*' "$PROJECT_DIR"/.aitask-scripts/aitask_gate_*.sh \
           | awk '{print $3}' | sort -u | tr '\n' ' ')
```
compared against the constant sourced from the lib, both normalized to sorted sets.

**3d. `test_exit_contract_unblocks_dependents()`** — end-to-end through the **real**
entry point (the orchestrator), on **`tests_pass`**: that is the gate the task is
actually about (`blocks_dependents: true`, `max_retries: 1`) and the one thinking_app
is blocked on, so the user-facing outcome is proved rather than inferred from the
build path.

- fixture registry: `tests_pass: {type: machine, verifier: aitask-gate-tests-pass, blocks_dependents: true, max_retries: 1}`; task declares `gates: [tests_pass]`.
- `test_command: "exit 2"` + `gate_command_exit_contract: [test_command]` → run `orch`, assert `status=skip` recorded and the gate was not retried, then
  `( cd "$d" && TASK_DIR="$d/aitasks" "$GATE_SH" deps-unblock <id> )` ⇒ `SATISFIED`
  (`aitask_gate.sh` resolves its registry from `$TASK_DIR/metadata/gates.yaml`, which the fixture provides).
- **Negative control**, same fixture with `test_command: "exit 1"` ⇒ `BLOCKED:tests_pass`.
- Also assert `archive-ready` moves from `BLOCKED:tests_pass` to `ALL_PASS` across the two, since `skip` is terminal-satisfied for archival too.

Register all four in the `# --- Run ---` block. Fixtures stay non-git dirs so
`code_digest → None` and the stopping heuristic stays inert (the file's existing
contract).

### 4. Documentation sweep

| File | Change |
|---|---|
| `seed/project_config.yaml` | New commented `gate_command_exit_contract` block after the `lint_command` section, in the file's existing banner style: what the contract is, why it is opt-in (name `make`/`pytest`), the per-key list form, **the exact set of accepted keys (`verify_build` / `test_command` / `lint_command`) and that anything else is ignored with a `note=` on the gate-run block**, and the aggregation rule. |
| `.aitask-scripts/gates_reference.yaml` **and** `aitasks/metadata/gates.yaml` | The three `# Runs project_config.yaml <key>; skips (exit 2) when unset (t635_12).` comments → "…when unset, **or when the command itself exits 2 and `<key>` is listed in `gate_command_exit_contract`**". Comment-only; the two files must stay byte-identical (`tests/test_gates_reference_drift.sh`). |
| `aidocs/gates/aitask-gate-framework.md` | At the verifier-contract list (≈ line 351, `0` = pass … `2` = skip …): note that for the three project-command gates a `2` also comes from the command itself, opt-in per key, and that only exit 2 qualifies. |
| `website/content/docs/skills/aitask-pick/build-verification.md` | New short section after the `test_command`/`lint_command` block: "Reporting *did not run* from a command" — the opt-in key, the accepted key set, the exit-code table, the aggregation rule, what an unrecognized entry does, and the worked example (a command serialized behind a host-global lock). |
| `.claude/skills/task-workflow/SKILL.md` | One row in the **Project Configuration** table (≈ line 1041): `gate_command_exit_contract` \| list of command keys \| (none) \| Command keys whose commands speak the gate exit contract (`0`=pass, `1`=fail, `2`=did not run → gate `skip`); any other non-zero is a failure. Accepts `verify_build` / `test_command` / `lint_command`; other entries are ignored and reported via `note=` \| `build_verified` / `tests_pass` / `lint` verifiers. |

### 5. Re-render + goldens (same commit as step 4's SKILL.md edit)

```bash
for p in default fast remote; do ./.aitask-scripts/aitask_skill_rerender.sh "$p"; done

PYTHON="$(source .aitask-scripts/lib/python_resolve.sh && require_ait_python)"
for p in default fast remote; do
  "$PYTHON" .aitask-scripts/lib/skill_template.py \
    .claude/skills/task-workflow/SKILL.md "aitasks/metadata/profiles/$p.yaml" claude \
    > "tests/golden/procs/task-workflow/SKILL-$p.md"
done
```

Review the golden diff — it must be exactly the one added table row and nothing else.

---

## Out of scope (stated, not silently dropped)

The **legacy Step-9 `verify_build` prose path** in `task-workflow/SKILL.md`,
`aitask-pickrem` and `aitask-pickweb` runs `verify_build` directly as agent
instructions ("run each sequentially, stop on first failure") and is *not* routed
through `run_command_gate`. A project that opts in therefore still has its exit 2
treated as a build failure on that path. This is a real inconsistency, deliberately
left out (it is agent prose across three skills plus their goldens, a different change
in kind) and proposed below as a spawned "after" mitigation.

### Post-phase (risk mitigations)

1. `[pin_status_exitcode_agreement]` Add a test group asserting that for **each** of
   the four outcomes — pass, fail, skip (no command configured), skip (command
   declared it did not run) — the verifier's returned `RC` and the `status=` it
   appended to the ledger agree under `gate_orchestrator.map_exit`
   (`0↔pass`, `1↔fail`, `2↔skip`). Drive it from the recorded pair, not from two
   independent expectations, so a future edit that records `skip` while returning `1`
   fails here rather than silently tripping the orchestrator's malformed-correction
   path on a `blocks_dependents` gate.

---

## Verification

```bash
bash tests/test_gate_verifiers.sh              # new + existing groups all green
bash tests/test_gates_reference_drift.sh       # registry comment edits didn't drift
bash tests/test_skill_render_task_workflow.sh  # goldens match the re-render
./.aitask-scripts/aitask_skill_verify.sh       # stub-surface / template check
shellcheck .aitask-scripts/aitask_gate_*.sh    # follows `source=lib/gate_verifier_lib.sh`
```

Negative controls are inside `test_gate_verifiers.sh` by construction: rows (a), (c),
(d), (e), (g), (h), (l), (m) and the `deps-unblock` `BLOCKED` control all **must fail**
against a naive "any non-zero → skip", "opt-in ignored", or "every unlisted key is a
typo" implementation. Before wiring the fix, confirm rows (b) — for **each** of the
three verifiers — plus (f), (j) and (k) fail against the *current* code; otherwise they
are vacuous. Row (l) is the one that keeps the low-severity misconfiguration
diagnosable: it must fail if the `note=` is dropped.

Then Step 9 (Post-Implementation): cleanup, archival and merge per the workflow.

---

## Risk

### Code-health risk: low

- The shared resolver extraction (step 1a) is on the code path of all three gates at
  once, so a semantic slip in it silently changes command resolution for
  `verify_build` / `test_command` / `lint_command` alike · severity: medium ·
  → mitigation: inline pre-phase pin_command_resolution
- `run_command_gate` decides whether a `blocks_dependents: true` gate is green, and
  `skip` is terminal-**satisfied** — an over-broad mapping would unblock dependents
  and satisfy the archival guard for a run that failed · severity: high ·
  → mitigation: inline post-phase pin_status_exitcode_agreement

### Goal-achievement risk: low

- Opt-in means the downstream project that motivated the task (thinking_app, whose
  `test_command` already exits 2 since its t280) is **not** fixed by this change alone
  — it stays red until it adds the key · severity: medium ·
  → mitigation: thinking_app_opt_in
- The legacy Step-9 `verify_build` prose path keeps treating an opted-in command's
  exit 2 as a build failure, so a project sees two different answers for the same
  command depending on which path ran it · severity: medium ·
  → mitigation: legacy_verify_build_exit_contract

### Planned mitigations
- timing: pre-phase | name: pin_command_resolution | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — shared resolver extraction on all three gates' path | desc: Land the resolver extraction alone first and prove Tests 1–3 plus quoted-scalar / block-list forms still pass before any behavior change
- timing: post-phase | name: pin_status_exitcode_agreement | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — skip is terminal-satisfied on a blocks_dependents gate | desc: Assert the returned RC and the appended ledger status agree under map_exit for all four outcomes
- timing: after | name: thinking_app_opt_in | type: chore | priority: high | effort: low | inline_risk: high | added_complexity: high | addresses: goal-achievement — motivating project not fixed by this change alone | desc: Cross-repo (thinking_app) — add gate_command_exit_contract: [test_command] to its project_config.yaml and verify a real heavy-lock refusal records skip end-to-end
- timing: after | name: legacy_verify_build_exit_contract | type: enhancement | priority: medium | effort: medium | inline_risk: high | added_complexity: high | addresses: goal-achievement — legacy Step-9 prose path disagrees with the gate path | desc: Teach the legacy verify_build prose path (task-workflow / pickrem / pickweb + goldens) the same opt-in contract, or document the divergence deliberately

**Reassessment after inlining:** both inline phases only add tests and reorder the
landing sequence — no new production code — so both dimensions stay **low**.
