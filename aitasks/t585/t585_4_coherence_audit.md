---
priority: medium
effort: medium
depends: [t585_3]
issue_type: documentation
status: Ready
labels: [web_site, positioning]
created_at: 2026-04-19 11:18
updated_at: 2026-04-19 11:18
---

## Context

After the landing page (t585_1), Concepts section (t585_2), and Overview (t585_3) are restructured around the new "agentic IDE in your terminal" positioning, sweep the rest of the website docs for:

1. Remaining Conductor/Beads/Speckit references that conflict with the new positioning.
2. Outdated framing (e.g., "tasks are just a kanban tool" vs. "agentic IDE").
3. Inconsistencies with the new theme structure.

This is child 4 of parent task t585. See parent plan `aiplans/p585_better_frawework_desc_in_website.md`. Read the **archived plan files** for completed siblings (`aiplans/archived/p585/p585_1_*.md`, `p585_2_*.md`, `p585_3_*.md`) — they contain the canonical positioning copy and conceptual structure to align against.

## Key Files to Modify

- `website/content/about/_index.md` — primary edit (still has Conductor/Beads inspiration sentence)
- `website/content/docs/_index.md` — one-line description, only if it conflicts with new positioning
- Other `website/content/docs/**/*.md` files — only if narrative framing conflicts. **Do NOT** re-edit reference pages just to insert positioning copy.

## Reference Files for Patterns

- Archived sibling plans `aiplans/archived/p585/p585_1_*.md`, `p585_2_*.md`, `p585_3_*.md` — primary reference for positioning, theme structure, and link patterns
- `website/content/about/_index.md` lines 17-22 — current "How aitasks Started" section with Conductor/Beads inspiration

## Implementation Plan

1. **Update `website/content/about/_index.md`:**
   - Remove the "Inspired by [Conductor]…and [Beads]…" sentence (line 21).
   - Rewrite the "How aitasks Started" section to stand on its own — the Light-Spec philosophy story doesn't need the external scaffolding. Keep the Feb 2026 origin and the intent-transfer framing.
   - Verify the rest of the page (creator bio, license, links) is consistent with the new positioning.

2. **Audit narrative pages for positioning conflicts:**
   - `docs/_index.md` — update the one-line description if it still says "AI-powered task management for code agents" or similar.
   - `docs/getting-started.md` — only adjust the intro paragraph if its framing now feels off; do NOT rewrite the walkthrough.
   - `docs/workflows/_index.md`, `docs/skills/_index.md`, `docs/tuis/_index.md`, `docs/commands/_index.md` — check intro paragraphs only; adjust if positioning conflicts.
   - Limit scope: do NOT touch reference pages (per-skill, per-command, per-TUI pages) just to insert positioning copy.

3. **Final Conductor/Beads/Speckit removal sweep:**
   - Run: `Grep -r "Conductor\|Beads\|Speckit\|spec-kit" website/content/`
   - Confirm zero matches in `website/content/`. If t585_3 chose to keep Speckit, leave it; otherwise remove.

4. **Coherence checks (light):**
   - Confirm theme terminology used in landing/overview is reused consistently (e.g., "agentic IDE", "long-term memory", "multi-agent verified scores").
   - Confirm all "Concepts" section links from sibling tasks resolve (no broken `relref`).

## Verification Steps

1. `Grep -r "Conductor\|Beads" website/content/` — zero matches.
2. (If Speckit was decided for removal in t585_3): `Grep -r "Speckit\|spec-kit" website/content/` — zero matches.
3. `cd website && hugo --gc --minify` — strict build passes with no broken refs.
4. `./serve.sh` and visit `/about/`, `/docs/`, `/docs/overview/` — visual flow consistent with landing page.
5. Spot-check 3-5 narrative pages for tonal consistency.

## Step 9 (Post-Implementation)

Follow standard task-workflow Step 9: review → commit doc files using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_4`, push.
