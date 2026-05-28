---
Task: t835_4_agy_documentation.md
Parent Task: aitasks/t835_add_agy_antigravity_cli_support.md
Sibling Tasks: aitasks/t835/t835_1_*.md, aitasks/t835/t835_2_*.md, aitasks/t835/t835_3_*.md, aitasks/t835/t835_5_*.md, aitasks/t835/t835_6_*.md
Archived Sibling Plans: aiplans/archived/p835/p835_1_*.md, p835_2_*.md, p835_3_*.md (after they archive)
Inverse Blueprint: aiplans/archived/p812/p812_4_remove_geminicli_documentation.md
Worktree: (none — fast profile, current branch)
Branch: main
Base branch: main
---

## Overview

Add `Antigravity CLI (agy)` to every user-facing documentation
surface: top-level prose, website docs, internal `aidocs/` reference
tables, and skill-closure source files. Then regenerate affected
goldens in the same commit per CLAUDE.md. Apply CLAUDE.md's
genericization rule — leave "Claude Code and all other supported
coding agents" prose intact; only add explicit `agy` rows where
enumerations are normative.

The full file-by-file plan lives in the task description. The
**load-bearing reference** is the `### For t814 (add-agy): inverse
instructions` subsection in
`aiplans/archived/p812/p812_4_remove_geminicli_documentation.md`.

## Order of operations

1. **Top-level prose:** `README.md`, `CLAUDE.md` — add
   `Antigravity CLI (agy)` to normative enumerations only.
   `CHANGELOG.md` — new entry under next pending release.

2. **Skill closure sources** — add agy to enumerations / detection
   branches in:
   - `.claude/skills/task-workflow/{model-self-detection,satisfaction-feedback,plan-externalization}.md`
   - `.claude/skills/aitask-{add-model,refresh-code-models,audit-wrappers}/SKILL.md` (or `.md.j2`)

3. **Website normative pages** — add agy rows in:
   - `commands/codeagent.md` (CLI mapping table + list-agents/list-models examples)
   - `installation/known-issues.md` (NEW `## Antigravity CLI` H2 modeled on Codex section)
   - `installation/updating-model-lists.md`
   - `installation/windows-wsl.md`
   - `skills/aitask-add-model.md`
   - `development/skills/aitask-audit-wrappers.md` (use IDs from t835_2)
   - `tuis/settings/{_index,how-to,reference}.md`

4. **Website genericized pages** — leave intact unless enumeration
   is genuinely normative for agy. Suspect set:
   `_index.md`, `about/_index.md`, `docs/overview.md`,
   `docs/getting-started.md`, `docs/skills/_index.md`,
   `docs/installation/_index.md`,
   `docs/concepts/{agent-attribution,verified-scores}.md`,
   `docs/skills/aitask-{pick/commit-attribution,refresh-code-models}.md`,
   `docs/tuis/board/how-to.md`.

5. **aidocs reference tables:**
   - `aitasks_extension_points.md` — touchpoint table (IDs from t835_2).
   - `model_reference_locations.md` — model registry + supported-agents tables (agy = `yes (limited)`).
   - `issue_type_vocabulary_duplication.md` — add `seed/agy_instructions.seed.md`.
   - `stub-skill-pattern.md` — §3g row; bump per-skill stub count from 3 to 4.

6. **Regenerate goldens.** Run
   `./.aitask-scripts/aitask_skill_rerender.sh <profile>` for each
   of default/fast/remote. Regenerate
   `tests/golden/procs/task-workflow/satisfaction-feedback-*.md`
   and any other affected goldens IN THE SAME COMMIT per CLAUDE.md.

7. **(Optional) blog post** at `website/content/blog/` announcing
   agy support — defer-able to t835_6 or a follow-up.

## Verification

- `cd website && ./serve.sh` — visually inspect each edited page.
- `./.aitask-scripts/aitask_skill_verify.sh` passes.
- `bash tests/test_*goldens*.sh` (or equivalent golden-diff suite) passes.
- `grep -rn "\bagy\b" website/content/docs/` shows agy consistently alongside codex where normative.
- `grep -rn "geminicli" website/content/docs/` returns nothing (verify t812_4 cleanup wasn't reintroduced).

## Step 9 reference

Standard task-workflow Step 9 archive after Step 8 approval.
