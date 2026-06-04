---
Task: t935_tests_use_resolve_python_not_bare_python3.md
Worktree: (current branch — profile 'fast')
Branch: (current branch — profile 'fast')
Base branch: main
---

# t935 — Tests use `resolve_python`, not bare `python3`

## Context

The t926 macOS-compat audit ran the test suite on a machine whose system
`python3` lacks the framework's third-party deps (`yaml` / `textual` / `rich`,
which live in the aitask venv at `~/.aitask/venv`). Several bash test harnesses
shell out to framework Python via **bare `python3`** (whatever is first on
`PATH`) instead of the canonical resolver. On such a machine they die with
`ModuleNotFoundError: No module named 'yaml'` / `'textual'` even though the venv
has the deps. The fix: make the affected harnesses resolve the interpreter
through `lib/python_resolve.sh` (prefers the venv), so they pick up the deps
regardless of what the system `python3` is.

The canonical resolver already exists — `.aitask-scripts/lib/python_resolve.sh`
(`resolve_python` / `require_ait_python`). ~27 tests already source it; the
idiom is `source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"; PY="$(require_ait_python)"`
(see `tests/test_skill_render.sh`, `tests/test_applink_smoke.sh`,
`tests/test_skill_verify.sh`). This task extends that idiom to the harnesses the
audit surfaced. No new helper is introduced.

## Scope decision (what to fix vs. deliberately leave)

A blanket `grep python3 tests/*.sh` returns ~30 files, but most must **not**
change. Only harnesses that invoke framework Python importing third-party deps
(verified transitively) are fixed.

**Fix (genuinely fail / silently skip without the venv):**

1. **`tests/run_all_python_tests.sh`** (named in task) — runs `python3 -m pytest`
   / `-m unittest` over `test_*.py` that import board/TUI modules (textual, yaml,
   rich). Lines 15, 16, 19.
2. **`tests/test_crew_report.sh`** (named in task) — runs
   `python3 .aitask-scripts/agentcrew/agentcrew_report.py` (imports
   `agentcrew_utils` → `import yaml`, confirmed at `agentcrew_utils.py:12`).
   Lines 118, 134, 148, 166, 188, 200, 302.
3. **`tests/test_aitask_merge.sh:58`** — already has a venv-preferring
   `TEST_PYTHON` guard (lines 11–17) but `run_merge_with_stderr()` leaks a bare
   `python3`. One-line fix: use the existing `$TEST_PYTHON`.
4. **`tests/test_multi_session_primitives.sh`** — `PYTHONPATH="$LIB_DIR" python3`
   importing `agent_launch_utils` (imports `yaml`). 7 sites (lines 35, 57, 103,
   150, 176, 189, 200).
5. **`tests/test_brainstorm_group_progress_aggregate.sh`** — case 3 imports
   `brainstorm_session` (`import yaml`, line 21); cases 1/2 import
   `brainstorm_app` (textual) and currently **skip** when textual is absent.
   Switching to the venv interpreter gives full coverage *and* fixes the yaml
   failure. 4 sites (lines 28, 80, 141, 185).
6. **`tests/test_update_multiline_yaml.sh:196`** — guards
   `if python3 -c 'import yaml'` then runs the board `task_yaml` serializer; on a
   venv-less `python3` it **silently SKIPs**. Resolving to the venv makes Test 7
   actually run (better coverage), with the SKIP kept as a defensive fallback.

**Leave unchanged (and why):**

- **Resolver / setup / fallback tests — bare `python3` is by design** (they stub
  or probe the system interpreter): `test_python_resolve.sh`,
  `test_python_resolve_pypy.sh`, `test_python_resolution_fallback.sh`,
  `test_setup_find_modern_python.sh`, `test_setup_python_install.sh`.
- **Already prefer the venv**: `test_crew_groups.sh`, `test_crew_runner.sh`,
  `test_crew_status.sh` (`find_python`), `test_brainstorm_cli.sh`.
- **stdlib-only targets — never import third-party deps**: `test_stats_data.sh`
  (`stats/*` has no `yaml`), `test_explain_binary.sh`
  (`aitask_explain_process_raw_data.py` is `sys`/`re`/`OrderedDict` only),
  `test_task_levels.sh` (`task_levels.LEVELS` constant), `test_opencode_setup.sh`
  (`json` only), the tmux harnesses (`test_tmux_control.sh`,
  `test_tmux_control_resilience.sh`, `test_kill_agent_pane_smart.sh`,
  `test_tmux_run_parity.sh`, `test_tmux_exact_session_targeting.sh` — asyncio /
  subprocess; have `PYTHON_BIN` override + SKIP guard).
- **Not an invocation**: `test_codeagent.sh:78` (`python3 -m py_compile` — compile
  only, no imports executed); `test_multi_session_monitor.sh:299` (`"python3"` is
  a fake process-name string in tmux fixture output).

## Implementation

For each fixed harness, add — once, after `PROJECT_DIR` is defined — the
established sourcing idiom, then replace the bare `python3` invocations with the
resolved interpreter. Use `require_ait_python` (matches the dominant test idiom;
dies with a clear `Run 'ait setup'` message rather than a cryptic
`ModuleNotFoundError` if no modern Python exists).

Insert (var name `PY`, except files with an existing var):
```bash
# shellcheck source=.aitask-scripts/lib/python_resolve.sh
source "$PROJECT_DIR/.aitask-scripts/lib/python_resolve.sh"
PY="$(require_ait_python)"
```

Per-file edits:

- **`run_all_python_tests.sh`** — source after line 8 (`PROJECT_DIR`); replace
  the three `python3` at lines 15/16/19 with `"$PY"`.
- **`test_crew_report.sh`** — source after line 8; `replace_all`
  `python3 .aitask-scripts/agentcrew/agentcrew_report.py` →
  `"$PY" .aitask-scripts/agentcrew/agentcrew_report.py` (covers all 7 sites,
  including the two `assert_exit_*` lines 200/302).
- **`test_aitask_merge.sh`** — line 58 only: `python3 aitask_merge.py` →
  `"$TEST_PYTHON" aitask_merge.py` (reuse the file's existing guard var; no new
  sourcing).
- **`test_multi_session_primitives.sh`** — source after `LIB_DIR` (line 23);
  `replace_all` `PYTHONPATH="$LIB_DIR" python3` →
  `PYTHONPATH="$LIB_DIR" "$PY"` (covers all 7 sites; the `TMUX_TMPDIR=…`-prefixed
  ones share this exact substring).
- **`test_brainstorm_group_progress_aggregate.sh`** — uses `REPO_ROOT`; source
  after line 19 with `PY="$(require_ait_python)"` (using `$REPO_ROOT` path);
  `replace_all` `python3 - ` → `"$PY" - ` (4 sites). Keep the existing
  `if spec is None: SKIP` guards as defensive fallback.
- **`test_update_multiline_yaml.sh`** — source after line 20 (`PROJECT_DIR`);
  change the guard `if python3 -c 'import yaml'` → `if "$PY" -c 'import yaml'`
  and the body `python3 - "$PROJECT_DIR"` → `"$PY" - "$PROJECT_DIR"`.

## Verification

- `shellcheck` the six edited harnesses (CLAUDE.md lint convention):
  `shellcheck tests/run_all_python_tests.sh tests/test_crew_report.sh tests/test_aitask_merge.sh tests/test_multi_session_primitives.sh tests/test_brainstorm_group_progress_aggregate.sh tests/test_update_multiline_yaml.sh`
- Run each edited harness on this machine (venv present) — all must still PASS;
  `test_update_multiline_yaml.sh` Test 7 should now run rather than SKIP:
  `bash tests/test_crew_report.sh`, `bash tests/run_all_python_tests.sh`,
  `bash tests/test_aitask_merge.sh`, `bash tests/test_multi_session_primitives.sh`,
  `bash tests/test_brainstorm_group_progress_aggregate.sh`,
  `bash tests/test_update_multiline_yaml.sh`.
- Confirm the resolved interpreter is the venv:
  `AIT_PYTHON= bash -c 'source .aitask-scripts/lib/python_resolve.sh; require_ait_python'`
  → `~/.aitask/venv/bin/python`.
- Original failure environment (cannot reproduce locally — system `python3` here
  also has the deps): on a host where `python3` lacks `yaml`/`textual`, the two
  named harnesses now pass by picking up the venv. The local venv-present run is
  the proxy: each harness must select `~/.aitask/venv/bin/python`, not whatever
  `python3` is on PATH.

See **Step 9 (Post-Implementation)** for cleanup, archival, and merge.

## Risk

### Code-health risk: low
- Mechanical, test-only change applying an already-established framework idiom
  (~27 tests source `python_resolve.sh`); no production code touched · severity:
  low · → mitigation: TBD
- Sourcing `python_resolve.sh` under `set -e`/`set -u`/`pipefail`: the lib guards
  all variable expansions and returns 0, and is already sourced under the same
  flags by existing tests · severity: low · → mitigation: TBD

### Goal-achievement risk: low
- Scope is judgment-based (which files import third-party deps transitively);
  mis-scoping could leave a failing harness or over-touch a deliberately-bare
  one. Mitigated by transitive-import verification and an explicit leave-list
  with reasons · severity: low · → mitigation: TBD
- Cannot reproduce the original `ModuleNotFoundError` locally (this box's
  `python3` has the deps); verified instead by asserting the venv interpreter is
  selected · severity: low · → mitigation: TBD

## Final Implementation Notes

- **Actual work done:** Applied the established `source python_resolve.sh; PY="$(require_ait_python)"`
  idiom to six harnesses and replaced their bare `python3` invocations with `"$PY"`:
  `run_all_python_tests.sh` (3 sites), `test_crew_report.sh` (7 sites, `replace_all`),
  `test_multi_session_primitives.sh` (7 sites), `test_brainstorm_group_progress_aggregate.sh`
  (4 sites), `test_update_multiline_yaml.sh` (Test 7 guard + body + SKIP message).
  `test_aitask_merge.sh` was a one-liner — line 58 leaked a bare `python3` despite the
  file already defining a venv-preferring `TEST_PYTHON`; fixed to use that existing var.
- **Deviations from plan:** None in scope. One mechanical correction during editing:
  a `replace_all` of `python3 - ` → `"$PY" -` in the brainstorm test collapsed the space
  before the heredoc/`"$CREW"` arg (`"$PY" -"$CREW"`); re-fixed all four sites to
  `"$PY" - …` with correct spacing. Verified by re-running the test (4/4 pass).
- **Issues encountered:** Could not reproduce the original `ModuleNotFoundError` on this
  Arch machine — both `~/.aitask/bin/python3` (wrapper) and `/usr/bin/python3` already
  have `yaml`/`textual`. Verified the fix by asserting the resolver selects
  `~/.aitask/venv/bin/python` and that each harness still passes.
  `test_multi_session_primitives.sh` cannot run in this session (its `require_no_tmux`
  guard refuses to run inside tmux — a pre-existing safety guard, unrelated to this
  change); validated the edited Tier-1 invocation standalone instead.
- **Key decisions:** (1) Used `require_ait_python` (not bare `resolve_python`) to match
  the dominant test idiom and fail with a clear `Run 'ait setup'` message rather than a
  cryptic `ModuleNotFoundError`. (2) Deliberately LEFT a large set of `python3` matches
  unchanged — resolver/setup/fallback tests (bare `python3` is by design), stdlib-only
  targets (`stats`, `task_levels`, `explain`, `opencode`, the tmux harnesses), files
  already preferring the venv (`test_crew_*`, `test_brainstorm_cli`), and non-invocation
  string matches. The leave-list with per-file reasons is in the Scope section above.
- **Upstream defects identified:** None. (Two unrelated working-tree changes —
  `tests/test_global_shim.sh` modified and `tests/test_packaging_cleanup.sh` untracked —
  appeared during the session from another process; they were deliberately excluded from
  this task's commit, not authored here.)
