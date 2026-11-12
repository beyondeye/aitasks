---
Task: t1912_move_codeagent_stats_to_plumbing_branch.md
Base branch: main
Output branch: main
plan_verified: []
---

# t1912 — Move code-agent stats to a plumbing branch (parent plan: decomposition)

## Context

`usagestats` / `verifiedstats` (and the derived `verified`) live inside
`aitasks/metadata/models_<agent>.json` on `aitask-data`. Every completion writes
them twice through `lib/verified_update_lib.sh`: pre-converge the shared
`.aitask-data` worktree, clone origin, commit, push, post-converge. On one
machine these stats commits are 88% of the rebase cycles of the shared worktree
(task Evidence section), i.e. they open the rebase windows the t1725 bugs live
in. Goal: a stats update never fetches, merges, rebases or pushes `aitask-data`
and never touches its index; readers show the same numbers.

## Decisions (user-confirmed at planning, 2026-11-12)

1. **Data model (a): counter files.** New orphan branch `aitask-stats`, one blob
   per agent: `<agent>.json` = `{"schema": 1, "models": {"<model name>":
   {"usagestats": {...}, "verifiedstats": {...}}}}` in today's exact bucket
   shape (`all_time` / `month` / `prev_month` / `week`, `period` stamps,
   `%Y-%m` and ISO `%G-W%V`). Write = read-modify-write recomputed on the
   origin tip on every retry (leased push, non-ff ⇒ rebuild from re-read tip).
   No per-event files, no compaction. (Task body recommended (b); rejected:
   migration has only aggregates, reads would walk thousands of blobs.)
2. **Publication re-homed per step.** The converge's push side effect is
   removed; every step that relied on it gets its own explicit `./ait git push`.
3. **Hard cutover per agent.** A per-agent migration marker on `aitask-stats`
   (`migrations/<agent>.json`). Loader rule: marker absent ⇒ legacy file stats
   **plus** branch stats (disjoint: branch then only holds post-cutover writes);
   marker present ⇒ **branch only**. The migration source is the
   **authoritative pre-cutover snapshot**: the file at the data branch's
   *freshly fetched origin tip*, never the local worktree copy, which can lag
   (local 100 runs vs origin 110). Order is **strip-then-absorb**, and the
   strip is a leased push against that exact tip, so its success proves no
   newer legacy content existed. The protocol is specified in t1912_5. A re-run
   after the marker strips any residue and warns with the discarded run counts
   (counters an older framework writes after the strip landed are not
   absorbed — accepted by the user).
4. **`verified` stays on `aitask-data` as a registry prior.** Writers stop
   updating it. Effective verified score = derived on read from
   `verifiedstats[skill].all_time` when runs > 0, else the static prior (the
   existing reader fallback order, unchanged). Seeds' hand-set priors and
   `test_codeagent_trail.sh` / `test_codeagent_work_report.sh` parity stay valid.

## Reusable pieces (verified in tree)

- `.aitask-scripts/lib/orphan_ref_store.py` — `probe_remote_branch`,
  `fetch_pinned` (private temp ref, never moves shared refs), `read_files`,
  `cat_blobs`, `build_commit`, `cas_push` (leased, OK/CONFLICT/ERROR),
  `cas_local`, `advance_ref`. Hardcodes `TMP_REF_PREFIX =
  "refs/aitask-relations/tmp/"` and `_FALLBACK_IDENT` → parameterize
  (default-preserving) so relations behaviour is unchanged.
- `.aitask-scripts/lib/model_stats_windows.py` — `resolve_windows`,
  `recent_aggregate`, `current_periods`, `stats_key_for_operation`. Readers keep
  going through it; the store adds only bump / merge / load.
- `.aitask-scripts/lib/registry_cas.sh` (`ait_cas_rewrite`) — the migration
  strip and the registry writers keep using it.
- `aitask_claim_id.sh` — reference for remote-ABSENT auto-create and the
  local-only branch.
- `lib/python_resolve.sh` `require_ait_python` — how bash calls the store CLI
  (precedent: `aitask_codeagent.sh` L442-448).

## Decomposition (children, in dependency order)

Children auto-depend on earlier siblings. Each child plan is written to
`aiplans/p1912/` with full context.

### Pre-phase (risk mitigations)

These are carried into the named child plans as the first steps there, ahead of
any code change in that child:

1. [relations_store_regression_baseline] In t1912_1, before editing
   `lib/orphan_ref_store.py`: run every relations test module
   (`tests/test_relations_*`, `tests/test_orphan_ref_store*`) and record the
   result for each assertion in the child plan. After the parameterization, run
   them again. Every assertion must keep its result, and the default
   `TMP_REF_PREFIX` and identity values must stay byte-identical.
2. [characterize_reader_values] In t1912_2, before touching any reader: build
   a fixture project with bucketed, flat, mixed and no-stats rows across all
   three agents, reusing the `test_codeagent.sh` Test 4b shape. With a pinned
   `today=`, capture a golden of `load_verified_rankings` / `load_usage_rankings`,
   the picker's `_build_top_all_ops` / `_build_top_usage` /
   `_build_options_for_agent` labels, the settings `_get_verified_label` /
   `_get_all_providers_label` / `_populate_models_tab` strings, and the
   `aitask_codeagent.sh list-models` `VERIFIED:` / `STATS:` lines. The golden
   is committed first. The post-switch run on the same fixture must reproduce
   it byte-for-byte, and so must the post-migration run (reused by t1912_5).

1. **t1912_1 `stats_store_library`** — `lib/model_stats_store.py` + CLI
   `aitask_model_stats.py`:
   - layout/schema above; `bump_usage`, `record_verified` (ports of the jq
     renderers in `aitask_usage_update.sh` L202-270 /
     `aitask_verified_update.sh` L216-299, incl. legacy flat → bucketed);
     `merge_buckets` (all_time adds; month-type buckets summed per period then
     re-slotted around the newest month; week summed on equal period else
     newer wins);
   - write loop: `fetch_pinned` → read tip → render → `build_commit` →
     `cas_push`; CONFLICT ⇒ re-fetch and recompute (bounded, jittered);
     success ⇒ `advance_ref refs/heads/aitask-stats`. Remote ABSENT ⇒ create
     the root commit. No remote ⇒ `cas_local` on `refs/heads/aitask-stats`.
     Local-only branch + remote ABSENT ⇒ push local (claim_id-style upgrade);
     both exist and diverged ⇒ fail closed with a diagnostic;
   - **one read ref, moved only by the store:** readers read
     `refs/heads/aitask-stats` and nothing else — never
     `refs/remotes/origin/aitask-stats`, whose presence depends on
     `remote.origin.fetch` (single-branch clones, restricted refspecs, or a
     negative `^refs/heads/…` like the artifact exclusion leave it missing or
     stale; `git fetch origin <branch>` with no destination updates no
     tracking ref under such a refspec);
   - **refresh = `aitask_model_stats.py refresh`** (`model_stats_store.refresh`):
     `probe_remote_branch` → `fetch_pinned` (explicit refspec into a private
     temp ref, independent of the configured fetch refspecs) → fast-forward
     `refs/heads/aitask-stats` via `advance_ref` when the fetched tip descends
     from it (or it is absent). Local not an ancestor ⇒ refuse to move it and
     warn `STATS_DIVERGED` (only reachable after a local-only period; the
     writer's upgrade path resolves it). Bounded, non-interactive, best-effort:
     a failure never fails the caller. **Supported refresh routes** (none of
     them render): (1) every stats write (the writer's fetch + push lands the
     merged tip locally); (2) `aitask_sync.sh` right after `do_fetch` (L2527),
     which also covers the board/syncer TUIs, because `sync_action_runner`
     drives `aitask_sync.sh --batch` — the refresh writes only to stderr and
     never changes the batch status line or exit code; (3)
     `aitask_pick_own.sh --sync` `sync_remote` (L240-260), after `task_sync`;
     (4) the explicit CLI verb. TUIs never fetch;
   - loader `load_agent_stats(project_root, agent)` /
     `load_all_stats(project_root)`: one `cat-file` batch of
     `refs/heads/aitask-stats`, **never fetches**. Applies the marker rule
     (decision 3) and returns the effective per-model
     `{usagestats, verifiedstats}`;
   - **cache covers only immutable inputs.** The in-process cache holds the
     *parsed branch content* only, keyed by `(realpath(git common dir),
     commit sha)`. The cache key includes repo identity because the stats TUI
     loads other projects. The legacy file overlay and the effective merge are
     **recomputed on every load** from the current `models_<agent>.json` — a
     task-data sync or a legacy writer can change the file while the stats
     ref stays put. Effective results are never cached;
   - all git runs against the repo root with an explicit `cwd`; nothing touches
     `.aitask-data`'s HEAD/index/worktree;
   - parameterize `orphan_ref_store` (prefix/ident) + relations regression run;
   - add `aitask-stats` to the reserved-ref lists
     (`lib/artifact_registry.py:58` `RESERVED_REFS`, `seed/project_config.yaml`
     ~L357 comment, `settings/settings_app.py` ~L453 text);
   - wire refresh route (2) into `aitask_sync.sh` and route (3) into
     `aitask_pick_own.sh` here, so cross-machine visibility exists before the
     writer cutover (with no branch on origin yet, the probe answers ABSENT and
     the refresh is a silent no-op);
   - tests:
     - unit: bump/merge/rollover parity against jq fixtures;
     - concurrency: two clones bump the same agent/model/skill concurrently,
       with a forced non-ff retry ⇒ totals equal the sum;
     - no-remote mode: record + read;
     - ABSENT auto-create;
     - **cross-clone visibility:** clone A writes; clone B reads before
       refresh ⇒ old value (proves no fetch per render); B runs `ait sync`
       (and separately `aitask_pick_own.sh --sync` and the CLI verb) ⇒ new
       value. Run the read-after-refresh case under three fetch
       configurations: the default refspec, a `--single-branch` clone (refspec
       limited to the code branch plus an explicit `aitask-data` mapping), and
       a negative `^refs/heads/aitask-stats` entry;
     - `aitask_sync.sh --batch` keeps a byte-identical stdout status line with
       the refresh failing (unreachable remote);
     - **cache invalidation:** one process, load ⇒ edit the legacy
       `models_<agent>.json` counters (no stats-ref change) ⇒ load ⇒ the new
       totals; plus a two-project same-process load proving the keys don't
       collide.
2. **t1912_2 `shared_stats_read_path`** — every reader through the loader:
   `lib/stats_data.py` (`load_verified_rankings` / `load_usage_rankings`),
   `lib/agent_model_picker.py` (`_build_top_all_ops`, `_build_top_usage`,
   `_build_options_for_agent` — also stop re-reading `MODEL_FILES` from disk
   there), `settings/settings_app.py` (`_aggregate_verifiedstats`,
   `_get_verified_label`, `_get_all_providers_label`,
   `_collect_non_default_skill_stats`, `_populate_models_tab`),
   `lib/config_utils.load_all_models` overlay (feeds
   `agent_command_screen.action_change_agent` / board / monitor pickers), and
   `aitask_codeagent.sh cmd_list_models` (jq L350-370: merge a store export via
   `--slurpfile`). One overlay helper: registry rows + loader stats ⇒ the same
   row shape readers consume today, so reader bodies change minimally. Lands
   **before** the writer cutover: with branch empty the loader returns file
   stats ⇒ identical values (parity proven by the pre-phase golden).
   `lib/cross_repo_settings.py` `_catalog_model_names` reads names only —
   confirmed, no change (state it in the child plan).
3. **t1912_3 `rehome_task_data_publication`** — explicit `./ait git push` at
   each step that today publishes only through the stats converge
   (explorer inventory; each re-checked when editing): task-workflow Step 9
   gate-guard "Defer — keep in-flight" (`SKILL.md` ~L1137-1144), child-split
   "Stop here" (`planning.md` ~L317/L332), cross-repo "Stop here"
   (`cross-repo-child-assignment.md` ~L163), explore "save for later"
   (`skill_templates/_auto_continue_block.j2` ~L64), `aitask-qa` Step 7,
   `aitask-docs-gap` Step 6→7, `aitask-add-model` Step 6→7,
   `aitask-refresh-code-models` Step 8→9. Edit `.md.j2` sources, rerender,
   regenerate goldens, run `aitask_skill_verify.sh`. Lands before t1912_4.
   Suggest port tasks for `.agents/` / `.opencode/` where not rendered from the
   same sources.
4. **t1912_4 `stats_writer_cutover`** — `aitask_usage_update.sh` /
   `aitask_verified_update.sh` keep their CLI, validation (agent string, model
   exists in registry — read-only), `--date`, `--silent`, and print
   `UPDATED:<agent>/<model>:<skill>:<value>`; the write goes to the store CLI.
   Delete `commit_metadata_update*`, the clone path, both converges and the
   counter use of `ait_cas_rewrite`; `verified_update_lib.sh` shrinks to the
   remaining helpers (or is removed — check every sourcer). `UPDATED_REMOTE_ONLY`
   disappears for stats (as t1696/t1912 Related anticipates): remove it from
   `task-workflow/satisfaction-feedback.md` (L31-32, L103-104) + goldens; a
   store failure is a warning that never fails the workflow. Register the new
   helper in the 5 whitelist touchpoints
   (`aidocs/framework/aitasks_extension_points.md` L375-394).
   Acceptance test: with `.aitask-data` dirty (modified tracked + untracked)
   and origin ahead, a usage and a verified update leave `.aitask-data` HEAD,
   index (`git ls-files -s` hash) and `status --porcelain` byte-identical, and a
   git wrapper on PATH records no fetch/merge/rebase/push of `aitask-data`.
   Update `test_usage_update.sh`, `test_verified_update.sh`,
   `test_verified_update_flags.sh`, `test_metadata_partial_sync_recovery.sh`
   (stats no longer produce the partial outcome — retarget or retire with a
   stated reason), `tests/lib/metadata_update_fixture.sh`,
   `test_metadata_writer_inventory.py` (L144-145 pins move/retire),
   `test_skill_render_task_workflow.sh` L348-384.
5. **t1912_5 `stats_migration_and_registry_split`** — `aitask_model_stats.py
   migrate [--agent X]` implements decision 3, per agent. With a remote, the
   steps are:
   1. **Marker check.** Refresh `aitask-stats`. A marker for the agent ⇒ skip
      to the residue check (step 6).
   2. **Pin the source.** `fetch_pinned` the data branch (the branch
      `current_task_branch` resolves: `aitask-data`, or the code branch in
      legacy mode) into a private temp ref ⇒ tip **O**. Read blob **B** =
      `O:aitasks/metadata/models_<agent>.json`. Unreachable remote or failed
      fetch ⇒ `MIGRATE_DEFERRED:<agent>|unreachable`; nothing is written and
      no marker is published.
   3. **Find the baseline strip — always, whatever B looks like.** Every strip
      commit carries the trailers `Stats-Migration-Agent: <agent>`,
      `Stats-Migration-Kind: baseline|residue` and `Stats-Migration-Id:`.
      Scan O's history with
      `git log --reverse --format=%H%x00%(trailers:key=…,valueonly)` and take
      the **oldest `baseline`** commit for the agent as **S1**. Do this before
      looking at B's keys: reappeared counters must never hide a pending
      baseline (the A-strips-then-pauses / old-writer-adds-1 / B-runs race).
      - S1 found ⇒ step 5 absorbs from S1, then step 6 strips any keys in B
        as residue.
      - Not found and B has stats keys ⇒ step 4 (baseline strip).
      - Not found and B has none ⇒ nothing to migrate: marker with
        `source: none`.
   4. **Baseline strip, leased.** Render B without `usagestats` /
      `verifiedstats`, using the same `jq` pretty-printer the writers use so
      the formatting stays byte-stable. `build_commit` on parent O changes
      only that path; the message carries the trailers with
      `Kind: baseline`. `cas_push` to the data branch with lease **O**:
      - OK ⇒ this commit is **S1**. The lease proves B was the newest legacy
        content at the cut.
      - CONFLICT (origin moved: an unrelated commit, an old-framework write,
        or a concurrent migrator) ⇒ nothing was stripped; restart at step 2
        with a fresh tip, which re-runs step 3. Bounded and jittered;
        exhaustion ⇒ `MIGRATE_DEFERRED:<agent>|contended`.
      - ERROR ⇒ deferred.

      **Uniqueness:** a baseline strip is pushed only against a tip whose
      history has no baseline for the agent, and the lease rejects any tip
      that moved. A second baseline would need a tip that both lacks S1 and
      equals origin after S1 landed — impossible. So there is at most one
      baseline per agent; every later strip is `residue`.

      This is a plumbing push. It never touches the local `.aitask-data`
      worktree or index, which catch up by normal sync.
   5. **Absorb + marker, one leased commit on `aitask-stats`.** Merge the
      counters of **`S1^:models_<agent>.json`** (exactly what the baseline
      removed: an immutable source, the same on every retry and for every
      migrator) into the branch. Write `migrations/<agent>.json` =
      `{migration_id, strip_commit: S1, source_commit: S1^, source_blob,
      absorbed_at}`. Recompute from the re-read tip on every retry.
      - A marker naming S1 ⇒ no-op (another migrator, or an earlier run,
        absorbed it).
      - A marker naming any other commit ⇒ fail closed with
        `MIGRATE_ERROR:<agent>|marker_mismatch`. This is a defensive check
        only, since uniqueness above makes it unreachable.
   6. **Residue.** Stats keys at the current tip, once S1 exists, are counters
      an older framework wrote after S1. Strip them with the same leased
      procedure, `Kind: residue`; never absorb them. Print
      `STRIPPED_RESIDUE:<agent>|<runs discarded>`. This is the user-accepted
      hard cutover; residue can never replace or shadow the baseline.

   With no remote, the source is the committed local data-branch HEAD. The
   worktree file must equal that HEAD blob; a dirty file ⇒ deferred. Strip via
   `ait_cas_rewrite` + `aitask_task_commit.sh`, then absorb + marker via
   `cas_local`. The same recovery runs from the local strip commit's trailers.

   While no marker exists the loader still adds file and branch counts. In
   the seconds between strip and absorb it therefore under-reports the
   stripped counts. That window is transient and recovered by step 3, and it
   can never double count: the marker is published only with the absorb.

   Runs from `ait setup` (`aitask_setup.sh` main, next to `setup_lock_branch`
   L6225) and from the `ait upgrade` existing-install hook block in
   `install.sh` (~L1959-1977, `declare -F` pattern). A `MIGRATE_DEFERRED`
   result is reported, never fatal; the next setup/upgrade retries. Stop
   re-adding
   keys: `aitask_add_model.sh` L161/L182 (drop `verifiedstats: {}`),
   `aitask_opencode_models.sh` L165 new-row default (t1919 note),
   refresh-code-models `SKILL.md` Step 6 text, strip stats keys from
   `seed/models_*.json` (incl. stale flat entry in `seed/models_opencode.json`),
   `aitask_install_merge.py merge_json_models` drops stats keys from seed rows
   defensively, `--sync-seed` copies without them. Note that config export no
   longer carries stats. Tests:
   - migration fixture parity against the `characterize_reader_values` golden;
   - **stale local vs newer remote:** the local data branch holds 100 runs,
     origin 110 ⇒ 110 absorbed, the marker names origin's commit as the
     source, and the stale local file is ignored;
   - **origin moves between pin and strip:** once with an unrelated commit,
     once with an old-framework stats write ⇒ the lease fails, nothing is
     stripped, and the restart absorbs the newer content;
   - **two clones migrate concurrently** ⇒ one strip, one absorb, totals equal
     the source;
   - **crash after a successful strip, before absorb** (seam hook) ⇒ the
     re-run recovers S1 by trailer and absorbs exactly once;
   - **baseline-recovery race:** migrator A strips 110 runs into S1, then
     pauses before absorb (seam); an old-framework write recreates 1 run;
     migrator B runs to completion ⇒ B absorbs 110 from `S1^`, the marker
     names S1, and the 1 run is stripped as residue
     (`STRIPPED_RESIDUE:…|1`); A resumes ⇒ no-op. Totals are 110. Also run
     the ordering where A resumes before B, and one where the residue
     appears after the marker;
   - **baseline uniqueness:** across all the race tests, the data branch
     history holds exactly one `Kind: baseline` commit per agent;
   - unreachable remote ⇒ `MIGRATE_DEFERRED`: no marker, no strip, and the
     loader still shows file + branch;
   - idempotent second run;
   - residue strip after the marker;
   - no-remote mode, including a dirty worktree file ⇒ deferred;
   - `.aitask-data` worktree HEAD/index unchanged by the remote-mode
     migration;
   - updated suites: `test_add_model.sh`, `test_opencode_models_merge.sh`,
     `test_install_merge.sh`.
6. **t1912_6 `stats_storage_docs`** — website `tuis/settings/reference.md`
   (L204-258), `skills/verified-scores.md`, `skills/aitask-add-model.md`,
   `installation/updating-model-lists.md`, `commands/codeagent.md`;
   aidocs `model_reference_locations.md`, `adding_a_new_codeagent.md`.
   Current-state prose only; run `check_links.py --build`.
7. **t1912_7 `stats_branch_retrospective`** — after ~2 weeks of normal use,
   replay the `.aitask-data` reflog as in the task's Evidence section; report
   rebase cycles / ff converges whose remote-only commits are stats commits
   (expected: none unless the other machine is still old). Follow-ups only if
   the data justifies them.

Cross-task notes to send after children exist: t1678 (stats writers no longer
touch the shared index — do not lock them), t1725 (stats-driven rebase windows
removed by t1912_4).

## Risk

### Code-health risk: high
- Wide blast radius: two writers, five reader stacks (stats, picker, settings, config_utils overlay, codeagent jq), task-workflow/explore/qa/docs-gap/add-model/refresh skills + goldens, setup/install, seeds · severity: high · → mitigation: none (contained by the 7-child decomposition; each child is separately reviewed and tested)
- Parameterizing the shared `orphan_ref_store.py` could regress the relations store · severity: medium · → mitigation: inline pre-phase relations_store_regression_baseline
- Reader switch could silently change displayed numbers (window resolution, `today=` threading, provider aggregation) · severity: medium · → mitigation: inline pre-phase characterize_reader_values
- The stats refresh hooked into `aitask_sync.sh` / `pick_own --sync` could disturb the sync wire protocol or add latency · severity: low · → mitigation: none (stderr-only, bounded, best-effort; the t1912_1 byte-identical `--batch` stdout test with a failing refresh covers it)

### Goal-achievement risk: medium
- Re-homed publication list is a grep inventory; a missed path would silently stop publishing task data once the converge is gone · severity: medium · → mitigation: t2288
- Hard cutover discards counters an older framework writes after the strip lands (user-accepted); a crash between strip and absorb must neither lose nor double count · severity: low · → mitigation: none (strip-then-absorb with the trailer recovery; t1912_5 tests the crash window)
- Migration absorbing a stale local snapshot would hide newer origin counts behind the marker · severity: high · → mitigation: none (designed out: the source is the freshly fetched origin tip, and the strip is a leased push against it; t1912_5 tests stale local vs newer remote, origin moving mid-migration, and concurrent migrators)

### Planned mitigations
- timing: pre-phase | name: relations_store_regression_baseline | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: orphan_ref_store parameterization regressing relations | desc: per-assertion relations test baseline before/after the parameterization (in t1912_1)
- timing: pre-phase | name: characterize_reader_values | type: test | priority: high | effort: low | inline_risk: low | added_complexity: low | addresses: reader switch silently changing displayed numbers | desc: committed golden of every reader's output on a pinned fixture before the switch (in t1912_2, reused by t1912_5)
- timing: after | name: pin_rehomed_push_sites | type: test | priority: medium | effort: medium | inline_risk: low | added_complexity: medium | addresses: a missed publication path after the converge is removed | desc: pinned-inventory test that each re-homed session-ending step carries an explicit ./ait git push after its last task-data commit, with a discovery tripwire for new stop exits (created post-approval as a standalone task depending on t1912_3, since the parent decomposes and never reaches Step 8d) | created: t2288

## Step 9 reference

Parent archival happens after all children are archived (Step 9
Post-Implementation of the last child / parent pick).

## Verification (parent level)

Each child carries its own verification. Parent done when: all children
archived; full `bash tests/run_all_python_tests.sh` verdict line PASSED; the
listed bash suites pass; `aitask_skill_verify.sh` clean; shellcheck clean on
touched scripts.
