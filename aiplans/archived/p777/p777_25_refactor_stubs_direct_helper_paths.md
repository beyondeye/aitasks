---
Task: t777_25_refactor_stubs_direct_helper_paths.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_10_convert_aitask_fold.md, aitasks/t777/t777_11_convert_aitask_qa.md, aitasks/t777/t777_12_convert_aitask_pr_import.md, aitasks/t777/t777_13_convert_aitask_revert.md, aitasks/t777/t777_14_convert_aitask_pickrem.md, aitasks/t777/t777_15_convert_aitask_pickweb.md, aitasks/t777/t777_16_extract_profile_editor_widget.md, aitasks/t777/t777_17_per_run_profile_edit_in_agentcommandscreen.md, aitasks/t777/t777_18_docs_update_claudemd_and_website.md, aitasks/t777/t777_19_retrospective_evaluation.md, aitasks/t777/t777_20_profile_modification_invalidation.md, aitasks/t777/t777_23_swap_task_workflown_to_task_workflow.md, aitasks/t777/t777_24_manual_verify_aitask_pickn.md, aitasks/t777/t777_26_template_completeness_and_resolver_key.md, aitasks/t777/t777_6_convert_aitask_pick_template_and_stubs.md, aitasks/t777/t777_8_convert_aitask_explore.md, aitasks/t777/t777_9_convert_aitask_review.md
Archived Sibling Plans: aiplans/archived/p777/p777_1_minijinja_dep_renderer_paths_resolver.md, aiplans/archived/p777/p777_21_map_pick_reference_closure_and_profile_keys.md, aiplans/archived/p777/p777_22_extend_renderer_for_uniform_recursive_rendering.md, aiplans/archived/p777/p777_2_aitask_skill_render_subcommand.md, aiplans/archived/p777/p777_3_stub_skill_design_and_gitignore.md, aiplans/archived/p777/p777_4_aitask_skill_verify_and_precommit.md, aiplans/archived/p777/p777_5_aitask_skillrun_wrapper_dispatcher.md, aiplans/archived/p777/p777_7_convert_task_workflow_shared_procs.md
Base branch: main
plan_verified: []
---

# t777_25 — Refactor stubs to direct helper paths (and remove `ait skill`)

## Context

The 4 stub files (`aitask-pickn` for claude/codex/gemini/opencode) currently
call `./ait skill render <skill> --profile <p> --agent <a>` in Step 2. The
dispatcher form forces every user installation to add a new allowlist entry
(`Bash(./ait skill render:*)` or equivalent) — friction with no payoff:
the stubs are not user-facing (users type `/aitask-pick`), and
`.aitask-scripts/aitask_skill_render.sh` is already whitelisted.

Per user direction: `ait skill` subcommands (`render`, `verify`) are **not
user-facing** and will be **removed entirely**. Only `ait skillrun` is kept
(it is the universal launcher used by Python TUIs — t777_5's core deliverable).
This is option (b) of the task's scope point 5.

## Files to modify

### Dispatcher removal

1. **`ait`** — Remove the entire `skill)` case block (lines 194–217). The
   `case` statement keeps every other entry untouched. `ait skill` is not
   listed in `show_usage` and is not in line 169's update-check skip-list,
   so no further `ait` edits are required.

### Stubs and canonical reference

2. **`aidocs/stub-skill-pattern.md`** — Step 2 in three subsections:
   - §3b (Claude/Codex SKILL.md form), line 36
   - §3c (Gemini TOML form), line 70
   - §3d (OpenCode MD form), line 104

   Change `./ait skill render <skill_short_name> --profile <profile> --agent <agent_literal>`
   → `./.aitask-scripts/aitask_skill_render.sh <skill_short_name> --profile <profile> --agent <agent_literal>`.

3. **4 stub files** — Step 2 line in each:
   - `.claude/skills/aitask-pickn/SKILL.md` (line 15)
   - `.agents/skills/aitask-pickn/SKILL.md` (line 15)
   - `.gemini/commands/aitask-pickn.toml` (line 16)
   - `.opencode/commands/aitask-pickn.md` (line 17)

### Verifier script (consumed by stubs and tests)

4. **`.aitask-scripts/aitask_skill_verify.sh`**:
   - Lines 38, 46, 126, 130: stdout/stderr prefix `ait skill verify:` →
     `aitask_skill_verify.sh:`.
   - Line 112: `grep -q "ait skill render ${skill}"` →
     `grep -q "aitask_skill_render.sh ${skill}"`.
   - Line 113: error message format string `"ait skill render %s"` →
     `"aitask_skill_render.sh %s"`.

### Docs

5. **`CLAUDE.md`** line 210: `./ait skill verify` →
   `./.aitask-scripts/aitask_skill_verify.sh`.

6. **`aidocs/skill_authoring_conventions.md`** — five references:
   - Lines 6, 17, 28, 29, 155: `ait skill verify` →
     `.aitask-scripts/aitask_skill_verify.sh` (or `./.aitask-scripts/...`
     where shown as a command).
   - Lines 109, 135: `ait skill render` → `aitask_skill_render.sh`.

### Tests

7. **`tests/test_skill_render.sh`**:
   - Remove Tests 16 and 17 (lines 334–346) — they exercise
     `./ait skill --help` and `./ait skill bogus`, which no longer exist.
   - Update header comment at line 4 (`./ait skill subcommand`) — replace
     with the two direct script entry points the test still covers.

8. **`tests/test_skill_verify.sh`**:
   - Helper `_write_canonical_stubs` (lines 105–139): change the four stub
     bodies it writes to use `./.aitask-scripts/aitask_skill_render.sh`
     instead of `./ait skill render`. This is what feeds Tests 2/4/5/6/7.
   - Line 212: assertion expecting `"ait skill verify: OK"` →
     `"aitask_skill_verify.sh: OK"` (matches step 4 output change).
   - Lines 228, 277 (intentionally-broken modified stubs for Tests 5/6):
     change `./ait skill render` → `./.aitask-scripts/aitask_skill_render.sh`.
   - Remove Tests 8 and 9 (lines 291–308) — they exercise the removed
     `./ait skill --help` and `./ait skill bogus`.

9. **`tests/test_skill_render_aitask_pickn.sh`**:
   - Test 4 wrapper call at line 127: `./ait skill render aitask-pickn …`
     → `./.aitask-scripts/aitask_skill_render.sh aitask-pickn …`.
   - Comment at line 123 — minor wording fix to drop "via the `ait skill
     render` wrapper".
   - Test 5 assertion at line 152: expected substring
     `"ait skill render aitask-pickn"` → `"aitask_skill_render.sh aitask-pickn"`.

## Out of scope (verified)

- **Golden files** under `tests/golden/skills/aitask-pickn/` — `grep -l
  "ait skill render"` returns nothing. The entry-point template does not
  emit dispatcher strings into rendered output. No update needed.
- **Plans p777_8..p777_15 and p777_18** — references are descriptions of
  the previous `ait skill verify` / `ait skill render` commands used as
  verification. Since the helper scripts (`aitask_skill_verify.sh`,
  `aitask_skill_render.sh`) keep equivalent behavior, the plan prose
  remains semantically valid; future implementers will read the updated
  `aidocs/stub-skill-pattern.md` for stub bodies. No per-plan edits
  required for this task.
- **`ait skillrun`** — kept. Core to t777_5; used by Python TUIs.
- **Whitelist files** — `.claude/settings.local.json`,
  `seed/claude_settings.local.json`, `.gemini/policies/aitasks-whitelist.toml`,
  `seed/geminicli_policies/aitasks-whitelist.toml` already list
  `aitask_skill_render.sh` / `aitask_skill_verify.sh` directly. No
  whitelist entries refer to `ait skill`. No changes needed.

## Verification

```bash
# Stub-render test (target test for this task)
bash tests/test_skill_render_aitask_pickn.sh

# Render test suite (Tests 16,17 removed)
bash tests/test_skill_render.sh

# Verify-script test suite (Tests 8,9 removed)
bash tests/test_skill_verify.sh

# Closure validator (now invoked directly)
./.aitask-scripts/aitask_skill_verify.sh

# Sanity sweep — no remaining references to the removed dispatcher
grep -rn 'ait skill ' --include='*.sh' --include='*.md' --include='*.py' \
  --include='*.j2' --include='*.toml' --include='*.json' . 2>/dev/null \
  | grep -v 'ait skillrun' | grep -v '/\.git/'
# Expected: no output.

# `ait skill foo` should now report unknown command
./ait skill verify; echo "rc=$?"
# Expected: "ait: unknown command 'skill'" on stderr, rc=1.
```

Expected: all three test scripts pass, the closure validator exits 0, the
sanity sweep returns no matches, and `ait skill` is rejected as an unknown
top-level command.

## Post-task downstream

- t777_24 manual verification re-run picks up the direct-path stubs.
- t777_6 Phase 5 atomic rename (`aitask-pickn` → `aitask-pick`) happens
  after t777_24 verifies.
- t777_8..t777_15 implementers read the updated
  `aidocs/stub-skill-pattern.md` for the new stub body form — no per-plan
  edits required.

## Step 9 (Post-Implementation)

Standard archive flow: update task status, archive task + plan, commit, push.

## Final Implementation Notes

- **Actual work done:** Removed `skill)` case from `./ait` entirely (option b
  per user direction — only `ait skillrun` is kept). Migrated 4 aitask-pickn
  stubs, `aidocs/stub-skill-pattern.md` §3b/c/d, `aidocs/skill_authoring_conventions.md`,
  `CLAUDE.md`, and 3 test files to direct-path form (`./.aitask-scripts/aitask_skill_render.sh` /
  `./.aitask-scripts/aitask_skill_verify.sh`). Updated `aitask_skill_verify.sh`
  to (a) print its own name as the output prefix and (b) grep for the new
  direct-path pattern in stubs. Removed dispatcher-specific tests:
  `test_skill_render.sh` Tests 16/17 and `test_skill_verify.sh` Tests 8/9.
  Net diff: 12 files, +37/-93 lines.
- **Deviations from plan:** None. The plan covered the exact set of files
  touched. Captured one extra residual sweep target (the header comment in
  `tests/test_skill_verify.sh` line 4 was also a `ait skill verify subcommand`
  reference) — fixed during the sanity sweep step.
- **Issues encountered:** `tests/test_skill_verify.sh` Test 1 fails on the
  current branch ("no .j2 templates" assertion). Confirmed via `git stash` /
  re-run that the failure is pre-existing — it landed when t777_6 Phase 1-4
  introduced `.claude/skills/aitask-pickn/SKILL.md.j2`. Triage tracked by
  t790 (`triage_preexisting_test_failures_post_t777`). Out of scope for this
  task; not caused by these changes.
- **Key decisions:**
  - Option (b) — full removal of `ait skill` subcommands — chosen by user
    over option (a) (keep wrappers, only stop using from stubs).
    Rationale: subcommands are not user-facing, only stub-internal; the
    direct helper paths (`aitask_skill_render.sh`, `aitask_skill_verify.sh`)
    are already whitelisted, so the dispatcher added cost without value.
  - Updated `aitask_skill_verify.sh` output prefix from
    `ait skill verify:` → `aitask_skill_verify.sh:` so log lines name a real
    invocation that still works. Mechanically required because the matching
    assertion (`tests/test_skill_verify.sh` line 212) also moved.
  - Goldens under `tests/golden/skills/aitask-pickn/` were not touched —
    pre-checked that none contained `ait skill render`; the dispatcher form
    only ever appeared in stub bodies, not in entry-point rendered output.
- **Upstream defects identified:** None.
- **Notes for sibling tasks:**
  - **For t777_8..t777_15 (other skill conversions):** Read updated
    `aidocs/stub-skill-pattern.md` §3b/c/d for the new stub body form —
    use `./.aitask-scripts/aitask_skill_render.sh <skill> --profile <p> --agent <a>`,
    NOT `./ait skill render …` (the dispatcher is gone).
  - **For t777_24 re-verification:** The 4 aitask-pickn stubs now use direct
    paths. Live `/aitask-pickn <id>` should not prompt for any new
    permission (the direct helper is pre-whitelisted via
    `.claude/settings.local.json`).
  - **For t777_6 Phase 5 rename:** When renaming `aitask-pickn` → `aitask-pick`,
    the canonical stub body comes from the updated stub-skill-pattern.md —
    no further dispatcher cleanup needed.
  - **Test infrastructure caveat:** `tests/test_skill_verify.sh` Test 1
    will continue to fail on any branch where a real `.j2` template
    exists in `.claude/skills/`. The test was designed against a state
    where no templates existed; t790 triages.
