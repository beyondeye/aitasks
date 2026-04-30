---
Task: t718_pypy_optional_runtime_for_tui_perf.md
Worktree: (none — current branch)
Branch: main
Base branch: main
---

# Plan: t718 — PyPy optional runtime for TUI performance (parent split plan)

## Context

`aidocs/python_tui_performance.md` (created by t718's predecessor analysis) identifies PyPy as the single biggest lever for board + codebrowser + other long-running Textual TUIs because Textual itself (pure Python) participates in PyPy's JIT speedups, which AOT options like mypyc/Nuitka cannot offer. The codebase is already PyPy 3.11 compatible (no PEP 695 syntax, no `tomllib`, no `typing.override`; `from __future__ import annotations` everywhere). The challenge is wiring PyPy in *additively*: keep CPython as the default for short-lived CLI scripts and the monitor/minimonitor (which is `fork+exec`-bound and gains ~0% from PyPy — handled by sibling task t719), and route only the long-running TUIs through PyPy when the user opts in.

The user confirmed this is high-effort and asked to **split into child tasks, building and testing the infrastructure first, then wiring the TUIs**. They also clarified two ambiguities in the original task description:

- The original "switch `aitask_stats.sh`" was a typo — that script is a one-shot CLI; the long-running stats TUI is `aitask_stats_tui.sh`. **Switch the TUI variant**.
- `aitask_brainstorm_tui.sh` was missing from the touchpoint list but is a long-running Textual TUI in the same class as board/codebrowser — **include it in the fast-path list**.

## Approach: split into 3 children + 1 doc child

The plan has natural cleavage between (a) plumbing PyPy alongside CPython without touching any caller, and (b) flipping caller scripts to use the fast path. Splitting along that line lets us land + test the infrastructure with no behavior change for anyone, then flip TUIs in a second commit, with docs as a final step.

```
t718_1  PyPy infrastructure (setup helpers + venv + resolver + --with-pypy flag)
        ├─ depends on: nothing
        └─ verifiable in isolation: ait setup --with-pypy installs PyPy venv;
           require_ait_python_fast() returns PyPy when AIT_USE_PYPY=1;
           bash install.sh --dir /tmp/scratch end-to-end test passes.

t718_2  Wire long-running TUIs to require_ait_python_fast
        ├─ depends on: t718_1
        ├─ scripts switched: aitask_board.sh, aitask_codebrowser.sh,
        │                    aitask_settings.sh, aitask_stats_tui.sh,
        │                    aitask_brainstorm_tui.sh
        └─ scripts confirmed unchanged: aitask_monitor.sh,
                                          aitask_minimonitor.sh,
                                          aitask_stats.sh (CLI),
                                          all other CLI scripts
                                          (aitask_pick.sh, aitask_create.sh, etc.)

t718_3  Documentation
        ├─ depends on: t718_1, t718_2 (so behavior is final before docs land)
        ├─ CLAUDE.md shell-conventions: document require_ait_python_fast
        │                               vs require_ait_python
        └─ website docs / README section: AIT_USE_PYPY=1 + --with-pypy flag,
                                          opt-in nature, disk cost,
                                          which TUIs benefit
```

Each child has effort=medium (pure-shell integration, well-bounded touchpoints). The child plans live at `aiplans/p718/p718_{1,2,3}_*.md` and will be written together with the child task files.

## `AIT_USE_PYPY` semantics (decided)

The env var is set **by the user in their shell** when invoking a TUI; the `ait`
dispatcher is **not** modified, and there is no project-config knob. Env vars
pass through `exec` naturally to launcher scripts. `require_ait_python_fast()`
reads `$AIT_USE_PYPY` and falls through to `require_ait_python` when PyPy is
unavailable or explicitly disabled.

| `AIT_USE_PYPY` | PyPy installed? | Result |
|----------------|-----------------|--------|
| `1` | Yes | PyPy (forced) |
| `1` | No | `die`: "Run `ait setup --with-pypy` first" |
| `0` | (any) | CPython (user override) |
| unset / empty | Yes | **PyPy** (default once installed) |
| unset / empty | No | CPython (silent — current behavior preserved) |

The "auto-use PyPy when installed" default is what makes `ait setup --with-pypy`
the user-facing opt-in: once they've installed PyPy, fast-path TUIs route
through it without needing per-invocation env vars. Monitor/minimonitor never
call `require_ait_python_fast` so `AIT_USE_PYPY=1 ait monitor` still uses
CPython — the opt-in is encoded in *which* launchers use the fast resolver.

t718_1 implements `require_ait_python_fast()` with this precedence in
`lib/python_resolve.sh`. t718_2 is then a 5-line edit per launcher.

## Single-source-of-truth for new constants

Per `feedback_single_source_of_truth_for_versions.md`, the new constants must be defined once and reused. The right home is `lib/python_resolve.sh` (already where `AIT_VENV_PYTHON_MIN` lives, already sourced by `aitask_setup.sh`). t718_1 will add:

```bash
# lib/python_resolve.sh
AIT_PYPY_PREFERRED="${AIT_PYPY_PREFERRED:-3.11}"
PYPY_VENV_DIR="${PYPY_VENV_DIR:-$HOME/.aitask/pypy_venv}"
```

`aitask_setup.sh` reads them via the existing source line; no literal paths or version strings duplicated across `aitask_setup.sh` and `python_resolve.sh`.

## Manual verification posture

The TUI launchers can only be meaningfully verified by launching them on PyPy and confirming they render. That's a behavioral check — exactly the case CLAUDE.md's manual-verification flow exists for. After the children are created I will use the manual-verification sibling-creation prompt (see planning.md "Manual verification sibling") to offer adding `t718_4` as an aggregate manual-verification task covering t718_1 (install flow) and t718_2 (TUI render under PyPy).

## Key existing infrastructure to reuse

- `find_modern_python` (`aitask_setup.sh:378`) — pattern for the new `find_pypy()` lookup.
- `install_modern_python` (`aitask_setup.sh:403`) — branches on `OS`; mirrored by `install_pypy()` with `uv python install pypy@3.11` (Linux) / `brew install pypy3` (macOS).
- `setup_python_venv` (`aitask_setup.sh:447`) — creates venv, installs deps, calls wrappers; mirrored by `setup_pypy_venv()` with the same dependency set into `$PYPY_VENV_DIR`.
- `resolve_python` / `require_ait_python` (`lib/python_resolve.sh:37-89`) — pattern for `resolve_pypy_python` / `require_ait_pypy` / `require_ait_python_fast`. The fast-path function honors `AIT_USE_PYPY` and falls back to CPython transparently.
- `main()` (`aitask_setup.sh:3107`) — currently no flag parsing; t718_1 adds a `--with-pypy` flag to the entry point, parsed before `detect_os`.
- `install.sh --dir <scratch>` — exists; used by the t718_1 integration test per CLAUDE.md "Test the full install flow for setup helpers".
- 19 callers of `require_ait_python` (grepped in `.aitask-scripts/aitask_*.sh`) — t718_2 only flips 5 of them, leaving the rest on CPython.

## Verification (parent-level, after all children)

- `bash install.sh --dir /tmp/aitt718 && cd /tmp/aitt718 && ./ait setup --with-pypy` completes; `~/.aitask/pypy_venv/bin/python -c 'import textual'` succeeds.
- Without `--with-pypy`, `./ait setup` is byte-for-byte unchanged from main behavior.
- `AIT_USE_PYPY=1 ./ait board` launches and renders under PyPy (verify via `python -c 'import sys; print(sys.implementation.name)'` from inside the venv equivalent).
- `AIT_USE_PYPY=1 ./ait monitor` is **still** on CPython (intentional — sibling task t719's territory).
- `git revert <t718 commits>` cleanly removes PyPy support without touching CPython behavior.

## Out of scope (recorded for clarity)

- Replacing CPython entirely (Option B in the aidoc — explicitly rejected).
- Any Python 3.12+ syntax — would break PyPy 3.11 fast path.
- Monitor/minimonitor changes — sibling task t719.
- Profiling/benchmarking infrastructure beyond a one-time manual spike.

## Reference

- `aidocs/python_tui_performance.md` — full background analysis.
- Sibling task `t719_monitor_tmux_control_mode_refactor.md` (currently Implementing) — addresses monitor/minimonitor's separate bottleneck class.

## Step 9 (Post-Implementation) note

Each child follows the standard task-workflow Step 9 cleanup/archival flow. The parent (t718) will be auto-archived by `aitask_archive.sh` when the last child is archived (per CLAUDE.md / archival semantics).
