---
Task: t1744_fix_failed_verification_t1737_item4.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1744 — Make the `fake_agent_binary` source ladder lazy

## Context

`tests/lib/fake_agent_binary.py` builds a "real executable named after a code
agent" by trying a ladder of sources and verifying each rung by running it. Its
docstring describes a ladder — rung 2 (compile a C sleeper) is for macOS, where
rung 1 (copy the system `sleep`) cannot run.

Manual verification t1737 item #4 measured the actual behaviour on Linux and
partially falsified it. What holds: the binary `fake_agent_binary()` *returns* is
rung 1 — a `shutil.copy` of `/usr/bin/sleep`, a regular file, never a symlink.
What is falsified: rung 2 is evaluated **unconditionally**, on every platform,
including when rung 1 succeeds.

`tests/lib/fake_agent_binary.py:134`:

```python
for source in (_sleep_binary(), _compiled_sleeper_path()):
```

The tuple is built eagerly, so `_compiled_sleeper_path()` runs before the loop
body ever executes — it `mkdtemp`s a build dir, writes `sleeper.c`, invokes
`cc`/`clang`/`gcc` and `_runs` the result, and then the loop returns on its first
iteration and throws that work away. Reproduced in this session with a spy:
`rung-2 call count: 1`, and a compiled binary at
`/tmp/ait-fake-agent-build-*/sleeper`.

Correctness is unaffected — the right binary is returned. The cost is one wasted
C compilation per test *process* that touches the fixture (it is memoised in the
`_compiled_sleeper` module global, so once per process, not once per call), and a
box with no C toolchain does strictly more work and logs more failure noise than
it needs to. It also contradicts the module's own stated contract.

Intended outcome: the ladder consults a rung only when the previous one failed,
and a test pins that at the production boundary so the eager form cannot come
back.

## Changes

### 1. `tests/lib/fake_agent_binary.py` — iterate over thunks

Replace the eagerly-built tuple in `fake_agent_binary()` (line 134) with a tuple
of the functions themselves, calling each only when the previous rung has failed:

```python
    # Thunks, not values: rung 2 compiles a C sleeper, and an eagerly built
    # `(_sleep_binary(), _compiled_sleeper_path())` pays for that compile on
    # every platform — including Linux, where rung 1 always wins and the
    # compiled binary is discarded unused (t1744).
    for get_source in (_sleep_binary, _compiled_sleeper_path):
        source = get_source()
        if not source:
            continue
        ...
```

The loop body is otherwise unchanged, and rung 3 (`allow_symlink`) and the
`FakeAgentBinaryUnavailable` raise below it are untouched.

Also make the contract the tests pin explicit in the module docstring: the
existing "tries a ladder and **verifies each rung by running it**" sentence gains
a clause saying a later rung is built only once the earlier one has failed.

### 2. New `tests/test_fake_agent_binary_ladder.py`

The whole benefit of this change lives at the call site, not in either helper, so
every case spies on the module attribute `_compiled_sleeper_path` and drives the
real `fake_agent_binary()` entry point.

**The loop has two distinct fall-through paths and the tests cover each
separately**, because they fail independently:

```python
    try:
        shutil.copy(source, dest); os.chmod(dest, 0o755)
    except OSError:
        continue          # path A — the source could not be copied
    if _runs(dest):
        return dest       # path B — the copy landed but will not execute
```

Path B is the macOS case the module exists for (docstring §2: `shutil.copy`
succeeds, then the copy is SIGKILLed on exec), so it is the **primary** positive
control. A test suite that only ever failed rung 1 through path A would stay
green against a regression that made `return dest` unconditional.

Stubs, all written into the test's own tmpdir, all `#!/bin/sh` and `chmod 0755`
— copyable and runnable on Linux and macOS alike, unlike a copy of the *system*
`sleep`:

- `ok_stub` — `exit 0`, so the real `_runs` accepts it;
- `fail_stub` — `exit 1`, so the real `_runs` rejects it **after** a successful
  copy (path B).

Five `unittest` cases:

1. **`test_rung_two_not_consulted_when_rung_one_succeeds`** — the case the task
   exists for. `_sleep_binary` → `ok_stub`; assert the spy recorded **zero**
   calls. Paired negative control in the same test: assert the returned file is
   byte-identical to `ok_stub` and is not a symlink — a zero-call assertion alone
   would pass just as well against a ladder that dropped rung 1 entirely.
2. **`test_rung_two_consulted_once_when_rung_one_copies_but_does_not_run`** —
   path B, the macOS shape. `_sleep_binary` → `fail_stub`, spy → `ok_stub`.
   Assert **exactly one** spy call and that the returned file is byte-identical
   to `ok_stub` (i.e. the fallback result, not the stale rung-1 copy that was
   sitting at `dest`).
3. **`test_rung_two_consulted_once_when_rung_one_cannot_be_copied`** — path A.
   `_sleep_binary` → a nonexistent path, so `shutil.copy` raises `OSError`; spy →
   `ok_stub`. Assert **exactly one** spy call and the rung-2 result.
4. **`test_unavailable_and_dest_cleaned_when_no_rung_runs`** — `_sleep_binary` →
   `fail_stub` (so rung 1 really does leave a file at `dest`), spy → `None`,
   `allow_symlink=False`. Assert `FakeAgentBinaryUnavailable` **and** that
   `dest` no longer exists. Driving this through path B is what makes the
   cleanup assertion non-vacuous: reached via path A nothing was ever created,
   and the `os.unlink(dest)` at lines 156-157 would go untested.
5. **`test_symlink_rung_resolves_and_executes_when_opted_in`** — rung 3 calls
   `_sleep_binary()` *again* (line 153), so the target must stay runnable while
   rungs 1-2 fail. Patch `_runs` → always `False` (the macOS-shaped "nothing
   copied here will run" condition, which is exactly when rung 3 exists),
   `_sleep_binary` → `ok_stub`, spy → `None`, `allow_symlink=True`. Assert
   `dest` is a symlink, that `os.path.realpath(dest)` is `ok_stub`, and — the
   actual point — that running `[dest, "0"]` exits 0 under a **real**
   `subprocess.run`, independent of the stubbed `_runs`. Also covers the
   `os.unlink(dest)` at lines 151-152, since rung 1's copy is present.

Cases 4 and 5 guard the two branches *below* the rewritten loop, which is the
only other thing this edit can disturb.

No case invokes a real compiler: rung 2 is spied in every one, so the module is
toolchain-independent and adds no measurable suite time.

Conventions followed from `tests/test_agent_keys.py`: module docstring with a
numbered list of what is covered and a `Run:` line, `from __future__ import
annotations`, the two `sys.path.insert` lines for `.aitask-scripts/lib` and
`tests/lib`, and an `unittest.main()` footer.

## Files

- `tests/lib/fake_agent_binary.py` — the fix (loop at line 134, docstring clause)
- `tests/test_fake_agent_binary_ladder.py` — new
- No other file changes. The two consumers (`tests/test_agent_keys.py`,
  `tests/test_prompt_scoping_live.py`) call `fake_agent_binary()` and need no
  edit; they are run as regression checks.

## Verification

Run once, in order:

1. `python3 tests/test_fake_agent_binary_ladder.py` — all five cases pass.
2. **Mutation check — the boundary test must be able to fail.** Temporarily
   restore the eager tuple, re-run the module, and confirm case 1 goes red and
   the other four stay green (cases 2-5 all fail rung 1, so rung 2 is consulted
   under either form and they cannot discriminate). Restore the fix and confirm
   all five green again. This is the plan's only mutation step — do not repeat
   it.
3. `python3 tests/test_agent_keys.py` — the real consumer of the fixture
   (`allow_symlink=True` path).
4. `python3 tests/test_prompt_scoping_live.py` — the tmux-reading consumer
   (`allow_symlink=False`, so it exercises the `FakeAgentBinaryUnavailable`
   contract). Report a skip honestly if the environment cannot run it.
5. Re-run the t1737 measurement in a fresh process — spy on
   `_compiled_sleeper_path`, call `fake_agent_binary()` on this Linux box, and
   confirm the call count is now **0** where t1737 measured **1**, with the
   returned path still a non-symlink copy of the system `sleep`. This is the
   original verification item, now passing.

## Implementation record

All plan steps completed as written; no deviations from the approved approach.

1. `tests/lib/fake_agent_binary.py` — loop rewritten over thunks, plus the
   docstring clause making the lazy contract explicit.
2. `tests/test_fake_agent_binary_ladder.py` — the five cases as planned.

### Post-review change (Step 8 iteration 1)

`setUp` created a `mkdtemp` per case with no matching cleanup, leaking five
`ait-ladder-test-*` directories per run. Fixed with
`self.addCleanup(shutil.rmtree, self.tmp, True)` registered immediately after
the `mkdtemp` — `addCleanup` rather than `tearDown` so it also fires after a
failing assertion. Measured both ways: 25 stragglers had accumulated from the
five verification runs above; after the fix a passing run and a deliberately
failing run (eager mutant re-applied) each added **0**. The 25 were removed.

Verification results:

1. `python3 tests/test_fake_agent_binary_ladder.py` — **5/5 OK** (0.007s).
2. **Mutation check** — three mutants applied and reverted in place (by edit, not
   `git restore`, since this worktree is shared and dirty):
   - the literal pre-fix eager tuple → **1 failure**, case 1 only;
   - the subtler *callable-but-eagerly-bound* form
     `(_sleep_binary, lambda v=_compiled_sleeper_path(): v)` — a genuine callable
     that still pays the compile → **1 failure**, case 1 only. This is the
     regression a `callable()` assertion or a type annotation would miss;
   - `if _runs(dest): return dest` → unconditional `return dest` (path B removed)
     → **3 failures**: cases 2, 4 and 5. Recorded because it is the mutant the
     originally planned positive control (a nonexistent rung-1 source, path A
     only) would **not** have detected — the plan-review concern that added the
     `fail_stub` was correct, and this is the evidence it is closed.

   The module was byte-identical to its pre-mutation state after each revert.
3. `python3 tests/test_agent_keys.py` — **18/18 OK** (5.2s).
4. `python3 tests/test_prompt_scoping_live.py` — **4/4 OK** (0.3s), no skips.
5. **The original t1737 item #4 measurement, re-run in a fresh process on this
   Linux box:**

   ```
   returned path is a copy of /usr/bin/sleep : True
   returned path is a symlink                : False
   rung-2 (_compiled_sleeper_path) CALL COUNT: 0   (t1737 measured 1)
   mode                                      : 0o755
   ```

   The verification item now holds in full: rung 1 is taken, the compiled and
   symlink rungs are not, and rung 2 is no longer evaluated at all.

## Risk

### Code-health risk: low

- The rewritten loop could disturb the rung-3 (`allow_symlink`) or
  `FakeAgentBinaryUnavailable` paths that sit directly below it · severity: low ·
  → mitigation: covered inside this plan by cases 4 and 5 of change 2; no
  separate task needed.

Blast radius is one test-only fixture module and its two consumers; no production
code path is touched, and the change is two lines within a single function.

### Goal-achievement risk: low

- None identified. The task records the exact measured defect, the fix is the one
  its evidence recommends, and verification step 5 re-runs the original t1737
  measurement, so delivery is directly observable rather than inferred.

### Planned mitigations

None. The single identified risk is already mitigated by an explicit step of this
plan (cases 4 and 5), so there is no candidate left to spawn or to inline as a
separate phase.

## Final Implementation Notes

- **Actual work done:** Exactly the approved plan. `tests/lib/fake_agent_binary.py`
  now iterates the source ladder over thunks (`for get_source in (_sleep_binary,
  _compiled_sleeper_path): source = get_source()`), so rung 2's C compile is paid
  for only when rung 1 has failed; the module docstring states that lazy contract
  explicitly. New `tests/test_fake_agent_binary_ladder.py` pins it at the
  production boundary with five cases (163 lines), none of which invokes a real
  compiler.
- **Deviations from plan:** None in approach. One post-review addition (Step 8
  iteration 1): `addCleanup(shutil.rmtree, ...)` for the per-case `mkdtemp`.
- **Issues encountered:** None during implementation. The plan itself was
  strengthened twice by review before and during Step 8 — see "Key decisions".
- **Key decisions:**
  - **Thunks over a `sys.platform` branch.** The module's stated design is to
    verify each rung by running it rather than branching on the platform; making
    the tuple lazy preserves that and changes only *when* a rung is built.
  - **Cover the loop's two fall-through paths separately.** `fake_agent_binary`
    can leave a rung either because `shutil.copy` raised (path A) or because the
    copy landed and `_runs()` rejected it (path B). Path B is the macOS case the
    module exists for. An earlier draft of the plan used only a nonexistent
    rung-1 source — path A — and mutation testing confirmed that draft would have
    missed a regression removing the `if _runs(dest)` check entirely: that mutant
    fails cases 2, 4 and 5, all of which exist because of the path-B control.
  - **`sh` stubs rather than the system `sleep`** as rung sources in tests. A
    copy of the platform `sleep` will not execute on macOS, so a stub is what
    makes each case deterministic on both platforms; an `exit 1` stub is what
    produces a path-B failure with the *real* `_runs`.
  - **Independent ground truth for rung 3.** Case 5 stubs `_runs` to False to
    reach the symlink rung, so the module's own verdict cannot be the evidence;
    the test executes the link under a real `subprocess.run` instead.
  - **Mutation-verified.** Three mutants, each reverted by an exact inverse edit
    rather than `git restore` (this worktree is shared and carries unrelated
    in-flight work from another session).
- **Upstream defects identified:** None
