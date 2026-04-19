---
Task: t594_2_systemic_consistency_sweep.md
Parent Task: aitasks/t594_website_documentation_coherence.md
Parent Plan: aiplans/p594_website_documentation_coherence.md
Sibling Tasks: aitasks/t594/t594_{1,3,4,5,6}_*.md
Worktree: (none — work on current branch)
Branch: main
Base branch: main
plan_verified_at: 2026-04-19 (pending append via aitask_plan_verified.sh)
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 18:51
---

# t594_2 — Systemic consistency sweep (cross-cutting) — VERIFIED

## Context

Cross-cutting child of t594. Five concepts are documented in 3-4 pages each, with slightly different wording in each place. User chose **conservative dedup** — keep the repetitions, just align wording and fix actual contradictions. Runs before t594_4/5/6 so canonical wording is set once.

This plan was **re-verified against the current codebase on 2026-04-19** (see Verification Updates section at bottom). Four of the original seven items had drifted from reality and have been dropped or re-scoped.

## Scope

**In-bounds:**
- Align wording of repeated concepts across pages.
- Fix the one real contradiction (fast-profile behavior).

**Out-of-bounds:**
- Removing any repeated concept from secondary locations (conservative stance).
- Structural edits.
- Changes to shipped profile YAMLs or source scripts — the `fast` profile contradiction fix updates the docs, not the YAML.

## Concrete target passages (post-verification)

### 1. TUI switcher `j` key — canonical short sentence across cross-cutting pages

**Canonical short sentence** (for brief mentions in cross-cutting pages):

> Press **`j`** inside any main TUI to open the **TUI switcher** dialog and jump to another TUI.

Apply to cross-cutting pages (non-TUI section) where a brief mention appears:

- `website/content/docs/getting-started.md:41` — currently includes explicit TUI list; shorten to canonical sentence + one clause about target TUIs if needed.
- `website/content/docs/installation/terminal-setup.md:38` — currently lists TUIs inline; align to canonical.
- `website/content/docs/workflows/tmux-ide.md:33` — currently describes what the dialog lists; align narrative wrap but preserve the "Select **board**" context-specific step.

**Preserve verbatim** (already set canonically by t594_1 — do NOT rewrite):

- `website/content/docs/tuis/_index.md:27` — authoritative long-form phrasing (mentions Monitor/Board/Code Browser/Settings + git TUI + dynamic agent/brainstorm windows).
- `website/content/docs/tuis/monitor/_index.md:67`, `tuis/monitor/how-to.md:85`, `tuis/minimonitor/how-to.md:88`, `tuis/board/how-to.md:323`, `tuis/codebrowser/how-to.md:201`, `tuis/settings/how-to.md:154` — t594_1 already normalized TUI-page phrasing; leave alone.

Other hits found (`grep -rn "TUI switcher" website/content/`): `tuis/monitor/reference.md:38,166-168`, `tuis/minimonitor/_index.md:27,40`, `workflows/tmux-ide.md:5,29,65,80`, `installation/terminal-setup.md:82,90`. These are short references inside tables or "see also" sections — do not touch unless they actually contradict the canonical sentence.

### 2. Install curl command — verbatim verification across 3 pages

**Authoritative source:** `install.sh:5` — `curl -fsSL https://raw.githubusercontent.com/beyondeye/aitasks/main/install.sh | bash`.

Spot-verify byte-equality at:

- `website/content/docs/installation/_index.md:17`
- `website/content/docs/getting-started.md:17`
- `website/content/docs/installation/windows-wsl.md:43`

Pre-verification check (2026-04-19) shows all three match the authoritative source. If the follow-up `ait setup` step differs in framing, align to one shape — but do NOT replace the surrounding narrative. This item is near-trivial after verification; keep as a safety check.

### 3. "Run from project root" warning — unified one-sentence shape across 3 pages

Current wordings:

- `installation/_index.md:12` — long admonition block (3 sentences of justification).
- `getting-started.md:20` — similar long admonition (4 sentences, different phrasing).
- `skills/_index.md:14` — shorter admonition focused on skills/paths (2 sentences).

Choose one canonical **lead sentence** shape and use it verbatim across all three locations. Keep the context-specific trailing justification per page (why it matters differs: installer paths vs agent relative paths). Suggested canonical lead: `**Run from the project root.** aitasks expects to be invoked from the directory containing \`.git/\` — the root of your project's git repository.` Then append the page-specific justification sentence.

### 4. Task file format intro — alignment between 2 pages

- `website/content/docs/concepts/tasks.md:8-10` — opens with "A **task** is a single markdown file in `aitasks/`..."
- `website/content/docs/development/task-format.md:7-10` — opens with "Tasks are markdown files with YAML frontmatter..."

Align the two intro sentences so the shared facts (location, naming, frontmatter + body) appear in the same order and similar wording. `concepts/tasks.md:18` already says "The complete frontmatter schema and worked examples live in the [Task File Format reference]..." — **no new cross-reference line needed**. Just tidy the opening sentences.

### 5. Pick variants (`/aitask-pick` vs `/aitask-pickrem` vs `/aitask-pickweb`) — unify step names only

- `website/content/docs/skills/aitask-pick/_index.md` — Step-by-Step uses labels: Profile selection, Task selection, Child task handling, Status checks, Assignment, Environment setup, Planning, Implementation, User review, Post-implementation.
- `website/content/docs/skills/aitask-pickrem.md` — uses: Initialize data branch, Load execution profile, Resolve task file, Sync with remote, Task status checks, Assign task, Environment setup, Create implementation plan, Implement and auto-commit, Archive and push.
- `website/content/docs/skills/aitask-pickweb.md` — uses: Initialize data branch, Load execution profile, Resolve task file, Read-only lock check, Task status checks, Create implementation plan, Implement, Auto-commit, Write completion marker.

Unify step names so a reader can map them across pages. Use the **core-operation label** (e.g., "Profile selection" / "Task resolution" / "Task status checks" / "Environment setup" / "Planning" / "Implementation" / "Review and commit" / "Post-implementation") as the shared vocabulary, then append `/aitask-pick`-specific or remote-specific qualifiers in parentheses where needed. Leave the pickweb and pickrem variant-specific steps (Initialize data branch, Sync with remote, Read-only lock check, Write completion marker) in place — they really are different, not just worded differently.

**Duplicate-table claim dropped:** The original plan claimed `aitask-pickweb.md` contained identical tables at lines 26-48 and 38-46. Verification (2026-04-19) confirms this is **not** the case: lines 28-36 compare pickweb-vs-pickrem, lines 40-48 compare pickweb-vs-pick. Different rows, different purposes. No deletion needed.

### 6. ~~Contradiction A — pickrem profile requirement~~ (DROPPED after verification)

Claim in original plan: "comparison table correctly says 'Required, auto-selected'... Elsewhere in the same page the prose describes profile as optional."

**Verification (2026-04-19)** of `website/content/docs/skills/aitask-pickrem.md`:

- Line 8: "all decisions are driven by an execution profile" — consistent with required.
- Line 32 (comparison row): "Required, auto-selected" — matches source of truth.
- Line 37 (Step 2): "Profile is required — aborts if none found" — consistent.
- Line 53: "Remote mode **requires** a profile — without one, the skill aborts." — consistent.

No contradictory prose remains. Drop this item.

### 7. Contradiction B — fast profile `post_plan_action` (FIX, cited locations updated)

**Ground truth:** `aitasks/metadata/profiles/fast.yaml:10` has `post_plan_action: ask` — the fast profile **prompts** after plan approval, it does not auto-stop. (The current planning session experienced the prompt, confirming the YAML.)

**Doc locations with the wrong claim** (re-verified 2026-04-19 — original plan citations were stale):

- `website/content/docs/concepts/execution-profiles.md:17` — table row: `| \`fast\` | Minimal prompts — skip confirmations, use the existing plan when present, stop after plan approval. |`
- `website/content/docs/skills/aitask-pick/execution-profiles.md:15` — bullet list: `- **fast** -- Skip confirmations, use userconfig email, stay on the current branch, stop after plan approval, and keep feedback questions enabled`

**Original plan cited `skills/aitask-pick/_index.md:24` which does NOT contain this text** (the `_index.md` description of fast is at the high level and does not mention post-plan behavior). Ignore the stale citation.

**Fix:** replace `stop after plan approval` with `pause for confirmation after plan approval` in both locations. Do NOT change `fast.yaml`.

## Authoritative sources

| Claim | Source of truth |
|---|---|
| Install curl command | `install.sh:5` |
| fast profile behavior | `aitasks/metadata/profiles/fast.yaml` |
| `/aitask-pickrem` profile requirement | `.claude/skills/aitask-pickrem/SKILL.md` |
| `/aitask-pick` profile optionality | `.claude/skills/aitask-pick/SKILL.md` and `.claude/skills/task-workflow/execution-profile-selection.md` |
| TUI switcher canonical long-form | `website/content/docs/tuis/_index.md:27` (set by t594_1) |
| Task file format authority | `website/content/docs/development/task-format.md` |

## Implementation plan (post-verification)

1. **TUI switcher `j`:** Apply canonical short sentence to cross-cutting pages `getting-started.md:41`, `installation/terminal-setup.md:38`, `workflows/tmux-ide.md:33` (preserving context-specific trailing clauses). Do NOT touch t594_1-normalized TUI pages.
2. **Curl command:** Spot-verify byte-equality across the 3 install pages; align follow-up `ait setup` framing if it differs.
3. **Project-root warning:** Choose canonical lead sentence; apply to `installation/_index.md:12`, `getting-started.md:20`, `skills/_index.md:14`, keeping per-page trailing justifications.
4. **Task-format intro:** Align opening sentences in `concepts/tasks.md:8-10` and `development/task-format.md:7-10`. The cross-reference at `concepts/tasks.md:18` already exists.
5. **Pick variants step names:** Adjust step labels in `skills/aitask-pick/_index.md`, `skills/aitask-pickrem.md`, `skills/aitask-pickweb.md` so the shared core operations use the same label. Do NOT delete any table — verification confirmed no duplicate table exists.
6. **Contradiction A:** Dropped per verification.
7. **Contradiction B:** Replace "stop after plan approval" with "pause for confirmation after plan approval" in `concepts/execution-profiles.md:17` and `skills/aitask-pick/execution-profiles.md:15`.
8. **Hugo build check:** `cd website && hugo build --gc --minify` — no warnings.

## Verification

- `grep -rn "TUI switcher" website/content/docs/` — cross-cutting pages now use the canonical short sentence; TUI pages (t594_1's scope) untouched.
- `diff <(grep -A2 "curl" website/content/docs/installation/_index.md) <(grep -A2 "curl" website/content/docs/getting-started.md)` — curl commands and `ait setup` follow-up match.
- `grep -rn "stop after plan approval" website/content/docs/` returns **no hits** after the fix.
- `grep -rn "pause for confirmation after plan approval" website/content/docs/` returns the 2 fixed locations.
- `grep -c "Required" website/content/docs/skills/aitask-pickrem.md` — unchanged; baseline was already correct.
- `cd website && hugo build --gc --minify` succeeds (baseline: 0 warnings on 2026-04-19).
- Step-name scan: `grep -E "^[0-9]+\. \*\*" website/content/docs/skills/aitask-pick*` shows consistent core-operation labels across the 3 pages.

## Step 9 reference

No worktree (`create_worktree: false`). `verify_build` in `project_config.yaml` is null, so Hugo build verification is this task's responsibility (run before committing). Archive via `./.aitask-scripts/aitask_archive.sh 594_2` after Step 8 approval.

## Verification Updates (2026-04-19)

Performed during plan verification before implementation (fast-profile `plan_preference_child: verify`). Changes from the pre-verification plan:

- **Item 4:** Removed "add explicit cross-reference line" sub-step — `concepts/tasks.md:18` already has it.
- **Item 5:** Removed "delete duplicate table" sub-step — the two tables in `aitask-pickweb.md` (lines 28-36 and 40-48) are not duplicates; they compare against different skills.
- **Item 6:** Dropped entirely — pickrem.md prose is internally consistent; no contradiction exists.
- **Item 7:** Re-cited target locations — the wrong text lives at `concepts/execution-profiles.md:17` and `skills/aitask-pick/execution-profiles.md:15`, not at `skills/aitask-pick/_index.md:24` as originally claimed.
- **Item 1:** Narrowed scope to cross-cutting pages; t594_1 already normalized the TUI section, so those pages should not be rewritten.

Implementing agent (for `plan_verified` append): recorded via Model Self-Detection at externalization time.
