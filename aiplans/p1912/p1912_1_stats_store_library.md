---
Task: t1912_1_stats_store_library.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-12 23:20
---

# t1912_1 — Stats store library (plan, verified 2026-11-12)

## Context

Child 1 of t1912. The code-agent counters (`usagestats` / `verifiedstats`) move off
`aitask-data` onto a plumbing-only orphan branch `aitask-stats`, so a stats write
never fetches, rebases or pushes the shared `.aitask-data` worktree (88% of its
rebase cycles today). This child builds only the store library, its CLI, and the
refresh routes. Nothing writes to the store until t1912_4, and nothing reads it
until t1912_2. Full spec: the task file. Parent decisions: data model (a) counter
blobs, hard cutover per agent via `migrations/<agent>.json` marker, `verified`
stays a registry prior (so **the store never writes `verified`**; `record_verified`
only returns the derived average).

## Verification findings (what changed since the plan was written)

- `orphan_ref_store.py`: `TMP_REF_PREFIX` L61, `_FALLBACK_IDENT` L63-68 still
  accurate. Only `fetch_pinned` (L149) and `_commit_env` (L267) read them; no
  other module or test references either constant.
- The jq renderers now run inside `ait_cas_rewrite` (`lib/registry_cas.sh`):
  `render_usage_bump` is `aitask_usage_update.sh` L202-273,
  `render_verified_update` is `aitask_verified_update.sh` L216-300. The bucket
  logic is unchanged. Port subtleties found:
  - jq `null + 1 = 1`; a missing `runs` / `score_sum` / `month` / `week` must
    behave as null (dict `.get`, treat None as 0 in additions, None period ≠ any
    string).
  - The flat legacy entry `{runs, score_sum}` may lack `score_sum` → null →
    `at_sum = mapped`.
  - `.prev_month //= …` replaces null **or false**.
  - A non-dict existing entry (number/string/list) → fresh buckets.
  - The existing `prev_month` object is carried as-is (extra keys kept).
  - The jq writer also sets `.verified[skill] = round(at_sum/at_runs)`. jq
    `round` is half-away-from-zero; Python `round` is banker's. Use
    `math.floor(x + 0.5)` (values are non-negative).
  - The CLI date rule = `model_stats_windows.current_periods(today)` (same
    month / prev calendar month / ISO `%G-W%V` as the bash `date` calls). Reuse
    it; do not re-derive.
- `aitask_sync.sh`: `do_fetch` L2042, call site L2527 — accurate. `do_fetch`
  `exit`s on NO_NETWORK / errors, so a refresh placed after it runs only after a
  successful fetch. `lib/sync_action_runner.py` gives the whole sync a 30 s
  budget (`DEFAULT_SYNC_TIMEOUT_SECONDS`), so the refresh uses a short timeout.
- `aitask_pick_own.sh` `sync_remote` is L241-244 (`task_sync; lock_cleanup`).
- `.aitask-data` is a worktree of the same repository (shared common dir), so
  `refs/heads/aitask-stats` is one ref for both.
- Reserved-ref sites accurate (`artifact_registry.py:58`,
  `seed/project_config.yaml:357`, `settings_app.py:453`). **One more skip list
  found:** `aitask_web_merge.sh:222` `is_skip_branch` — the set the
  `RESERVED_REFS` comment names as its source. Add `aitask-stats` there too.
- Test seam precedent: `relations_store._test_hook(point, **ctx)` (no-op that
  tests monkeypatch). Jitter precedent: `time.sleep(random.uniform(0.05, 0.4) * attempt)`.
- Fixtures to reuse: `tests/lib/sync_fixture.sh` (`setup_repo`, `run_sync`;
  branch-mode clone + bare remote + `aitask-locks`), and
  `tests/lib/metadata_update_fixture.sh` + `test_scaffold.sh` (how
  `test_usage_update.sh` runs the real jq writers in a scratch repo, local-only).

### Pre-phase (risk mitigations)

1. [relations_store_regression_baseline] Before editing
   `lib/orphan_ref_store.py`, run every relations / orphan-store module:
   `tests/test_relations_store.py`, `test_relations_worker.py`,
   `test_relations_consume.py`, `test_relations_config.py`,
   `test_relations_analysis_cli.py` (via
   `python3 -m pytest -v -p no:randomly <file>` or `unittest -v`), plus
   `test_relations_cli.sh`, `test_relations_enqueue.sh`, `test_setup_relations.sh`,
   `test_codeagent_relations.sh`. Record each test id / assertion verdict in a
   `## Baseline` section of the plan file. Re-run after step 1; any changed
   verdict blocks the child.

## Steps

1. **`lib/orphan_ref_store.py` — default-preserving parameters.**
   - `fetch_pinned(repo, ref, timeout, remote="origin", *, tmp_prefix=TMP_REF_PREFIX)`.
   - `_commit_env(repo, extra=None, ident=None)` uses `ident or _FALLBACK_IDENT`.
   - `build_commit(..., extra_parents=(), *, ident=None)` and
     `commit_tree_from_files(..., parents=(), *, ident=None)` pass it through.
   - Module constants unchanged; relations call sites unchanged.

2. **NEW `lib/model_stats_store.py` — pure layer** (stdlib only).
   - Constants: `BRANCH = "aitask-stats"`, `L_REF = "refs/heads/aitask-stats"`,
     `TMP_PREFIX = "refs/aitask-stats/tmp/"`, `IDENT` (`ait stats` /
     `ait-stats@localhost`), `SCHEMA = 1`, `MAX_ATTEMPTS = 8`,
     `DEFAULT_TIMEOUT = 10` (env `AIT_STATS_FETCH_TIMEOUT`).
   - Exceptions: `StatsError(reason)`, `StatsDiverged(StatsError)` (carries
     local/remote shas).
   - `bump_usage(blob, model, skill, today) -> (blob, month_runs)` — faithful port
     of `render_usage_bump` (see findings).
   - `record_verified(blob, model, skill, score_100, today) -> (blob, avg)` —
     port of `render_verified_update` minus the `verified` write; avg =
     `floor(at_sum/at_runs + 0.5)`. `score_100` = raw 1-5 × 20 (CLI maps).
   - Both copy the input (never mutate the caller's dict), create
     `models[model]` / its stats key when missing.
   - `merge_buckets(a, b)`:
     - flat `{runs, score_sum}` is normalized to `all_time` only (it has no
       periods);
     - `all_time` adds `runs` (and `score_sum` when either side is scored);
     - month-type buckets: collect `month` + `prev_month` from both sides with a
       non-empty period, sum per period. `month` = the newest period;
       `prev_month` = the bucket for the calendar month before it, else empty
       `{"period": "", "runs": 0[, "score_sum": 0]}`;
     - `week`: equal period ⇒ sum, else the newer (lexicographic ISO) wins; an
       empty/missing side yields the other;
     - scored ⇔ any input bucket has `score_sum`.
   - `merge_stats(legacy_models, branch_models)`: per model, per stats key, per
     skill: present on one side only ⇒ a deep copy unchanged (keeps today's
     values byte-for-byte while the branch is empty); both ⇒ `merge_buckets`.
   - `parse_blob(bytes)` / `render_blob(obj)`: `{"schema":1,"models":{}}`;
     `json.dumps(sort_keys=True, indent=2) + "\n"`. An unknown schema ⇒
     `StatsError("unsupported_schema")`.

3. **`lib/model_stats_store.py` — git layer.** Every git call passes the
   repo toplevel (`ors.toplevel(project_root)`) as `cwd`. Nothing names
   `.aitask-data`.
   - `update(project_root, agent, fn, *, timeout=None, message=None)`, where
     `fn(blob) -> (blob, value)`. Per attempt (jittered sleep from attempt 1):
     - `local = resolve(L_REF)`.
     - **No remote** (`remote_url` None): base = local → render →
       `build_commit` → `cas_local(L_REF, commit, local)`. CONFLICT ⇒ retry.
     - `probe_remote_branch`: `ERROR:<r>` ⇒ `StatsError(r)`.
     - **ABSENT**: base = local (None ⇒ root commit). This publishes any
       local-only history in the same push. `cas_push` with an empty lease.
     - **PRESENT**: `fetch_pinned(tmp_prefix=TMP_PREFIX)` ⇒ remote. Then:
       - local None, or local an ancestor of remote ⇒ base = remote;
       - remote an ancestor of local (local strictly ahead: fast-forward safe,
         nothing lost) ⇒ base = local;
       - otherwise ⇒ `StatsDiverged` (no retry).
     - `_test_hook("after_pin", attempt=…, base=…)`. Read `<agent>.json` from
       base (`ors.read_file`) → `fn` → `build_commit(base, {path: bytes},
       ident=IDENT)` → `cas_push(commit, BRANCH, lease=remote-or-None)`.
     - CONFLICT ⇒ retry (recompute from the re-read tip). ERROR ⇒
       `StatsError`. OK ⇒ `advance_ref(L_REF, commit)`. A non-ADVANCED result
       is only a warning (the push landed). Return value.
     - Exhaustion ⇒ `StatsError("contended")`.
   - `refresh(project_root, timeout=None) -> (kind, detail)`; never raises
     (catch all → `("skipped", "error:<r>")`). The cases:
     - no remote ⇒ `skipped/no_remote`;
     - probe ERROR ⇒ `skipped/unreachable:<r>`;
     - ABSENT ⇒ `skipped/absent`;
     - fetch error ⇒ `skipped/unreachable:<r>`;
     - local None or local an ancestor of remote ⇒ `advance_ref` ⇒
       `refreshed/<sha>`;
     - remote an ancestor of local ⇒ `refreshed/<local sha>` (local ahead);
     - else ⇒ `diverged/<local>|<remote>` (ref not moved).
   - **Loader** (never fetches, never raises on git failure; a git failure is
     treated as no branch content and reported once on stderr):
     - `_branch_content(root)`: `sha = resolve(L_REF)`; key =
       `(git_common_dir(root), sha)`. On a cache miss: `ors.read_files(root, sha)`
       (one `ls-tree` + one `cat-file --batch`) → parsed
       `{"agents": {agent: models}, "markers": {agent}}`. Bounded dict cache
       (≤16 entries). Only this immutable parse is cached.
     - `_metadata_dir(root, metadata_path=None)`, which keeps each project's
       legacy counters isolated. It copies the root-isolation rule of
       `config_utils.load_all_models` (L293-297) inline, because
       `config_utils` imports `yaml` and this module is stdlib-only. Name the
       source in a comment:
       - `metadata_path` given ⇒ used verbatim; no ambient `TASK_DIR` is read
         (for cross-repo callers);
       - else `rel = Path(os.environ.get("TASK_DIR", "aitasks"))`. When it is
         **absolute**, fall back to `aitasks`; otherwise
         `Path(root) / rel` would discard `root` and read another project's
         file. Return `Path(root) / rel / "metadata"`.
     - `_legacy_models(root, agent, metadata_path=None)`: read
       `models_<agent>.json` from that dir on every call →
       `{name: {"usagestats": …, "verifiedstats": …}}` (only keys present;
       missing or invalid file ⇒ `{}`).
     - `load_agent_stats(root, agent, *, metadata_path=None)`: marker present ⇒
       branch only; else `merge_stats(legacy, branch)`. Returns
       `{model: {"usagestats": {…}, "verifiedstats": {…}}}` (new dicts every
       call).
     - `load_all_stats(root, *, metadata_path=None)`: agents = branch agents ∪
       `models_*.json` in the metadata dir.

4. **NEW `.aitask-scripts/aitask_model_stats.py` CLI** (argparse; `--root`,
   default cwd; adds `lib/` to `sys.path`).
   - `bump-usage --agent --model --skill [--date YYYY-MM-DD]` ⇒
     `UPDATED:<agent>/<model>:<skill>:<month runs>`.
   - `record-verified … --score 1-5 [--date]` ⇒ `UPDATED:…:<avg>`.
   - Validation: agent `^[a-z][a-z0-9]*$`, model `^[a-z0-9_]+$`, skill
     `^[A-Za-z0-9][A-Za-z0-9_.-]*$` (covers every key in use today), score
     `^[1-5]$`, date strict ISO. Bad input ⇒ `STATS_ERROR:usage:<msg>`, exit 2.
   - Write failure ⇒ `STATS_ERROR:<reason>` exit 1; divergence ⇒
     `STATS_DIVERGED:<local>|<remote>` exit 1.
   - `refresh [--timeout N]` ⇒ `REFRESHED:<sha>` | `REFRESH_SKIPPED:<reason>` |
     `STATS_DIVERGED:<l>|<r>`; **always exit 0**.
   - `export --agent X` ⇒ `{"schema":1,"models":{…}}` (the effective, loader
     view) on stdout.
   - `show` ⇒ one line per agent/model/skill:
     `<agent>/<model> <usagestats|verifiedstats> <skill> all_time=<runs>[ avg=<n>]`,
     plus a header with the branch sha and per-agent marker state.
   - All output single-line structured; diagnostics to stderr.

5. **Refresh routes (best-effort, stderr only).** Add to `lib/task_utils.sh`
   (sourced by both callers; no new source-on-startup lib, so the scaffold rule
   does not apply):
   ```bash
   # Best-effort fast-forward of refs/heads/aitask-stats from origin (t1912_1).
   # Never writes stdout, never fails the caller, no-op when the CLI or a Python
   # is missing (scaffolded test repos).
   ait_model_stats_refresh() {
       local cli="$SCRIPT_DIR/aitask_model_stats.py" py out
       [[ -f "$cli" ]] || return 0
       py="$(resolve_python 2>/dev/null || true)"
       [[ -n "$py" ]] || return 0
       out="$("$py" "$cli" refresh --root . --timeout "${AIT_STATS_REFRESH_TIMEOUT:-5}" 2>&1)" || true
       case "$out" in
           REFRESHED:*|REFRESH_SKIPPED:no_remote|REFRESH_SKIPPED:absent|"") ;;
           *) printf 'model-stats refresh: %s\n' "$out" >&2 ;;
       esac
       return 0
   }
   ```
   - `aitask_sync.sh`: call `ait_model_stats_refresh` on the line after
     `do_fetch` (L2527).
   - `aitask_pick_own.sh` `sync_remote`: `task_sync; ait_model_stats_refresh; lock_cleanup`.

6. **Reserved refs:** add `aitask-stats` to `artifact_registry.RESERVED_REFS`,
   the `seed/project_config.yaml` L357 comment, the `settings_app.py` L453 help
   text, and `aitask_web_merge.sh` `is_skip_branch`.

7. **Tests.**
   - NEW `tests/test_model_stats_store.py` (unittest; scratch bare origin +
     clones under a tempdir, `Env` pattern from `test_relations_store.py`):
     - pure: rollover across month, ISO week (2026-12-31 → 2027-W53/W01) and
       year; non-adjacent month gap ⇒ empty prev_month; legacy flat → bucketed;
       null/missing fields; `.5` rounding; `merge_buckets` (equal/different
       weeks, overlapping periods, gap re-slot, flat side, unscored usage);
       `merge_stats` one-sided identity;
     - concurrency: clones A and B bump the same agent/model/skill. A's
       `_test_hook("after_pin")` (patched, fires once) runs B's full `update` ⇒
       A's push CONFLICTs and retries ⇒ all_time runs = 2, and both clones end
       with the same totals;
     - no-remote record + load; ABSENT ⇒ root commit created on origin;
     - local-only commits, then a remote is added (branch absent) ⇒ the next
       write pushes the local history (origin tip descends from the old local
       tip);
     - diverged local/remote ⇒ `StatsDiverged`; `refresh` ⇒ `diverged`, ref
       unmoved;
     - visibility: A writes; B `load` ⇒ old value. A git wrapper on PATH logs
       every git argv, and none of the load's calls is `fetch` / `ls-remote`.
       B `refresh` ⇒ new value. Repeat the refresh under B configs: default
       refspec, `--single-branch` clone + explicit `aitask-data` fetch line,
       and an added `^refs/heads/aitask-stats` negative refspec;
     - cache: load ⇒ edit legacy `models_claudecode.json` counters ⇒ load ⇒
       new totals (same stats sha). Two projects in one process ⇒ independent
       results. Marker present ⇒ legacy ignored;
     - root isolation:
       - Set up roots A and B, each with distinct legacy counters and distinct
         branch counters, and a decoy third directory C holding its own
         `metadata/models_claudecode.json` with yet other counters.
       - Under `TASK_DIR=<absolute C>`: `load_agent_stats(A)` equals A's
         legacy + A's branch, `load_agent_stats(B)` equals B's, and neither
         contains C's counters.
       - Under the relative non-default `TASK_DIR=mytasks` (with
         `<root>/mytasks/metadata` present), each root reads its own
         `mytasks`.
       - `metadata_path=` is honoured verbatim. This is the same
         hostile-environment shape as `tests/test_cross_repo_settings.py`
         L727-728;
     - `.aitask-data` untouched: branch-mode clone, worktree dirtied (modified
       tracked + untracked file), origin `aitask-data` advanced. Before/after a
       store write: HEAD, `ls-files -s` hash and `status --porcelain`
       byte-identical.
   - NEW `tests/test_model_stats_parity.sh`: scratch repo built like
     `test_usage_update.sh` (local-only path, real jq writers with `--date`).
     A date sequence covers same week, new week, new month, month skip and the
     year boundary; it also covers a flat legacy verifiedstats row. After each
     step, compare `jq -S` of the writer's `usagestats`/`verifiedstats[skill]`
     with the Python port fed the same pre-state (driver: `python3 -c` importing
     the module), plus the printed value.
   - NEW `tests/test_model_stats_refresh_routes.sh` (`sync_fixture.sh`):
     - clone A (plain clone of `remote.git`) records via the CLI; the fixture
       clone does not see it until `run_sync --batch`, then sees it. The same
       holds separately for `aitask_pick_own.sh --sync` and for CLI `refresh`;
     - the `--batch` stdout line and exit code are byte-identical between a
       control run and runs where the refresh fails: a held
       `refs/heads/aitask-stats.lock`, a diverged local stats ref, and a broken
       CLI (`aitask_model_stats.py` replaced with `exit 3`);
     - ABSENT ⇒ no stderr noise.
   - Bash tests whose bodies run in subshells opt into
     `assert_counters_init` / `assert_counters_load` (CLAUDE.md t1207).

### Post-phase (risk mitigations)

1. [refresh_timeout_bound] In `test_model_stats_store.py`, write a dedicated
   executable `hang` (`#!/bin/sh` + `exec sleep 30`) into the test tempdir.
   - Point B's origin at `ext::<abs path to hang>`. Do **not** use
     `ext::sh -c "sleep 30"`: the ext transport splits on spaces without
     shell-quote parsing, so that URL fails at once with an EOF error. Assert
     the path has no spaces and skip if it does.
   - Allow the transport with `protocol.ext.allow=always` through the
     `GIT_CONFIG_COUNT` / `KEY_0` / `VALUE_0` env.
   - `ors.probe_remote_branch(..., timeout=1)` returns exactly `ERROR:timeout`.
   - `refresh(timeout=1)` returns exactly `("skipped", "unreachable:timeout")`
     after **≥ 0.9 s** and **< 5 s**. The lower bound and the exact reason
     stop an immediate transport failure from passing as timeout coverage.
   - CLI `refresh --timeout 1` prints `REFRESH_SKIPPED:unreachable:timeout`
     and exits 0 within the same window.
   - Together these prove the sync's 30 s budget can lose at most about twice
     the refresh timeout.

## Verification

- The new tests pass; the relations baseline is unchanged.
- `shellcheck .aitask-scripts/aitask_sync.sh .aitask-scripts/aitask_pick_own.sh .aitask-scripts/lib/task_utils.sh .aitask-scripts/aitask_web_merge.sh`.
- Existing: `test_usage_update.sh`, `test_verified_update.sh`, `test_sync.sh`,
  `test_sync_fetch_exclusion.sh`, `test_pick_own_*.sh`,
  `test_artifact_gitbranch_backend.sh`, `test_relations_*`.
- `bash tests/run_all_python_tests.sh` last line `PYTHON SUITE: PASSED`.

## Step 9

Post-Implementation per task-workflow (current branch, no worktree).

## Risk

### Code-health risk: medium
- Parameterizing the shared `orphan_ref_store.py` could regress the relations store · severity: medium · → mitigation: inline pre-phase relations_store_regression_baseline
- The jq → Python port could drift on null/rounding edge cases before t1912_4 deletes the jq · severity: medium · → mitigation: none (the parity test in step 7 runs the real jq writers)
- The legacy overlay could read another project's `models_*.json` under an absolute `TASK_DIR`, merging foreign counters into an unmigrated project · severity: medium · → mitigation: none (designed out with the `load_all_models` root-isolation rule, pinned by the root-isolation test in step 7)
- The refresh hook in `aitask_sync.sh` / `pick_own --sync` could break their stdout wire protocol · severity: low · → mitigation: none (stderr-only helper; byte-identical `--batch` test with three failure modes)

### Goal-achievement risk: low
- The refresh could add latency that pushes a `--batch` sync past the runner's 30 s budget on a slow remote · severity: low · → mitigation: inline post-phase refresh_timeout_bound
- The loader's return shape is fixed before t1912_2 has adopted it · severity: low · → mitigation: none (t1912_2 may extend the module; the shape mirrors the per-row keys readers already consume)

### Planned mitigations
- timing: pre-phase | name: relations_store_regression_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: orphan_ref_store parameterization regressing relations | desc: per-assertion relations test baseline before/after the parameterization
- timing: post-phase | name: refresh_timeout_bound | type: test | priority: low | effort: low | inline_risk: low | added_complexity: low | addresses: refresh latency pushing a --batch sync past the runner budget | desc: hanging ext:: remote; refresh(timeout=1) returns unreachable:timeout well within bound, CLI exits 0
