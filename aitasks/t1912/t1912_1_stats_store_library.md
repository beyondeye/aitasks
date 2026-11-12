---
priority: high
effort: high
depends: []
issue_type: feature
status: Implementing
labels: [git, concurrency, verifiedstats, models, robustness]
gates: [risk_evaluated]
active_gates: [risk_evaluated]
active_gates_filtered: []
active_gates_profile: fast
active_gates_digest: 5892c63ff1b4.681bafac2cb9.d73bba2fc21f
assigned_to: dario-e@beyond-eye.com
anchor: 1599
created_at: 2026-11-12 19:41
updated_at: 2026-11-12 20:21
---

## Context

Child 1 of t1912 (move code-agent usage/verified counters off `aitask-data`
onto a plumbing-only orphan branch). Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. Read it first.
Its "Decisions" are user-confirmed:

- **Data model (a): counter files.** These are not per-event files.
- **Hard cutover per agent**, via a migration marker.
- **`verified` stays on `aitask-data` as a registry prior.**

This child builds the store library, its CLI and the refresh routes. Nothing
writes to the store until t1912_4 (writer cutover). Nothing reads it until
t1912_2 (shared read path).

Today the counters live in `aitasks/metadata/models_<agent>.json` (agents:
`claudecode`, `codex`, `opencode`) under `usagestats` / `verifiedstats`.
`lib/verified_update_lib.sh` writes them: it clones origin, commits and
pushes, then converges the shared `.aitask-data` worktree. That cycle is 88%
of the worktree's rebase cycles.

## Goal

Add a store on orphan branch **`aitask-stats`**:

- Writes are a read-modify-write, recomputed on the origin tip on every retry.
- Writes never touch `.aitask-data`'s HEAD, index or worktree.
- A loader serves readers from one store-owned local ref and never fetches.

## Layout (schema 1)

- `<agent>.json`:
  `{"schema": 1, "models": {"<model name>": {"usagestats": {...}, "verifiedstats": {...}}}}`.
  Bucket shape is exactly today's:
  - `usagestats[skill]` = `{all_time:{runs}, prev_month:{period,runs}, month:{period,runs}, week:{period,runs}}`.
  - `verifiedstats[skill]` is the same, with `score_sum` in every bucket.
  - `month` / `prev_month` periods are `%Y-%m`; `week` is ISO `%G-W%V`.
  - An empty `prev_month` is `{"period": "", "runs": 0}`.
- `migrations/<agent>.json`: the per-agent cutover marker. Its content is
  defined by t1912_5; this child only needs to read whether it exists.

## Key files

- NEW `.aitask-scripts/lib/model_stats_store.py`, a stdlib-only library:
  - `bump_usage(blob, model, skill, today)`: port of the jq renderer
    `render_usage_bump` in `.aitask-scripts/aitask_usage_update.sh`
    (~L202-270).
  - `record_verified(blob, model, skill, score_100, today)`: port of
    `render_verified_update` in `.aitask-scripts/aitask_verified_update.sh`
    (~L216-299). It includes the legacy flat `{runs, score_sum}` → bucketed
    conversion, and the score maps 1-5 → ×20.
  - Rollover rule, identical to the jq:
    - if `month.period == current`, keep `prev_month`;
    - else if `month.period == prev_month_target`, `prev_month = old month`;
    - else `{"period": "", "runs": 0}`;
    - month/week restart at 1 (or at the score) on a period change.
  - Return the printed value as today: usage → `month.runs`;
    verified → `round(all_time.score_sum / all_time.runs)`.
  - `merge_buckets(a, b)`, used by t1912_5 absorb and by the legacy overlay:
    - `all_time` adds;
    - month-type buckets (`month` + `prev_month` from both sides) are summed
      per period, then re-slotted around the newest month period;
    - `week` sums on an equal period, otherwise the newer period wins.
  - Write transaction `update(project_root, agent, fn)`:
    - remote PRESENT ⇒ `fetch_pinned` → read `<agent>.json` from the pinned
      tip → `fn` → `build_commit` → `cas_push` with lease on the pinned
      tip. CONFLICT ⇒ re-fetch and recompute (bounded, ~8 attempts,
      jittered). OK ⇒ `advance_ref refs/heads/aitask-stats` to the pushed
      commit, fast-forward only. ERROR ⇒ fail with a diagnostic.
    - remote ABSENT ⇒ create the root commit and push it with an empty
      lease. A local branch that exists while the remote is ABSENT ⇒ push
      local first (like `try_push_local_to_remote` in `aitask_claim_id.sh`
      ~L227-244).
    - local and remote both exist and the local is not an ancestor ⇒ fail
      closed with `STATS_DIVERGED`.
    - no remote ⇒ `cas_local` on `refs/heads/aitask-stats`.
  - `refresh(project_root)`: `probe_remote_branch` → `fetch_pinned` →
    `advance_ref refs/heads/aitask-stats` when the fetched tip descends from
    local, or local is absent. Not an ancestor ⇒ warn `STATS_DIVERGED`, do
    not move. Bounded and non-interactive; it never raises to callers.
  - Loader `load_agent_stats(project_root, agent)` / `load_all_stats(project_root)`:
    - **Reads only `refs/heads/aitask-stats`**, never
      `refs/remotes/origin/aitask-stats`. That ref exists only if
      `remote.origin.fetch` maps it; single-branch clones, restricted
      refspecs and negative `^refs/heads/…` entries leave it missing or
      stale.
    - One `cat-file` batch. **Never fetches.**
    - Marker rule: marker absent ⇒ effective = legacy file stats (from
      `models_<agent>.json`, same path resolution as today's readers:
      `<project_root or cwd>/<TASK_DIR or aitasks>/metadata`) merged with
      branch stats. Marker present ⇒ branch only.
  - **Cache: immutable inputs only.**
    - Cache the parsed branch content keyed by
      `(realpath(git common dir), commit sha)`.
    - Recompute the legacy overlay and the effective merge on **every**
      load. A task-data sync or a legacy writer changes the file without
      moving the stats ref.
    - Never cache effective results.
  - Every git call uses an explicit `cwd` of the repo root. Nothing operates
    on `.aitask-data`.
- NEW `.aitask-scripts/aitask_model_stats.py`, the CLI:
  - verbs `bump-usage --agent --model --skill [--date]`,
    `record-verified --agent --model --skill --score [--date]`, `refresh`,
    `export --agent` (JSON on stdout, for jq consumers in t1912_2),
    `show`;
  - structured single-line outputs, e.g.
    `UPDATED:<agent>/<model>:<skill>:<value>`, `REFRESHED:<sha>`,
    `REFRESH_SKIPPED:<reason>`, `STATS_ERROR:<reason>`.
  - The `migrate` verb comes later, in t1912_5.
- EDIT `.aitask-scripts/lib/orphan_ref_store.py`: parameterize
  `TMP_REF_PREFIX` (L61) and `_FALLBACK_IDENT` (L63-68). Keep the defaults
  byte-identical for relations. Adding keyword arguments or a small
  per-store config object is fine.
- EDIT `.aitask-scripts/aitask_sync.sh`: call the refresh right after
  `do_fetch` (call site ~L2527, defined ~L2042).
  - Best-effort and stderr-only.
  - It must never change the `--batch` stdout status line or the exit code.
    `lib/sync_action_runner.py` parses that wire protocol for the board and
    syncer TUIs.
- EDIT `.aitask-scripts/aitask_pick_own.sh`: refresh in `sync_remote`
  (~L240-260), after `task_sync`. Best-effort.
- EDIT the reserved-ref lists to add `aitask-stats`:
  - `lib/artifact_registry.py:58` `RESERVED_REFS`;
  - `seed/project_config.yaml` ~L357 comment;
  - `settings/settings_app.py` ~L453 help text.
- Python is invoked from bash via `require_ait_python` (`lib/python_resolve.sh`).
  Precedent: `aitask_codeagent.sh` ~L442-448.

## Reference files

- `.aitask-scripts/lib/orphan_ref_store.py`: `probe_remote_branch`,
  `fetch_pinned`, `read_files`, `cat_blobs`, `build_commit`, `cas_push`,
  `cas_local`, `advance_ref`. Its observed-git-behaviour table is in the
  module docstring.
- `.aitask-scripts/lib/relations_store.py`: a policy layer on
  `orphan_ref_store`.
- `aidocs/framework/task_relations.md`, sections "Store API" (L166-207) and
  "Refs" / "Modes".
- `.aitask-scripts/aitask_claim_id.sh` (`aitask-ids`): ABSENT auto-upgrade
  and the local-only branch.
- `.aitask-scripts/lib/model_stats_windows.py`: window rules. It is not
  changed here.
- Memory rules to apply: fast-forward-only shared refs; lease every push on
  the exact base; revalidate on every CAS retry; cache keys cover every
  consumed input.

## Implementation plan

### Pre-phase (risk mitigations)

1. [relations_store_regression_baseline] Before editing
   `lib/orphan_ref_store.py`, run every relations / orphan-store test module
   (`ls tests | grep -E 'relations|orphan_ref'`). Record the result of each
   assertion in the plan file. Re-run after the change: every assertion must
   keep its result. The defaults (`TMP_REF_PREFIX`, ident) stay
   byte-identical.

### Main steps

1. Parameterize `orphan_ref_store.py` while preserving the defaults.
2. Write `model_stats_store.py`: pure functions first, then transaction,
   refresh and loader.
3. Write the `aitask_model_stats.py` CLI.
4. Wire the refresh into `aitask_sync.sh` and `aitask_pick_own.sh`.
   Before any writer exists, the probe answers ABSENT and the refresh is a
   silent no-op.
5. Add the reserved-ref entries.
6. Add tests (below).

The new helper is not invoked by skills until t1912_4, so its whitelist
entries land there.

## Verification

- Unit (Python): bump/record parity against the jq renderers.
  - Run the existing jq writers on the same fixtures with
    `--date YYYY-MM-DD`, so this child's ports are proven equal before
    t1912_4 deletes the jq.
  - Cover rollover across month, ISO week and year boundaries, the legacy
    flat format, and `merge_buckets` cases.
- Concurrency: two clones bump the same agent/model/skill. Force a non-ff
  retry with a deterministic seam hook, not timing ⇒ the totals equal the
  sum and no increment is lost.
- No-remote mode: record and read.
- ABSENT ⇒ auto-create. Local-only branch, then the remote appears ⇒ the
  local tip is pushed. Diverged ⇒ `STATS_DIVERGED`.
- **Cross-clone visibility:**
  - Clone A writes. Clone B reads before refresh ⇒ the old value (proves no
    fetch per render).
  - B runs `ait sync` ⇒ the new value. Repeat separately for
    `aitask_pick_own.sh --sync` and the CLI `refresh`.
  - Run the read-after-refresh case under three fetch configurations: the
    default refspec; a `--single-branch` clone (refspec limited to the code
    branch plus an explicit `aitask-data` mapping); and a negative
    `^refs/heads/aitask-stats` entry.
- `aitask_sync.sh --batch` stdout is byte-identical with the refresh failing
  (unreachable remote).
- **Cache invalidation:**
  - In one process: load ⇒ edit the legacy `models_<agent>.json` counters
    with no stats-ref change ⇒ load ⇒ the new totals.
  - Two projects loaded in the same process ⇒ no key collision.
- `.aitask-data` is untouched by a store write: HEAD, the `ls-files -s` hash
  and `status --porcelain` are byte-identical.
- `shellcheck` on the touched scripts; run the relevant Python and bash tests.

Step 9 (Post-Implementation) applies.
