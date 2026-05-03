---
Task: t732_fix_failing_pre_existing_test_suite.md
Base branch: main
plan_verified: []
---

# Plan: t732 — triage split for failing pre-existing test suite

## Context

t732 is a triage parent surfaced during t623_1 regression testing. On `main` (today: `74c59788`), 13 of 112 shell tests under `tests/` fail on a clean Linux/CPython 3.14.3 environment (originally documented as 14; `test_python_resolve_pypy.sh` has since been fixed by t728/t731).

The originally proposed cluster split (A–E) was sound but **fresh exploration uncovered a cross-cluster root cause** that collapses 4 of the failures into a single fix and changes the cluster boundaries. This plan documents the revised split, then creates 6 cluster-fix children + 1 trailing whole-suite verification child.

The parent task itself is **planning + child creation only** — no fixes land here. Each child carries detailed context so it can be picked in a fresh Claude Code session.

## Key finding from exploration

Tests `test_task_push.sh`, `test_brainstorm_cli.sh`, `test_explain_context.sh`, and `test_migrate_archives.sh` all fail with the same first-line error:

```
… line N: <scratch>/.aitask-scripts/lib/aitask_path.sh: No such file or directory
```

`lib/aitask_path.sh` was added by **t695_3** (Apr 28) and is now sourced unconditionally on `./ait` line 7 (and from many helper scripts on their early lines). 55 test files build a fake `.aitask-scripts/lib/` and copy only the libs they think they need; none of them copy `aitask_path.sh`. The 4 tests above happen to invoke `./ait` or scripts that source `aitask_path.sh`, so they crash; the other 51 happen to dodge it (for now). This single missing-copy is responsible for those 4 failures, cutting across the original Cluster C and Cluster E groupings.

## Revised cluster split (6 children + 1 trailing eval)

| Child | Cluster | Priority | Tests | Root-cause summary |
|-------|---------|----------|-------|--------------------|
| t732_1 | A — Textual / Python 3.14 TUI API drift | high | `test_multi_session_minimonitor.sh`, `test_tui_switcher_multi_session.sh` | Textual `_thread_id` AttributeError + unawaited coroutine; `#switcher_desync` queried before mount |
| t732_2 | B — python_resolve.sh version comparison | medium | `test_python_resolve.sh` | Resolver rejects Python 3.13.0 as < 3.11 (lex-vs-numeric or stub-interaction bug). `test_python_resolve_pypy.sh` already fixed by t728/t731 — verify but expect green. |
| t732_3 | C — Branch-mode / upgrade-commit regressions | medium | `test_init_data.sh`, `test_t644_branch_mode_upgrade.sh`, `test_t167_integration.sh` | Two sub-issues: (a) init-data symlink/data-branch flow returning `NO_DATA_BRANCH`; (b) t644+t167 both expect upgrade to commit a new file with `committed to git` output and a version-tagged message — likely regressed by t623_1 (Extract global shim) |
| t732_4 | D — External-tool / agent metadata drift | medium | `test_codex_model_detect.sh`, `test_gemini_setup.sh` | (a) codex model-name detection 0/24 MATCH — refresh `models_codex.json` against current Codex CLI; (b) gemini Test 8 global-policy install: temp venv `bin/python` path missing |
| t732_5 | Z — Test scaffolds missing `aitask_path.sh` | high | `test_task_push.sh`, `test_brainstorm_cli.sh`, `test_explain_context.sh`, `test_migrate_archives.sh` | Single root cause (see "Key finding" above). Implementer chooses between mechanical patch (add `cp aitask_path.sh` to each test) vs structural fix (extract `tests/lib/test_scaffold.sh` helper for fake-repo bootstrap, then converge tests onto it). |
| t732_6 | F — codemap help text drift | low | `test_contribute.sh` (1-of-123) | Single assertion `codemap help mentions shared venv` expecting "shared aitasks Python" string. Decide whether `aitask_codemap.sh` help text or the test is stale. |
| t732_7 | Final verification (retrospective eval) | medium | Whole suite | After siblings land, re-run all 112 tests; confirm 0 failures; document any new regressions; update CLAUDE.md only for recurring portability/scaffolding gotchas. |

**Note on cluster ordering and dependencies.** None of the cluster children block each other. Recommended pick order:
1. **t732_5 first** — most mechanical, single root cause, unblocks confidence in the rest of the suite.
2. **t732_1 (Cluster A)** — daily-UX impact, justifies high priority.
3. **t732_2 / t732_3 / t732_4** — independent, pick by interest.
4. **t732_6** — one-line fix, can be batched with whichever child the implementer is in.
5. **t732_7 last** — depends on all six siblings.

`depends:` frontmatter on t732_7 will list `[1,2,3,4,5,6]` (relative child IDs); the others get `depends: []`.

## Coordination with active install-methods refactor (t623)

t623 ("more installation methods") is in flight; relevant facts confirmed during this planning phase:

| Sub-task | Status | Scope | Overlap with t732? |
|----------|--------|-------|--------------------|
| t623_1 | Done (`d627c0f5`) | Extracted global shim to `packaging/shim/ait`, added strategy doc | **Yes — likely root cause of Cluster C upgrade-commit failures (t644, t167)** |
| t623_2 | Implementing (dario-e) | Homebrew tap + reusable `release-packaging.yml` CI workflow | None (packaging-only; no runtime install/upgrade or test changes) |
| t623_3/4/5/6/7 | Ready | AUR / deb / rpm packaging + docs + manual verification | None (same — packaging distribution, not runtime) |

**Implication for t732:** The cluster split below is unaffected. Cluster C's child task description carries an explicit cross-reference to t623_1 so the implementer reads the archived plan before deciding fix-the-test vs fix-the-code.

## Side observation (out of scope, surface to user)

Repo root has 5 untracked 50 MB PostScript files dated 2026-04-29 with Python-stdlib names (`os`, `shutil`, `subprocess`, `time`, `unittest`) — generated by ImageMagick (`%%Creator: (ImageMagick)`). They predate this task by 5 days and are unrelated to test failures. Likely stray output from an earlier `convert ... <module-name>` or similar command (no extension). Not in scope for t732, but worth flagging for the user to delete.

## Implementation steps for THIS task (parent planning only)

All work happens via `aitask_create.sh --batch` per the **Batch Task Creation Procedure** (`.claude/skills/task-workflow/task-creation-batch.md`).

### Step 1 — Create the 7 child tasks

For each child below, run:

```bash
./.aitask-scripts/aitask_create.sh --batch \
  --parent 732 \
  --name <child_name> \
  --priority <p> --effort <e> \
  --issue-type <type> \
  --labels <labels> \
  --desc-file <tmp_desc.md>
```

Each child's description (`<tmp_desc.md>`) MUST contain (per `planning.md` "Child Task Documentation Requirements"):
- **Context** — what cluster, why this fix is needed, how it fits into t732
- **Failing tests** — exact filenames and the specific failure messages observed today
- **Root cause hypothesis** — what we believe the bug is (from the parent's analysis)
- **Key files to modify** — full paths with brief change descriptions
- **Reference files for patterns** — similar fixes / related code
- **Implementation plan** — step-by-step
- **Verification** — `bash <test>` passes; whole-suite reruns cleanly for files in this child's scope

Specific child specs:

#### t732_1 — Cluster A
- name: `cluster_a_textual_tui_api_drift`
- priority: high, effort: medium
- issue-type: bug
- labels: `testing,tui,textual`
- Body must include: Textual version probe (`pip show textual`), the exact line in `tests/test_multi_session_minimonitor.sh` and `lib/tui_switcher.py:483` that throws, and reference to the CLAUDE.md "Priority bindings + `App.query_one` gotcha" entry.

#### t732_2 — Cluster B
- name: `cluster_b_python_resolve_version_comparison`
- priority: medium, effort: low
- issue-type: bug
- labels: `testing,bash_scripts,portability`
- Body must include: the exact stub harness from `tests/test_python_resolve.sh` (`make_stub` block, lines ~50-90), the `AIT_VENV_PYTHON_MIN` constant in `lib/python_resolve.sh:32`, and a note that `test_python_resolve_pypy.sh` is already passing (t728+t731) — do not assume the whole resolver is broken.

#### t732_3 — Cluster C
- name: `cluster_c_branch_mode_and_upgrade_commit`
- priority: medium, effort: high
- issue-type: bug
- labels: `testing,branch_mode,upgrade,install_scripts`
- Body must include:
  - Split into two sub-sections (init-data vs upgrade-commit).
  - Recent suspect commits: `d627c0f5` t623_1 shim extraction, `709380a5` t695_3 PATH lib. Bisect against pre-t623_1 (`8fb777bd`) if upgrade-commit failures are unclear.
  - **Coordination note (active install refactor):** t623 ("more installation methods") is currently in flight. t623_1 is done and is the prime suspect for the upgrade-commit failures. **Before patching either tests or code, read `aiplans/archived/p623/p623_1_*.md`** to determine whether the new upgrade output is intentional (→ update test assertions) or accidental (→ restore the missing `committed to git` / version-tagged commit message in `aitask_setup.sh`/`install.sh`).
  - Note that t623_2 (currently `Implementing`, dario-e@beyond-eye.com) is **packaging-CI only** (Homebrew tap, `packaging/homebrew/`, `.github/workflows/release-packaging.yml`) and does NOT modify the runtime install/upgrade flow. There is no merge conflict expected, but if the implementer is tempted to expand scope beyond the failing tests into the broader install tree, sync with the t623 owner first.

#### t732_4 — Cluster D
- name: `cluster_d_external_tool_drift`
- priority: medium, effort: medium
- issue-type: bug
- labels: `testing,external_tools,codex,gemini`
- Body must include: instruction to first run `aitask_refresh_code_models` (or invoke `/aitask-refresh-code-models`) for codex; for gemini, the exact failure line `/tmp/.../bin/python: No such file or directory` and a pointer to `tests/test_gemini_setup.sh` Test 8 setup.

#### t732_5 — Cluster Z (highlight as "single root cause across 4 tests")
- name: `cluster_z_test_scaffold_missing_aitask_path`
- priority: high, effort: low
- issue-type: bug
- labels: `testing,bash_scripts,test_infrastructure`
- Body must include:
  - The 4 failing tests + the exact error line they all share
  - The two implementation strategies (mechanical patch vs `tests/lib/test_scaffold.sh` helper extraction). Recommend the helper approach per CLAUDE.md "Single source of truth for cross-script constants" (also: 51 currently-passing tests have the same time-bomb missing copy — a helper would inoculate them).
  - If helper approach chosen, note this is a refactor that should converge all 55 tests; it is NOT an "out of scope" follow-up — surface as t732_5's own work or split into t732_5_1 (scaffold helper extraction) + t732_5_2 (port tests onto helper).

#### t732_6 — Cluster F
- name: `cluster_f_codemap_help_text`
- priority: low, effort: low
- issue-type: bug
- labels: `testing,documentation`
- Body must include: the assertion line `tests/test_contribute.sh:558`, the path `aitask_codemap.sh`, and a note to determine which side is the source of truth before patching.

#### t732_7 — Final verification (trailing eval)
- name: `verify_full_suite_zero_failures`
- priority: medium, effort: low
- issue-type: test
- labels: `testing,verification`
- depends: `[732_1, 732_2, 732_3, 732_4, 732_5, 732_6]` (set via `--depends`)
- Body must include: the driver loop from t732 ("Origin" section), the success condition (0 failures), the regression-handling protocol (spawn follow-up tasks rather than expanding scope here), and the CLAUDE.md update gate (only if a recurring portability/scaffolding gotcha was learned).

### Step 2 — Write child plan files

For each child, write `aiplans/p732/p732_<N>_<name>.md` using the Child Task plan metadata header. Each plan file should mirror the child task's body but in a "plan execution" format:

```markdown
---
Task: t732_<N>_<name>.md
Parent Task: aitasks/t732_fix_failing_pre_existing_test_suite.md
Sibling Tasks: aitasks/t732/t732_*.md
Archived Sibling Plans: aiplans/archived/p732/p732_*.md
Worktree: (current branch — fast profile sets create_worktree:false)
Branch: (current branch)
Base branch: main
---
```

Plans do NOT go through `EnterPlanMode`/`ExitPlanMode`; write them directly.

Commit the plan files together:

```bash
mkdir -p aiplans/p732
./ait git add aiplans/p732/
./ait git commit -m "ait: Add t732 child implementation plans"
```

### Step 3 — Manual-verification sibling check

Per `planning.md`, after children are created, ask the user (via AskUserQuestion) whether any of the 7 children produce behavior needing manual verification. For a test-suite triage parent, the answer is almost certainly "No, not needed" — the children's own automated test runs are the verification — but the workflow requires the prompt.

### Step 4 — Revert parent status & release lock

After child creation:

```bash
./.aitask-scripts/aitask_update.sh --batch 732 --status Ready --assigned-to ""
./.aitask-scripts/aitask_lock.sh --unlock 732 2>/dev/null || true
```

This is required by the workflow when a parent gets children — only the child being worked on should be `Implementing`. The board will display the parent as "Has children".

### Step 5 — Child task checkpoint

Per `planning.md`, after children + plans are written, present the **interactive** child-task checkpoint (this checkpoint ALWAYS asks, ignoring `post_plan_action` in the profile):

- "Start first child" → restart with `/aitask-pick 732_5` (recommended first per Implementation Order above; user may choose differently)
- "Stop here" → satisfaction feedback, then end the workflow

## Files this plan affects

**Created:**
- `aitasks/t732/t732_1_cluster_a_textual_tui_api_drift.md`
- `aitasks/t732/t732_2_cluster_b_python_resolve_version_comparison.md`
- `aitasks/t732/t732_3_cluster_c_branch_mode_and_upgrade_commit.md`
- `aitasks/t732/t732_4_cluster_d_external_tool_drift.md`
- `aitasks/t732/t732_5_cluster_z_test_scaffold_missing_aitask_path.md`
- `aitasks/t732/t732_6_cluster_f_codemap_help_text.md`
- `aitasks/t732/t732_7_verify_full_suite_zero_failures.md`
- `aiplans/p732/p732_1_*.md` … `p732_7_*.md` (7 plan files)
- `aiplans/p732_fix_failing_pre_existing_test_suite.md` (this parent plan, externalized)

**Modified:**
- `aitasks/t732_fix_failing_pre_existing_test_suite.md` (status → Ready, assigned_to cleared, `children_to_implement: [1,2,3,4,5,6,7]` populated by `aitask_create.sh --parent`)

**Untouched in this task:**
- All `.aitask-scripts/*` scripts and all `tests/test_*.sh` files. Each child task does its own implementation.

## Verification

This is a planning task; verification is structural, not behavioral:

1. `./.aitask-scripts/aitask_query_files.sh has-children 732` returns `HAS_CHILDREN:7`.
2. `cat aitasks/t732_fix_failing_pre_existing_test_suite.md | grep children_to_implement` shows the 7 children.
3. `ls aiplans/p732/` shows 7 plan files.
4. `cat aitasks/t732_fix_failing_pre_existing_test_suite.md | grep status` shows `status: Ready`.
5. Each child file exists with detailed Context / Failing tests / Root cause / Files / Plan / Verification sections.
6. Per **Step 9 (Post-Implementation)**, the parent is left in `Ready` and the workflow ends after the child checkpoint — actual implementation happens in subsequent `/aitask-pick 732_N` invocations.
