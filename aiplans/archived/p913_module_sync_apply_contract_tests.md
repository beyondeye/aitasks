---
Task: t913_module_sync_apply_contract_tests.md
Worktree: (current branch — profile 'fast')
Branch: main
Base branch: main
---

# Plan: t913 — module_sync apply + scan-bundle contract tests

## Context

`module_sync` (t756_4) added a genuinely new code path with no analog in `crew.py`:
`register_module_syncer` shells out to **real `git log`** (`_sync_touched_files` /
`_sync_scoped_diff`) and to **`aitask_explain_context.sh`** (`_sync_explain_context`)
to bundle three read-only streams for the syncer agent. t756_4's risk evaluation
flagged this subprocess + large-bundle surface as **medium code-health risk**, and
this task (t913) is the "after" mitigation that hardens it.

The existing unit test `tests/test_brainstorm_module_sync.py` covers the happy path
and refusal, but it **stubs all three scan helpers** (`_sync_touched_files`,
`_sync_scoped_diff`, `_sync_explain_context` are `patch`-ed out). So the actual
subprocess/stdout boundary — real `git log --grep=(tN)`, the `--since last_synced_at`
horizon, the 60k truncation cap, and the explain-context shell-out — is **untested**.

Goal: add integration/contract coverage that drives those surfaces *for real*,
paralleling `tests/test_brainstorm_module_ops_integration.py` (t906), which does the
same for decompose/merge — including its Group D `_StubRepo` pattern (subprocess +
stdout-parse boundary against a stubbed `aitask_create.sh`).

## Approach

Add one new self-contained test file:
**`tests/test_brainstorm_module_sync_apply_contract.py`**

No production code changes (issue_type: `test`). It reuses the seeding/import patterns
already established in `tests/test_brainstorm_module_sync.py` and the stub-repo +
cwd-switch pattern from `tests/test_brainstorm_module_ops_integration.py` Group D.

### Functions under test (all existing — REUSE, do not reimplement)

| Function | Location | What the new test exercises |
|----------|----------|-----------------------------|
| `register_module_syncer` | `brainstorm_crew.py:1081` | live scan bundling + refuse guards |
| `_sync_touched_files` | `brainstorm_crew.py:963` | real `git log --grep`, `--since` horizon, existing-path filter |
| `_sync_scoped_diff` | `brainstorm_crew.py:986` | real `git log -p`, `_SYNC_DIFF_MAX_CHARS`=60000 truncation marker |
| `_sync_explain_context` | `brainstorm_crew.py:1011` | stubbed `aitask_explain_context.sh` stdout + unavailable notice |
| `apply_module_syncer_output` | `brainstorm_session.py:1529` | worktree round-trip, single-parent, HEAD advance, `last_synced_at` stamp |
| `_module_syncer_needs_apply` / `_agent_to_group_name` / `_group_subgraph` | session | poller decision contract / group↔agent round-trip |

### Test fixtures

1. **`_seed_base(wt, module_tasks, last_synced)`** — copied/adapted from the unit
   test: seeds `br_graph_state.yaml` + umbrella `n000_init` + (optionally) the
   `parser` module subgraph & HEAD. Used by the apply and refuse groups.

2. **`_GitSyncRepo`** (new context manager, modeled on t906's `_StubRepo`) — for the
   **register/bundling** group, since the scan helpers run from `cwd` (repo root):
   - `tempfile.mkdtemp()`, `git init`, set `user.name`/`user.email` (local config).
   - Commit one or more files with messages containing the `(t756_8)` suffix; control
     commit dates via `GIT_AUTHOR_DATE` / `GIT_COMMITTER_DATE` env for the `--since` test.
   - Seed brainstorm graph state in the same dir (`session_dir` = repo root) via `_seed_base`.
   - Write a stub `.aitask-scripts/aitask_explain_context.sh` (chmod 0755) that prints a
     known marker (or `exit 1` for the unavailable case) — exactly the Group D stub shape.
   - `os.chdir` into it on enter, restore prior cwd on exit (in `__exit__`, exception-safe).
   - In these tests, `_run_addwork` is patched out and `_write_agent_input` is captured to
     inspect the assembled bundle; the **three scan helpers are NOT patched** (run for real).

### Test groups (parallel t906's A–D)

**Group A — apply path round-trip (worktree fixture).** Uses `_seed_base` + `patch`
`brainstorm.brainstorm_session.crew_worktree`. Beyond what the unit test already asserts,
add the genuinely-additive cases:
- `test_apply_round_trip_all_properties`: single apply asserts **all four** at once —
  synced node `parents == [prior_head]` (single parent), `module_label == "parser"`,
  `get_head(module="parser")` advanced, `get_head()` (umbrella) **untouched**, and
  `last_synced_at["parser"]` stamped non-empty. Also assert the group↔agent round-trip
  the poller dispatch relies on: `_agent_to_group_name("module_syncer_001") == "module_sync_001"`.
- `test_resync_advances_from_synced_head`: apply twice; the **second** synced node's
  `parents == [first_synced_id]` and the module HEAD advances again — proving re-sync
  chains off the prior sync, and `last_synced_at` is re-stamped.

**Group B — register live scan bundling (the new subprocess surface).** Uses `_GitSyncRepo`:
- `test_register_bundles_live_git_and_explain`: real commit `(t756_8)` touching `a.py`;
  stub explain prints `EXPLAIN_MARKER`; create `aiplans/p756/p756_8_x.md` with `PLAN_MARKER`.
  Assert bundle (captured `_write_agent_input` content) contains `## Sync Sources`,
  `t756_8`, the real diff hunk for `a.py`, `EXPLAIN_MARKER`, and `PLAN_MARKER`; and that
  `register_module_syncer` returns `module_syncer_001`.
- `test_since_horizon_excludes_pre_sync_commits`: two commits (old `a.py`, new `b.py`)
  with controlled dates; `last_synced_at["parser"]` set between them; assert the bundle's
  scoped diff includes `b.py` but **not** `a.py`. *(Fallback if git `--since` proves
  finicky: assert the `--since` value reached the helper via the existing call-args
  technique used by the unit test — but prefer the end-to-end assertion.)*
- `test_scoped_diff_truncation_cap`: commit a file whose diff exceeds 60000 chars under
  `(t756_8)`; assert the bundle contains `[... scoped diff truncated at 60000 chars ...]`.
- `test_explain_context_unavailable_notice`: stub `aitask_explain_context.sh` exits 1;
  assert bundle contains `(explain-context unavailable:`.
- `test_no_matching_commits_empty_streams`: linked task id with no `(tN)` commits; assert
  the bundle shows the placeholders (`(no scoped changes found since last sync)`).

**Group C — refuse path / decision contract.** Uses `_seed_base` (no git needed — these
raise before the scan helpers):
- `test_refuses_without_linked_task`: `module_tasks={}` → `ValueError` matching
  `"requires a linked task"`.
- `test_refuses_without_source_head`: `module_tasks={"parser":"756_8"}` but no `parser`
  HEAD seeded → `ValueError` matching `"requires a HEAD"`.
- **Scope-honesty docstring** (mirroring t906 Group B's headless-poller note): the wizard's
  `_config_module_sync` Next-disable predicate (`brainstorm_app.py:6349`,
  `disabled = not bool(linked) or not bool(source_head)`) is a Textual App method that
  mounts widgets and cannot run headless. Group C therefore asserts the **two
  raise-conditions in `register_module_syncer` that back that predicate** — not the live
  Button state.

## Rejected alternatives

- **Extracting a pure `_module_sync_allowed(linked, head)` predicate from `brainstorm_app.py`
  to unit-test the disabled state directly.** Rejected: this is a `test`-only task; t906 set
  the precedent of asserting the backing function contract + a scope-honesty note rather than
  refactoring app code. Adding a production predicate would widen blast radius for no behavioral
  gain. Noted here as the deferred option if a future task touches the wizard gating.
- **Adding cases into the existing `test_brainstorm_module_sync.py`.** Rejected: that file is the
  *unit* layer (helpers stubbed); mixing real-subprocess integration fixtures (`git init`, cwd
  switching) into it muddies the unit/integration split. A separate file matches the t906
  unit-file / integration-file separation.

## Risk

### Code-health risk: low
- Test-only change, single new file, follows the established t906 integration-test pattern. The
  only concern is test flakiness from real `git` + cwd switching + commit-date control · severity: low · → mitigation: none (bounded — cwd restore is exception-safe; `--since` test has a documented call-args fallback)

### Goal-achievement risk: low
- Every surface the risk evaluation flagged (apply round-trip, `--since` horizon, 60k truncation, explain-context shell-out, refuse path) is reachable and assertable with the chosen fixtures; the approach is proven by t906 · severity: low · → mitigation: none

## Verification

```bash
# New file passes:
python3 tests/test_brainstorm_module_sync_apply_contract.py
# Existing unit test still passes (no production change, but confirm imports intact):
python3 tests/test_brainstorm_module_sync.py
# Sibling integration test still passes:
python3 tests/test_brainstorm_module_ops_integration.py
```
Expected: all OK. `test_command` is `null` in `project_config.yaml` and `verify_build`
is unset, so Step 9 build verification is skipped. No goldens/`.j2` affected (not a
skill change). Run `/aitask-qa 913` afterward for any further coverage-gap analysis.

## Step 9 (Post-Implementation)
No separate branch (profile 'fast' — current branch). After review/commit, archive via
`./.aitask-scripts/aitask_archive.sh 913` and `./ait git push`.

## Final Implementation Notes
- **Actual work done:** Added `tests/test_brainstorm_module_sync_apply_contract.py`
  (404 lines, 9 tests) exactly as planned — Group A (apply round-trip + re-sync chain),
  Group B (live scan bundling via a real `git init` repo + stubbed `aitask_explain_context.sh`,
  driving `_sync_touched_files` / `_sync_scoped_diff` / `_sync_explain_context` for real),
  Group C (refuse-path decision contract backing the wizard Next-disable predicate).
  No production code changed.
- **Deviations from plan:** None. The `_GitSyncRepo` fixture and the `--since` horizon
  test landed as designed; git's `--since` with pinned `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE`
  proved deterministic, so the documented call-args fallback was not needed. The truncation
  test imports `_SYNC_DIFF_MAX_CHARS` from `brainstorm_crew` rather than hard-coding 60000,
  so the assertion tracks the constant.
- **Issues encountered:** None. All 9 new tests pass; the existing unit test
  (`test_brainstorm_module_sync.py`, 5) and the t906 sibling
  (`test_brainstorm_module_ops_integration.py`, 16) remain green.
- **Key decisions:** Kept this as a separate integration file (not folded into the unit
  test) to preserve the unit/integration split t906 established; asserted the refuse
  contract that backs the wizard predicate rather than refactoring `brainstorm_app.py`
  (test-only task, lowest blast radius).
- **Upstream defects identified:** None
