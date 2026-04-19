---
Task: t594_2_systemic_consistency_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,3,4,5,6}_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
---

# t594_2 — Systemic consistency sweep (cross-cutting)

## Context

Cross-cutting child of t594. Five concepts are documented in 3-4 pages each, with slightly different wording in each place. User chose **conservative dedup** — keep the repetitions, just align wording and fix two contradictions. This child runs independently of t594_1/3 and BEFORE t594_4/5/6 (which depend on it) so the canonical wording is set once.

## Scope

**In-bounds:**
- Align wording of repeated concepts across pages.
- Resolve two contradictions (profile requirement narrative, fast-profile behavior).
- Remove duplicate comparison table inside `aitask-pickweb.md`.

**Out-of-bounds:**
- Removing any repeated concept from secondary locations (conservative stance).
- Structural edits.
- Changes to shipped profile YAMLs or source scripts — **except** the `fast` profile contradiction fix which, by default resolution in the parent plan, updates the docs (not the YAML).

## Concrete target passages

### 1. TUI switcher `j` key — canonical sentence across 4+ pages

- `website/content/docs/getting-started.md:41`
- `website/content/docs/tuis/_index.md:27`
- `website/content/docs/installation/terminal-setup.md:38`
- `website/content/docs/workflows/tmux-ide.md:33`
- Plus any other `grep -rn "TUI switcher" website/content/` hits.

Choose one canonical sentence shape and replace all. Suggested: `Press **\`j\`** inside any main TUI to open the TUI switcher dialog and jump to another TUI.`

### 2. Install curl command — verbatim match across 3 pages

- `website/content/docs/installation/_index.md:8-26`
- `website/content/docs/getting-started.md:10-26`
- `website/content/docs/installation/windows-wsl.md:40-52`

**Authoritative source:** `install.sh` at repo root. Pull the exact curl URL + any flags from `install.sh` (or from its documented invocation). Ensure all three pages show byte-identical curl commands and the same `ait setup` follow-up.

### 3. "Run from project root" warning — unified phrasing across 3+ pages

- `website/content/docs/installation/_index.md:12`
- `website/content/docs/getting-started.md:20`
- `website/content/docs/skills/_index.md:14`

One-sentence shape, same across all locations.

### 4. Task file format intro — alignment between 2 pages

- `website/content/docs/concepts/tasks.md:8-10`
- `website/content/docs/development/task-format.md:7-10`

Both describe the same thing (location, naming, frontmatter). Align the overview sentences. Add an explicit line in `concepts/tasks.md` saying `development/task-format.md` is the full-schema authority. Do NOT remove the overview from `concepts/tasks.md`.

### 5. Pick variants (`/aitask-pick` vs `/aitask-pickrem` vs `/aitask-pickweb`) — unify step names

- `website/content/docs/skills/aitask-pick/_index.md`
- `website/content/docs/skills/aitask-pickrem.md`
- `website/content/docs/skills/aitask-pickweb.md`

All three describe similar step sequences with different step names. Unify step naming so a reader can map one to another. **Remove the duplicate comparison table** inside `aitask-pickweb.md` (identical tables at lines 26-48 and 38-46 — delete one).

### 6. Contradiction A — profile requirement narrative in `aitask-pickrem.md`

The comparison table correctly says "Required, auto-selected" for `/aitask-pickrem`. Elsewhere in the same page the prose describes profile as optional. Rewrite the prose to match the table.

**Source of truth:** `.claude/skills/aitask-pickrem/SKILL.md:23-24` — profile required.

### 7. Contradiction B — fast profile `post_plan_action`

- Docs: `skills/aitask-pick/_index.md:24` and `skills/aitask-pick/execution-profiles.md:14` describe the shipped `fast` profile as "stops after plan approval".
- YAML: `aitasks/metadata/profiles/fast.yaml:10` has `post_plan_action: ask` — it prompts, it does not auto-stop. This planning session itself experienced the prompt, confirming the YAML is ground truth.

**Default fix (per parent plan):** update the docs to "pauses for confirmation after plan approval" or similar. Do NOT change the YAML. If during implementation you conclude the YAML is wrong, flag it and ask — but the default is docs-first.

## Authoritative sources

| Claim | Source of truth |
|---|---|
| Install curl command | `install.sh` at repo root |
| fast profile behavior | `aitasks/metadata/profiles/fast.yaml` |
| `/aitask-pickrem` profile requirement | `.claude/skills/aitask-pickrem/SKILL.md` |
| `/aitask-pick` profile optionality | `.claude/skills/aitask-pick/SKILL.md` and `.claude/skills/task-workflow/execution-profile-selection.md` |

## Implementation plan

1. **Grep inventory:** `grep -rn "TUI switcher" website/content/docs/` → list all hits; pick canonical sentence; replace all.
2. **Curl command alignment:** read `install.sh`; extract the invocation; diff all 3 doc locations; align verbatim.
3. **Project-root warning:** unify one-sentence phrasing across all locations.
4. **Task-format intro:** align both pages' intro sentences; add the "see task-format.md for full schema" line in `concepts/tasks.md`.
5. **Pick variants:** unify step names across 3 pages. Delete one of the duplicate tables in `aitask-pickweb.md` (compare contents carefully — keep the one with more useful context, remove the other).
6. **Contradiction A:** rewrite the prose in `aitask-pickrem.md` to match the comparison table.
7. **Contradiction B:** update `skills/aitask-pick/_index.md:24` and `execution-profiles.md:14` fast-profile description to match `fast.yaml`'s `post_plan_action: ask` behavior.
8. **Hugo build check.**

## Verification

- `grep -rn "TUI switcher" website/content/docs/` — all hits share the same canonical phrasing.
- Curl commands byte-equal across the 3 install pages (`diff` them).
- Run `/aitask-pick --profile fast` through the plan step — the doc's description now matches observed behavior (a prompt appears after plan approval, not an auto-start).
- `grep -c "Required" website/content/docs/skills/aitask-pickrem.md` — the comparison table and the prose agree.
- `cd website && hugo build --gc --minify` succeeds.
- `aitask-pickweb.md` contains only one "Key Differences from /aitask-pick" table.

## Step 9 reference

Archive via `./.aitask-scripts/aitask_archive.sh 594_2` after Step 8 approval.
