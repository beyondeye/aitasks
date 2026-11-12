---
priority: high
effort: high
depends: [t1912_4]
issue_type: feature
status: Ready
labels: [git, concurrency, verifiedstats, models, robustness]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-11-12 19:43
updated_at: 2026-11-12 19:43
---

## Context

Child 5 of t1912. Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. Read its
Decisions 3 and 4 and the t1912_5 section; the protocol below is copied from
it and was hardened over three user review rounds. Depends on t1912_1, _2, _3
and _4.

Existing counters in `aitasks/metadata/models_<agent>.json` (`usagestats`,
`verifiedstats`) must move into `aitask-stats` once. They are then stripped
from the registry files, and nothing may re-add them.

User decisions:
- **Hard cutover per agent.** The marker is `migrations/<agent>.json` on
  `aitask-stats`. Loader: marker absent ⇒ file + branch; marker present ⇒
  branch only. Counters an older framework writes after the baseline strip
  are discarded (residue) and never absorbed.
- **`verified` stays** in `models_*.json` as the registry prior. Do not
  strip it.

## Migration protocol: `aitask_model_stats.py migrate [--agent X]`, per agent, with a remote

1. **Marker check.** Refresh `aitask-stats`. A marker for the agent ⇒ go to
   step 6.
2. **Pin the source.**
   - `fetch_pinned` the data branch into a private temp ref ⇒ tip **O**. The
     data branch is the one `current_task_branch` resolves: `aitask-data`,
     or the code branch in legacy mode.
   - Read blob **B** = `O:aitasks/metadata/models_<agent>.json`. **Never use
     the local worktree copy**: it can lag (local 100 runs vs origin 110).
   - Unreachable remote or failed fetch ⇒
     `MIGRATE_DEFERRED:<agent>|unreachable`; nothing written, no marker.
3. **Find the baseline strip — always, whatever B looks like.**
   - Strip commits carry the trailers `Stats-Migration-Agent: <agent>`,
     `Stats-Migration-Kind: baseline|residue` and `Stats-Migration-Id:`.
   - Scan O's history (`git log --reverse --format=%H%x00%(trailers:key=…,valueonly)`)
     and take the **oldest `baseline`** commit for the agent as **S1**.
   - Do this **before** looking at B's keys. Reappeared counters must never
     hide a pending baseline. The race: migrator A strips, then pauses; an
     old writer adds 1 run; migrator B runs.
   - Outcomes:
     - S1 found ⇒ step 5, then step 6 strips B's keys as residue.
     - Not found and B has stats keys ⇒ step 4.
     - Not found and B has none ⇒ marker with `source: none`.
4. **Baseline strip, leased.**
   - Render B without `usagestats` / `verifiedstats`. Use the same `jq`
     pretty-printer the writers use, so formatting stays byte-stable.
   - `build_commit` on parent O changes only that path. The message carries
     the trailers with `Kind: baseline`.
   - `cas_push` to the data branch with lease **O**:
     - OK ⇒ this is **S1**.
     - CONFLICT ⇒ nothing was stripped; restart at step 2 (bounded,
       jittered). Exhaustion ⇒ `MIGRATE_DEFERRED:<agent>|contended`.
     - ERROR ⇒ deferred.
   - **Uniqueness:** a baseline is only pushed against a tip with no
     baseline in its history, and the lease rejects any moved tip. So there
     is at most one baseline per agent.
   - This is a plumbing push. It never touches the local `.aitask-data`
     worktree or index; they catch up via normal sync.
5. **Absorb + marker: one leased commit on `aitask-stats`.**
   - Use `merge_buckets` (t1912_1) to merge the counters of
     **`S1^:models_<agent>.json`** into the branch. That is an immutable
     source, the same for every retry and every migrator.
   - Write the marker
     `{migration_id, strip_commit: S1, source_commit: S1^, source_blob, absorbed_at}`.
   - Recompute from the re-read tip on every retry.
   - A marker already naming S1 ⇒ no-op.
   - A marker naming any other commit ⇒ fail closed with
     `MIGRATE_ERROR:<agent>|marker_mismatch` (defensive; unreachable by
     uniqueness).
6. **Residue.** Stats keys at the current tip once S1 exists are post-S1
   old-framework writes. Strip them the same leased way with `Kind: residue`,
   **never absorb**, and print `STRIPPED_RESIDUE:<agent>|<runs discarded>`.

**No remote:**
- The source is the committed local data-branch HEAD. The worktree file must
  equal that HEAD blob; dirty ⇒ deferred.
- Strip via `ait_cas_rewrite` (`lib/registry_cas.sh`) +
  `./.aitask-scripts/aitask_task_commit.sh` (scoped, with trailers).
- Absorb + marker via `cas_local`.
- Same trailer recovery.

**Transient window:** with no marker, the loader sums file + branch. Between
the strip and the absorb it under-reports for seconds; step 3 recovers it,
and it never double counts.

**Where it runs:**
- `ait setup`: `aitask_setup.sh` main, next to `setup_lock_branch` (~L6225).
- `ait upgrade`: the existing-install hook block in `install.sh`
  (~L1959-1977, using the `declare -F <fn>` pattern from the sourced
  `aitask_setup.sh --source-only`).
- `MIGRATE_DEFERRED` is reported and never fatal; the next setup/upgrade
  retries.
- Read `aidocs/framework/aitasks_extension_points.md` (L449-468) before
  editing setup/install. Test the full `install.sh --dir <scratch>` →
  `ait setup` flow under a scratch `HOME`.

## Registry split: stop re-adding keys

- `aitask_add_model.sh` ~L161 / ~L182: drop `"verifiedstats": {}`; keep
  `"verified": {}`.
- `aitask_opencode_models.sh` ~L165 new-row defaults: drop `verifiedstats`.
  The merge at ~L183-235 carries only what is already on the row (t1919
  note), so it cannot re-add them.
- `--sync-seed` (~L368-375) copies the registry to `seed/`. It must not
  carry stats keys, so strip them on copy.
- `.claude/skills/aitask-refresh-code-models/SKILL.md` Step 6 (~L70-71,
  L113-126): text says preserve/initialize `verified` only. Suggest port
  tasks for the wrappers.
- `seed/models_*.json`: strip `usagestats` / `verifiedstats`, including the
  stale flat entry on `openai_gpt_5_4` in `seed/models_opencode.json`.
- `.aitask-scripts/aitask_install_merge.py` `merge_json_models` (~L105-133):
  drop stats keys from seed-only rows defensively.
- `lib/config_utils.py` export/import (`DEFAULT_EXPORT_PATTERNS` ~L65-70):
  the bundle no longer carries stats. Note this in t1912_6 docs; no code
  change unless an import could re-add keys (then strip them on import).
- `tests/test_metadata_writer_inventory.py`: classify any new writer
  (migrate strip).

## Tests

- **Parity:** the `characterize_reader_values` golden from t1912_2
  reproduces byte-for-byte after migrating the fixture.
- **Stale local vs newer remote:** local holds 100 runs, origin 110 ⇒ 110
  absorbed; the marker names origin's commit.
- **Origin moves between pin and strip** (deterministic seam hook): once
  with an unrelated commit, once with an old-framework stats write ⇒ the
  lease fails, nothing is stripped, and the restart absorbs the newer
  content.
- **Two clones migrate concurrently** ⇒ one baseline, one absorb; totals
  equal the source.
- **Crash after a successful strip, before absorb** (seam) ⇒ the re-run
  recovers S1 by trailer and absorbs exactly once.
- **Baseline-recovery race:**
  - A strips 110 runs into S1 and pauses before absorb (seam).
  - An old-framework write recreates 1 run.
  - B runs to completion ⇒ B absorbs 110 from `S1^`, the marker names S1,
    and the 1 run is stripped as residue (`STRIPPED_RESIDUE:…|1`).
  - A resumes ⇒ no-op. Totals are 110.
  - Also cover: A resumes before B; residue appears after the marker.
- **Baseline uniqueness:** exactly one `Kind: baseline` commit per agent
  across all the race tests.
- Unreachable remote ⇒ `MIGRATE_DEFERRED`: no marker, no strip, loader
  still shows file + branch.
- Idempotent second run.
- No-remote mode, including a dirty file ⇒ deferred.
- Remote-mode migration leaves the `.aitask-data` worktree HEAD and index
  unchanged.
- Updated: `tests/test_add_model.sh`, `tests/test_opencode_models_merge.sh`,
  `tests/test_opencode_models_reserved.sh`, `tests/test_install_merge.sh`.
  Seed-parity tests `test_codeagent_trail.sh` / `test_codeagent_work_report.sh`
  read `verified` and must stay green.

## Verification

- All the above pass.
- shellcheck is clean.
- Python suite verdict is PASSED.
- Run `migrate` on this repo for real at the end and report the per-agent
  outputs. Ask the user before running it, because it pushes to origin.

Step 9 (Post-Implementation) applies.
