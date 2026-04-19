---
Task: t585_4_coherence_audit.md
Parent Task: aitasks/t585_better_frawework_desc_in_website.md
Sibling Tasks: aitasks/t585/t585_1_landing_page_redesign.md, aitasks/t585/t585_2_concepts_section.md, aitasks/t585/t585_3_overview_rewrite.md, aitasks/t585/t585_5_readme_revamp.md
Archived Sibling Plans: aiplans/archived/p585/p585_*_*.md
Worktree: aiwork/t585_4_coherence_audit
Branch: aitask/t585_4_coherence_audit
Base branch: main
plan_verified:
  - claudecode/opus4_7_1m @ 2026-04-19 15:49
---

# t585_4 — Coherence Audit + Conductor/Beads Removal Sweep

## Context

After t585_1 (landing), t585_2 (Concepts section), and t585_3 (Overview) restructured the website around the "agentic IDE in your terminal" positioning, two pockets of legacy framing remain:

1. The "Inspired by Conductor…and Beads…" sentence in `website/content/about/_index.md` (line 21).
2. The `docs/_index.md` tagline — "AI-powered task management for multi-agent development workflows" (line 10) — still frames the framework as task management rather than an agentic IDE.

This task sweeps those two spots and confirms the rest is clean.

## Verification Findings (pre-implementation)

Ran exhaustive grep + page-by-page review. Confirmed:
- **Conductor/Beads:** one occurrence — `about/_index.md:21`.
- **Speckit / spec-kit:** zero occurrences (t585_3 already removed from overview).
- **Narrative pages with positioning conflict:** only `docs/_index.md:10` (description field).
- **Other narrative pages** (`docs/getting-started.md`, `docs/workflows/_index.md`, `docs/skills/_index.md`, `docs/tuis/_index.md`, `docs/commands/_index.md`) — all have neutral or aligned framing; no edits required.
- **Concepts relrefs:** all 14 Concepts pages exist; `hugo --gc --minify` builds clean, no broken refs.

## Canonical Positioning Vocabulary (for consistency checks)

From archived sibling plans:
- "agentic IDE in your terminal" (primary)
- "long-term memory for agents" (via archived tasks/plans)
- "tight git coupling, AI-enhanced"
- "task decomposition & parallelism"
- "AI-enhanced code review"
- "multi-agent with verified scores"
- Supporting: "Light Spec", "living documents", "queryable context", "verified scores", "repository-centric"

## Implementation Plan

### Step 1 — Rewrite Conductor/Beads paragraph in `about/_index.md`

File: `website/content/about/_index.md` (lines 14–22 block, target line 21).

- Remove the entire "Inspired by [Conductor](...)'s repository-centric model and [Beads](...)'s task-based workflow, **aitasks** combined these ideas..." sentence.
- Rewrite the paragraph so the Light-Spec / repository-centric story stands on its own: keep the "tasks, plans, and workflow automation live inside the project repository — no external services, no databases, no daemons" framing (that content should survive — it's the positioning payload), but drop the external-framework attribution.
- Leave the preceding paragraphs (Intent Transfer Problem, Light Spec) untouched unless they now read oddly after the final paragraph is rewritten.
- Do not change creator bio, license, links, or other sections.

### Step 2 — Fix `docs/_index.md` description

File: `website/content/docs/_index.md` (line 10, the `description:` frontmatter field, plus any matching body copy if present).

- Replace "AI-powered task management for multi-agent development workflows" with a one-liner aligned to the new positioning. Candidate: "An agentic IDE in your terminal — task management, git-integrated workflows, code review, and multi-agent orchestration."
- Keep the one-line format; this is a section description, not a manifesto.

### Step 3 — Confirmation sweeps (verify, no edits expected)

Run:
- `Grep -rn "Conductor\|Beads" website/content/` → expect zero matches after Step 1.
- `Grep -rn "Speckit\|spec-kit" website/content/` → expect zero matches (already clean).

If either returns a non-zero result unexpectedly, investigate and either remove or document the exception in "Final Implementation Notes" before proceeding.

### Step 4 — Build verification

- `cd website && hugo --gc --minify` — strict build must pass with no broken refs and no template warnings.

### Step 5 — Spot-check pass (read-only)

Quickly re-skim these pages to confirm no surprise regressions introduced by edits:
- `website/content/about/_index.md` (edited)
- `website/content/docs/_index.md` (edited)
- `website/content/_index.md` (landing, unchanged — spot for tonal coherence)
- `website/content/docs/overview/_index.md` or equivalent (unchanged — tonal coherence)

No edits in this step; it only validates that Steps 1–2 landed cleanly.

## Critical Files

- `website/content/about/_index.md` — primary edit (Step 1)
- `website/content/docs/_index.md` — minor edit (Step 2)

## Verification

1. `Grep -rn "Conductor\|Beads" website/content/` — zero matches.
2. `Grep -rn "Speckit\|spec-kit" website/content/` — zero matches.
3. `cd website && hugo --gc --minify` — strict build passes.
4. Visual skim of `/about/`, `/docs/`, `/docs/overview/` via `./serve.sh` — tonal flow consistent with landing page.

## Step 9 (Post-Implementation)

Standard task-workflow Step 9: review → commit doc files using `git`, commit plan file using `./ait git`, archive with `./.aitask-scripts/aitask_archive.sh 585_4`, push.
