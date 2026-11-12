---
priority: high
effort: medium
depends: [t1912_1]
issue_type: refactor
status: Ready
labels: [verifiedstats, models, robustness]
gates: [risk_evaluated]
anchor: 1599
created_at: 2026-11-12 19:42
updated_at: 2026-11-12 19:42
---

## Context

Child 2 of t1912. Parent plan:
`aiplans/p1912_move_codeagent_stats_to_plumbing_branch.md`. It depends on
t1912_1, which provides `lib/model_stats_store.py`: `load_agent_stats` /
`load_all_stats` (a marker-aware effective view) and the CLI `export`.

Today every reader loads `usagestats` / `verifiedstats` / `verified` straight
from `aitasks/metadata/models_<agent>.json`. This child routes **every**
reader through the store loader, before any writer moves (t1912_4). With the
`aitask-stats` branch still empty, the loader returns exactly the file stats,
so the displayed values must not change. Once writers and the migration land,
readers keep working with no further edits.

User-confirmed decisions (parent plan):
- Marker absent ⇒ effective = file stats + branch stats. Marker present ⇒
  branch only.
- **`verified` stays on `aitask-data` as a registry prior.** The effective
  verified score is derived from `verifiedstats[skill].all_time` when
  runs > 0, else the prior. This is the existing reader fallback order.

## Reader inventory to convert (line numbers approximate; re-check)

- `.aitask-scripts/lib/stats_data.py`:
  - `load_verified_rankings(project_root=None, today=None)` (~L521-652);
  - `load_usage_rankings` (~L655-768);
  - path helper `_paths_for` (~L73-85).
- `.aitask-scripts/lib/agent_model_picker.py`:
  - `_build_top_all_ops` (~L397-425) and `_build_top_usage` (~L427-452);
  - `_build_options_for_agent` (~L600-640). This one re-reads
    `MODEL_FILES[agent]` from disk instead of using the `all_models` it was
    given; fix that so it uses the overlaid models.
- `.aitask-scripts/lib/config_utils.py` `load_all_models(project_root, …)`
  (~L262-305). It feeds `lib/agent_command_screen.py`
  `action_change_agent` (~L885-901), which the board, codebrowser,
  brainstorm, monitor, minimonitor, syncer, trails and switcher all use.
- `.aitask-scripts/settings/settings_app.py`:
  - `ConfigManager.load_all` (~L810-846);
  - `_aggregate_verifiedstats` (~L599-637);
  - `_get_verified_label` (~L2675) and `_get_all_providers_label` (~L2703);
  - `_collect_non_default_skill_stats` (~L2730) and `_populate_models_tab`
    (~L4371-4460).
- `.aitask-scripts/aitask_codeagent.sh` `cmd_list_models` (jq ~L350-370).
  It prints `VERIFIED:` from `.verified` and `STATS:op(runs N, avg M)` from
  `verifiedstats[op].all_time` or the flat format. Merge
  `aitask_model_stats.py export --agent <a>` with
  `jq --slurpfile` (or an equivalent), and keep both line formats byte-stable.
- `.aitask-scripts/lib/cross_repo_settings.py` `_catalog_model_names`
  (~L371-390) reads model **names only**. Confirm and state "no change" in
  the plan.
- `model_supersession.py` and `aitask_resolve_detected_agent.sh` read only
  `name` / `cli_id` / `status`. No change.

## Approach

Add one overlay helper, e.g. `model_stats_store.overlay_models(project_root,
agent, rows)` or a `config_utils` wrapper. It takes the registry rows and
returns rows with `usagestats` / `verifiedstats` replaced by the loader's
effective view, so reader bodies change minimally.

- The overlay output keeps the exact row shape readers consume today.
- `verified` passes through from the registry untouched (it is the prior).
- Readers that already accept `project_root` must pass it through, because
  the stats TUI loads other projects.
- Keep `model_stats_windows.py` as the single window-resolution
  implementation.

## Implementation plan

### Pre-phase (risk mitigations)

1. [characterize_reader_values] **Before touching any reader**, build a
   fixture project under `tests/` with bucketed, flat, mixed and no-stats
   rows across all three agents. Reuse the shape of `tests/test_codeagent.sh`
   Test 4b (~L129-162) and add codex/opencode rows plus a `review` key, so
   `batch-review` mapping is covered.

   With a pinned `today=` (e.g. `date(2026, 11, 4)`), capture a golden of:
   - `load_verified_rankings` / `load_usage_rankings`;
   - the picker's `_build_top_all_ops` / `_build_top_usage` /
     `_build_options_for_agent` labels;
   - the settings `_get_verified_label` / `_get_all_providers_label` /
     `_populate_models_tab` strings (a fake `config_mgr`, as in
     `tests/test_settings_verifiedstats_windows.py`);
   - `aitask_codeagent.sh list-models` `VERIFIED:` / `STATS:` lines.

   Commit the golden and its generator first. After the switch, the same
   fixture must reproduce it byte-for-byte. t1912_5 reuses it for the
   post-migration parity check.

### Main steps

1. Overlay helper and tests.
2. Convert each reader.
3. Update tests that patch `MODEL_FILES` or build in-memory models, where the
   overlay changes the seam:
   - `tests/test_agent_model_picker.py`;
   - `tests/test_agent_model_picker_narrow.py`;
   - `tests/test_settings_verifiedstats_windows.py`;
   - `tests/test_aitask_stats_py.py` (TestVerifiedRankings, TestUsageRankings);
   - `tests/test_stats_data.sh`;
   - `tests/test_codeagent.sh` Test 3 / 4b.
4. Golden parity, plus one extra case: a fixture with branch stats seeded
   through the store (marker absent) ⇒ the readers show file + branch summed;
   with a marker ⇒ branch only.

## Verification

- The characterization golden reproduces byte-for-byte.
- The listed Python suites pass:
  `bash tests/run_all_python_tests.sh --test-dir <dir>` or the full suite.
  Read only the last line for the verdict.
- `bash tests/test_codeagent.sh` and `bash tests/test_stats_data.sh` pass.
- TUIs never fetch: no reader path calls `refresh`.

Step 9 (Post-Implementation) applies.
