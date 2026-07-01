---
name: aitask-gate-template
description: Scaffold for authoring a new gate verifier. Documents the orchestrator's verifier contract (positional args, exit codes, sidecar log, ledger append) and provides a copy-me script template.
---

## Purpose

A **gate verifier** is the command the gate orchestrator
(`lib/gate_orchestrator.py`) runs to decide whether a machine gate passes. This
skill is the authoring scaffold: it documents the contract every verifier must
honor and gives you a copy-me script. Use it when adding a project- or
framework-specific gate (e.g. `build_verified`, `tests_pass`, `docs_updated`,
`license_check`).

A gate is one of two kinds:
- a **command verifier** (default) — a shell command the headless orchestrator
  runs (exit codes); use for programmatic checks (build, tests, lint, state
  inspection). Documented next.
- a **procedure-backed** gate (`kind: procedure`) — an agent **skill** that does
  work and confirms with the user, run by the attended task-workflow / aitask-resume
  (the headless engine defers it). Use when the gate verifies *work an agent must
  do* (e.g. `docs_updated`). See "Procedure-backed (agent) verifier" below.

Authoring a **command** gate is two steps:
1. Write a verifier command that honors the contract below.
2. Point a gate at it in `aitasks/metadata/gates.yaml`: set the gate's
   `verifier:` to the command (and `max_retries:` / `timeout_seconds:` /
   `unlocks:` as needed).

## Verifier contract

**Invocation** (positional args, in order):

```
<verifier> <task-id> <attempt> <run-id>
```

- `<task-id>` — e.g. `42` or `42_3`. Read the task file for context (plan, scope).
- `<attempt>` — the attempt number the orchestrator already wrote on the
  `running` block.
- `<run-id>` — the run id the orchestrator generated; **reuse it verbatim** when
  appending so the orchestrator and verifier agree on the same run.

**Exit codes** — the exit code is **AUTHORITATIVE**:

| Code | Meaning |
|------|---------|
| `0`  | pass — the check succeeded |
| `1`  | fail — the check ran and did not pass (a code fix is needed) |
| `2`  | skip — the gate does not apply to this task (recorded distinctly; still satisfies unlock/archive) |
| `3`  | error — the verifier itself failed (distinct from `fail`) |
| `4`  | pending — **HUMAN gates only**; a machine verifier must NEVER return `4` (the orchestrator maps a machine `4` to `error`) |

A verifier MAY append its own terminal block (to carry rich `Result:` / `Log:`
body fields), but **its appended status MUST equal its exit code**. If they
disagree, the orchestrator appends an `error` malformed-correction and the run is
treated as `error` — the exit code wins.

**A verifier MUST:**
1. Read the task file for context.
2. Run its verification logic.
3. Write full output to `.aitask-gates/<task-id>/<gate>_<run-id>.log`.
4. Append its terminal block via `aitask_gate.sh append` (never edit the task
   markdown directly), reusing `<run-id>`.
5. `exit` the right code.

**A verifier MUST NOT:**
- Modify the task frontmatter.
- Modify any other gate's `## Gate Runs` entries.
- Create a signal file for a human gate (see below).
- Retry beyond its budget — the orchestrator owns retries; the verifier runs once
  per invocation.

## Machine-gate verifier — copy-me script

```bash
#!/usr/bin/env bash
# aitask_gate_<name>.sh — verifier for the <name> gate.
# Contract: <task-id> <attempt> <run-id>; exit 0=pass 1=fail 2=skip 3=error.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GATE="<name>"
task_id="${1:?task-id required}"
attempt="${2:?attempt required}"
run_id="${3:?run-id required}"

logdir=".aitask-gates/${task_id}"
mkdir -p "$logdir"
log="${logdir}/${GATE}_${run_id}.log"

# --- replace this block with the real check ---------------------------------
if some_check_command > "$log" 2>&1; then
    status=pass; code=0
else
    status=fail; code=1
fi
# ----------------------------------------------------------------------------

"$SCRIPT_DIR/aitask_gate.sh" append "$task_id" "$GATE" "$status" \
    run="$run_id" attempt="$attempt" type=machine \
    verifier="aitask-gate-<name>" result="<short summary>" log="$log" >/dev/null
exit "$code"
```

Register it in the registry:

```yaml
gates:
  <name>:
    type: machine
    description: "..."
    verifier: aitask-gate-<name>   # → .aitask-scripts/aitask_gate_<name>.sh
    max_retries: 2
    # unlocks: omit for the linear default; [a, b] for a parallel fan-out; [] = terminal
```

**Verifier resolution** (one place owns it — `gate_orchestrator.resolve_verifier`):
- a value containing `/` or naming an existing file runs directly;
- a bare `aitask-gate-<x>` resolves to `.aitask-scripts/aitask_gate_<x>.sh`;
- anything else is treated as a command on `PATH`.

## Procedure-backed (agent) verifier — `kind: procedure`

Some gates verify **work an agent must do**, not a check a shell command can run —
e.g. `docs_updated` (update the docs for this change), or a project's
`changelog_updated`. These are **procedure-backed** gates: the `verifier` names an
**`aitask-gate-<name>` skill** (a `.claude/skills/aitask-gate-<name>/`), and the
gate is marked `kind: procedure` in the registry:

```yaml
gates:
  <name>:
    type: machine
    kind: procedure                 # headless engine defers this (needs-agent)
    description: "..."
    verifier: aitask-gate-<name>    # resolves to the SKILL for attended dispatch
    max_retries: 0
```

**How they run (differs from a command verifier):**
- The **headless** engine (`ait gates run`) does **not** execute a procedure gate.
  It reports it `needs agent (procedure-backed gate …)` and defers.
- The **attended** path (task-workflow Step 8 / `aitask-resume`) drives it:
  1. allocate the run — `aitask_gate.sh begin-procedure <task-id> <name>` opens the
     `running` block and prints `RUN_ID:<id>` / `ATTEMPT:<n>`;
  2. Read-and-follow `.claude/skills/aitask-gate-<name>/SKILL.md` with
     `<task-id> <attempt> <run-id>`;
  3. the skill does the work, **confirms with the user**, and closes the run.

**The skill records the terminal block** (reusing `<run-id>`), the same
`--only-if-running` reconcile a command verifier uses:

```bash
./.aitask-scripts/aitask_gate.sh append --only-if-running <run-id> \
    <task-id> <name> <pass|skip|fail> \
    run=<run-id> attempt=<attempt> type=machine \
    verifier=aitask-gate-<name> result="<summary>" log="$log"
```

**Status semantics** (procedure gates use the same three terminal states):
- `pass` — the required work was performed, OR inspected and already correct.
- `skip` — evaluated and **not applicable** to this change (terminal-satisfied).
- `fail` — the work is needed but the user rejects/blocks it.

Do **not** pass a `kind=` field to `append` — `kind` lives in the registry; the
marker line carries `type=machine`. See `aitask-gate-docs-updated` for a worked
example. (Full custom/external/remote procedure-gate support is a follow-up; today
procedure gates are dispatched by the attended task-workflow / aitask-resume path.)

## Human-gate verifier — special case

For `type: human` gates, the "verifier" is the orchestrator's built-in read-side
detection (you usually do not write a script). The orchestrator checks the gate's
`signal_target` (with `<task-id>`→`t<id>` and `<gate>` substituted): if the file
exists it appends `pass`; otherwise it appends `pending`. Exit-code analogue:
`0`=signal present (pass), `4`=pending.

> **Agents MUST NEVER create the signal for a human gate, suggest automating its
> creation, impersonate a reviewer, or bypass its absence. This is a
> non-negotiable autonomy control.**

**Scope boundary (t635_11):** the orchestrator ships **read-side** `file-touch`
detection (observe pass/pending). Signal **creation** (`ait gate pass`),
`signal: comment`, and remote comment polling arrive in **t635_15** — do not
add signal-creation tooling here.

---

## Notes

- The contract and the orchestrator decision tree live in
  `aidocs/gates/aitask-gate-framework.md`.
- New verifiers are run by the `aitask-run-gates` skill / `ait gates run`
  (one engine: `lib/gate_orchestrator.py`).
- Whitelist any new `aitask_gate_<name>.sh` verifier you create as a helper
  script (see `aidocs/framework/aitasks_extension_points.md`).
