---
Task: t1416_gate_stale_witness_surface_parity.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
Output branch: main
---

# t1416 — Resolve the ledger-only / witness-re-validated surface split

## Context

t1409 made a human gate's **code-bound witness** re-validated on *every*
observation, not just before the first `pass`. Two surfaces enforce it —
`gate_orchestrator.Engine._read_state()` (write side) and
`gate_ledger.archive_status(task_file, registry_file)` (read-side archival
guard, via `aitask_gate.sh archive-ready`).

Four surfaces were left **ledger-only** on a *cost* argument ("a git subprocess
per task per refresh"), recorded as a low-severity goal-achievement risk in
`aiplans/archived/p1409_*.md`: a board badge or an `ait ls` row can disagree
with the enforcing decision. This task resolves the split instead of leaving it
as tribal knowledge.

**Exploration changed the shape of the answer: the four surfaces are not
alike.** Two of them have no cost problem at all, one has a *semantics*
question the cost argument was hiding, and one has a reason to stay ledger-only
that is stronger than cost. Measurements on this repo:

| fact | value |
|---|---|
| `code_digest()` | ~9 ms warm (3 git subprocesses) |
| `.signed` witnesses present | **0** (the attended lane never writes one) |
| `stale_signed_gates()` pre-filter | no-git; git fires only for a task that *has* a stamped witness |
| `ait ls` | 12.5 s, ~all of it the 307 per-task `deps-unblock` subprocesses (47 ms each) — pre-existing, out of scope |

So the decided split is:

| Surface | Decision | Reason |
|---|---|---|
| `gate_orchestrator.unlocked()` | **re-validate** | One-shot, single-task, human-invoked introspection verb (`gate_orchestrator.py:494`). There is no loop — the per-task-fan-out rationale never applied. Costs at most one `code_digest()`. |
| `gate_ledger.read_task_gate_state()` | **re-validate** | Board threads a **once-per-refresh** digest (mirroring the existing `gate_registry()` per-refresh cache). Lazy: zero git calls in a repo with no signed witnesses. |
| `aitask_gate.sh deps-unblock` | **re-validate** | A *semantics* decision, not a cost one: `review_approved` / `merge_approved` are `blocks_dependents: true` **and** are exactly the two code-bound gates. A signature against different code is not approval of the code a dependent would build on. |
| `gate_ledger.archive_status_from_text()` | **ratify ledger-only** + drift guard | Not cost: (a) it is a **pure-text contract** — no filesystem, no registry, no task id (`gate_ledger.py:1583`); (b) `trail_gather.task_record()["gates_pending"]` is **hashed into the trail's `input_digest`** staleness key (`trail_gather.py:413` → `:424` → `:1078`), so making it code-state-dependent would flip every trail's staleness verdict on unrelated commits. |

Two surfaces are ratified ledger-only, both registered in a drift guard:
`archive_status_from_text()` (above) and the **monitor / minimonitor compact
gate column**. The monitor is ratified because it calls
`read_task_gate_state(path)` with **no registry** (`monitor_core.py:2955`), so
it cannot classify a human gate at all, and its cache is keyed on
`(st_mtime_ns, st_size)` of the *task file* (`monitor_core.py:2929`) — a code
change does not touch that file, so a digest-sensitive verdict would need the
digest in the cache key, re-computed every 3 s tick, undoing the t1111_1
optimization that stopped the per-tick cache clear. It also runs cross-project
where the witness path (`resolve_signal_target` → cwd-relative) resolves wrong.
**This is a deliberate narrowing** of "board/monitor" and is stated as such: the
two surfaces t1409's risk actually named — "a board badge or `ait ls` row" — are
both fixed.

**Outcome:** every surface that reports archival readiness or releases
dependents either re-validates the signature, or is registered in a guard that
fails when a new ledger-only consumer is added without picking a side.

## Approach

One shared demotion helper, threaded four ways, plus one structural guard. No
new invariant a future caller has to remember: the same
`gate_ledger.stale_signed_gates()` classifier t1409 introduced stays the single
implementation, and every surface reaches it through one new function.

The digest channel gains a fourth state — a **zero-arg callable** — so
"compute once per refresh, but only if something needs it" is expressible
without the caller guessing. Today's `_COMPUTE_DIGEST` sentinel already
distinguishes "compute lazily" from an explicit `None` ("unverifiable"); a
callable is the missing "here is my memo, call it if the cheap pre-filter finds
a candidate".

## Implementation

### Pre-phase (risk mitigations)

0. `[witness_heavy_cost_probe]` **Measure before committing to the design** (the
   task's own instruction: *"Measure the cost before committing to it — the board
   refresh budget is the binding constraint"*). The lazy pre-filter is exactly
   defeated when tasks carry stamped witnesses, so build a throwaway fixture with
   ~50 gated tasks that **all** carry a stamped `.signed` witness and measure,
   against a same-fixture baseline with the witnesses removed:
   - `time ait ls` — projected added cost W×3 git subprocesses ≈ 50 × 9 ms ≈
     0.45 s on this repo's 12.5 s baseline (~3.6%);
   - one board refresh, with a `code_digest` call-counting spy — projected
     **exactly 1** call regardless of W, added wall-clock ≈ 9 ms.

   **Thresholds and fallback (decided now, not after the fact):**
   - Board refresh: **> 1** `code_digest()` per refresh, or **> 50 ms** added at
     W=50 → the memo/threading design is wrong; stop and re-plan it.
   - `ait ls`: **> 10%** added wall-clock at W=50 → do **not** ship the lazy
     per-process default. Fallback: thread the digest across processes —
     `aitask_ls.sh` computes it once before its loop and passes it to each call
     as an explicit `deps-unblock --code-digest <value>` **argument** (an
     argument, not an env var: it is visible at the call site and cannot leak
     between repos or survive into an unrelated process). That caps `ait ls` at
     one git triple total. `dependents_status` already accepts the digest, so
     the fallback is a shell-side change only.
   - Record the measured numbers and which branch was taken in the plan before
     proceeding; if a threshold is crossed, say so and re-plan rather than
     restating the projection.

1. `[guard_enforcing_path_consolidation]` Capture a baseline of the **enforcing**
   path before touching it: run `bash tests/test_gate_orchestrator.sh` and record
   the Test 9 / 9c / 9d results.
2. `[guard_enforcing_path_consolidation]` Land **only** §2's
   `Engine._read_state()` → `gl.demote_stale_signed(...)` consolidation (plus the
   `demote_stale_signed` helper it needs), as an isolated edit with nothing else
   in the working tree, and re-run `bash tests/test_gate_orchestrator.sh`. Tests
   9/9c/9d MUST be byte-identical to the baseline — the consolidation is
   behaviour-preserving by construction. Only then proceed to the four new
   surfaces, so any later enforcing-path regression is attributable to a
   specific edit rather than to the batch.

### 1. `.aitask-scripts/lib/gate_ledger.py`

**a. Resolve the digest channel in one place.** Add next to `_COMPUTE_DIGEST`
(`:1356`):

```python
def _resolve_digest(current_digest):
    """Resolve the four-state digest channel to ``str | None``.

    ``_COMPUTE_DIGEST`` -> compute now; a callable -> call it now (the
    once-per-refresh memo); a ``str`` -> use it; ``None`` -> unverifiable, a
    real answer that ``witness_state`` resolves to ``unstamped`` (accept).
    Called ONLY after the no-git pre-filter finds a candidate, so a provider is
    never invoked in the common no-witness case.
    """
    if current_digest is _COMPUTE_DIGEST:
        return code_digest()
    if callable(current_digest):
        return current_digest()
    return current_digest
```

Rewrite `stale_signed_gates` (`:1475`) lines 1503-1504 to
`current_digest = _resolve_digest(current_digest)` and extend its docstring to
document all four states.

**b. The shared demotion.** New public helper (the one seam every surface uses):

```python
def demote_stale_signed(gates, registry, state, task_id,
                        current_digest=_COMPUTE_DIGEST):
    """``(state_without_stale, stale)`` — the derived view with code-stale
    human-gate signatures removed (t1409/t1416).

    The single seam every consuming surface goes through, so an added surface
    cannot accidentally get a ledger-only view: the orchestrator's
    ``_read_state``, the archival guard, ``unlocked()``, ``read_task_gate_state``
    and ``dependents_status`` all call this. Returns the ORIGINAL mapping object
    unchanged (not a copy) when nothing is stale — the overwhelmingly common
    case must allocate nothing.
    """
    stale = stale_signed_gates(gates, registry, state, task_id, current_digest)
    if not stale:
        return state, []
    return {k: v for k, v in state.items() if k not in stale}, stale
```

**c. `TaskGateState`** (`:138`) gains one field, defaulted so every existing
constructor call and consumer keeps working:

```python
    stale_signed: list[str] = field(default_factory=list)
```

**d. `read_task_gate_state`** (`:1660`) — new optional `current_digest`
parameter; demote before deriving the two decisions; keep `current` as the raw
ledger:

```python
def read_task_gate_state(task_file, registry_file=None,
                         current_digest=_COMPUTE_DIGEST) -> TaskGateState:
```

Between `:1680` and `:1681`:

```python
    effective, stale = demote_stale_signed(
        active, registry, current, task_id_from_file(task_file), current_digest)
    archive_decision, archive_pending = _archive_status_from_state(active, effective)
    dep_decision, dep_pending = _dependents_status_from_state(
        active, also_effective, registry, effective)
```

`current` deliberately keeps the raw ledger run (the ledger really does say
`pass` — that is the fact; `stale_signed` is the separate fact that the
signature no longer binds). `status_text` is unchanged. Rewrite the docstring:
the ledger-only caveat becomes "re-validated when a registry AND a digest
channel are available; a caller that passes no registry (the monitor) cannot
classify human gates and is ledger-only by construction — see the drift guard".

**e. `dependents_status`** (`:1311`) — new optional `current_digest`; demote
over the **required** set (so an `also_blocks_dependents: [review_approved]`
entry is re-validated too, not just declared gates):

```python
    required = required_unblock_gates(active, also_effective, registry)
    state = derive_gate_runs(text)
    effective, _stale = demote_stale_signed(
        required, registry, state, task_id_from_file(task_file), current_digest)
    return _dependents_status_from_state(active, also_effective, registry, effective)
```

Docstring: add the stale-signature rule and the cost bound — the lazy default
means git runs only for a task that carries a stamped witness, so `ait ls` pays
W×3 git subprocesses for W signed tasks, not N.

**f. `compact_gate_summary`** (`:341`) — count `state.stale_signed` out of the
pass total into its own segment: `"3/4 pass, 1 stale"`. Inert for the monitor
(which never populates the field) until a caller supplies a registry.

**g. `archive_status_from_text`** (`:1583`) — docstring only: replace the cost
rationale with the two contract reasons (pure-text twin; trail `input_digest`
stability), and point at the drift guard by test-file name.

### 2. `.aitask-scripts/lib/gate_orchestrator.py`

- `Engine._read_state()` (`:346-348`) — replace the inline `del state[g]` loop
  with `state, _ = gl.demote_stale_signed(active, self.registry, state, self.task_id, self.digest)`.
  Behaviour-identical; it stops a second copy of the demotion existing.
- `unlocked()` (`:494`) — call `parse_gate_run_blocks(text)` **once** (it is
  currently called twice, `:503` and `:504`), then demote before
  `compute_unlocked`. Docstring flips from "LEDGER-ONLY … a gate whose signature
  has gone stale is still reported satisfied here" to "re-validates the
  signature, exactly as `Engine._read_state` does, so `ait gates unlocked`
  cannot disagree with `ait gates run`".

### 3. `.aitask-scripts/board/aitask_board.py`

- `TaskManager.__init__` (near `:1145`): `self.gate_digest_cache = _DIGEST_UNSET`
  (module-level `_DIGEST_UNSET = object()`).
- `clear_gate_cache()` (`:1524`): add `self.gate_digest_cache = _DIGEST_UNSET`.
- New `code_digest_for_refresh()` mirroring `gate_registry()` (`:1529`) —
  memoized per refresh cycle, fails closed to `None` (unverifiable → accept).
- `gate_state_for()` (`:1550`): pass `current_digest=self.code_digest_for_refresh`
  — the **bound method**, so the digest is computed at most once per refresh and
  only if some task has a stamped witness.
- `_inflight_item_for()` (`:1663`): new branch **before** the `ALL_PASS` one:

  ```python
  elif state and state.stale_signed:
      group = "human"
      next_action = "awaiting re-sign: " + ", ".join(state.stale_signed)
  ```

  (`archive_decision` already flips to `BLOCKED` from 1d, so the `ALL_PASS`
  branch stops firing; this branch is what tells the user *why*.)
- `_gate_summary()` (`:1595`): render a stale gate as
  `⚠ review_approved:pass (stale signature)` instead of its ledger icon.
- `InFlightItem` (`:98`): add `stale_signed: list[str] = field(default_factory=list)`
  and populate it.
- `_human_pending_gates()` (`:1610`) stays **unchanged** — it reports ledger
  truth; the stale set is its own distinct state (the chosen UX).

### 4. `.aitask-scripts/aitask_gate.sh`

`cmd_deps_unblock` comment block (`:560-566`) — the claim "low-frequency
decision (only on `ait ls`…)" is wrong (it is one subprocess *per gated task*
per `ait ls`). Correct it, and state that the decision now re-validates a
code-bound signature with the lazy pre-filter bound. Update the `deps-unblock`
help lines (`:20`, `:1184`).

### 5. Tests

**a. `tests/test_gate_stale_witness_parity.sh`** (new) — a git fixture with a
gitignored witness dir, modelled on `tests/test_gate_orchestrator.sh` Test 9d
(`:455-520`). Seed: `active_gates: [review_approved]`, ledger `pass`, witness
stamped with the current digest. Then mutate a code file and assert **all three
fixed surfaces flip**, each asserted *before* anything re-pends the ledger so
only the overlay can produce the result:

| surface | before mutation | after mutation |
|---|---|---|
| `aitask_gate.sh deps-unblock <id>` | `SATISFIED` | `BLOCKED:review_approved` |
| `gate_orchestrator.py unlocked <file>` | (empty) | `review_approved` |
| `read_task_gate_state(file, registry)` | `ALL_PASS`, `stale_signed == []` | `BLOCKED`, `stale_signed == ["review_approved"]` |

Plus the discriminating negative case (t1409's Test 9c constraint): a satisfied
human gate with a `signal_target` but **no witness** — the attended-recorded
pass — must stay `SATISFIED` / unlocked-empty / `ALL_PASS` on all three.

**Negative controls, one mutation at a time** (each surface has its own
enforcement point, so a combined revert would mask a broken one — the exact
trap t1409 hit): revert the demotion in `unlocked()` alone, in
`read_task_gate_state` alone, and in `dependents_status` alone, and record that
each produces failures in **exactly** its own surface's assertions.

**b. `tests/test_gate_stale_signed_unit.py`** (new) — closes the gap that
`stale_signed_gates` has **no direct unit test** anywhere in `tests/`. Covers
the four digest states, and pins the laziness contract with a call-counting
provider: `provider_calls == 0` when no stamped witness exists, `== 1` when one
does (never per-gate).

**c. `tests/test_board_gate_digest_budget.py`** (new) — a `code_digest`
call-counting spy over board refreshes (pattern:
`tests/test_board_render_scoping.py:355-447`, including its discard-boot-spawns
and anti-vacuity steps):

- **Within one refresh:** **0** calls when no task has a stamped witness, and
  **exactly 1** across a refresh that renders many stale-signed tasks — asserted
  exactly (never `assertLessEqual`).
- **Across two refreshes — the invalidation contract.** The single-refresh count
  proves the memo works; it says nothing about the memo being *dropped*. A
  process-lifetime digest is strictly worse than a per-task cache miss: it makes
  a stale approval read valid (or a fresh one read stale) until the board is
  restarted. So: refresh #1 with a witness stamped against the current code →
  the in-flight row reads `all gates pass — archive/re-enter` and `stale_signed`
  is empty; **mutate a code file between the refreshes**; refresh #2 → the digest
  is recomputed (spy count goes 1 → 2, not 1 → 1) **and the verdict flips** to
  `awaiting re-sign: review_approved`. Then re-sign and run refresh #3 to assert
  it flips back — proving the memo tracks the digest in both directions rather
  than latching.
- **Invalidation-path coverage.** Drive both refresh entry points that clear the
  cache (`load_tasks:1343` and `refresh_board:7739`) and assert each recomputes,
  so the memo is not silently correct on only one of them. `clear_gate_cache()`
  is the sole invalidation point for the existing `gate_state_cache` too, which
  is precisely why the digest must not acquire a second, independent lifetime —
  the test pins them to the same one.
- Plus the render assertion that a stale-signed in-flight row reads
  `awaiting re-sign: review_approved` and that `_gate_summary` marks it
  `⚠ review_approved:pass (stale signature)`.

**c2. Digest-failure behaviour at each changed public surface** (added to §5a's
fixture and §5b): `code_digest()` returning `None` (git absent / no commits) is
the documented *unverifiable → accept* policy, but until now it was only
exercised inside the classifier. Each of the three newly-changed surfaces gets an
explicit case, driven through the documented seam (a non-git fixture directory,
which is how `tests/test_gate_orchestrator.sh:13` and `test_gate_verifiers.sh:15`
already force `code_digest() -> None`) rather than a test-only override:

| surface | with an unverifiable digest |
|---|---|
| `read_task_gate_state(file, registry)` | `archive_decision == "ALL_PASS"`, `stale_signed == []`, no exception |
| `gate_orchestrator.unlocked(file)` | same set as the ledger-only result today, no exception |
| `dependents_status(file, registry)` | `SATISFIED`, no exception |

Plus the same three with a digest **provider that raises**: the board's
`code_digest_for_refresh()` is total (catches `Exception` → `None`, mirroring
`gate_registry()` at `aitask_board.py:1533-1538`), so a raising provider must
never escape to the TUI — asserted at the board surface, not just the helper.
`_resolve_digest` itself deliberately does **not** swallow: a provider is a
caller's object and making it total is the caller's job, so a bug there stays
visible instead of being silently reinterpreted as "unverifiable".

**d. `tests/test_gate_ledger_only_surfaces.py`** (new) — the drift guard, Family
B (AST + frozen registry), modelled on `tests/test_board_persistence_seam.py:490-593`:

- `LEDGER_ONLY_CONSUMERS` — a frozen `{(file, enclosing_function): reason}` map
  registering exactly the ratified sites: `stats_data.collect_inflight`,
  `trail_gather._gates_pending`, `monitor_core.GateSummaryCache.summary_for`.
- Scanner walks every `.aitask-scripts/**/*.py` for calls to
  `archive_status_from_text` / `_archive_status_from_state`, and for calls to
  `read_task_gate_state` **with no registry argument** (the by-construction
  ledger-only shape), resolving the enclosing function via a parent map.
  **Fails closed**: an unresolvable receiver or an unparsable file yields an
  `UNANALYSABLE:` marker that can never compare equal, and a parse error
  **raises** rather than skipping.
- **Alias detection — the guard must not have the hole it is guarding.** A
  call-name-only scanner misses `f = archive_status_from_text; f(text)`, which
  would make the "cannot silently grow" claim false. So the scan also treats a
  **re-binding of any watched name as a finding in its own right**, whatever it
  is later called through:
  - `from gate_ledger import archive_status_from_text as <alias>` and
    `import gate_ledger as <alias>` where the alias is not the conventional
    `gate_ledger` / `gl`;
  - any assignment whose value is a watched `ast.Name` or
    `<module>.<watched attr>` (`f = archive_status_from_text`,
    `f = gate_ledger.read_task_gate_state`), including tuple targets;
  - passing a watched name as a bare argument (`map(archive_status_from_text, …)`,
    `functools.partial(archive_status_from_text, …)`) — i.e. any use of the name
    in a non-`Call.func` position.

  Each such binding is reported as `ALIAS:<file>:<line>:<name>` and must be
  registered like a call site, so aliasing is *visible and reviewed* rather than
  invisible. This makes the residual boundary genuinely narrow: only a name
  reached through a data structure (`getattr(gate_ledger, name)`, a dict of
  callables) escapes — and `getattr` on the gate modules is itself flagged.
- **Paired production convention** (a guard plus the rule it enforces, since a
  scanner alone is a claim about syntax, not about intent). State in
  `archive_status_from_text`'s and `read_task_gate_state`'s docstrings and in
  `aidocs/gates/gate-guarded-archival.md`: *these functions are called directly,
  never aliased or indirected — the ledger-only/re-validated split is enforced by
  a syntactic guard, and an indirection defeats it.* The guard's failure message
  cites the convention, so a deviation arrives as a review conversation with a
  named rule rather than as a mysterious red test.
- `assertEqual(scan(), LEDGER_ONLY_CONSUMERS)` — exact, both directions.
- Anti-vacuity: assert the scan found ≥1 call site **and** that the alias pass is
  live (a synthetic alias in a temp copy is detected) — an alias check that never
  fires is indistinguishable from one that is broken.
- Negative controls over **temp copies** of real source: (a) a new ledger-only
  consumer injected → caught; (b) the same consumer reached through an alias →
  caught by the alias pass, which is the control that proves concern-3 is closed
  rather than merely documented.
- Failure message names all three remedies: *pass a registry + digest so the
  surface re-validates; register it here with a reason; or — if you aliased —
  call it directly per the convention.*
- Documented scope boundary (now narrow, and stated honestly): `tests/` is not
  scanned, and a watched function retrieved dynamically from a data structure at
  runtime is not statically decidable — `getattr` against the gate modules is
  flagged so the undecidable case surfaces rather than passing silently.

### 6. Docs

- `aidocs/gates/gate-guarded-archival.md:93-101` — replace the "Deliberately
  ledger-only surfaces" paragraph (which currently ends "Closing that gap with a
  once-per-refresh digest is tracked separately") with the **decided** split
  table above, naming the drift guard as the enforcement and the two ratified
  surfaces with their contract reasons.
- `aidocs/gates/dependency-unblock-semantics.md` — extend the unblock criterion
  (`:56-66`) with the stale-signature rule: a required gate that is
  ledger-`pass` but code-stale counts as **not** satisfied, since
  `review_approved` / `merge_approved` are precisely the code-bound gates flagged
  `blocks_dependents: true`.
- `aidocs/gates/aitask-gate-framework.md` — the re-validation now runs on the
  introspection and TUI read paths too, not only `gates run` + `archive-ready`.

## Verification

**Gate 0 — the pre-phase cost probe must pass its declared thresholds before any
surface is changed.** If `ait ls` regresses >10% or the board does more than one
`code_digest()` per refresh at W=50, stop and re-plan (fallback named in the
pre-phase), rather than proceeding and reporting the projection.

Negative control **first** — each new assertion must fail against unfixed code,
one mutation at a time (§5a), before the fix is applied.

```bash
bash tests/test_gate_stale_witness_parity.sh          # new, the regression
bash tests/test_gate_orchestrator.sh                  # 9c/9d must stay green
bash tests/test_dependency_unblock.sh                 # incl. the :111 shell/python parity
bash tests/test_gate_guarded_archival.sh
bash tests/test_gate_active_gates.sh
bash tests/test_gate_cli_wiring.sh
bash tests/test_gate_pass.sh
bash tests/test_gate_reentry.sh
bash tests/test_gate_verifiers.sh
bash tests/test_query_files_inflight.sh
bash tests/test_gates_reference_drift.sh
bash tests/run_all_python_tests.sh                    # incl. test_gate_stale_signed_unit.py,
                                                      # test_board_gate_digest_budget.py,
                                                      # test_gate_ledger_only_surfaces.py
shellcheck .aitask-scripts/aitask_gate.sh
```

Python modules specifically at risk and individually checked: the
`archive_status_from_text` ↔ `archive_status(no registry)` parity assertion
(`tests/test_gate_ledger_python_parser.py:226` — must stay true, since neither
is changed), and the two monitor disk-read counters
(`tests/test_monitor_gate_cache.py`, `tests/test_monitor_gate_summary.py` — must
stay at their current counts, proving the monitor really is untouched).

Live end-to-end in a throwaway git fixture, mirroring t1409's repro but on the
newly-fixed surfaces: `ait gate pass <id> review_approved`, touch a code file,
then confirm `ait ls` keeps the dependent blocked, `ait gates unlocked <id>`
lists `review_approved`, and the board's In-Flight view reads
`awaiting re-sign: review_approved` instead of `all gates pass —
archive/re-enter`.

Also run the live fixture **twice with a code change in between**, with the board
left open across both refreshes — the one shape a single-refresh assertion cannot
see, and the failure mode (a digest pinned for the process lifetime) that would
otherwise only show up after hours of use.

Board budget: `tests/test_board_gate_digest_budget.py` pins **exactly** one
`code_digest()` per refresh **and** that a second refresh after a code change
recomputes it and flips the verdict; measured baseline for the call itself is
~9 ms.

Step 9 (Post-Implementation) handles merge, `ait gates run`, and archival.

## Risk

### Code-health risk: medium
- `Engine._read_state()`'s inline demotion is replaced by the shared
  `demote_stale_signed()` — an edit to the **enforcing** path t1409 just fixed,
  where a mistake would stop re-pending stale-signed gates entirely ·
  severity: medium · → mitigation: inline pre-phase guard_enforcing_path_consolidation
- The digest channel grows a fourth state (sentinel | callable | `str` | `None`).
  `None` is a real answer ("unverifiable → accept") and `callable(None)` is
  `False`, so the check order in `_resolve_digest` is load-bearing; a mis-ordered
  branch would silently turn "unverifiable" into "compute" · severity: medium ·
  → mitigation: covered in-plan (§5b, the four-state `_resolve_digest` unit test
  with a call-counting provider)
- The board gains a process-lifetime memo whose only invalidation is
  `clear_gate_cache()` — which has exactly two callers (`load_tasks:1343`,
  `refresh_board:7739`) while `_rerender_trail` deliberately skips several
  sibling refresh steps. A missed invalidation path would pin one digest for the
  process lifetime, making a stale approval read valid (or a fresh one read
  stale) until restart · severity: medium · → mitigation: covered in-plan (§5c,
  the **two-refresh** test: code mutated between refreshes, digest recomputed
  **and** verdict flipped, then flipped back on re-sign, driven through both
  invalidation entry points)
- Blast radius spans a load-bearing shared module (`gate_ledger.py`), the
  orchestrator, a ~7k-line TUI, one shell verb, 4 new test modules and 3 design
  docs · severity: medium · → mitigation: inline pre-phase guard_enforcing_path_consolidation
- The new drift guard could overclaim or pass vacuously — in particular a
  call-name-only scanner would miss an aliased consumer, making the "the split
  cannot silently grow" claim false · severity: medium · → mitigation: covered
  in-plan (§5d, the alias pass reporting every re-binding of a watched name, its
  own anti-vacuity assertion, an aliased-consumer negative control, and the
  paired documented call-directly convention)

### Goal-achievement risk: low
- The split is decided per surface from read source and measured cost, and the
  three-way shape was confirmed with the user before planning · severity: low
- **Deliberate narrowing:** the monitor / minimonitor compact gate column stays
  ledger-only (no registry passed; `(mtime_ns, size)` cache key; cross-project
  cwd), so that one badge can still disagree with the enforcing decision. The
  two surfaces t1409's risk actually named — board and `ait ls` — are both
  fixed · severity: low · → mitigation: monitor_stale_gate_column_parity
- No repo currently writes `.signed` witnesses, so the new behaviour is proven
  by synthetic fixtures and one live end-to-end run rather than by production
  use; the per-task cost bound (W×3 git subprocesses for W signed tasks; ≤1
  digest per board refresh) is reasoned, not measured under load ·
  severity: medium · → mitigation: inline pre-phase witness_heavy_cost_probe
- The digest-failure path (`code_digest() -> None`, git absent / no commits) is
  the documented *unverifiable → accept* policy but is now exposed through three
  new public surfaces (board, `gates unlocked`, dependency unblocking), where an
  unhandled failure would crash a TUI or falsely block dependents ·
  severity: low · → mitigation: covered in-plan (§5c2, per-surface
  unverifiable-digest and raising-provider cases driven through a non-git fixture)

### Planned mitigations
- timing: pre-phase | name: guard_enforcing_path_consolidation | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — the `_read_state` consolidation touches the enforcing path t1409 just fixed | desc: Land the `_read_state` → `demote_stale_signed` consolidation as an isolated first edit, with `test_gate_orchestrator.sh` 9/9c/9d captured as a baseline before it and re-run immediately after.
- timing: pre-phase | name: witness_heavy_cost_probe | type: performance | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health / goal-achievement — the per-task cost bound is reasoned, not measured, and the task requires measuring before committing to the design | desc: Measure `ait ls` and one board refresh against a ~50-task fixture where every task carries a stamped witness, BEFORE finalizing the design, against declared thresholds with a named fallback (cross-process digest threading via an explicit `--code-digest` argument).
- timing: after | name: monitor_stale_gate_column_parity | type: enhancement | priority: low | effort: medium | inline_risk: high | added_complexity: medium | addresses: goal-achievement — the monitor / minimonitor compact gate column stays ledger-only | desc: Bring the monitor compact gate column into signature parity, deciding the GateSummaryCache key question (adding the digest re-opens the t1111_1 per-tick-clear optimization) and the cross-project cwd resolution of the witness path.

**Reassessment after inlining:** both inline phases are separable, bounded
pre-work — a baseline test run and a measurement pass with declared thresholds.
The cost probe moving *ahead* of implementation (per review) means the design can
still be re-planned before any surface is changed, which lowers goal-achievement
risk. Levels: code-health **medium**, goal-achievement **low**.

## Out of scope (recorded, not silently dropped)

- **`ait ls` is 12.5 s here**, essentially all of it `aitask_ls.sh:184-196`
  spawning one `aitask_gate.sh deps-unblock` subprocess (47 ms) per gated task
  — 307 of them. Pre-existing and independent of this change; a batched
  `deps-unblock` verb would collapse it to one process (and would make the
  digest free as a side effect). Recorded as an upstream defect for a follow-up
  task at Step 8b.
- **Monitor / minimonitor compact gate column** — ratified ledger-only with
  reasons (see Context) and registered in the drift guard; revisiting it means
  putting the digest in the `GateSummaryCache` key, which undoes t1111_1.
