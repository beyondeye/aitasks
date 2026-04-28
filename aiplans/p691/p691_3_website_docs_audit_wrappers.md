---
Task: t691_3_website_docs_audit_wrappers.md
Parent Task: aitasks/t691_audit_and_port_aitask_wrappers_across_code_agents.md
Sibling Tasks: aitasks/t691/t691_1_phase1_skill_wrapper_audit_port.md, aitasks/t691/t691_2_phase2_helper_whitelist_audit.md
Archived Sibling Plans: aiplans/archived/p691/p691_*_*.md
Worktree: (current branch)
Branch: main
Base branch: main
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
