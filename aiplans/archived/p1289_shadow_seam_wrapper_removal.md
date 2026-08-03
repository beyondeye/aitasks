---
Task: t1289_shadow_seam_wrapper_removal.md
Worktree: (none — current branch)
Branch: main
Base branch: main
Output branch: main
---

# t1289 — Remove the transitional shadow-seam delegators from `MiniMonitorApp`

## Context

t1216_1 lifted minimonitor's shadow helpers into `monitor/monitor_core.py` so
`ait monitor` and `ait minimonitor` share one implementation. It deliberately
left one-line delegators behind on `MiniMonitorApp` for a single reason: the
existing shadow test suite binds to those private names, and keeping the seams
let the whole characterization net pass **byte-unmodified** — that task's proof
that the lift changed no behaviour.

That proof has served its purpose. t1216_2/_3/_4 have landed (all archived under
`aitasks/archived/t1216/`, parent `Done`), so `monitor_app.py` is now a second
real consumer calling the shared functions directly (`monitor_app.py:1084`,
`:2863`, `:2898`). The seams are now pure structure debt: two names for one
implementation. This task removes them and points minimonitor's own call sites
and tests at the shared functions, exactly as `monitor_app.py` already does.

This is a **pure de-duplication** — no behaviour changes.

## Scope (verified by AST scan, not by reading)

An AST scan of `MiniMonitorApp` for "method or class alias whose entire body is
a call to a shared import" returns exactly the four members the task names, plus
one module-level alias:

| Member | Delegates to |
|---|---|
| `_find_shadow_pane_for_sync` (`:1431`) | `monitor_core.find_shadow_pane` |
| `_find_shadow_pane_for` (`:1435`) | `monitor_core.find_shadow_pane_async` |
| `_capture_shadow_text` (`:1439`) | `monitor_core.capture_shadow_text` |
| `_format_stale_duration` (`:1490`) | `monitor_shared.format_stale_duration` |
| `_unparsed_msg` (`:109`, module level) | `monitor_shared.unparsed_concerns_msg` |

`_unparsed_msg` is in scope on its own authority — its comment already reads
"Removed by the shadow_seam_wrapper_removal follow-up (t1289)."

`_spawn_shadow` (`:1381`) stays. It is a **policy adapter, not a pass-through
seam** — the AST scan does not flag it, and `aidocs/framework/shadow_agent.md:146-148`
documents the carve-out explicitly.

### The `match_shadow_pane` decision

The task asks to decide one way and be consistent. **Remove the re-export.**
`minimonitor_app.py:36` imports it purely to re-export (`noqa: F401`); no
production code in that module calls it. Its only consumers are four assertions
in `tests/test_minimonitor_concern_action.py`, which are repointed at
`monitor_core` (already imported there as `mc`).

## Changes

### 1. `.aitask-scripts/monitor/minimonitor_app.py`

**Deletions**
- `:33-36` — drop `match_shadow_pane` from the `monitor.tmux_monitor` import and
  the three-line comment justifying the re-export.
- `:92-95` — retire the "helpers now live in monitor_core" comment block; after
  this change the imports say that themselves.
- `:108-109` — delete the `_unparsed_msg = unparsed_concerns_msg` alias and its
  comment.
- `:1424-1443` — delete the "The three helpers below are delegating seams"
  comment and the three methods. Keep the `# -- Shadow concern picker (t1037_4)`
  section header.
- `:1489-1490` — delete the `_format_stale_duration` staticmethod alias and its
  comment. `_update_shadow_freshness` at `:1479` already calls
  `format_stale_duration` directly and is untouched.

**Import boundary — explicit decision: keep importing through `monitor.tmux_monitor`.**
`minimonitor_app.py:27` pulls the shared shadow functions from
`monitor/tmux_monitor.py`, which is a **backwards-compatibility shim** whose own
docstring says "Add new code to `monitor_core.py`, not here" — so the concern
that this leaves a layer of indirection is fair. It is nonetheless the
**established boundary for both apps**: `monitor_app.py:26-38`, the second real
consumer this task waited for, imports `capture_shadow_text`,
`compute_shadow_staleness`, `find_shadow_pane_status` and `spawn_shadow` the same
way, and the shim re-exports the whole t1216_1 / t1216_4 seam deliberately
(`tmux_monitor.py:44-56`). Repointing minimonitor alone would make the two apps
disagree; repointing both is a separate repo-wide import migration, not this
task. Residual risk — a future shim rebind reintroducing indirection while the
`MiniMonitorApp` seam scan still passes — is closed by the runtime identity
assertion in verification step 1c, which pins `mm.<fn> is mc.<fn>`.

**Call-site rewrites** — each substitutes the delegator body verbatim, so the
argv, ordering, and sync/async character are unchanged:

| Line | From | To |
|---|---|---|
| `:1302`, `:1345` | `self._find_shadow_pane_for_sync(followed_pane)` | `find_shadow_pane(self._monitor, followed_pane)` |
| `:1505`, `:1583` | `await self._find_shadow_pane_for(snap.pane.pane_id)` | `await find_shadow_pane_async(self._monitor, snap.pane.pane_id)` |
| `:1512`, `:1599` | `await self._capture_shadow_text(shadow_pane)` | `await capture_shadow_text(shadow_pane)` |
| `:1521` | `await self._capture_shadow_text(shadow_pane, lines=…)` | `await capture_shadow_text(shadow_pane, lines=…)` |
| `:1536`, `:1619` | `_unparsed_msg(lost)` | `unparsed_concerns_msg(lost)` |

All four `self._monitor` uses are already guarded: `:1302`/`:1345` sit after an
`if self._monitor is None: return`, and the two async sites passed
`self._monitor` through the delegator unchanged.

### 2. `tests/test_minimonitor_concern_action.py`

The stubs move from **instance attribute** to **module attribute**: the call
sites now resolve `capture_shadow_text` from `minimonitor_app`'s globals, so
`app._capture_shadow_text = …` would intercept nothing. Add one helper beside
`_async_return`:

```python
def _stub_capture(test, coro):
    """Bind minimonitor's module-level capture seam for one test (t1289).

    The delegating ``_capture_shadow_text`` method is gone: the call sites
    resolve ``capture_shadow_text`` from ``minimonitor_app``'s globals, so the
    stub replaces the module attribute. The original is restored on teardown;
    call again to re-stub mid-test.
    """
    if not hasattr(test, "_orig_capture"):
        test._orig_capture = mm.capture_shadow_text
        test.addCleanup(setattr, mm, "capture_shadow_text", test._orig_capture)
    mm.capture_shadow_text = coro
```

Then, per the acceptance rule, **only the called name changes — no assertion
changes**:

- Every `app._capture_shadow_text = _async_return(X)` (17 sites across
  `ActionPickConcernsTests`, `AutoOfferTests`, `ShadowFreshnessTests`) becomes
  `_stub_capture(self, _async_return(X))`; the two `_capture` closures in
  `test_retries_deeper_on_truncated_head` / `test_warns_when_deeper_retry_still_truncated`
  / `test_genuinely_no_block_keeps_the_plain_message` become
  `_stub_capture(self, _capture)`. `AutoOfferTests._app` and
  `ShadowFreshnessTests._fresh_app` already receive `self`.
- `MatchShadowPaneTests` — `mm.match_shadow_pane` → `mc.match_shadow_pane` (4 lines).
- `ShadowFreshnessTests.test_format_stale_duration` — `f = mm.MiniMonitorApp._format_stale_duration`
  → `f = format_stale_duration`, adding
  `from monitor.monitor_shared import format_stale_duration`.
- `CaptureArgvTests._run_capture` — drop the now-pointless `app = _mk_app()` and
  call `mm.capture_shadow_text("%5", **kwargs)`. Calling it through `mm` (not
  `mc`) is deliberate: that is the exact binding the production call sites
  resolve. Update the class docstring's `_capture_shadow_text` reference.

`LaunchShadowGuardTests` needs **no change** — it drives `action_launch_shadow`
through `_FakeMon.tmux_run`, and the rewritten guard still issues the same sync
gateway call. Its `sync_calls`/`async_calls` assertions keep proving the "no
await trap" property. Same for the shadow-pane lookups in
`ActionPickConcernsTests`/`AutoOfferTests`, which reach the real
`find_shadow_pane_async` via `_FakeMon.tmux_run_async` and are unaffected.

### 3. `tests/test_minimonitor_concern_smoke.py`

The most careful migration — this module's whole point is that the capture path
is **not** stubbed. Preserve that: keep wrapping the *real* helper, only pinning
the scrollback depth. In `ConcernCaptureSmokeTests`:

```python
    def _patch(self, obj, name, value):
        self.addCleanup(setattr, obj, name, getattr(obj, name))
        setattr(obj, name, value)

    def _app(self, lines: int):
        ...
        app._find_own_agent_snapshot = lambda: _snap("%99")
        # The delegating seams are gone (t1289): `_maybe_offer_concerns`
        # resolves both helpers from `minimonitor_app`'s globals, so the stubs
        # are module attributes now. The capture wrapper still calls the REAL
        # helper — only the scrollback depth is pinned.
        self._patch(mm, "find_shadow_pane_async", _async_pane(self.pane_id))
        real_capture = mm.capture_shadow_text
        self._patch(
            mm, "capture_shadow_text",
            lambda pane, *, _r=real_capture: _r(pane, lines=lines),
        )
        return app
```

Both test bodies then call `asyncio.run(mm.capture_shadow_text(self.pane_id))`
instead of `app._capture_shadow_text(...)`, which resolves the pinned wrapper.
Update the module docstring's two `_capture_shadow_text` mentions (`:3`, `:8`).

### 4. `aiplans/p1118_mobile_shadow_agent_driving_over_applink.md:280-281`

Its "Reused existing code" inventory lists `minimonitor_app.py` — `match_shadow_pane`.
t1118 is unimplemented, so this would send its implementer to a name that no
longer exists there. One-line correction: attribute `match_shadow_pane` to
`monitor_core.py` (where it has lived since t1216_1) and leave the
`_update_shadow_freshness` half unchanged. Three other plan/task references to
"the `match_shadow_pane` pattern" describe the function generically and stay
correct.

**Explicitly out of scope:** `aidocs/framework/python_tui_performance.md:33`
pins minimonitor at "733 LOC". That is a dated benchmark snapshot, not a live
claim, and re-measuring it is a different task. `tests/test_shadow_seam.py`
already targets the shared functions and needs no change, as the task predicted;
`tests/test_minimonitor_shadow_pick.py` turns out to reference none of the five
names and is untouched. A repo-wide sweep found **zero** references in `aidocs/`,
`website/`, `.claude/`, `.agents/`, `.opencode/`, `seed/`, `CLAUDE.md`, or any
shell script.

## Verification

1. **Acceptance criterion, mechanically** — re-run the AST scan; it must print
   nothing:
   ```bash
   python3 - <<'EOF'
   import ast, pathlib
   src = pathlib.Path(".aitask-scripts/monitor/minimonitor_app.py").read_text()
   tree = ast.parse(src)
   shared = {a.asname or a.name for n in ast.walk(tree)
             if isinstance(n, ast.ImportFrom)
             and n.module in ("monitor.tmux_monitor", "monitor.monitor_shared",
                              "monitor.monitor_core")
             for a in n.names}
   cls = next(n for n in tree.body
              if isinstance(n, ast.ClassDef) and n.name == "MiniMonitorApp")
   for scope, nodes in (("class", cls.body), ("module", tree.body)):
       for n in nodes:
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
               body = [s for s in n.body if not (isinstance(s, ast.Expr)
                       and isinstance(s.value, ast.Constant))]
               if len(body) == 1 and isinstance(body[0], ast.Return):
                   v = body[0].value
                   v = v.value if isinstance(v, ast.Await) else v
                   if isinstance(v, ast.Call) and getattr(v.func, "id", "") in shared:
                       print(f"DELEGATOR {scope} {n.lineno}: {n.name}")
           if isinstance(n, ast.Assign):
               v = n.value
               if isinstance(v, ast.Call) and getattr(v.func, "id", "") == "staticmethod":
                   v = v.args[0]
               if isinstance(v, ast.Name) and v.id in shared:
                   print(f"DELEGATOR {scope} {n.lineno}: {n.targets[0].id}")
   EOF
   ```
   **1b — no *executable* stragglers.** A `grep` is the wrong instrument here:
   the migrated code deliberately *names* the removed members in comments and
   docstrings to explain why the stubs are module-level, so a text search would
   fail on a correct migration and pressure us into deleting useful prose. Scan
   the AST instead, which cannot see strings or comments:
   ```bash
   python3 - <<'EOF'
   import ast, pathlib
   GONE = {"_find_shadow_pane_for", "_find_shadow_pane_for_sync",
           "_capture_shadow_text", "_format_stale_duration", "_unparsed_msg"}
   for p in [*pathlib.Path(".aitask-scripts").rglob("*.py"),
             *pathlib.Path("tests").rglob("*.py")]:
       for n in ast.walk(ast.parse(p.read_text())):
           name = (n.attr if isinstance(n, ast.Attribute)
                   else n.id if isinstance(n, ast.Name) else None)
           if name in GONE:
               print(f"EXECUTABLE REF {p}:{n.lineno}: {name}")
   EOF
   ```
   Must print nothing. `match_shadow_pane` needs no scan: once the re-export is
   gone, any surviving `mm.match_shadow_pane` raises `AttributeError` and the
   suite fails loudly.

   **1c — the shim did not rebind.** Both apps import the shared functions
   through the `monitor.tmux_monitor` compatibility shim (see the import-boundary
   decision above). Assert the names minimonitor resolves are literally
   `monitor_core`'s objects, so a future shim rebind cannot slip indirection back
   in behind a passing seam scan:
   ```bash
   python3 -c "
   import sys; sys.path[:0] = ['.aitask-scripts', '.aitask-scripts/lib']
   from monitor import minimonitor_app as mm, monitor_core as mc
   for f in ('find_shadow_pane', 'find_shadow_pane_async', 'capture_shadow_text'):
       assert getattr(mm, f) is getattr(mc, f), f
   assert not hasattr(mm, 'match_shadow_pane'), 're-export still present'
   print('IMPORT BOUNDARY OK')"
   ```

2. **Prove the migrated stubs still discriminate.** A module-attribute stub that
   silently fails to intercept would let the suite pass while testing the real
   tmux path. Temporarily revert one `_stub_capture(self, …)` call to the old
   `app._capture_shadow_text = …` form and confirm
   `test_happy_path_modal_then_clipboard` **fails**; restore it. Without this,
   a green suite proves nothing about the migration.

3. **Targeted suites** (tmux 3.7b is present, so the live smoke really runs — it
   is not silently skipped):
   ```bash
   python3 -m unittest tests.test_minimonitor_concern_action \
                       tests.test_minimonitor_concern_smoke \
                       tests.test_minimonitor_shadow_pick \
                       tests.test_shadow_seam -v
   bash tests/test_no_raw_tmux.sh
   bash tests/test_shortcuts_registry_coverage.sh
   ```

3b. **Prove the module patch survives the parallel lane.** The runner's pytest
   + xdist tier is installed on this machine (`xdist 3.8.0`, `~/.aitask/dev_tier`
   present), so the parallel lane is live, and both migrated files patch the same
   `minimonitor_app` attributes. `--dist loadfile` is what makes that safe:
   workers are separate **processes** (that is also why the runner needs
   loadfile — ~39 modules `chdir`), each executing its file's tests
   sequentially, so no test can observe another's stub. Pin it by running rather
   than asserting it:
   ```bash
   ~/.aitask/venv/bin/python -m pytest -n 2 --dist loadfile -v \
       tests/test_minimonitor_concern_action.py \
       tests/test_minimonitor_concern_smoke.py \
       tests/test_shadow_seam.py
   ```
   If a future runner change ever moves to in-process parallelism, these stubs
   must become scoped patches — noted in the plan's Final Implementation Notes.

4. **Full suite** — `bash tests/run_all_python_tests.sh` (takes the parallel
   pytest lane on this machine); read only the last line
   (`PYTHON SUITE: PASSED|FAILED …`). Do not pipe it without `pipefail`. Re-run
   once with `AIT_TEST_PARALLEL=0` to confirm the serial lane agrees.

5. **Live sanity** — `./ait minimonitor` starts, and with a shadow running,
   `c` (pick concerns) and `e` (duplicate-shadow guard) behave as before.

6. Step 9 (Post-Implementation) handles archival; there is no worktree to clean
   up (current-branch mode).

## Risk

### Code-health risk: low

- The test stubs move from instance attributes to **module attributes**, which
  is process-global state: a leaked patch would bleed into unrelated tests in
  the same process and could mask a real failure. Two things contain it. Within
  a process, every patch goes through `_stub_capture` / `_patch`, which register
  `addCleanup` restore **at bind time** rather than relying on a `tearDown` an
  early failure could skip. Across the suite, the runner's parallel lane
  (`xdist`, live on this machine) is **process**-based with `--dist loadfile`,
  so the two files that patch `minimonitor_app` cannot interleave — verified by
  running them under the real lane (verification 3b), not assumed. The standing
  condition is that the runner stays process-parallel; in-process parallelism
  would require scoped patches. · severity: low · → mitigation: none needed
- The shared functions are still imported through the `monitor.tmux_monitor`
  compatibility shim rather than `monitor_core` directly. That matches
  `monitor_app.py` and is the deliberate boundary (see the import-boundary
  decision), but it means a future shim rebind could reintroduce indirection
  without tripping the seam scan. Closed by the `mm.<fn> is mc.<fn>` identity
  assertion in verification 1c. · severity: low · → mitigation: none needed
- Everything else is deletion: ~30 lines of delegators and comments removed, no
  new structure introduced, and the resulting call sites become byte-identical
  in shape to the ones `monitor_app.py` already uses. · severity: low · →
  mitigation: none needed

### Goal-achievement risk: low

- The acceptance criterion is mechanically checkable (verification step 1), and
  the scope was enumerated by AST scan plus a repo-wide reference sweep rather
  than by reading, so an unnoticed fifth delegator or an unswept caller is
  unlikely. · severity: low · → mitigation: none needed
- The one substantive judgement is the smoke test, whose value depends on the
  real capture path staying unstubbed. Verification step 2 (the discrimination
  check) and step 3's intermediate shape assertions — which the smoke already
  makes — are what keep that honest. · severity: low · → mitigation: none needed

**No mitigation tasks planned.** Both dimensions are `low` and each bullet above
is already contained by the plan itself (`addCleanup`-at-bind-time for the stub
state; verification steps 1–2 for the coverage concern). The one candidate that
would otherwise fit — committing the AST scan as a permanent regression guard —
was considered and explicitly declined in favour of a one-time verification, so
it is not re-proposed here. No `### Planned mitigations` subsection is written,
so Step 7 and Step 8d find nothing and no-op.

## Final Implementation Notes

- **Actual work done:** Implemented exactly as planned. Deleted the four
  `MiniMonitorApp` delegators (`_find_shadow_pane_for_sync`,
  `_find_shadow_pane_for`, `_capture_shadow_text`, `_format_stale_duration`),
  the module-level `_unparsed_msg` alias, and the unused `match_shadow_pane`
  re-export from `minimonitor_app.py` (−59/+13). Rewrote 9 call sites to the
  shared functions verbatim. Migrated
  `tests/test_minimonitor_concern_action.py` (17 capture stubs → the new
  module-level `_stub_capture` helper; `mm.match_shadow_pane` →
  `mc.match_shadow_pane`; `_format_stale_duration` → `format_stale_duration`;
  `CaptureArgvTests` now drives `mm.capture_shadow_text` directly) and
  `tests/test_minimonitor_concern_smoke.py` (a `_patch` helper rebinds
  `find_shadow_pane_async` and wraps the REAL `capture_shadow_text` with only
  the scrollback depth pinned). Corrected one stale line in
  `aiplans/p1118_mobile_shadow_agent_driving_over_applink.md` that attributed
  `match_shadow_pane` to `minimonitor_app.py`. **No assertion was changed** —
  every test change is a change of which name it calls, per the task's
  acceptance rule.

- **Deviations from plan:** None substantive. Two decisions the plan recorded
  and the implementation kept: (a) the duplicate `MatchShadowPaneTests` /
  `test_format_stale_duration` classes were **repointed at `monitor_core`
  rather than deleted**, so they now literally duplicate coverage in
  `tests/test_shadow_seam.py` — chosen deliberately to honour "change only
  which name it calls"; (b) the AST acceptance scan was run as a **one-time
  verification, not committed as a guard test**.

- **Issues encountered:**
  - The plan's original grep-based straggler check was self-contradictory — the
    migrated code deliberately *names* the removed members in comments and
    docstrings, so a text search fails on a correct migration. Replaced before
    implementation with an AST scan that cannot see strings or comments.
  - `_TASK_ID_RE` is flagged unused by pyflakes in `minimonitor_app.py`.
    Verified **pre-existing** (present on `HEAD` before this change) and left
    alone. This change reduced that file's pyflakes warnings from 2 to 1 by
    removing the `match_shadow_pane` re-export.
  - `main` advanced mid-session: t1354_3 (opt-in pytest-xdist parallel lane)
    and t1366 landed during planning. t1354_3 rewrote
    `test_minimonitor_concern_smoke.py`'s tmux fixture to a per-PID socket with
    a private `TMUX_TMPDIR`; this task's edits sit cleanly on top of it.
  - A concurrent session's syncer swept the `p1118` plan correction into its
    own commit `c337b9aa7` ("ait: Auto-commit task changes before sync"). The
    content is committed and correct, just under another session's message; not
    rewritten, to avoid touching shared history.

- **Key decisions:**
  - **Import boundary kept at `monitor.tmux_monitor`.** That module is a
    backwards-compatibility shim ("Add new code to `monitor_core.py`, not
    here"), but it is the established boundary for *both* apps —
    `monitor_app.py:26-38` imports the same seam through it. Repointing
    minimonitor alone would make the two apps disagree; repointing both is a
    separate repo-wide migration. The residual (a future shim rebind
    reintroducing indirection behind a passing seam scan) is closed by a
    runtime `mm.<fn> is mc.<fn>` identity assertion, run as verification 1c.
  - **`match_shadow_pane` re-export removed** (the task asked for one
    consistent choice): no production code in `minimonitor_app` called it, and
    its only consumers were four test assertions now pointing at `monitor_core`.
  - **Test stubs are module-global state**, which is only safe because the
    runner's parallel lane is *process*-based (`xdist` with `--dist loadfile`,
    which is also why ~39 chdir-ing modules need loadfile). Verified by running
    the three shadow files under the real lane, not by assuming it. **If the
    runner ever moves to in-process parallelism, `_stub_capture` / `_patch`
    must become scoped patches.**

- **Verification performed:** AST acceptance scan (no delegators) and executable
  -reference scan both clean; import-boundary identity assertion `IMPORT
  BOUNDARY OK`; **negative control** — reverting one `_stub_capture` call to the
  old instance-attribute form made `test_happy_path_modal_then_clipboard` fail
  with `AssertionError: 0 != 1` on `spy_pushed`, proving the module stub is
  load-bearing (restored afterwards, `__pycache__` purged first); live-tmux
  smoke ran for real (tmux 3.7b present) — 2 passed; parallel lane over the
  three shadow files — 93 passed; `test_no_raw_tmux.sh` 5/5 and
  `test_shortcuts_registry_coverage.sh` passed; full suite green on **both**
  lanes (`PYTHON SUITE: PASSED (runner=pytest, exit=0)`; serial:
  `3123 passed, 1 skipped`); `./ait minimonitor` booted in an isolated tmux pane
  and rendered its `e/E:shadow` and `c:concerns` bindings with no traceback.

- **Upstream defects identified:** None
