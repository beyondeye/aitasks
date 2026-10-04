---
Task: t1886_register_sonnet5_5_and_gpt6_1_sol_and_promote_defaults.md
Base branch: main
Output branch: main
---

# t1886 — Register sonnet5_5 / sonnet5_5_1m / gpt6_1_sol and promote defaults

## Context

Claude Sonnet 5.5 (Claude Code 2.1.288) and GPT-6.1 Sol (Codex CLI 0.160.0) are
out. The framework should register them and make each the default wherever its
predecessor (`claudecode/sonnet5`, `codex/gpt6_sol`) is the default today. The
predecessors stay registered. `sonnet5_5_1m` is registered (not promoted) so a
session on the `[1m]` variant self-detects to a real entry instead of the
reserved `unregistered_*` fallback, which the stats writers reject. This mirrors
`opus5_5_1m` (t1884).

**Preconditions re-verified while planning (2026-10-04):**
- `codex debug models | jq -r '.models[].slug'` lists `gpt-6.1-sol`.
- The op lists match the task body exactly:
  - metadata config: sonnet5 → `explain, batch-review, qa, raw,
    brainstorm-comparator, brainstorm-initializer, work-report` (7);
    gpt6_sol → `shadow, discuss` (2).
  - seed config: sonnet5 → `explain, work-report, batch-review, qa, raw` (5);
    gpt6_sol → `shadow, discuss` (2).
- The concurrent-edit barrier is clean: `git status --porcelain` on the 7 main
  paths and `./ait git status --porcelain` on the 3 data paths were both empty.
- A repo-wide grep (excluding archives and the fixture tests the task lists)
  finds the predecessor names only in the seed config, the two docs, Test 28
  (`tests/test_codeagent.sh:542`) and the comment at
  `tests/lib/codeagent_defaults.sh:107`. The shim lines
  `tests/test_codeagent.sh:230/243` are fixture data and are left alone.

## Implementation

All registry and config writes go through `.aitask-scripts/aitask_add_model.sh`
(atomic tempfile, `jq` validation, then `mv`). The JSON is never hand-edited.

1. **Re-check the precondition** right before writing:
   `codex debug models | jq -r '.models[].slug' | grep -qx gpt-6.1-sol`. Stop
   if it is missing. Re-run the porcelain barrier on all 10 paths too.

2. **Register: dry-run, review, then apply.** Each call writes both
   `aitasks/metadata/models_<agent>.json` and `seed/models_<agent>.json`:
   ```bash
   A=./.aitask-scripts/aitask_add_model.sh
   $A add-json --agent claudecode --name sonnet5_5    --cli-id claude-sonnet-5-5 \
     --notes "Best speed/intelligence balance, 1M context, 128K output, adaptive thinking always on"
   $A add-json --agent claudecode --name sonnet5_5_1m --cli-id 'claude-sonnet-5-5[1m]' \
     --notes "Best speed/intelligence balance, 1M context (explicit [1m] variant), 128K output, adaptive thinking always on"
   $A add-json --agent codex      --name gpt6_1_sol   --cli-id gpt-6.1-sol \
     --notes "Latest GPT-6.1 workhorse model for coding and everyday agentic work"
   ```
   Run each with `--dry-run` first. The dry-run should show exactly one
   appended entry per file.

3. **Promote: dry-run, review, then apply.** Each call patches both the
   metadata config and the seed config:
   ```bash
   $A promote-config --agent claudecode --name sonnet5_5 \
     --ops explain,batch-review,qa,raw,work-report,brainstorm-comparator,brainstorm-initializer
   $A promote-config --agent codex --name gpt6_1_sol --ops shadow,discuss
   ```
   The dry-run must show 7 + 5 = 12 sonnet value changes and 2 + 2 = 4 sol value
   changes, every one from `sonnet5` / `gpt6_sol`. The 2 brainstorm keys are
   absent from the seed, and the helper skips them silently there. Do **not**
   run `promote-default-agent-string`: the hardcoded fallback is `opus5_5`.

4. **Hand edits** (the helper does not touch these):
   - `website/content/docs/commands/codeagent.md`:
     - The table rows for `explain`, `work-report`, `batch-review`, `qa` and
       `raw` (lines 54/57/59/60/64) change to `claudecode/sonnet5_5`.
     - The `shadow` and `discuss` rows (lines 61/62) change to
       `codex/gpt6_1_sol`.
     - The example JSON (lines 186–188) changes from `sonnet5` to `sonnet5_5`.
   - `website/content/docs/tuis/codebrowser/how-to.md:199`:
     `claudecode/sonnet5` becomes `claudecode/sonnet5_5`.
   - `tests/test_codeagent.sh` Test 28 (lines 539–542): replace the literal
     assertion with the t1318 derive idiom Test 5 already uses (the
     `seed_cfg` variable is already in scope from line 131):
     ```bash
     # Test 28: resolve explain returns the SEEDED explain default — derived, never pinned
     echo "--- Test 28: resolve explain ---"
     seeded_explain=$(codeagent_config_default explain "$seed_cfg")
     assert_exit_zero "seed config declares an explain default" test -n "$seeded_explain"
     sentinel=$(codeagent_sentinel_excluding "$TMPDIR_TEST/aitasks/metadata" "$seeded_explain")
     assert_exit_zero "a sentinel agent string is available for explain" test -n "$sentinel"
     output=$(cd "$TMPDIR_TEST" && DEFAULT_AGENT_STRING="$sentinel" bash "$CODEAGENT" resolve explain 2>&1)
     assert_eq "resolve explain matches the seeded default" \
         "$seeded_explain" "$(codeagent_resolve_field AGENT_STRING "$output")"
     ```
     Check at implementation time whether earlier tests overwrote the
     fixture's `codeagent_config.json` (Test 25c restores
     `project_config.yaml` only). If a test did, re-derive from the fixture's
     installed config instead of `$seed_cfg`.
   - `tests/lib/codeagent_defaults.sh:107`: change the comment
     `codex/gpt6_sol today` to `codex/gpt6_1_sol today`.

5. **Link check:** `cd website && python3 check_links.py --build`.

## Verification

- Bash tests: `tests/test_codeagent.sh`, `test_codeagent_work_report.sh`,
  `test_codeagent_discuss.sh`, `test_add_model.sh`,
  `test_shadow_spawn_learner.sh`, `test_resolve_detected_agent.sh`. All must be
  green. Exploration baselines were 199/199, 29/29 and 35/35.
- Python: `bash tests/run_all_python_tests.sh`. Read only the last-line verdict
  (`set -o pipefail` if piping).
- Behaviour:
  - `aitask_codeagent.sh resolve explain` gives
    `AGENT_STRING:claudecode/sonnet5_5` and `CLI_ID:claude-sonnet-5-5`.
  - `resolve shadow` and `resolve discuss` give `codex/gpt6_1_sol` and
    `gpt-6.1-sol`.
  - Every other op is unchanged versus `HEAD`. Use `jq -S .defaults` on the
    `HEAD` and live configs (metadata via `./ait git show HEAD:…`, seed via
    `git show HEAD:…`) and confirm the diff is exactly the promoted keys.
  - `aitask_resolve_detected_agent.sh --agent claudecode --cli-id
    'claude-sonnet-5-5[1m]'` gives `claudecode/sonnet5_5_1m`. The same with
    `--agent codex --cli-id gpt-6.1-sol` gives `codex/gpt6_1_sol`.
- After the commits, re-verify against the committed revisions (`git show
  <sha>:path`, `./ait git show <sha>:path`).
- Negative control for Test 28: run with `AIT_CODEAGENT_FIXTURE_OMIT_OPS=explain`.
  The assertion must turn red.

## Commit layout

Path-scoped only:
- **Data branch:** `./.aitask-scripts/aitask_task_commit.sh -m "ait:
  Register sonnet5_5/sonnet5_5_1m/gpt6_1_sol and promote to default (t1886)"
  aitasks/metadata/models_claudecode.json aitasks/metadata/models_codex.json
  aitasks/metadata/codeagent_config.json`
- **main:** `git commit -m "feature: Register sonnet5_5/sonnet5_5_1m/gpt6_1_sol
  and promote to default (t1886)" -- seed/models_claudecode.json
  seed/models_codex.json seed/codeagent_config.json
  website/content/docs/commands/codeagent.md
  website/content/docs/tuis/codebrowser/how-to.md tests/test_codeagent.sh
  tests/lib/codeagent_defaults.sh`. The body must call out the seed behaviour
  change: freshly seeded projects now default the sonnet ops to `sonnet5_5` and
  shadow/discuss to `gpt6_1_sol`.

Then Step 9 (Post-Implementation): archival via the task-workflow.

## Out of scope

- OpenCode catalogs (`ait opencode-models --sync-seed`).
- `gpt-6-astra` (candidate follow-up).
- `aidocs/framework/model_reference_locations.md` (t1341).
- `aidocs/codeagents/claudecode_builtin_prompts.md`.

## Risk

### Code-health risk: low
None identified. The registry and config writes go through the existing atomic
helper, and the hand edits are 2 doc files, 1 test block converted to the
established derive idiom, and 1 comment. A repo-wide grep shows no script or
non-fixture test that pins the predecessor names.

### Goal-achievement risk: low
None identified. Both CLI IDs were verified against the live CLIs during
planning, and are re-checked before writing. The op lists re-derived from
`.defaults` match the task. Self-detection of the `[1m]` variant is covered by
the explicit `sonnet5_5_1m` registration.

## Final Implementation Notes
- **Actual work done:** Registered `claudecode/sonnet5_5` (`claude-sonnet-5-5`),
  `claudecode/sonnet5_5_1m` (`claude-sonnet-5-5[1m]`) and `codex/gpt6_1_sol`
  (`gpt-6.1-sol`) in both the metadata and seed registries via
  `aitask_add_model.sh add-json`. Promoted `sonnet5_5` for 7 metadata ops / 5
  seed ops and `gpt6_1_sol` for `shadow`/`discuss` in both configs via
  `promote-config`. Hand-edited the `codeagent.md` table + example JSON and the
  codebrowser how-to `qa` default, converted `test_codeagent.sh` Test 28 to the
  t1318 derive idiom (seed default + injected sentinel `DEFAULT_AGENT_STRING`,
  exact-field `assert_eq`), and refreshed the `codeagent_defaults.sh` comment.
- **Deviations from plan:** None. The dry-runs showed exactly one appended entry
  per registry file, and 12 sonnet + 4 sol value changes all from the
  predecessors.
- **Issues encountered:** None. Test 28 needed no fixture re-derivation: the
  fixture's project config stays the seed copy, and the earlier tests only
  write and remove `codeagent_config.local.json`.
- **Key decisions:** Test 28 reuses Test 5's `seed_cfg`, and its sentinel
  pattern makes "read the config" distinguishable from "fell through to the
  hardcoded default". `test_codeagent.sh` went from 199 to 201 assertions: one
  literal assertion became three.
- **Verification:**
  - Bash tests: `test_codeagent` 201/201, `test_codeagent_work_report` 29/29,
    and `test_codeagent_discuss`, `test_add_model` (58),
    `test_shadow_spawn_learner` (22) and `test_resolve_detected_agent` (55) all
    passed.
  - Python suite: `PYTHON SUITE: PASSED (runner=pytest, exit=0)`.
    `check_links.py --build` passed with `SWEEP: PASSED`.
  - Negative control: `AIT_CODEAGENT_FIXTURE_OMIT_OPS=explain` turns Test 28
    red.
  - Resolution: `resolve explain` gives `sonnet5_5`, and `shadow`/`discuss`
    give `gpt6_1_sol`. Self-detection of `[1m]` gives `sonnet5_5_1m`.
  - The `.defaults` diff versus HEAD contains only the promoted keys.
- **Upstream defects identified:** None
