---
Task: t1409_fix_failed_verification_t1109_item5.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1409 — Re-validate a code-bound human-gate signature after it has passed

## Context

`aitasks/metadata/gates.yaml` documents `review_approved` / `merge_approved` as
**code-bound**: `ait gate pass` stamps the witness file with the repo's
`code_digest`, and "a signature against a different code state re-pends".

That contract holds only while the gate's ledger status is non-terminal. Once a
`pass` is recorded, the witness is never read again:

- `gate_orchestrator.py:470` — `run()` short-circuits with "All gates satisfied"
  when `all(_satisfied(state, g) for g in active)`; `_satisfied` reads the
  **ledger status**, never the witness.
- `gate_orchestrator.py:227` (`compute_unlocked`) skips any already-satisfied
  gate, so `_handle_human()` — the only caller of `_signal_state()`, which does
  the digest comparison — is unreachable.
- `gate_ledger.archive_status()` is ledger-only too, so
  `aitask_gate.sh archive-ready` independently reports `ALL_PASS`.

Net effect (reproduced live on t1408 during the t1109 manual verification): sign
→ change a code file → `ait gates run` says "All gates satisfied", `archive-ready`
says `ALL_PASS`, and the task archives carrying code the reviewer never approved.
Only the `--gate <name>` force path (`_force_one`) surfaced the staleness.

This matters because the headless lane's documented completion sequence is *stop
at pending → human signs → re-run to archive*, and any code change during that
resumed run (e.g. fixing a machine-gate failure surfaced in the same Step 9.5)
moves the digest with nothing re-checking it.

**Outcome:** the code-binding is re-validated on every observation, before and
after a recorded pass, on both the write-side engine (`ait gates run`) and the
read-side archival guard (`archive-ready`).

## Approach

Two structural moves, no new invariant for future callers to remember:

1. **Lift the witness/digest primitives into the shared substrate**
   (`lib/gate_ledger.py`), so the engine and the archival guard classify
   staleness with **one** implementation instead of two agreeing copies.
2. **Demote stale-signed gates inside `Engine._read_state()`** rather than
   special-casing the short-circuit. Every consumer of the derived state (the
   all-satisfied check, `compute_unlocked`, `blocked_reason`, `_handle_human`,
   and `_force_one`) then sees the gate as unsatisfied for free, and the
   *existing* `_handle_human` stale branch does the re-pend — no new append site.

### Deliberate scoping decisions

- **Only `stale` re-pends.** `absent` (no witness) must stay accepted: attended
  sessions record `review_approved` directly from the interactive approval and
  never write a witness. `unstamped` (witness with no `code_digest`) stays
  accepted for backward compatibility. This is what keeps
  `test_gate_orchestrator.sh` Test 9c green.
- **"Cannot check" is its own state, and each path decides it.** When
  `code_digest()` returns `None` (git absent / no commits), staleness is
  *unverifiable*, and both paths resolve it the same way the existing
  `_signal_state` already does: accept (treat as `unstamped`). Recorded in the
  docstring, not left implicit.
- **The archival guard reports, it does not write.** `archive-ready` is a
  read-only decision verb; on a stale signature it returns
  `BLOCKED:<gate>` and lets `ait gates run` (the single writer of observed
  human-gate blocks) record the `pending`. Documented, so the transient
  "`ait gate status` says pass / `archive-ready` says BLOCKED" window is a stated
  contract rather than a surprise.
- **Digest computation is lazy.** `stale_signed_gates()` collects candidates
  (satisfied + `type: human` + witness file present) *first* and only shells out
  to git if the candidate list is non-empty. `archive-ready` runs on every
  archival and in `aitask_query_files.sh inflight`; the overwhelmingly common
  case (no witness files) stays exactly as cheap as today.

### Out of scope (explicit dispositions)

| Surface | Disposition |
|---|---|
| `archive_status_from_text()` — used by `stats_data.py`, `trail_gather.py` | Stays ledger-only. Content-level twin by contract (no filesystem/git); these are analytics scans over many tasks. Documented in its docstring as the ledger-only twin. |
| `read_task_gate_state()` — board / monitor TUI badge | Stays ledger-only (per-task git calls would be a per-refresh cost across ~100 tasks). Documented. |
| `deps-unblock` | Stays ledger-only — same per-task cost on every `ait ls`. Out of the task's stated scope (`gates run` + `archive-ready`). |
| `gate_orchestrator.unlocked()` (`ait gates unlocked`) | Ledger-only introspection; the enforcing path is `run()`. |

## Implementation

### 1. `.aitask-scripts/lib/gate_ledger.py`

Add a `# --- code-state digest + human-gate signal witness ---` section (stdlib
only; `subprocess` is stdlib):

- **Move** from `gate_orchestrator.py`: `_git()`, `_DIGEST_EXCLUDES`,
  `code_digest(cwd=None)`, `_read_witness_digest()` → public
  `read_witness_digest()`, and `_task_id_from_file()` → public
  `task_id_from_file()`. Docstrings move with them.
- `resolve_signal_target(template, task_id, gate) -> str` — the
  `<task-id>`→`t<id>` / `<gate>` substitution, currently inline in
  `Engine._signal_state`.
- `witness_state(gate, registry, task_id, current_digest) -> (kind, recorded)` —
  the classifier extracted verbatim from `Engine._signal_state`
  (`absent` / `fresh` / `stale` / `unstamped`), now pure.
- `stale_signed_gates(active, registry, state, task_id, current_digest=_UNSET)
  -> list[str]` — satisfied (`pass`/`skip`) **and** `type: human` **and** witness
  file exists **and** `witness_state(...) == "stale"`, in `active` order. Computes
  `code_digest()` lazily only when the cheap candidate filter is non-empty; `_UNSET`
  sentinel distinguishes "compute it" from a caller-supplied digest (including
  `None`, which means unverifiable → `[]`).

Extend the archival decision:

```python
def archive_status(task_file: str, registry_file: str | None = None):
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    decision, nonpass = archive_status_from_text(text)   # ledger-only base
    if decision == "NO_GATES" or not registry_file:
        return decision, nonpass
    active = read_active_gates_from_text(text)
    stale = stale_signed_gates(active, read_registry(registry_file),
                               derive_gate_runs(text), task_id_from_file(task_file))
    if not stale:
        return decision, nonpass
    blocked = [g for g in active if g in nonpass or g in stale]   # declared order
    return ("BLOCKED", blocked)
```

`registry_file` defaults to `None` so any existing single-arg caller keeps
today's behavior. CLI: `archive-ready <file> [registry]` forwards `argv[2]`.

### 2. `.aitask-scripts/lib/gate_orchestrator.py`

- Re-export the moved helpers so the public names keep working (the
  `gate_orchestrator.py code-digest` CLI, `tests/test_gate_orchestrator.sh`,
  `aitask_gate_pass.sh`): `code_digest = gl.code_digest`,
  `_read_witness_digest = gl.read_witness_digest`,
  `_task_id_from_file = gl.task_id_from_file`.
- `Engine._signal_state()` becomes a one-line delegation to
  `gl.witness_state(gate, self.registry, self.task_id, self.digest)`.
- `Engine._read_state()` — the fix:

```python
        state = {r.name: r for r in runs}
        # t1409: a recorded pass must NOT freeze the code-binding. A human gate
        # whose witness was signed against a DIFFERENT code state is dropped
        # from the derived view, so every consumer — the all-satisfied
        # short-circuit, compute_unlocked, blocked_reason, _handle_human and
        # _force_one — sees it as unsatisfied and the existing stale branch of
        # _handle_human re-pends it with the 'stale signature' note.
        for g in gl.stale_signed_gates(active, self.registry, state,
                                       self.task_id, self.digest):
            del state[g]
```

`runs_by_gate` is left intact, so retry budgets and the stopping heuristic are
unaffected. Termination: once re-pended the gate is no longer satisfied, so the
demotion cannot re-fire, and `_handle_human`'s `cur.status == "pending"` branch
returns `False` → `changed` is `False` → the loop breaks.

### 3. `.aitask-scripts/aitask_gate.sh`

`cmd_archive_ready()` → `delegate_python archive-ready "$file" "$REGISTRY" || echo "NO_GATES"`,
with the comment updated to name the witness re-validation and the
report-don't-write split.

### 4. `tests/test_gate_orchestrator.sh`

- **New `test_human_gate_post_pass_stale` (Test 9d)** — the regression, in a git
  fixture with a gitignored `sig/`:
  1. witness stamped with the current digest → `orch` → `review: pass`;
     `archive-ready` → `ALL_PASS` (seeds the state — an empty ledger would make
     the later assertion vacuous).
  2. mutate `code.txt` → digest flips.
  3. `orch` → output contains `review: pending` **and** `stale signature`;
     ledger status is `pending`.
  4. `archive-ready` → `BLOCKED:review`.
- **Extend `test_human_gate_no_repend` (Test 9c)** with
  `archive-ready → ALL_PASS`: the discriminating negative case — a satisfied
  human gate with a `signal_target` but **no witness** (the attended-recorded
  pass) must not be re-pended or blocked.
- Update the file header comment to name the post-pass re-validation.

### 5. Docs

- `aidocs/gates/gate-guarded-archival.md` — `archive_status(task_file,
  registry_file)`: the ledger-only base decision plus the witness overlay;
  `BLOCKED:<csv>` can now name a gate whose *ledger* says `pass`; the
  report-don't-write split; `archive_status_from_text` named as the ledger-only
  twin with its consumers.
- `aidocs/gates/aitask-gate-framework.md` — extend the walkthrough note at
  step 24 (and the `signal` schema row) to state the freshness check runs on
  **every** observation, including after a recorded pass, and that both
  `ait gates run` and the archival guard enforce it.

## Verification

Negative control first — the new assertions must fail against unfixed code:

```bash
git stash                                   # or: write the test before the fix
bash tests/test_gate_orchestrator.sh        # Test 9d MUST fail (ALL_PASS / "All gates satisfied")
```

Then, with the fix applied:

```bash
bash tests/test_gate_orchestrator.sh        # 9d passes, 9c (no-repend) still passes
bash tests/test_gate_guarded_archival.sh
bash tests/test_gate_pass.sh
bash tests/test_gate_cli_wiring.sh
bash tests/test_gate_verifiers.sh
bash tests/test_gate_ledger.sh
bash tests/test_gate_recorded_pass.sh
bash tests/test_gate_reentry.sh
bash tests/test_query_files_inflight.sh
bash tests/test_gates_reference_drift.sh
bash tests/run_all_python_tests.sh --test-dir tests   # gate_ledger / orchestrator parser modules
shellcheck .aitask-scripts/aitask_gate.sh
```

End-to-end sanity in a throwaway git fixture (mirrors the t1109 live repro):
sign a gate with `ait gate pass`, touch a code file, then confirm
`ait gates run <id>` re-pends with the `stale signature` note and
`aitask_gate.sh archive-ready <id>` reports `BLOCKED:review_approved`.

Step 9 (Post-Implementation) handles merge, `ait gates run`, and archival.

## Risk

### Code-health risk: medium
- Moving `code_digest` / witness helpers from `gate_orchestrator.py` into
  `gate_ledger.py` touches a load-bearing shared module and two public-ish call
  sites (`aitask_gate_pass.sh` shells `gate_orchestrator.py code-digest`;
  `tests/test_gate_orchestrator.sh` does too) · severity: medium · → mitigation:
  keep module-level re-export aliases in `gate_orchestrator.py` so no name
  disappears, and run the full gate test set listed above
- Demoting a gate inside `_read_state()` changes the derived view for *every*
  engine consumer at once; a mistake in the predicate would re-pend legitimately
  passed gates (attended `review_approved` has no witness at all) · severity:
  medium · → mitigation: the predicate requires an *existing, stamped, mismatched*
  witness, and Test 9c is the standing negative control that an
  attended-recorded pass with no witness is never demoted
- `archive-ready` returns a bare `BLOCKED:<gate>` for a gate whose ledger still
  reads `pass`, so `aitask_archive.sh`'s `GATE_PENDING:<csv>` tells the user to
  wait for a gate rather than to re-sign a stale signature · severity: low ·
  → mitigation: gate_stale_signature_archive_message
- `archive-ready` gains a conditional git shell-out; a non-lazy implementation
  would slow `ait ls`-adjacent paths · severity: low · → mitigation: candidate
  filter before the digest call, so the no-witness case does zero extra work

### Goal-achievement risk: low
- The failure is precisely reproduced and its two mechanisms are read directly
  in source; the fix closes both, and the regression test asserts both surfaces
  (`gates run` **and** `archive-ready`) as the task's acceptance criteria
  require · severity: low
- Four agreeing-but-unfixed surfaces (`archive_status_from_text`,
  `read_task_gate_state`, `deps-unblock`, `unlocked`) remain ledger-only, so a
  board badge or `ait ls` row can disagree with the enforcing decision ·
  severity: low · → mitigation: gate_stale_witness_surface_parity

### Planned mitigations
- timing: after | name: gate_stale_witness_surface_parity | type: enhancement | priority: medium | effort: medium | addresses: goal-achievement — ledger-only surfaces disagree with the enforcing decision | desc: Thread a once-per-refresh code digest through archive_status_from_text / read_task_gate_state / deps-unblock / gates unlocked, or ratify them as deliberately ledger-only with a drift guard.
- timing: after | name: gate_stale_signature_archive_message | type: enhancement | priority: low | effort: low | addresses: code-health — bare BLOCKED:<gate> for a ledger-pass gate | desc: Give aitask_archive.sh a distinct GATE_STALE_SIGNATURE:<csv> signal so the user is told to re-sign with 'ait gate pass' instead of to wait for a pending gate.

## Post-Review Changes

### Change Request 1 (2026-08-04 14:45)

- **Requested by user:** The Test 9d `archive-ready` assertion did not
  discriminate. It ran *after* `orch "$d" 93`, and that re-pend moves the ledger
  to `pending` — so `archive-ready` returns `BLOCKED` from the ledger alone,
  even with the new stale-witness overlay in `gate_ledger.archive_status()`
  removed or broken. Assert `BLOCKED:review` immediately after the code
  mutation and *before* the `orch` call, then keep the post-re-pend assertion.
- **Changes made:** Verified the concern — CONFIRMED. Test 9d step 3 now asserts
  the read-side guard first, with `assert_contains "pre-run: the ledger still
  reads pass"` pinning the precondition that makes it discriminating (only the
  overlay can produce `BLOCKED` while the ledger says `pass`). The write-side
  re-pend assertions moved to step 4, followed by a second `archive-ready`
  check on the re-pended ledger. Two single-mutation negative controls were then
  run to prove each fix has its own discriminator (see below).
- **Files affected:** `tests/test_gate_orchestrator.sh`

## Final Implementation Notes

- **Actual work done:** Implemented as planned, in three parts.
  1. `lib/gate_ledger.py` gained a shared "code-state digest + human-gate signal
     witness" section: `code_digest` / `_git` / `_DIGEST_EXCLUDES`,
     `read_witness_digest` and `task_id_from_file` moved here from
     `gate_orchestrator.py`; `resolve_signal_target`, `witness_state` (the
     `absent`/`fresh`/`stale`/`unstamped` classifier extracted from
     `Engine._signal_state`), `_has_stamped_witness` and `stale_signed_gates`
     are new. `archive_status()` now takes an optional `registry_file` and adds
     stale-signed gates to the blocked list; the CLI forwards `argv[2]`.
  2. `lib/gate_orchestrator.py` re-exports the moved names, `_signal_state`
     delegates to `gl.witness_state`, and `Engine._read_state()` deletes
     stale-signed gates from the derived state map.
  3. `aitask_gate.sh cmd_archive_ready` passes `"$REGISTRY"`.
- **Deviations from plan:** One addition not in the plan — while consolidating,
  the three inline copies of the satisfied-predicate
  (`(state.get(g).status if state.get(g) else None) in SATISFIED_STATUSES`) in
  `_dependents_status_from_state`, `_archive_status_from_state` and
  `unmet_procedure_gates` were folded into the new shared `_gate_satisfied()`
  that `stale_signed_gates` needed anyway. Behaviour-identical; it just stops a
  fourth copy from being added. No other deviation.
- **Issues encountered:**
  - *The regression test initially did not discriminate* (found in review, see
    Change Request 1). The original negative control reverted BOTH fixes at
    once, which masked it: with the orchestrator fix alone, the re-pend supplies
    the `BLOCKED` that the read-side assertion was crediting to the overlay. The
    lesson generalizes — when one change has two enforcement points, the
    negative control must disable them **one at a time**.
  - Final negative controls (each a single mutation, then restored):
    | mutation | failures |
    |---|---|
    | `aitask_gate.sh` drops `"$REGISTRY"` (read-side off, engine intact) | exactly 1 — `stale witness alone blocks archival (ledger untouched)`, got `ALL_PASS` |
    | `_read_state` demotion replaced with `pass` (engine off, read-side intact) | exactly 3 — the re-pend assertions, got `All gates satisfied` |
  - Test 9c constrained the design: it has a `signal_target` but no witness file,
    so re-pending on anything other than `stale` (e.g. on `absent`) would break
    the attended lane, which records `review_approved` from the interactive
    approval and never writes a witness.
- **Key decisions:**
  - **Demote in `_read_state()` rather than guard the short-circuit.** The
    alternative (an explicit re-validation pass before `all(_satisfied(...))`)
    is an invariant every future entry point must remember; demoting at the one
    place state is read makes `run()`, `compute_unlocked`, `blocked_reason`,
    `_handle_human` and `_force_one` correct without any of them knowing. The
    re-pend then reuses `_handle_human`'s existing `stale` branch, so there is
    no second append site and no second copy of the note text.
  - **Move the primitives into `gate_ledger` instead of adding an orchestrator
    CLI verb the shell could call.** Two enforcement points must not own two
    classifiers. Re-export aliases keep `gate_orchestrator.py code-digest` and
    every importer working.
  - **`archive-ready` reports; it does not write.** It is a read-only decision
    verb, and `ait gates run` stays the single writer of observed human-gate
    blocks. The transient "status says pass / archive-ready says BLOCKED" window
    is documented as the contract in both the docstring and
    `aidocs/gates/gate-guarded-archival.md`.
  - **Unverifiable ≠ stale.** A `None` digest (no git / no commits) resolves to
    `unstamped` (accept), the same as a witness with no recorded digest — never
    a guessed `stale`. `witness_state` decides this explicitly rather than
    leaving it to callers.
  - **Lazy digest.** `stale_signed_gates` applies a no-git pre-filter
    (satisfied + `type: human` + a stamped witness on disk) and only shells out
    to git if something survives, so `archive-ready` — which runs on every
    archival and in `aitask_query_files.sh inflight` — costs nothing in the
    common no-witness case.
  - **Four surfaces left deliberately ledger-only** (`archive_status_from_text`
    → stats/trail, `read_task_gate_state` → board badge, `deps-unblock`,
    `gates unlocked`): per-task git subprocesses across a refresh are not
    affordable. Written into each docstring and into the archival doc as a
    stated split, with `gate_stale_witness_surface_parity` as the follow-up.
- **Upstream defects identified:** None
