---
priority: medium
effort: medium
depends: [t585_2]
issue_type: documentation
status: Ready
labels: [web_site, positioning]
created_at: 2026-04-19 11:18
updated_at: 2026-04-19 11:18
---

## Context

Rewrite `website/content/docs/overview.md` to align with the new positioning ("A full agentic IDE in your terminal"), reflect the framework's actual scope, and remove all Conductor/Beads references that are now misleading.

This is child 3 of parent task t585. See parent plan `aiplans/p585_better_frawework_desc_in_website.md`. The new Overview links into the Concepts section (created by sibling t585_2) for conceptual deep-dives.

## Key Files to Modify

- `website/content/docs/overview.md` — full rewrite

## Reference Files for Patterns

- Sibling t585_1 (`aitasks/t585/t585_1_landing_page_redesign.md`) — for the canonical positioning and 6-theme breakdown
- Sibling t585_2 (`aitasks/t585/t585_2_concepts_section.md`) — for the list of Concepts pages to link into
- `aitasks/archived/t585/t585_*.md` — completed siblings (if any) — read their archived plan files in `aiplans/archived/p585/` for implementation context
- `website/content/docs/_index.md` — existing root docs intro
- `website/content/about/_index.md` — narrative tone reference

## Implementation Plan

1. **Reframe with the new positioning:**
   - Replace the existing "AI coding agents have reached…" intro with a tighter version anchored on "agentic IDE in your terminal" + the intent-transfer challenge.
   - Trim the "Core Philosophy" section. Keep the "Light Spec" framing but make it shorter and modern.
   - Consider removing the Speckit reference (line 17). The user has approved removing Conductor/Beads everywhere; Speckit is in the same family of misleading references — confirm with user during implementation if uncertain.

2. **Remove Conductor/Beads references:**
   - Delete the `(Inspired by Conductor)` parenthetical (line 24) and the `[Conductor](https://github.com/...)` hyperlink.
   - Delete the `(The [Beads](...) Evolution)` parenthetical (line 28) and the `[Beads]` hyperlink.
   - Reword the surrounding bullets so they stand on their own merits without the external scaffolding.

3. **Replace "Key Features & Architecture" with the 6-theme structure:**
   - Use the same 6 themes as the landing page (3 hero + 3 deep-dive):
     - Agentic IDE in your terminal (link to `concepts/ide-model/`)
     - Long-term memory for agents (link to `concepts/agent-memory/`)
     - Tight git coupling, AI-enhanced (link to `concepts/git-branching-model/` + workflow pages)
     - Task decomposition & parallelism (link to `concepts/parent-child/` + `workflows/task-decomposition/`)
     - AI-enhanced code review (link to `workflows/code-review/` + `concepts/review-guides/`)
     - Multi-agent support with verified scores (link to `concepts/agent-attribution/` + `concepts/verified-scores/`)
   - Each theme: short intro paragraph + 2-4 bullets of concrete capabilities + a "See also" line linking into Concepts/Workflows/Skills.

4. **Add coverage for currently-missing items:**
   - Codebrowser, Monitor, Brainstorm TUIs (currently overview only mentions Board + Code Browser).
   - Verified scores (currently absent).
   - Multi-agent crew model.

5. **Keep "Battle tested" + "Fully customizable workflow" closing bullets** but trim and modernize. The customizable-workflow bullet should still mention `/aitask-contribute`.

6. **Update the trailing "Next: Installation" link** if it conflicts with the new IA. Probably keep as-is.

## Style Rules

- Describe current state only — no "previously…" / "this used to be…" framing.
- Cross-references via `relref` — match the existing pattern at `docs/overview.md:43,49`.
- Concise. Overview is a navigation-and-orientation page, not a tutorial. Aim for ~80-120 lines max after rewrite.

## Verification Steps

1. `cd website && ./serve.sh` — site builds with no Hugo errors.
2. Open `http://localhost:1313/docs/overview/` — page renders cleanly.
3. Click each cross-reference into Concepts/Workflows/Skills — confirm they resolve. (If t585_2 is not yet merged, Concepts links may warn but should not break the build.)
4. `Grep -r "Conductor\|Beads"` against `website/content/docs/overview.md` — zero matches.
5. Confirm visual flow matches the landing page (consistent theme order, terminology).

## Step 9 (Post-Implementation)

Follow standard task-workflow Step 9: review → commit overview doc using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_3`, push.
