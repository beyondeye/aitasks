---
Task: t691_3_website_docs_audit_wrappers.md
Parent Task: aitasks/t691_audit_and_port_aitask_wrappers_across_code_agents.md
Sibling Tasks: aitasks/t691/t691_1_phase1_skill_wrapper_audit_port.md, aitasks/t691/t691_2_phase2_helper_whitelist_audit.md
Archived Sibling Plans: aiplans/archived/p691/p691_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-28 12:06
---

# Plan: t691_3 — Website documentation for `aitask-audit-wrappers`

## Summary

Add a per-skill page on the project website for the new `aitask-audit-wrappers` skill (introduced by t691_1 + t691_2). Update the existing `aitask-add-model.md` page to cross-reference it. Add a row to `_index.md`. Build the site to confirm no broken links.

## Depends on

- t691_2 (so the docs can describe both phases accurately).
- Read `aiplans/archived/p691/p691_1_*.md` and `aiplans/archived/p691/p691_2_*.md` for the implemented skill and helper-script details. Pull exact CLI flags, structured-output line formats, and confirmation-gate UX directly from those archived plans.

## Files

**New:** `website/content/docs/skills/aitask-audit-wrappers.md`

**Edit:**
- `website/content/docs/skills/aitask-add-model.md` — additive cross-reference paragraph.
- `website/content/docs/skills/_index.md` — one row added under "Configuration & Reporting".

## Step 1 — Write the new page

Frontmatter:

```yaml
---
title: "/aitask-audit-wrappers"
linkTitle: "/aitask-audit-wrappers"
weight: 57
description: "Audit and port aitask skill wrappers across code-agent trees, plus helper-script whitelist coverage"
maturity: [experimental]
depth: [advanced]
---
```

Sections (in order):

1. **Lead paragraph** — what the skill does, why a multi-agent framework needs it. Mention the four wrapper trees and the two `activate_skill` policy lists explicitly so users searching for `.gemini/commands` or `.opencode/skills` find the page.
2. **Usage** — example invocations (no-arg, `--phase=skills`, `--phase=whitelist`, `--phase=all`).
3. **When to Use** — note that this is a developer-facing skill: useful when adding a new `.claude/skills/aitask-*` or a new `.aitask-scripts/aitask_*.sh` helper. Reference the manual one-off port performed in t689 as the motivating example.
4. **Phase 1 — wrapper audit and port** — describe the 4 wrapper trees, the source-of-truth principle, the structured `GAP:` and `POLICY_GAP:` discovery output, and the per-gap AskUserQuestion gate. Show the `WROTE:` apply output.
5. **Phase 2 — helper-script whitelist** — describe the 5 touchpoints (with link to CLAUDE.md "Adding a New Helper Script"), the `MISSING:<touchpoint>:<helper>` discovery output, and the matrix shown to the user.
6. **Output** block — show example `GAP:`/`POLICY_GAP:`/`MISSING:`/`WROTE:`/`COMMITTED:` lines verbatim.
7. **Self-bootstrap** — short note that wrappers for a brand-new skill must be hand-written for the first run because the audit helper cannot port a skill that does not yet exist in the wrapper trees.
8. **Idempotency** — show that re-running produces no `GAP:`/`POLICY_GAP:`/`MISSING:` output.
9. **Cross-links** — `aitask-add-model` (sibling dev-only skill), CLAUDE.md "WORKING ON SKILLS / CUSTOM COMMANDS" + "Adding a New Helper Script", `tests/test_opencode_setup.sh` + `tests/test_gemini_setup.sh` (verification).

Use the existing `aitask-add-model.md` (78 lines) and `aitask-refresh-code-models.md` for tone, voice, and section-heading style.

## Step 2 — Update `aitask-add-model.md`

Add a paragraph (additive only) near the end of the page:

```markdown
## Drift detection

Drift between `.claude/skills/` (the source of truth for skills) and the four
wrapper trees that ship to other code agents is now caught automatically by
[`/aitask-audit-wrappers`](../aitask-audit-wrappers/). Run that skill after
adding or modifying a skill in `.claude/skills/aitask-*/SKILL.md` to keep all
agent trees in sync.
```

No content removal; existing sections stay intact.

## Step 3 — Update `_index.md`

Under the existing "Configuration & Reporting" table (where `/aitask-add-model`, `/aitask-refresh-code-models`, `/aitask-stats`, `/aitask-changelog` already live), add a row:

```markdown
| [`/aitask-audit-wrappers`](aitask-audit-wrappers/) | Audit and port skill wrappers across all code-agent trees |
```

Do not introduce a "Framework Development" subsection — that grouping change is reserved for the sibling t697 (analyze dev-only skill filtering); this child only adds one row to the existing structure.

## Step 4 — Build verification

```bash
cd website && hugo build --gc --minify
```

Watch for warnings touching the new or edited pages (broken refs, missing weights, frontmatter validation). All must pass cleanly.

Optionally, run the local dev server (`./serve.sh`) and visually confirm:
- New page resolves at `/docs/skills/aitask-audit-wrappers/`.
- Skills `_index.md` table shows the new row.
- Cross-links from `aitask-add-model.md` resolve.

## Step 9 — Post-implementation

- Code commit (regular `git`): the new page + edits to existing pages.
- Plan commit (`./ait git`): this plan file with Final Implementation Notes.
- Archive via `./.aitask-scripts/aitask_archive.sh 691_3`.
- When the last child archives, parent t691 archives automatically.

## Final Implementation Notes

- **Actual work done:** Created `website/content/docs/development/skills/aitask-audit-wrappers.md` (~95 lines, weight 57, `maturity: [experimental]`, `depth: [advanced]`) modeled on the existing `aitask-add-model.md` page. Sections: lead paragraph, Usage block, When to Use comparison table (manual port vs. automated audit), Phase 1 details with the 4 wrapper trees + 2 policy files enumerated, Phase 2 details with the 5-touchpoint table, Output reference for structured `KEY:value` lines, Self-bootstrap explanation, Idempotency assertions linking to the setup tests, and Related links to `aitask-add-model` and CLAUDE.md. Created `website/content/docs/development/skills/_index.md` as the landing page for the new "Framework Development Skills" subsection (weight 80) listing the new audit-wrappers page. Updated `aitask-add-model.md` with an additive "Drift detection" section that cross-references the audit-wrappers page at the new path.

- **Deviations from plan:**
  1. **Page location moved per user direction.** Original plan placed the new page at `website/content/docs/skills/aitask-audit-wrappers.md` alongside other aitask-* pages. During Step 8 review the user requested a dedicated subpage under the development tree. Final location: `website/content/docs/development/skills/aitask-audit-wrappers.md`, with a new `development/skills/_index.md` landing page. This separates dev-only / framework-internal skills from the user-facing skills index — anticipating the recommendation t697 will likely make.
  2. **Did NOT add a row to user-facing `_index.md`** (Configuration & Reporting table) as the original plan called for. The page now lives under `/docs/development/skills/` and is surfaced via the new development-tree subsection's `_index.md` instead. Cleaner separation than the plan envisioned.
  3. **Cross-reference path adjusted** in `aitask-add-model.md`: link is now `(../../development/skills/aitask-audit-wrappers/)` instead of `(../aitask-audit-wrappers/)` to reflect the new location.
  4. **Two unrelated `relref "skills"` shortcodes disambiguated.** The new `development/skills/_index.md` introduced a second page with `linkTitle: "Skills"`, which Hugo flagged as ambiguous when resolved by short name. Updated `website/content/docs/workflows/_index.md` and `website/content/docs/workflows/task-consolidation.md` to use the explicit `{{< relref "/docs/skills" >}}` form (was `{{< relref "skills" >}}`) so the user-facing skills index is unambiguously referenced. Both files functionally render the same — the change is internal to Hugo's link resolution.

- **Issues encountered:**
  - Initial Hugo build after the move emitted two `REF_NOT_FOUND: page reference "skills" is ambiguous` errors — root cause: the `development/skills/_index.md` introduces a second "skills" page, and existing references in `workflows/` resolved short. Fix: use full content paths in the existing `relref` calls (see deviation #4).

- **Key decisions:**
  - The new development-skills landing page (`development/skills/_index.md`) has TWO tables: "Pure framework-development skills" (just `aitask-audit-wrappers` for now) and "Useful for framework development *and* normal use" (cross-references back to `aitask-add-model`, `aitask-refresh-code-models`, `aitask-changelog` at their canonical `/docs/skills/` locations). The latter group is *linked*, not moved — these pages stay where users can find them.
  - `aitask-add-model.md`, `aitask-refresh-code-models.md`, and `aitask-changelog.md` were NOT moved. Only the new `aitask-audit-wrappers.md` page lives under `development/skills/`. The cross-reference structure means contributors browsing the development tree can find the skills relevant to their work without forcing the canonical location of any user-facing skill to change.
  - When t697 lands and decides which (if any) other skills are *purely* dev-only, those pages can move into the "Pure framework-development skills" table here.

- **Key decisions:**
  - Kept the page in `skills/` alongside other aitask-* pages (rather than creating a new `framework-development/` subsection). Rationale: the page exists for users navigating directly to it; the grouping question (separate subsection vs. integration into Configuration & Reporting vs. omission from index) is exactly what t697 is tasked to decide.
  - Used the same maturity/depth tags as `aitask-add-model.md` (`experimental` / `advanced`). These signal that the page is for advanced users / framework developers.
  - Linked CLAUDE.md from the Related section using a github.com link (the repository hosts the canonical CLAUDE.md). For `tests/test_*_setup.sh` references, also linked github.com so the docs work as a static site without needing relative-path navigation into the source tree.

- **Upstream defects identified:** None.

- **Notes for sibling tasks:**
  - **t697 (dev-only filtering analysis):** the new aitask-audit-wrappers.md page exists but is intentionally not surfaced in `_index.md`. When t697 lands, it will recommend (a) add to existing tables, (b) create a "Framework Development" subsection in `_index.md`, or (c) filter the page out of the docs build entirely. Either way, this child task left the file in place to support whichever direction t697 chooses.
  - The `aitask-add-model.md` "Drift detection" section is purely additive — t697 can preserve or remove it cleanly.

- **Verification results:** `cd website && hugo build --gc --minify` exits 0 with 173 pages built (was 172). New page rendered at `public/docs/skills/aitask-audit-wrappers/index.html`. Updated cross-link from `aitask-add-model.md` rendered correctly.
