---
Task: t2074_9_branch_layout_enforcement.md
Parent Task: aitasks/t2074_branch_mode_layout_hardening.md
Sibling Tasks: aitasks/t2074/t2074_1_data_layout_classifier.md, aitasks/t2074/t2074_3_setup_layout_repair.md, aitasks/t2074/t2074_12_broken_layout_docs.md, aitasks/t2074/t2074_14_manual_verification_branch_mode_layout_hardening.md
Archived Sibling Plans: aiplans/archived/p2074/p2074_*_*.md
Base branch: main
Output branch: main
---

# t2074_9: Branch layout enforcement (Steps 0 → A → B → C)

This child absorbs t2074_2 (Step A) and t2074_10 (Step C). The binding contract
is the enforcement table and wiring in
`aiplans/p2074_branch_mode_layout_hardening.md`. Legacy behaviour stays
unchanged throughout.

## Steps
0. **Shared-file gate**, applied to `task_utils.sh`, `test_task_push.sh` and
   `test_task_git.sh`:
   - `git diff --quiet` must pass on each file, and t2064's commit must be in
     the log.
   - Re-check the gate just before the first edit.
   - Do the non-overlapping work first. If the gate still fails, stop and ask.

   Also read the inbox, where t2074_1 may hand over the `git-health` work.
A. **Fixture preparation**, from the description's `## Merged from t2074_2`
   section:
   - Write `tests/lib/data_branch_fixture.sh` and its self-test.
   - Convert the five clone-style or stub branch fixtures. Read each builder
     before changing it, and keep its signature.
   - Run the throwaway measurement in an isolated worktree, convert any other
     stub layouts it finds, and record the list.
   - Leave the legacy fixtures unchanged.
B. **Shell enforcement:**
   - Rung validation, including the `missing_storage` die in rung 4.
   - The writer guard before the bypass, then the writer audit.
   - Reader guards with the reexec → parse/help → guard ordering.
   - The errexit audit.
   - `git-health`, if it was handed over.
   - Then write `tests/test_data_layout_refusal.sh` from the enforcement
     table, covering every bullet under "Step B tests".
C. **Python and board enforcement**, from `## Merged from t2074_10`:
   - `_task_git_cmd` resolves from the repo root, validates fresh, and takes
     the inspection/mutation class argument.
   - Board startup refusal, and the sync refusal toast.
   - The caller-class enumeration test, the transition tests (a)/(b)/(c), and
     the snapshot planted control.

## Verification
- Every bash test, run individually.
- The Python suite, whose last line must read `PYTHON SUITE: PASSED`.
- `shellcheck`.

## Step 9
Commit as `refactor: … (t2074_9)`, then archive. Archival deletes the folded
t2074_2 and t2074_10 task files and their plans (`aitask_archive.sh:419-439`).

## Completeness checklist (restructuring check, 2026-10-20)

Each entry maps one requirement in the parent plan's t2074_9 section to its
location in this task's final description, as a section heading plus a quoted
line. The **reverse check** asks whether any active requirement in the
description lacks an entry. It found two items, added below as B.7 and A.7.

| # | Requirement (parent plan) | Location in t2074_9 description |
|---|---|---|
| E.1 | Enforcement table is the source for wiring and tests | `## Enforcement table (the source for every wiring choice and test)` |
| 0.1 | Gate on the three shared files: diff and t2064 commit | `## Step 0` — "For `.aitask-scripts/lib/task_utils.sh`, `tests/test_task_push.sh` and `tests/test_task_git.sh`:" |
| 0.2 | Re-check before edit; non-overlap first; stop and ask | `## Step 0` — "Re-check immediately before the first edit." / "If the gate still fails, stop and ask the user." |
| 0.3 | Read inbox for the git-health handover | `## Step 0` — "Also read this task's `## Inbox`" |
| A.1 | Convert the five branch fixtures, keeping signatures | `## Merged from t2074_2` › `## Scope (Step A)` — "Convert only the branch-mode fixtures that strict validation rejects." |
| A.2 | Shared helper `ait_fixture_to_branch_mode` / `fixture_data_git` | same — "Add a shared helper, `tests/lib/data_branch_fixture.sh`:" |
| A.3 | Self-test classifies like `setup_data_branch` | same — "Self-test: the helper's layout must classify `branch`/`ready`" |
| A.4 | Legacy fixtures stay | same — "**Legacy fixtures stay unchanged.**" |
| A.5 | Throwaway measurement in an isolated worktree; convert what it finds | same — "**Measurement.** Run the whole suite once with the Step B validation applied" |
| A.6 | Read every builder before reuse | same — "read every builder before reusing it" |
| A.7 | Converted-fixture consumers pass (reverse-check addition) | `## Merged from t2074_2` › `## Verification` — "Every test that uses a converted fixture passes" |
| B.1 | Rung 1–3 validation; rung 4 missing_storage dies | `## Step B` item 1 — "Rung 4 classifies first: `broken:missing_storage` dies" |
| B.2 | Writer guard before the bypass; wedge-only bypass | `## Step B` item 2 — "calls `ait_require_data_paths` **first**, before the `AIT_GIT_SKIP_STATE_CHECK` bypass" |
| B.3 | Writer audit, with and without `--commit` | `## Step B` item 3 — "Every writer must reach the guard before its first write" |
| B.4 | Reader guards with ordering; others out of scope | `## Step B` item 4 — "`cross_repo_reexec_or_continue` … then argument parsing and the help/usage exits … then `ait_require_data_paths`" |
| B.5 | errexit audit, one test per site | `## Step B` item 5 — "Cover every new die path." |
| B.6 | `git-health` reporting if handed over | `## Step B` item 6 |
| B.7 | Legacy tokens, passthrough and prompt untouched (reverse-check addition) | `## Step B` item 7 — "Legacy behaviour stays untouched" |
| B.T1 | Broken states: all classes refuse | `### Step B tests` — "**Broken states:** every class refuses." |
| B.T2 | `unlinked`: git works, readers and writers refuse | same — "**`unlinked`:** git routing works" |
| B.T3 | Legacy / uninitialized controls | same — "**`legacy` and `uninitialized`:** positive controls, unchanged." |
| B.T4 | Dirty, untracked and ignored fixture data | same — "**Fixture data:** each fixture carries dirty, untracked and ignored data" |
| B.T5 | Command list incl. `update --batch` without `--commit`, with and without bypass | same — "**Commands under test:**" |
| B.T6 | Manifest + snapshots + positive control + mutant | same — "**No-mutation proof:**" |
| B.T7 | Missing storage: refuse, no code-branch commit, setup restores, re-read | same — "**Missing storage:**" |
| B.T8 | Bisect recovery | same — "**Bisect recovery:**" |
| B.T9 | Representative reads | same — "**Representative reads:**" |
| B.T10 | Reader ordering (broken source / broken dest / help) | same — "**Reader ordering**" |
| B.T11 | T13c / T13d acceptance | same — "**T13c / T13d acceptance:**" |
| B.T12 | errexit test per site | same — "**errexit:** one test per audited site." |
| C.1 | Repo-root resolution, fresh per call, never `snapshot()` | `## Merged from t2074_10` › `## Scope (Step C)` — "**Repo-root resolution, validated fresh.**" |
| C.2 | Inspection (C1a) vs mutation (C1a+C1b) classes | same — "**Two named operation classes**" |
| C.3 | Explicit class argument plus a caller-enumeration test | same — "`_task_git_cmd` takes an explicit class argument. A test enumerates every caller" |
| C.4 | Legacy `["git"]`; broken raises; callers never fall back | same — "Behaviour by state:" |
| C.5 | Board startup refusal; sync refusal toast | same — "**Board startup** applies the reader-class check" |
| C.6 | `desync_state`, `cross_repo_settings`, `REASON_DEST_LEGACY_LAYOUT` untouched | same — "**Not touched:**" |
| C.T1 | Non-root cwd resolves to the data worktree | `## Tests` — "From a non-root cwd, a valid layout resolves" |
| C.T2 | Broken fixture refused; no git on the code repo | same — "A broken `board_fixture` is refused" |
| C.T3 | Legacy board fixture works | same — "The legacy board fixture still works." |
| C.T4 | Transitions (a), (b), (c) with table-derived expectations | same — "**Same-process transitions.**" |
| C.T5 | No-mutation proof per refusal | same — "Every refusal must prove nothing changed:" |
| C.T6 | Cached-`snapshot()` planted control fails (a) | same — "Planted control: a variant that reads the cached `snapshot()`" |
| V.1 | Every bash test, run individually | `## Verification (whole child)` |
| V.2 | Python suite PASSED, with pipefail | same |
| V.3 | `shellcheck` | same |

Result: every requirement is located, and the reverse check added two
(A.7, B.7). Active requirements carry no pre-rescope text: the scan triage for
`quarantine`, `legacy fixture`, `NEEDS_CONVERSION`, `REASON_DEST_LEGACY_LAYOUT`,
`desync_state` and `snapshot()` matched only "unchanged / not touched"
statements, the display-only usage, and the planted control.
