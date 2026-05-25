---
priority: medium
effort: medium
depends: []
issue_type: refactor
status: Implementing
labels: [python, script-performance, ait_setup]
assigned_to: dario-e@beyond-eye.com
created_at: 2026-05-18 12:43
updated_at: 2026-05-25 09:16
boardidx: 100
---

## Motivation

The PyPy fast path (added by t718) was justified by the *theoretical* argument that PyPy speeds up Textual + Rich + user code (often 2-5×). Empirical verification (t718_5, t718_6) found that the actual win is much smaller or negative on this codebase, and that the gap has narrowed further because the installed CPython is now 3.14.4 (adaptive specialization + tail-call interpreter), while PyPy is still on Python 3.11.15 with no stable 3.12 release in sight (v7.3.22, April 2026).

### Empirical evidence (already in `aidocs/python_tui_performance.md`)

| TUI | Verdict | Delta | Source |
|-----|---------|-------|--------|
| Board (KanbanApp) | KEEP | PyPy 13.6% faster steady state; cold-start regresses 153 ms | t718_6 |
| Codebrowser | REVERTED | PyPy 17% slower; cold-start regresses 168 ms | t718_6 |
| Monitor (control-mode path) | REVERTED | PyPy 76-90% slower at 3/8 panes | t718_5 |
| Monitor (legacy fallback path) | REVERTED | PyPy 3.2-7.4× slower | t718_5 |
| Minimonitor | REVERTED | Same as monitor | t718_5 |
| Settings | **NOT MEASURED** — routed by analogy with board | — | t718_2 |
| Brainstorm TUI | **NOT MEASURED** — routed by analogy with board | — | t718_2 |
| Syncer | **NOT MEASURED** — routed by analogy with board | — | t718_2 |
| Stats TUI | Stays on CPython (plotext install gap) | — | t718_2 |

### External evidence (May 2026 web research)

- PyPy still wins on pure-Python compute loops (10-18× on math/recursion) — **not the shape of any aitasks TUI workload**.
- PyPy loses when "JIT cannot help": small per-frame work dispatched through C-accelerated layers (Rich/Textual render path). Matches the codebrowser empirical revert.
- CPython 3.14's experimental JIT in community testing "does not appear to provide significant gains" — so the local CPython is already close to its post-JIT ceiling for this code shape.
- CPython 3.14 free-threaded build is up to 3× faster than standard 3.14 on CPU-heavy multi-threaded workloads — direction CPython is gaining quickly; PyPy is not.
- PyPy team's recent focus is C-extension parity (RPython json encoder, etc.), not Python-version chase.

### Cost of keeping the dual-venv fast path

- ~100-150 MB extra disk in `~/.aitask/pypy_venv/`.
- Separate `plotext` install gap (stats-tui blocked from PyPy because plotext is CPython-only).
- Dual resolver paths (`require_ait_python` vs `require_ait_python_fast`).
- `--with-pypy` install flag, install prompts, AIT_USE_PYPY env-var precedence.
- "Don't adopt Python 3.12+ syntax" constraint persists indefinitely (PEP 695 `type X = ...`, `typing.override`, `tomllib`, etc.).
- macOS install path (t729 follow-up still Ready) — extra surface to maintain.

### Benefit of keeping it

- Board: ~13.6% steady-state win after warmup. Cold-start loses 153 ms. Net positive only for sessions of moderate duration.

## Goal

Retire the PyPy fast path and consolidate on CPython 3.14.4. Trade board's 13.6% steady-state for simpler infrastructure, unblocked Python 3.12+ syntax adoption, and removal of cross-cutting dual-venv plumbing.

## In scope

This task is intentionally large and should likely be split into children at plan time. Surface areas:

1. **Launcher revert** — `aitask_board.sh`, `aitask_settings.sh`, `aitask_brainstorm_tui.sh`, `aitask_syncer.sh`: revert `require_ait_python_fast` → `require_ait_python` (4 files, 1 line each).

2. **Resolver retirement** — remove `require_ait_python_fast` from `.aitask-scripts/lib/python_resolve.sh` (and `_AIT_RESOLVED_PYPY` caching). Remove `require_ait_pypy`. Update all callers.

3. **Install path** — remove `install_pypy`, `setup_pypy_venv`, `_install_pypy_linux`, `_install_pypy_macos` from `aitask_setup.sh`. Remove `--with-pypy` flag and any interactive PyPy install prompt. Remove `~/.aitask/pypy_venv/` if present (offer cleanup on next `ait setup` / `ait upgrade`).

4. **Env var contract** — remove `AIT_USE_PYPY` env-var precedence logic and documentation. Note: this is a user-observable removal; document the deprecation clearly.

5. **Documentation** — rewrite `aidocs/python_tui_performance.md` to reflect the retirement; keep the empirical tables as historical record but flip the "Recommendations" section to "Single-interpreter (CPython 3.14+) consolidation." Update CLAUDE.md TUI Conventions section (`require_ait_python_fast` rule, `AIT_USE_PYPY` precedence table, the `monitor`/`minimonitor`/`codebrowser`/`stats-tui` empirical-verification rules — those targeted *exceptions* become moot when there is no fast path).

6. **Website docs** — `website/content/docs/installation/` and any "PyPy fast path" mention. Per the documentation-current-state-only rule, simply remove PyPy references; do not add "previously…" framing.

7. **Seed configs** — check `seed/` for any PyPy bootstrapping (install hints, config defaults).

8. **Dependent tasks (auto-moot)** — when this lands, the following pending tasks become moot and should be cancelled or archived as "obsoleted by retirement":
   - `t729` — manual_verification_pypy_install_macos_followup
   - `t718_4` — manual_verification_pypy_optional_runtime_for_tui_perf

   These are flagged for surfacing during planning, not folded into this task.

## Out of scope

- Enabling CPython 3.14's experimental JIT (`--enable-experimental-jit`). Available on the installed Python but currently `sys._jit.is_enabled() = False`. External evidence suggests minimal gain; consider a separate exploration task if interest revives. **Trigger to reconsider:** if a future CPython release ships JIT as enabled-by-default with substantiated wins, re-evaluate at that point.
- Free-threaded CPython migration. Not applicable to asyncio-driven TUIs at current bottleneck shape.
- Adopting Python 3.12+ syntax (PEP 695 type statements, etc.). After retirement, this becomes *possible* but should be a separate "modernize to 3.12+ idioms" task — not part of the retirement itself.

## Sequencing & risk

- The board 13.6% loss is the single user-visible regression. Recommend documenting it in the implementation commit message and the website "what's new" section so users searching for "why is board slower?" find the rationale.
- Verify on a fresh install that the simplified `ait setup` flow still completes cleanly on both Linux (uv-managed CPython) and macOS (brew-managed CPython).
- Run `tests/test_*` after the launcher reverts to confirm no test depends on PyPy being present.

## Open questions for planning

1. Should retirement be staged? E.g., first revert the three unverified TUIs (settings, brainstorm, syncer) to CPython, observe for a release, *then* revert board. Alternative: rip the whole path out in one task since the resolver/install/docs touch is the same regardless.
2. For users who already have `~/.aitask/pypy_venv/` populated: silent removal, or one-shot deprecation notice on next `ait` invocation?
3. Should we add a "/aitask-pypy-revisit" trigger document under `aidocs/` so a future contributor knows when to re-evaluate (e.g., PyPy 3.12 stable + ≥10% board win + ≥0% codebrowser parity)?
