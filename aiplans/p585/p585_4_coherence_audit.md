---
Task: t585_4_coherence_audit.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_1_landing_page_redesign.md, aitasks/t585/t585_2_concepts_section.md, aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_5_readme_revamp.md
Archived Sibling Plans: aiplans/archived/p585/p585_*_*.md
Worktree: aiwork/t585_4_coherence_audit
Branch: aitask/t585_4_coherence_audit
Base branch: main
---

# t585_4 — Coherence Audit + Conductor/Beads Removal Sweep

## Context

After siblings t585_1 (landing), t585_2 (concepts), and t585_3 (overview) restructure the website around the new "agentic IDE in your terminal" positioning, sweep the rest of the website docs for:

1. The remaining Conductor/Beads sentence on `about/_index.md`.
2. Any other narrative pages whose framing conflicts with the new positioning.
3. Confirm zero Conductor/Beads references in `website/content/`.

Parent context: `aiplans/p585_better_frawework_desc_in_website.md`. Read archived sibling plans (`aiplans/archived/p585/p585_*_*.md`) — they contain the canonical positioning copy and the conceptual structure to align against.

## Implementation Plan

### Step 1 — Update `website/content/about/_index.md`

The page currently mentions "Inspired by [Conductor]…and [Beads]…" on line 21. Action:

- Remove the entire sentence beginning "Inspired by [Conductor]…".
- Rewrite the surrounding "How aitasks Started" paragraph so the Light-Spec philosophy story stands on its own. Keep the Feb 2026 origin and the intent-transfer framing.
- Verify the rest of the page (creator bio, license, links) is consistent with the new positioning. No structural changes needed unless something jumps out.

### Step 2 — Audit narrative pages

Limit scope to **landing-page-adjacent narrative pages**. Do NOT re-edit per-skill / per-command / per-TUI reference pages just to insert positioning copy.

Pages to check:

- `website/content/docs/_index.md` — one-line description; update if it conflicts with the new positioning.
- `website/content/docs/getting-started.md` — only adjust the intro paragraph if its framing now feels off. Do NOT rewrite the walkthrough.
- `website/content/docs/workflows/_index.md`, `skills/_index.md`, `tuis/_index.md`, `commands/_index.md` — check intro paragraphs only; adjust if positioning conflicts. Likely a 1-2 line tweak each at most.

### Step 3 — Final removal sweep

- Run: `Grep -r "Conductor|Beads" website/content/`
  Confirm zero matches.
- (If t585_3 chose to remove Speckit too): `Grep -r "Speckit|spec-kit" website/content/` — confirm zero matches. If t585_3 left Speckit, leave it.

### Step 4 — Coherence checks

- Confirm theme terminology is reused consistently across landing/overview/about (e.g., "agentic IDE", "long-term memory", "verified scores").
- Confirm all `relref` links into the new Concepts section resolve (they should, since t585_2 has merged by the time this child runs).

## Critical Files

- `website/content/about/_index.md` — primary edit
- `website/content/docs/_index.md` — minor edit (one line)
- `website/content/docs/getting-started.md` — minor intro tweak only if needed
- `website/content/docs/{workflows,skills,tuis,commands}/_index.md` — minor intro tweaks only if needed

## Existing Patterns to Reuse

- About page structure (cover → narrative → lead → 3-feature row → narrative → table → 3-link row) — preserve, only edit the narrative paragraph that contains the Conductor/Beads sentence.

## Verification

1. `Grep -rn "Conductor\|Beads" website/content/` — zero matches.
2. (If applicable): `Grep -rn "Speckit\|spec-kit" website/content/` — zero matches.
3. `cd website && hugo --gc --minify` — strict build passes with no broken refs.
4. `./serve.sh` and visit `/about/`, `/docs/`, `/docs/overview/` — visual flow consistent with the redesigned landing page.
5. Spot-check 3-5 narrative pages for tonal consistency.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit doc files using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_4`, push.
