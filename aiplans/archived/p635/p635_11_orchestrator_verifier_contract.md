---
Task: t635_11_orchestrator_verifier_contract.md
Parent Task: aitasks/t635_gates_framework.md
Sibling Tasks: aitasks/t635/t635_12_build_test_machine_gates.md, aitasks/t635/t635_13_risk_evaluation_gate_integration.md, aitasks/t635/t635_14_profile_gate_declaration_unification.md, aitasks/t635/t635_15_async_human_gates.md, aitasks/t635/t635_16_remote_projection_appendix_a.md, aitasks/t635/t635_17_autonomous_lane_rigor.md, aitasks/t635/t635_18_website_documentation.md, aitasks/t635/t635_19_docs_updated_gate.md, aitasks/t635/t635_20_stats_multistage_completion.md, aitasks/t635/t635_21_gate_ledger_merge_safety.md, aitasks/t635/t635_22_polish_board_inflight_empty_gate_state.md
Archived Sibling Plans: aiplans/archived/p635/p635_10_monitor_gate_status_column.md, aiplans/archived/p635/p635_1_gate_ledger_substrate.md, aiplans/archived/p635/p635_2_task_workflow_checkpoint_recording.md, aiplans/archived/p635/p635_3_dependency_unblock_semantics.md, aiplans/archived/p635/p635_4_gate_guarded_archival.md, aiplans/archived/p635/p635_5_ledger_driven_reentry.md, aiplans/archived/p635/p635_6_aitask_resume_skill.md, aiplans/archived/p635/p635_7_gate_aware_aitask_pick.md, aiplans/archived/p635/p635_8_python_gate_ledger_parser.md, aiplans/archived/p635/p635_9_board_inflight_action_view.md
Base branch: main
plan_verified: []
---

# t635_11 — Gate Orchestrator + Verifier Contract (Phase 4)

## Context

The aitasks **gate framework** (`aidocs/gates/aitask-gate-framework.md`) makes task
execution stateful and multi-pass: named verification checkpoints (gates) declared in
task frontmatter, recorded as append-only marker blockquotes in a `## Gate Runs`
section. Phases 1–3 (t635_1…t635_10) shipped the **substrate**: the marker format and
`aitask_gate.sh` (append/status/list/deps-unblock/archive-ready/resume-point), the
`lib/gate_ledger.py` parser, the `aitask_gate_record.sh` recorder, a minimal
`gates.yaml` registry (`type`/`description`/`blocks_dependents` only), gate-guarded
archival, ledger-driven re-entry, and TUI visibility.

What is still missing is the **engine** that actually *runs* gates. Today nothing
computes which gates are runnable, dispatches verifiers, applies retry budgets, or
stops at a pending human gate. **t635_11 (Phase 4) lands that engine**, behind the
already-shipped `aitask-resume` front (t635_6) — "one engine, not two". It is the
blocking parent for the first concrete machine-gate conversions (t635_12 build/tests,
t635_13 risk, t635_19 docs) and the profile→gate unification (t635_14).

**Outcome:** `ait gates run <task-id>` (and the autonomous lane, and the
`aitask-run-gates` skill) can read a task's declared gates + the registry, run the
unlocked machine-gate verifiers in parallel within their retry budgets, observe human
gates without ever self-signalling, and converge — all derived from the ledger, with
no frontmatter writes.

## Architecture decision (confirmed with user)

**Two layers.** A headless, unit-testable Python engine + bash wrapper (Layer 1), and
thin Claude skills as fronts (Layer 2). This diverges from the framework doc's "the
orchestrator is a skill that delegates to verifier skills via the Task tool" wording,
because that framing predates the substrate that actually shipped (bash+python
helpers, not skills) and three hard constraints forbid it:

1. `ait` is a bash dispatcher — `ait gates run` and the autonomous lane (aitask-pickrem,
   t635_17) need **headless** execution; a dispatcher cannot invoke a Claude skill.
2. Project rule: orchestration logic (unlocked-set DAG, retry budget, stopping
   heuristic, exit-code interpretation) is pure decision logic that must be unit-tested
   **without spawning agents** — mandating a Python module, mirroring how
   `gate_ledger.py` is the testable core under `aitask_gate.sh`.
3. `claude -p` headless print mode is discouraged (`shell_conventions.md`).

**Verifiers are resolvable COMMANDS, not skills** — positional args
`<task-id> <attempt> <run-id>` + exit codes `0=pass / 1=fail / 2=skip / 3=error /
4=pending` (4 = human-gate pending). The engine interprets exit codes centrally; stub
scripts reproduce every code in tests. A verifier MAY be implemented as a skill
internally, but its orchestrator-facing contract is the script/exit-code contract.

**Confirmed scope decisions:**
- **Human gates: read-side `file-touch` detection ships now; signal CREATION defers to
  t635_15.** The engine checks `signal_target` (with `<task-id>` substituted): file
  present → append `pass`; absent → append `pending`; it NEVER self-signals. `ait gate
  pass` (signal creation) is out of scope. **This boundary must be loudly documented**
  (registry header, verifier template, and a coordination note added to t635_15's task
  file) so the human-gate sibling doesn't miss that read-side detection already exists.
- **Stopping-heuristic state lives in the ledger `note=` body field** (`note=stuckhash:<git-blob-hash>`),
  honoring D6 (derive state from the ledger only) — no new schema, no sidecar.
- **Registry `verifier:` values stay EMPTY in this task** — the engine treats an empty
  `verifier:` as "no auto-run". Populating them is t635_12 (build/tests), t635_13
  (risk), t635_19 (docs). This keeps the registry valid before any concrete verifier
  exists.

## Out of scope (later children — do NOT build)
- Concrete verifier commands for tests/build/docs (t635_12, t635_19); risk-eval gate
  conversion (t635_13); profile→gate declaration unification (t635_14).
- Async / `signal: comment` human gates, comment polling, and `ait gate pass` signal
  CREATION (t635_15). Remote projection / label+comment mirror / Appendix A (t635_16).

---

## New files

### `.aitask-scripts/lib/gate_orchestrator.py` — the engine (stdlib only)
Imports `gate_ledger` for parse/derive/append; owns all orchestration decision logic.
- **Extend the registry parser** — add the new per-gate keys *inside*
  `gate_ledger.read_registry` (ONE registry parser): `verifier` (str, default `""`),
  `max_retries` (int, default `0`), `unlocks`, `timeout_seconds` (int, optional),
  `signal` / `signal_target` (str, human only). Defaults keep existing callers
  unaffected. **`unlocks` must distinguish ABSENT from explicit empty (concern 1):** the
  key is parsed to `None` when **absent** (→ use the linear default for that gate) and to
  a `list[str]` when present (inline `[a,b]` or block `- a`), where an explicit `[]` means
  "terminal — unlocks nothing". Never collapse absent → `[]`.
- **`SATISFIED = {pass, skip}` (concern 2).** A gate counts as *satisfied* (for unlocking
  successors, for the all-satisfied stop, and for archive/dependents) iff its current
  status is `pass` **or** `skip`. `skip` (exit 2) = "evaluated, not applicable" — it is
  **terminal-satisfied**: it unlocks successors and never blocks archive or dependents,
  but is recorded distinctly in history (per framework open-Q3, skip stays distinct from
  pass). This requires extending the satisfied-predicate in `gate_ledger.archive_status`
  and `dependents_status` (currently pass-only) to `pass OR skip` — a deliberate, tested
  edit to the shared helper (flagged under Cross-cutting). Without it a not-applicable
  `docs_updated` skip would block archive forever.
- **`compute_unlocked(declared, registry, state) -> list[str]`** — the DAG rule, computed
  **per-gate** (concern 1): g is unlocked iff every predecessor of g is *satisfied*
  (`pass`/`skip`), AND `state[g] not in SATISFIED`, AND `attempts(g) < max_retries(g)+1`.
  Predecessors are resolved per-gate from each gate p's `successors(p)`:
  `successors(p) = registry[p].unlocks` when that key is **present** (incl. explicit `[]`);
  when **absent**, `successors(p) = [next gate after p in the task's gates: list]` (linear
  default). `predecessors(g) = { p | g ∈ successors(p) }`. So a gate with an absent
  `unlocks` keeps its linear successor while a sibling that declares `unlocks:` overrides
  only its own — mixing parallel and linear correctly. Pure — unit-testable on in-memory
  dicts, no subprocess.
- **`blocked_reason(g, …)`** — `exhausted` / `pending human` / `upstream <name> failed`,
  for the empty-unlocked report.
- **`is_stuck(task_file, gate, state)`** — stopping heuristic over the **code change
  surface, NOT the task file (concern 3).** Hashing the task file is wrong because the
  engine's own gate-run appends mutate it every run, so the hash would always differ and
  the heuristic would never fire. Instead the change surface is the repo's **code state**,
  and it must cover **staged, unstaged, AND untracked** code (concern A) — a fix the user
  staged or added as a new file must still flip the digest:
  `code_digest = sha( git rev-parse HEAD  +  git diff HEAD <excludes>  +  Σ over
  git ls-files --others --exclude-standard <excludes>: (path + sha(content)) )`. Note
  **`git diff HEAD`** (not plain `git diff`) captures **both staged and unstaged** tracked
  changes, and the `ls-files --others` term adds **untracked** file contents; plain
  `git diff` would miss both. `<excludes>` scopes out the task/plan data paths
  (`':(exclude)aitasks/**' ':(exclude)aiplans/**' ':(exclude).aitask-data/**'`) so ledger
  churn is ignored and only a real code change flips the digest. On each `fail` append,
  record `note=stuckhash:<code_digest>`; on
  next dispatch, if the current `code_digest` equals the last fail's recorded value AND
  the prior attempt was a fail, mark exhausted-by-heuristic and skip dispatch (don't burn
  budget). A code change between attempts flips the digest → the gate is eligible again.
  (Exact path-exclusion under the data-branch/symlink architecture is nailed by Test 5.)
  Framework §Worked example "stopping heuristic".
- **`run_gate(task_id, gate, registry, attempt, run_id, dry_run)`** — resolve the
  verifier command, append a `running` block via `aitask_gate.sh append` subprocess
  (reuse its per-task lock + atomic write — never write the task file directly), spawn
  the verifier with `<task-id> <attempt> <run-id>`, enforce `timeout_seconds` (on timeout
  the verifier subprocess is **killed before** `ensure_terminal_block`, so it cannot
  append afterwards), map exit code → status via `map_exit(code, gate_type)` below.
- **`map_exit(code, gate_type)` — gate-type-aware (concern 4):** `0→pass, 1→fail, 2→skip,
  3→error`. `4` is **pending ONLY for human gates**; a **machine** verifier returning `4`
  is malfunctioning → map to `error` (a machine gate must never enter `pending`). Any
  other/unknown code → `error`.
- **`reconcile_terminal(task_id, gate, run_id, exit_status, attempt)` — exit code is
  AUTHORITATIVE; reconcile the verifier's self-append (concerns 4, 6, B).** The verifier
  MAY append its own terminal block (to carry rich body fields: Result/Log), but the
  **exit code is the source of truth for STATUS** — a verifier must never be trusted to
  self-report a status that contradicts its exit code. After the verifier returns,
  re-derive the run_id's current state and act in three cases (the check+append done
  atomically under the per-task lock — see the `aitask_gate.sh` edit):
  1. **Still `running`** (verifier appended nothing) → append the engine's terminal block
     = `exit_status` via `append --only-if-running <run-id>`. (agreement by construction)
  2. **Terminal AND == `exit_status`** → no-op. Exactly one terminal block for the run_id.
  3. **Terminal BUT != `exit_status` (mismatch, concern B)** → the verifier lied (e.g.
     appended `pass` but exited `1`). Do NOT trust the ledger entry: append a **fresh-run_id
     `error` correction block** with `note=malformed: verifier reported <claimed> but exited
     <code> → treated as error`, and **report** it. Because derivation is last-marker-wins,
     the correction becomes the gate's current state (`error`), overriding the verifier's
     false claim — append-only, no rewrite. (The per-run_id "single terminal" invariant of
     concern 6 still holds: the correction is its own run_id.)
  This makes the engine the final arbiter via the exit code while preserving the framework's
  "verifier appends a rich block" contract. The `aitask-gate-template` documents the
  invariant: **a verifier's appended status MUST equal its exit code**, or the engine flags
  the run malformed.
- **`run(task_id, *, gate=None, dry_run=False, max_parallel=2, registry_file)`** — the
  decision-tree driver (see pseudocode). Re-reads the ledger each iteration; bounded
  fixpoint (max iters = len(declared)+1) → idempotent no-op. Empty `verifier:` ⇒ skip
  machine dispatch (leave the gate for human/checkpoint recording).
- **`--gate <name>` semantics (concern 7) — explicit force-run of a single gate.** It
  **force-runs `<name>` regardless of its current `pass`/`skip` state and regardless of
  retry-budget exhaustion** (an explicit human override — this is the "unless `--gate`"
  carve-out the re-entry contract's skip-already-passed rule refers to), provided its
  predecessors are *satisfied* (won't run if upstreams aren't `pass`/`skip`). It runs that
  one gate only (no fan-out) and does not loop. If predecessors are unsatisfied, report why
  and do nothing.
- **`main(argv)`** mirroring `gate_ledger.py`'s CLI: `run <task-file> [--gate g]
  [--dry-run] [--max-parallel N] [--registry path]` and `unlocked <task-file>
  [--registry path]` (prints the unlocked set, one per line — backs `ait gates unlocked`).
- **Parallelism cap:** `min(max_parallel, os.cpu_count() or 1)` in Python (cleaner than
  the getconf/sysctl/nproc chain); the bash wrapper only resolves the *profile* value.
  Dispatch via `ThreadPoolExecutor`; appends serialize through `aitask_gate.sh`'s lock.

### `.aitask-scripts/aitask_run_gates.sh` — headless entry (whitelisted helper)
`set -euo pipefail`; source `terminal_compat.sh`, `task_utils.sh`, `python_resolve.sh`,
`yaml_utils.sh` (mirror `aitask_gate.sh`'s header). **Argument parsing (concern 5) — parse
and SHIFT before delegating, so args are never duplicated:** `subcmd="$1"; shift`
(`run`|`unlocked`); `task_id="$1"; shift` → `resolve_task_file "$task_id"` → `"$file"`; the
**remaining** `"$@"` is only the flags (`--gate`/`--dry-run`/…). Resolve the active profile
(`aitask_skill_resolve_profile.sh run-gates` → `aitasks/metadata/profiles/<name>.yaml`,
honoring `local/` precedence) and read `max_parallel_gates` (default 2). Then delegate
exactly once: `gate_orchestrator.py "$subcmd" "$file" --max-parallel <n> --registry
aitasks/metadata/gates.yaml "$@"` — the subcommand and task-id appear once; only residual
flags flow through `"$@"`. Propagate stdout + exit code. This is what `ait gates
run/unlocked`, the `aitask-run-gates` skill, `aitask-resume`, and aitask-pickrem call.

### `.aitask-scripts/aitask_gate_log.sh` — `ait gate log <task-id> <gate>`
Resolve task file → find the current run's `Log:` body field for `<gate>` → `cat` the
sidecar at `.aitask-gates/<task-id>/<gate>_<run-id>.log`. No log → friendly message,
exit 0. (Whitelisted helper.)

### `.aitask-scripts/aitask_gate_fail.sh` — `ait gate fail <task-id> <gate> [--reason …]`
~25-line wrapper over `aitask_gate.sh append <id> <gate> fail [note=<reason>]` (manual
fail marker, e.g. a human rejecting review). Dedicated helper (unit-testable) over an
inline dispatcher shim. (Whitelisted helper.)

### New skill `aitask-run-gates` (profile-aware stub + `.md.j2`)
Full stub set per `stub-skill-pattern.md`: Claude stub `.claude/skills/aitask-run-gates/SKILL.md`
(resolver key `run-gates`), `SKILL.md.j2`, Codex `.agents/skills/aitask-run-gates/SKILL.md`,
OpenCode `.opencode/commands/aitask-run-gates.md`. Body: parse `<task-id> [--gate <name>]
[--dry-run]`; resolve task file; run `aitask_run_gates.sh run <task-id> […]`; narrate the
decision tree / results; on "pending human", explain the next human action; **never fork
the engine logic** — it is the conversational twin of `ait gates run`. Likely
profile-invariant (single `-default` golden + byte-invariance assertion).

### New skill `aitask-gate-template` (profile-aware stub + `.md.j2`)
The verifier authoring scaffold. Body documents: the contract (positional args; exit
codes — **machine verifiers return `0=pass / 1=fail / 2=skip / 3=error`; `4=pending` is
HUMAN-GATE-ONLY** and a normal machine verifier must never return it); **the exit code is
AUTHORITATIVE — if a verifier appends its own terminal block, its status MUST equal its
exit code, or the engine flags the run malformed and treats it as `error`** (concern B);
a copy-me **script scaffold** (read task → run check → write sidecar
log → append terminal block via `aitask_gate.sh append` → `exit` the right code); the
MUST-NOT list (no frontmatter edits, no other gates' runs, **never create a human-gate
signal**, no retries beyond budget); the human-gate special case (check signal,
append pass/pending, exit 0/4, verbatim "Agents MUST NEVER create the signal for a
human gate"); and the **verifier-command resolution rules** (`resolve_verifier` lives in
`gate_orchestrator.py` — document it here: a path under `.aitask-scripts/` runs directly;
a bare `aitask-gate-<x>` → `.aitask-scripts/aitask_gate_<x>.sh`). **Document the human-gate
scope boundary**: read-side file-touch detection exists as of t635_11; signal CREATION
arrives in t635_15.

### Test files
- `tests/test_gate_orchestrator.sh` (bash, mirrors `tests/test_gate_reentry.sh`: asserts.sh
  + test_scaffold.sh, mktemp dirs, PASS/FAIL). Stub verifiers = scripts that `exit N` and
  optionally append. Cases: (1) no gates → no-op; (2) unlocked DAG — **linear default with
  `unlocks:` ABSENT** (only first gate unlocked, then next after it passes), **explicit
  `unlocks:` fan-out** (A unlocks [B,C] → both unlock together), and the **mixed case** (one
  gate absent=linear, one declares unlocks), already-satisfied/exhausted excluded; (2b)
  **absent-vs-`[]` regression** — a registry with `unlocks: []` on a gate makes it terminal,
  NOT root-unlocked, and absent keys stay linear (guards concern 1); (3) exit codes
  0/1/2/3 → pass/fail/skip/error; **machine verifier exit 4 → `error`** (concern 4); (3b)
  **skip is terminal-satisfied** — a `skip` predecessor unlocks successors AND
  `archive-ready` returns ALL_PASS (does not block) (concern 2); (4) retry within budget
  (attempt increments to max_retries+1); (5) stopping heuristic over the **code surface** —
  two identical fails with only gate-run appends in between (NO code change) → second run
  stops/exhausted; then assert the digest flips for **each** of: an unstaged edit, a
  **staged** edit (`git add`), and a **new untracked** file → gate eligible again; and that
  a pure gate-run append does NOT flip it (guards concerns 3 + A); (6) parallel dispatch
  `--max-parallel 2` both run, ledger well-formed (no interleaving); `--max-parallel 1`
  serial; (6b) **idempotent terminal append** — a stub verifier that appends its OWN
  terminal block (matching its exit code) leaves exactly ONE terminal entry (engine
  no-ops); a verifier that appends NONE still leaves exactly one (guards concern 6); (6c)
  **status/exit mismatch** — a stub verifier that appends `pass` but **exits 1** → engine
  appends a fresh-run_id `error` malformed-correction, derived current status = `error`
  (not pass), and reports it (guards concern B); (7) `--dry-run`
  appends nothing; (8) idempotent no-op on all-pass; (9) human gate — absent signal → one
  `pending`, never self-signals; create file → `pass`; (10) **`--gate <name>` force-runs a
  passed gate** (overrides skip-already-passed) but refuses when predecessors unsatisfied
  (concern 7); (11) `ait gates unlocked`; (12) python-absent degrade guard.
- `tests/test_gate_orchestrator_registry.py` (or fold into
  `tests/test_gate_ledger_python_parser.py`): extended `read_registry` parses the new
  keys (inline + block) with correct defaults and **`unlocks` absent → `None` vs explicit
  `[]` → empty list** (concern 1); `compute_unlocked` pure on in-memory state incl. the
  mixed absent/declared case and `skip`-as-satisfied; `archive_status`/`dependents_status`
  treat `skip` as satisfied (concern 2).
- `tests/test_gate_cli_wiring.sh`: `ait gates run/unlocked/list/status` + `ait gate
  append/fail/log` dispatch to the right helpers (assert via `--help`/dry-run, no agent).
- `tests/test_skill_render_aitask_run_gates.sh` + `tests/test_skill_render_aitask_gate_template.sh`
  mirroring `tests/test_skill_render_aitask_resume.sh` (per-profile golden diff,
  agent-invariance Test 1b, no-runtime-reresolve Test 3b, cross-agent ref Test 4).

## Edits to existing files

### `.aitask-scripts/lib/gate_ledger.py` — registry keys + skip-satisfied (shared helper)
Two edits to the shared parser (blast radius: every gate consumer — flag + test): (a)
extend `read_registry` to capture the new per-gate keys, with **`unlocks` absent → `None`**
distinct from explicit `[]` (concern 1); (b) extend the *satisfied* predicate in
`archive_status` and `dependents_status` from `== pass` to `status in {pass, skip}`
(concern 2), so a not-applicable `skip` does not block archive/dependents. Both backed by
the registry python test. Keep `gate_ledger.py` stdlib-only and side-effect-light (TUIs
depend on it).

### `.aitask-scripts/aitask_gate.sh` — atomic conditional append (concern 6)
Add `append --only-if-running <run-id> <task-id> <gate> <status> [k=v…]` (or an
`ensure-terminal` subcommand): **inside the existing per-task mkdir lock**, re-read the
ledger and append the terminal block **only if** the block for that exact `run=<run-id>` is
still `running`; no-op if a terminal block already exists. This makes the engine's
`ensure_terminal_block` a single atomic operation (no TOCTOU between check and append).
Reuse the existing lock + atomic-write path; covered by Test 6b.

### `aitasks/metadata/gates.yaml` — full registry schema
Add the orchestration keys to each gate, **`verifier: ""` left empty** (machine example:
`verifier: ""`, `max_retries`, `timeout_seconds`; human example adds `signal: file-touch`,
`signal_target: ".aitask-gates/<task-id>/<gate>.signed"`). **Do NOT materialize `unlocks:`
on every gate (concern 1)** — an explicit `unlocks: []` means "terminal, unlocks nothing"
and is NOT the same as the key being absent (absent → linear default). Since this task's
gates keep their default linear order, **leave `unlocks:` ABSENT on the seeded gates** and
document the key only in the header comment (with a parallel-fan-out example shown
commented-out). Materializing `[]` everywhere would make every gate root-unlocked and run
in parallel — the exact bug compute_unlocked's per-gate absence rule avoids. Expand the
header comment to document every new key, the **absent-vs-explicit-`[]` unlock rule**, that
`skip` is terminal-satisfied (does not block), the `<task-id>` substitution, that empty
`verifier` = no auto-run, **and the human-gate boundary** (read-side detection in t635_11,
signal creation in t635_15).

### `ait` dispatcher — add `gate)` and `gates)` cases
Follow the `crew)` / `brainstorm)` nested-subcommand exemplar; place before `git)`.
- `gates)`: `run`→`aitask_run_gates.sh run`, `unlocked`→`aitask_run_gates.sh unlocked`,
  `list`→`aitask_gate.sh list`, `status`→`aitask_gate.sh status`, help block.
- `gate)`: `append`→`aitask_gate.sh append`, `fail`→`aitask_gate_fail.sh`,
  `log`→`aitask_gate_log.sh`, help block. **Do NOT add `gate pass`** (t635_15).

### `.claude/skills/aitask-resume/SKILL.md.j2` — refit as the engine's front
Replace Step 2's `--gate` "report only / Do not run a verifier" block (current rendered
lines ~98–105): when `--gate <name>` (or an explicit run-gates intent) is present, invoke
`aitask_run_gates.sh run <task-id> --gate <name>` and narrate the result. Remove the
"Automated per-gate verifier execution arrives with the orchestrator" disclaimer — that
future has arrived. Keep the no-`--gate` resume hand-off unchanged; the skill stays a
FRONT (never re-derives unlocked/retry logic). On "pending human", surface and stop (no
self-signal). Edit the `.md.j2` ONLY; the profile-agnostic stubs don't change — goldens
regenerate.

### `.aitask-scripts/lib/profile_editor.py` + profiles + docs — `max_parallel_gates`
Register `max_parallel_gates` (int, default 2) in `profile_editor.py`'s `FIELDS` table +
help text + "Gates" group (mirror `record_gates`). Add `max_parallel_gates: 2` to
`aitasks/metadata/profiles/fast.yaml` (the gates-enabled profile). Add a schema-table row
to `.claude/skills/task-workflow/profiles.md`.

### t635_15 task file — coordination note (bidirectional link)
Per the user's explicit doc request and the repo's coordination-link convention, add a
note to `aitasks/t635/t635_15_async_human_gates.md` recording that t635_11 shipped
**read-side file-touch** human-gate detection (pending/pass observation), so t635_15 owns
only signal **creation** (`ait gate pass`), `signal: comment`, and polling — not the read
path. Commit via `./ait git`.

---

## Engine algorithm (pseudocode)

```
SATISFIED = {pass, skip}                            # skip = evaluated/not-applicable, terminal-satisfied

run(task_id, gate=None, dry_run=False, max_parallel=2, registry_file):
  text, declared = read(task_file), read_declared_gates(text)
  if not declared: report("No gates declared; nothing to do."); return 0
  registry = read_registry(registry_file)          # unlocks: None=absent vs []=explicit-terminal
  if gate is not None:                              # --gate: explicit single force-run
    if predecessors(gate) all in SATISFIED:        # override skip-already-passed + budget
      force_run_one(task_id, gate, registry); return 0
    else: report(gate, "predecessors not satisfied"); return 0
  loop (bounded: max iters = len(declared)+1):
    state = derive_gate_runs(read(task_file))       # re-read after appends
    if all(state[g].status in SATISFIED for g in declared):
      report("All gates satisfied. Ready for archive."); suggest_done(); return 0
    unlocked = compute_unlocked(declared, registry, state)   # per-gate absent/declared rule
    if not unlocked:
      for g in declared where state[g] not in SATISFIED: report(g, blocked_reason(g,…))
      return 0
    machine = [g in unlocked if registry[g].type=='machine' and registry[g].verifier
                and not is_stuck(task_file, g, state)]   # empty verifier => skip dispatch
    human   = [g in unlocked if registry[g].type=='human']
    if dry_run: report_decision_tree(unlocked, machine, human); return 0
    with ThreadPool(min(max_parallel, cpu, len(machine))):
      for g in machine:
        attempt, run_id = current_attempt(state,g)+1, iso_now()
        gate_append(task_id, g, 'running', attempt, run_id, verifier=…)
        code = spawn(resolve_verifier(registry[g].verifier), task_id, attempt, run_id,
                     timeout=registry[g].timeout_seconds)   # killed on timeout before append
        status = map_exit(code, registry[g].type)   # machine 4 -> error; human 4 -> pending; AUTHORITATIVE
        reconcile_terminal(task_id, g, run_id, status, attempt,
                           note=('stuckhash:'+code_digest() if status==fail else None))
        #   running        -> append status (only_if_running, atomic under lock)
        #   terminal==status-> no-op
        #   terminal!=status-> append fresh-run_id ERROR 'malformed' correction (last-wins) + report
    for g in human:                                  # never self-signal
      if signal_present(registry[g], task_id): gate_append(task_id, g, 'pass', …)
      elif not pending_exists(state, g):        gate_append(task_id, g, 'pending', type='human')
    if no machine gate changed state this iteration: break   # idempotent fixpoint
  return 0
# map_exit(code, type): 0->pass 1->fail 2->skip 3->error ; 4-> (pending if type==human else error) ; else error
# code_digest = sha(git rev-parse HEAD + git diff HEAD<excl> + untracked file contents<excl>)
#   <excl> = exclude aitasks/ aiplans/ .aitask-data/ ; diff HEAD = staged+unstaged; ls-files --others = untracked
```

## Re-entry contract (framework §Re-entry contract)
Idempotent no-op; skip-already-passed (unless `--gate`); retry within budget; stop at
pending-human; NO frontmatter writes; append-only; task-level lock around appends
(delegated to `aitask_gate.sh`); stopping heuristic for identical repeated failures.

## Cross-cutting obligations
1. **Whitelist (per `aitasks_extension_points.md`)** the 3 new skill-invoked helpers
   (`aitask_run_gates.sh`, `aitask_gate_log.sh`, `aitask_gate_fail.sh`) across all
   touchpoints: `.claude/settings.local.json`, `.codex/rules/default.rules`,
   `seed/claude_settings.local.json`, `seed/codex_rules.default.rules`,
   `seed/opencode_config.seed.json`. (`gate_orchestrator.py` is reached only via the
   wrapper → not whitelisted.)
2. **Regenerate goldens in the same commit** for `aitask-resume` (3 existing:
   `SKILL-{default,fast,remote}-claude.md`) and the two new skills (add golden dirs).
3. **`./.aitask-scripts/aitask_skill_verify.sh`** must pass — each new skill ships all 3
   stub surfaces (claude/codex/opencode) or it fails.
4. **`tests/lib/test_scaffold.sh`** — if `aitask_run_gates.sh` sources a lib not in the
   fake-repo baseline, add it to `setup_fake_aitask_repo()` (it needs `task_utils.sh` +
   `gate_ledger.py` + `gate_orchestrator.py`).
5. **macOS portability** (`sed_macos_issues.md`): `sed_inplace` not `sed -i`; no
   `grep -P`; no gawk-only 3-arg `match()`; `os.cpu_count()` for the core cap.
6. **Cross-agent port follow-ups:** skill-source changes auto-render Claude→Codex/OpenCode;
   suggest separate aitasks only if an agent-specific surface is touched (likely none here).

## Verification (end-to-end)
1. **Unit/integration:** `bash tests/test_gate_orchestrator.sh`,
   `bash tests/test_gate_cli_wiring.sh`, the registry python test, and both
   `test_skill_render_*` tests — all PASS.
2. **Lint:** `shellcheck .aitask-scripts/aitask_run_gates.sh
   .aitask-scripts/aitask_gate_log.sh .aitask-scripts/aitask_gate_fail.sh`.
3. **Skill verify + goldens:** `./.aitask-scripts/aitask_skill_verify.sh` passes; goldens
   regenerated and committed in the same change.
4. **Live smoke (manual):** craft a temp task with `gates: [g1, g2]`, a registry whose
   `g1.verifier` points at a stub script that exits 0/1, and run `ait gates run <id>`,
   `ait gates unlocked <id>`, `ait gates run <id> --dry-run`, `ait gate log <id> g1`,
   `ait gate fail <id> g2 --reason x`; confirm the ledger derives correctly and a
   human gate with an absent `signal_target` stays `pending` (never self-signalled).
5. Reference **Step 9 (Post-Implementation)** for cleanup / archival / merge.

## Risk

### Code-health risk: medium
- Extending the **shared** `gate_ledger.read_registry` with the new keys ripples to
  every consumer (decision helpers + TUIs t635_8/9/10); a parser regression would
  corrupt gate status framework-wide · severity: medium · → mitigation: defaulted new
  keys (backward-compatible) + a registry unit test asserting existing callers are
  unaffected (in-plan, Test `read_registry` defaults).
- Parallel verifier dispatch (ThreadPool + subprocess, appends serialized only by
  `aitask_gate.sh`'s per-task mkdir lock) introduces concurrency that could interleave
  or corrupt the ledger · severity: medium · → mitigation: in-plan test asserting a
  well-formed ledger under `--max-parallel 2` and parity under `--max-parallel 1`; reuse
  the proven existing lock rather than a new one.
- The `aitask-resume` `--gate` path flips from report-only to engine-invoking; a
  regression could break the existing resume front · severity: low · → mitigation: leave
  the no-`--gate` hand-off untouched; render-golden + behavioral assertion.

### Goal-achievement risk: medium
- **Stopping-heuristic hashing subtlety (RESOLVED in design — concern 3):** hashing the
  task file is wrong because the engine's own gate-run appends mutate it every run, so the
  hash would always differ and the heuristic would never fire. **Decided:** hash the
  **code change surface** instead — `sha(git rev-parse HEAD + git diff)` scoped to exclude
  `aitasks/`/`aiplans/`/`.aitask-data/`, stored as `note=stuckhash:`. A code fix flips the
  digest (gate eligible again); a pure gate-run append does not · severity: high (mitigated)
  · → mitigation: Test 5 asserts both directions; exact data-path exclusion under the
  data-branch/symlink layout nailed there.
- No concrete verifier exists in this task (empty `verifier:`), so the engine is
  validated only against stub scripts; real-verifier integration is first exercised in
  t635_12 · severity: medium · → mitigation: gate_orchestrator_live_verify (exhaustive
  stub coverage of every exit code 0–4 + the manual live-smoke in Verification §4 cover
  this task; the live behavioral validation against a real verifier runs in the
  follow-up).

### Planned mitigations
- timing: after | name: t1015 (gate_orchestrator_live_verify) | type: manual_verification | priority: medium | effort: medium | addresses: goal-achievement "no concrete verifier exercises the engine until t635_12" | desc: autonomous manual-verification driving the live orchestrator end-to-end against the first real verifier — parallel dispatch, retry-within-budget, the stopping heuristic on a real fail→fix→pass loop, and pending-human observation; coordinate to run after t635_12 lands a concrete verifier.

## Final Implementation Notes

- **Actual work done:** Built the two-layer gate engine exactly as planned.
  New: `lib/gate_orchestrator.py` (engine), `aitask_run_gates.sh` (wrapper),
  `aitask_gate_log.sh`, `aitask_gate_fail.sh`, skills `aitask-run-gates` +
  `aitask-gate-template`, tests `test_gate_orchestrator.sh` (33),
  `test_gate_orchestrator_registry.py` (25), `test_gate_cli_wiring.sh` (12).
  Edited: `gate_ledger.py` (registry keys + skip-satisfied), `aitask_gate.sh`
  (`--only-if-running`), `ait` (gate/gates cases), `gates.yaml` (schema+docs),
  `aitask-resume` `.md.j2` refit (+goldens), `profile_editor.py`/`fast.yaml`/
  `profiles.md` (`max_parallel_gates`), whitelists (4 framework touchpoints),
  t635_15 coordination note. All confirmed design decisions implemented:
  exit-code-authoritative reconcile, code-surface stopping heuristic
  (staged+unstaged+untracked), global linear-vs-DAG unlock mode, atomic
  `--only-if-running`, gate-type-aware exit map, parse-and-shift wrapper args.

- **Deviations from plan:** The two new skills were authored as PLAIN Claude
  skills (no profile-aware stub + `.md.j2` + goldens) instead of profile-aware
  stubs, because they have zero profile-varying behavior — matching the
  established plain-skill pattern (`aitask-shadow`, `aitask-create`) and avoiding
  the stub/render/goldens overhead for no benefit. Codex/OpenCode ports are
  filed as follow-up **t635_23** (plain skills do not auto-render). The
  `aitask-resume` refit remains a `.md.j2` edit (it IS profile-aware) with
  regenerated goldens. Decision surfaced explicitly at review; approved.

- **Issues encountered:** The new tests caught THREE real engine bugs during
  development — (1) parallel fan-out was re-chained by an implicit linear edge
  (fixed: GLOBAL linear-vs-DAG mode, not per-gate); (2) `is_stuck` compared
  historical fail digests to each other, so it never re-enabled after a code fix
  (fixed: compare trailing fails against the CURRENT code digest); (3) the
  fixpoint loop cap `len(declared)+1` cut off legitimate retries (fixed:
  budget-aware backstop). Also: a gate with an empty `verifier` that was unlocked
  produced no report (fixed: report non-runnable unlocked gates). The live
  `.claude/settings.local.json` whitelist edit was blocked by the auto-mode
  self-modification guard — the 4 framework-artifact touchpoints are done; the
  user may add the 3 helpers to their live settings.

- **Key decisions:** Verifiers are resolvable COMMANDS (positional args + exit
  codes), not skills — forced by headless `ait gates run` / autonomous-lane
  needs. Human gates ship READ-SIDE file-touch detection only (creation →
  t635_15, coordinated). `verifier:` values stay empty (populated by t635_12/13/
  19). Stopping-heuristic state lives in the ledger `note=stuckhash:` on the
  engine-authored running block.

- **Upstream defects identified:** None. (Two PRE-EXISTING, unrelated test
  failures were surfaced — board-load AttributeError in
  test_settings_shortcuts_tab.py / test_shortcut_scopes.py, and the
  task-workflown source-file-list parity drift missing gate-recording.md — but
  neither seeded a t635_11 symptom; both are filed as follow-up **t1014**.)

- **Notes for sibling tasks:** The orchestrator engine is COMPLETE and the
  contract is frozen — t635_12 (build/tests), t635_13 (risk), t635_19 (docs)
  just set a gate's `verifier:` in `gates.yaml` to an `aitask-gate-<name>` (→
  `.aitask-scripts/aitask_gate_<name>.sh`) honoring the `aitask-gate-template`
  contract (exit 0/1/2/3; `4`=pending is human-only). The engine handles
  retries, parallelism, the stopping heuristic, and ledger appends — verifiers
  must NOT re-implement those. `skip` (exit 2) is terminal-satisfied. Whitelist
  any new `aitask_gate_<name>.sh`. t635_14 (profile→gate unification) can declare
  gates per profile; `max_parallel_gates` is already a profile key. t635_15 owns
  human-signal CREATION only (read-side already done) — see its coordination
  note. t635_16 (remote projection / Appendix A) is the post-append hook layer,
  not yet present.
