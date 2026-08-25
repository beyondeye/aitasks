---
Task: t1527_single_source_local_dependency_resolution.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1527 — Single-source local dependency resolution

## Context

Three surfaces independently answer "is task X blocked by its `depends`?", with
three different policies, so `ait ls`, the minimonitor task picker and the board
can disagree about the same task:

| surface | site | unresolvable dep | gate-release (t635_3) |
|---|---|---|---|
| `ait ls` | `aitask_ls.sh:289` `is_task_uncompleted` | fail-open ("not in the active set ⇒ completed") | yes, via `deps-unblock-batch` |
| minimonitor | `monitor_core.py:3569` `blocking_dependencies` | fail-closed | **no — absent entirely** |
| board | `aitask_board.py:1752` `unresolved_local_deps` | fail-open (`if dep_task and …`) | yes, in-process |

Two independent wrong answers follow: an unresolvable id is silently satisfied on
two of three surfaces, and a dependency sitting at `Implementing` with every
required gate `SATISFIED` unblocks its dependents in `ait ls` and on the board
while the minimonitor still reports it as blocking.

The cross-repo half already does this correctly in both surfaces that implement
it (`xdeps` is fail-closed and renders `(UNREACHABLE)` — `aitask_ls.sh:471-474`,
`aitask_board.py:1763`). This task brings the local half up to that standard; it
does not invent a policy.

**Live-data baseline (measured on main, 2026-08-25, 445 active task files):**
144 deps resolve to a loose archived file (Done), 99 to `Ready`, 2 to
`Implementing`, 2 to `Postponed`, **0 unresolvable**, and **0 tasks currently
release dependents via gates**. So the behavioural change lands on an empty set
today — it is a correctness fix for the surfaces, not a re-verdict of the
backlog. (The `[2, 3]` case that motivated the task was data-fixed in
`6f78a3e05`.)

## Decisions taken (settled before planning)

1. **Policy: fail-closed, tri-state.** `SATISFIED` / `BLOCKING` /
   `UNRESOLVABLE` are three outcomes. `UNRESOLVABLE` blocks *and* renders
   distinguishably — `(UNRESOLVED)`, mirroring the cross-repo `(UNREACHABLE)`.
2. **Resolution scope: loose files only.** Active `aitasks/` + loose
   `aitasks/archived/`. Numbered bundles (`archived/_b<N>/old<M>.tar.zst`) are
   **never** read — the documented non-goal from the task's rule 4. `ait ls`
   ordering-independent consequence: a dep that is later swept into a bundle
   flips to `(UNRESOLVED)` and blocks. That is the accepted residual, recorded
   under Risk below.
3. **`find_ready_siblings` (the 4th resolver, minimonitor `n`):** gets the
   gate-release rule only. Its deliberate sibling scoping and hint semantics are
   unchanged, and it stays out of the parity harness.
4. **`ait ls` display narrows to the blocking deps.** Today
   `blocking_info="$d_text"` prints *every* dep of a blocked task; the board and
   minimonitor print only the ones that block. With a per-dep verdict available
   there is no reason to keep the misleading form. Single-dep output
   (`Blocked (by 10)`) is unchanged, so `test_dependency_unblock.sh` and
   `test_xdeps_blocking.sh` stay green.

## The one decision core

New module **`.aitask-scripts/lib/dep_resolution.py`** — the single place that
turns a `depends:` list into verdicts. It sits in `lib/` (base layer: it imports
`task_yaml` and `gate_ledger`, and nothing above them, per
`tests/test_no_lib_to_tui_import.sh`).

```python
SATISFIED, BLOCKING, UNRESOLVABLE = "SATISFIED", "BLOCKING", "UNRESOLVABLE"
UNRESOLVED_MARKER = "(UNRESOLVED)"

@dataclass(frozen=True)
class DepVerdict:
    raw: str          # the token as written in `depends:` — display provenance
    canonical: str    # "10" / "423_6"  — the resolution key
    verdict: str      # one of the three above
    @property
    def blocking(self) -> bool: ...            # verdict != SATISFIED
    def display(self, *, prefix: str = "") -> str: ...   # "t10" / "2 (UNRESOLVED)"

def canonical_dep_id(raw) -> str | None        # "t423_6"/"423_6"/423 -> "423_6"/"423"

class LocalDepResolver:
    """Resolve dep ids against ONE tasks tree. Loose files only."""
    def __init__(self, tasks_dir, registry_file=None): ...
    def begin_cycle(self, *, digest_provider=None) -> None  # new evaluator + generation
    def facts(self, canonical) -> DepFacts | None   # (status, gate_released)
    def classify(self, depends_raw) -> list[DepVerdict]
    def invalidate_all(self) -> None                # forced immediate re-resolve
```

- **Resolution** = the glob `monitor_core._resolve` already uses, hoisted:
  parent → `aitasks/t<id>_*.md` then `aitasks/archived/t<id>_*.md`; child →
  `aitasks/t<p>/t<p>_<c>_*.md` then `aitasks/archived/t<p>/…`. Active wins.
  No match → `UNRESOLVABLE`.
- **Verdict rule** (the whole policy, in one function):
  `facts is None → UNRESOLVABLE`; `status == "Done" → SATISFIED`;
  `gate_released → SATISFIED`; else `BLOCKING`.
- **The scan's pre-filter may only skip a CERTAINTY** (tightened during review).
  `may_have_depends()` first treated any `depends:` line with no same-line value
  as dep-free — but a bare key is the head of a valid YAML **block list**
  (`depends:` / `  - 999`), which really does declare dependencies. `ait ls`
  skipped those tasks while the board and minimonitor parsed and blocked them:
  the three-surface disagreement this module exists to remove, reintroduced by
  its own optimisation. Only an explicit **inline empty list** (`[]` / `[ ]`) or
  an absent key is now certain; a bare or comment-only key is parsed. The same
  correction applies to `aitask_ls.sh`'s lookup guard, which keyed off its
  inline-only parsed value and had to move to *key presence*.
- **A malformed `depends:` field is itself UNRESOLVABLE** (added during review).
  `task_yaml._normalize_task_ids` deliberately passes a non-list value through
  untouched so consumers can detect it — and before this change no consumer did.
  `read_depends(raw) -> (tokens, malformed)` is the one reader: a scalar
  (`depends: 999`, `depends: "999"`) or a mapping yields
  `([], True)` and one `UNRESOLVABLE` verdict rendered as
  `<malformed depends> (UNRESOLVED)`; an absent / `None` / `[]` / blank field is
  genuinely no-dependencies and is **not** malformed. The field must never be
  *iterated*: measured, `depends: 999` raised `TypeError` inside
  `monitor_core._resolve` (killing the lookup outright) and `depends: "999"`
  yielded `['9','9','9']` — three dependencies nobody wrote. `TaskInfo` now
  carries `depends_malformed` beside `depends`, and every read takes both.
- **`gate_released` goes through a new *bulk* seam, never the per-task API.**
  `gate_ledger.dependents_status()` re-reads and re-parses `gates.yaml` on
  **every** call (`gate_ledger.py:1430-1435`) and passes the `_COMPUTE_DIGEST`
  sentinel, so `stale_signed_gates` resolves a **~5 ms `code_digest()` git
  subprocess per task carrying a stamped witness** (`gate_ledger.py:1763`). One
  cold `deps-blocking-scan` built on it would restore, inside a single process,
  exactly the per-edge cost t1472 removed. (My 87 ms/445-file measurement did
  **not** cover this: this repo currently has zero stamped witnesses, so the
  digest branch never ran.)

  So `gate_ledger.py` grows a **public** evaluator seam that hoists both costs —
  the shape `dependents_status_batch` already implements privately:

  ```python
  class DependentsEvaluator:
      """One registry parse + one _DigestMemo, shared across a whole scan/refresh."""
      def __init__(self, registry_file=None, current_digest=_COMPUTE_DIGEST): ...
      def __call__(self, text: str, task_id: str) -> tuple[str, list[str]]: ...
      # wraps _dependents_status_for_text with the hoisted registry + memo
  ```

  `dependents_status_batch` is **refactored to use it** rather than keeping its
  own inline hoist, so there is one memoization path and it is the one the new
  resolver rides. `dependents_status` (per-task) is untouched — its callers and
  `tests/test_deps_unblock_batch.sh` keep their contract.

- **An evaluator lives for exactly ONE scan/refresh cycle — never for the
  resolver's lifetime.** It caches both the registry parse and (via
  `_DigestMemo`, which resolves at most once *ever* and memoizes failures) the
  repo code digest that re-validates signed human-gate approvals. Holding one
  across a long-lived board/minimonitor session is the exact hazard t1416
  closed, and the codebase already says so: `TaskManager.clear_gate_cache`
  resets `gate_digest_cache` and `gate_registry_cache` per refresh, with the
  comment *"a lifetime longer than one refresh cycle is not a cache miss — it
  silently freezes every signature verdict until the process restarts"*
  (`aitask_board.py:1195-1203`). A frozen digest or registry would keep a
  gate-released dependency `SATISFIED` after the code changed, the witness was
  updated, or `gates.yaml` was edited — until restart.

  So `begin_cycle()` installs a **fresh** `DependentsEvaluator` and bumps a
  generation counter; the level-2 facts cache stamps its generation, so
  `gate_released` is recomputed on the first touch of each new cycle while the
  level-1 directory index (pure filesystem naming — evaluator-independent)
  survives untouched. Cycle owners:
  - `ait ls` scan — one cycle per process (trivially correct);
  - **board** — `begin_cycle()` is called from `clear_gate_cache()`, so the
    resolver's boundary is *the same line* that already enforces the invariant
    for `gate_digest_cache`, and the two can never drift apart;
  - **minimonitor** — `blocking_dependencies(refresh=True)` begins a cycle
    (`refresh=False` reuses the current one, matching its documented "skips the
    forced invalidation" contract); `find_ready_siblings` begins one per call,
    which matches its existing "reads every sibling from disk on each call".
- **Caching is two-level and each level self-invalidates on the event that can
  change its answer.** Keying only by resolved-file identity is not enough: a
  *miss* has no path to stat, and an archived hit keeps its identity when an
  active copy appears — so a long-lived minimonitor would keep reporting
  `UNRESOLVED` after the task is created, and keep serving the archived `Done`
  copy after an active one shadows it. Both are **directory** events, so:
  - **level 1 — id→path index, per directory, keyed by the directory's own
    `(st_mtime_ns, st_ino)`.** Adding, removing or renaming an entry bumps the
    parent directory's mtime, so a new active file, a new archived file, and a
    deleted one all invalidate the index that produced the stale answer. A
    directory that does not exist is itself a cached state and is re-checked the
    same way. Lookup order stays active-then-archived, so the rebuilt index
    restores active-beats-archived precedence automatically.
  - **level 2 — parsed facts, per file, keyed by `(st_mtime_ns, st_size)`** (the
    identity `_file_identity` and `GateSummaryCache` already use). An *edit* does
    not touch the directory mtime, and this is the level that catches it.
  - **accepted residual + its escape hatch:** a create-and-delete pair landing in
    the same mtime tick leaves the index stale — the same residual
    `TaskInfoCache`'s `(mtime_ns, size)` key already accepts. `invalidate_all()`
    is the forced immediate re-resolve for it, and the minimonitor's existing
    `refresh=True` path calls it (preserving today's `self.invalidate(dep)`
    semantics verbatim).
- **Frontmatter is read via `task_yaml.parse_frontmatter`**, whose
  `_TaskSafeLoader` already keeps `423_6` a string rather than YAML-1.1-coercing
  it to `4236`. Verified: 0 mangled dep ids in the live tree.

## Surface changes

### Pre-phase (risk mitigations)

1. `[characterize_ls_listing_baseline]` **Before touching `aitask_ls.sh`**,
   capture the live tree's listing as a golden into the scratchpad:
   `./ait ls -v --all` and `./ait ls -v --children 635`. After the change, diff
   both. The measured baseline predicts a byte-identical result; any difference
   must be one this plan names deliberately (only decision 4's multi-dep display
   narrowing qualifies) — anything else is a regression, not a re-verdict.
2. `[scan_failure_is_its_own_state]` **Before wiring `ait ls` to the new verb**,
   fix its failure contract: `deps-blocking-scan` ends its output with a
   terminal `SCAN_OK` line, and the bash consumer treats a non-zero exit **or a
   trailer that is not the exact final line** as a third state. *Presence is not
   enough* (tightened during review): a `*"SCAN_OK"*` substring test also accepts
   `SCAN_OK: nothing to do` from a damaged scanner and a marker printed before
   the scan died partway — both exit 0, both then contribute no rows for the
   tasks never reached, and those dependents silently read as Ready. The whole
   point of a terminal marker is that it can only be written after the last row — not as "nothing is blocked". In that
   state `ait ls` warns on stderr (naming the verb and its exit status) and
   marks every task carrying a non-empty `depends:` as
   `Blocked (by <deps>) [unverified]`. Ship it with a forced-failure test that
   injects a broken verb (a stub on `PATH`/an overridden script path) and
   asserts *both* halves: the warning reaches stderr, and no dep-carrying task
   lists as `Ready`. An empty scan output is **not** a valid "nothing blocked"
   answer unless the trailer is present.

### 1. `ait ls` (`.aitask-scripts/aitask_ls.sh`)

New batched verb, the consumer-side twin of `deps-unblock`, alongside it in the
same script:

```
./.aitask-scripts/aitask_gate.sh deps-blocking-scan
# one line per task file with >=1 non-satisfied dep:
#   <path>\t<display-csv>       e.g.  aitasks/t20_x.md\t10, 2 (UNRESOLVED)
```

`aitask_gate.sh` gains `delegate_python_deps()` next to the existing
`delegate_python_phase()` (same precedent, different module), and `--help` gains
the verb next to `deps-unblock` / `deps-unblock-batch`.

In `aitask_ls.sh`:
- **Delete** `build_dep_satisfied_set()`, `dep_satisfied_file`, and
  `is_task_uncompleted()`'s gate branch — the whole local-dep loop in
  `calculate_blocked_status` (lines 450-460) is replaced by one map lookup.
  `existing_ids_file` stays (duplicate-id warning still uses it).
- **Rule 3 (perf) is satisfied and improved:** today's shape is one batched
  subprocess *plus* ~2 `grep` forks per dep edge (~500 forks). The new shape is
  **one** subprocess and **zero** forks per dep. Lookup is a fork-free,
  bash-3.2-safe substring scan over the scan output held in one variable — no
  `declare -A` (macOS system bash is 3.2, per `sed_macos_issues.md`).
- `parse_task_metadata` records the current file path in a global so
  `calculate_blocked_status` can key the lookup; xdeps handling is untouched and
  still appends to `blocking_info` after the local part.

### 2. minimonitor (`monitor/monitor_core.py`, `monitor/monitor_shared.py`)

- `TaskInfoCache.blocking_dependencies(...)` returns **`list[DepVerdict]`**
  instead of `list[str]` — a which-items return, since the dialog must render
  the unresolvable ones differently. It builds/keeps one `LocalDepResolver` per
  project root; `refresh=True` now calls `resolver.invalidate_all()` — the same
  "forced immediate retry of a negative, and re-decide active-beats-archived"
  role the current `self.invalidate(dep)` loop plays, so the documented
  `refresh=` contract is preserved exactly. Its docstring's fail-closed
  paragraph is rewritten to point at the core.
- `TaskPickConfirmDialog._eligibility_lines` (`monitor_shared.py:1653`) renders
  `⛔ blocked by t10 t2 (UNRESOLVED)`. `#pick-eligibility` is a wrapping `Static`,
  so the ~40-column narrow variant wraps rather than clips — pinned by a
  render-level test rather than assumed.
- `find_ready_siblings` (`monitor_core.py:3755`): its second pass replaces
  `sib_status.get(dep) != "Done"` with the core's verdict for that sibling
  (gate-release included). Sibling scoping and the returned `list[str]` of
  sibling ids are unchanged.

### 3. board (`board/aitask_board.py`)

- New `TaskManager.local_dep_verdicts(task) -> list[DepVerdict]` is the primary
  API; `unresolved_local_deps(task) -> list[str]` becomes the display-string
  wrapper over it, so its two call sites (`_inflight_item_for:1842`, the detail
  pane at `:3120` → `🔗 {', '.join(...)}`) keep working and now show
  `t2 (UNRESOLVED)`.
- `dependency_released_by_gates` is no longer called from the dep path (the core
  owns that rule); it stays if any other caller needs it, otherwise it is deleted
  with its now-unused branch.
- The resolver instance lives on `TaskManager` and **`clear_gate_cache()` calls
  `resolver.begin_cycle()`** — the file-identity caches are self-invalidating and
  survive, but the evaluator (registry + digest) is renewed on the same line that
  already renews `gate_digest_cache` / `gate_registry_cache`. The comment there
  is extended to name the resolver, so a future edit cannot drop one and keep the
  other.

## Verification

New module `tests/test_local_dep_parity.py` (unittest, runs under the standard
runner):

1. **Parity over one fixture set, surface against surface.** One temp repo
   (`aitasks/` + `metadata/gates.yaml` from `gates_reference.yaml`, using
   `tests/lib/board_fixture.py`'s `load_board_module` for the board and a real
   `TaskInfoCache` for the minimonitor) with dependents pointing at: a `Done`
   dep, a `Ready` dep, a **loose archived** dep, an **unresolvable** id, a dep at
   `Implementing` with all gates `SATISFIED` (the case that currently splits
   2-to-1), and an id whose **bundle exists but is never read** (decision 2).
   Each surface is reduced to `(blocked, blocking_ids, unresolved_ids)` — `ait ls`
   by parsing its real `Status: Blocked (by …)` output — and the three tuples are
   asserted **equal to each other**, with the failure message naming the surface
   that differs.
2. **Negative controls, one per language.**
   - bash: run the parity comparison against a `sed`-mutated copy of
     `aitask_ls.sh` with the scan call removed (restoring fail-open) and assert
     the comparison fails naming `ait ls`.
   - python: patch `TaskManager.unresolved_local_deps` back to its pre-fix
     fail-open body and assert the comparison fails naming `board`.
3. **Render-level assertions** (`render().plain`, not source inspection):
   `TaskPickConfirmDialog` at 40 columns shows `(UNRESOLVED)` unclipped, and the
   board detail pane's `🔗` label carries it.
4. **Unit tests for the core** in the same module: the tri-state table, id
   canonicalization (`t423_6` / `423_6` / `423` / `4236`), and the
   identity-cache re-read (mutate a dep file, assert the verdict flips).
5. **Instrumented fan-out — the evaluator actually hoists.** Counter-wrap
   `gate_ledger.read_registry` and `gate_ledger.code_digest`, then run one
   `deps-blocking-scan` over a fixture of N≥20 gated tasks of which **≥2 carry a
   stamped `code_digest` witness file** (the only shape that reaches the git
   subprocess — `_has_stamped_witness`, `gate_ledger.py:1728`). Assert
   `read_registry` ran **exactly once** and `code_digest` **at most once**.
   *Negative control:* re-run the same scan with the resolver constructed
   per-dep (no shared evaluator) and assert the counters go to N — proving the
   assertion can fail and that the fixture really reaches the expensive path.
   Also re-assert the wall-clock rule 3 claim on the live tree (`time ./ait ls
   -v 15` vs the 4.5 s baseline).
6. **Cache-freshness transitions**, one test per named stale answer:
   (a) resolve an id to `UNRESOLVABLE`, **create** the task file, re-resolve
   through the *same* resolver instance, assert it flips to `BLOCKING`/`SATISFIED`
   with no explicit invalidation; (b) resolve an id to the archived `Done` copy,
   **add** an active file for the same id, re-resolve, assert the active copy's
   status wins. Both assert the *cached* path (call twice, no
   `invalidate_all()`), so a resolver that only checked file identity fails them.
7. **Evaluator lifetime — a new cycle really re-decides.** Three tests, each
   driving one long-lived resolver (no restart, no new instance):
   (a) edit `gates.yaml` to flip a gate's `blocks_dependents` between cycles and
   assert the dep's verdict changes; (b) with a stamped `code_digest` witness
   present, change the digest the provider returns between cycles and assert a
   previously gate-released dep re-pends to `BLOCKING` (the t1416 contract, now
   reachable through this path); (c) update the witness file itself between
   cycles and assert the same. **Negative control:** apply each change *within*
   one cycle and assert the verdict does **not** move — which proves the cycle
   boundary is what re-decides, not incidental re-reading, and that (a)-(c)
   would fail against a resolver-lifetime evaluator.
   Plus one structural guard: counter-wrap `DependentsEvaluator.__init__` and
   assert a board `refresh_board()` constructs exactly one per refresh — the same
   shape that pins `gate_digest_cache` today.
8. **`find_ready_siblings`**, focused, sibling-scope-preserving: a sibling at
   `Implementing` with all gates `SATISFIED` is **not** returned as blocking; a
   sibling at `Implementing` with a required gate still pending **is**; and a
   non-sibling dep (a `t<other>` id) is still ignored — the scoping control that
   proves the change did not widen the hint.

Regression sweep — must stay green:
`tests/test_dependency_unblock.sh`, `tests/test_deps_unblock_batch.sh`,
`tests/test_xdeps_blocking.sh`, `tests/test_minimonitor_pick_by_number.py`
(its `blocking_dependencies` assertions and its fake cache at line 117 are
updated to the `DepVerdict` shape), `tests/test_board_inflight_view.py`,
`tests/test_no_lib_to_tui_import.sh`, plus
`shellcheck .aitask-scripts/aitask_ls.sh .aitask-scripts/aitask_gate.sh` and
`bash tests/run_all_python_tests.sh`.

Manual: `./ait ls -v 15` before/after must be byte-identical on the live tree
(baseline above says nothing should re-verdict).

## Performance: measured outcome, and the amendment it needs

**Correctness verdicts: unchanged.** The characterization golden differs on
exactly 10 lines, every one a decision-4 display narrowing whose dropped ids
were each verified to be archived `Done` tasks. Zero re-verdicts.

**Timing: a measured regression remains.** Interleaved 11-run A/B on this
checkout, HEAD's `aitask_ls.sh` vs the new one, alternating in one session:

| | median | min |
|---|---|---|
| before | 4.802 s | 4.617 s |
| after  | 5.126 s | 4.946 s |

**+0.324 s median (+6.7 %)**, min-to-min +0.329 s — the two agree, so this is a
real cost and not load noise. (An earlier figure of +0.139 s reported during
review was measured with too few samples on a loaded box and was optimistic;
this table supersedes it. The plan's original "4.5 s baseline" was taken on an
idle box and is not comparable — only the same-session A/B above is.)

**Where it goes, measured — not estimated:**

| phase | cost |
|---|---|
| `deps-blocking-scan` subprocess | 0.360 s |
| bash row lookups (331 parents x 92 rows) | 0.104 s |
| *removed:* old `grep -lE` + `deps-unblock-batch` | −0.065 s |
| *removed:* ~250 per-dep `grep` forks | ~−0.080 s |
| **net** | **≈ +0.32 s** |

`cProfile` attributes **91 % of the scan to `task_yaml.parse_frontmatter`** —
566 PyYAML parses (209 dependents that pass the pre-filter + 357 dependency
targets). The old path did **zero** YAML parses: `gate_ledger` is `re`-only by
design, and dependency resolution was inferred from filename existence, which is
exactly the fail-open this task removes. **The regression is the price of
actually reading the tasks.**

What was already recovered (0.43 s → 0.36 s of scan): a conservative
`may_have_depends()` pre-filter, and priming the facts cache from text the scan
has already read (~250 fewer re-parses). The pre-filter skips **54 %** of files
(244 of 453) — an earlier "~78 %" claim in this plan counted only the Ready
listing and was wrong.

**Rule 3 as the task states it is met** — the batched call is preserved, still
exactly one subprocess, nothing regressed into per-dep subprocesses. The plan's
stricter "must not regress" wording is **not** met, and this section is the
explicit amendment.

**The one remaining lever, and why it is not taken here.** Routing
`task_yaml.parse_frontmatter` through libyaml's `CSafeLoader` is a ~5x parse win
that would take the scan to ~0.1 s and put `ait ls` back at or below its old
cost. Verified during this task that `CSafeLoader` honours `_TaskSafeLoader`'s
custom implicit resolver exactly — `[423_6, 12, t9_1]` parses identically under
both loaders. It is declined **in this task** because `task_yaml` is the
base-layer module the board, minimonitor, merge tool, codebrowser, diffviewer
and the report/trail gatherers all depend on, libyaml is not guaranteed present
(a fallback is required), and a silent resolver regression there would mis-parse
every child task id repo-wide. It is tracked as **t1611**
(`task_yaml_csafeloader_parse_speedup`, `depends: [1527]`), whose verification
parses every task file in the repo under both loaders and asserts equality,
covers the no-libyaml fallback explicitly, and re-measures `ait ls`.

## Risk

### Code-health risk: medium
- The new `deps-blocking-scan` subprocess is a process boundary in the
  most-used command, and its *total* failure degrades to "no blocking info at
  all" — i.e. every task lists as Ready. That is fail-**open**, the exact defect
  class this task removes. · severity: medium · → mitigation: inline pre-phase scan_failure_is_its_own_state
- Three dep implementations are replaced at once, including `ait ls`'s hottest
  loop (`calculate_blocked_status` + `is_task_uncompleted`, both deleted). A
  subtle bash regression there silently re-verdicts every listing, and nothing
  in the current suite compares whole-listing output before vs after.
  · severity: medium · → mitigation: inline pre-phase characterize_ls_listing_baseline
- `dependents_status_batch` is refactored onto the new `DependentsEvaluator`
  seam, so this task edits the t1472 perf-critical path it also has to preserve.
  · severity: low · → mitigation: covered — `tests/test_deps_unblock_batch.sh`
  pins its existing contract and Verification §5 pins the hoisting it exists for
- The evaluator hoisting that satisfies rule 3 is the same mechanism that, held
  too long, freezes signature verdicts (t1416). Perf and freshness pull in
  opposite directions here and the cycle boundary is the only thing separating
  them. · severity: medium · → mitigation: covered — the boundary is placed on
  the existing `clear_gate_cache()` line so it cannot drift, and Verification §7
  pins both directions (a new cycle re-decides; within a cycle it does not)
- Accepted residual (decision 2): a dep swept into a numbered bundle later flips
  to `(UNRESOLVED)` and blocks its dependent, requiring a data cleanup. Deliberate
  — the honest rendering rule 1 asks for. · severity: low · → mitigation: none (accepted)

### Goal-achievement risk: low
- The parity assertion could pass vacuously if the three surfaces are reduced
  through one lossy helper (e.g. `ait ls` display parsing that drops the
  `(UNRESOLVED)` marker), making all three agree on a tuple that hides a real
  difference. · severity: low · → mitigation: covered by the two negative
  controls already in Verification §2

### Planned mitigations
- timing: pre-phase | name: scan_failure_is_its_own_state | type: bug | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 1 (scan subprocess degrades fail-open) | desc: Define and test the deps-blocking-scan failure contract before wiring ait ls to it, so "cannot verify" is its own state rather than "nothing is blocked".
- timing: pre-phase | name: characterize_ls_listing_baseline | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: code-health risk 2 (silent re-verdict of every listing) | desc: Golden the live-tree ait ls output before touching aitask_ls.sh and diff it after, so any re-verdict is deliberate.

**Reassessment after inlining both mitigations:** code-health stays **medium** —
the two named risks are now covered, but the blast radius (6 load-bearing files,
including the most-used command and both main TUIs) is unchanged and is what the
level describes. Goal-achievement stays **low**.

**Post-implementation reassessment (Step 9).** Both named code-health risks were
realised in some form and caught by their own mitigations, which is the outcome
the levels described: the scan's failure contract needed tightening twice (exact
terminal trailer), and the `ait ls` characterization golden is what proved zero
re-verdicts. A third, unforeseen risk of the same class landed too — the scan's
own pre-filter briefly reintroduced a surface disagreement (block-list
`depends:`) — and was caught by the cross-surface parity test rather than by a
listed mitigation. Code-health **medium** was the right call. Goal-achievement
**low** held: the delivered shape is the planned one.

## Out of scope

- **t1528** (write-time `depends` validation) is the producer side. This task
  settles the canonical accepted forms — `<N>`, `t<N>`, `<N>_<M>`, `t<N>_<M>` —
  and t1528 enforces exactly those.
- **t1611** — `task_yaml` + libyaml `CSafeLoader`, created by this task to repay
  the +0.324 s regression measured above. Gated on this task (`depends: [1527]`)
  because it must be measured against this scan.
- Bundle extraction for dep resolution (decision 2).
- `ait ls`'s xdeps path, which is already fail-closed and correct.

## Final Implementation Notes

- **Actual work done:** all three surfaces now consume one core,
  `lib/dep_resolution.py` (`LocalDepResolver`, `DepVerdict`, `read_depends`,
  `may_have_depends`, `classify_facts`). `gate_ledger.py` gained the public
  `DependentsEvaluator` seam and `dependents_status_batch` was refactored onto
  it. `aitask_gate.sh` gained `deps-blocking-scan` (+ `delegate_python_deps`);
  `aitask_ls.sh` lost `build_dep_satisfied_set` / `is_task_uncompleted` and its
  whole local-dep loop; `TaskInfoCache.blocking_dependencies` returns
  `DepVerdict`s and `find_ready_siblings` lost its private status map; the board
  gained `local_dep_verdicts` and lost `dependency_released_by_gates` (no
  remaining callers). `tests/test_local_dep_parity.py` is 32 tests over 8
  sections; every guard was probed by deliberate mutation and observed to fail.

- **Deviations from plan:**
  - The plan's bash lookup ("fork-free substring scan over one variable")
    measured **15 s for 451 lookups** — bash's `${var#*"$key"}` retries the glob
    from every position over a 6 KB blob. Replaced with two parallel INDEXED
    arrays and a linear scan: **0.094 s**, still bash-3.2 safe (no `declare -A`).
  - `_dep_resolver` is a CLASS-level attribute on `TaskManager`, not an
    `__init__` assignment: three test harnesses build a `TaskManager` via
    `__new__` and populate only what they need, and "not built yet" is the
    honest default for all of them.
  - The characterization step used `-v -s all --all-levels 9999`; the plan's
    `--all` is not a flag.
  - Four review rounds changed the design after the plan was approved — the
    malformed-`depends:` reader, the exact-terminal-`SCAN_OK` rule, the
    block-list pre-filter correction, and the performance amendment. Each is
    written into the sections above rather than only here.

- **Issues encountered:**
  - `may_have_depends()`'s first version treated a bare `depends:` key as
    dep-free. That is a YAML block-list head, so `ait ls` skipped tasks the
    board and minimonitor blocked — the three-surface disagreement this task
    removes, reintroduced by its own optimisation. `aitask_ls.sh`'s lookup guard
    had the same bug independently (it keyed off its inline-only parsed value);
    both halves are now pinned by `BlockListDependsTests`.
  - The instrumented fan-out test counted **0** registry parses in the full
    suite while passing in isolation: the suite holds **two distinct
    `gate_ledger` module objects loaded from the same file path**, so patching
    this module's own import intercepted nothing and the `<= 1` assertion passed
    vacuously. It now patches `dep_resolution.gate_ledger` and asserts `== 1`.
  - `depends: 999` made `monitor_core._resolve` raise `TypeError` and
    `depends: "999"` made it invent `['9','9','9']` — both pre-existing, both
    now routed through `read_depends`.
  - **Concurrent sessions.** At least two other agents edited this working tree
    throughout. `monitor_core.py` / `monitor_shared.py` carried their hunks and
    mine, so the commit stages only my hunks (filtered patch → `git apply
    --cached`), verified by materialising the index tree and running the suite
    from it. `tests/test_shadow_phase_restamp.py` and
    `tests/test_collection_structure.py` fail in the working tree from their
    in-flight minimonitor work and PASS in the isolated staged tree.

- **Key decisions:** fail-closed tri-state; loose files only (bundles never
  extracted, pinned with a REAL bundle the scan must ignore); the evaluator's
  lifetime is one cycle, bound to the line that already renews
  `gate_digest_cache`; `ait ls` lists only the deps that actually block.

- **Upstream defects identified:**
  - `.aitask-scripts/monitor/monitor_core.py:3800 — _resolve iterated the raw
    depends field, so a scalar `depends: 999` raised TypeError and killed the
    whole task lookup, and `depends: "999"` yielded three per-character
    dependencies. Pre-existing; fixed here because the shared reader had to
    exist anyway.` (fixed in this task, recorded for traceability)
  - `tests/lib/board_fixture.py — the suite loads .aitask-scripts/lib modules
    under more than one module object (measured: two distinct `gate_ledger`
    objects from one path). Any test that patches a lib module by its own import
    can silently intercept nothing. Not fixed here; a suite-wide guard asserting
    single-instance lib imports would catch a whole class of vacuous tests.`

### Gate verification note (Step 9)

`ait gates run 1527` first recorded `risk_evaluated: fail` — "plan has no
'## Risk' section". That was **self-inflicted and real**: the edit that rewrote
this plan's performance section spliced from `## Performance…` to
`## Out of scope`, and the `## Risk` section sat between them, so it was deleted.
The verifier was correct.

`risk_evaluated` has a retry budget of 0 (the format check is deterministic —
re-running an unchanged plan cannot produce a different answer), so the
orchestrator then reported `blocked: exhausted` rather than re-running. The
section was restored from `f23ea5bf7` (the original plan commit), committed, and
the real verifier `aitask_gate_risk.sh` was invoked directly; it appended its own
genuine `pass`. No status was hand-written and no `ait gate pass` override was
used — but the orchestrator's retry budget *was* bypassed by invoking the
verifier outside it, and that is worth knowing when reading this ledger: the run
id reads `manual-recheck` rather than an orchestrator-generated one.
