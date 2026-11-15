---
Task: t1912_2_shared_stats_read_path.md
Parent Task: aitasks/t1912_move_codeagent_stats_to_plumbing_branch.md
Sibling Tasks: aitasks/t1912/t1912_*_*.md
Archived Sibling Plans: aiplans/archived/p1912/p1912_*_*.md
Base branch: main
Output branch: main
plan_verified:
  - claudecode/opus5_5 @ 2026-11-15 17:48
---

# t1912_2: Shared stats read path (plan, verified 2026-11-15)

## Context

Child 2 of t1912. t1912_1 shipped `lib/model_stats_store.py`, a loader over the
plumbing branch `aitask-stats`. That branch is still empty: no writer uses it
until t1912_4. This child routes **every** reader of `usagestats` /
`verifiedstats` through the store, so a later writer cutover (t1912_4) and the
migration (t1912_5) need no further reader edits. While the branch is empty, the
values every reader displays must not change by a single byte, with **one
deliberate exception**. `list-models` `VERIFIED:` now applies parent decision 4's
effective-score rule. A row whose prior is missing or differs from its recorded
`verifiedstats` average therefore shows the derived score instead of the raw
prior. Writers never produce such rows, and the live registry has none
(measured below). Today the fixture's `mixed` row is the only one: its
`VERIFIED:` goes from empty to `pick=95,wrap=80`, which Step 4 pins with an
explicit assertion.

Parent decisions:
- Marker absent ⇒ effective view = file + branch. Marker present ⇒ branch only.
- `verified` stays in the registry as a prior and passes through untouched.

## Verification findings (what changed since the plan was written)

- **Reader inventory is complete.** A repo-wide grep for `verifiedstats|usagestats`
  in `.aitask-scripts` finds only the listed readers. The other hits are the
  writers (`aitask_usage_update.sh`, `aitask_verified_update.sh`) and the registry
  seeders (`aitask_add_model.sh:161,182`, `aitask_opencode_models.sh:165`), which
  write an empty `verifiedstats: {}`. Those belong to t1912_4 / t1912_5.
- **Line numbers now:**
  - `stats_data.py`: `_paths_for` L73, `load_verified_rankings` L521, `load_usage_rankings` L655.
  - picker: `_build_top_all_ops` L397, `_build_top_usage` L427, `_build_options_for_agent` L600 (it re-reads `MODEL_FILES` at L601).
  - `config_utils.load_all_models` L269.
  - settings: `ConfigManager.load_all` L811 (models block L823-838), `_aggregate_verifiedstats` L600, `_populate_models_tab` L4372.
  - `aitask_codeagent.sh` `cmd_list_models` L315 (jq L351-371).
- **`cross_repo_settings._catalog_model_names` (L371) reads `name` only. No change.**
  `model_supersession.py` and `aitask_resolve_detected_agent.sh` likewise need no change.
- **Settings readers all consume `config_mgr.models`:** `_get_verified_label`,
  `_get_all_providers_label`, `_collect_non_default_skill_stats`, `_populate_models_tab`,
  and the picker opened from Settings (L3139). So one overlay in `load_all` covers
  all of them, with no edits to the reader bodies.
- **Picker callers.** Exactly three pass `all_models`:
  - `agent_command_screen.py:890` passes `load_all_models(self._project_root)`;
  - `settings_app.py:3139` passes `config_mgr.models`;
  - `test_brainstorm_guarded_dismiss.py:573`.
  So `_build_options_for_agent` can read `self.all_models[agent]`.
- **Ordering hazard (new).** `mss.merge_stats` builds skills in *sorted* order.
  Several surfaces print skills in dict order: the jq `STATS:` line
  (`to_entries`), the settings Models tab (`vs.items()`), and the all-providers
  aggregate. Overlaying through `merge_stats` would therefore reorder output.
  The overlay must keep the file's skill order. Fixture "mixed"
  (`pick` then `wrap`) plus a deliberately unsorted row pin this.
- **Repo-resolution hazard (new).** `load_agent_stats(root)` re-reads the legacy
  file from `root/<TASK_DIR>/metadata`. That is not always the file the reader
  just parsed. With an absolute `TASK_DIR` (tests) and `project_root=None`, the
  git root would be the cwd, i.e. the real repo, so its branch would merge into a
  fixture. The fix: the overlay takes the legacy stats **from the rows the reader
  already holds**, and the git repo **from the directory those rows were read
  from**.
  - In branch mode, `aitasks/metadata` resolves to the `.aitask-data` worktree,
    whose common dir is `.git`. So `refs/heads/aitask-stats` is the same ref
    (checked: `git -C aitasks/metadata rev-parse --git-common-dir` gives
    `/home/ddt/Work/aitasks/.git`).
- **Effective verified score (review finding, confirmed).** Parent decision 4:
  writers stop updating `verified`; the effective score is
  `round(verifiedstats[skill].all_time.score_sum / runs)` when runs > 0, else the
  prior.
  - The picker (`_build_options_for_agent` L611-628), the settings labels (L2687-2695)
    and the Models tab (L4404-4414) already follow that precedence.
  - The one surface that prints the prior raw is `list-models` `VERIFIED:`
    (`aitask_codeagent.sh` L351). Once branch runs change an average, its
    headline would freeze while `STATS:` moves. It must apply the rule.
  - Measured on the live registry (all three agents): **zero** rows/skills where
    `verified[k]` ≠ the derived `verifiedstats` average with runs > 0, and no
    skill with runs that lacks a prior. So applying the rule is byte-identical
    on real data while the branch is empty.
- **Scaffold dependency (review finding, confirmed).** `model_stats_store` imports
  `model_stats_windows` (L63) and `orphan_ref_store` (L62). The scaffold must copy
  that closure with `copy_lib_py_closure` (`tests/lib/test_scaffold.sh:234`, which
  is transitive), not a hand list.
- `model_stats_windows.current_periods` defaults through the module-level
  `date.today()`. The golden pins it by patching `model_stats_windows.date`;
  the settings labels take no `today` argument.

### Pre-phase (risk mitigations)

1. [characterize_reader_values] **Before any reader edit**, add and commit the
   golden harness:
   - `tests/golden/stats_readers/models_{claudecode,codex,opencode}.json`: a
     fixture covering these cases:
     - bucketed, flat (`{runs, score_sum}`), mixed, and no-stats rows;
     - a row whose skill keys are deliberately unsorted (`wrap`, `explore`, `pick`);
     - a `review` key, so the `batch-review` mapping is covered;
     - stale and current-period dated buckets around `today=2026-11-04`;
     - an `unavailable` row;
     - a `verified` prior with no stats;
     - one cli_id shared across codex and opencode, so all-providers aggregation fires;
     - `usagestats` on several rows.
   - `tests/lib/stats_reader_capture.py`: `capture(root) -> str`. It runs with
     `cwd=root` and patches `model_stats_windows.date` to a fixed `today`.
     Text sections, deterministic:
     1. `load_verified_rankings(root, today)` / `load_usage_rankings(root, today)`:
        every `op/provider/window → (cli_id, display, score?, runs)`.
     2. Picker: `AgentModelPickerScreen(op, all_models=load_all_models(root), today=…)`
        for ops `pick`, `explore`, `batch-review`. Capture `_build_top_all_ops`,
        `_build_top_usage`, and `_build_options_for_agent(a)` for each agent.
        Pre-change, this last call reads the cwd-relative `MODEL_FILES`, the
        same fixture.
     3. Settings: a real `ConfigManager()` (cwd = root; absent config layers read
        as `{}`), then a fake `self` carrying that `config_mgr`. Capture:
        - `_get_verified_label` / `_get_all_providers_label` for every agent/model × op;
        - `_collect_non_default_skill_stats`;
        - `_populate_models_tab`, with `query_one` returning a recording
          container and `settings_app.Static` / `Label` patched to record
          their text.
     4. `bash <repo>/.aitask-scripts/aitask_codeagent.sh list-models <agent>` for
        each agent, plus `--active-only claudecode`, with cwd = root.
   - `__main__` (re)writes `tests/golden/stats_readers/expected.txt`.
   - `tests/test_stats_readers_golden.py`:
     - builds a scratch `git init` project with the fixture under `aitasks/metadata`;
     - asserts `capture()` equals `expected.txt` byte for byte;
     - prints a unified diff on mismatch.
   - Generate the golden on the unmodified tree, run the test green, and commit
     it (`test: …`). t1912_5 reuses it for its post-migration parity check.

## Steps

1. **Overlay helper in `lib/model_stats_store.py`** (stdlib only, never fetches).
   - `overlay_rows(repo, agent, rows) -> list`:
     - `content = _branch_content(repo)`; `branch = content["agents"].get(agent, {})`;
       `marked = agent in content["markers"]`.
     - It returns a new list. A non-dict row, or a row without a string `name`,
       passes through unchanged. Every other row is a shallow copy; per stats key:
       - **marker present:** the branch's entry for this model, or the key is
         removed when the branch has none;
       - **no marker and no branch data** for (model, key): the row's own value
         is kept as is (deep copy, original skill order). This is the
         byte-stability guarantee while the branch is empty;
       - **no marker, with branch data:** if the row's value is a dict, iterate
         its skills in file order (`merge_buckets` for a skill on both sides, a
         deep copy otherwise), then append the branch-only skills in sorted order.
     - The rule is per row, so a duplicate `name` cannot collapse two rows'
       stats. `verified` and every other field pass through. Input is never
       mutated.
   - `overlay_data(repo, agent, data)`: when `data` is a dict whose `models` is a
     list, it returns `{**data, "models": overlay_rows(...)}`; otherwise it
     returns `data` unchanged.
   - Docstrings state the repo rule: `repo` is the directory the rows were read
     from (or the explicit project root), never an ambient cwd.
   - CLI `aitask_model_stats.py overlay --agent A --file F [--root R]`. `--root`
     defaults to `dirname(F)`. The verb prints `overlay_data(...)` as
     `json.dumps(indent=2, ensure_ascii=False)`, preserving key order. An
     unreadable or invalid file gives `STATS_ERROR:usage:…`, exit 2. Add it to
     the docstring verb table.

2. **Convert each reader.**
   - `stats_data.py`: in both rankings loaders, iterate
     `mss.overlay_rows(project_root or metadata_dir, agent, payload.get("models", []))`.
     This applies only when `models` is a list; otherwise keep today's iteration.
     `project_root` is already threaded, and `load_model_cli_ids` is unchanged
     (it reads cli_id only).
   - `config_utils.load_all_models`: overlay each provider's
     `data` with repo = `metadata_path` if given, else `project_root` if given,
     else `meta`. `model_stats_store` is imported lazily inside the function, so
     config_utils' import graph is unchanged.
   - `agent_model_picker._build_options_for_agent`: read
     `self.all_models.get(agent, {}).get("models", [])`. Drop the `MODEL_FILES`
     re-read and the now-unused `_load_json` import. Keep the `MODEL_FILES`
     re-export, which `test_task_dir_module_constants.py` pins. `_build_top_*`
     already read `all_models`, so they need no change.
   - `settings_app.ConfigManager.load_all`: after filtering entry dicts, set
     `"models": mss.overlay_rows(path.parent, provider, filtered)`. The models
     are read-only in Settings: export copies files from disk, never from
     memory.
   - `aitask_codeagent.sh cmd_list_models`: new helper `_list_models_view <agent> <file>`.
     - It prints the overlaid JSON via `"$py" "$SCRIPT_DIR/aitask_model_stats.py"
       overlay --agent "$agent" --file "$models_file"`.
     - When the CLI or a Python is missing (scaffolded tests), it falls back to
       `cat "$models_file"` silently.
     - When the CLI fails, it prints `warn` once and falls back to `cat`.
     - The jq program reads `<<<"$view"`. The line formats stay byte-stable.
   - **`VERIFIED:` applies the effective-score rule** (presentation only; the
     stored prior is never written).
     - Compute the per-skill `$b` all_time bucket once. Use the same
       normalization `STATS:` uses today: bucketed `all_time`, flat
       `{runs, score_sum}`, else `{}`.
     - Then `VERIFIED:` =
       - the prior's keys **in prior order**, each value replaced by
         `(score_sum // 0) / runs | round` when that skill has runs > 0, else
         the prior value;
       - followed by the skills with runs > 0 that the prior lacks, in
         `verifiedstats` order.
     - The rounding (`jq round`) is the same as `STATS:` and the writer's.
     - With writer-consistent data this equals today's output; see the
       measurement above. `STATS:` is unchanged.

3. **Confirm no-change readers:** `cross_repo_settings._catalog_model_names` (names
   only), `model_supersession.py`, `aitask_resolve_detected_agent.sh`. Record it
   in the Final Implementation Notes.

4. **Tests.**
   - `tests/test_model_stats_store.py`, new class `OverlayTests`:
     - empty branch ⇒ identity, compared by `==` and by `list(keys)` order, on an unsorted row;
     - no marker + branch ⇒ summed (`merge_buckets`), file skill order first,
       branch-only skills appended;
     - marker ⇒ branch only, and a key the branch lacks is removed;
     - non-dict, nameless and duplicate-name rows;
     - input is not mutated;
     - `verified` passes through.
   - `tests/test_stats_readers_golden.py`, two more cases on the same fixture:
     - branch stats seeded through `mss.update` (no marker) ⇒ rankings, picker,
       settings and `list-models` show file + branch. The expected values are
       computed independently from the seeded numbers, not from the golden;
     - commit a `migrations/<agent>.json` marker ⇒ those surfaces show branch only.
   - Hostile `TASK_DIR`:
     - Set `TASK_DIR=<absolute decoy>` with `cwd` = a real-branch repo, and call
       `load_all_models(project_root=fixture)`. It shows the fixture's stats and
       none of the cwd repo's branch.
     - Call `stats_data` with `project_root=None` and an absolute `TASK_DIR`
       pointing at a scratch git repo. The overlay reads that repo's branch,
       not the cwd's.
   - `tests/test_agent_model_picker.py` `PerAgentListTests`: build the screen with
     `all_models={"claudecode": models}` instead of patching `MODEL_FILES`. Add a
     case proving it uses the `all_models` it was given: a `MODEL_FILES` decoy
     with different stats must not be read.
   - `tests/test_codeagent.sh`, Test 4c (branch-backed `list-models`).
     - Scaffold: `cp aitask_model_stats.py`, then
       `copy_lib_py_closure "$env" model_stats_store`. The closure brings
       `model_stats_windows` and `orphan_ref_store`; assert the CLI imports
       (`overlay --help` exits 0) before relying on it.
     - Seed the branch through the CLI (`record-verified`), so a model's prior
       (`verified.pick = 95`, file all_time 4 runs / 380) **differs** from the
       effective summed average. Example: 2 branch runs at score 2 (40 each) ⇒
       (380+80)/6 = 77.
     - Assert `STATS:pick(runs 6, avg 77)` and the headline `VERIFIED:pick=77`,
       not the frozen 95.
     - A second skill with a prior and no runs keeps its prior value in place.
     - Commit a `migrations/claudecode.json` marker ⇒ branch only:
       `STATS:pick(runs 2, avg 40)`, `VERIFIED:pick=40`.
   - Existing Test 3 / 4b stay as they are; the CLI is absent there, so they
     exercise the silent fallback. Add one 4b assertion pinning the rule:
     the `mixed` row (empty prior, stats with runs) now shows
     `VERIFIED:pick=95,wrap=80`.
   - Golden fixture constraint: every row with runs > 0 carries a matching
     prior (writer-consistent, like the live registry). The pre-change golden
     then stays byte-identical after the `VERIFIED:` change. The
     prior-differs case lives in Test 4c and in the golden test's summed and
     marker cases, which assert the derived headline.
   - Check `tests/test_agent_model_picker_narrow.py`,
     `test_settings_verifiedstats_windows.py`, `test_aitask_stats_py.py`
     (TestVerifiedRankings / TestUsageRankings) and `test_stats_data.sh`. They
     build in-memory models or use non-git tmp roots, so they need no seam
     change. A non-git root reads as an empty branch (one stderr line); keep
     their assertions.

### Post-phase (risk mitigations)

1. [readers_never_fetch] In `test_stats_readers_golden.py`, put a git wrapper on
   `PATH` that logs every argv. Run the whole `capture()` (all four reader
   families) against a project that has a reachable `origin` with a newer
   `aitask-stats` tip. Assert:
   - no logged call is `fetch`, `ls-remote`, `push` or `remote-*`;
   - the displayed values are the local (older) ones.

   This proves the "TUIs never fetch / no reader calls refresh" claim at the
   process boundary.

## Verification

- `python3 -m pytest tests/test_stats_readers_golden.py -v` passes. The golden
  reproduces byte for byte after every reader edit, and the summed and marker
  cases pass.
  - The golden's fixture is writer-consistent: every prior matches its average.
    So it proves parity for that shape only, not for missing or inconsistent
    priors.
  - That deliberate exception is covered separately: Test 4b's `mixed`
    assertion and Test 4c's prior-differs case pin the changed `VERIFIED:`
    behavior.
- `tests/test_model_stats_store.py`, `test_agent_model_picker.py`,
  `test_agent_model_picker_narrow.py`, `test_settings_verifiedstats_windows.py`,
  `test_aitask_stats_py.py`, `test_cross_repo_settings.py`,
  `test_task_dir_module_constants.py` and `test_brainstorm_guarded_dismiss.py`
  pass.
- `bash tests/test_codeagent.sh` and `bash tests/test_stats_data.sh` pass.
- `shellcheck .aitask-scripts/aitask_codeagent.sh`.
- Full suite: `bash tests/run_all_python_tests.sh`. Read only the last line.

## Step 9

Post-Implementation per task-workflow (current branch, no worktree).

## Risk

### Code-health risk: medium
- The overlay could reorder skills or reshape rows, so a TUI or `list-models` shows different text with an empty branch · severity: medium · → mitigation: inline pre-phase characterize_reader_values
- The overlay could resolve the wrong git repo (cwd vs the metadata dir under an absolute `TASK_DIR`) and merge another repo's branch into a project · severity: medium · → mitigation: none (designed out: legacy stats come from the rows the reader holds, and the repo from the directory they were read from; pinned by the hostile `TASK_DIR` tests in step 4)
- The `_build_options_for_agent` seam change breaks tests that patch `MODEL_FILES` · severity: low · → mitigation: none (step 4 updates them, plus a decoy test)
- `list-models` now depends on Python for the overlay · severity: low · → mitigation: none (silent fallback to the raw file when the CLI or Python is missing; a warning on CLI failure)

### Goal-achievement risk: low
- `list-models` could show a frozen `VERIFIED:` prior next to a moving `STATS:` average once branch runs exist · severity: medium · → mitigation: none (step 2 applies the effective-score rule in the jq presentation; Test 4c asserts a prior that differs from the derived headline)
- A reader path could fetch or refresh, so a TUI pays a network round trip per render · severity: low · → mitigation: inline post-phase readers_never_fetch
- The summed and marker semantics could be wired at some readers but not others · severity: low · → mitigation: none (step 4 runs the summed and marker cases through all four reader families in the same harness as the golden)

Reassessed with both inline phases in place: the levels are unchanged. Code
health stays medium because of the blast radius: six reader sites across three
TUIs and a CLI.

### Planned mitigations
- timing: pre-phase | name: characterize_reader_values | type: test | priority: high | effort: medium | inline_risk: low | added_complexity: medium | addresses: overlay reordering/reshaping displayed reader output | desc: byte-exact golden of every reader family on a fixture, committed before any reader edit; reused by t1912_5
- timing: post-phase | name: readers_never_fetch | type: test | priority: medium | effort: low | inline_risk: low | added_complexity: low | addresses: a reader path fetching/refreshing per render | desc: git argv-logging wrapper across the full reader capture against a newer origin tip; no fetch/ls-remote/push, local values shown

## Final Implementation Notes

- **Actual work done:** All steps and both inline mitigations landed as planned.
  - Pre-phase `characterize_reader_values` was committed on its own before any
    reader edit (`test: Capture a characterization golden …`):
    - fixture `tests/golden/stats_readers/models_*.json`;
    - capture harness `tests/lib/stats_reader_capture.py`, which covers rankings,
      picker, the settings labels and Models tab, and `list-models`;
    - golden `expected.txt` (253 lines) and `tests/test_stats_readers_golden.py`.
  - `lib/model_stats_store.py` gained `overlay_rows` / `overlay_data` (plus the
    `_overlay_key` helper), and the CLI gained the verb
    `aitask_model_stats.py overlay --agent A --file F [--root R]`.
  - Readers converted:
    - `stats_data` `load_verified_rankings` / `load_usage_rankings` (via
      `_effective_rows`);
    - `config_utils.load_all_models`;
    - `agent_model_picker._build_options_for_agent`, which now reads
      `self.all_models`;
    - `settings_app.ConfigManager.load_all`;
    - `aitask_codeagent.sh list-models`: the new `_list_models_view`, plus jq that
      derives the effective `VERIFIED:`.
  - After every reader edit the golden reproduced byte for byte. The live
    registry's `list-models` output for all three agents was also byte-identical
    old vs new (checked by running the HEAD script copy against `aitasks/metadata`).
- **Deviations from plan:**
  - The `stats_data` rankings now treat a non-dict `models_*.json` payload as
    "no rows". Before, `payload.get` raised `AttributeError`, which was not
    caught. That is a strictly more lenient, display-only path.
  - The `test_codeagent.sh` branch case is named Test 4c (new block), as planned.
    The prior-differs, marker and broken-CLI cases all live there.
- **Issues encountered:**
  - The new branch-backed / hostile-TASK_DIR / no-fetch tests passed on the first
    run, so I ran controls in a scratch worktree at the pre-phase commit:
    - with the old readers, 5/6 fail (only the golden passes, as it must);
    - a mutant with repo = `Path.cwd()` in `stats_data` and `config_utils` fails
      both hostile-TASK_DIR tests;
    - a mutant where `overlay_rows` calls `refresh()` fails `readers_never_fetch`,
      listing the `ls-remote` / `fetch` argv.
  - The scratch worktree was removed afterwards.
- **Key decisions:**
  - The overlay takes the legacy counters from the rows the reader already holds,
    not from a second file read (`load_agent_stats` re-reads
    `root/<TASK_DIR>/metadata`). It takes the git repo from the directory those
    rows came from: an explicit `project_root`, else the metadata dir, never the
    cwd.
  - The overlay preserves file skill order: one-sided skills are deep copies, and
    branch-only skills are appended in sorted order. `merge_stats` would have
    reordered `STATS:` and the Models tab.
  - `VERIFIED:` follows parent decision 4: prior keys stay in prior order, with
    the value replaced by the all_time average when runs > 0, and skills with
    runs but no prior are appended. The stored prior is never written.
  - In `list-models`, the overlay falls back to the raw file: silently when the
    CLI or a Python is missing (scaffolds), with a `warn` on CLI failure.
- **No-change readers confirmed:** `cross_repo_settings._catalog_model_names`
  (names only), `model_supersession.py`, `aitask_resolve_detected_agent.sh`.
- **Upstream defects identified:**
  - `tests/test_screen_recording_cli.py` — 6 tests fail deterministically at HEAD `57b660ff0`, without any t1912_2 change:
    - `AnimMode::test_narrow_roi_sheet_labels_stay_inside_their_cells`;
    - `BugMode::test_layout_reduced_sheets_list_the_frames_they_hold`;
    - `ContactSheets::test_too_many_frames_for_readable_labels_reduce_each_sheet`;
    - `SheetMode::test_hostile_names_are_staged_and_shown_safely`, `test_narrow_tiles_keep_labels_inside_their_cells`, `test_too_many_per_sheet_is_split_with_a_warning`.

    These are contact-sheet label layout assertions, e.g. "1485 not less than or equal to 400 : premise: w_min was measured over these labels" and "64 not less than 64". The cause may be environment-dependent (fonts / ffmpeg build); not diagnosed.
  - `tests/test_aitask_questions.py` — `StoreTests::test_candidate_is_a_remote_client_inside_the_project` and `test_children_are_read_from_every_thread_and_hosting_stops_at_an_app_server` fail at the same HEAD with "stand-in (thread|main) never started its child" (t2281 area). Both also fail in isolation; not diagnosed.
- **Notes for sibling tasks:**
  - **t1912_4 (writers):**
    - Readers already show file + branch, so a writer that starts writing the
      branch is visible immediately, with no reader edit.
    - Writers must stop updating `verified`. `list-models`, the picker and
      settings all derive it from verifiedstats when runs > 0.
    - Seed branch counters in tests through the CLI (`record-verified` /
      `bump-usage --date`), as `test_stats_readers_golden.seed` does.
  - **t1912_5 (migration):**
    - Re-run `tests/test_stats_readers_golden.py` after the migration; it is the
      parity check. Capture before and after with
      `stats_reader_capture.py <root>` on the real registry, too.
    - A marker drops every stats key the branch lacks for that model. A model
      whose counters were not absorbed would therefore show only its prior.
    - The golden fixture is writer-consistent (prior == average). Inconsistent
      priors are covered by `test_codeagent.sh` 4b / 4c.
  - **Any new reader:** call `model_stats_store.overlay_rows(<dir the rows came
    from or explicit root>, agent, rows)`. Never read `usagestats` /
    `verifiedstats` from the file directly, and never pass the cwd.
  - Scaffolds that need the store use
    `copy_lib_py_closure <repo> model_stats_store` plus
    `cp aitask_model_stats.py`. The closure includes `model_stats_windows` and
    `orphan_ref_store`.
