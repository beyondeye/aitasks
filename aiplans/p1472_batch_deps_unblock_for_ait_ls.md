---
Task: t1472_batch_deps_unblock_for_ait_ls.md
Worktree: (none — current branch)
Branch: (current)
Base branch: main
Output branch: main
---

# t1472 — Batch `deps-unblock` for `ait ls`

## Context

`ait ls` is slow, and nothing ever attributed the cost. `build_dep_satisfied_set()`
in `.aitask-scripts/aitask_ls.sh:172-198` greps for every active task whose
frontmatter carries `gates:` / `active_gates:` / `also_blocks_dependents:`, then
spawns **one `aitask_gate.sh` subprocess per candidate** — each of which starts a
fresh Python interpreter to run `gate_ledger.py deps-unblock`.

Measured on this repo, right now:

| measurement | value |
|---|---|
| gated candidates | 190 |
| `ait ls 15`, total | **18.9 s** |
| the `deps-unblock` fan-out alone | **9.7 s** (51% of the total) |
| one `deps-unblock` call | ~46 ms |

t1416 made `deps-unblock` re-validate code-bound human-gate signatures. The
no-git pre-filter keeps that free for a task with no stamped witness, but each
task that *does* carry one adds a `code_digest()` (~5 ms) — and because every
task is its own process, the lazy digest cannot amortize. The added cost is
linear in the number of signed tasks (+2.2% at W=50, crossing +10% at W≈230).
Batching removes that scaling concern as a side effect: one digest for the whole
`ait ls` instead of one per signed task.

**Outcome:** 190 subprocesses → 1. Expected `ait ls` ≈ 18.9 s → ≈ 9 s.

> **Scope note on the task's stated expectation.** The task text predicts
> "~12.5 s → well under 1 s". That applies to the **fan-out**, not to `ait ls`
> overall: the other ~9.2 s is unrelated work in `aitask_ls.sh` that this task
> does not touch. The plan is written against the fan-out figure and reports both
> numbers so the distinction is visible rather than read as a miss.

`aitask_ls.sh:194` is the **only** production caller of the per-task verb; every
other reference is a test or a doc. The per-task verb still stays — it is a
documented public CLI verb, and `tests/test_dependency_unblock.sh:111`,
`tests/test_gate_active_gates.sh`, and `tests/test_gate_stale_witness_parity.sh`
all pin it.

## Design

**One shared decision core, two CLI surfaces.** The single largest hazard here is
the batch verb and the per-task verb drifting into two implementations of the
unblock decision. The plan prevents that structurally rather than by convention:
`dependents_status()`'s body is extracted into a private
`_dependents_status_for_text(...)`, and *both* verbs call it. Neither surface
holds any decision logic of its own. This mirrors the existing
`_dependents_status_from_state()` seam directly above it.

**Digest amortization reuses the board's proven pattern.** `_resolve_digest()`
(`gate_ledger.py:1409-1435`) already accepts a **callable** as one of its four
digest states, invoked only *after* a task's no-git pre-filter finds a stamped
witness. The board threads exactly such a memo
(`aitask_board.TaskManager.code_digest_for_refresh`, `aitask_board.py:1550`). The
batch does the same: a batch over 190 unsigned tasks never shells out to git; any
number of signed ones shells out exactly **once**.

**The path round-trips instead of an id.** The batch echoes back each input
**path**, not a derived id. `aitask_ls.sh` already derives its dep-set key from
the basename, so echoing the path keeps that normalization as the *single* place
a task file maps to a key — no id-canonicalization agreement needed across the
Python/bash boundary.

## Implementation

### Pre-phase (risk mitigations)

**`ls_output_characterization`** — runs FIRST, before any file below is touched.
The "before" capture is unobtainable once the code changes, which is why this is
a phase and not a Verification bullet.

```bash
./ait ls 15    > /tmp/t1472_before_plain.txt 2>&1
./ait ls -v 15 > /tmp/t1472_before_v.txt     2>&1
./ait ls -v -l backend 15 > /tmp/t1472_before_label.txt 2>&1
```

Also capture the ground-truth decision vector the batch must reproduce:

```bash
grep -lE '^(gates|active_gates|also_blocks_dependents):' \
  aitasks/t[0-9]*_*.md aitasks/t[0-9]*/t[0-9]*_[0-9]*_*.md 2>/dev/null \
  | while IFS= read -r f; do b="${f##*/}"; \
      [[ "$b" =~ ^t([0-9]+)_([0-9]+)_ ]] && id="${BASH_REMATCH[1]}_${BASH_REMATCH[2]}" \
        || { [[ "$b" =~ ^t([0-9]+)_ ]] && id="${BASH_REMATCH[1]}"; }; \
      printf '%s\t%s\n' "$(TASK_DIR=aitasks ./.aitask-scripts/aitask_gate.sh \
        deps-unblock "$id" 2>/dev/null || echo NO_GATES)" "$f"; \
    done > /tmp/t1472_before_decisions.txt
```

Verification step 7 then diffs the post-change captures against these three
files and the decision vector against the batch's own output. Any difference is
a blocking defect, not a judgement call.

### 1. `.aitask-scripts/lib/gate_ledger.py`

**1a. Extract the shared core.** Split `dependents_status()` (currently
`:1342-1392`) so the body becomes a text-level private function and the public
function is a thin file+registry reader:

```python
def _dependents_status_for_text(text: str, registry: dict[str, dict],
                                task_id: str,
                                current_digest) -> tuple[str, list[str]]:
    """Shared core of the per-task and batched deps-unblock verbs (t1472).

    Both `dependents_status` and `dependents_status_batch` route through here,
    so the two CLI surfaces cannot drift into two implementations of the
    decision (pinned by tests/test_deps_unblock_batch.sh).
    """
    active, filtered, _valid = read_active_tuple_from_text(text)
    also = _read_frontmatter_list_from_text(text, "also_blocks_dependents")
    also_effective = [g for g in also if g not in filtered]
    effective, _stale = demote_stale_signed(
        required_unblock_gates(active, also_effective, registry), registry,
        derive_gate_runs(text), task_id, current_digest)
    return _dependents_status_from_state(active, also_effective, registry,
                                         effective)


def dependents_status(task_file, registry_file, current_digest=_COMPUTE_DIGEST):
    """<existing docstring, cost paragraph updated — see 1d>"""
    with open(task_file, encoding="utf-8") as fh:
        text = fh.read()
    return _dependents_status_for_text(
        text, read_registry(registry_file) if registry_file else {},
        task_id_from_file(task_file), current_digest)
```

Behavior is unchanged: same reads, same order, same seam
(`demote_stale_signed`).

**1b. Add the one-shot digest memo**, placed next to `_resolve_digest`:

```python
class _DigestMemo:
    """One-shot memo over the four-state digest channel (t1472).

    Batch analogue of the board's `TaskManager.code_digest_for_refresh`. Passed
    to the decision core as a *callable*, so `_resolve_digest` invokes it only
    after some task's no-git pre-filter finds a stamped witness: a batch of 300
    unsigned tasks never shells out to git; any number of signed ones shells out
    exactly once. Delegating to `_resolve_digest` is what keeps all four
    incoming states (sentinel / callable / str / None) handled in one place.

    **A failed provider is memoized as the FAILURE, and re-raised.** It must not
    decay into a cached `None`: `witness_state` resolves `current_digest is None`
    to `unstamped` = *accept* (`gate_ledger.py:1535-1536`), so a cached None
    would let every signed task after the first release its dependents on a
    code-bound witness that was never re-validated — the exact fail-open t1416
    closed. It is also the pattern `_resolve_digest` forbids one layer down
    ("swallowing here would reinterpret a caller bug as 'unverifiable' and
    quietly accept a signature nobody validated", `:1426-1429`).

    So: resolve at most ONCE (a failed provider is never retried, so a batch
    cannot pay N failing subprocesses), and every later caller re-raises the
    stored exception. Each signed row then hits the batch's per-file guard and
    falls back to `NO_GATES` — conservative, since a task whose staleness cannot
    be determined must not release its dependents. Unsigned rows never call the
    memo at all and are unaffected.

    `Exception`, not `BaseException`: a `KeyboardInterrupt` must still kill the
    batch rather than be replayed per row.
    """
    __slots__ = ("_source", "_value", "_error", "_done")

    def __init__(self, source):
        self._source = source
        self._value = None
        self._error = None
        self._done = False

    def __call__(self):
        if not self._done:
            self._done = True                     # set first: never retry
            try:
                self._value = _resolve_digest(self._source)
            except Exception as exc:              # noqa: BLE001 — stored + re-raised
                self._error = exc
                raise
        if self._error is not None:
            raise self._error
        return self._value
```

**1c. Add the batch API**, directly below `dependents_status`:

```python
def dependents_status_batch(task_files, registry_file,
                            current_digest=_COMPUTE_DIGEST):
    """`(rows, setup_error)` — one `(path, decision, pending)` row per input
    path, in input order, plus the setup failure that forced them all (t1472).

    A plain function, not a generator: the caller needs BOTH the rows and the
    setup verdict, and a generator would force either a second registry parse
    in the CLI or a `StopIteration.value` dance. 190 rows is nothing to hold.

    One process, ONE registry parse, and AT MOST one `code_digest()` for the
    whole batch — replacing `ait ls`'s former one-subprocess-per-gated-task
    fan-out (190 processes / 9.7s on the framework repo).

    **Totality is the contract: every input path yields exactly one row.** Two
    distinct degradation boundaries keep it true.

    *Per-file* — a file that cannot be read or decided yields `("NO_GATES", [])`
    plus a stderr diagnostic naming it, rather than aborting the batch. This
    reproduces the boundary the old shape got for free from the per-task
    `delegate_python ... || echo "NO_GATES"` fallback: collapsing N processes
    into 1 must not let one bad task file cost `ait ls` every other decision.

    *Setup* — `read_registry` runs ONCE, before the loop, and is therefore
    outside every per-file guard. It already returns `{}` for a missing
    registry, but still raises on a directory path, unreadable permissions,
    non-UTF-8 bytes, or a TOCTOU delete. Left unguarded that would abort the
    batch before a single row, so the promised rows and diagnostic would never
    exist. Guarded, a setup failure degrades to the SAME shape: `NO_GATES` for
    every input row, ONE diagnostic (not N copies of the same cause), and a
    non-None `setup_error` the CLI turns into a NONZERO exit — so a caller that
    reads exit status can still tell "everything fell back" from "nothing was
    gated", a distinction invisible in the rows themselves.

    Falling back to a partial `registry={}` decision is deliberately NOT done:
    with no registry no gate carries `blocks_dependents`, so `also_blocks_dependents`
    entries would still be honored while registry-flagged ones silently would
    not — an inconsistent half-decision. All-`NO_GATES` is the conservative
    whole answer (the caller falls back to file-existence, so a dependent stays
    blocked until archival); it is not fail-open.
    """
    setup_error = None
    try:
        registry = read_registry(registry_file) if registry_file else {}
    except Exception as exc:                          # noqa: BLE001 — see above
        registry, setup_error = {}, exc
        sys.stderr.write(
            f"deps-unblock-batch: registry unavailable ({registry_file}): {exc}"
            f" — every task falls back to NO_GATES\n")
    if setup_error is not None:
        return [(p, "NO_GATES", []) for p in task_files], setup_error

    memo = _DigestMemo(current_digest)
    rows = []
    for path in task_files:
        try:
            with open(path, encoding="utf-8") as fh:
                text = fh.read()
            decision, pending = _dependents_status_for_text(
                text, registry, task_id_from_file(path), memo)
        except Exception as exc:                      # noqa: BLE001 — see above
            sys.stderr.write(f"deps-unblock-batch: {path}: {exc}\n")
            decision, pending = "NO_GATES", []
        rows.append((path, decision, pending))
    return rows, None
```

**1d. CLI verb**, next to the existing `deps-unblock` block (`:1937-1947`). It
owns the exit code; the registry is parsed exactly once, inside the batch:

```python
if cmd == "deps-unblock-batch":
    registry_file = argv[1] if len(argv) > 1 else None
    paths = [p for p in (ln.rstrip("\n") for ln in sys.stdin) if p]
    rows, setup_error = dependents_status_batch(paths, registry_file)
    for path, decision, pending in rows:
        label = "BLOCKED:" + ",".join(pending) if decision == "BLOCKED" else decision
        sys.stdout.write(f"{label}\t{path}\n")
    return 1 if setup_error is not None else 0
```

**Exit-code contract:** `0` = every row decided (per-file fallbacks included —
those are isolated and the other rows are valid). `1` = setup failed, all rows
are a conservative `NO_GATES`. Rows are always written to stdout **before** the
nonzero return, so `aitask_ls.sh`'s `|| true` degrades safely either way.

**1e. Docstring updates in the same file:**
- Module CLI block (`:25-27`) — add the `deps-unblock-batch` line.
- `dependents_status`'s **Cost** paragraph (`:1373-1379`) currently ends "the
  batched-`deps-unblock` follow-up subsumes it" — that follow-up is now this
  task. Rewrite to state that `ait ls` goes through `dependents_status_batch`,
  which amortizes to one digest, and that the per-task verb keeps the
  linear-in-W cost for single-task callers.

### 2. `.aitask-scripts/aitask_gate.sh`

**2a.** Add `cmd_deps_unblock_batch()` beside `cmd_deps_unblock` (`:597`):

```bash
# deps-unblock-batch: the batched twin of deps-unblock (t1472). Reads task FILE
# PATHS on stdin (one per line, already resolved — no resolve_task_file pass) and
# prints `<decision>\t<path>` per input line, in input order. The path round-trips
# so the caller keeps ownership of id normalization.
#
# No `|| echo NO_GATES` fallback: on a python-unavailable failure the caller sees
# NO output, which is exactly equivalent to N x NO_GATES (no task enters the
# dep-satisfied set) — the same degradation the per-task verb produces.
#
# Exit status passes through unchanged: 0 = every row decided, 1 = registry
# setup failed and every row is a conservative NO_GATES (rows are still printed).
# NOTE: `aitask_ls.sh` discards this verb's stderr and ignores its exit status,
# because in both failure shapes the rows it reads are already safe. A systematic
# failure is therefore INVISIBLE in `ait ls` output — "nothing is gated" and "the
# decider is broken" look identical there. Diagnose by running this verb by hand
# with stderr attached:
#   printf '%s\n' aitasks/t123_x.md | ./.aitask-scripts/aitask_gate.sh deps-unblock-batch
cmd_deps_unblock_batch() {
    delegate_python deps-unblock-batch "$REGISTRY"
}
```

**2b.** Dispatch entry after `deps-unblock)` (`:1397`):
```bash
deps-unblock-batch) shift; cmd_deps_unblock_batch "$@" ;;
```

**2c.** Help text — a `deps-unblock-batch` block after the `deps-unblock` block
(`:1235-1243`), documenting the stdin/stdout shapes **and the exit-code
contract** (0 = all rows decided; 1 = registry setup failed, all rows NO_GATES).

**2d.** Header comment block: add the verb to the `:20` verb list and to the
python-only exceptions list at `:48`.

**2e.** Fix the now-stale comment above `cmd_deps_unblock` (`:584-587`), which
says the fan-out "is tracked separately". Replace with: `ait ls` now uses
`deps-unblock-batch`; this per-task verb is for single-task callers and tests.

### 3. `.aitask-scripts/aitask_ls.sh` — `build_dep_satisfied_set()`

Replace the per-candidate loop (`:183-196`) with a single batch call. Two wins:
the 190 gate subprocesses collapse to 1, **and** the 190 `basename` forks go away
(`${f##*/}`, and only for the SATISFIED rows).

```bash
    # ONE subprocess for the whole candidate list (t1472). Decisions come back
    # as `<decision>\t<path>`; the path round-trips so the normalization below
    # stays the single place a task file maps to a dep-set key.
    local decision f base norm
    while IFS=$'\t' read -r decision f; do
        [[ "$decision" == "SATISFIED" ]] || continue
        base="${f##*/}"
        if [[ "$base" =~ ^t([0-9]+)_([0-9]+)_ ]]; then
            norm="t${BASH_REMATCH[1]}_${BASH_REMATCH[2]}"
        elif [[ "$base" =~ ^t([0-9]+)_ ]]; then
            norm="${BASH_REMATCH[1]}"
        else
            continue
        fi
        printf '%s\n' "$norm" >> "$dep_satisfied_file"
    done < <(printf '%s\n' "$candidates" \
        | TASK_DIR="$TASK_DIR" "$gate_script" deps-unblock-batch 2>/dev/null || true)
```

The surrounding contract is untouched: same `grep -lE` candidate scan, same
normalized keys in `dep_satisfied_file`, same `is_task_uncompleted()` consumer.

### 4. New test — `tests/test_deps_unblock_batch.sh`

Self-contained bash test in the house style (`set -u`, `tests/lib/asserts.sh`,
own PASS/FAIL summary), modelled on `tests/test_dependency_unblock.sh`.

Cases are labelled **T1–T9** so they cannot be confused with, or half-updated
against, the separately numbered command checklist under `## Verification`.

**T1. Decision parity over a full-shape fixture set.** Reuse that file's
   `write_task` / `mark` / registry fixtures to build one file per decision
   shape: ungated → `NO_GATES`; gated but no `blocks_dependents` gate →
   `NO_GATES`; required gate pending → `BLOCKED:<g>`; all required pass →
   `SATISFIED`; `also_blocks_dependents` pending → `BLOCKED`; `also` satisfied →
   `SATISFIED`. Run the per-task verb once per fixture, run the batch **once**
   over all of them, assert the decision vectors are element-wise identical
   **and** that the echoed paths match the input order.
**T2. Negative control.** Re-run the batch against a *second* registry in which
`build_verified: blocks_dependents` is flipped to `false`, and assert the two
vectors now **differ**. One mutation, and it proves the T1 assertion is
load-bearing rather than vacuously equal. (A passing negative control would mean
the comparison is wrong.)

**T3. Stale-witness re-validation survives batching.** Using the git-repo +
gitignored-witness fixture from `tests/test_gate_stale_witness_parity.sh:55-100`,
assert a task whose ledger reads `pass` but whose witness is signed against a
stale digest comes back `BLOCKED:review` from the batch, exactly as from the
per-task verb. This is the t1416 semantics the batch must not lose.

**T4. Digest amortization is exact.** Two complementary assertions, because
counting raw `git` invocations alone cannot express "one digest":
`code_digest()` issues **3** git commands in a repo with commits (`rev-parse
HEAD`, `diff HEAD …`, `ls-files --others …` — `gate_ledger.py:1458-1466`), and
only **1** when `rev-parse HEAD` fails. A test asserting "git called once" would
fail on correct batching.

- *Exact count, via the documented seam.* `current_digest` is a public parameter
  and `_resolve_digest` explicitly accepts a **callable**. Drive
  `dependents_status_batch` from Python with a counting callable over a fixture
  of **3** signed tasks and assert it is invoked **exactly once** — and
  **zero** times for a fixture of 3 *unsigned* tasks (verified reachable:
  `stale_signed_gates` resolves the digest at `gate_ledger.py:1586`, strictly
  after the no-witness pre-filter at `:1580-1585`). This is the precise
  assertion; it needs no magic git constant. Runs from the bash file via a
  `"$PYTHON" - <<'PY'` heredoc so the test stays self-contained.
- *End-to-end invariance, via a `git` PATH shim.* Count shim invocations for a
  batch over **1** signed task and over **3** signed tasks and assert the two
  counts are **equal** (and non-zero). Asserting invariance across N sidesteps
  the 3-vs-1 constant entirely, while still proving amortization through the
  real subprocess path. For contrast, assert the per-task loop over the same 3
  tasks yields **3×** that count.

**T5. Per-file isolation.** A batch whose input includes a nonexistent path
returns `NO_GATES` for that row, still decides every other row correctly, exits
**0**, and writes a stderr diagnostic **naming that path** (asserted on the
message body, not merely on stderr being non-empty).

**T6. Setup failure is total and diagnosable.** Point the verb at a registry path
that is a **directory** (a case `read_registry`'s `os.path.exists` guard lets
through to `open()`, unlike a missing file, which correctly returns `{}`). Assert:
every input path gets exactly one `NO_GATES` row, in input order; exit status is
**1**; stderr carries **exactly one** diagnostic naming the registry path and the
cause — not one copy per row. Also assert the *missing*-registry case still
behaves as today: exit **0**, rows decided against an empty registry.

**T7. Edge cases.** Empty stdin → empty stdout, exit 0. Blank input lines are
skipped (and do not produce rows).

**T8. Bash surface parity.** `aitask_gate.sh deps-unblock-batch` in a scaffolded
repo returns the same rows as the direct `gate_ledger.py` invocation, **and
propagates the exit status** in both the clean and the setup-failure case
(mirrors `test_dependency_unblock.sh:110`).

**T9. `aitask_ls.sh` integration is unchanged.** In a scaffolded repo with a
gated upstream whose required gates all pass, `aitask_ls.sh` still shows the
dependent as unblocked; with the registry broken as in T6, it falls back to
showing the dependent blocked rather than crashing or emitting a partial list.

**T10. A failing digest provider fails safe for EVERY signed row.** The
regression test for the `_DigestMemo` hazard above — the one case where a
half-right memo silently releases dependents.

Fixture: **3 signed** tasks (witness on disk, ledger `pass`, gate flagged
`blocks_dependents: true`) plus **1 unsigned** gated task whose decision does not
depend on the digest. Drive `dependents_status_batch` with a `current_digest`
callable that **raises on its first invocation** and would return a *valid,
matching* digest if ever called again. Assert:

- all **3** signed rows come back `NO_GATES` — not just the first;
- the provider was invoked **exactly once** (no retry — otherwise a broken
  provider costs N failures per `ait ls`);
- stderr carries one diagnostic per signed row;
- the unsigned row still decides normally, and the batch exits **0** (this is
  per-file isolation, not a setup failure);
- for contrast, the same fixture with a *working* provider yields `SATISFIED`
  for the signed rows — so the test cannot pass by the fixture simply being
  blocked for some unrelated reason.

**This test discriminates.** Against the rejected memo (cache `None`, do not
re-raise), signed rows 2 and 3 return `SATISFIED` because `witness_state` accepts
a `None` digest as `unstamped`. The "would return a valid digest if called again"
provider is what makes that failure visible rather than indistinguishable from a
correct fallback.

### 5. Docs

- `aidocs/gates/dependency-unblock-semantics.md` — the implementation paragraph
  (`:68-72`) names `aitask_gate.sh deps-unblock` as the surface consumed by
  `aitask_ls.sh`; add the batched surface as what `ait ls` actually calls.
- `aidocs/gates/gate-guarded-archival.md` — the "Which surfaces re-validate"
  table row for `deps-unblock` (`:106`); note the batch amortizes to one digest
  per `ait ls`, the same property the board row already claims.

### Post-phase (risk mitigations)

**`batch_failure_diagnosability`** — runs after step 5, before Verification.

The per-file `except Exception → NO_GATES` boundary keeps one bad task file from
costing `ait ls` every other decision, but it converts a loud crash into a quiet
degradation — and `aitask_ls.sh` discards the batch's stderr, so in production
the diagnostic reaches nobody.

- **T10** covers the third boundary — a failing digest provider. It is the one
  that most needed a test: batching makes a single provider outcome decide many
  rows, and the naive memo turns that into accepted-but-unvalidated signatures
  for every signed row after the first.
- **T5** asserts the per-file diagnostic **names the offending path**, not merely
  that the row came back `NO_GATES`. Without that assertion the boundary is
  tested as a swallow and not as a *diagnostic*.
- **T6** covers the systematic case, which is the one the boundary could not
  otherwise reach: `read_registry` runs once, outside the per-file guard, so an
  unguarded setup failure aborts before any row and the promised diagnostic
  never exists. The guard added in §1c makes that path total (all-`NO_GATES`
  rows, exit 1, one diagnostic naming the cause) — which is what makes this
  mitigation implementable at all rather than aspirational.
- **Exit status is the machine-readable half.** Stderr is discarded by
  `aitask_ls.sh`, so the `1` from a setup failure is the only signal a
  non-interactive caller can act on. It distinguishes "everything fell back"
  from "nothing was gated" — two states that are byte-identical in the rows.
- Document the discard explicitly in `cmd_deps_unblock_batch`'s comment (§2a):
  `ait ls` drops this verb's stderr and ignores its status, so a systematic
  failure is diagnosed by running the verb by hand with stderr attached.

## Verification

1. `bash tests/test_dependency_unblock.sh` — green, **including** the `:111`
   shell/python parity assertion.
2. `bash tests/test_deps_unblock_batch.sh` — the new test above, green, with its
   negative control demonstrated failing-when-it-should.
3. `bash tests/test_gate_active_gates.sh` and
   `bash tests/test_gate_stale_witness_parity.sh` — green (both pin
   `deps-unblock` semantics this refactor moves through a new seam).
4. `bash tests/run_all_python_tests.sh` — read only the last line
   (`PYTHON SUITE: PASSED|FAILED (runner=…, exit=N)`).
5. `shellcheck .aitask-scripts/aitask_gate.sh .aitask-scripts/aitask_ls.sh`.
6. **Before/after timing, measured within one run** (this box runs concurrent
   agents, so cross-run absolute numbers are not comparable — memory:
   within-run ablation only). One script that, back to back:
   - times the old shape (loop `aitask_gate.sh deps-unblock` over the candidate
     list) — baseline captured today: **9.7 s / 190 candidates**;
   - times the new shape (one `deps-unblock-batch` over the same list);
   - asserts the two produce **identical** SATISFIED sets on the live repo.
   Then a plain `time ./ait ls 15` for the end-to-end figure (baseline **18.9 s**).
7. **Characterization diff** (closes the pre-phase). Re-capture all three
   `ait ls` variants and diff against `/tmp/t1472_before_*.txt`; re-capture the
   decision vector via `deps-unblock-batch` and diff against
   `/tmp/t1472_before_decisions.txt` (same `<decision>\t<path>` shape, so the two
   are directly comparable). All four diffs must be **empty** — this is a pure
   performance refactor of a decision that must not move. Any difference is a
   blocking defect.

Step 9 (Post-Implementation) handles cleanup, gate verification, merge into
`main`, and archival.

## Risk

Levels below are the **reassessment against the augmented plan** (both inline
phases included), per `risk-evaluation.md`'s reassessment note.

### Code-health risk: medium
- `build_dep_satisfied_set()` feeds `is_task_uncompleted()`, which decides
  Blocked-vs-Ready for every task in `ait ls` and the board. A batch that
  silently mis-decides would mis-render blocking repo-wide, and the failure is
  quiet (a wrong Ready, not a crash). · severity: low (was medium — the
  pre-phase golden makes a moved decision a hard diff against 190 real gated
  tasks) · → mitigation: inline pre-phase ls_output_characterization
- The per-file `except Exception → NO_GATES` isolation boundary can mask a
  genuine bug across all 190 rows. It is required to preserve the old
  per-process boundary, but it converts a loud crash into a quiet degradation.
  · severity: medium (unchanged — the post-phase makes the failure *diagnosable*
  but does not remove the compromise; "nothing is gated" and "the decider is
  broken" remain indistinguishable in `ait ls` output itself) ·
  → mitigation: inline post-phase batch_failure_diagnosability
- **Amortizing the digest introduces cross-row coupling that per-process
  execution did not have.** One shared memo means one provider outcome now
  decides many rows, so any state it caches propagates. The specific trap: a
  cached `None` reads as "unverifiable" and `witness_state` accepts it
  (`:1535-1536`), releasing dependents on unvalidated signatures. Closed by
  memoizing the failure and re-raising it (§1b) so every signed row falls back
  to `NO_GATES`, and pinned by T10, which discriminates against the naive memo.
  · severity: low (closed by construction + a discriminating regression test;
  listed because the coupling is inherent to batching and any future change to
  the memo re-opens it) · → mitigation: inline post-phase batch_failure_diagnosability
- Two CLI surfaces for one decision is the classic drift shape. Mitigated
  structurally by the extracted `_dependents_status_for_text` core (neither
  surface holds decision logic) plus the parity test and its negative control.
  · severity: low · → mitigation: inline pre-phase ls_output_characterization

**Why still medium, not low:** the swallow-and-continue boundary is a real,
unremovable structural compromise on a load-bearing read path. The inline phases
reduce the chance a defect goes *undetected*; they do not remove the compromise.

### Goal-achievement risk: low
- The fan-out cost is already measured and attributed (9.7 s of 18.9 s), the
  seam already accepts a threaded digest, and the caller already holds the
  paths — so the approach is verified, not assumed. The only stated-expectation
  gap is "well under 1 s" applying to the fan-out rather than to `ait ls`
  overall, which the Context section states explicitly. · severity: low ·
  → mitigation: None needed

### Planned mitigations
- timing: pre-phase | name: ls_output_characterization | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — silent mis-decision of Blocked-vs-Ready across ls/board | desc: Capture ait ls output and the per-task deps-unblock decision vector before any code change; diff byte-for-byte after.
- timing: post-phase | name: batch_failure_diagnosability | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: code-health — except-Exception boundary masking a systematic bug as 190 quiet NO_GATES | desc: Assert the isolation boundary's stderr diagnostic names the offending path, cover the all-rows-fail case, and document that aitask_ls.sh discards stderr.

## Final Implementation Notes

- **Actual work done:** Implemented as planned, all five sections plus both inline
  risk-mitigation phases.
  - `gate_ledger.py`: extracted `_dependents_status_for_text` as the shared
    decision core; added `_DigestMemo`, `dependents_status_batch` returning
    `(rows, setup_error)`, and the `deps-unblock-batch` CLI verb.
  - `aitask_gate.sh`: `cmd_deps_unblock_batch`, dispatch entry, help block, header
    verb list + python-only exceptions, and corrected the stale "batching is
    tracked separately" comment above `cmd_deps_unblock`.
  - `aitask_ls.sh`: `build_dep_satisfied_set()` now makes ONE batch call.
  - `tests/test_deps_unblock_batch.sh`: new, 46 assertions (T1–T10).
  - `aidocs/gates/dependency-unblock-semantics.md` + `gate-guarded-archival.md`.

- **Measured result (within one run, per the task's Verification):**

  | measurement | before | after |
  |---|---|---|
  | `deps-unblock` fan-out, 191 candidates | 9926 ms | **56 ms** (~177×) |
  | `ait ls 15` end-to-end | 18.9 s | **4.1 s** |
  | processes | 191 gate + 191 `basename` | **1** |

  The task predicted "~12.5 s → well under 1 s" for the fan-out; 56 ms clears it.
  `ait ls` overall lands at 4.1 s, not <1 s, because the remaining ~4 s is
  unrelated work in `aitask_ls.sh` — the Context section called this out before
  implementation so it would not read as a miss.

- **Deviations from plan:** Two, both additive.
  1. Removed the 191 `basename` forks as well (`${f##*/}`, and only on SATISFIED
     rows). Planned as a minor side-benefit; it is part of why the end-to-end win
     exceeded the predicted ~9 s.
  2. Added a T7 assertion pinning the CLI's blank-line contract (below).

- **Issues encountered:**
  - *Two T-case expectations were wrong on first run (fixture, not invariant).*
    T10's "unsigned control" declared `build_verified`, absent from the signed
    fixture's registry, so it returned `NO_GATES` — correct, but indistinguishable
    from an isolated row, making it a weak control. Fixed by adding a MACHINE-typed
    `build` gate to that registry: `stale_signed_gates`' pre-filter only considers
    `type: human`, so the control row provably never resolves the digest and
    returns a distinctive `SATISFIED`. T9 asserted a task with `status:
    Implementing` would be listed; `aitask_ls.sh:79` sets `STATUS_FILTER="Ready"`,
    so it never is — retargeted to the dependent. In both cases the assertion's
    intent was preserved and only the fixture moved.
  - *The live characterization is weaker than the plan assumed.* All 191 live rows
    are `NO_GATES`, because the only gate tasks declare is `risk_evaluated`
    (`blocks_dependents: false`). The golden therefore detects a false-`SATISFIED`
    regression but cannot confirm `SATISFIED`/`BLOCKED` reproduction on live data —
    that weight rests entirely on T1/T3's fixtures, which makes them load-bearing
    rather than belt-and-braces. Worth knowing before anyone trims them.
  - *A false alarm worth recording.* The first before/after decision-vector diff
    looked like a decision change but was pure reordering: this machine's
    interactive `grep` is a shell function wrapping **ugrep 7.5.0**, which
    parallelizes and returns non-deterministic `-l` order even for a fixed sorted
    arg list. Framework scripts get GNU grep 3.12 via `/usr/bin/grep` (fresh
    `#!/usr/bin/env bash`), so `aitask_ls.sh`'s enumeration IS stable and nothing
    in the repo is affected. Comparisons were redone against an explicitly sorted
    path list.

- **Key decisions:**
  - *One core, two surfaces.* Both verbs route through
    `_dependents_status_for_text`; neither holds decision logic. Structural, not
    conventional — the drift the task warned about is impossible rather than
    merely tested against.
  - *Echo the path, not a derived id.* Keeps `aitask_ls.sh`'s basename
    normalization the single place a task file maps to a dep-set key, so no
    id-canonicalization agreement is needed across the Python/bash boundary.
  - *`(rows, setup_error)` rather than a generator.* The CLI needs both the rows
    and the setup verdict; a generator would have forced either a second registry
    parse or a `StopIteration.value` dance — the former defeating the point.
  - *A failed digest provider is memoized as the FAILURE and re-raised.* Caught in
    plan review. Caching a bare `None` would let `witness_state` read it as
    `unstamped` = accept, releasing dependents on signatures nobody re-validated —
    the exact t1416 fail-open, reintroduced one layer up from where
    `_resolve_digest` forbids it. T10 is the regression test and **was
    demonstrated failing** against the naive memo: it produced
    `decisions=NO_GATES,SATISFIED,SATISFIED,SATISFIED` with only **1** diagnostic
    instead of 3 — rows 2–3 failing open, silently.
  - *Blank stdin lines produce no row.* Caught in Step 8 review. The alternative
    (emitting `NO_GATES\t`) would hand `aitask_ls.sh` an empty basename to
    normalize, so the docs were corrected instead: the one-to-one guarantee is per
    NON-EMPTY input line, and callers should key off the echoed path. Qualified at
    all five CLI claim sites; the `dependents_status_batch` docstring claim was
    left (it is accurate for the function, which receives a pre-filtered list) but
    sharpened to name where filtering happens.
  - *`NO_GATES` as the conservative fallback everywhere.* It routes the caller
    back to file-existence, so a dependent stays blocked until the upstream
    archives. Never fail-open. A partial `registry={}` decision was explicitly
    rejected: it would honor `also_blocks_dependents` while silently dropping
    registry-flagged gates.

- **Upstream defects identified:** None.

- **Verification performed:**
  - All four characterization diffs **empty** (3 `ait ls` variants + the 191-row
    decision vector vs. the pristine pre-change baseline).
  - Batch ≡ per-task verb, same sorted input, same run, order included.
  - `tests/test_deps_unblock_batch.sh` 46/46, with the T2 and T10 negative
    controls both demonstrated failing when they should.
  - `tests/test_dependency_unblock.sh` 12/12 (incl. the `:111` parity assertion);
    `test_gate_active_gates.sh` and `test_gate_stale_witness_parity.sh` PASSED.
  - `bash tests/run_all_python_tests.sh` → `PYTHON SUITE: PASSED (runner=pytest,
    exit=0)`.
  - `shellcheck`: finding counts identical to baseline on both edited scripts
    (4 and 7, all SC1091/SC2010/SC2034 pre-existing); zero warnings or errors on
    the new test.
