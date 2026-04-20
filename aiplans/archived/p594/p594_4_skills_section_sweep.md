---
Task: t594_4_skills_section_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,2,3,5,6}_*.md
Depends on: t594_2 (canonical wording for pick/pickrem/pickweb)
Worktree: (none — work on current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-20 11:06
---

# t594_4 — Skills section coherence sweep — VERIFIED

## Context

Largest child of t594 (27 pages under `website/content/docs/skills/`). Depends on t594_2 which unified canonical core labels (Profile selection, Task status checks, Assignment, Environment setup, Planning, Implementation, Post-implementation) across pick/pickrem/pickweb. This child applies broader factual drift fixes, profile-field additions, `--profile` argument docs, per-skill SKILL.md diff, default-model alignment, related-skills cross-links, and `_index.md` category polish.

This plan was **re-verified against the current codebase on 2026-04-20** before implementation (fast-profile `plan_preference_child: verify`). The core items (A–F) remained accurate; the verification discovered additional per-skill drift items that are now folded into item D.

## Scope

**In-bounds:**
- Add missing profile fields to `skills/aitask-pick/execution-profiles.md` (standard + remote-mode).
- Document `--profile <name>` on `skills/aitask-explore.md`.
- Per-skill SKILL.md drift diff and fixes (major-step-structure level).
- Align default-model mentions with `DEFAULT_AGENT_STRING="claudecode/opus4_7_1m"`.
- Add "Related skills" cross-link sections where missing.
- Tighten category descriptions in `skills/_index.md` (do NOT reorder or change weights).

**Out-of-bounds:**
- Re-fixing core labels already canonicalized by t594_2.
- Reordering `skills/_index.md` category structure (weights preserved).
- Creating new skill documentation pages.
- Changing the shipped profile YAMLs (`aitasks/metadata/profiles/*.yaml`) or source scripts.

## Pre-verification findings (2026-04-20)

Confirmed still accurate:
- `skills/aitask-pick/execution-profiles.md` field table still ends at `qa_tier` (line 35). Standard fields `plan_verification_required`/`plan_verification_stale_after_hours` and all 8 remote-mode fields are MISSING.
- `.claude/skills/task-workflow/profiles.md:31-32` documents the verification fields with defaults (int, 1 and 24).
- `skills/aitask-pickrem.md:79-104` contains the remote-mode field table (can be mirrored or linked).
- `skills/aitask-explore.md` lines 10-13 show usage as `/aitask-explore` with no arguments documented; `.claude/skills/aitask-explore/SKILL.md:6-12` declares `--profile <name>`.
- `DEFAULT_AGENT_STRING="claudecode/opus4_7_1m"` lives at `.aitask-scripts/aitask_codeagent.sh:21` (plan cited line 27; off by 6, immaterial). Matches `aitasks/metadata/codeagent_config.json:3`.
- All five "Related" cross-link targets (`aitask-explore`, `aitask-pick/_index`, `aitask-review`, `aitask-wrap`, `aitask-contribute`) currently have NO Related section — clean additions.
- `skills/_index.md` organizes by weight-ordered categories (weights 10–70). No explicit "do not reorder" text in file, but sibling-task scope forbids reordering.
- 27 skills pages confirmed (24 top-level `.md` + `aitask-pick/` with 4 files + `_index.md` + `verified-scores.md`).

New drift items discovered during verification (folded into item D below):
- **aitask-explore step ordering drift:** docs list "Profile selection" as step 1, but `aitask-explore/SKILL.md` actually runs profile selection at Step 3b, AFTER task creation (Step 3). The docs give a misleading story.
- **aitask-qa missing step:** docs don't list "Satisfaction Feedback" (SKILL.md Step 7).
- **aitask-wrap missing callouts:** docs don't call out Step 1b (Check for Recent Claude Plans) or Step 6 (Satisfaction Feedback).
- **aitask-revert grouping difference:** docs split what SKILL.md has as a single Step 2 ("Task Analysis & Confirmation") into two items. Low priority — not a functional gap.

## Concrete drift items to fix

### A. Profile field additions to `skills/aitask-pick/execution-profiles.md`

Append to the Standard Profile Fields table (after `qa_tier`):

| Field | Type | Default | Purpose |
|---|---|---|---|
| `plan_verification_required` | int | `1` | Minimum fresh plan_verified entries required to skip verification in Step 6.0. |
| `plan_verification_stale_after_hours` | int | `24` | Age threshold for treating a plan_verified entry as stale. |

Source of truth: `.claude/skills/task-workflow/profiles.md:31-32`. Both fields are shipped in `fast.yaml:8-9`.

### B. Remote-only profile fields

Add a dedicated "Remote-mode fields" subsection on `skills/aitask-pick/execution-profiles.md` covering:

- `force_unlock_stale` — bool, default `false`.
- `done_task_action` — string, default `archive`.
- `orphan_parent_action` — string, default `archive`.
- `complexity_action` — string, default `single_task`.
- `review_action` — string, default `commit`.
- `issue_action` — string, default `close_with_notes`.
- `abort_plan_action` — string, default `keep`.
- `abort_revert_status` — string, default `Ready`.

Implementation choice: add a one-line pointer ("For remote-mode profile fields, see [/aitask-pickrem](../aitask-pickrem/#remote-mode-profile-fields)") rather than mirroring the full table, to avoid duplication drift risk. Confirm the anchor exists.

### C. `aitask-explore.md`: document `--profile <name>`

Add a "Usage" note after the current usage block showing:

```
/aitask-explore [--profile <name>]
```

Plus one sentence: "The optional `--profile <name>` argument overrides execution-profile selection for this invocation. Matches the `/aitask-pick --profile` behavior."

Source: `.claude/skills/aitask-explore/SKILL.md:6-12`.

### D. Per-skill SKILL.md diff pass

Priority order (most-used / highest-drift-risk first):

1. **`skills/aitask-pick/_index.md`** vs `.claude/skills/aitask-pick/SKILL.md` — hub skill. **No major drift found** (docs correctly summarize pick's Steps 0–2 + handoff note for Steps 3–9 from shared workflow).
2. **`skills/aitask-pickrem.md`** — **no major drift**. Steps align post-t594_2.
3. **`skills/aitask-pickweb.md`** — **no major drift**. All 9 listed items map to SKILL.md steps.
4. **`skills/aitask-explore.md`** — **FIX NEEDED.** Current docs order (Profile selection first) misrepresents SKILL.md where profile selection is Step 3b (AFTER task creation at Step 3). Rewrite step list to reflect real order:
   1. Exploration setup
   2. Iterative exploration
   3. Task creation (with related-task discovery)
   4. Profile selection
   5. Decision point / optional handoff
   Mention in prose that profile selection is deferred until task creation so exploration remains profile-independent.
5. **`skills/aitask-qa.md`** — **FIX NEEDED.** Add "Satisfaction feedback" as a final step item matching SKILL.md Step 7.
6. **`skills/aitask-review.md`** — no major drift. Steps align.
7. **`skills/aitask-fold.md`** — no major drift. Steps align.
8. **`skills/aitask-wrap.md`** — **MINOR FIX.** Add a brief mention of the Claude-Plans check (SKILL.md Step 1b) in the analysis step description; add "Satisfaction feedback" as the final step.
9. **`skills/aitask-revert.md`** — optional tidy. Current 7-item list works functionally; could condense to match SKILL.md's Step 2 grouping. **Skip unless trivial** — low value.
10. Remaining 18 pages — spot-check only; no pre-identified drift.

### E. Default-model alignment

Grep `website/content/docs/skills/` and `website/content/docs/concepts/` for model-name mentions. Expected primary hit: `skills/aitask-add-model.md`. Verify all mentions either use `claudecode/opus4_7_1m` (matching `.aitask-scripts/aitask_codeagent.sh:21`) or are deliberately generic ("replace with your default model"). Fix any stale-pinned model IDs.

### F. Related-skills cross-links

Add a small "## Related" section near the bottom of each file (before any "## Notes" or "## Workflows" terminal section):

- `aitask-explore.md` → `/aitask-fold`, `/aitask-pick`.
- `aitask-pick/_index.md` → `/aitask-qa`, `/aitask-review`, `/aitask-revert`.
- `aitask-review.md` → `/aitask-pick`.
- `aitask-wrap.md` → `/aitask-pick`.
- `aitask-contribute.md` → `/aitask-contribution-review`.

Use the phrasing already set by existing "Related" sections in `aitask-add-model.md` / `aitask-refresh-code-models.md` / `aitask-fold.md` ("See also") — keep style consistent.

### G. Category polish in `skills/_index.md`

Tighten description text only — do NOT reorder entries, do NOT change weights. Specific targets from verification:
- "Contributions" category intro — one-word redundancy with bullet descriptions (minor trim).
- Remaining categories — already lean; pass on them unless reading surfaces obvious churn.

## Authoritative sources

| Topic | Source |
|---|---|
| Each skill's step flow | `.claude/skills/<name>/SKILL.md` |
| Shared workflow steps | `.claude/skills/task-workflow/*.md` |
| Shipped profiles | `aitasks/metadata/profiles/*.yaml` |
| Canonical profile field list | `.claude/skills/task-workflow/profiles.md` |
| Default code-agent model | `.aitask-scripts/aitask_codeagent.sh:21`, `aitasks/metadata/codeagent_config.json` |
| Remote-mode field table (for pointer) | `website/content/docs/skills/aitask-pickrem.md:79-104` |

## Implementation plan

1. **Profile field additions** — item A (append 2 rows) and item B (add Remote-mode subsection with pointer).
2. **`--profile` on explore** — item C.
3. **Per-skill SKILL.md fixes** in this order:
   1. `aitask-explore.md` — reorder step list (D.4).
   2. `aitask-qa.md` — append satisfaction-feedback step (D.5).
   3. `aitask-wrap.md` — add Claude-Plans check mention + feedback step (D.8).
   4. `aitask-revert.md` — skip unless trivial (D.9).
   5. Spot-check the remaining 18 pages (D.10); fix only concrete drift.
4. **Default-model alignment** — item E (grep + fix).
5. **Related-skills cross-links** — item F (5 files).
6. **Category polish** — item G (descriptions only).
7. **Hugo build check** — `cd website && hugo build --gc --minify`. Expect 0 warnings (baseline: 148 pages, 0 warnings, ~750ms from t594_3 run on 2026-04-20).

## Verification

- `grep -n "plan_verification_required" website/content/docs/skills/aitask-pick/execution-profiles.md` returns a hit.
- `grep -n "plan_verification_stale_after_hours" website/content/docs/skills/aitask-pick/execution-profiles.md` returns a hit.
- `grep -n "Remote-mode" website/content/docs/skills/aitask-pick/execution-profiles.md` returns a hit OR an inline pointer to `/aitask-pickrem` is present.
- `grep -n "\-\-profile" website/content/docs/skills/aitask-explore.md` returns the new usage mention.
- `website/content/docs/skills/aitask-explore.md` step list shows "Profile selection" AFTER "Task creation".
- `grep -n "Satisfaction feedback\|Satisfaction Feedback" website/content/docs/skills/aitask-qa.md` returns a hit.
- `grep -rn "## Related\|## See also" website/content/docs/skills/aitask-{explore,review,wrap,contribute}.md website/content/docs/skills/aitask-pick/_index.md` — all 5 files return hits.
- `grep -rn "opus4_" website/content/docs/` — any remaining mention matches `claudecode/opus4_7_1m`.
- `cd website && hugo build --gc --minify` succeeds (0 warnings).

## Step 9 reference

No worktree (`create_worktree: false`). `verify_build` in `project_config.yaml` is null, so Hugo build verification is this task's responsibility (Step 7 of implementation). Archive via `./.aitask-scripts/aitask_archive.sh 594_4` after Step 8 approval.

## Final Implementation Notes

- **Actual work done:** 8 files touched under `website/content/docs/skills/`:
  - **Item A (`aitask-pick/execution-profiles.md`):** Appended `plan_verification_required` (int, default 1) and `plan_verification_stale_after_hours` (int, default 24) rows to the Standard Profile Fields table between `plan_preference_child` and `post_plan_action`.
  - **Item B (`aitask-pick/execution-profiles.md`):** Added a new `## Remote-Mode Profile Fields` section with a pointer to [/aitask-pickrem → Remote-Specific Profile Fields](../aitask-pickrem/#remote-specific-profile-fields). Chose pointer over table mirror to avoid duplication drift.
  - **Item C (`aitask-explore.md`):** Updated Usage block to `/aitask-explore [--profile <name>]` and added a one-sentence explanation that the argument mirrors `/aitask-pick --profile`.
  - **Item D.4 (`aitask-explore.md`):** Reordered step list — Profile selection was incorrectly listed as step 1; moved to step 4, AFTER Task creation, matching SKILL.md Step 3b. Added explanatory phrase: "Deferred until after task creation so exploration itself is profile-independent".
  - **Item D.5 (`aitask-qa.md`):** Appended step 9 "Satisfaction feedback" matching SKILL.md Step 7.
  - **Item D.8 (`aitask-wrap.md`):** Expanded step 3 "Analyze diff" to mention the `~/.claude/plans/` Claude-Plans check (SKILL.md Step 1b) in Claude Code. Appended step 7 "Satisfaction feedback".
  - **Item D.9 (`aitask-revert.md`):** Skipped per plan — current 7-item list is functionally accurate; re-grouping to match SKILL.md Step 2 would be cosmetic only.
  - **Item E (default-model alignment):** No edits needed. Grep confirmed all `opus4_7_1m` mentions in skills/ and concepts/ are correctly cited as the default; older `opus4_6` mentions are clearly labeled as schema examples in `codeagent.md` / `verified-scores.md`, not authoritative defaults.
  - **Item F (`aitask-{explore,review,wrap,contribute}.md` and `aitask-pick/_index.md`):** Added `## Related` sections at the bottom of all 5 target files with the cross-links specified in the plan (aitask-explore → fold, pick; pick/_index → qa, review, revert; review → pick; wrap → pick; contribute → contribution-review). Used the bullet-list style from `aitask-add-model.md`, not the inline "See also" style from `aitask-fold.md` — bullet form gives each link its own short rationale.
  - **Item G (`_index.md`):** Tightened Task Management category description — dropped inaccurate "import" from "Create, organize, import, and wrap tasks." (no Task Management skill actually imports; import lives in Contributions). Left all weights/order unchanged. Other category descriptions passed unchanged on review (Contributions description was briefly considered for a trim but was semantically accurate about the bidirectional nature — kept).
- **Deviations from plan:** None — plan was verified and corrected before implementation (see Pre-verification findings and the ASK_STALE-like drift discoveries that were folded into item D before coding began).
- **Issues encountered:**
  1. First attempt at the `aitask-pick/_index.md` Related-section edit used a relative path of `../../workflows/` that doesn't match the actual file, which uses `../../workflows/`. The file already had the correct form; my first Edit call matched against a 3-level path I'd mentally fabricated. Re-read the file, used the real string, applied cleanly.
- **Key decisions:**
  - **Remote-mode fields (B):** Chose pointer-only form over mirroring the full 8-row table. Rationale: `/aitask-pickrem` already owns the canonical remote-mode field table with types/defaults; duplicating it into `execution-profiles.md` would create a two-place-update burden and guaranteed drift over time. The pointer keeps a single source of truth.
  - **aitask-explore step reorder (D.4):** The docs had Profile selection as step 1, but SKILL.md actually runs it at Step 3b (AFTER task creation). This is a user-visible factual inaccuracy in the docs, not just a label difference. Fixed by reordering the numbered list. Added a trailing clause explaining *why* profile selection is deferred, because moving the item without context would raise "why is this last?" questions.
  - **aitask-revert (D.9) skipped:** Plan already marked it as optional. The 7-item docs list covers all major steps from SKILL.md; the difference is one grouping (Task Analysis & Confirmation → split into "Task analysis" + "Selection and confirmation"). Both forms convey the same information to a reader. Reshaping for parity alone would risk introducing churn without improving clarity.
  - **Related sections placement (F):** Placed AFTER the final narrative section on each page (after Workflows) but BEFORE any EOF. This puts cross-links at the natural "where to go next" reading position.
- **Notes for sibling tasks (t594_5, t594_6):**
  - **Drift discovery discipline:** Pre-implementation verification (fast profile `plan_preference_child: verify`) surfaced 3 additional fix items (aitask-explore step order, aitask-qa feedback step, aitask-wrap feedback + claude-plans mention) that the original plan didn't enumerate. Apply the same pattern: before editing, diff `website/content/docs/skills/<name>.md` against `.claude/skills/<name>/SKILL.md` for structural (not wording) drift.
  - **Cross-reference style for Related sections:** Use the `## Related` bullet form from `aitask-add-model.md`, not the inline `**See also:**` form. Each link gets one short rationale. Placed after `## Workflows` on skill pages.
  - **Remote-mode field pointer:** Any future cross-linking to remote-mode fields should point to `#remote-specific-profile-fields` in `/aitask-pickrem`, which is the canonical location.
  - **Default model:** `claudecode/opus4_7_1m` is confirmed current in `.aitask-scripts/aitask_codeagent.sh:21` and `codeagent_config.json`. `opus4_6` appears in docs only as schema examples — don't treat those as stale.
  - **Category structure in `_index.md`:** Descriptions may be tightened, but categories themselves must not be reordered or reweighted. "Import" does NOT belong in Task Management (no import skill there).
- **Build verification:** `cd website && hugo build --gc --minify` — 148 pages, 0 warnings, 833 ms.
