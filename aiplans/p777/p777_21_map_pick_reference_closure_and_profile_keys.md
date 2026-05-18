---
Task: t777_21_map_pick_reference_closure_and_profile_keys.md
Parent Task: aitasks/t777_modular_pick_skill.md
Sibling Tasks: aitasks/t777/t777_*_*.md
Archived Sibling Plans: aiplans/archived/p777/p777_*_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# Plan: t777_21 — Map pick-skill reference closure and profile-key usage

## Context

t777 redesigns execution-profile handling by pre-rendering skills via Jinja templates (minijinja). The pilot (t777_6) converted `aitask-pick/SKILL.md` alone — but Step 3 of that skill immediately hands off to `task-workflow/SKILL.md`, which itself loads ~16 sub-procedures, many containing their own runtime `Profile check:` blocks. Without a recursive renderer (t777_22) and conversion of every shared procedure (t777_7), the templating model leaks at the first hand-off.

This audit walks the static markdown-reference closure starting from `.claude/skills/aitask-pick/SKILL.md`, enumerates every profile-driven runtime branch within that closure, and surfaces the exact edit list for t777_7 + the golden-file test corpus for t777_22. **No code changes — the deliverable is this discovery document.**

## Methodology

1. **Closure walk (BFS, cycle-detected):** start at `.claude/skills/aitask-pick/SKILL.md`. For each file, extract every `<name>.md` reference and resolve against:
   - `.claude/skills/<dir>/<name>.md` (absolute repo-relative)
   - `<curdir>/<name>.md` (sibling)
   - `<other-skill>/<name>.md` under `.claude/skills/`
   Example task filenames matching `t\d+_*` (e.g., `t16_implement_auth.md`) are excluded as illustrative content, not real refs.

2. **Branch-site detection:** for each closure file, grep for runtime profile-conditional sites using:
   ```python
   re.compile(r'(Profile check[.:]|If the active profile|active profile has|active profile exists|If the effective action is|profile-(?:driven|aware))', re.IGNORECASE)
   ```
   This catches the canonical `**Profile check:**` heading style (most common) plus variants used by `remote-drift-check.md` (`**Profile check.**` — period) and `manual-verification-followup.md` (`If the active profile has …`).

3. **Key extraction:** for each detected branch site, scan a 9-line window (the site line + next 8 lines) for backticked tokens matching the known profile-key set defined in `fast.yaml` + `remote.yaml` + the keys observed in `profiles.md`. Known keys consulted:
   ```
   skip_task_confirmation, default_email, create_worktree, plan_preference,
   plan_preference_child, plan_verification_required,
   plan_verification_stale_after_hours, post_plan_action,
   post_plan_action_for_child, enableFeedbackQuestions, explore_auto_continue,
   qa_mode, manual_verification_followup_mode, base_branch, remote_drift_check
   ```

## Reference closure (23 files)

BFS from `.claude/skills/aitask-pick/SKILL.md`:

```
.claude/skills/aitask-pick/SKILL.md                                  [root]
.claude/skills/task-workflow/SKILL.md
.claude/skills/task-workflow/agent-attribution.md
.claude/skills/task-workflow/code-agent-commit-attribution.md
.claude/skills/task-workflow/contributor-attribution.md
.claude/skills/task-workflow/crash-recovery.md
.claude/skills/task-workflow/execution-profile-selection-auto.md
.claude/skills/task-workflow/execution-profile-selection.md
.claude/skills/task-workflow/issue-update.md
.claude/skills/task-workflow/lock-release.md
.claude/skills/task-workflow/manual-verification-followup.md
.claude/skills/task-workflow/manual-verification.md
.claude/skills/task-workflow/model-self-detection.md
.claude/skills/task-workflow/plan-externalization.md
.claude/skills/task-workflow/planning.md
.claude/skills/task-workflow/pr-close-decline.md
.claude/skills/task-workflow/profiles.md
.claude/skills/task-workflow/remote-drift-check.md
.claude/skills/task-workflow/repo-structure.md
.claude/skills/task-workflow/satisfaction-feedback.md
.claude/skills/task-workflow/task-abort.md
.claude/skills/task-workflow/task-creation-batch.md
.claude/skills/task-workflow/upstream-followup.md
```

**Not in closure (referenced from CLAUDE.md only, not from any skill file):**
- `.claude/skills/task-workflow/stub-skill-pattern.md` — authoring reference for stub-skill design, consumed by humans/agents reading CLAUDE.md, not loaded by any runtime skill.

**Cycle edges detected (resolved by visited-set):** `execution-profile-selection.md ↔ execution-profile-selection-auto.md`, `contributor-attribution.md ↔ code-agent-commit-attribution.md`, and the `SKILL.md → planning.md → SKILL.md` back-reference among others.

## Per-file profile-driven branches

| File | Branch sites | Lines | Profile keys (in branch windows) | Other profile keys mentioned in file |
|------|--------------|-------|---------------------------------|--------------------------------------|
| `aitask-pick/SKILL.md` | 2 | 44, 72 | `skip_task_confirmation` | — |
| `task-workflow/SKILL.md` | 4 | 98, 183, 198, 226 | `base_branch`, `create_worktree`, `default_email` | `post_plan_action`, `skip_task_confirmation` (mentioned in Step 8 NON-SKIPPABLE note as keys that do *not* cover review) |
| `task-workflow/planning.md` | 5 | 29, 35, 291, 294, 299 | `base_branch`, `plan_preference`, `plan_preference_child`, `plan_verification_required`, `plan_verification_stale_after_hours`, `post_plan_action`, `post_plan_action_for_child` | — |
| `task-workflow/manual-verification-followup.md` | 1 | 19 | `manual_verification_followup_mode` | — |
| `task-workflow/remote-drift-check.md` | 1 | 17 | — (key `remote_drift_check` appears as `\`remote_drift_check: skip\`` so window-grep for bare token misses; key IS used at the site) | `base_branch` |
| `task-workflow/satisfaction-feedback.md` | 1 | 34 | `enableFeedbackQuestions` | — |
| `task-workflow/agent-attribution.md` | 0 | — | — | — |
| `task-workflow/code-agent-commit-attribution.md` | 0 | — | — | — |
| `task-workflow/contributor-attribution.md` | 0 | — | — | — |
| `task-workflow/crash-recovery.md` | 0 | — | — | — |
| `task-workflow/execution-profile-selection-auto.md` | 0 | — | — | — |
| `task-workflow/execution-profile-selection.md` | 0 | — | — | — |
| `task-workflow/issue-update.md` | 0 | — | — | — |
| `task-workflow/lock-release.md` | 0 | — | — | — |
| `task-workflow/manual-verification.md` | 0 | — | — | — |
| `task-workflow/model-self-detection.md` | 0 | — | — | — |
| `task-workflow/plan-externalization.md` | 0 | — | — | — |
| `task-workflow/pr-close-decline.md` | 0 | — | — | — |
| `task-workflow/profiles.md` | 0 | — | — | All keys appear as reference documentation (this file is the profile schema), not as runtime branches |
| `task-workflow/repo-structure.md` | 0 | — | — | — |
| `task-workflow/task-abort.md` | 0 | — | — | — |
| `task-workflow/task-creation-batch.md` | 0 | — | — | — |
| `task-workflow/upstream-followup.md` | 0 | — | — | — |

### Sample conditional text (one per file with branch sites)

- **`aitask-pick/SKILL.md:44`** — `- **Profile check:** If the active profile has \`skip_task_confirmation\` set to \`true\`:`
- **`task-workflow/SKILL.md:98`** — `5. **Profile check:** If the active profile has \`default_email\` set:`
- **`task-workflow/SKILL.md:183`** — `- **Profile check:** If the active profile has \`create_worktree\` set:`
- **`task-workflow/SKILL.md:198`** — `- **Profile check:** If the active profile has \`base_branch\` set:`
- **`task-workflow/planning.md:29`** — `**Profile check:** If the active profile has \`plan_preference\` set (or \`plan_preference_child\` for child tasks ...):`
- **`task-workflow/planning.md:291`** — `1. If \`is_child\` is true AND the active profile has \`post_plan_action_for_child\` set, use \`post_plan_action_for_child\` as the effective action.`
- **`task-workflow/planning.md:294`** — `**Profile check:** If the effective action is \`"start_implementation"\`:`
- **`task-workflow/manual-verification-followup.md:19`** — `If the active profile has \`manual_verification_followup_mode\` set to \`"never"\`, display:`
- **`task-workflow/remote-drift-check.md:17`** — `1. **Profile check.** If the active profile has \`remote_drift_check: skip\`, return immediately with no display.`
- **`task-workflow/satisfaction-feedback.md:34`** — `1. **Profile check:** If the active profile exists and \`enableFeedbackQuestions\` is set to \`false\`, skip the remainder of Step 1.`

### Branch-site false-positive / detection notes

- **`task-workflow/SKILL.md:226`** — matched by the regex (`"Profile check"` in a *cross-reference* to `planning.md`'s checkpoint section), but is descriptive prose, not an own conditional. Counted in the table for honesty, but t777_7 only needs to wrap the three real `**Profile check:**` blocks (L98, L183, L198) — L226 is just narrative. The three real keys consumed remain `default_email`, `create_worktree`, `base_branch`.
- **`task-workflow/planning.md:35`** — matched by `profile-driven` substring (the heading `**Verify Decision sub-procedure** (profile-driven verify path only):`), which sits *inside* the L29 Profile-check block. It is not a separate branch; counted as a site for traceability only.
- **`task-workflow/planning.md:299`** — matched by `If the effective action is` (the *else* branch of the L294 conditional). t777_7 will likely express L294 + L299 as one `{% if profile.post_plan_action == "start_implementation" %} … {% else %} … {% endif %}` block.
- **`task-workflow/remote-drift-check.md:17`** — the key `remote_drift_check` IS the conditional, but appears in the file as the inline backticked phrase `\`remote_drift_check: skip\`` rather than a bare token, so the 9-line window grep does not extract it. Treat this row as: site=1, key=`remote_drift_check`. (Documented in the table's "Profile keys (in branch windows)" column with the clarifying note.)

## Summary

### Files needing t777_7 edits (6 of 23 — ~26%)

| File | Branch sites | Keys to wrap |
|------|--------------|--------------|
| `aitask-pick/SKILL.md` | 2 | `skip_task_confirmation` |
| `task-workflow/SKILL.md` | 3 (real) | `default_email`, `create_worktree`, `base_branch` |
| `task-workflow/planning.md` | 3 (real) | `plan_preference`, `plan_preference_child`, `plan_verification_required`, `plan_verification_stale_after_hours`, `post_plan_action`, `post_plan_action_for_child` |
| `task-workflow/manual-verification-followup.md` | 1 | `manual_verification_followup_mode` |
| `task-workflow/remote-drift-check.md` | 1 | `remote_drift_check` |
| `task-workflow/satisfaction-feedback.md` | 1 | `enableFeedbackQuestions` |

**Note on aitask-pick/SKILL.md:** the pilot conversion (t777_6) has already converted this file to a `.j2` template. The 2 sites listed are the conversion footprint that needs to be re-validated after t777_22 lands the recursive walker (the recursive walker will newly cover the 5 shared procs above, but the pilot conversion of `aitask-pick/SKILL.md` itself is already in place).

### Files passing through identity-render (17 of 23 — ~74%)

These have **zero profile-driven branches**. Under the t777_22 recursive renderer they should serialize byte-identically to source (i.e. their `.j2` form, if introduced, is just a copy of the `.md`). They form the **passthrough corpus** for the t777_22 golden-file tests:

```
agent-attribution.md
code-agent-commit-attribution.md
contributor-attribution.md
crash-recovery.md
execution-profile-selection-auto.md
execution-profile-selection.md
issue-update.md
lock-release.md
manual-verification.md
model-self-detection.md
plan-externalization.md
pr-close-decline.md
profiles.md
repo-structure.md
task-abort.md
task-creation-batch.md
upstream-followup.md
```

### Profile-key universe consumed by the pick closure (12 keys)

```
base_branch                              create_worktree
default_email                            enableFeedbackQuestions
manual_verification_followup_mode        plan_preference
plan_preference_child                    plan_verification_required
plan_verification_stale_after_hours      post_plan_action
post_plan_action_for_child               remote_drift_check
skip_task_confirmation
```

**Keys defined in `fast.yaml` but NOT consumed by any pick-closure file** (so the pick-closure tests need not cover them):
- `explore_auto_continue` — consumed only by the aitask-explore closure (out of scope here)
- `qa_mode` — consumed only by the aitask-qa closure (out of scope here)

## Implications

### For t777_22 (recursive renderer + golden-file tests)

- **Golden-file corpus must cover at minimum 6 × N profile combinations** for the 6 branch-bearing files, where N is the number of profiles that change behavior at any of the keys consumed by that file. Concretely:
  - `aitask-pick/SKILL.md`: 2 profiles suffice (`skip_task_confirmation: true|false`).
  - `task-workflow/planning.md`: largest matrix — at least 8 combinations across `plan_preference ∈ {use_current, verify, create_new}`, `post_plan_action ∈ {ask, start_implementation}`, and `plan_verification_*` thresholds.
  - 17 identity-render files form a single passthrough corpus — assert byte-identical output across any profile.
- **Cycle-detect at walk time** — confirmed cycles in the static reference graph (`SKILL.md ↔ planning.md`, `execution-profile-selection.md ↔ execution-profile-selection-auto.md`, etc.). The visited-set used in this audit's BFS must be carried into the renderer's walker.
- **Reference-rewrite scope:** the recursive renderer needs to rewrite `.md` cross-references inside rendered output to point at the per-profile rendered tree (e.g. `aitask-pick-fast-/`), or leave them as `.md` and rely on the agent to resolve them against the rendered dir. Decision deferred to t777_22 plan.

### For t777_7 (convert task-workflow shared procs)

- **Edit list is exactly the 5 task-workflow files** above (excluding `aitask-pick/SKILL.md`, which t777_6 already converted):
  1. `task-workflow/SKILL.md` — 3 sites
  2. `task-workflow/planning.md` — 3 sites (largest)
  3. `task-workflow/manual-verification-followup.md` — 1 site
  4. `task-workflow/remote-drift-check.md` — 1 site (key in backticked phrase — be careful when wrapping)
  5. `task-workflow/satisfaction-feedback.md` — 1 site

- **Total real `{% if profile.X %}` wrapping sites: 9** across 5 files (3+3+1+1+1).

- **No edits needed in 17 identity-render files** — at most they may need empty `.j2` stubs (effectively copies) if the renderer requires every closure file to be a template.

## Verification

- **Reproducibility of closure walk:** the BFS algorithm + reference resolver above (small Python snippet) can be re-run on any future checkout. Expected output: 23 files.
- **Reproducibility of branch-site enumeration:**
  ```bash
  grep -lrE 'Profile check[.:]|If the active profile|active profile has|profile-driven' \
    .claude/skills/aitask-pick/SKILL.md \
    .claude/skills/task-workflow/*.md
  ```
  Expected 6 file matches (the 6 in the "needing edits" table).
- **Stub-skill-pattern.md absence confirmed:**
  ```bash
  grep -lr 'stub-skill-pattern' .claude/skills/
  ```
  Expected: empty (it is referenced from CLAUDE.md only, not from any skill file).

## Out of scope

- Code changes — this is a discovery / audit task only. No `.j2` conversions, no renderer extensions, no profile-key additions.
- Closure walks for other skill roots (explore, fold, qa, etc.) — those are owned by their respective t777_8 / t777_10 / t777_11 / etc. children.
- Decisions on how t777_22 should rewrite cross-references in rendered output (deferred to t777_22 planning).
- Hand-coded test fixtures for t777_22 — this audit identifies the corpus shape; t777_22 builds the fixtures.

## Step 9 — Post-Implementation

Standard child-task archival via `./.aitask-scripts/aitask_archive.sh 777_21`. No code commit, only the plan-file commit; the plan IS the deliverable. The "Final Implementation Notes" section can be a one-liner ("Discovery document complete — see body for closure list, table, and edit summary") since the audit findings already live in this document body.

## Final Implementation Notes

- **Actual work done:** Discovery audit complete — see the body of this document for the BFS closure (23 files), the per-file branch-site table, the 6-file edit list for t777_7, the 17-file passthrough corpus for t777_22, and the 12-key profile-key universe. No code changes.

- **Deviations from plan:** None. Both verification commands produced the expected output: the branch-site grep matched exactly the 6 files listed in the "Files needing t777_7 edits" table, and `stub-skill-pattern.md` is not referenced from any closure file (confirming the CLAUDE.md-only origin).

- **Issues encountered:** Two regex-detection edge cases worth noting for sibling consumers:
  - `task-workflow/remote-drift-check.md:17` uses `**Profile check.**` (period, not colon). Future audits/walkers should accept both.
  - The key `remote_drift_check` appears in that file as the inline backticked phrase `` `remote_drift_check: skip` `` rather than a bare token, so a naive bare-token grep within a window misses it. The key IS used — t777_7 will need to wrap the conditional.

- **Key decisions:**
  - Closure is exactly 23 files. `stub-skill-pattern.md` is intentionally excluded (not referenced from any runtime skill file).
  - The 17 identity-render files should form a single passthrough corpus in t777_22's golden-file tests — assert byte-identical output across any profile.
  - `aitask-pick/SKILL.md` is listed under "Files needing t777_7 edits" for completeness, but t777_6 already converted it to a `.j2` template. t777_7's net new edit list is the 5 task-workflow files (9 real `{% if profile.X %}` wrapping sites total: 3+3+1+1+1).

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t777_22 (recursive renderer):** Use the BFS algorithm in §Methodology. Carry a visited-set — confirmed cycles exist (`SKILL.md ↔ planning.md`, `execution-profile-selection.md ↔ execution-profile-selection-auto.md`, `contributor-attribution.md ↔ code-agent-commit-attribution.md`). The renderer's reference-rewrite policy (rewrite `.md` cross-refs to per-profile rendered dir vs. leave as `.md`) is still open — pick during t777_22 planning.
  - **t777_7 (convert shared procs):** Edit list is precise and exhaustive (5 files, 9 sites). Largest matrix is `planning.md` (~8 profile combinations needed for golden-file coverage). The `remote-drift-check.md` site needs special care because the key is in a backticked-phrase form rather than a bare token.
  - **Out-of-pick-closure keys:** `explore_auto_continue` and `qa_mode` are NOT consumed in the pick closure — they will surface in t777_8 (explore) and t777_11 (qa) closure audits respectively. Future siblings doing the same audit for their own root should expect to find them.
