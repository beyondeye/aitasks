---
Task: t579_4_update_tests_and_docs_for_opus_4_7.md
Parent Task: aitasks/t579_support_for_opus_4_7.md
Archived Sibling Plans: aiplans/archived/p579/p579_1_audit_refresh_code_models_and_design_add_model_skill.md, aiplans/archived/p579/p579_2_implement_aitask_add_model_skill.md, aiplans/archived/p579/p579_3_add_opus_4_7_as_new_default_using_add_model_skill.md, aiplans/archived/p579/p579_5_externalize_model_defaults.md
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-17 10:43
---

# Plan: t579_4 — Update tests and docs for Opus 4.7 (verified)

## Context

Final child of parent t579 (Opus 4.7 support). t579_3 registered two
Claude Opus 4.7 variants (`opus4_7` standard + `opus4_7_1m` 1M context)
and promoted `opus4_7_1m` to default for 5 operations and for
`DEFAULT_AGENT_STRING`. The `aitask-add-model` skill used in t579_3
intentionally does NOT touch prose docs, test fixtures, or
`aidocs/claudecode_tools.md`. This task consumes t579_3's manual-review
list to finish the rollout — updating default-sensitive test assertions,
adding opus4_7/opus4_7_1m coverage, refreshing docs, and creating the
manual mirror of the new `aitask-add-model` skill in the website.

After this task archives, `aitask_archive.sh` auto-archives parent t579
since all children are complete.

## Verification findings (verify path)

Verified against current codebase on 2026-04-17. Key findings:

1. **Pre-existing bug in `tests/test_codeagent.sh` confirmed.** The
   script currently fails at Test 2 because `task_utils.sh:14` sources
   `archive_utils.sh`, but `setup_test_env()` at line 75 does not copy
   `archive_utils.sh`. `set -e` masks the failure — only "Test 2" appears
   before silent exit 1.

2. **Default-sensitive assertions precisely located** in
   `tests/test_codeagent.sh`:
   - Test 5 (lines 140–144): `resolve pick` → opus4_6 → MUST change to
     `opus4_7_1m` / `claude-opus-4-7[1m]`
   - Test 11 (line 193): `--dry-run invoke pick 42` model flag content
     → MUST change to `claude-opus-4-7[1m]`
   - Tests 15–26 (coauthor tests explicit for opus4_6 / sonnet4_6 /
     haiku4_5): these test metadata for specific models, opus4_6 is
     STILL registered → **keep unchanged**
   - Test 3 (list-models): opus4_6 is still registered → existing
     asserts stay valid. Add parallel asserts for opus4_7 and
     opus4_7_1m presence.

3. **`tests/test_resolve_detected_agent.sh`**: all 11 tests currently
   pass. Plan requires ADDING tests for opus4_7 mappings, not
   modifying existing ones. The resolver does a pure `jq` exact-match
   on `cli_id` — `claude-opus-4-7[1m]` has no special handling, it's a
   literal string match. Shell quoting matters (brackets).

4. **`codeagent_config.json`** confirmed: 5 ops → `claudecode/opus4_7_1m`
   (`pick`, `explore`, `brainstorm-explorer`, `brainstorm-synthesizer`,
   `brainstorm-detailer`). `DEFAULT_AGENT_STRING="claudecode/opus4_7_1m"`.

5. **`tests/test_brainstorm_crew.py`** FULL_DEFAULTS fixture (lines
   354–360): self-contained — tests currently PASS. Update is fidelity
   only, low-risk textual swap of `opus4_6` → `opus4_7_1m` for
   explorer/synthesizer/detailer (comparator and patcher keep
   sonnet4_6). Line 422 (`"pick": "claudecode/opus4_6"`) and line 469
   (`explorer agent_string`) update alongside.

6. **`tests/test_aitask_stats_py.py`** uses opus4_6 as stats fixture at
   lines 81, 122, 205, 397, 499. Add opus4_7 entry (empty
   `verifiedstats`) alongside — tests the "model present with zero
   stats" code path.

7. **`tests/test_verified_update_flags.sh`**: per audit in
   `aidocs/model_reference_locations.md:102` this is tagged
   `informational_only` — fixture pinned to opus4_6 intentionally.
   **Leave unchanged.**

8. **`aidocs/claudecode_tools.md:5`**: single-line update confirmed.

9. **`website/content/docs/commands/codeagent.md`**: current table
   (lines 54–57) uses stale operation names (`task-pick` vs actual
   `pick`) AND stale defaults. Rebuild table against real
   `codeagent_config.json`. Line 167 (hardcoded default) must be
   updated. Resolve/dry-run example output (lines 104–108, 118–119)
   should reflect the new default for accuracy — update those.
   Format-illustration lines (16, 28, 36, 208–209, 248) stay per
   audit's `informational_only` tag.

10. **`website/content/docs/tuis/settings/reference.md:156–157`**: per
    audit `informational_only`, but plan calls for a single-line
    refresh. Swap to `opus4_7_1m` / `claude-opus-4-7[1m]` to keep
    examples current.

11. **`website/content/docs/skills/aitask-add-model.md`** does NOT
    exist. Pattern: website skill docs are manual marketing-style
    mirrors (not auto-generated from `.claude/skills/*/SKILL.md`).
    Compare style to `aitask-refresh-code-models.md`. Need to create.

12. **Final sweep** will highlight format-illustration hits in
    `aidocs/{brainstorming,agentcrew}/*.md`,
    `aidocs/model_reference_locations.md`, and
    `website/content/docs/tuis/settings/_index.md:26` — all per audit
    `informational_only`, leave untouched but document the decision.

## Deviations from original plan

- Plan text "add a case asserting `DEFAULT_AGENT_STRING` resolves to
  `claudecode/opus4_7`" → actual promoted default is
  `claudecode/opus4_7_1m`. Use that.
- Plan said resolve test adds `claude-opus-4-7 → claudecode/opus4_7`.
  Adding BOTH variants (`claude-opus-4-7 → opus4_7` AND
  `claude-opus-4-7[1m] → opus4_7_1m`) because both were registered.
- Plan step 5 says commit with a single code+plan commit; per CLAUDE.md
  the plan file uses `./ait git` and code uses plain `git` — split
  accordingly.

## Implementation steps

### Step 1. Fix pre-existing bug in `tests/test_codeagent.sh`
At line 75 (immediately after `task_utils.sh` copy), add:
```bash
cp "$PROJECT_DIR/.aitask-scripts/lib/archive_utils.sh" "$tmpdir/.aitask-scripts/lib/"
```
Run `bash tests/test_codeagent.sh` — it should now proceed past Test 2.
Expect failures at Tests 5 and 11 (default-sensitive asserts) — those
are fixed in Step 2.

### Step 2. Update default-sensitive asserts in `tests/test_codeagent.sh`
- Test 5 (lines 140–144): `opus4_6` → `opus4_7_1m`,
  `claude-opus-4-6` → `claude-opus-4-7[1m]`
- Test 11 (line 193): `claude-opus-4-6` → `claude-opus-4-7[1m]`
- Test 3 (list-models): ADD two new `assert_contains` lines:
  - `"MODEL:opus4_7"` present
  - `"MODEL:opus4_7_1m"` present
- Do NOT change coauthor tests (15–26) — they test metadata for
  specific models, opus4_6 still registered.

Run `bash tests/test_codeagent.sh` — should pass.

### Step 3. Add opus4_7 mappings to `tests/test_resolve_detected_agent.sh`
After existing "exact match claudecode" block (line 55–57), add:
```bash
echo "=== Test: exact match claudecode opus4_7 ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id claude-opus-4-7 2>&1)
assert_eq "claudecode opus4_7 exact match" "AGENT_STRING:claudecode/opus4_7" "$result"

echo "=== Test: exact match claudecode opus4_7_1m ==="
result=$(AITASK_AGENT_STRING="" bash "$RESOLVE_SCRIPT" --agent claudecode --cli-id 'claude-opus-4-7[1m]' 2>&1)
assert_eq "claudecode opus4_7_1m exact match" "AGENT_STRING:claudecode/opus4_7_1m" "$result"
```
Single-quote the `[1m]` cli-id to prevent shell glob issues.

Run `bash tests/test_resolve_detected_agent.sh` — should pass 13 tests.

### Step 4. Add opus4_7 fixture to `tests/test_aitask_stats_py.py`
Locate the claudecode models fixture at lines 80–83 and 498–501:
```python
(metadata / "models_claudecode.json").write_text(
    json.dumps({"models": [{"name": "opus4_6", "cli_id": "claude-opus-4-6"}]}),
    encoding="utf-8",
)
```
Change to include opus4_7 alongside:
```python
(metadata / "models_claudecode.json").write_text(
    json.dumps({"models": [
        {"name": "opus4_6", "cli_id": "claude-opus-4-6"},
        {"name": "opus4_7", "cli_id": "claude-opus-4-7", "verifiedstats": {}},
    ]}),
    encoding="utf-8",
)
```
For the more elaborate fixture at lines 392–408 (with verifiedstats),
leave opus4_6 entry intact and append a second dict entry for opus4_7
with `"verifiedstats": {}`.

Run `python3 -m unittest tests.test_aitask_stats_py` — should stay green.

### Step 5. Update `tests/test_brainstorm_crew.py` fixtures
- Lines 355, 357, 358: `claudecode/opus4_6` → `claudecode/opus4_7_1m`
  (explorer, synthesizer, detailer)
- Line 422: `"pick": "claudecode/opus4_6"` → `"pick": "claudecode/opus4_7_1m"`
- Line 469 assertion: `"claudecode/opus4_6"` → `"claudecode/opus4_7_1m"`

Run `python3 -m unittest tests.test_brainstorm_crew` — should stay green.

### Step 6. Update `aidocs/claudecode_tools.md`
Line 5:
```
**Model:** Claude Opus 4.6 (`claude-opus-4-6`)
```
→
```
**Model:** Claude Opus 4.7 (`claude-opus-4-7`)
```
(No `[1m]` in the tools doc — that's a client-side context signal, not
the model identity. Keeps alignment with the line 3/4 "Generated at"
metadata convention.)

### Step 7. Update `website/content/docs/commands/codeagent.md`
- **Operational defaults table (lines 52–58)**: rebuild against
  actual `codeagent_config.json`. Replace table rows with:

  ```
  | Operation | Description | Default |
  |-----------|-------------|---------|
  | `pick` | Picking and implementing tasks | `claudecode/opus4_7_1m` |
  | `explain` | Explaining or documenting code | `claudecode/sonnet4_6` |
  | `explore` | Exploring the codebase | `claudecode/opus4_7_1m` |
  | `batch-review` | Batch code review | `claudecode/sonnet4_6` |
  | `qa` | Test coverage analysis | `claudecode/sonnet4_6` |
  | `raw` | Direct/ad-hoc invocations (passthrough) | `claudecode/sonnet4_6` |
  ```

- **Line 167 hardcoded default**: `claudecode/opus4_6` →
  `claudecode/opus4_7_1m`
- **Resolve example (lines 104–110)**: update AGENT_STRING/MODEL/CLI_ID
  lines to show `claudecode/opus4_7_1m` / `opus4_7_1m` /
  `claude-opus-4-7[1m]`.
- **Dry-run narrative (lines 118–119)**: update to show resolved
  command with the new default cli_id.
- **Project-config example (lines 173–182)**: update `"task-pick"` key
  name to `"pick"` and its value to `"claudecode/opus4_7_1m"`. Other
  example keys (`explain`, `batch-review`, `raw`) stay. Adds `qa` and
  `explore` for realism? Optional — keep minimal to reduce churn.

Leave lines 16, 28, 36, 89 (list-models output format example), 176–179
format demos, 208–209 (model-schema example), 248 (implemented_with
example) — per audit, format illustrations.

### Step 8. Update `website/content/docs/tuis/settings/reference.md`
Lines 156–157 (model entry schema example):
```json
  "name": "opus4_6",
  "cli_id": "claude-opus-4-6",
```
→
```json
  "name": "opus4_7_1m",
  "cli_id": "claude-opus-4-7[1m]",
```

### Step 9. Create `website/content/docs/skills/aitask-add-model.md`
Manual mirror following the style of `aitask-refresh-code-models.md`
(the most closely-related skill). Frontmatter:
```yaml
---
title: "/aitask-add-model"
linkTitle: "/aitask-add-model"
weight: 56
description: "Register a known code-agent model in models_<agent>.json and optionally promote it to default"
---
```
Body sections (concise, marketing-style):
- Intro paragraph — relationship to `/aitask-refresh-code-models`
- **Usage** (CLI flags + interactive modes)
- **When to use** (newly announced models where you already know the
  cli_id/notes)
- **Two modes** (add vs promote) with bullet list of what each writes
- **Manual-review list** — brief mention that the skill emits a list
  of files that still reference the old default
- **Related** — link to `/aitask-refresh-code-models`,
  `ait codeagent`, `codeagent_config.json`

Keep to roughly the same length and depth as
`aitask-refresh-code-models.md` (~100 lines).

### Step 10. Final sweep
```bash
grep -rn 'opus4_6\|claude-opus-4-6' \
  aitasks/metadata/ seed/ .aitask-scripts/ aidocs/ website/content/docs/ \
  tests/ 2>/dev/null \
  | grep -v verifiedstats | grep -v archived
```
Expected remaining hits (documented exceptions):
- `aidocs/model_reference_locations.md` — the audit spec itself
- `aidocs/brainstorming/brainstorm_engine_architecture.md` (lines
  476, 479, 482, 485, 488) — historical rationale, `informational_only`
- `aidocs/agentcrew/agentcrew_architecture.md` — architecture examples,
  `informational_only`
- `.aitask-scripts/aitask_codeagent.sh` help-text format examples
- `tests/test_verified_update.sh`, `tests/test_verified_update_flags.sh`,
  and `tests/test_crew_*.sh` — pinned fixtures, `informational_only`
- `website/content/docs/tuis/{settings/_index.md,board/reference.md}`,
  `website/content/docs/skills/aitask-refresh-code-models.md`,
  `website/content/docs/commands/codeagent.md` lines 16/28/36/208/248 —
  format illustrations

Record this list in Final Implementation Notes.

### Step 11. Website build check (optional)
```bash
cd website && hugo build --gc --minify
```
Only run if hugo is available on the machine — don't block on it.

### Step 12. Commits (plain `git` for code, `./ait git` for `aiplans/`)

```bash
# Code-only commit (tests + docs)
git add tests/test_codeagent.sh tests/test_resolve_detected_agent.sh \
        tests/test_aitask_stats_py.py tests/test_brainstorm_crew.py \
        aidocs/claudecode_tools.md \
        website/content/docs/commands/codeagent.md \
        website/content/docs/tuis/settings/reference.md \
        website/content/docs/skills/aitask-add-model.md
git commit -m "documentation: Update tests and docs for Opus 4.7 default (t579_4)"

# Plan commit (separate via ./ait git)
./ait git add aiplans/p579/p579_4_update_tests_and_docs_for_opus_4_7.md
./ait git commit -m "ait: Update plan for t579_4"
```
(Actual commit creation is Step 8 of the workflow, not this plan.)

## Verification

1. `bash tests/test_codeagent.sh` → exits 0 with all tests passing
   (including the two new opus4_7 list-models asserts).
2. `bash tests/test_resolve_detected_agent.sh` → 13 tests pass.
3. `python3 -m unittest tests.test_brainstorm_crew` → 34 tests pass.
4. `python3 -m unittest tests.test_aitask_stats_py` → 18 tests pass.
5. `bash tests/test_verified_update_flags.sh` → unchanged, passes.
6. `shellcheck .aitask-scripts/aitask_*.sh` → no new warnings.
7. Final grep sweep returns only documented exceptions listed in
   Step 10.
8. If run locally, `ait codeagent resolve pick` prints
   `AGENT_STRING:claudecode/opus4_7_1m`.

## Step 9 (Post-Implementation)

Standard archival via `./.aitask-scripts/aitask_archive.sh 579_4`.
Parent t579 auto-archives since all children are then complete. Final
Implementation Notes (to be filled at commit time) should cover:

- Which tests required updates vs which already passed
- The exact list of `opus4_6` references intentionally kept and why
  (from the final sweep)
- Whether the website build was verified locally
- Confirmation that parent t579 auto-archived

## Critical files to be modified

- `tests/test_codeagent.sh` — setup bug fix + default asserts
- `tests/test_resolve_detected_agent.sh` — add opus4_7 cases
- `tests/test_aitask_stats_py.py` — add opus4_7 fixture
- `tests/test_brainstorm_crew.py` — update FULL_DEFAULTS fixture
- `aidocs/claudecode_tools.md` — line 5
- `website/content/docs/commands/codeagent.md` — defaults table +
  hardcoded-default line + resolve example + config example
- `website/content/docs/tuis/settings/reference.md` — example schema
- `website/content/docs/skills/aitask-add-model.md` — new file

## Reference files for patterns

- `aitasks/metadata/codeagent_config.json` — source of truth for
  current op defaults
- `.aitask-scripts/aitask_codeagent.sh:21` — `DEFAULT_AGENT_STRING`
- `aitasks/metadata/models_claudecode.json` — registered models
- `website/content/docs/skills/aitask-refresh-code-models.md` —
  style/structure template for the new skill page
- `aidocs/model_reference_locations.md` — audit spec listing every
  opus4_6 reference with `needed_for_promote` /
  `informational_only` tags
- `aiplans/archived/p579/p579_3_*.md` Final Implementation Notes —
  manual-review list from t579_3
